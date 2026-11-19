#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y --no-install-recommends ca-certificates curl unzip libstdc++6 libuuid1 libcrypt1

prefix=/opt/opencourant-20261011
if [[ ! -d "$prefix" ]]; then
    install -d /opt
    stage=$(mktemp -d /opt/.opencourant-XXXXXXXX)
    trap 'rm -rf -- "$stage"' EXIT
    archive="$stage/OpenCourant_linux64.zip"
    curl -fLsS --retry 3 https://github.com/OpenCourant/OpenCourant/releases/download/latest-20261011/OpenCourant_linux64.zip -o "$archive"
    echo "6cb419677ca36d73acb96218cc0cf5e4f7d50494d9c7812ba27935e3c0f8ec94  $archive" | sha256sum -c -
    unzip -q "$archive" -d "$stage"
    mv -T "$stage/OpenCourant" "$prefix"
fi

cat > "$prefix/run-solver" <<'LAUNCH'
#!/bin/sh
export OPENCOURANT_PATH=/opt/opencourant-20261011
export RAD_CFG_PATH="$OPENCOURANT_PATH/hm_cfg_files"
export RAD_H3D_PATH="$OPENCOURANT_PATH/extlib/h3d/lib/linux64"
export LD_LIBRARY_PATH="$OPENCOURANT_PATH/extlib/hm_reader/linux64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OMP_STACKSIZE="${OMP_STACKSIZE:-400m}"
exec "$OPENCOURANT_PATH/exec/${0##*/}" "$@"
LAUNCH
chmod 755 "$prefix/run-solver"
IFS= read -r linux_user < /root/wsl-manager-user
for tool in starter_linux64_gf engine_linux64_gf; do
    ln -sfn "$prefix/run-solver" "/usr/local/bin/$tool"
    runuser -u "$linux_user" -- "/usr/local/bin/$tool" -version
done
