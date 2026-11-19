#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get install -y netgen python3-netgen

command -v netgen
IFS= read -r linux_user < /root/wsl-manager-user
runuser -u "$linux_user" -- /usr/bin/python3 - <<'PY'
from netgen.csg import CSGeometry, OrthoBrick, Pnt

geometry = CSGeometry()
geometry.Add(OrthoBrick(Pnt(0, 0, 0), Pnt(1, 1, 1)))
mesh = geometry.GenerateMesh(maxh=0.5)
if not len(mesh.Elements3D()):
    raise RuntimeError("Netgen generated no volume elements")
PY
