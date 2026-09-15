#!/usr/bin/env python3
"""Pixel UI core: 4x panel layer, 2x text layer, 5x7 arcade font, RPG windows."""

from __future__ import annotations

import cv2
import numpy as np

FONT = "/usr/share/fonts/aidlux/NotoSansCJKsc-Regular.otf"

# sweetie-16, BGR
NIGHT = (44, 28, 26)
PLUM = (93, 39, 93)
RED = (83, 62, 177)
ORANGE = (87, 125, 239)
YELLOW = (117, 205, 255)
LIME = (112, 240, 167)
GREEN = (100, 183, 56)
TEAL = (121, 113, 37)
NAVY = (111, 54, 41)
BLUE = (201, 93, 59)
AZURE = (246, 166, 65)
CYAN = (247, 239, 115)
WHITE = (244, 244, 244)
SILVER = (194, 176, 148)
GRAY = (134, 108, 86)
SLATE = (87, 60, 51)

# legacy aliases used elsewhere
INK = NIGHT
MINT = LIME
CREAM = WHITE
GOLD = YELLOW
ROSE = RED
SKY = ORANGE
MUTED = SILVER

SCALE = 4
TEXT_MUL = 2

GLYPHS = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "10001", "11001", "10101", "10011", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10011", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    ":": ("00000", "00100", "00000", "00000", "00000", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00000", "00100"),
    ",": ("00000", "00000", "00000", "00000", "00000", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "%": ("10001", "10010", "00100", "00100", "00100", "01001", "10001"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "*": ("00000", "01010", "00100", "11111", "00100", "01010", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
}


_GLYPH_CACHE: dict[tuple, np.ndarray] = {}
_TEXT_CACHE: dict[tuple, np.ndarray] = {}
_FONT_CACHE: dict[int, object] = {}


def _glyph_mask(ch: str, px: int):
    """Boolean mask for one 5x7 glyph, cached per (char, pixel size)."""
    key = (ch, px)
    m = _GLYPH_CACHE.get(key)
    if m is not None:
        return m
    rows = GLYPHS.get(ch.upper())
    if rows is None:
        _GLYPH_CACHE[key] = None
        return None
    base = np.array([[c == "1" for c in row] for row in rows], dtype=bool)
    m = np.repeat(np.repeat(base, px, axis=0), px, axis=1)
    _GLYPH_CACHE[key] = m
    return m


def _stamp(layer: np.ndarray, mask: np.ndarray, x: int, y: int, bgr, th: int, tw: int) -> None:
    gh, gw = mask.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(tw, x + gw), min(th, y + gh)
    if x1 <= x0 or y1 <= y0:
        return
    sub = mask[y0 - y : y1 - y, x0 - x : x1 - x]
    region = layer[y0:y1, x0:x1]
    region[sub] = (bgr[0], bgr[1], bgr[2], 255)


def _stamp_rgba(layer: np.ndarray, spr: np.ndarray, x: int, y: int, th: int, tw: int) -> None:
    gh, gw = spr.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(tw, x + gw), min(th, y + gh)
    if x1 <= x0 or y1 <= y0:
        return
    sub = spr[y0 - y : y1 - y, x0 - x : x1 - x]
    hit = sub[:, :, 3] > 0
    region = layer[y0:y1, x0:x1]
    region[hit] = sub[hit]


def _font(size: int):
    f = _FONT_CACHE.get(size)
    if f is not None:
        return f
    from PIL import ImageFont

    try:
        f = ImageFont.truetype(FONT, size)
    except OSError:
        f = ImageFont.load_default()
    _FONT_CACHE[size] = f
    return f


def _text_sprite(s: str, size: int, bgr, shadow: bool):
    """Render a CJK string once, then reuse the pixels every frame."""
    key = (s, size, bgr, shadow)
    spr = _TEXT_CACHE.get(key)
    if spr is not None or key in _TEXT_CACHE:
        return spr
    try:
        from PIL import Image, ImageDraw

        font = _font(size)
        box = font.getbbox(s)
        w = int(box[2]) + size // 2 + 3
        h = int(box[3]) + size // 2 + 3
        img = Image.new("RGBA", (max(w, 2), max(h, 2)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        if shadow:
            draw.text((1, 1), s, font=font, fill=(26, 28, 44, 255))
        draw.text((0, 0), s, font=font, fill=(bgr[2], bgr[1], bgr[0], 255))
        arr = np.array(img)
    except Exception:
        _TEXT_CACHE[key] = None
        return None
    hard = arr[:, :, 3] >= 110
    out = np.zeros(arr.shape, np.uint8)
    out[hard, 0] = arr[hard][:, 2]
    out[hard, 1] = arr[hard][:, 1]
    out[hard, 2] = arr[hard][:, 0]
    out[hard, 3] = 255
    if len(_TEXT_CACHE) > 600:
        _TEXT_CACHE.clear()
    _TEXT_CACHE[key] = out
    return out


class PixelScreen:
    """Panel art on a 320x180 grid; text on a 640x360 grid. One composite."""

    def __init__(self, h: int, w: int, scale: int = SCALE) -> None:
        self.s = scale
        self.lh = max(1, h // scale)
        self.lw = max(1, w // scale)
        self.p = np.zeros((self.lh, self.lw, 4), np.uint8)
        self.dim = 0.0
        self._cjk: list[tuple] = []
        self._px: list[tuple] = []

    # ---------- panel layer ----------

    def pset(self, x: int, y: int, bgr, a: int = 255) -> None:
        if 0 <= x < self.lw and 0 <= y < self.lh:
            self.p[y, x] = (bgr[0], bgr[1], bgr[2], a)

    def rect(self, x: int, y: int, w: int, h: int, bgr, a: int = 255) -> None:
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.lw, int(x + w)), min(self.lh, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        self.p[y0:y1, x0:x1] = (bgr[0], bgr[1], bgr[2], a)

    def hline(self, x: int, y: int, w: int, bgr, a: int = 255) -> None:
        self.rect(x, y, w, 1, bgr, a)

    def vline(self, x: int, y: int, h: int, bgr, a: int = 255) -> None:
        self.rect(x, y, 1, h, bgr, a)

    def frame(self, x: int, y: int, w: int, h: int, bgr, t: int = 1) -> None:
        self.rect(x, y, w, t, bgr)
        self.rect(x, y + h - t, w, t, bgr)
        self.rect(x, y, t, h, bgr)
        self.rect(x + w - t, y, t, h, bgr)

    def window(self, x: int, y: int, w: int, h: int, accent=YELLOW, fill=NAVY, a: int = 232) -> None:
        """RPG dialog: beveled ink rim, accent inner line, two-tone fill, studs."""
        self.rect(x + 1, y, w - 2, h, NIGHT, 255)
        self.rect(x, y + 1, w, h - 2, NIGHT, 255)
        self.rect(x + 1, y + 1, w - 2, h - 2, accent, 255)
        self.rect(x + 2, y + 2, w - 4, h - 4, fill, a)
        self.rect(x + 2, y + 2, w - 4, 1, SLATE, min(255, a + 20))
        self.rect(x + 2, y + h - 3, w - 4, 1, NIGHT, min(255, a + 20))
        for cx in (x + 2, x + w - 4):
            for cy in (y + 2, y + h - 4):
                self.rect(cx, cy, 2, 2, accent, 255)

    def bar(self, x: int, y: int, w: int, h: int, frac: float, fill_bgr=LIME, back=SLATE) -> None:
        self.rect(x, y, w, h, NIGHT)
        self.rect(x + 1, y + 1, w - 2, h - 2, back)
        n = int((w - 2) * max(0.0, min(1.0, frac)))
        if n > 0:
            self.rect(x + 1, y + 1, n, h - 2, fill_bgr)
            self.rect(x + 1, y + 1, n, 1, WHITE, 170)

    def seg_bar(self, x: int, y: int, w: int, h: int, frac: float, fill_bgr=LIME, seg: int = 4) -> None:
        """Chunky segmented gauge — reads better on video than a smooth bar."""
        self.rect(x, y, w, h, NIGHT)
        inner = w - 2
        cells = max(1, inner // seg)
        lit = int(round(cells * max(0.0, min(1.0, frac))))
        for i in range(cells):
            cx = x + 1 + i * seg
            col = fill_bgr if i < lit else SLATE
            self.rect(cx, y + 1, seg - 1, h - 2, col)

    def pips(self, x: int, y: int, total: int, done: int, cur: int = -1) -> None:
        for i in range(total):
            cx = x + i * 6
            if i < done:
                self.rect(cx, y, 4, 4, LIME)
            elif i == cur:
                self.rect(cx, y, 4, 4, YELLOW)
                self.rect(cx + 1, y + 1, 2, 2, WHITE)
            else:
                self.rect(cx, y, 4, 4, SLATE)
            self.frame(cx - 1, y - 1, 6, 6, NIGHT)

    def sprite(self, x: int, y: int, rows, colors: dict, flip: bool = False) -> None:
        for j, row in enumerate(rows):
            line = row[::-1] if flip else row
            for i, ch in enumerate(line):
                if ch in " .":
                    continue
                c = colors.get(ch)
                if c is not None:
                    self.pset(x + i, y + j, c, 255)

    def tri_up(self, x: int, y: int, w: int, h: int, bgr) -> None:
        """Apex at the top, base at the bottom."""
        for j in range(h):
            half = int((j + 1) * (w / 2) / h)
            self.rect(x + w // 2 - half, y + j, max(1, half * 2), 1, bgr)

    def disc(self, cx: int, cy: int, r: int, bgr) -> None:
        for j in range(-r, r + 1):
            span = int((r * r - j * j) ** 0.5)
            self.rect(cx - span, cy + j, span * 2 + 1, 1, bgr)

    # ---------- text ----------

    def text(self, x: int, y: int, s: str, bgr=WHITE, size: int = 13, shadow: bool = True) -> None:
        """CJK/any text. x,y in panel coords; size in text-layer px (~2x on screen)."""
        if s:
            self._cjk.append((s, (int(x) * TEXT_MUL, int(y) * TEXT_MUL), int(size), bgr, shadow))

    def pf(self, x: int, y: int, s: str, bgr=WHITE, px: int = 1, shadow: bool = True) -> None:
        """Arcade 5x7 bitmap text. x,y in panel coords."""
        if s:
            self._px.append((s.upper(), int(x) * TEXT_MUL, int(y) * TEXT_MUL, bgr, max(1, int(px)), shadow))

    def pf_width(self, s: str, px: int = 1) -> int:
        """Width in panel coords."""
        return int(len(s) * 6 * px / TEXT_MUL)

    def _blit_pf(self, layer: np.ndarray) -> None:
        th, tw = layer.shape[:2]
        for s, x0, y0, bgr, px, shadow in self._px:
            cx = x0
            for ch in s:
                mask = _glyph_mask(ch, px)
                if mask is not None:
                    if shadow:
                        _stamp(layer, mask, cx + px, y0 + px, NIGHT, th, tw)
                    _stamp(layer, mask, cx, y0, bgr, th, tw)
                cx += 6 * px

    def _blit_cjk(self, layer: np.ndarray) -> None:
        th, tw = layer.shape[:2]
        for s, org, size, bgr, shadow in self._cjk:
            spr = _text_sprite(s, size, bgr, shadow)
            if spr is None:
                continue
            _stamp_rgba(layer, spr, org[0], org[1], th, tw)

    # ---------- output ----------

    def blit(self, img: np.ndarray) -> None:
        if self.dim > 0.0:
            k = 1.0 - min(0.9, self.dim)
            cv2.addWeighted(img, k, np.zeros_like(img), 0.0, 8.0, dst=img)
        tw, th = self.lw * TEXT_MUL, self.lh * TEXT_MUL
        layer = cv2.resize(self.p, (tw, th), interpolation=cv2.INTER_NEAREST)
        self._blit_pf(layer)
        self._blit_cjk(layer)
        h, w = img.shape[:2]
        # binary mask keeps the composite a fast copy instead of a 720p blend
        alpha = layer[:, :, 3]
        alpha[alpha < 110] = 0
        alpha[alpha >= 110] = 255
        rows = np.flatnonzero(alpha.any(axis=1))
        if rows.size == 0:
            return
        # composite only the bands that actually hold chrome; the middle of the
        # screen is usually empty and a full 720p blend costs real frame time
        cut = np.flatnonzero(np.diff(rows) > 1)
        starts = np.concatenate(([0], cut + 1))
        ends = np.concatenate((cut, [rows.size - 1]))
        for si, ei in zip(starts, ends):
            y0, y1 = int(rows[si]), int(rows[ei]) + 1
            band = layer[y0:y1]
            cols = np.flatnonzero(band[:, :, 3].any(axis=0))
            if cols.size == 0:
                continue
            x0, x1 = int(cols[0]), int(cols[-1]) + 1
            up = cv2.resize(
                band[:, x0:x1],
                ((x1 - x0) * TEXT_MUL, (y1 - y0) * TEXT_MUL),
                interpolation=cv2.INTER_NEAREST,
            )
            dy0, dx0 = y0 * TEXT_MUL, x0 * TEXT_MUL
            dy1, dx1 = min(h, dy0 + up.shape[0]), min(w, dx0 + up.shape[1])
            if dy1 <= dy0 or dx1 <= dx0:
                continue
            up = up[: dy1 - dy0, : dx1 - dx0]
            a = up[:, :, 3]
            rgb = up[:, :, :3]
            dst = img[dy0:dy1, dx0:dx1]
            solid = a == 255
            dst[solid] = rgb[solid]
            soft = (a > 0) & ~solid
            if soft.any():
                af = a[soft][:, None].astype(np.float32) / 255.0
                dst[soft] = (
                    rgb[soft].astype(np.float32) * af + dst[soft].astype(np.float32) * (1.0 - af)
                ).astype(np.uint8)


def scanlines(img: np.ndarray, step: int = 4) -> None:
    """Arcade CRT feel; integer-only so it stays cheap at 720p."""
    rows = img[::step]
    np.subtract(rows, rows >> 2, out=rows)


def vignette_bars(scr: PixelScreen, top: int = 0, bottom: int = 0) -> None:
    if top:
        scr.rect(0, 0, scr.lw, top, NIGHT, 190)
    if bottom:
        scr.rect(0, scr.lh - bottom, scr.lw, bottom, NIGHT, 190)


# ---------- shared sprite art ----------

DINO = (
    "......####..",
    "....##++++#.",
    "...#++++++#.",
    "...#++o+++#.",
    "..##+++++#..",
    ".#++++++++#.",
    "#+++##+++#..",
    "#++#..#++#..",
    ".##....##...",
    ".#.#...#.#..",
)

CACTUS = ("..#.#.", ".##.##", "#.#.#.", "..#...", "..#...", "..#...", ".###..")

EAGLE_UP = ("#.......#", ".#+++++#.", "..#+++#..", "...#+#...", "....#....")
EAGLE_MID = (".........", "#+++++++#", ".#+++++#.", "..#+#+#..", "....#....")
EAGLE_DN = (".........", "..#+++#..", "#+++++++#", ".#+++++#.", "....#....")

CLOUD = ("..####..", ".######.", "########", ".######.")

HAND = ("..#.#.#..", ".########", ".########", "..######.", "...####..", "....##...")

SKIER = ("..##..", ".####.", "..##..", ".####.", "#.##.#", "..##..")

GATE = ("####", "#..#", ".#..", ".#..", ".#..")

NOTE = ("..##", ".###", "####", "##..")

MUG = ("#####..", "#...#.#", "#...#.#", "#...#.#", "#####..")

BIRD = ("..#..", ".###.", "#####", ".#.#.")

PLANT = ("..#..", ".#.#.", "#.#.#", "..#..", ".###.")

SPINE_OK = ("..##..", "..##..", "..##..", "..##..", "..##..", ".####.")
SPINE_BAD = ("....##", "...##.", "..##..", "..##..", ".##...", "####..")

CHAIR = ("#####.", "#....#", "#####.", "..#...", "..#...", ".#.#..")

STAR = (".#.", "###", ".#.")

DINO_PAL = {"#": NIGHT, "+": LIME, "o": WHITE}
DINO_HIT_PAL = {"#": NIGHT, "+": RED, "o": WHITE}
CACTUS_PAL = {"#": GREEN}
EAGLE_PAL = {"#": NIGHT, "+": ORANGE}
CLOUD_PAL = {"#": WHITE}
HAND_PAL = {"#": YELLOW}
SKIER_PAL = {"#": CYAN}
GATE_PAL = {"#": RED}
NOTE_PAL = {"#": CYAN}
MUG_PAL = {"#": SILVER}
BIRD_PAL = {"#": AZURE}
PLANT_PAL = {"#": GREEN}
SPINE_PAL_OK = {"#": LIME}
SPINE_PAL_BAD = {"#": RED}
CHAIR_PAL = {"#": SILVER}
STAR_PAL = {"#": YELLOW}


# ---------- webcam-space pixel drawing ----------


def snap(pt, scale: int = SCALE):
    return (int(pt[0] // scale * scale + scale // 2), int(pt[1] // scale * scale + scale // 2))


def pixel_line(img: np.ndarray, a, b, bgr, scale: int = SCALE, thick: int = 2) -> None:
    ax, ay = snap(a, scale)
    bx, by = snap(b, scale)
    ax, ay, bx, by = ax // scale, ay // scale, bx // scale, by // scale
    n = max(abs(bx - ax), abs(by - ay), 1)
    if n > 400:
        return
    h, w = img.shape[:2]
    step = scale * max(1, thick)
    for i in range(n + 1):
        x0 = (ax + (bx - ax) * i // n) * scale
        y0 = (ay + (by - ay) * i // n) * scale
        if x0 < 0 or y0 < 0:
            continue
        img[y0 : min(h, y0 + step), x0 : min(w, x0 + step)] = bgr


_DIAMOND: dict[tuple, np.ndarray] = {}


def _diamond(cells: int, band: int | None, scale: int) -> np.ndarray:
    """Pixel-grid diamond (filled or ring), upscaled and cached."""
    key = (cells, band, scale)
    m = _DIAMOND.get(key)
    if m is not None:
        return m
    n = cells * 2 + 1
    yy, xx = np.mgrid[0:n, 0:n]
    d = np.abs(xx - cells) + np.abs(yy - cells)
    base = d <= cells if band is None else (d <= cells) & (d > cells - band)
    m = np.repeat(np.repeat(base, scale, axis=0), scale, axis=1)
    if len(_DIAMOND) > 160:
        _DIAMOND.clear()
    _DIAMOND[key] = m
    return m


def _paint_mask(img: np.ndarray, mask: np.ndarray, cx: int, cy: int, bgr) -> None:
    gh, gw = mask.shape
    h, w = img.shape[:2]
    x, y = cx - gw // 2, cy - gh // 2
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(w, x + gw), min(h, y + gh)
    if x1 <= x0 or y1 <= y0:
        return
    sub = mask[y0 - y : y1 - y, x0 - x : x1 - x]
    img[y0:y1, x0:x1][sub] = bgr


def pixel_head(img: np.ndarray, c, r: int, bgr, scale: int = SCALE) -> None:
    cx, cy = snap(c, scale)
    cells = max(1, int(r) // scale)
    _paint_mask(img, _diamond(cells, None, scale), cx, cy, bgr)


def pixel_ring(img: np.ndarray, c, r: int, bgr, scale: int = SCALE, thick: int = 2) -> None:
    """Diamond outline on the pixel grid — marks the head without hiding the face."""
    cx, cy = snap(c, scale)
    cells = max(3, int(r) // scale)
    _paint_mask(img, _diamond(cells, max(1, thick), scale), cx, cy, bgr)
