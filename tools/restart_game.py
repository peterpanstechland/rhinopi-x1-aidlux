#!/usr/bin/env python3
from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "examples/06_shadow_puppet/game.py",
    "examples/06_shadow_puppet/gestures.py",
    "examples/06_shadow_puppet/overlay.py",
    "examples/06_shadow_puppet/loop.py",
    "examples/06_shadow_puppet/scenes.py",
    "examples/06_shadow_puppet/posture.py",
    "examples/06_shadow_puppet/puppet.py",
    "examples/06_shadow_puppet/hand_tracker.py",
    "examples/06_shadow_puppet/pixel_ui.py",
    "examples/06_shadow_puppet/stats.py",
    "examples/06_shadow_puppet/test_loop.py",
    "examples/06_shadow_puppet/render_probe.py",
    "examples/06_shadow_puppet/README.md",
    "examples/04_mediapipe/pose_tracker.py",
]
EXTRA_ARGS = [a for a in sys.argv[1:]]


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
    sftp = client.open_sftp()
    for rel in FILES:
        sftp.put(str(ROOT / rel), f"rhinopi-lab/{rel}")
        print("uploaded", rel)
    sftp.close()
    client.exec_command("pkill -9 -f '06_shadow_puppet/game.py' || true", timeout=10)
    time.sleep(2.0)
    argv = ["python3", "/home/aidlux/rhinopi-lab/examples/06_shadow_puppet/game.py", "--port", "8090"]
    argv += EXTRA_ARGS
    cmd = " ".join(shlex.quote(a) for a in argv)
    launch = f"setsid nohup {cmd} > /tmp/puppet.log 2>&1 < /dev/null & echo started $!"
    _, stdout, stderr = client.exec_command(launch, timeout=20)
    sys.stdout.write(stdout.read().decode())
    sys.stderr.write(stderr.read().decode())
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
