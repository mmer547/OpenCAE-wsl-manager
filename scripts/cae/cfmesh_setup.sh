#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /

IFS= read -r linux_user < /root/wsl-manager-user
user_home=$(getent passwd "$linux_user" | cut -d: -f6)
as_user=(runuser -u "$linux_user" -- env HOME="$user_home")

# The version chooser and the regular checkboxes both install to these paths.
projects=()
for project in /usr/lib/openfoam/openfoam[0-9][0-9][0-9][0-9]; do
    version=${project##*/openfoam}
    if [[ -f "$project/etc/bashrc" && "$version" =~ ^[0-9]{2}(06|12)$ ]] && (( 10#$version >= 2406 )); then
        projects+=("$project")
    fi
done

apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
if [[ ${#projects[@]} -eq 0 ]]; then
    apt-get install -y --no-install-recommends ca-certificates curl libpciaccess0 zlib1g
    temp=$(mktemp -d)
    trap 'rm -rf "$temp"' EXIT
    archive="$temp/cfMesh-1.2.0-binaries.tgz"
    curl -fLsS --retry 3 https://downloads.sourceforge.net/project/cfmesh/1.2.0/cfMesh-1.2.0-binaries.tgz -o "$archive"
    printf '%s  %s\n' e0cefb7126e821c0759bc5f69777e7905dcfd7e5fa80548c503ea08d15060a3a "$archive" | sha256sum -c -
    mkdir -p /opt
    tar --no-same-owner --same-permissions -xzf "$archive" -C /opt
    "${as_user[@]}" /opt/cfMesh-1.2.0/bin/cartesianMesh -help >/dev/null
    "${as_user[@]}" bash -s <<'CONFIGURE'
line='export PATH="$PATH:/opt/cfMesh-1.2.0/bin"'
grep -Fqx "$line" "$HOME/.bashrc" || printf '\n%s\n' "$line" >> "$HOME/.bashrc"
CONFIGURE
    exit 0
fi

apt-get install -y --no-install-recommends build-essential ca-certificates curl git python3
for project in "${projects[@]}"; do
    version=${project##*/openfoam}
    # Use the cfmesh gitlink of the matching OpenFOAM release. The default
    # branch of integration-cfmesh predates the API changes in v2506.
    url="https://gitlab.com/api/v4/projects/openfoam%2Fcore%2Fopenfoam/repository/tree"
    revision=$(curl -fLsS --retry 3 "$url?path=plugins&per_page=100&ref=OpenFOAM-v$version" |
        python3 -c '
import json, re, sys
for entry in json.load(sys.stdin):
    if entry["path"] == "plugins/cfmesh" and entry["type"] == "commit" and re.fullmatch("[0-9a-f]{40}", entry["id"]):
        print(entry["id"])
        break
else:
    sys.exit("OpenFOAM リリースに対応する cfMesh のコミットが見つかりません。")')
    "${as_user[@]}" bash -s -- "$project/etc/bashrc" "$version" "$revision" <<'BUILD'
foam_bashrc=$1
expected_version=$2
revision=$3
set --
cd "$HOME" || exit 1
source "$foam_bashrc" || exit 1
set -euo pipefail
if [[ "${WM_PROJECT_VERSION#v}" != "$expected_version" ]]; then
    echo "cfMesh に必要な OpenFOAM v$expected_version を読み込めませんでした。" >&2
    exit 1
fi

mkdir -p "$WM_PROJECT_USER_DIR/modules"
cd "$WM_PROJECT_USER_DIR/modules"
remote=https://gitlab.com/openfoam/community/cfmesh.git
if [[ ! -d integration-cfmesh/.git ]]; then
    git clone --no-checkout "$remote" integration-cfmesh
fi
cd integration-cfmesh
if [[ "$(git remote get-url origin)" != "$remote" ]]; then
    echo "$PWD の取得元が cfMesh の公式リポジトリと一致しません。" >&2
    exit 1
fi
if ! git cat-file -e "$revision^{commit}"; then
    git fetch origin "$revision"
fi
git checkout --detach "$revision"
jobs=$(nproc)
if (( jobs > 2 )); then jobs=2; fi
if ! ./Allwmake -j"$jobs" > log.Allwmake 2>&1; then
    tail -n 25 log.Allwmake >&2
    exit 1
fi
if [[ ! -s "$FOAM_USER_LIBBIN/libmeshLibrary.so" || "$(command -v cartesianMesh)" != "$FOAM_USER_APPBIN/cartesianMesh" ]]; then
    echo "OpenFOAM $WM_PROJECT_VERSION 用の cfMesh がユーザー領域に生成されませんでした。" >&2
    tail -n 12 log.Allwmake >&2
    exit 1
fi
command -v cartesianMesh
cartesianMesh -help >/dev/null
BUILD
done
