#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
fingerprint=9F0E375806520BD65BC61B18A728AE60A790F0EB
key=$(mktemp)
trap 'rm -f "$key"' EXIT
curl -fsSL --retry 3 "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$fingerprint" -o "$key"
actual=$(gpg --batch --show-keys --with-colons "$key" | awk -F: '$1=="pub"{primary=1; next} primary && $1=="fpr"{print $10; primary=0}')
test "$actual" = "$fingerprint"
install -Dm644 "$key" /etc/apt/keyrings/freecad.asc
echo 'deb [signed-by=/etc/apt/keyrings/freecad.asc] https://ppa.launchpadcontent.net/freecad-maintainers/freecad-stable/ubuntu noble main' > /etc/apt/sources.list.d/freecad.list
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y freecad
command -v freecad
dpkg-query -W freecad-python3
