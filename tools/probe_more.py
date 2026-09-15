#!/usr/bin/env python3
from __future__ import annotations

import sys

import paramiko

CMDS = r"""
set +e
echo '===== AID-PKG ====='
aid-pkg --help 2>&1 | head -20
echo '===== MMS ====='
mms --help 2>&1 | head -30
echo '===== EXAMPLES ====='
ls /usr/local/share 2>/dev/null | head -40
ls /usr/local/share/aidlite 2>/dev/null | head
ls /opt 2>/dev/null | head
echo '===== SAMPLE MODELS ====='
find /usr/local/share /opt /home/aidlux -maxdepth 4 -iname '*yolo*' -o -iname '*.ctx.bin' -o -iname '*qnn*.bin' 2>/dev/null | head -40
echo '===== PIP ====='
python3 -m pip -V 2>/dev/null
python3 -c 'import numpy; print("numpy", numpy.__version__)' 2>/dev/null
echo '===== DESKTOP ====='
ls /usr/share/applications 2>/dev/null | head
echo '===== ADB ====='
which adb; getprop ro.build.display.id 2>/dev/null; getprop ro.product.model 2>/dev/null
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
    _, stdout, stderr = client.exec_command(CMDS, timeout=40)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err[:4000])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
