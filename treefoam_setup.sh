#!/bin/bash
set -euo pipefail
cd /
export DEBIAN_FRONTEND=noninteractive
bash /root/openfoam_setup.sh
apt-get install -y --no-install-recommends unzip paraview python3-vtk9 python3-pyqt5 \
    python3-gi python3-gi-cairo gir1.2-gtk-3.0 nautilus gnome-terminal gedit \
    dbus-x11 locales fonts-noto-cjk gettext xclip wl-clipboard
locale-gen ja_JP.UTF-8 en_US.UTF-8

stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
archive="$stage/treefoam.zip"
curl -fLsS --retry 3 https://opencae-dalab.org/download/all_treefoam_3.38-261001.zip -o "$archive"
echo "15a6ce444cbdc86053396d7bb91dc512e96be00cfff1efd931f235b7c5f8bce3  $archive" | sha256sum -c -
unzip -q "$archive" 'treefoam_*.deb' 'treefoam-doc_*.deb' -d "$stage"
apt-get install -y "$stage"/treefoam_*.deb "$stage"/treefoam-doc_*.deb

IFS= read -r linux_user < /root/wsl-manager-user
runuser -u "$linux_user" -- bash -e <<'CONFIG'
cd "$HOME"
mkdir -p .TreeFoamUser OpenFOAM/run
if [[ ! -f .TreeFoamUser/configTreeFoam ]]; then
    tmp=$(mktemp .TreeFoamUser/config.XXXXXX)
    trap 'rm -f "$tmp"' EXIT
    sed -e 's/^OFversion .*/OFversion 12/' \
        -e "s|^rootDir .*|rootDir $HOME|" -e "s|^workDir .*|workDir $HOME/OpenFOAM/run|" \
        -e '/^bashrcFOAM /s/v2606/12/' -e '/^paraFoam /s/v2606/12/' \
        -e '/^\(Terminal\|TerminalRun\|foamTerminal\|foamTerminalRun\|editor\) /d' \
        -e '/^#\(Terminal\|TerminalRun\|foamTerminal\|foamTerminalRun\) gnome-terminal/s/^#//' \
        -e '/^#editor gedit/s/^#//' /opt/TreeFoam/configTreeFoam > "$tmp"
    mv "$tmp" .TreeFoamUser/configTreeFoam
fi
CONFIG
printf '%s\n' '#!/bin/sh' 'exec /opt/TreeFoam/treefoam "$@"' > /usr/local/bin/treefoam
chmod 755 /usr/local/bin/treefoam
test -x /opt/TreeFoam/treefoam
command -v paraview
runuser -u "$linux_user" -- python3 -c 'import gi, vtk; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk; from PyQt5 import QtWidgets'
