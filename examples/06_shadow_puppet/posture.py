#!/usr/bin/env python3
"""Sitting posture from upper-body landmarks: forward head, slouch, tilt, distance."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pose_tracker import PoseResult

# neck ratio = (shoulder_mid_y - nose_y) / shoulder_width
NECK_GOOD = 0.62
NECK_BAD = 0.34
# shoulder line slope, normalized by shoulder width
TILT_GOOD = 0.05
TILT_BAD = 0.16
# nose horizontal offset from shoulder mid
SHIFT_GOOD = 0.10
SHIFT_BAD = 0.30
# shoulder width as a share of frame width
NEAR_GOOD = 0.46
NEAR_BAD = 0.68
# shoulder line height as a share of frame height (sinking in the chair)
SINK_GOOD = 0.62
SINK_BAD = 0.82

BAD_ENTER = 62.0
BAD_EXIT = 72.0
NUDGE_AFTER = 25.0
NUDGE_EVERY = 60.0

LABELS = {
    "neck": ("低头前伸", "把下巴收回来，屏幕抬高一点"),
    "tilt": ("肩膀歪了", "两边肩膀放平，别单肩扛"),
    "shift": ("身子偏了", "坐回椅子正中"),
    "near": ("离屏幕太近", "往后靠一点，背贴靠背"),
    "sink": ("整个人往下塌", "坐直，让椅背托住腰"),
}


def _ramp(v: float, good: float, bad: float) -> float:
    """0 at good, 1 at bad."""
    if bad == good:
        return 0.0
    return float(np.clip((v - good) / (bad - good), 0.0, 1.0))


@dataclass
class PostureReading:
    ok: bool = False
    score: float = 100.0
    worst: str = ""
    title: str = ""
    advice: str = ""
    neck: float = 0.0
    tilt: float = 0.0
    shift: float = 0.0
    near: float = 0.0
    sink: float = 0.0


@dataclass
class PostureWatch:
    score: float = 100.0
    reading: PostureReading = field(default_factory=PostureReading)
    bad: bool = False
    bad_s: float = 0.0
    bad_total: float = 0.0
    good_total: float = 0.0
    nudge_t: float = 0.0
    nudge: str = ""
    nudge_hold: float = 0.0
    samples: int = 0
    sum_score: float = 0.0
    stale: float = 9.0
    base_neck: float = 0.0
    base_sink: float = 0.0
    _cal_n: int = 0
    _cal_neck: float = 0.0
    _cal_sink: float = 0.0

    @property
    def avg(self) -> float:
        return self.sum_score / self.samples if self.samples else 100.0

    def recalibrate(self) -> None:
        """Called right after a stretch round: the person is sitting up now."""
        self._cal_n = 0
        self._cal_neck = 0.0
        self._cal_sink = 0.0
        self.base_neck = 0.0
        self.base_sink = 0.0

    def measure(self, pose: PoseResult, shape) -> PostureReading:
        r = PostureReading()
        if not pose.ok or len(pose.xy) < 25:
            return r
        h, w = shape[:2]

        def p(i, min_vis=0.25):
            if i >= len(pose.xy) or pose.vis[i] < min_vis:
                return None
            return pose.xy[i]

        l_sh, r_sh, nose = p(11), p(12), p(0)
        if l_sh is None or r_sh is None or nose is None:
            return r
        sh_w = float(abs(r_sh[0] - l_sh[0]))
        if sh_w < w * 0.08:
            return r
        mid_x = (l_sh[0] + r_sh[0]) * 0.5
        mid_y = (l_sh[1] + r_sh[1]) * 0.5

        neck = float((mid_y - nose[1]) / sh_w)
        tilt = float(abs(l_sh[1] - r_sh[1]) / sh_w)
        shift = float(abs(nose[0] - mid_x) / sh_w)
        near = float(sh_w / w)
        sink = float(mid_y / h)

        if self._cal_n < 45:
            self._cal_n += 1
            self._cal_neck += neck
            self._cal_sink += sink
            if self._cal_n == 45:
                self.base_neck = self._cal_neck / 45.0
                self.base_sink = self._cal_sink / 45.0

        neck_good, neck_bad = NECK_GOOD, NECK_BAD
        sink_good, sink_bad = SINK_GOOD, SINK_BAD
        if self.base_neck > 0.2:
            neck_good = max(NECK_BAD + 0.08, min(self.base_neck, 1.2))
            neck_bad = neck_good * 0.55
        if self.base_sink > 0.2:
            sink_good = min(self.base_sink + 0.03, 0.9)
            sink_bad = min(sink_good + 0.18, 0.97)

        r.neck = _ramp(-neck, -neck_good, -neck_bad)
        r.tilt = _ramp(tilt, TILT_GOOD, TILT_BAD)
        r.shift = _ramp(shift, SHIFT_GOOD, SHIFT_BAD)
        r.near = _ramp(near, NEAR_GOOD, NEAR_BAD)
        r.sink = _ramp(sink, sink_good, sink_bad)

        pen = 46 * r.neck + 22 * r.tilt + 16 * r.shift + 22 * r.near + 26 * r.sink
        r.score = float(np.clip(100.0 - pen, 0.0, 100.0))
        worst_key, worst_val = "", 0.0
        for key in ("neck", "sink", "near", "tilt", "shift"):
            v = getattr(r, key)
            if v > worst_val:
                worst_key, worst_val = key, v
        if worst_val > 0.35:
            r.worst = worst_key
            r.title, r.advice = LABELS[worst_key]
        r.ok = True
        return r

    def step(self, pose: PoseResult, shape, dt: float, active: bool = True) -> PostureReading:
        r = self.measure(pose, shape)
        self.nudge_hold = max(0.0, self.nudge_hold - dt)
        if not r.ok:
            # pose drops out constantly while typing; hold the last reading
            self.stale += dt
            return self.reading if self.stale < 2.5 else r
        self.stale = 0.0
        self.reading = r
        self.score = 0.9 * self.score + 0.1 * r.score
        self.samples += 1
        self.sum_score += r.score
        if not active:
            return r
        if self.score < BAD_ENTER:
            self.bad = True
        elif self.score > BAD_EXIT:
            self.bad = False
            self.bad_s = 0.0
        if self.bad:
            self.bad_s += dt
            self.bad_total += dt
            self.nudge_t += dt
            if self.bad_s > NUDGE_AFTER and self.nudge_t > NUDGE_EVERY:
                self.nudge_t = 0.0
                self.nudge = r.title or "坐姿走形了"
                self.nudge_hold = 4.0
        else:
            self.good_total += dt
            self.nudge_t = min(self.nudge_t, NUDGE_EVERY)
        return r

    def grade(self) -> str:
        s = self.avg
        if s >= 88:
            return "S"
        if s >= 76:
            return "A"
        if s >= 62:
            return "B"
        return "C"

    def snapshot(self) -> dict:
        r = self.reading
        return {
            "score": round(self.score, 1),
            "avg": round(self.avg, 1),
            "grade": self.grade(),
            "bad": self.bad,
            "bad_s": round(self.bad_s, 1),
            "bad_total": round(self.bad_total, 1),
            "worst": r.worst,
            "title": r.title,
            "advice": r.advice,
            "tracked": r.ok and self.stale < 2.5,
        }
