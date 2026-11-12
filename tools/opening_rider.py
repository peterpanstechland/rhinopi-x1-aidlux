"""Planted arcade rider and the six pixel cels shared with the desert station."""

from functools import lru_cache
from math import atan2, degrees, sin
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw

ART = Path(__file__).resolve().parent / "opening_art"
SIZE = (124, 122)
ORIGIN = (55, 109)
NEAREST = Image.Resampling.NEAREST


@lru_cache(maxsize=6)
def motion_cel(name):
    names = ("low", "high", "run", "crouch", "leap", "land")
    index = names.index(name)
    left, top = index % 3 * 100, index // 3 * 108
    with Image.open(ART / "developer-arcade-moves.png") as sheet:
        tile = sheet.crop((left, top, left + 100, top + 108)).convert("RGBA")
    return tile.crop(tile.getbbox())


@lru_cache(maxsize=1)
def sleeves():
    """Follow the painted jacket seam; the hands can rotate independently of the eyes."""
    seams = (
        ([(0,29),(18,29),(22,32),(25,35),(26,41),(23,47),(0,53)],
         [(55,49),(60,49),(65,47),(70,47),(76,50),(91,48),(91,66),
          (65,66),(59,60),(54,56)]),
        ([(0,17),(8,16),(13,20),(15,26),(18,31),(22,36),(27,39),(30,43),
          (27,50),(21,50),(14,46),(10,39),(0,34)],
         [(54,42),(60,39),(65,33),(65,25),(66,17),(72,11),(85,10),(86,27),
          (79,31),(75,38),(70,45),(65,51),(59,51),(55,48)]),
    )
    arms = []
    for name, outlines in zip(("low", "high"), seams):
        source = motion_cel(name)
        torso = source.copy()
        side = []
        for outline in outlines:
            mask = Image.new("L", source.size)
            ImageDraw.Draw(mask).polygon(outline,fill=255)
            cut = source.copy()
            cut.putalpha(ImageChops.multiply(source.getchannel("A"), mask))
            side.append(cut)
            torso.putalpha(ImageChops.subtract(torso.getchannel("A"), mask))
        arms.append(side)
        if name == "low":
            body = torso
    return body, arms


@lru_cache(maxsize=40)
def planted_pose(mode, step):
    body, arms = sleeves()
    pose = Image.new("RGBA", SIZE)
    rise = step / 12 if mode == "flight" else 0
    bank = step / 8 if mode == "ski" else 0
    # In the downstroke hands are almost parallel to the deck. On the next cel
    # the palm opens and the elbow leads up. The two soles never change anchors.
    source = int(rise > .48)
    sockets = (((23,39),(60,52)), ((23,43),(58,45)))
    grips = (((4,43),(82,55)), ((3,26),(77,21)))
    low = sockets[0]
    # Short folds below the pivot remain behind the sleeve on every exposure.
    d = ImageDraw.Draw(pose)
    d.polygon([(65,63),(77,64),(82,67),(77,73),(70,76),(64,76)],
              fill="#ad4024",outline="#692236")
    d.polygon([(65,64),(77,65),(78,68),(70,73),(65,74)],fill="#e56622")
    for (x,y),color in zip(low,("#a13b25","#a33e26")):
        d.ellipse((x+14,y+14,x+20,y+21),fill=color)
    for side in range(2):
        origin = sockets[source][side]
        hand = grips[source][side]
        start = atan2(grips[0][side][1]-low[side][1],grips[0][side][0]-low[side][0])
        finish = atan2(grips[1][side][1]-sockets[1][side][1],
                       grips[1][side][0]-sockets[1][side][0])
        arc = (degrees(finish-start)+180)%360-180
        target = degrees(start) + arc * rise + bank * (20 if side else -15)
        native = degrees(atan2(hand[1]-origin[1],hand[0]-origin[0]))
        socket = (low[side][0]+17,low[side][1]+17)
        on_stage = Image.new("RGBA",SIZE)
        on_stage.alpha_composite(arms[source][side],(socket[0]-origin[0],socket[1]-origin[1]))
        pose.alpha_composite(on_stage.rotate(native-target,NEAREST,center=socket))
    pose.alpha_composite(body,(17,17))
    # Transfer weight from the soles to the hips, then to the shoulders.
    # The head translates as a unit so the frames of his glasses stay crisp.
    yy,xx = np.indices((SIZE[1],SIZE[0]),dtype=np.float32)
    up = np.clip((ORIGIN[1]-yy-8)/60,0,1)
    up = up*up*(3-2*up)
    dx = np.rint(up * (-5*rise+13*bank))
    dy = np.rint(up * (-7*rise+3*abs(bank)))
    return cv2.remap(np.array(pose),xx-dx,yy-dy,cv2.INTER_NEAREST,
                     borderMode=cv2.BORDER_CONSTANT)


def rider_image(phase, mode, steer, slope):
    step = round((1+sin(phase-.1))*6) if mode == "flight" else round(steer*8)
    cel = planted_pose(mode,step)
    yy,xx = np.indices((SIZE[1],SIZE[0]),dtype=np.float32)
    heel = np.clip((yy-72)/24,0,1)
    # Pitch the ankles to the deck. The face keeps looking at the next station.
    pixels = cv2.remap(cel,xx,yy-np.rint((xx-ORIGIN[0])*slope*heel),cv2.INTER_NEAREST,
                       borderMode=cv2.BORDER_CONSTANT)
    return Image.fromarray(pixels)


def draw_rider(frame, x, deck_y, phase, mode, *, steer=0, slope=0, scale=1):
    actor = rider_image(phase, mode, steer, slope)
    rect = actor.getbbox()
    size = round((rect[2]-rect[0])*2*scale),round((rect[3]-rect[1])*2*scale)
    tile = actor.crop(rect).resize(size,NEAREST)
    at = round(2*x+(rect[0]-ORIGIN[0])*2*scale), round(2*deck_y+(rect[1]-ORIGIN[1])*2*scale)
    frame.paste(tile,at,tile)


def draw_deck(draw, x, y, slope, mode):
    """Paint a long shared board. Surface, boots, and robot use the same pitched line."""
    def points(contour):
        return [(round(x + dx), round(y + dx*slope + dy)) for dx, dy in contour]

    air = mode == "flight"
    draw.polygon(points([(-56,-4),(-49,-1),(-36,0),(31,0),(45,-3),(56,-9),
                         (56,-5),(45,2),(31,6),(-31,6),(-48,3)]), fill="#263344")
    draw.polygon(points([(-51,-3),(-36,-1),(31,-1),(46,-4),(54,-8),
                         (46,-2),(32,2),(-34,2)]), fill="#f0bd79" if air else "#e5c08f")
    draw.line(points([(-31,3),(30,3),(40,1)]), fill="#b26750" if air else "#6c9c9e")
    # The couplers sit below the soles, making both grounded contacts readable.
    for offset in ((-37,-22), (0,15), (22,35)):
        draw.line(points([(offset[0],0),(offset[1],0)]),fill="#b8d0c2")
    if air:
        draw.polygon(points([(-38,4),(-46,11),(-35,10),(-20,6)]), fill="#537785")
        draw.line(points([(-41,9),(-32,7)]),fill="#84afa6")
    else:
        draw.line(points([(-48,8),(-35,10),(30,9),(49,3)]), fill="#536e7a",width=2)
