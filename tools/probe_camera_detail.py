#!/usr/bin/env python3
"""Query V4L formats and grab a still from the USB camera."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import paramiko

REMOTE_SCRIPT = r"""
set +e
echo '===== FORMATS video2 ====='
v4l2-ctl -d /dev/video2 --all
echo '===== LIST-FORMATS video2 ====='
v4l2-ctl -d /dev/video2 --list-formats-ext
echo '===== FORMATS video3 ====='
v4l2-ctl -d /dev/video3 --all 2>&1 | head -40
echo '===== GRAB ====='
python3 - <<'PY'
import time
from pathlib import Path

import cv2

out = Path.home() / "rhinopi-lab" / "captures"
out.mkdir(parents=True, exist_ok=True)
cap = cv2.VideoCapture(2, cv2.CAP_V4L2)
if not cap.isOpened():
    raise SystemExit("open video2 failed")
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
print("after_set", cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT), cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FOURCC))

# discard a few frames while AE settles
for _ in range(8):
    cap.read()

ok, frame = cap.read()
if not ok:
    raise SystemExit("read failed")
still = out / "usb_c920_1280x720.jpg"
cv2.imwrite(str(still), frame)
print("saved", still, frame.shape, frame.mean())

samples = []
n = 30
t0 = time.perf_counter()
for _ in range(n):
    t1 = time.perf_counter()
    ok, _ = cap.read()
    samples.append((time.perf_counter() - t1) * 1000)
    if not ok:
        print("drop")
elapsed = time.perf_counter() - t0
print(f"loop_fps {n/elapsed:.2f}  frame_ms_avg {sum(samples)/len(samples):.2f}  min {min(samples):.2f}  max {max(samples):.2f}")
cap.release()
PY
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
    _, stdout, stderr = client.exec_command(REMOTE_SCRIPT, timeout=90)
    sys.stdout.write(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        sys.stderr.write("STDERR:\n" + err)

    sftp = client.open_sftp()
    remote = "/home/aidlux/rhinopi-lab/captures/usb_c920_1280x720.jpg"
    local = Path(__file__).resolve().parents[1] / "docs" / "images" / "02-usb-preview.jpg"
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(remote, str(local))
        print(f"\ndownloaded {remote} -> {local} ({local.stat().st_size} bytes)")
    except OSError as exc:
        print(f"\ndownload failed: {exc}")
    sftp.close()
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
