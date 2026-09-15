#!/usr/bin/env python3
"""See if the board can speak ADB over TCP."""

from __future__ import annotations

import sys

import paramiko

CMDS = r"""
set +e
echo '===== ADB ====='
which adb
getprop sys.usb.config 2>/dev/null
getprop persist.adb.tcp.port 2>/dev/null
getprop service.adb.tcp.port 2>/dev/null
echo '===== LISTEN ====='
ss -lnt 2>/dev/null | head -40
netstat -lnt 2>/dev/null | head -40
echo '===== USB GADGET ====='
ls /sys/class/android_usb 2>/dev/null
cat /sys/class/android_usb/android0/functions 2>/dev/null
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
    _, stdout, stderr = client.exec_command(CMDS, timeout=20)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write(err[:2000])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
