#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates git build-essential gfortran autoconf automake libtool libltdl-dev liblapack-dev libsuitesparse-dev pkg-config
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
cd "$stage"
git init -q
git fetch --depth=1 https://public.gitlab.polimi.it/DAER/mbdyn.git 767fd42ec08957dc7da9fd48f70e86066869aa7c
git checkout --detach FETCH_HEAD
sh bootstrap.sh
CPPFLAGS=-I/usr/include/suitesparse ./configure --prefix=/usr/local --disable-Werror
make -j2
make install
ldconfig
mbdyn --version

id cae >/dev/null 2>&1 || useradd --create-home --shell /bin/bash cae
printf '[user]\ndefault=cae\n' > /etc/wsl.conf
