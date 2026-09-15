#!/usr/bin/env python3
"""Print a Rhino Pi / AidLux environment snapshot."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=20)
        return out.strip()
    except Exception as exc:  # noqa: BLE001
        return f"ERROR: {exc}"


def try_import(name: str):
    try:
        mod = __import__(name)
        ver = getattr(mod, "__version__", None)
        extra = {}
        if name == "aidlite":
            for fn_name in ("get_py_library_version", "get_library_version"):
                fn = getattr(mod, fn_name, None)
                if callable(fn):
                    try:
                        extra[fn_name] = fn()
                    except Exception as exc:  # noqa: BLE001
                        extra[fn_name] = f"error: {exc}"
        return {"ok": True, "version": ver, **extra}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def thermal_sample() -> dict[str, int]:
    root = Path("/sys/class/thermal")
    wanted = ("cpuss-0", "nspss-0", "gpuss-0", "video", "ddr")
    found: dict[str, int] = {}
    if not root.exists():
        return found
    for zone in sorted(root.glob("thermal_zone*")):
        typ = (zone / "type").read_text(encoding="utf-8", errors="ignore").strip()
        if typ not in wanted:
            continue
        raw = (zone / "temp").read_text(encoding="utf-8", errors="ignore").strip()
        try:
            found[typ] = int(raw)
        except ValueError:
            continue
    return found


def main() -> int:
    report = {
        "hostname": platform.node(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "os_release": run(["bash", "-lc", "cat /etc/os-release | sed -n '1,8p'"]),
        "cpu": run(["bash", "-lc", "lscpu | sed -n '1,20p'"]),
        "mem": run(["free", "-h"]),
        "disk": run(["df", "-h", "/"]),
        "which": {
            "python3": shutil.which("python3"),
            "aid-pkg": shutil.which("aid-pkg"),
            "mms": shutil.which("mms"),
        },
        "modules": {
            "numpy": try_import("numpy"),
            "cv2": try_import("cv2"),
            "aidlite": try_import("aidlite"),
            "mediapipe": try_import("mediapipe"),
        },
        "packages": run(["bash", "-lc", "dpkg -l | grep -iE 'aidlite|aid-mms|aidcv|aidstream|aidgen-qnn' | awk '{print $2, $3}'"]),
        "video_nodes": run(["bash", "-lc", "ls -l /dev/video* 2>/dev/null || true"]),
        "v4l_names": run(
            [
                "bash",
                "-lc",
                "for d in /sys/class/video4linux/video*; do echo -n \"$d \"; cat \"$d/name\" 2>/dev/null; done",
            ]
        ),
        "lsusb": run(["bash", "-lc", "lsusb 2>/dev/null | head -20 || true"]),
        "thermal_milli_c": thermal_sample(),
        "cwd": os.getcwd(),
        "user": os.environ.get("USER") or os.environ.get("LOGNAME"),
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n=== summary ===")
    print(f"host     {report['hostname']}  kernel {report['kernel']}")
    print(f"python   {report['python']}")
    for name, info in report["modules"].items():
        if info.get("ok"):
            ver = info.get("get_py_library_version") or info.get("version") or "ok"
            print(f"module   {name}: OK  {ver}")
        else:
            print(f"module   {name}: MISSING  {info.get('error')}")
    print("aid-pkg ", report["which"]["aid-pkg"])
    print("mms     ", report["which"]["mms"])
    print("video   ", "yes" if "/dev/video" in report["video_nodes"] else "none")
    if report.get("v4l_names") and not str(report["v4l_names"]).startswith("ERROR"):
        print("v4l     ", " | ".join(report["v4l_names"].splitlines()))
    if report["thermal_milli_c"]:
        pretty = {k: f"{v/1000:.1f}C" for k, v in report["thermal_milli_c"].items()}
        print("thermal ", pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
