#!/usr/bin/env python3
"""Run the UI render probe on the board and pull the screenshots back."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".tmp_ui"
FILES = [
    "examples/06_shadow_puppet/overlay.py",
    "examples/06_shadow_puppet/scenes.py",
    "examples/06_shadow_puppet/puppet.py",
    "examples/06_shadow_puppet/pixel_ui.py",
    "examples/06_shadow_puppet/loop.py",
    "examples/06_shadow_puppet/gestures.py",
    "examples/06_shadow_puppet/posture.py",
    "examples/06_shadow_puppet/render_probe.py",
]
REMOTE_OUT = "/tmp/ui"


def main() -> int:
    only = sys.argv[1:] or None
    LOCAL.mkdir(exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        "192.168.88.216",
        username="aidlux",
        password="aidlux",
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    sftp = c.open_sftp()
    for rel in FILES:
        sftp.put(str(ROOT / rel), f"rhinopi-lab/{rel}")
    print("uploaded", len(FILES), "files")
    cmd = (
        f"rm -rf {REMOTE_OUT} && cd /home/aidlux/rhinopi-lab/examples/06_shadow_puppet && "
        f"python3 render_probe.py --out {REMOTE_OUT} 2>&1 | tail -n 30"
    )
    _, o, _ = c.exec_command(cmd, timeout=180)
    print(o.read().decode(errors="replace"))
    try:
        names = sorted(sftp.listdir(REMOTE_OUT))
    except OSError as exc:
        print("no output dir:", exc)
        sftp.close()
        c.close()
        return 1
    for name in names:
        if not name.endswith(".jpg"):
            continue
        if only and not any(k in name for k in only):
            continue
        sftp.get(f"{REMOTE_OUT}/{name}", str(LOCAL / name))
        print("pulled", name)
    sftp.close()
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
