#!/bin/bash
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl
install -d -m 0755 /etc/apt/keyrings
curl --fail --location --silent --show-error --retry 3 https://dl.openfoam.org/gpg.key -o /etc/apt/keyrings/openfoam.asc.tmp
install -m 0644 /etc/apt/keyrings/openfoam.asc.tmp /etc/apt/keyrings/openfoam.asc
rm /etc/apt/keyrings/openfoam.asc.tmp
echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/openfoam.asc] https://dl.openfoam.org/ubuntu noble main' > /etc/apt/sources.list.d/openfoam.list
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends openfoam12
if ! id cae >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash cae
fi
init='source /opt/openfoam12/etc/bashrc'
grep -Fxq "$init" /home/cae/.bashrc || echo "$init" >> /home/cae/.bashrc
runuser -u cae -- env HOME=/home/cae bash -c '
    cd "$HOME" || exit 1
    source /opt/openfoam12/etc/bashrc
    test "$WM_PROJECT_VERSION" = 12 && blockMesh -help >/dev/null && foamRun -help >/dev/null
'
# This file belongs to the fresh Ubuntu Base image imported by the manager.
printf '[user]\ndefault=cae\n' > /etc/wsl.conf
