#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl unzip python3 python3-numpy python3-scipy
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
curl -fLsS --retry 3 https://github.com/su2code/SU2/releases/download/v8.6.0/SU2_v8.6.0_linux64-omp.zip -o "$archive"
echo "b306dcb7e76caec54e376542916aae14a32abd6c2f6fa8b871ec10ffe80b41ac  $archive" | sha256sum -c -
unzip -oq "$archive" -d /opt/su2-8.6.0
for tool in SU2_CFD SU2_DEF SU2_DOT SU2_GEO SU2_SOL; do
    ln -sf "/opt/su2-8.6.0/bin/$tool" "/usr/local/bin/$tool"
done
SU2_CFD --help >/dev/null
