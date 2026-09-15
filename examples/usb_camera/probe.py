#!/usr/bin/env python3
"""Find the USB capture node, grab a still, and measure MJPG FPS."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import cv2


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=20).strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def v4l_names() -> dict[int, str]:
    root = Path("/sys/class/video4linux")
    names: dict[int, str] = {}
    if not root.exists():
        return names
    for node in sorted(root.glob("video*")):
        try:
            idx = int(node.name.replace("video", ""))
        except ValueError:
            continue
        name_file = node / "name"
        names[idx] = name_file.read_text(encoding="utf-8", errors="ignore").strip() if name_file.exists() else ""
    return names


def find_usb_capture(names: dict[int, str], preferred: int | None) -> int:
    if preferred is not None:
        return preferred
    for idx, name in names.items():
        lower = name.lower()
        if "webcam" in lower or "camera" in lower or "uvc" in lower:
            return idx
    # Official X1 pattern: USB UVC lands on video2, not video0.
    if 2 in names:
        return 2
    raise SystemExit("no USB capture node found; plug a UVC camera into a Type-A port")


def open_usb(index: int, width: int, height: int, fps: int, fourcc: str) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise SystemExit(f"OpenCV cannot open /dev/video{index} (metadata nodes like video3 will fail)")
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    return cap


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=None, help="V4L index, default: auto")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--fourcc", default="MJPG")
    parser.add_argument("--warmup", type=int, default=8)
    parser.add_argument("--loops", type=int, default=30)
    parser.add_argument(
        "--out",
        default=str(Path.home() / "rhinopi-lab" / "captures" / "usb_preview.jpg"),
    )
    args = parser.parse_args()

    names = v4l_names()
    index = find_usb_capture(names, args.index)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cap = open_usb(index, args.width, args.height, args.fps, args.fourcc)
    for _ in range(args.warmup):
        cap.read()
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise SystemExit("failed to read a frame")
    cv2.imwrite(str(out), frame)

    samples: list[float] = []
    t0 = time.perf_counter()
    for _ in range(args.loops):
        t1 = time.perf_counter()
        ok, _ = cap.read()
        samples.append((time.perf_counter() - t1) * 1000)
        if not ok:
            break
    elapsed = time.perf_counter() - t0
    cap.release()

    report = {
        "lsusb": run(["lsusb"]),
        "v4l_names": {f"/dev/video{k}": v for k, v in names.items()},
        "opened": f"/dev/video{index}",
        "fourcc": args.fourcc,
        "requested": [args.width, args.height, args.fps],
        "frame_shape": list(frame.shape),
        "still": str(out),
        "loop_fps": round(len(samples) / elapsed, 2) if elapsed else None,
        "frame_ms_avg": round(sum(samples) / len(samples), 2) if samples else None,
        "frame_ms_min": round(min(samples), 2) if samples else None,
        "frame_ms_max": round(max(samples), 2) if samples else None,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n=== summary ===")
    print(f"opened  /dev/video{index}  {names.get(index, '')}")
    print(f"frame   {frame.shape}  {args.fourcc}")
    print(f"still   {out}")
    print(f"fps     {report['loop_fps']}  avg {report['frame_ms_avg']} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
