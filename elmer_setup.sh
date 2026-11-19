#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
fingerprint=1FE4A88ACFEE8388A409F23A89358ABF9FB7E178
key=$(mktemp)
trap 'rm -f "$key"' EXIT
curl -fsSL --retry 3 "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x$fingerprint" -o "$key"
actual=$(gpg --batch --show-keys --with-colons "$key" | awk -F: '$1=="pub"{primary=1; next} primary && $1=="fpr"{print $10; primary=0}')
test "$actual" = "$fingerprint"
install -Dm644 "$key" /etc/apt/keyrings/elmer.asc
echo 'deb [signed-by=/etc/apt/keyrings/elmer.asc] https://ppa.launchpadcontent.net/elmer-csc-ubuntu/elmer-csc-ppa/ubuntu noble main' > /etc/apt/sources.list.d/elmer.list
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y elmerfem-csc
command -v ElmerSolver >/dev/null
command -v ElmerGrid >/dev/null
