#!/usr/bin/env python3
"""Lightweight board stats: thermal zones + occasional NPU YOLO pulse."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

NPU_MODEL = (
    "/usr/local/share/aidlite/examples/aidlite_qnn236/data/"
    "qnn_yolov5_multi/cutoff_yolov5s_640_sigmoid_w8a8.qnn236.ctx.bin"
)
NPU_IMAGE = (
    "/usr/local/share/aidlite/examples/aidlite_qnn236/data/qnn_yolov5_multi/bus.jpg"
)


def thermal() -> dict[str, float]:
    root = Path("/sys/class/thermal")
    wanted = ("cpuss-0", "nspss-0", "gpuss-0")
    out: dict[str, float] = {}
    if not root.exists():
        return out
    for zone in root.glob("thermal_zone*"):
        try:
            typ = (zone / "type").read_text(encoding="utf-8", errors="ignore").strip()
            if typ not in wanted:
                continue
            out[typ] = int((zone / "temp").read_text().strip()) / 1000.0
        except (OSError, ValueError):
            continue
    return out


def _letterbox(image, size: int = 640) -> np.ndarray:
    import cv2

    h, w, _ = image.shape
    mask = np.zeros((size, size, 3), dtype=np.float32)
    scale = max(h / size, w / size)
    nh, nw = int(h / scale), int(w / scale)
    img = cv2.resize(image, (nw, nh))
    mask[:nh, :nw, :] = img
    return mask


class DeadPulse:
    ok = False
    err = "off"
    ms = 0.0

    def tick(self, *args, **kwargs) -> None:
        return

    def snapshot(self) -> dict:
        return {"ok": False, "ms": 0.0, "err": self.err, "thermal": thermal()}


class NpuPulse:
    def __init__(self) -> None:
        self.ok = False
        self.ms = 0.0
        self.err = ""
        self._itp = None
        self._in = None
        self._outs: list[str] = []
        self._n = 0
        try:
            self._setup()
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            self.err = str(exc)

    def _setup(self) -> None:
        import aidlite
        import cv2

        if not Path(NPU_MODEL).exists():
            raise RuntimeError("yolov5s qnn model missing")
        model = aidlite.Model.create_instance(NPU_MODEL)
        cfg = aidlite.Config.create_instance()
        cfg.framework_type = aidlite.FrameworkType.TYPE_QNN236
        cfg.accelerate_type = aidlite.AccelerateType.TYPE_DSP
        itp = aidlite.InterpreterBuilder.build_interpreter_from_model_and_config(model, cfg)
        if itp is None or itp.init() != 0 or itp.load_model() != 0:
            raise RuntimeError("qnn interpreter failed")
        info = itp.get_input_tensor_info()
        self._in = info[0][0].name
        self._outs = [t.name for g in itp.get_output_tensor_info() for t in g]
        self._itp = itp
        self.ok = True
        img = cv2.imread(NPU_IMAGE)
        if img is not None:
            self.tick(img, force=True)

    def tick(self, bgr, every: int = 18, force: bool = False) -> None:
        if not self.ok or self._itp is None:
            return
        self._n += 1
        if not force and self._n % every != 0:
            return
        import cv2

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        inp = (_letterbox(rgb, 640) / 255.0).astype(np.float32)
        t0 = time.perf_counter()
        if self._itp.set_input_tensor(self._in, inp.data) != 0:
            return
        if self._itp.invoke() != 0:
            return
        for name in self._outs:
            self._itp.get_output_tensor(name)
        self.ms = (time.perf_counter() - t0) * 1000.0

    def snapshot(self) -> dict:
        return {
            "ok": self.ok,
            "ms": self.ms,
            "err": self.err,
            "thermal": thermal(),
            "backend": "QNN236 DSP YOLOv5s",
        }
