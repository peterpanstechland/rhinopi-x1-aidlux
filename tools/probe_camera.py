#!/usr/bin/env python3
"""SSH onto the board and inspect USB / V4L / OpenCV camera nodes."""

from __future__ import annotations

import argparse
import sys

import paramiko

REMOTE_SCRIPT = r"""
set +e
echo '===== LSUSB ====='
lsusb
echo '===== LSUSB -T ====='
lsusb -t 2>/dev/null
echo '===== VIDEO NODES ====='
ls -l /dev/video* 2>/dev/null
echo '===== V4L2-CTL ====='
command -v v4l2-ctl
v4l2-ctl --list-devices 2>/dev/null
echo '===== SYS VIDEO ====='
for d in /sys/class/video4linux/video*; do
  echo "-- $d"
  cat "$d/name" 2>/dev/null
  readlink -f "$d/device" 2>/dev/null
done
echo '===== GROUPS ====='
id
groups
echo '===== OPENCV SCAN ====='
python3 - <<'PY'
import json
import time

import cv2

nodes = []
for i in range(40):
    path = f"/dev/video{i}"
    try:
        open(path, "rb").close()
    except OSError:
        continue
    nodes.append(i)

print("readable_nodes", nodes)
results = []
for i in nodes:
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
    opened = bool(cap.isOpened())
    w = h = fps = backend = None
    ok = False
    shape = None
    elapsed_ms = None
    if opened:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS)
        backend = cap.getBackendName()
        t0 = time.perf_counter()
        ok, frame = cap.read()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        if ok and frame is not None:
            shape = list(frame.shape)
    cap.release()
    results.append({
        "index": i,
        "opened": opened,
        "read_ok": bool(ok),
        "shape": shape,
        "width": w,
        "height": h,
        "fps": fps,
        "backend": backend,
        "first_frame_ms": elapsed_ms,
    })
print(json.dumps(results, indent=2, ensure_ascii=False))
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
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
