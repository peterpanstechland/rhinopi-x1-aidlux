#!/usr/bin/env python3
"""Upper-body gestures that work in a desk webcam crop."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pose_tracker import PoseResult


def _p(pose: PoseResult, idx: int, min_vis: float = 0.12):
    if not pose.ok or idx >= len(pose.xy) or pose.vis[idx] < min_vis:
        return None
    return pose.xy[idx]


def _mid(a, b):
    if a is None or b is None:
        return None
    return (a + b) * 0.5


@dataclass
class Motion:
    wings: float = 0.0
    wing_l: float = 0.0  # left arm T-pose quality 0..1
    wing_r: float = 0.0
    flap: float = 0.0
    wave: float = 0.0
    lean: float = 0.0
    lean_dir: float = 0.0
    piano: float = 0.0
    piano_x: float = 0.5  # 0..1 across body for pose-fallback keys
    hands_up: float = 0.0
    jump: float = 0.0  # 1-frame pulse
    jump_armed: bool = True
    turn: float = 0.0
    turn_dir: float = 0.0
    nod: float = 0.0
    energy: float = 0.0
    span: float = 0.0
    piano_side: str = ""
    nod_count: int = 0
    wave_side: float = 0.0


@dataclass
class GestureTracker:
    prev_l: np.ndarray | None = None
    prev_r: np.ndarray | None = None
    prev_nose: np.ndarray | None = None
    prev_mid_y: float | None = None
    flap_e: float = 0.0
    wave_e: float = 0.0
    piano_e: float = 0.0
    nod_e: float = 0.0
    last_up: str = ""
    nod_count: int = 0
    nod_armed: bool = True
    jump_armed: bool = True
    nod_down: float = 0.0
    flap_dir: float = 0.0
    prev_wy: float | None = None

    def update(self, pose: PoseResult) -> Motion:
        l_sh, r_sh = _p(pose, 11), _p(pose, 12)
        l_wr, r_wr = _p(pose, 15), _p(pose, 16)
        l_hip, r_hip = _p(pose, 23), _p(pose, 24)
        nose = _p(pose, 0)
        mid_sh = _mid(l_sh, r_sh)
        mid_hip = _mid(l_hip, r_hip)
        m = Motion()
        if mid_sh is None or l_wr is None or r_wr is None or l_sh is None or r_sh is None:
            self.prev_l = l_wr
            self.prev_r = r_wr
            self.prev_nose = nose
            self.prev_mid_y = None
            return m
        sh_w = float(np.linalg.norm(r_sh - l_sh)) + 1e-3
        span = float(abs(r_wr[0] - l_wr[0])) / sh_w
        m.span = span
        # per-arm T-pose: reach out + stay near shoulder height
        l_reach = float((l_sh[0] - l_wr[0]) / sh_w)  # left wrist further left
        r_reach = float((r_wr[0] - r_sh[0]) / sh_w)
        l_lvl = 1.0 - abs(float(l_wr[1] - l_sh[1])) / (sh_w * 0.75)
        r_lvl = 1.0 - abs(float(r_wr[1] - r_sh[1])) / (sh_w * 0.75)
        m.wing_l = float(np.clip(l_reach / 0.85, 0.0, 1.0) * np.clip(l_lvl, 0.25, 1.0))
        m.wing_r = float(np.clip(r_reach / 0.85, 0.0, 1.0) * np.clip(r_lvl, 0.25, 1.0))
        m.wings = float(min(m.wing_l, m.wing_r))
        mid_y = (l_wr[1] + r_wr[1]) * 0.5
        if abs(mid_y - mid_sh[1]) > sh_w * 1.1:
            m.wings *= 0.45
            m.wing_l *= 0.45
            m.wing_r *= 0.45
        # horizontal hand position for piano fallback (0=left … 1=right of torso)
        mid_x = float(mid_sh[0])
        m.piano_x = float(np.clip(((l_wr[0] + r_wr[0]) * 0.5 - mid_x) / (sh_w * 2.2) + 0.5, 0.0, 1.0))

        # hands_up: average wrist height vs shoulders (desk-friendly)
        l_el, r_el = _p(pose, 13), _p(pose, 14)
        avg_wr_y = float((l_wr[1] + r_wr[1]) * 0.5)
        clear = float(mid_sh[1] - avg_wr_y)
        m.hands_up = float(np.clip(clear / (sh_w * 0.40), 0.0, 1.0))
        if clear < -sh_w * 0.15:
            m.hands_up = 0.0
        # elbows up also counts (wrists often clipped at frame top)
        if l_el is not None and r_el is not None:
            el_avg = float((l_el[1] + r_el[1]) * 0.5)
            el_up = float(np.clip((mid_sh[1] - el_avg) / (sh_w * 0.35), 0.0, 1.0))
            m.hands_up = float(max(m.hands_up, el_up * 0.9))

        # JUMP (dino): chair bounce — shoulders rise as a whole.
        # Deliberately NOT "arms flap" so it won't feel like eagle.
        both_rising = False
        if self.prev_l is not None and self.prev_r is not None:
            up_l = float(self.prev_l[1] - l_wr[1])
            up_r = float(self.prev_r[1] - r_wr[1])
            both_rising = up_l > 8 and up_r > 8
        hop = False
        if self.prev_mid_y is not None:
            hop = (self.prev_mid_y - float(mid_sh[1])) > sh_w * 0.055
        # backup: fists near torso then push up once (arms close, not T-pose)
        arms_in = span < 1.55
        power_up = arms_in and both_rising and m.hands_up >= 0.18
        if self.jump_armed and (hop or power_up):
            m.jump = 1.0
            self.jump_armed = False
        elif (not hop) and m.hands_up < 0.08 and (
            self.prev_mid_y is None
            or abs(self.prev_mid_y - float(mid_sh[1])) < sh_w * 0.025
        ):
            self.jump_armed = True

        if mid_hip is not None:
            m.lean_dir = float(np.clip((mid_sh[0] - mid_hip[0]) / (sh_w * 0.55), -1.0, 1.0))
        else:
            m.lean_dir = float(np.clip((r_sh[1] - l_sh[1]) / (sh_w * 0.35), -1.0, 1.0))
        m.lean = abs(m.lean_dir)
        if nose is not None:
            off = float((nose[0] - mid_sh[0]) / (sh_w * 0.45))
            m.turn_dir = float(np.clip(off, -1.0, 1.0))
            m.turn = abs(m.turn_dir)
        if self.prev_l is not None and self.prev_r is not None:
            vl = float(np.linalg.norm(l_wr - self.prev_l))
            vr = float(np.linalg.norm(r_wr - self.prev_r))
            m.energy = (vl + vr) / sh_w
            self.wave_e = 0.65 * self.wave_e + 0.35 * min(1.6, (vl + vr) / (sh_w * 0.35))
            dx = (l_wr[0] - self.prev_l[0]) + (r_wr[0] - self.prev_r[0])
            m.wave_side = float(np.clip(dx / (sh_w * 0.25), -1.0, 1.0))
            # flap: wrist vertical motion — works for T-pose and V-pose
            wy = float((l_wr[1] + r_wr[1]) * 0.5)
            dy = abs((l_wr[1] - self.prev_l[1]) + (r_wr[1] - self.prev_r[1])) / 2
            self.flap_e = 0.35 * self.flap_e + 0.65 * min(1.7, dy / (sh_w * 0.10))
            if self.prev_wy is not None:
                dwy = self.prev_wy - wy  # >0 arms rising
                if self.flap_dir <= 0 and dwy > sh_w * 0.035:
                    self.flap_e = min(1.7, self.flap_e + 0.55)
                elif self.flap_dir >= 0 and dwy < -sh_w * 0.035:
                    self.flap_e = min(1.7, self.flap_e + 0.45)
                self.flap_dir = 1.0 if dwy > 0 else (-1.0 if dwy < 0 else self.flap_dir)
            self.prev_wy = wy
            up_l = l_wr[1] < r_wr[1] - 18
            up_now = "l" if up_l else "r"
            if up_now != self.last_up and abs(l_wr[1] - r_wr[1]) > 22:
                self.piano_e = min(1.4, self.piano_e + 0.35)
                self.last_up = up_now
            else:
                self.piano_e *= 0.92
            m.piano_side = self.last_up
        # don't multiply by wings — V-flap must still register
        m.flap = float(np.clip(self.flap_e, 0.0, 1.0))
        if self.prev_nose is not None and nose is not None:
            # Low-FPS friendly: accumulate a downward dip, count when it reverses
            # (or on one big down step if a whole nod lands in a single frame).
            dy = float(nose[1] - self.prev_nose[1])
            floor = max(5.0, sh_w * 0.04)
            self.nod_e = 0.25 * self.nod_e + 0.75 * min(1.8, abs(dy) / floor)
            if dy > 0.0:
                self.nod_down += dy
            if self.nod_armed and dy >= floor * 1.1:
                # one chunky down frame ≈ a nod at ~6 FPS
                self.nod_count += 1
                self.nod_armed = False
                self.nod_down = 0.0
            elif self.nod_armed and dy <= 0.0 and self.nod_down >= floor:
                self.nod_count += 1
                self.nod_armed = False
                self.nod_down = 0.0
            elif (not self.nod_armed) and dy <= -floor * 0.2:
                self.nod_armed = True
                self.nod_down = 0.0
            elif dy < 0.0 and self.nod_armed:
                self.nod_down = max(0.0, self.nod_down + dy * 0.5)
        m.nod_count = self.nod_count
        m.wave = float(np.clip(self.wave_e, 0.0, 1.0))
        m.piano = float(np.clip(self.piano_e, 0.0, 1.0))
        m.nod = float(np.clip(self.nod_e, 0.0, 1.0))
        m.jump_armed = self.jump_armed
        # flap already set above; keep a floor if only wings moved
        if m.flap <= 0.0:
            m.flap = float(np.clip(self.flap_e, 0.0, 1.0))
        self.prev_l, self.prev_r, self.prev_nose = l_wr, r_wr, nose
        self.prev_mid_y = float(mid_sh[1])
        return m
