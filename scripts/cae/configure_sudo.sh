#!/bin/sh
# Run as root for the Linux account created by the manager.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
user=$1
if [ ! -f /etc/debian_version ]; then
    # The general WSL installer also supports non-Debian distributions.
    if [ "${2:-}" = "--if-debian" ]; then exit 0; fi
    echo "この sudo 設定は Ubuntu / Debian 系の環境用です。" >&2
    exit 1
fi
uid=$(id -u -- "$user")
if [ "$uid" -lt 1000 ] || [ "$uid" -eq 65534 ]; then
    echo "作成時に指定した一般ユーザー名を確認してください。" >&2
    exit 1
fi
if [ ! -x /usr/bin/sudo ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends sudo
fi
usermod -aG sudo -- "$user"
# Check the effective policy for this user without prompting for their password.
sudo -n -l -U "$user" -u root -- /usr/bin/id -u >/dev/null
