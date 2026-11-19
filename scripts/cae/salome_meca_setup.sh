#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /
IFS= read -r linux_user < /root/wsl-manager-user
user_home=$(getent passwd "$linux_user" | cut -d: -f6)
test -d "$user_home"
apt-get -o Acquire::Retries=5 -o APT::Update::Error-Mode=any update
apt-get -o Acquire::Retries=5 install -y --no-install-recommends ca-certificates curl squashfs-tools fuse3
pkg=/var/tmp/apptainer_1.4.5_amd64.deb
if ! command -v apptainer >/dev/null; then
    curl -fLsS --retry 5 https://github.com/apptainer/apptainer/releases/download/v1.4.5/apptainer_1.4.5_amd64.deb -o "$pkg"
    echo "70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05  $pkg" | sha256sum -c -
    apt-get -o Acquire::Retries=5 install -y "$pkg"
fi
base=salome_meca-lgpl-2025.1.0-1-20251026-scibian-12
IFS= read -r source < /root/salome-meca-source
runuser -u "$linux_user" -- env HOME="$user_home" bash -e -c '
    mkdir -p "$HOME/containers"
    cd "$HOME/containers"
    if [[ ! -f "$1.sif" ]]; then
        cp -- "$2" "$1.sif.part"
        apptainer sif list "$1.sif.part" >/dev/null
        mv "$1.sif.part" "$1.sif"
    fi
    apptainer run --app install "./$1.sif"
    test -x "./$1"
' bash "$base" "$source"
printf '#!/bin/sh\nexec "%s/containers/%s" "$@"\n' "$user_home" "$base" > /usr/local/bin/salome-meca
chmod 755 /usr/local/bin/salome-meca
