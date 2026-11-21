#!/bin/bash
set -euo pipefail
cd /
IFS= read -r linux_user < /root/wsl-manager-user
user_home=$(getent passwd "$linux_user" | cut -d: -f6)
test -d "$user_home"
export DEBIAN_FRONTEND=noninteractive
apt-get -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl build-essential gnuplot imagemagick

runuser -u "$linux_user" -- env HOME="$user_home" bash <<'BUILD'
set -euo pipefail
cd "$HOME"
if [[ ! -d olb-1.9r0 ]]; then
    stage=$(mktemp -d "$HOME/.openlb-XXXXXXXX")
    trap 'rm -rf -- "$stage"' EXIT
    curl -fLsS --retry 3 https://zenodo.org/records/17899765/files/olb-1.9r0.tgz -o "$stage/release.tgz"
    echo "e4d2421b50643482036917c4416145f7d6b495492f3afac64e048212361c8b3e  $stage/release.tgz" | sha256sum -c -
    tar -xzf "$stage/release.tgz" -C "$stage"
    mv -T "$stage/olb-1.9r0" olb-1.9r0
fi
cd olb-1.9r0
make
make -C examples/laminar/poiseuille2d
test -x examples/laminar/poiseuille2d/poiseuille2d
BUILD
