#!/usr/bin/env python3
"""Render the same pixel robot as the web stage, driven by mirrored upper-body joints."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from pixel_ui import LIME, PixelScreen
from pose_tracker import PoseResult

# Colors are BGRA on the logical pixel canvas.
INK = (43, 20, 66, 255)
SLEEVE = (121, 173, 131, 255)
MINT = (139, 206, 181, 255)
GLOVE = (160, 225, 252, 255)
LIGHT = (181, 241, 255, 255)
GOLD = (153, 220, 255, 255)
VIOLET = (251, 183, 203, 255)
PAD = np.array([24, 9])
FEET = PAD + (38, 70)
BODY_H = 36  # The game uses cy + BODY_H for the collision ground.


@lru_cache(maxsize=1)
def _sprite_parts():
    path = Path(__file__).resolve().parent / "web" / "art" / "stage-player.png"
    sheet = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
    if sheet is None or sheet.shape != (78, 156, 4):
        raise ValueError(f"Invalid Xiaodian sprite sheet: {path}")
    return sheet[:, :78], sheet[:, 78:]


@lru_cache(maxsize=1)
def _ski_torso():
    path = Path(__file__).resolve().parent / "web" / "art" / "partner-parts.png"
    sheet = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
    if sheet is None or sheet.shape != (48, 384, 4):
        raise ValueError(f"Invalid partner sprite sheet: {path}")
    return sheet[:, 96:144]


def _draw_ski_stance(dst, cx, ground, bank):
    """Project each ski and its boot around the same binding on the snow."""
    sin, cos = math.sin(bank*math.pi/3), math.cos(bank*math.pi/3)
    scale = .75
    feet = [(side, side*(8+2*cos), -side*sin*4) for side in (-1, 1)]
    feet.sort(key=lambda foot: foot[2])

    def project(x, y, across, forward, height):
        return (round(cx+scale*(x+across*cos+forward*sin)),
                round(ground+scale*(y+(forward*cos-across*sin)*.65-height)))

    def face(x, y, corners, tint):
        points = np.array([project(x, y, *v) for v in corners], np.int32)
        cv2.fillPoly(dst, [points], tint)

    for _, x, y in feet:
        face(x, y, [(-3,-18,1),(3,-18,1),(4,22,1),(2,30,4),(-2,30,4),(-4,22,1)], INK)
        face(x, y, [(-2,-16,2),(2,-16,2),(3,21,2),(-3,21,2)], (225,206,132,255))
        face(x, y, [(-3,17,2),(3,17,2),(3,24,3),(-3,24,3)], (71,113,237,255))
        face(x, y, [(-3,24,3),(3,24,3),(1,29,4),(-1,29,4)], GOLD)
    for side, x, y in feet:
        hip = (round(cx+scale*(bank*5+side*5)), round(ground-scale*(19-2*abs(bank))))
        knee = (round(cx+scale*(x+sin*6)), round(ground+scale*(y-10-side*bank*2)))
        ankle = project(x, y, 0, 0, 5)
        for start, end in [(hip,knee),(knee,ankle)]:
            cv2.line(dst, start, end, INK, 5)
            cv2.line(dst, start, end, SLEEVE, 3)
        face(x, y, [(-4,-4,7),(4,-4,7),(5,5,5),(3,10,1),(-3,10,1),(-5,5,4)], INK)
        face(x, y, [(-3,-4,8),(3,-4,8),(4,2,7),(3,8,4),(-3,8,4),(-4,2,7)], (45,105,221,255))
        face(x, y, [(-3,1,7),(3,1,7),(3,3,6),(-3,3,6)], GOLD)


def _blit(dst, src, x, y):
    """Overlay a nearest-neighbor sprite, clipping when a jump reaches the stage edge."""
    h, w = src.shape[:2]
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, dst.shape[1]), min(y + h, dst.shape[0])
    if x1 > x0 and y1 > y0:
        crop = src[y0-y:y1-y, x0-x:x1-x]
        cv2.copyTo(crop, crop[:, :, 3], dst[y0:y1, x0:x1])


def _direction(v, fallback):
    norm = np.linalg.norm(v)
    return v / norm if norm > .001 else fallback


def _pt(v):
    return tuple(np.rint(v).astype(int))


class PixelPuppet:
    def __init__(self):
        self.head, self.body = _sprite_parts()
        self.j = {}
        self.have = False
        self.lost = 9.0

    def update(self, pose: PoseResult, dt: float) -> bool:
        pts = self._read(pose)
        if pts is None:
            self.lost += dt
            return self.have and self.lost < 1.5
        for name in self.j.keys() - pts.keys():
            del self.j[name]
        for name, value in pts.items():
            previous = self.j.get(name)
            weight = .85 if name == "nose" else .55
            self.j[name] = value if not self.have or previous is None or self.lost > .3 else previous + (value-previous)*weight
        self.have = True
        self.lost = 0.0
        return True

    def _read(self, pose):
        if not pose.ok:
            return None

        def point(i):
            if i >= min(len(pose.xy), len(pose.vis)) or not (pose.vis[i] >= .2):
                return None
            value = pose.xy[i].astype(np.float32)
            return value if np.isfinite(value).all() else None

        left, right = point(11), point(12)
        if left is None or right is None:
            return None
        swapped = left[0] > right[0]
        if swapped:
            left, right = right, left
        span = float(right[0] - left[0])
        if span < 8:
            return None
        center = (left + right) * .5
        raw = {"nose": point(0), "l_sh": left, "r_sh": right}
        for name, index in (("el", 13), ("wr", 15)):
            raw["l_" + name] = point(index + int(swapped))
            raw["r_" + name] = point(index + int(not swapped))
        return {name: (v-center)/span for name, v in raw.items() if v is not None}

    def _arm(self, side):
        sign = -1 if side == "l" else 1
        sh, el, wr = (self.j.get(f"{side}_{part}") for part in ("sh", "el", "wr"))
        shoulder = PAD + (38 + 13*sign, 50 + np.clip(sh[1]*26, -4, 4))
        if wr is not None and el is None:
            # Infer the elbow when only the shoulder and wrist are visible.
            target = (wr-sh)*26
            axis = _direction(target, np.array([sign, 0]))
            length = np.clip(np.linalg.norm(target), 2, 25)
            along = (13**2 - 12**2 + length**2)/(2*length)
            normal = np.array([-axis[1], axis[0]])
            bend_side = np.sign(-axis[1]*sign) if abs(axis[1]) > .05 else np.sign(axis[0])
            elbow = shoulder + axis*along + normal*bend_side*np.sqrt(max(0, 13**2 - along**2))
            return shoulder, elbow, shoulder + axis*length
        upper = np.array([sign, .7]) if el is None else el-sh
        lower = np.array([sign*.38, .9]) if el is None or wr is None else wr-el
        elbow = shoulder + 13*_direction(upper, np.array([0, 1]))
        return shoulder, elbow, elbow + 12*_direction(lower, np.array([0, 1]))

    @staticmethod
    def _forearm(layer, elbow, wrist):
        cv2.line(layer, _pt(elbow), _pt(wrist), INK, 6)
        cv2.line(layer, _pt(elbow), _pt(wrist), MINT, 3)
        x, y = _pt(wrist)
        cv2.rectangle(layer, (x-4, y-3), (x+3, y+3), INK, -1)
        cv2.rectangle(layer, (x-3, y-2), (x+2, y+2), GLOVE, -1)
        cv2.rectangle(layer, (x-2, y-3), (x, y-1), LIGHT, -1)

    def draw(self, scr, cx, cy, accent=LIME, shirt=None, style="", nod=0.0, turn_dir=0.0, lean=0.0):
        if not self.have or self.lost >= 1.5:
            return
        layer = np.zeros((91, 127, 4), np.uint8)
        arms = [self._arm(side) for side in ("l", "r")]
        if style != "piano":
            for side, (shoulder, elbow, wrist) in zip(("l","r"), arms):
                reach = wrist-shoulder
                if style == "eagle" and abs(reach[0]) > 10 and side+"_wr" in self.j:
                    sign = np.sign(reach[0])
                    for i in range(3):
                        base = shoulder + reach*(.40 + i*.18)
                        vertices = [base, base + (sign*6, reach[1]*.16), base + (sign*(3-i), 9-i)]
                        cv2.fillConvexPoly(layer, np.rint(vertices).astype(np.int32), MINT if i == 1 else GLOVE)
                cv2.line(layer, _pt(shoulder), _pt(elbow), INK, 7)
                cv2.line(layer, _pt(shoulder), _pt(elbow), SLEEVE, 4)
                self._forearm(layer, elbow, wrist)
        if style == "ski":
            bank = float(np.clip(lean, -1, 1))
            _draw_ski_stance(scr.p, cx, cy + BODY_H, bank)
            _blit(layer, _ski_torso(), PAD[0]+15, PAD[1]+26)
        else:
            _blit(layer, self.body, *PAD)
        nose = self.j.get("nose")
        yaw = float(nose[0]) if nose is not None else 0.
        rest_y = float(np.clip((nose[1]+.68)*9, -3, 5)) if nose is not None else 0.
        turn = float(np.clip(turn_dir/.38,-1,1)) if style == "turn" and nose is not None else 0.
        dip = float(np.clip(nod,0,1)) if style == "nod" and nose is not None else 0.
        sx = (-1 if turn>.40 else 1) * (1-.30*abs(turn))
        sy = 1-.27*dip
        # Anchor at the same neck joint used by the web player.
        head_x = PAD[0]+38+round(np.clip(yaw,-.7,.7)*4 + turn*7)-38*sx
        head_y = PAD[1]+48+round(dip*3 if dip else rest_y)-48*sy
        matrix = np.float32([[sx,0,head_x],[0,sy,head_y]])
        head = cv2.warpAffine(self.head,matrix,(layer.shape[1],layer.shape[0]),flags=cv2.INTER_NEAREST)
        _blit(layer,head,0,0)
        if style != "piano":
            for side, (_,elbow,wrist) in zip(("l","r"),arms):
                wx, wy = wrist-PAD
                if side+"_wr" in self.j and 15 < wx < 62 and wy < 53:
                    self._forearm(layer,elbow,wrist)
        if style == "ski" and lean:
            matrix = cv2.getRotationMatrix2D(tuple(map(float, FEET)), float(np.clip(-lean,-1,1))*11, 1)
            layer = cv2.warpAffine(layer, matrix, (layer.shape[1],layer.shape[0]), flags=cv2.INTER_NEAREST)
        scale = .74 if style == "piano" else 1.
        if style == "piano":
            layer = cv2.resize(layer, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        feet_y = cy + (20 if style == "piano" else BODY_H)
        _blit(scr.p, layer, round(cx-FEET[0]*scale), round(feet_y-FEET[1]*scale))

    def draw_piano_arms(self, scr: PixelScreen, cx, cy, targets, shirt=None):
        if not self.have or self.lost >= 1.5:
            return
        for side,(hx,hy,fingers,pitch) in enumerate(targets):
            wrist_mode = len(fingers) == 1
            if wrist_mode and ("r_wr" if side else "l_wr") not in self.j:
                continue
            sx = cx + (10 if side else -10)
            sy = cy+5
            if wrist_mode:
                hy += round(fingers[0][1]*5)
            elbow = (round(sx+.65*(hx-sx)), round(sy+.4*(hy-sy)))
            cv2.line(scr.p, (sx,sy), elbow, INK, 7)
            cv2.line(scr.p, (sx,sy), elbow, SLEEVE, 4)
            cv2.line(scr.p, elbow, (hx,hy), INK, 6)
            cv2.line(scr.p, elbow, (hx,hy), MINT, 3)
            color = VIOLET if side else MINT
            palm_w = 10 if wrist_mode else pitch*3
            scr.rect(hx-palm_w//2-1,hy-5,palm_w+2,8,INK)
            scr.rect(hx-palm_w//2,hy-4,palm_w,6,GLOVE)
            for i,(x,press) in enumerate(fingers):
                length = 5+round(press*6)
                width = 4 if wrist_mode else max(3,pitch//3)
                if not wrist_mode:
                    cv2.line(scr.p,(hx+round((i-2)*pitch*.6),hy),(x,hy+3),INK,4)
                    cv2.line(scr.p,(hx+round((i-2)*pitch*.6),hy),(x,hy+3),GLOVE,2)
                scr.rect(x-width//2-1,hy+2,width+2,length+1,INK)
                scr.rect(x-width//2,hy+2,width,length,color)
