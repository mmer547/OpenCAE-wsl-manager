#!/bin/bash
# Called by an edition-specific setup script in the same directory.
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /
case "$1" in
    foundation)
        repo=https://dl.openfoam.org/ubuntu
        key=https://dl.openfoam.org/gpg.key
        pattern='openfoam([1-9][0-9]?)$'
        suffix=''
        base=/opt
        ;;
    keysight)
        repo=https://dl.openfoam.com/repos/deb
        key=https://dl.openfoam.com/pubkey.gpg
        pattern='openfoam([0-9]{2}(06|12))-default$'
        suffix=-default
        base=/usr/lib/openfoam
        ;;
    *) exit 2 ;;
esac
source_file=/etc/apt/sources.list.d/openfoam-"$1".list
keyring=/etc/apt/keyrings/openfoam-"$1".asc
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends curl ca-certificates
stage=$(mktemp)
trap 'rm -f "$stage"' EXIT
curl -fsSL --retry 3 "$key" -o "$stage"
install -Dm644 "$stage" "$keyring"
printf 'deb [arch=amd64 signed-by=%s] %s noble main\n' "$keyring" "$repo" > "$source_file"
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update

# Read the authenticated Packages index retained by APT for this source.
index=$(apt-get -o Dir::Etc::sourcelist="$source_file" -o Dir::Etc::sourceparts=- \
    indextargets --format '$(FILENAME)' 'Identifier: Packages' 'Architecture: amd64')
test -f "$index"
version=$(/usr/lib/apt/apt-helper cat-file "$index" |
    awk -v RS='' '!/(^|\n)Version: [^\n]*~/' |
    sed -nE "s/^Package: $pattern/\\1/p" | sort -nu | tail -1)
if [[ -z "$version" ]]; then
    echo "$repo: Ubuntu 24.04 用の正式リリースが見つかりません。" >&2
    exit 1
fi
apt-get install -y "openfoam${version}${suffix}"
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
