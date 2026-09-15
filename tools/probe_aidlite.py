#!/usr/bin/env python3
from __future__ import annotations

import sys

import paramiko

CMDS = r"""
set +e
echo '===== AID-PKG HELP ====='
aid-pkg help 2>&1 | head -40
echo '===== AIDLITE SHARE ====='
ls -la /usr/local/share/aidlite 2>/dev/null | head -30
ls /usr/local/share/aidlite/examples 2>/dev/null | head
echo '===== AIDSTREAM YOLO ====='
ls -la /usr/local/share/aidstream-gst/example/datas 2>/dev/null
echo '===== AIDLITE DIR ====='
python3 - <<'PY'
import aidlite, os
print("aidlite file", getattr(aidlite, "__file__", None))
print([x for x in dir(aidlite) if not x.startswith("_")])
PY
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
    _, stdout, stderr = client.exec_command(CMDS, timeout=30)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err[:3000])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
