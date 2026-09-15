#!/usr/bin/env python3
"""Inspect apt/dpkg breakage on the AidLux board."""

from __future__ import annotations

import sys

import paramiko

CMDS = r"""
set +e
echo '===== HOLD ====='
apt-mark showhold 2>/dev/null
echo '===== KMOD ====='
dpkg -l kmod libkmod2 2>/dev/null
echo '===== POLICY ====='
apt-cache policy kmod libkmod2 2>/dev/null
echo '===== CHECK ====='
dpkg --audit 2>/dev/null
echo '===== BROKEN ====='
apt-get check 2>&1
echo '===== SOURCES ====='
ls /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null
echo '----- sources.list -----'
cat /etc/apt/sources.list 2>/dev/null
echo '----- sources.d -----'
for f in /etc/apt/sources.list.d/*; do echo "== $f"; cat "$f"; done
echo '===== UNAME ====='
uname -a
echo '===== AIDLITE ====='
python3 -c 'import aidlite,cv2; print(aidlite.get_py_library_version()); print(cv2.__version__)' 2>&1
echo '===== HISTORY TAIL ====='
tail -n 40 /var/log/apt/history.log 2>/dev/null
echo '===== TERM TAIL ====='
tail -n 80 /var/log/apt/term.log 2>/dev/null
"""


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
    _, stdout, stderr = client.exec_command(CMDS, timeout=60)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
