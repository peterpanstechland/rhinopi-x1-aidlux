#!/usr/bin/env python3
"""USB camera + onboard AidLite Pose overlay, streamed to a browser."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04_mediapipe"))
sys.path.insert(0, str(ROOT / "usb_camera"))
sys.path.insert(0, str(ROOT / "06_shadow_puppet"))

from camera import open_usb  # noqa: E402
from game import JpegHub, start_http  # noqa: E402
from pose_tracker import PoseTracker, draw_skeleton  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--save", default="")
    parser.add_argument("--accel", default="GPU")
    args = parser.parse_args()

    tracker = PoseTracker(accel=args.accel, full_body=True)
    cap = open_usb(args.index, args.width, args.height)
    hub = JpegHub()
    if not args.no_web:
        start_http(hub, "0.0.0.0", args.port)
        print(f"open  http://192.168.88.216:{args.port}/", flush=True)
    t_end = time.perf_counter() + args.seconds if args.seconds else None
    last = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            frame = cv2.flip(frame, 1)
            pose = tracker.infer(frame)
            draw_skeleton(frame, pose)
            cv2.putText(
                frame,
                f"AidLite Pose  {'OK' if pose.ok else '---'}  {pose.infer_ms:.0f} ms",
                (24, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (80, 220, 255),
                2,
                cv2.LINE_AA,
            )
            hub.update(frame)
            last = frame
            if t_end and time.perf_counter() >= t_end:
                break
    except KeyboardInterrupt:
        print("stop")
    finally:
        cap.release()
        if args.save and last is not None:
            Path(args.save).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(args.save, last)
            print("saved", args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
