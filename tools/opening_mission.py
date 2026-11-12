"""The island chart used in the Night Shift opening, at its native 384x216 pixel grid.

The background is an original Runway illustration (task 39b9f11b-fe19-4be3-9f75-1fb540d8f0d6).
Coordinates follow the rooftop, cliff, train, mountains, hall, desert, lighthouses and transmitter.
"""
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SIZE = (384, 216)
OUTPUT = (768, 432)
ART = Path(__file__).with_name("opening_art")
STATIONS = ((159, 145), (123, 53), (174, 89), (234, 24),
            (282, 61), (299, 141), (363, 78), (348, 37))
INK, MINT, GOLD = "#122333", "#a5ffd6", "#ffde85"


@lru_cache(maxsize=None)
def _font(size):
    paths = (os.getenv("OPENING_CJK_FONT"), "C:/Windows/Fonts/msyhbd.ttc",
             "/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    for path in paths:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Set OPENING_CJK_FONT to a Chinese display font.")


@lru_cache(maxsize=2)
def _island(online):
    with Image.open(ART / "night-route.png") as source:
        rgb = np.asarray(source.convert("RGB"), dtype=float)
    # Reserve the ocean for lettering. The powered island changes from blue to warm daylight.
    strength = np.interp(np.arange(SIZE[0]), [0, 88, 158, 240, 383], [.35, .41, .78, 1, 1])
    palette = [1.16, 1.13, 1.05] if online else [.63, .66, .89]
    rgb = rgb * np.array(palette) * strength[None, :, None]
    return Image.fromarray(np.uint8(rgb.clip(0, 255)))


@lru_cache(maxsize=4)
def _marquee(text):
    w, h = 188, 46
    font = _font(32)
    mask = Image.new("L", (w,h))
    lettering = ImageDraw.Draw(mask)
    for index, char in enumerate(text):
        lettering.text((4 + 35*index,2), char, 255, font=font, anchor="lt")
    # Deliberately stepped italic edges and hard bands, as on an arcade title screen.
    src = np.asarray(mask)
    slant = np.zeros_like(src)
    for y in range(h):
        offset = (h-y)//7
        slant[y,offset:] = src[y,:w-offset] if offset else src[y]
    alpha = Image.fromarray(np.where(slant > 100, 255, 0).astype("uint8"))
    face = Image.new("RGB", (w,h))
    d = ImageDraw.Draw(face)
    bands = [(0,"#fff6c8"),(6,"#ffdd8a"),(11,"#ffb669"),(18,"#fff0b1"),
             (20,"#f49a56"),(27,"#de694d"),(35,"#a44d51")]
    for y, color in bands:
        d.rectangle((0,y,w,h),fill=color)
    return face, alpha


def _title(im, text):
    face, mask = _marquee(text)
    for dx,dy,color in [(2,5,"#121723"),(1,3,"#452d43"),(0,2,"#793a43"),(-1,0,"#181b30")]:
        im.paste(color,(9+dx,70+dy,197+dx,116+dy),mask)
    im.paste(face,(9,70),mask)


def _path(d, start, end, powered):
    x,y = start
    dx,dy = end[0]-x, end[1]-y
    steps = max(abs(dx), abs(dy))
    d.line([start,end], fill="#172735", width=3)
    if powered:
        d.line([start,end], fill="#a0e7b3", width=1)
    else:
        for i in range(0,steps,4):
            d.point((round(x+dx*i/steps),round(y+dy*i/steps)),fill="#a6aeba")


def _station(d, pos, on, pulse):
    x,y = pos
    tone = GOLD if on else "#abacbb"
    d.polygon([(x,y-5),(x+5,y),(x,y+5),(x-5,y)],fill=INK)
    d.polygon([(x,y-3),(x+3,y),(x,y+3),(x-3,y)],fill=tone)
    if on:
        d.point((x,y),fill="#fffbe2")
    if pulse:
        r = 7 + pulse
        for sx,sy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            d.line([(x+sx*(r-2),y+sy*r),(x+sx*r,y+sy*r),(x+sx*r,y+sy*(r-2))],fill=MINT)


def mission_frame(elapsed, completed=0, finale=False):
    """Full-screen briefing or payoff. The goal is legible even in the first frame."""
    im = _island(finale).copy()
    if not finale:
        # The scanner searches the dark island while the mission lettering stays still.
        sweep = 111 + round(279*min(1, max(0, elapsed/1.3)))
        overlay = Image.new("RGBA", SIZE)
        sweep_draw = ImageDraw.Draw(overlay)
        for i in range(14):
            sweep_draw.line([(sweep-i+15,0),(sweep-i-33,216)],fill=(130,239,195,55-4*i))
        im = Image.alpha_composite(im.convert("RGBA"),overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    count = 8 if finale else max(0,min(int(completed),8))
    for i in range(1,8):
        _path(d, STATIONS[i-1], STATIONS[i], i<count)
    for i,pos in enumerate(STATIONS):
        _station(d, pos, i<count, 1+int(2*(elapsed*2%1)) if i==(7 if finale else min(count,7)) else 0)
        if finale:
            age = elapsed - .14*i
            if 0 < age < .40:
                x,y = pos
                r = 5 + round(age*20)
                d.ellipse((x-r,y-r,x+r,y+r), outline="#e1ddaf")
    if finale:
        # One last packet runs through the eight restored transmitters.
        step = min(6.999, max(0, elapsed*5.3))
        i = int(step)
        a,b = STATIONS[i],STATIONS[i+1]
        px,py = [round(v + (w-v)*(step-i)) for v,w in zip(a,b)]
        d.rectangle((px-1,py-1,px+1,py+1),fill="#fff7d9")
        for ix in range(13):
            x=143+(ix*11)%44
            y=144+(ix*7)%16
            if math.sin(ix+elapsed*4)>-.25:
                d.rectangle((x,y,x+1,y),fill=GOLD)
    d.line((15,54,100,54),fill="#65b9ab",width=1)
    d.rectangle((15,50,21,52),fill=GOLD)
    d.text((16,35), "工位回血", font=_font(12), fill="#a9dec7",anchor="lt")
    _title(im, "全城通电" if finale else "夜班行动")
    d.text((17,117), f"{count:02d} / 08", font=_font(12),fill=GOLD,anchor="lt")
    message = "八座信号站全部点亮" if finale else "点亮全城八座信号站"
    d.rectangle((12,177,157,202),fill="#172938",outline="#659186")
    d.rectangle((12,177,15,202),fill=MINT)
    d.text((23,184),message,font=_font(14),fill="#f0f4d4",anchor="lt")
    return im.resize(OUTPUT, Image.Resampling.NEAREST)


def route_strip(frame, n):
    """Keep the active stage visible across cuts. Draw only in the lower-right safe area."""
    d = ImageDraw.Draw(frame)
    n = max(0, min(8,int(n)))
    d.rounded_rectangle((522,390,750,422),radius=6,fill=INK,outline="#75939a",width=2)
    d.text((534,407), "信号", font=_font(17),fill="#e0e4df",anchor="lm")
    for i in range(8):
        x = 584+i*15
        d.rectangle((x,401,x+10,412),fill=MINT if i<n else "#465668")
    d.text((740,406), f"{n}/8",font=_font(16),fill=GOLD,anchor="rm")
    return frame
