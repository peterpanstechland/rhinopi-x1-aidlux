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
from desk_http import JpegHub, start_http  # noqa: E402
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
    server = None if args.no_web else start_http(hub, None, "0.0.0.0", args.port)
    if server:
        print(f"HTTP listening on 0.0.0.0:{server.server_port}", flush=True)
    t_end = time.perf_counter() + args.seconds if args.seconds else None
    last = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                if t_end and time.perf_counter() >= t_end:
                    if last is None:
                        print("No camera frames received.", file=sys.stderr)
                        return 1
                    break
                time.sleep(0.05)
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
        if server:
            server.shutdown()
            server.server_close()
        cap.release()
        if args.save and last is not None:
            Path(args.save).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(args.save, last)
            print("saved", args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
