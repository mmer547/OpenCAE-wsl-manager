#!/bin/bash
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /
IFS= read -r linux_user < /root/wsl-manager-user
user_home=$(getent passwd "$linux_user" | cut -d: -f6)
test -d "$user_home"
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl
install -d -m 0755 /etc/apt/keyrings
curl --fail --location --silent --show-error --retry 3 https://dl.openfoam.org/gpg.key -o /etc/apt/keyrings/openfoam.asc.tmp
install -m 0644 /etc/apt/keyrings/openfoam.asc.tmp /etc/apt/keyrings/openfoam.asc
rm /etc/apt/keyrings/openfoam.asc.tmp
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/openfoam.asc] https://dl.openfoam.org/ubuntu noble main' > /etc/apt/sources.list.d/openfoam.list
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends openfoam12
init='source /opt/openfoam12/etc/bashrc'
grep -Fxq "$init" "$user_home/.bashrc" || echo "$init" >> "$user_home/.bashrc"
runuser -u "$linux_user" -- env HOME="$user_home" bash -c '
    cd "$HOME" || exit 1
    source /opt/openfoam12/etc/bashrc
    test "$WM_PROJECT_VERSION" = 12 && blockMesh -help >/dev/null && foamRun -help >/dev/null
'
