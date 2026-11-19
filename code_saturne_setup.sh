#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl build-essential gfortran autoconf automake libtool autopoint gettext pkg-config python3 python3-pyqt5 pyqt5-dev-tools qttools5-dev-tools python3-numpy libxml2-dev zlib1g-dev
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
curl -fsSL --retry 3 https://codeload.github.com/code-saturne/code_saturne/tar.gz/refs/tags/v9.0.2 -o "$stage/source.tgz"
echo "d599c333fb90b47f096770a7f0b6025698880c74d3db0ae9c9f590ec102e4e66  $stage/source.tgz" | sha256sum -c -
tar -xzf "$stage/source.tgz" -C "$stage"
cd "$stage/code_saturne-9.0.2"
./sbin/bootstrap
mkdir "$stage/build"
cd "$stage/build"
"$stage/code_saturne-9.0.2/configure" --prefix=/usr/local PYTHON=/usr/bin/python3
make -j2
make install
ldconfig
code_saturne info --version

id cae >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cae
printf '[user]\ndefault=cae\n' > /etc/wsl.conf
