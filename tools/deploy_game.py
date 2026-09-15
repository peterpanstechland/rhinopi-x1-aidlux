#!/usr/bin/env python3
from __future__ import annotations

import posixpath
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "examples/usb_camera/camera.py",
    "examples/04_mediapipe/pose_tracker.py",
    "examples/04_mediapipe/pose_preview.py",
    "examples/04_mediapipe/README.md",
    "examples/06_shadow_puppet/game.py",
    "examples/06_shadow_puppet/README.md",
]


def mkdir_p(sftp, remote: str) -> None:
    parts = remote.strip("/").split("/")
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}" if cur else part
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


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
    for rel in FILES:
        remote = posixpath.join("rhinopi-lab", rel)
        mkdir_p(sftp, posixpath.dirname(remote))
        sftp.put(str(ROOT / rel), remote)
        print("uploaded", rel)
    sftp.close()

    cmd = (
        "python3 rhinopi-lab/examples/06_shadow_puppet/game.py "
        "--seconds 16 --no-web "
        "--save /home/aidlux/rhinopi-lab/captures/puppet_smoke.jpg"
    )
    print("\n########## smoke ##########\n")
    _, stdout, stderr = client.exec_command(cmd, timeout=180)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
