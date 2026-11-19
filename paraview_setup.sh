#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y paraview
QT_QPA_PLATFORM=offscreen paraview --version

id cae >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cae
printf '[user]\ndefault=cae\n' > /etc/wsl.conf
