#!/usr/bin/env python3
"""Copy example scripts to the board and run them."""

from __future__ import annotations

import argparse
import posixpath
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ("examples/01_env_check/check_env.py", "examples/01_env_check/check_env.py"),
    ("examples/01_env_check/README.md", "examples/01_env_check/README.md"),
    ("examples/02_compute_bench/bench.py", "examples/02_compute_bench/bench.py"),
    ("examples/02_compute_bench/README.md", "examples/02_compute_bench/README.md"),
    ("examples/usb_camera/probe.py", "examples/usb_camera/probe.py"),
    ("examples/usb_camera/README.md", "examples/usb_camera/README.md"),
]


def mkdir_p(sftp: paramiko.SFTPClient, remote: str) -> None:
    parts = remote.strip("/").split("/")
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}" if cur else f"/{part}" if remote.startswith("/") else part
        if remote.startswith("/") and not cur.startswith("/"):
            cur = "/" + cur
        try:
            sftp.stat(cur)
        except OSError:
            sftp.mkdir(cur)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.88.216")
    parser.add_argument("--user", default="aidlux")
    parser.add_argument("--password", default="aidlux")
    parser.add_argument("--remote-root", default="rhinopi-lab")
    parser.add_argument("--skip-npu", action="store_true")
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
    sftp = client.open_sftp()
    for local_rel, remote_rel in FILES:
        local = ROOT / local_rel
        remote = posixpath.join(args.remote_root, remote_rel)
        mkdir_p(sftp, posixpath.dirname(remote))
        sftp.put(str(local), remote)
        print(f"uploaded {local_rel} -> {remote}")
    sftp.close()

    commands = [
        f"python3 {args.remote_root}/examples/01_env_check/check_env.py",
        (
            f"python3 {args.remote_root}/examples/02_compute_bench/bench.py"
            + (" --skip-npu" if args.skip_npu else "")
        ),
    ]
    for cmd in commands:
        print(f"\n########## {cmd} ##########\n")
        _, stdout, stderr = client.exec_command(cmd, timeout=180)
        sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
        err = stderr.read().decode("utf-8", errors="replace")
        if err.strip():
            sys.stderr.write("STDERR:\n" + err)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
