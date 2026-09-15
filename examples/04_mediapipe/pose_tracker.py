#!/usr/bin/env python3
"""BlazePose via onboard AidLite TFLite models (not the PyPI mediapipe wheel)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DEFAULT_MODEL_DIR = Path("/opt/aidlux/app/aid-examples/pose_detect_track/models")

# MediaPipe Pose 33 + 6 extra (full-body tflite).
POSE_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    (11, 13), (13, 15), (15, 17), (17, 19), (19, 15), (15, 21),
    (12, 14), (14, 16), (16, 18), (18, 20), (20, 16), (16, 22),
    (11, 12), (12, 24), (24, 23), (23, 11),
    (23, 25), (25, 27), (24, 26), (26, 28),
    (27, 29), (27, 31), (28, 30), (28, 32),
)

# After a selfie flip, MediaPipe sometimes still labels left/right as if
# the image were unmirrored. Force index 11 onto the image-left side.
LR_PAIRS = (
    (1, 4), (2, 5), (3, 6), (7, 8), (9, 10),
    (11, 12), (13, 14), (15, 16), (17, 18), (19, 20), (21, 22),
    (23, 24), (25, 26), (27, 28), (29, 30), (31, 32),
)

LM = {
    "nose": 0,
    "l_sh": 11,
    "r_sh": 12,
    "l_el": 13,
    "r_el": 14,
    "l_wr": 15,
    "r_wr": 16,
    "l_hip": 23,
    "r_hip": 24,
    "l_knee": 25,
    "r_knee": 26,
    "l_ank": 27,
    "r_ank": 28,
}


def _ensure_screen_left(xy: np.ndarray, vis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Make landmark 11 the shoulder on the left side of the image."""
    if len(xy) <= 12:
        return xy, vis
    if float(xy[11][0]) <= float(xy[12][0]):
        return xy, vis
    xy = xy.copy()
    vis = vis.copy()
    for a, b in LR_PAIRS:
        if b >= len(xy):
            continue
        xy[a], xy[b] = xy[b].copy(), xy[a].copy()
        vis[a], vis[b] = float(vis[b]), float(vis[a])
    return xy, vis


@dataclass
class PoseResult:
    ok: bool
    xy: np.ndarray  # (N, 2) image pixels
    vis: np.ndarray  # (N,)
    infer_ms: float


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _build_tflite(path: str, in_shape: list, out_shapes: list, accel: str):
    import aidlite

    model = aidlite.Model.create_instance(path)
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
    if itp is None:
        raise RuntimeError(f"cannot build interpreter {path}")
    if itp.init() != 0 or itp.load_model() != 0:
        raise RuntimeError(f"cannot init/load {path}")
    return itp


def _resize_pad(img: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
    h0, w0 = img.shape[:2]
    if h0 >= w0:
        h1, w1 = 256, 256 * w0 // h0
        padh, padw = 0, 256 - w1
        scale = w0 / w1
    else:
        h1, w1 = 256 * h0 // w0, 256
        padh, padw = 256 - h1, 0
        scale = h0 / h1
    padh1, padh2 = padh // 2, padh // 2 + padh % 2
    padw1, padw2 = padw // 2, padw // 2 + padw % 2
    img1 = cv2.resize(img, (w1, h1))
    img1 = np.pad(img1, ((padh1, padh2), (padw1, padw2), (0, 0)), constant_values=0)
    pad = (int(padh1 * scale), int(padw1 * scale))
    img2 = cv2.resize(img1, (128, 128))
    return img2, scale, pad


def _decode_boxes(raw_boxes: np.ndarray, anchors: np.ndarray) -> np.ndarray:
    boxes = np.zeros_like(raw_boxes)
    x_center = raw_boxes[..., 0] / 128.0 * anchors[:, 2] + anchors[:, 0]
    y_center = raw_boxes[..., 1] / 128.0 * anchors[:, 3] + anchors[:, 1]
    w = raw_boxes[..., 2] / 128.0 * anchors[:, 2]
    h = raw_boxes[..., 3] / 128.0 * anchors[:, 3]
    boxes[..., 0] = y_center - h / 2.0
    boxes[..., 1] = x_center - w / 2.0
    boxes[..., 2] = y_center + h / 2.0
    boxes[..., 3] = x_center + w / 2.0
    for k in range(4):
        offset = 4 + k * 2
        boxes[..., offset] = raw_boxes[..., offset] / 128.0 * anchors[:, 2] + anchors[:, 0]
        boxes[..., offset + 1] = raw_boxes[..., offset + 1] / 128.0 * anchors[:, 3] + anchors[:, 1]
    return boxes


def _nms(dets: np.ndarray, thresh: float) -> np.ndarray:
    if dets.size == 0:
        return dets.reshape(0, 13)
    x1, y1, x2, y2 = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3]
    scores = dets[:, 12]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[np.ndarray] = []
    while order.size > 0:
        i = order[0]
        keep.append(dets[i])
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return np.stack(keep) if keep else dets.reshape(0, 13)


def _denorm_det(det: np.ndarray, scale: float, pad: tuple[int, int]) -> np.ndarray:
    out = det.copy()
    out[:, 0] = out[:, 0] * scale * 256 - pad[0]
    out[:, 1] = out[:, 1] * scale * 256 - pad[1]
    out[:, 2] = out[:, 2] * scale * 256 - pad[0]
    out[:, 3] = out[:, 3] * scale * 256 - pad[1]
    out[:, 4::2] = out[:, 4::2] * scale * 256 - pad[1]
    out[:, 5::2] = out[:, 5::2] * scale * 256 - pad[0]
    return out


def _detection_to_roi(detection: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    kp1, kp2 = 2, 3
    theta0 = np.pi / 2
    dscale = 1.5
    xc = detection[:, 4 + 2 * kp1]
    yc = detection[:, 4 + 2 * kp1 + 1]
    x1 = detection[:, 4 + 2 * kp2]
    y1 = detection[:, 4 + 2 * kp2 + 1]
    scale = np.sqrt((xc - x1) ** 2 + (yc - y1) ** 2) * 2 * dscale
    theta = np.arctan2(detection[:, 4 + 2 * kp1 + 1] - y1, detection[:, 4 + 2 * kp1] - x1) - theta0
    return xc, yc, scale, theta


def _extract_roi(frame: np.ndarray, xc, yc, theta, scale):
    points = np.array([[-1, -1, 1, 1], [-1, 1, -1, 1]], dtype=np.float32).reshape(1, 2, 4)
    points = points * scale.reshape(-1, 1, 1) / 2
    theta = theta.reshape(-1, 1, 1)
    rot = np.concatenate(
        (
            np.concatenate((np.cos(theta), -np.sin(theta)), 2),
            np.concatenate((np.sin(theta), np.cos(theta)), 2),
        ),
        1,
    )
    center = np.concatenate((xc.reshape(-1, 1, 1), yc.reshape(-1, 1, 1)), 1)
    points = rot @ points + center
    res = 256
    dst = np.array([[0, 0], [0, res - 1], [res - 1, 0]], dtype=np.float32)
    imgs, affines = [], []
    for i in range(points.shape[0]):
        src = points[i, :, :3].T.astype(np.float32)
        mat = cv2.getAffineTransform(src, dst)
        imgs.append(cv2.warpAffine(frame, mat, (res, res)))
        affines.append(cv2.invertAffineTransform(mat).astype(np.float32))
    if not imgs:
        return np.zeros((0, res, res, 3), np.float32), np.zeros((0, 2, 3), np.float32)
    return np.stack(imgs).astype(np.float32) / 255.0, np.stack(affines)


class PoseTracker:
    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        accel: str = "GPU",
        score_thresh: float = 0.42,
        flag_thresh: float = 0.5,
        smooth: float = 0.35,
        full_body: bool = True,
        selfie: bool = False,
    ) -> None:
        model_dir = Path(model_dir)
        self.score_thresh = score_thresh
        self.flag_thresh = flag_thresh
        self.smooth = smooth
        self.full_body = full_body
        # When True, input is expected to be cv2.flip(..., 1) and we force
        # landmark 11 onto the left side of the image if the model disagrees.
        self.selfie = selfie
        self.anchors = np.load(model_dir / "anchors.npy")
        self.det = _build_tflite(
            str(model_dir / "pose_detection.tflite"),
            [[1, 128, 128, 3]],
            [[1, 896, 12, 4], [1, 896, 1, 4]],
            accel,
        )
        if full_body:
            lm_name, n_pts, out0 = "pose_landmark_full_body.tflite", 39, [1, 195, 1, 1]
        else:
            lm_name, n_pts, out0 = "pose_landmark_upper_body.tflite", 31, [1, 155, 4, 1]
        self.n_pts = n_pts
        self.lm = _build_tflite(
            str(model_dir / lm_name),
            [[1, 256, 256, 3]],
            [out0, [1, 1, 1, 1], [1, 128, 128, 1]],
            accel,
        )
        self._xy: np.ndarray | None = None

    def infer(self, bgr: np.ndarray) -> PoseResult:
        import time

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        img2, scale, pad = _resize_pad(rgb)
        inp = np.ascontiguousarray(img2.astype(np.float32) / 255.0)
        t0 = time.perf_counter()
        if self.det.set_input_tensor(0, inp) != 0 or self.det.invoke() != 0:
            return PoseResult(False, np.zeros((self.n_pts, 2)), np.zeros(self.n_pts), 0.0)
        boxes = self.det.get_output_tensor(0).reshape(896, -1)
        scores = self.det.get_output_tensor(1).reshape(-1)
        raw = _decode_boxes(boxes, self.anchors)
        conf = _sigmoid(scores)
        mask = conf >= self.score_thresh
        if not np.any(mask):
            self._xy = None
            return PoseResult(False, np.zeros((self.n_pts, 2)), np.zeros(self.n_pts), (time.perf_counter() - t0) * 1000)
        dets = np.hstack((raw[mask], conf[mask, None]))
        dets = _nms(dets, 0.3)
        dets = _denorm_det(dets, scale, pad)
        xc, yc, roi_scale, theta = _detection_to_roi(dets[:1])
        crops, affines = _extract_roi(rgb, xc, yc, theta, roi_scale)
        if crops.shape[0] == 0:
            return PoseResult(False, np.zeros((self.n_pts, 2)), np.zeros(self.n_pts), (time.perf_counter() - t0) * 1000)
        crop = np.ascontiguousarray(crops[:1])
        if self.lm.set_input_tensor(0, crop) != 0 or self.lm.invoke() != 0:
            return PoseResult(False, np.zeros((self.n_pts, 2)), np.zeros(self.n_pts), (time.perf_counter() - t0) * 1000)
        flag = float(self.lm.get_output_tensor(1).reshape(-1)[0])
        landmarks = self.lm.get_output_tensor(0).reshape(1, self.n_pts, -1).copy()
        affine = affines[0]
        xy = (affine[:, :2] @ landmarks[0, :, :2].T + affine[:, 2:]).T
        vis = landmarks[0, :, 3] if landmarks.shape[-1] >= 4 else np.ones(self.n_pts)
        if self.selfie:
            xy, vis = _ensure_screen_left(xy, vis)
        infer_ms = (time.perf_counter() - t0) * 1000
        if flag < self.flag_thresh:
            self._xy = None
            return PoseResult(False, xy, vis, infer_ms)
        if self._xy is None:
            self._xy = xy
        else:
            self._xy = self.smooth * xy + (1.0 - self.smooth) * self._xy
        return PoseResult(True, self._xy.copy(), vis, infer_ms)


def draw_skeleton(img: np.ndarray, pose: PoseResult, color=(80, 220, 255)) -> np.ndarray:
    if not pose.ok:
        return img
    for a, b in POSE_CONNECTIONS:
        if a >= len(pose.xy) or b >= len(pose.xy):
            continue
        if pose.vis[a] < 0.2 or pose.vis[b] < 0.2:
            continue
        pa = tuple(np.round(pose.xy[a]).astype(int))
        pb = tuple(np.round(pose.xy[b]).astype(int))
        cv2.line(img, pa, pb, (240, 240, 240), 2, cv2.LINE_AA)
    for i, pt in enumerate(pose.xy[:33]):
        if pose.vis[i] < 0.2:
            continue
        cv2.circle(img, tuple(np.round(pt).astype(int)), 4, color, -1, cv2.LINE_AA)
    return img
