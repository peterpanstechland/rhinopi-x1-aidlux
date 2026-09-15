#!/usr/bin/env python3
"""Open the USB UVC capture node on Rhino Pi X1."""

from __future__ import annotations

from pathlib import Path

import cv2


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


def find_usb_capture(preferred: int | None = None) -> int:
    if preferred is not None:
        return preferred
    names = v4l_names()
    for idx, name in names.items():
        lower = name.lower()
        if "webcam" in lower or "camera" in lower or "uvc" in lower:
            return idx
    if 2 in names:
        return 2
    raise SystemExit("no USB capture node; plug a UVC camera into a Type-A port")


def open_usb(index: int | None = None, width: int = 1280, height: int = 720, fps: int = 30, fourcc: str = "MJPG") -> cv2.VideoCapture:
    idx = find_usb_capture(index)
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise SystemExit(f"cannot open /dev/video{idx}")
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    return cap
