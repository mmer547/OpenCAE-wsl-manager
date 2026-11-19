#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
fingerprint=5DE86CC050F6623BBA7995B864CE41328E03B30A
keydir=$(mktemp -d)
key="$keydir/download.asc"
trap 'rm -rf -- "$keydir"' EXIT
curl -fsSL --retry 3 "https://build.openmodelica.org/apt/openmodelica.asc" -o "$key"
gpg --batch --homedir "$keydir" --import "$key"
gpg --batch --homedir "$keydir" --armor --export "$fingerprint" > "$keydir/signer.asc"
test -s "$keydir/signer.asc"
install -Dm644 "$keydir/signer.asc" /etc/apt/keyrings/openmodelica.asc
echo 'deb [signed-by=/etc/apt/keyrings/openmodelica.asc] https://build.openmodelica.org/apt noble stable' > /etc/apt/sources.list.d/openmodelica.list
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y omc omedit omlibrary
omc --version
command -v OMEdit
