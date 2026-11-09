#!/usr/bin/env python3
from __future__ import annotations

import posixpath
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "examples/06_shadow_puppet"


def game_files() -> list[Path]:
    web = GAME / "web"
    if not (web / "index.html").is_file():
        raise FileNotFoundError(web / "index.html")
    assets = [
        asset for asset in web.rglob("*")
        if asset.is_file() and not any(part.startswith(".") for part in asset.relative_to(web).parts)
    ]
    return [
        ROOT / "examples/usb_camera/camera.py",
        ROOT / "examples/04_mediapipe/pose_tracker.py",
        ROOT / "examples/04_mediapipe/pose_preview.py",
        ROOT / "examples/04_mediapipe/README.md",
        GAME / "README.md",
        *sorted(GAME.glob("*.py")),
        *sorted(assets),
    ]


def mkdir_p(sftp, remote: str) -> None:
    parts = remote.strip("/").split("/")
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}" if cur else part
        try:
            sftp.stat(cur)
        except FileNotFoundError:
            sftp.mkdir(cur)


def upload_game(client) -> None:
    made = set()
    with client.open_sftp() as sftp:
        for local in game_files():
            rel = local.relative_to(ROOT).as_posix()
            remote = posixpath.join("rhinopi-lab", rel)
            parent = posixpath.dirname(remote)
            if parent not in made:
                mkdir_p(sftp, parent)
                made.add(parent)
            sftp.put(str(local), remote)
            print("uploaded", rel)


def run_remote(client, cmd: str, timeout: int) -> int:
    _, stdout, _ = client.exec_command(cmd, timeout=timeout)
    stdout.channel.set_combine_stderr(True)
    for line in stdout:
        sys.stdout.write(line)
    return stdout.channel.recv_exit_status()


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
    cmd = (
        "python3 rhinopi-lab/examples/06_shadow_puppet/game.py "
        "--seconds 16 --no-web "
        "--save /home/aidlux/rhinopi-lab/captures/puppet_smoke.jpg"
    )
    try:
        upload_game(client)
        print("\nSmoke test\n")
        return run_remote(client, cmd, timeout=180)
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
