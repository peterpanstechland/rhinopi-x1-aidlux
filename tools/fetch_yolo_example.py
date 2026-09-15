#!/usr/bin/env python3
from __future__ import annotations

import sys

import paramiko

PATH = "/usr/local/share/aidlite/examples/aidlite_qnn236/python/qnn_yolov5_multi.py"


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
    sftp = client.open_sftp()
    with sftp.open(PATH, "r") as fh:
        data = fh.read()
    sys.stdout.write(data.decode("utf-8", errors="replace"))
    sftp.close()
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
