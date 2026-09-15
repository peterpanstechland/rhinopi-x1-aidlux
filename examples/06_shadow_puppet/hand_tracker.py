#!/usr/bin/env python3
"""Hand landmarks via the onboard palm_detection + hand_landmark tflite pair."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

MODEL_DIR = Path("/opt/aidlux/app/aid-examples/hand_track/models")

TIPS = (4, 8, 12, 16, 20)
BONES = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (5, 6),
    (6, 7),
    (7, 8),
    (9, 10),
    (10, 11),
    (11, 12),
    (13, 14),
    (14, 15),
    (15, 16),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 5),
    (5, 9),
    (9, 13),
    (13, 17),
    (17, 0),
)


@dataclass
class Hand:
    xy: np.ndarray  # (21, 2) image pixels
    box: tuple  # (x0, y0, x1, y1)

    @property
    def wrist(self):
        return self.xy[0]

    @property
    def tips(self):
        return self.xy[list(TIPS)]

    @property
    def span(self) -> float:
        return float(np.linalg.norm(self.xy[5] - self.xy[17])) + 1e-3


@dataclass
class HandResult:
    hands: list = field(default_factory=list)
    infer_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.hands)


def _prep(img: np.ndarray, size: int) -> np.ndarray:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (size, size))
    out = (2.0 / 255.0) * rgb.astype(np.float32) - 1.0
    return np.ascontiguousarray(out[None, ...])


def _build(path: Path, in_shape, out_shapes, accel: str):
    import aidlite

    model = aidlite.Model.create_instance(str(path))
    if model is None:
        raise RuntimeError(f"cannot create model {path}")
    model.set_model_properties(
        in_shape,
        aidlite.DataType.TYPE_FLOAT32,
        out_shapes,
        aidlite.DataType.TYPE_FLOAT32,
    )
    cfg = aidlite.Config.create_instance()
    cfg.implement_type = aidlite.ImplementType.TYPE_FAST
    cfg.framework_type = aidlite.FrameworkType.TYPE_TFLITE
    cfg.accelerate_type = getattr(aidlite.AccelerateType, f"TYPE_{accel}")
    cfg.number_of_threads = 4
    itp = aidlite.InterpreterBuilder.build_interpretper_from_model_and_config(model, cfg)
    if itp is None or itp.init() != 0 or itp.load_model() != 0:
        raise RuntimeError(f"cannot init {path}")
    return itp


def _decode(raw_boxes: np.ndarray, scores: np.ndarray, anchors: np.ndarray, thresh: float):
    raw = raw_boxes.reshape(896, 18)
    sc = 1.0 / (1.0 + np.exp(-np.clip(scores.reshape(896), -100.0, 100.0)))
    keep = sc >= thresh
    if not np.any(keep):
        return np.zeros((0, 5), np.float32)
    r = raw[keep]
    a = anchors[keep]
    s = sc[keep]
    xc = r[:, 0] / 128.0 * a[:, 2] + a[:, 0]
    yc = r[:, 1] / 128.0 * a[:, 3] + a[:, 1]
    w = r[:, 2] / 128.0 * a[:, 2]
    h = r[:, 3] / 128.0 * a[:, 3]
    out = np.stack([yc - h / 2, xc - w / 2, yc + h / 2, xc + w / 2, s], axis=1)
    order = np.argsort(-out[:, 4])
    return out[order][:6].astype(np.float32)


def _nms(dets: np.ndarray, thresh: float = 0.35) -> np.ndarray:
    keep = []
    for d in dets:
        drop = False
        for k in keep:
            y0 = max(d[0], k[0])
            x0 = max(d[1], k[1])
            y1 = min(d[2], k[2])
            x1 = min(d[3], k[3])
            inter = max(0.0, y1 - y0) * max(0.0, x1 - x0)
            if inter <= 0:
                continue
            a = (d[2] - d[0]) * (d[3] - d[1])
            b = (k[2] - k[0]) * (k[3] - k[1])
            if inter / (a + b - inter) > thresh:
                drop = True
                break
        if not drop:
            keep.append(d)
        if len(keep) == 2:
            break
    return np.stack(keep) if keep else dets[:0]


class HandTracker:
    def __init__(
        self,
        model_dir: Path | str = MODEL_DIR,
        accel: str = "GPU",
        score_thresh: float = 0.55,
        redetect_every: int = 6,
    ) -> None:
        d = Path(model_dir)
        self.score_thresh = score_thresh
        self.redetect_every = max(1, redetect_every)
        self.anchors = np.load(d / "anchors.npy").astype(np.float32)
        self.palm = _build(d / "palm_detection.tflite", [[1, 128, 128, 3]], [[1, 896, 18], [1, 896, 1]], accel)
        self.mesh = _build(d / "hand_landmark.tflite", [[1, 224, 224, 3]], [[1, 63], [1], [1]], accel)
        self._boxes: list = []
        self._n = 0

    def _detect(self, frame: np.ndarray) -> list:
        h, w = frame.shape[:2]
        inp = _prep(frame, 128)
        if self.palm.set_input_tensor(0, inp.data) != 0 or self.palm.invoke() != 0:
            return []
        a = self.palm.get_output_tensor(0)
        b = self.palm.get_output_tensor(1)
        if a is None or b is None:
            return []
        if a.size == 896:
            scores, boxes = a, b
        else:
            scores, boxes = b, a
        dets = _decode(boxes, scores, self.anchors, self.score_thresh)
        if dets.shape[0] == 0:
            return []
        dets = _nms(dets)
        out = []
        for d in dets:
            ymin, xmin, ymax, xmax = d[0] * h, d[1] * w, d[2] * h, d[3] * w
            side = max(ymax - ymin, xmax - xmin) * 224.0 / 128.0
            cx, cy = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0
            x0 = int(max(0, cx - side / 2))
            x1 = int(min(w, cx + side / 2))
            y0 = int(max(0, cy - side / 2 - 0.18 * side))
            y1 = int(min(h, cy + side / 2 - 0.18 * side))
            if x1 - x0 > 24 and y1 - y0 > 24:
                out.append((x0, y0, x1, y1))
        return out

    def infer(self, frame: np.ndarray) -> HandResult:
        import time

        t0 = time.perf_counter()
        self._n += 1
        if not self._boxes or self._n % self.redetect_every == 0:
            self._boxes = self._detect(frame)
        hands = []
        for box in self._boxes[:2]:
            x0, y0, x1, y1 = box
            roi = frame[y0:y1, x0:x1]
            if roi.size == 0:
                continue
            inp = _prep(roi, 224)
            if self.mesh.set_input_tensor(0, inp.data) != 0 or self.mesh.invoke() != 0:
                continue
            raw = self.mesh.get_output_tensor(0)
            if raw is None or raw.size < 63:
                continue
            pts = np.asarray(raw, dtype=np.float32).reshape(21, 3)[:, :2] / 224.0
            xy = np.empty((21, 2), np.float32)
            xy[:, 0] = x0 + pts[:, 0] * (x1 - x0)
            xy[:, 1] = y0 + pts[:, 1] * (y1 - y0)
            hands.append(Hand(xy, box))
        if not hands:
            self._boxes = []
        else:
            # keep tracking from the landmark bounds so we can skip detection
            self._boxes = []
            for hd in hands:
                mn = hd.xy.min(axis=0)
                mx = hd.xy.max(axis=0)
                pad = max(18.0, 0.35 * float(max(mx - mn)))
                self._boxes.append(
                    (
                        int(max(0, mn[0] - pad)),
                        int(max(0, mn[1] - pad)),
                        int(min(frame.shape[1], mx[0] + pad)),
                        int(min(frame.shape[0], mx[1] + pad)),
                    )
                )
        return HandResult(hands, (time.perf_counter() - t0) * 1000.0)
