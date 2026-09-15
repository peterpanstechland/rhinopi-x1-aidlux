#!/usr/bin/env python3
"""Collect a first-boot snapshot from a Rhino Pi / AidLux board over SSH."""

from __future__ import annotations

import argparse
import sys

import paramiko

REMOTE_SCRIPT = r"""
set +e
echo '===== HOST ====='
hostname
uname -a
echo '===== OS ====='
cat /etc/os-release 2>/dev/null
echo '===== CPU ====='
lscpu 2>/dev/null | head -40
echo '===== MEM ====='
free -h
echo '===== DISK ====='
df -h /
echo '===== PYTHON ====='
python3 --version 2>/dev/null
which python3
echo '===== AIDLITE ====='
python3 - <<'PY'
try:
    import aidlite
    ver = None
    for name in ("get_py_library_version", "get_library_version"):
        fn = getattr(aidlite, name, None)
        if callable(fn):
            try:
                ver = fn()
                print(name, ver)
            except Exception as exc:
                print(name, "error", exc)
    print("aidlite_ok", True)
except Exception as exc:
    print("aidlite import failed:", exc)
PY
python3 - <<'PY'
try:
    import cv2
    print("opencv", cv2.__version__)
except Exception as exc:
    print("cv2 missing:", exc)
try:
    import mediapipe
    print("mediapipe", mediapipe.__version__)
except Exception as exc:
    print("mediapipe missing:", exc)
PY
echo '===== PKGS ====='
command -v aid-pkg
command -v mms
command -v apt
dpkg -l 2>/dev/null | grep -iE 'aidlite|aidlux|qnn|aidstream|aidcv' | head -50
echo '===== VIDEO ====='
ls -l /dev/video* 2>/dev/null
echo '===== USB ====='
lsusb 2>/dev/null | head -40
echo '===== NET ====='
ip -4 addr 2>/dev/null
echo '===== TEMP ====='
for z in /sys/class/thermal/thermal_zone*; do
  echo -n "$z "
  cat "$z/type" 2>/dev/null | tr -d '\n'
  echo -n " "
  cat "$z/temp" 2>/dev/null
done
echo '===== WHO ====='
whoami
id
pwd
echo '===== HOME ====='
ls -la ~
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.88.216")
    parser.add_argument("--user", default="aidlux")
    parser.add_argument("--password", default="aidlux")
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host,
        username=args.user,
        password=args.password,
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    stdin, stdout, stderr = client.exec_command(REMOTE_SCRIPT, timeout=60)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
