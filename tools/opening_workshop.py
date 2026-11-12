"""Animated close-ups of the programmer in his workshop before the first mission."""

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

SOURCE=Path(__file__).resolve().parent/"opening_art/arcade-workshop.png"


@lru_cache(maxsize=3)
def plate(index):
    with Image.open(SOURCE) as source:
        image=source.crop((0,index*288,512,(index+1)*288)).convert("RGB")
    return image.resize((768,432),Image.Resampling.NEAREST)


@lru_cache(maxsize=1)
def fields():
    yy,xx=np.indices((432,768),dtype=np.float32)
    def area(x,y,w,h):
        return np.exp(-((xx-x)/w)**2-((yy-y)/h)**2)
    return (xx,yy,area(194,302,46,26),area(316,301,43,23),area(270,161,104,101),
            area(333,171,122,108),area(480,253,78,71),area(266,144,100,105),
            area(272,162,11,12)+area(317,146,8,11))


def warp(index,x,y):
    return Image.fromarray(cv2.remap(np.asarray(plate(index)),x,y,cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REFLECT_101))


def typing(t):
    xx,yy,left_hand,right_hand,head,*_=fields()
    left=max(0,math.sin(t*16))**2
    right=max(0,math.sin(t*20+.8))**2
    frame=warp(0,xx-head*math.sin(t*2.1)*1.8,
               yy-left_hand*left*6-right_hand*right*7-head*(1+math.sin(t*3.1))*1.8)
    d=ImageDraw.Draw(frame)
    # On-screen terminal cursor and two diodes have independent rhythms.
    if int(t*3.4)%2==0:
        d.line((635,230,641,231),fill="#ffdd82",width=2)
    for x,y,on in ((47,379,left),(67,386,right)):
        if on>.60:d.rectangle((x,y,x+3,y+2),fill="#d2ef9c")
    return frame


def sleeping(t,cramp=0):
    xx,yy,_,_,_,cheek,shoulder,_,_=fields()
    breath=math.sin(t*2.9)
    return warp(1,xx+cheek*breath*1.3+shoulder*cramp*3.0,
                yy-cheek*breath*2.5+shoulder*(breath*1.2+cramp*6.4))


def waking(t):
    xx,yy,*_,face,eyes=fields()
    lift=min(1,t/.48)
    settle=math.sin(min(1,t/1.18)*math.pi)
    # Both pupils track the same arc from the lit CRT to the tabletop.
    landing=min(1,max(0,(t-.39)/.64))
    return warp(2,xx-face*(1.2*settle-2.7*(1-lift))+eyes*3*landing,
                yy+face*(4.8*settle-3.4*(1-lift))-eyes*2.7*landing)
