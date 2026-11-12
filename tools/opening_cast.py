"""Pixel acting for the developer. Coordinates use a 144 px cel with a fixed boot line."""

from functools import lru_cache
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ART = Path(__file__).resolve().parent / "opening_art"
PIXEL = Image.Resampling.NEAREST
CEL = 144
FOOT = (72, 134)
STANCES = ("ready", "raise", "hold", "wave", "exhale", "rest")
FACES = ("left", "center", "right", "down", "up", "relaxed")


@lru_cache(maxsize=2)
def atlas(name):
    with Image.open(ART / name) as source:
        return source.convert("RGBA")


def cel(image, index, size):
    row, col = divmod(index, 3)
    return image.crop((col*size, row*size, (col+1)*size, (row+1)*size))


@lru_cache(maxsize=6)
def pose(name):
    return cel(atlas("arcade-developer.png"), STANCES.index(name), CEL)


@lru_cache(maxsize=6)
def face(name):
    pic = cel(atlas("arcade-faces.png"), FACES.index(name), 72)
    return pic.crop(pic.getbbox())


def split(image, polygon):
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    cut = Image.new("RGBA", image.size)
    cut.paste(image, mask=mask)
    rest = image.copy()
    rest.paste((0, 0, 0, 0), mask=mask)
    return rest, cut


@lru_cache(maxsize=1)
def spread():
    body, left = split(pose("hold"), [(0,52),(51,60),(51,68),(52,76),(0,84)])
    body, right = split(body, [(143,52),(87,60),(87,69),(86,76),(143,85)])
    return body, left, right


def on_stage(frame, image, x, foot, scale):
    size = round(CEL*scale*2)
    enlarged = image.resize((size,size), PIXEL)
    frame.paste(enlarged,(round(2*(x-FOOT[0]*scale)),round(2*(foot-FOOT[1]*scale))),enlarged)


def stretch(frame, x, foot, amount, scale=1.18):
    body, left, right = spread()
    actor = Image.new("RGBA",body.size)
    wrists = []
    for arm, shoulder, angle, wrist in (
        (left,(51,68),68*(1-amount),(29,69)),
        (right,(87,68),-70*(1-amount),(109,69)),
    ):
        actor.alpha_composite(arm.rotate(angle,PIXEL,center=shoulder))
        rad=math.radians(angle)
        dx,dy=wrist[0]-shoulder[0],wrist[1]-shoulder[1]
        px=shoulder[0]+dx*math.cos(rad)+dy*math.sin(rad)
        py=shoulder[1]-dx*math.sin(rad)+dy*math.cos(rad)
        wrists.append((2*(x+(px-FOOT[0])*scale),2*(foot+(py-FOOT[1])*scale)))
    actor.alpha_composite(body)
    on_stage(frame,actor,x,foot,scale)
    return wrists


@lru_cache(maxsize=1)
def waving_arm():
    return split(pose("wave"),[(88,61),(94,58),(96,52),(94,43),(93,36),(116,32),
                              (122,53),(108,69),(98,74),(89,73)])


def wave(frame, x, foot, amount, phase):
    if amount<.04:
        on_stage(frame,pose("ready"),x,foot,1.06)
        return
    body,arm = waving_arm()
    # Raise the whole arm, then swing the wrist from the elbow far enough to
    # register the same side-to-side gesture the camera measures in this game.
    wrist_angle = 22*math.sin(phase)*amount
    posed = arm.rotate(wrist_angle,PIXEL,center=(98,64))
    image = posed.rotate(-102*(1-amount),PIXEL,center=(90,67))
    image.alpha_composite(body)
    on_stage(frame,image,x,foot,1.06)


@lru_cache(maxsize=1)
def neck_down():
    image=pose("ready").copy()
    d=ImageDraw.Draw(image)
    d.polygon([(0,0),(143,0),(143,64),(85,64),(80,66),(65,64),(58,61),(0,61)],fill=(0,0,0,0))
    d.polygon([(62,62),(69,58),(81,58),(87,63),(79,68),(72,67)],fill="#613144")
    d.polygon([(67,61),(72,58),(79,59),(84,63),(77,65),(71,64)],fill="#e68c5a")
    d.polygon([(72,66),(78,67),(84,64),(80,71),(76,69)],fill="#256367")
    return image


def turn_or_nod(frame, x, foot, move, value, scale):
    body=neck_down().copy()
    if move=="look":
        name="left" if value<-.43 else "right" if value>.43 else "center"
        dx=-round(2*value)
        dy=0
    else:
        name="down" if value>.32 else "center"
        dx=0
        dy=round(8*value)
    head=face(name)
    height=52 if move=="look" else round(53-5*value)
    width=round(height*head.width/head.height)
    head=head.resize((width,height),PIXEL)
    body.alpha_composite(head,(76-width//2+dx,68-height+dy))
    on_stage(frame,body,x,foot,scale)


@lru_cache(maxsize=1)
def grid():
    return np.indices((CEL,CEL),dtype=np.float32)


def resting(frame, elapsed):
    # The closed-eye exhale anticipates the weight shift into the cross-foot stance.
    rest=elapsed>.80
    drawn=pose("rest" if rest else "exhale")
    yy,xx=grid()
    upper=np.clip((122-yy)/58,0,1)
    breath=math.sin(min(1,elapsed/.80)*math.pi)*2.0 if not rest else math.sin((elapsed-.8)*2.8)*.42
    shoulder=np.exp(-((yy-72)/27)**2)
    image=cv2.remap(np.asarray(drawn),xx-.45*breath*upper,yy+breath*shoulder,
                    cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
    d=ImageDraw.Draw(frame)
    d.ellipse((125,388,227,400),fill="#302a40")
    on_stage(frame,Image.fromarray(image),89,197,1.22)


def portrait():
    upper=pose("ready").crop((36,12,99,99))
    return upper.resize((71,98),PIXEL)


def stand_up(frame, progress):
    # Lean over planted boots, then extend the knees. A continuous deformation
    # across the belt keeps both wrists attached even where they overlap the hips.
    seated=1-progress
    yy,xx=grid()
    ratio=1-.46*seated
    bent_waist=FOOT[1]-(FOOT[1]-85)*ratio
    sy=np.where(yy<bent_waist,yy-bent_waist+85,(yy-bent_waist)/ratio+85)
    weight=np.clip((FOOT[1]-sy)/56,0,1)
    sx=xx-(4*seated+2*math.sin(progress*math.pi))*weight
    pic=cv2.remap(np.asarray(pose("ready")),sx,sy,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
    on_stage(frame,Image.fromarray(pic),88,197,1.20)


@lru_cache(maxsize=2)
def pointing(down):
    hands=atlas("arcade-hands.png")
    row=1 if down else 0
    part=hands.crop((0,row*54,184,(row+1)*54))
    part=part.crop(part.getbbox())
    part=part.resize((part.width*3,part.height*3),PIXEL)
    alpha=np.asarray(part.getchannel("A"))
    ys,xs=np.where(alpha>127)
    if down:
        tip=int(ys.max())
        return part,int(np.median(xs[ys>=tip-2])),tip
    tip=int(xs.max())
    return part,tip,int(np.median(ys[xs>tip-5]))
