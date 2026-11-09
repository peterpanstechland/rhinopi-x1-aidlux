#!/usr/bin/env python3
"""Upper-body gestures in mirrored screen coordinates, scaled to shoulder width."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from pose_tracker import PoseResult


def _p(pose: PoseResult, idx: int, min_vis: float = 0.25):
    if not pose.ok or idx >= min(len(pose.xy), len(pose.vis)) or not pose.vis[idx] >= min_vis:
        return None
    point = pose.xy[idx]
    return point if np.isfinite(point).all() else None


def _mid(a, b):
    if a is None or b is None:
        return None
    return (a + b) * 0.5


@dataclass
class Motion:
    wings: float = 0.0
    wing_l: float = 0.0
    wing_r: float = 0.0
    flap: float = 0.0
    wave: float = 0.0
    lean: float = 0.0
    lean_dir: float = 0.0
    piano: float = 0.0
    piano_lx: float = 0.35
    piano_rx: float = 0.65
    hands_up: float = 0.0
    jump: float = 0.0
    jump_armed: bool = True
    turn: float = 0.0
    turn_dir: float = 0.0
    nod: float = 0.0
    energy: float = 0.0
    span: float = 0.0
    piano_side: str = ""
    nod_count: int = 0
    wave_side: float = 0.0
    flap_beat: bool = False
    shoulders_seen: bool = False
    face_seen: bool = False
    wrist_count: int = 0


@dataclass
class Stroke:
    """Emit a direction only after moving a minimum distance from the last extreme."""
    extreme: float | None = None
    direction: int = 0

    def reset(self) -> None:
        self.extreme = None
        self.direction = 0

    def update(self, value: float, distance: float) -> int:
        if self.extreme is None:
            self.extreme = value
            return 0
        delta = value - self.extreme
        if self.direction >= 0 and delta <= -distance:
            self.direction = -1
        elif self.direction <= 0 and delta >= distance:
            self.direction = 1
        else:
            if delta * self.direction > 0:
                self.extreme = value
            return 0
        self.extreme = value
        return self.direction


@dataclass
class GestureTracker:
    prev_l: np.ndarray | None = None
    prev_r: np.ndarray | None = None
    prev_mid_y: float | None = None
    jump_armed: bool = True
    nod_count: int = 0
    jump_home_y: float | None = None
    nod_dipped: bool = False
    flap_lifted: bool = False
    nod_stroke: Stroke = field(default_factory=Stroke)
    flap_extrema: tuple[float, float] | None = None
    wave_strokes: tuple[Stroke, Stroke] = field(default_factory=lambda: (Stroke(), Stroke()))
    piano_strokes: tuple[Stroke, Stroke] = field(default_factory=lambda: (Stroke(), Stroke()))
    lean_e: float = 0.0
    home_sh_x: float | None = None
    turn_e: float = 0.0

    def _reset_head(self) -> None:
        self.nod_stroke.reset()
        self.nod_dipped = False
        self.lean_e = self.turn_e = 0.0
        self.home_sh_x = None

    def _head(self, m: Motion, pose: PoseResult, nose, mid_sh, mid_hip, sh_w: float) -> None:
        if nose is None:
            self._reset_head()
            return
        m.face_seen = True
        raw_lean = (nose[0] - mid_sh[0]) / (sh_w * .42)
        if mid_hip is not None:
            torso = (mid_sh[0] - mid_hip[0]) / (sh_w * .55)
            raw_lean = .75 * raw_lean + .25 * torso
        if self.home_sh_x is None:
            self.home_sh_x = float(mid_sh[0])
        self.home_sh_x = .97 * self.home_sh_x + .03 * float(mid_sh[0])
        shift = (mid_sh[0] - self.home_sh_x) / (sh_w * .85)
        self.lean_e = .78 * self.lean_e + .22 * float(np.clip(.7 * raw_lean + .3 * shift, -1.35, 1.35))
        m.lean_dir = float(np.clip(self.lean_e, -1, 1)) if abs(self.lean_e) >= .1 else 0.0
        m.lean = abs(m.lean_dir)

        left_ear, right_ear = _p(pose, 7, .12), _p(pose, 8, .12)
        yaw = (nose[0] - mid_sh[0]) / (sh_w * .38)
        if left_ear is not None and right_ear is not None:
            ear_w = abs(right_ear[0] - left_ear[0])
            ear_mid = (right_ear[0] + left_ear[0]) * .5
            offset = (nose[0] - ear_mid) / max(ear_w * .45, sh_w * .10)
            near = (abs(nose[0] - left_ear[0]) - abs(nose[0] - right_ear[0])) / max(ear_w, 1)
            yaw = .6 * offset + .4 * near
        # With a single visible ear, nose offset still measures direction; disappearance alone is not a turn.
        self.turn_e = .72 * self.turn_e + .28 * float(np.clip(yaw, -1.4, 1.4))
        m.turn_dir = float(np.clip(self.turn_e, -1, 1))
        m.turn = abs(m.turn_dir)

        # Nose relative to shoulders rejects a whole-body bounce. Score on the return up.
        depth = float((nose[1] - mid_sh[1]) / sh_w)
        direction = self.nod_stroke.update(depth, .065)
        if direction == 1:
            self.nod_dipped = True
        elif direction == -1 and self.nod_dipped:
            self.nod_count += 1
            self.nod_dipped = False
            m.nod = 1.0
        m.nod_count = self.nod_count

    def _wave(self, m: Motion, l_wr, r_wr, mid_sh, sh_w: float) -> None:
        for wrist, stroke in zip((l_wr, r_wr), self.wave_strokes):
            if wrist is None or wrist[1] > mid_sh[1] + .20 * sh_w:
                stroke.reset()
                continue
            offset = float((wrist[0] - mid_sh[0]) / sh_w)
            direction = stroke.update(offset, .15)
            if direction:
                m.wave_side = float(direction)
                m.wave = 1.0

    def update(self, pose: PoseResult, frame_shape=None) -> Motion:
        if pose.ok and frame_shape is not None:
            height, width = frame_shape[:2]
            x, y = pose.xy.T
            inside = (x >= 0) & (x < width) & (y >= 0) & (y < height)
            pose = replace(pose, vis=np.where(inside, pose.vis, 0))
        l_sh, r_sh = _p(pose, 11), _p(pose, 12)
        l_wr, r_wr = _p(pose, 15), _p(pose, 16)
        mid_sh = _mid(l_sh, r_sh)
        m = Motion(nod_count=self.nod_count)
        sh_w = float(np.linalg.norm(r_sh - l_sh)) if mid_sh is not None else 0.0
        if sh_w < 8:
            self._reset_head()
            self.flap_extrema = None
            self.flap_lifted = False
            for stroke in (*self.wave_strokes, *self.piano_strokes):
                stroke.reset()
            self.prev_l = self.prev_r = self.prev_mid_y = None
            self.jump_home_y = None
            self.jump_armed = True
            return m
        m.shoulders_seen = True
        m.wrist_count = int(l_wr is not None) + int(r_wr is not None)
        self._head(m, pose, _p(pose, 0), mid_sh, _mid(_p(pose, 23), _p(pose, 24)), sh_w)
        self._wave(m, l_wr, r_wr, mid_sh, sh_w)
        previous_y = self.prev_mid_y
        self.prev_mid_y = float(mid_sh[1])
        rise = (previous_y - self.prev_mid_y) / sh_w if previous_y is not None else 0.0
        for side, wrist, prev, stroke in zip(("l", "r"), (l_wr, r_wr), (self.prev_l, self.prev_r), self.piano_strokes):
            if wrist is None:
                stroke.reset()
                continue
            if prev is not None:
                m.energy += float(np.linalg.norm(wrist - prev)) / sh_w
            key_x = float(np.clip((wrist[0] - mid_sh[0]) / (sh_w * 2.6) + .5, .03, .97))
            if side == "l":
                m.piano_lx = key_x
            else:
                m.piano_rx = key_x
            if stroke.update(float((wrist[1] - mid_sh[1]) / sh_w), .10) == 1 and not m.piano_side:
                m.piano, m.piano_side = 1.0, side

        power_up = False
        if l_wr is not None and r_wr is not None:
            m.span = float(abs(r_wr[0] - l_wr[0])) / sh_w
            l_reach = float((l_sh[0] - l_wr[0]) / sh_w)
            r_reach = float((r_wr[0] - r_sh[0]) / sh_w)
            l_lvl = 1.0 - abs(float(l_wr[1] - l_sh[1])) / (sh_w * 0.75)
            r_lvl = 1.0 - abs(float(r_wr[1] - r_sh[1])) / (sh_w * 0.75)
            m.wing_l = float(np.clip(l_reach / .85, 0, 1) * np.clip(l_lvl, .25, 1))
            m.wing_r = float(np.clip(r_reach / .85, 0, 1) * np.clip(r_lvl, .25, 1))
            m.wings = min(m.wing_l, m.wing_r)
            mid_y = (l_wr[1] + r_wr[1]) * 0.5
            if abs(mid_y - mid_sh[1]) > sh_w * 1.1:
                m.wings *= 0.45
                m.wing_l *= 0.45
                m.wing_r *= 0.45
            # Both wrists must clear shoulder height for the two-hand launch.
            m.hands_up = float(np.clip(min(l_sh[1] - l_wr[1], r_sh[1] - r_wr[1]) / (sh_w * .40), 0, 1))
            if self.prev_l is not None and self.prev_r is not None:
                delta_l = (l_wr[1] - self.prev_l[1]) / sh_w + rise
                delta_r = (r_wr[1] - self.prev_r[1]) / sh_w + rise
                power_up = m.span < 1.55 and max(delta_l, delta_r) < -.04 and m.hands_up >= .18
                if delta_l * delta_r > 0:
                    m.flap = float(np.clip(min(abs(delta_l), abs(delta_r)) / .12, 0, 1))
            if min(l_reach, r_reach) > .30:
                # Each wing travels the full distance on each half of the same beat.
                heights = ((l_wr[1] - l_sh[1]) / sh_w, (r_wr[1] - r_sh[1]) / sh_w)
                old = self.flap_extrema or heights
                extreme = min if self.flap_lifted else max
                self.flap_extrema = tuple(extreme(a, b) for a, b in zip(old, heights))
                direction = 1 if self.flap_lifted else -1
                if m.flap > .03 and all(direction * (h - peak) >= .18 for h, peak in zip(heights, self.flap_extrema)):
                    m.flap_beat = self.flap_lifted
                    self.flap_lifted = not self.flap_lifted
                    self.flap_extrema = heights
            else:
                self.flap_extrema = None
                self.flap_lifted = False
        else:
            self.flap_extrema = None
            self.flap_lifted = False

        if self.jump_armed and (rise > .055 or power_up):
            m.jump = 1.0
            self.jump_armed = False
            self.jump_home_y = previous_y if rise > .055 else None
        elif (self.jump_home_y is None or self.prev_mid_y >= self.jump_home_y - sh_w * .03) and m.hands_up < .08:
            self.jump_armed = True
            self.jump_home_y = None
        m.jump_armed = self.jump_armed
        self.prev_l, self.prev_r = l_wr, r_wr
        return m
