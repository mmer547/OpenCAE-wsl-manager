#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y calculix-ccx calculix-cgx
command -v ccx >/dev/null
command -v cgx >/dev/null

id cae >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cae
printf '[user]\ndefault=cae\n' > /etc/wsl.conf
