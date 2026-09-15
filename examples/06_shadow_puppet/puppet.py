#!/usr/bin/env python3
"""Minecraft-Steve style avatar: fixed blocky proportions, mocap-driven limbs."""

from __future__ import annotations

import numpy as np

from pixel_ui import LIME, NIGHT, WHITE, PixelScreen
from pose_tracker import PoseResult

# Steve palette, BGR
SKIN = (104, 136, 181)
SKIN_LT = (120, 155, 200)
SKIN_DK = (73, 99, 142)
HAIR = (22, 32, 46)
HAIR_LT = (32, 45, 63)
EYE_W = (245, 245, 245)
EYE_B = (168, 60, 60)
SHIRT = (172, 172, 0)
SHIRT_DK = (132, 132, 0)
SHIRT_LT = (198, 198, 20)
PANTS = (165, 58, 58)
PANTS_DK = (126, 44, 44)
SHOE = (78, 78, 78)
MOUTH = (54, 75, 107)

PAL = {
    "H": HAIR,
    "h": HAIR_LT,
    "S": SKIN,
    "s": SKIN_DK,
    "W": EYE_W,
    "B": EYE_B,
    "M": MOUTH,
    ".": None,
}

HEAD = (
    ".HHHHHHHHHH.",
    "HHHHHHHHHHHH",
    "HHhHHHHHHhHH",
    "HHSSSSSSSSHH",
    "HHSWWBBWWSHH",
    "HHSWWBBWWSHH",
    "HHSSSSssSSHH",
    "HHSSMMMMSSHH",
    "HHSSSsssSSHH",
    "HHSSSSSSSSHH",
    ".HSSSSSSSSH.",
    "..SSSSSSSS..",
)

# Side profiles for the turn challenge (looking left / right on screen).
HEAD_L = (
    ".HHHHHHHHHH.",
    "HHHHHHHHHHHH",
    "HHHHHHHHHhHH",
    "HHSSSSSSSSHH",
    "HHSWWBBSSSHH",
    "HHSWWBBSSSHH",
    "HHSSSSssSSHH",
    "HHSSMMSSSSHH",
    "HHSSSsssSSHH",
    "HHSSSSSSSSHH",
    ".HSSSSSSSSH.",
    "..SSSSSSSS..",
)

HEAD_R = (
    ".HHHHHHHHHH.",
    "HHHHHHHHHHHH",
    "HHhHHHHHHHHH",
    "HHSSSSSSSSHH",
    "HHSSSBBWWSHH",
    "HHSSSBBWWSHH",
    "HHSSSSssSSHH",
    "HHSSSSMMSSHH",
    "HHSSSsssSSHH",
    "HHSSSSSSSSHH",
    ".HSSSSSSSSH.",
    "..SSSSSSSS..",
)

# Classic Steve ×1.5 — fits a 120px stage next to game props.
HEAD_W = 12
HEAD_H = 12
TORSO_W = 12
TORSO_H = 18
ARM_W = 4
LEG_W = 6
UPPER_ARM = 10
FORE_ARM = 10
LEG_H = 18
# shoulder → shoe; keep Stage.AV_SH_Y = GROUND - BODY_H in sync
BODY_H = TORSO_H + LEG_H  # 36

# shoulders sit this far below the top of the head block
SH_HALF = 6.0
LIMB_W = LEG_W  # back-compat alias


def _unit(v, fallback):
    n = float(np.linalg.norm(v))
    if n < 1e-3:
        return fallback
    return v / n


class PixelPuppet:
    """Body-space joints get smoothed; the body is drawn with fixed block sizes."""

    def __init__(self) -> None:
        self.j: dict[str, np.ndarray] = {}
        self.have = False
        self.lost = 9.0
        self.breathe = 0.0
        self.face = "idle"

    def update(self, pose: PoseResult, dt: float) -> bool:
        self.breathe += dt
        pts = self._read(pose)
        if pts is None:
            self.lost += dt
            return self.have and self.lost < 1.5
        self.lost = 0.0
        for name, v in pts.items():
            # nose drives the visible nod — keep it snappy
            if name == "nose":
                k = 0.85 if self.have else 1.0
            else:
                k = 0.45 if self.have else 1.0
            cur = self.j.get(name)
            self.j[name] = v if cur is None else cur + (v - cur) * k
        self.have = True
        return True

    def _read(self, pose: PoseResult):
        if not pose.ok or len(pose.xy) < 25:
            return None

        def p(i, min_vis=0.2):
            if i >= len(pose.xy) or pose.vis[i] < min_vis:
                return None
            return pose.xy[i].astype(np.float32)

        l_sh, r_sh = p(11), p(12)
        if l_sh is None or r_sh is None:
            return None
        # Bind by screen X so Steve's left matches the webcam's left side,
        # even if BlazePose left/right labels are still swapped once.
        l_el, r_el = p(13), p(14)
        l_wr, r_wr = p(15), p(16)
        if float(l_sh[0]) > float(r_sh[0]):
            l_sh, r_sh = r_sh, l_sh
            l_el, r_el = r_el, l_el
            l_wr, r_wr = r_wr, l_wr
        sw = float(abs(r_sh[0] - l_sh[0]))
        if sw < 30:
            return None
        mid = (l_sh + r_sh) * 0.5
        scale = 2.0 / sw

        def body(v):
            if v is None:
                return None
            return np.array([(v[0] - mid[0]) * scale, (v[1] - mid[1]) * scale], np.float32)

        raw = {
            "l_sh": l_sh,
            "r_sh": r_sh,
            "l_el": l_el,
            "r_el": r_el,
            "l_wr": l_wr,
            "r_wr": r_wr,
            "nose": p(0),
        }
        out = {}
        for name, v in raw.items():
            b = body(v)
            if b is not None:
                out[name] = b
        out.setdefault("nose", np.array([0.0, -1.6], np.float32))
        out.setdefault("l_el", out["l_sh"] + np.array([0.35, 1.0], np.float32))
        out.setdefault("r_el", out["r_sh"] + np.array([-0.35, 1.0], np.float32))
        out.setdefault("l_wr", out["l_el"] + np.array([0.2, 1.0], np.float32))
        out.setdefault("r_wr", out["r_el"] + np.array([-0.2, 1.0], np.float32))
        return out

    # ---------- drawing ----------

    def draw(
        self,
        scr: PixelScreen,
        cx: int,
        cy: int,
        accent=LIME,
        shirt=SHIRT,
        style: str = "",
        nod: float = 0.0,
        turn_dir: float = 0.0,
    ) -> None:
        """cy is the shoulder line; Steve stands BODY_H px tall below it.

        style='nod' → bobblehead + big vertical travel so the nod reads as a game beat.
        style='turn' → bigger head yaw.
        """
        if not self.have:
            return
        bob = int(1.0 * np.sin(self.breathe * 2.0))
        cy += bob
        down = np.array([0.0, 1.0], np.float32)
        bobble = style == "nod"
        turny = style == "turn"
        head_scale = 3 if bobble else (2 if turny else 1)
        hw = HEAD_W * head_scale
        hh = HEAD_H * head_scale

        # legs first — flush under the torso
        ly = cy + TORSO_H
        for dx in (-TORSO_W // 2, 0):
            scr.rect(cx + dx - 1, ly - 1, LEG_W + 2, LEG_H + 2, NIGHT)
            scr.rect(cx + dx, ly, LEG_W, LEG_H, PANTS)
            scr.rect(cx + dx, ly, 2, LEG_H, PANTS_DK)
            scr.rect(cx + dx + LEG_W - 2, ly, 1, LEG_H, PANTS_DK)
            scr.rect(cx + dx, ly + LEG_H - 4, LEG_W, 4, SHOE)
            scr.rect(cx + dx, ly + LEG_H - 4, LEG_W, 1, NIGHT)

        # slim arms
        for side, sx in (("l", -1), ("r", 1)):
            sh = self.j.get(f"{side}_sh")
            el = self.j.get(f"{side}_el")
            wr = self.j.get(f"{side}_wr")
            if sh is None or el is None or wr is None:
                continue
            d1 = _unit(el - sh, down)
            d2 = _unit(wr - el, down)
            ax = cx + sx * (TORSO_W // 2 + ARM_W // 2 + 1)
            ay = cy + 2
            ex = int(round(ax + d1[0] * UPPER_ARM))
            ey = int(round(ay + d1[1] * UPPER_ARM))
            wx = int(round(ex + d2[0] * FORE_ARM))
            wy = int(round(ey + d2[1] * FORE_ARM))
            self._bar(scr, (ax, ay), (ex, ey), ARM_W, shirt)
            self._bar(scr, (ex, ey), (wx, wy), ARM_W, SKIN)
            scr.rect(wx - 1, wy - 1, 3, 3, NIGHT)
            scr.rect(wx, wy, 2, 2, SKIN_LT)

        # torso — tip forward a bit while nodding down
        tip = 0
        if bobble:
            tip = int(np.clip(nod * 6.0, 0, 10))
        tx = cx - TORSO_W // 2
        scr.rect(tx - 1, cy - 1 + tip, TORSO_W + 2, TORSO_H + 2, NIGHT)
        scr.rect(tx, cy + tip, TORSO_W, TORSO_H, shirt)
        scr.rect(tx, cy + tip, TORSO_W, 2, SHIRT_LT if shirt is SHIRT else shirt)
        scr.rect(cx - 1, cy + 2 + tip, 2, TORSO_H - 2, SHIRT_DK)
        scr.rect(tx, cy + TORSO_H - 2 + tip, TORSO_W, 2, SHIRT_DK)
        scr.rect(cx - 2, cy + tip, 4, 2, SKIN_DK)

        # head tracking — exaggerate, but never detach from the collar
        nose = self.j.get("nose", np.array([0.0, -1.6], np.float32))
        max_x = 6 if bobble else (2 if turny else 3)
        if bobble:
            hdx = int(np.clip(nose[0] * 5.0, -max_x, max_x))
            # big vertical travel so a desk nod reads as a game beat
            hdy = int(np.clip((nose[1] + 1.6) * 16.0 + nod * 14.0, -10, 24))
        elif turny:
            # profile sprite shows the turn; only a tiny lean on the neck
            hdx = int(np.clip(turn_dir * 2.5, -max_x, max_x))
            hdy = int(np.clip((nose[1] + 1.6) * 2.0, -2, 3))
        else:
            hdx = int(np.clip(nose[0] * 3.0, -max_x, max_x))
            hdy = int(np.clip((nose[1] + 1.6) * 2.5, -2, 3))
        hx = cx - hw // 2 + hdx
        hy = cy - hh + 4 + hdy + tip
        # keep chin near collar, but allow a wide nod arc
        hy = min(hy, cy + tip + 6)
        hy = max(hy, cy + tip - hh - 10)

        # neck bridge collar → chin (drawn under the head)
        chin_x = hx + hw // 2
        chin_y = hy + hh
        self._bar(scr, (cx, cy + tip + 1), (chin_x, chin_y), 4, SKIN_DK)
        scr.rect(cx - 2, cy + tip - 1, 4, 4, SKIN_DK)

        if turny and turn_dir < -0.28:
            face_rows = HEAD_L
        elif turny and turn_dir > 0.28:
            face_rows = HEAD_R
        else:
            face_rows = HEAD

        scr.rect(hx - 1, hy - 1, hw + 2, hh + 2, NIGHT)
        self._blit_head(scr, hx, hy, head_scale, face_rows)
        if face_rows is HEAD_L:
            scr.rect(hx + hw - 2 * head_scale, hy + 3 * head_scale, 2 * head_scale, 5 * head_scale, HAIR)
            scr.rect(hx + hw - head_scale, hy + 5 * head_scale, head_scale, 2 * head_scale, SKIN_DK)
        elif face_rows is HEAD_R:
            scr.rect(hx, hy + 3 * head_scale, 2 * head_scale, 5 * head_scale, HAIR)
            scr.rect(hx, hy + 5 * head_scale, head_scale, 2 * head_scale, SKIN_DK)
        if self.face == "happy":
            scr.rect(hx + 2 * head_scale, hy + 8 * head_scale, 8 * head_scale, 2 * head_scale, accent)
        elif self.face == "tired":
            scr.rect(hx + 2 * head_scale, hy + 5 * head_scale, 3 * head_scale, 2 * head_scale, MOUTH)
            scr.rect(hx + 7 * head_scale, hy + 5 * head_scale, 3 * head_scale, 2 * head_scale, MOUTH)

    def _blit_head(self, scr: PixelScreen, hx: int, hy: int, scale: int, rows=None) -> None:
        rows = HEAD if rows is None else rows
        if scale <= 1:
            scr.sprite(hx, hy, rows, PAL)
            return
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch in " .":
                    continue
                c = PAL.get(ch)
                if c is not None:
                    scr.rect(hx + i * scale, hy + j * scale, scale, scale, c)

    def _bar(self, scr: PixelScreen, a, b, width: int, color) -> None:
        """Thin limb: fill first, 1px ink rim — avoids black-stick look."""
        dx, dy = int(b[0] - a[0]), int(b[1] - a[1])
        n = max(abs(dx), abs(dy), 1)
        if n > 120:
            return
        half = max(0, width // 2)
        for i in range(n + 1):
            x = int(a[0]) + dx * i // n
            y = int(a[1]) + dy * i // n
            scr.rect(x - half, y - half, width, width, color)
        # light outline only on the ends so diagonals stay readable
        scr.rect(int(a[0]) - half, int(a[1]) - half, width, width, NIGHT)
        scr.rect(int(b[0]) - half, int(b[1]) - half, width, width, NIGHT)
        scr.rect(int(a[0]) - half + 1, int(a[1]) - half + 1, max(1, width - 2), max(1, width - 2), color)
        scr.rect(int(b[0]) - half + 1, int(b[1]) - half + 1, max(1, width - 2), max(1, width - 2), color)

    # ---------- helpers ----------

    def joint(self, name: str, cx: int, cy: int):
        v = self.j.get(name)
        if v is None:
            return None
        return (int(round(cx + v[0] * SH_HALF)), int(round(cy + v[1] * SH_HALF)))

    def span_units(self) -> float:
        l_wr, r_wr = self.j.get("l_wr"), self.j.get("r_wr")
        if l_wr is None or r_wr is None:
            return 0.0
        return float(abs(l_wr[0] - r_wr[0]))
