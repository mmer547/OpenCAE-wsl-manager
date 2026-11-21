#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl build-essential gfortran autoconf automake libtool libltdl-dev liblapack-dev libsuitesparse-dev pkg-config
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
commit=767fd42ec08957dc7da9fd48f70e86066869aa7c
curl -fsSL --retry 4 "https://public.gitlab.polimi.it/DAER/mbdyn/-/archive/$commit/mbdyn-$commit.tar.gz" -o "$stage/mbdyn.tar.gz"
echo "37ac4dc68b029cf6436ee9a66622992b0224cb96990bf92a1e04379775f9f1b0  $stage/mbdyn.tar.gz" | sha256sum -c -
tar -xzf "$stage/mbdyn.tar.gz" -C "$stage"
cd "$stage/mbdyn-$commit"
sh bootstrap.sh
CPPFLAGS=-I/usr/include/suitesparse ./configure --prefix=/usr/local --disable-Werror
make -j2
make install
ldconfig
mbdyn --version
