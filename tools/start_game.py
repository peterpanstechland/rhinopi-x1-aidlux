#!/usr/bin/env python3
from __future__ import annotations

import sys

import paramiko

LAUNCH = r"""
python3 -c 'import subprocess; log=open("/tmp/puppet.log","a"); subprocess.Popen(["python3","/home/aidlux/rhinopi-lab/examples/06_shadow_puppet/game.py","--port","8090"], stdout=log, stderr=subprocess.STDOUT, start_new_session=True); print("started")'
"""


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        "192.168.88.216",
        username="aidlux",
        password="aidlux",
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    _, stdout, stderr = client.exec_command(LAUNCH, timeout=20)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write(err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
