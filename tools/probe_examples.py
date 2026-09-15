#!/usr/bin/env python3
from __future__ import annotations

import sys

import paramiko

CMDS = r"""
set +e
echo '===== AIDLITE EXAMPLES TREE ====='
find /usr/local/share/aidlite/examples -maxdepth 3 -type d
echo '===== SAMPLE PY ====='
find /usr/local/share/aidlite/examples -name '*.py' | head -40
echo '===== QNN236 SAMPLE ====='
ls -la /usr/local/share/aidlite/examples/aidlite_qnn236 2>/dev/null | head
find /usr/local/share/aidlite/examples/aidlite_qnn236 -maxdepth 3 | head -40
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
        sys.stderr.write("STDERR:\n" + err[:2000])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
