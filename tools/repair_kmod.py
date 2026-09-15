#!/usr/bin/env python3
"""Finish the kmod/libkmod2 configure without a TTY pager."""

from __future__ import annotations

import sys

import paramiko

KILL = r"""
kill 6705 6704 6646 2>/dev/null || true
sleep 1
ps -ef | grep -E 'apt|dpkg|pager|repair' | grep -v grep || true
"""

REMOTE = r"""
set -eu
export DEBIAN_FRONTEND=noninteractive
export PAGER=cat
export SYSTEMD_PAGER=cat
PASS=aidlux

echo '===== STATUS ====='
dpkg-query -W -f='${db:Status-Abbrev} ${Package} ${Version}\n' kmod libkmod2 systemd udev util-linux

echo '===== OVERWRITE KMOD ====='
echo "$PASS" | sudo -S dpkg -i --force-overwrite /tmp/kmod_29-1ubuntu1.1_arm64.deb || true

echo '===== FIX BROKEN ====='
echo "$PASS" | sudo -S env DEBIAN_FRONTEND=noninteractive apt-get --fix-broken install -y -o Dpkg::Options::="--force-confold"

echo '===== CONFIGURE ====='
echo "$PASS" | sudo -S env DEBIAN_FRONTEND=noninteractive dpkg --configure -a

echo '===== AFTER ====='
dpkg-query -W -f='${db:Status-Abbrev} ${Package} ${Version}\n' kmod libkmod2 systemd udev util-linux
echo '===== AUDIT ====='
echo "$PASS" | sudo -S dpkg --audit
echo '===== APT CHECK ====='
echo "$PASS" | sudo -S apt-get check
echo '===== AIDLITE ====='
python3 -c 'import aidlite,cv2; print(aidlite.get_py_library_version()); print("opencv", cv2.__version__)'
echo '===== DONE ====='
"""


def run(client: paramiko.SSHClient, script: str, timeout: int) -> str:
    _, stdout, stderr = client.exec_command(script, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("STDERR:\n" + err)
    return out


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        "192.168.88.216",
        username="aidlux",
        password="aidlux",
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    print("##### kill hung pager #####")
    run(client, KILL, 20)
    print("##### repair #####")
    run(client, REMOTE, 300)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
