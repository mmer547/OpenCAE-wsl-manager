#!/bin/bash
# Called by an edition-specific setup script in the same directory.
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /
case "$1" in foundation|keysight) ;; *) exit 2 ;; esac
selection="/root/openfoam_$1.version"
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends curl ca-certificates
stage=$(mktemp)
trap 'rm -f "$stage"' EXIT
case "$1" in
    keysight)
        # The upstream repository script configures the key and source for this Ubuntu release.
        curl -fsSL --retry 3 https://dl.openfoam.com/add-debian-repo.sh -o "$stage"
        bash "$stage"
        apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
        version=2606
        if [[ -f "$selection" ]]; then IFS= read -r version < "$selection"; fi
        [[ "$version" =~ ^[0-9]{2}(06|12)$ ]] || { echo "Keysight の版番号が不正です: $version" >&2; exit 1; }
        package="openfoam${version}-default"
        base=/usr/lib/openfoam
        ;;
    foundation)
        source_file=/etc/apt/sources.list.d/openfoam-foundation.list
        keyring=/etc/apt/keyrings/openfoam-foundation.asc
        curl -fsSL --retry 3 https://dl.openfoam.org/gpg.key -o "$stage"
        install -Dm644 "$stage" "$keyring"
        printf 'deb [arch=amd64 signed-by=%s] https://dl.openfoam.org/ubuntu noble main\n' "$keyring" > "$source_file"
        apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
        index=$(apt-get -o Dir::Etc::sourcelist="$source_file" -o Dir::Etc::sourceparts=- \
            indextargets --format '$(FILENAME)' 'Identifier: Packages' 'Architecture: amd64')
        test -f "$index"
        releases=$(/usr/lib/apt/apt-helper cat-file "$index" |
            awk -v RS='' '!/(^|\n)Version: [^\n]*~/' |
            sed -nE 's/^Package: openfoam([1-9][0-9]?)$/\1/p' | sort -nu)
        if [[ -f "$selection" ]]; then
            IFS= read -r version < "$selection"
        else
            version=$(tail -1 <<< "$releases")
        fi
        if [[ -z "$version" ]] || ! grep -Fxq -- "$version" <<< "$releases"; then
            echo "Foundation の正式版 ($version) が Ubuntu 24.04 のパッケージ一覧にありません。" >&2
            exit 1
        fi
        package="openfoam${version}"
        base=/opt
        ;;
esac
apt-get install -y "$package"
envfile="$base/openfoam$version/etc/bashrc"
IFS= read -r linux_user < /root/wsl-manager-user
user_home=$(getent passwd "$linux_user" | cut -d: -f6)
runuser -u "$linux_user" -- env HOME="$user_home" bash -c '
    foam_bashrc=$1
    expected_version=$2
    # OpenFOAM treats positional arguments as additional files to source.
    set --
    cd "$HOME" && source "$foam_bashrc" && test "${WM_PROJECT_VERSION#v}" = "$expected_version" && blockMesh -help >/dev/null
' bash "$envfile" "$version"
if ! grep -Eq '^(source|\.) (/opt/openfoam|/usr/lib/openfoam/).*etc/bashrc$' "$user_home/.bashrc"; then
    printf 'source %s\n' "$envfile" >> "$user_home/.bashrc"
fi
