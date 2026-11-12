"""Render the 54.5-second Night Shift prologue with the game's pixel cast and Runway music.

Run: python tools/render_opening.py --ffmpeg <ffmpeg executable>
Requires Pillow, NumPy, OpenCV and ffmpeg. All artwork and audio live in the repository.
Set OPENING_CJK_FONT to provide a Chinese font on systems without one.
"""

import argparse
import math
from functools import lru_cache
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import opening_cast as cast
import opening_workshop as workshop
from opening_partner import robot_world

ROOT = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web"
FPS = 24
OUTPUT = (768, 432)
INK = "#22263b"
PLATES = Image.open(ROOT / "art/stage-plates.png").convert("RGB")
NEAREST = Image.Resampling.NEAREST


def box(d, x, y, width, height, color):
    x, y, w, h = (round(v) for v in (x, y, width, height))
    if w > 0 and h > 0:
        d.rectangle((x, y, x+w-1, y+h-1), fill=color)


def path(d, coords, color, width=1):
    d.line([(round(x), round(y)) for x, y in coords], fill=color, width=width)


def poly(d, coords, color):
    d.polygon([(round(x), round(y)) for x, y in coords], fill=color)


def smooth(t):
    t = min(1, max(0, t))
    return t*t*(3-2*t)


def mix(a, b, f):
    return a + (b-a)*f


ART = Path(__file__).resolve().parent / "opening_art"


def ease(start, stop, t):
    return smooth((t-start)/(stop-start))


def bump(start, peak, end, t):
    return ease(start,peak,t)*(1-ease(peak,end,t))


def camera(frame,cx=192,cy=108,width=384):
    """Cinematography coordinates are in a 384x216 guide; source and output are twice as dense."""
    h=width*9/16
    left=max(0,min(384-width,cx-width/2));top=max(0,min(216-h,cy-h/2))
    if width==384:return frame.copy()
    return frame.transform(OUTPUT,Image.Transform.EXTENT,
                           (left*2,top*2,(left+width)*2,(top+h)*2),Image.Resampling.BICUBIC)


def track(seq,t):
    for (a,v),(b,w) in zip(seq,seq[1:]):
        if t<=b:return mix(v,w,max(0,(t-a)/(b-a)))
    return seq[-1][1]


def rising(t):
    frame=studio().copy()
    crt_shell(frame,game_screen(0))
    rise=ease(.14,1.46,t)
    cast.stand_up(frame,rise)
    lead=bump(.25,.63,1.03,t)
    robot_world(frame,"reach" if t<.78 else "wave",t*1.5,136+3*rise,197-10*lead,.71,
                angle=4*lead)
    return camera(frame,mix(121,148,rise),mix(123,106,rise),mix(249,308,rise))


def pain_marks(im, points, intensity):
    if intensity<.03:return im
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    for x,y,side in points:
        for radius,alpha in ((13,38),(9,51)):
            d.ellipse((x-radius,y-radius*.8,x+radius,y+radius*.8),fill=(208,60,65,round(alpha*intensity)))
        for j in range(2):
            xx=x+side*(3+j*5)
            line=[(xx,y+4-j),(xx+side*4,y-2-j),(xx+side*2,y-3-j),(xx+side*7,y-10-j)]
            path(d,line,(146,58,65,round(255*intensity)),3)
            path(d,line,(255,173,135,round(255*intensity)),1)
    overlay=fx.resize(OUTPUT,NEAREST);im.paste(overlay,(0,0),overlay)
    return im


@lru_cache(maxsize=12)
def font(size):
    candidates=[
        os.environ.get("OPENING_CJK_FONT"),
        "C:/Windows/Fonts/msyhbd.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return ImageFont.truetype(candidate,size)
    raise RuntimeError("Set OPENING_CJK_FONT to a Chinese TrueType or OpenType font.")


def lettering(draw, location, copy, size, color, anchor="mm"):
    draw.text(location, copy, font=font(size), fill=color, anchor=anchor)


def speech(frame, speaker, line, top=False, portrait=None):
    """A persistent, speaker-labelled dialogue box, readable on a phone with sound off."""
    draw=ImageDraw.Draw(frame)
    line_width=round(draw.textlength(line,font=font(29)))
    name_width=round(draw.textlength(speaker,font=font(22)))
    portrait_space=49 if portrait else 0
    w=name_width+line_width+62+portrait_space
    left=22 if speaker!="小电" else OUTPUT[0]-w-22
    y=15 if top else 360
    ink="#1c2338"
    color={"小电":"#abebcc","同事":"#d0b7ff"}.get(speaker,"#f1bc87")
    draw.rounded_rectangle((left+3,y+4,left+w+3,y+58),radius=9,fill="#141a2a")
    draw.rounded_rectangle((left,y,left+w,y+54),radius=9,fill=ink,outline=color,width=2)
    if portrait:
        face=cast.face('down')
        stamp=face.crop(face.getbbox());stamp.thumbnail((42,47),Image.Resampling.LANCZOS)
        frame.paste(stamp,(left+12,y+4),stamp)
    text_left=left+portrait_space
    lettering(draw,(text_left+15,y+27),speaker,22,color,"lm")
    draw.line((text_left+name_width+24,y+14,text_left+name_width+24,y+40),fill="#65717c",width=2)
    lettering(draw,(text_left+name_width+37,y+27),line,29,"#fff3df","lm")
    return frame


@lru_cache(maxsize=1)
def studio():
    """A wider view of the midnight lab, including the CRT, desk lamp and rolling chair."""
    p=Image.new("RGB",(384,216));d=ImageDraw.Draw(p);rng=random.Random(382)
    for y in range(216):
        ratio=y/215
        shade=tuple(round(mix(a,b,ratio)) for a,b in zip((35,41,74),(73,67,89)))
        box(d,0,y,384,1,shade)
    box(d,0,13,215,123,"#191e38");box(d,0,16,213,117,"#666689")
    for y in range(110):
        color=tuple(round(mix(a,b,y/109)) for a,b in zip((44,58,110),(102,99,146)))
        box(d,0,y+18,210,1,color)
    for plane in (0,1):
        for x in range(-5,210,14+plane*3):
            h=rng.randint(17,65);base=123+plane*4;w=rng.randint(11,20)
            box(d,x,base-h,w,h,"#505583" if not plane else "#363d6a")
            for yy in range(base-h+5,base,7):
                for xx in range(x+2,x+w-2,5):
                    if rng.random()>.3:box(d,xx,yy,2,3,rng.choice(("#7c81a5","#8287a1","#a89890")))
    for x in (13,83,151,208):
        box(d,x,16,3,116,"#31334f");box(d,x+3,16,1,116,"#777895")
    box(d,0,43,212,3,"#444967");box(d,0,128,215,6,"#302f49")
    box(d,0,131,215,2,"#8a8190")
    box(d,0,184,384,32,"#504b65")
    for x in range(-20,420,39):path(d,[(x,184),(x-15,216)],"#45435a")
    box(d,0,185,384,2,"#777082")
    # At the edge of the work area are the solder station, two drawers and a coiled lead.
    box(d,0,132,45,9,"#9d8582");box(d,0,141,39,29,"#464757")
    for y in (145,154):
        box(d,0,y,37,1,"#7b7078");box(d,17,y+3,9,1,"#a79995")
    box(d,0,116,26,15,"#374649");box(d,2,118,17,7,"#5c7771")
    path(d,[(2,123),(6,122),(9,119),(11,123),(16,121)],"#a6d4a3")
    box(d,22,120,2,2,"#d99a7c")
    # Warm light over the developer ties this wider angle to the original desk lamp.
    light=Image.new("RGBA",p.size);ld=ImageDraw.Draw(light)
    poly(ld,[(49,27),(66,27),(150,150),(28,150)],(255,205,133,21))
    poly(ld,[(52,27),(63,27),(124,146),(44,146)],(255,206,143,13))
    p=Image.alpha_composite(p.convert("RGBA"),light).convert("RGB")
    d=ImageDraw.Draw(p)
    path(d,[(9,0),(28,5),(46,18),(56,18)],"#222839",4)
    path(d,[(13,0),(30,7),(46,16)],"#9a8982")
    poly(d,[(43,23),(51,16),(60,15),(69,20),(72,26),(45,28)],"#393744")
    path(d,[(46,27),(69,25)],"#ffd797",2)
    # Empty chair behind the standing player.
    d.rounded_rectangle((11,122,42,166),radius=6,fill="#242737",outline="#6c6474",width=2)
    box(d,24,165,40,7,"#353344");box(d,44,172,4,20,"#77717c")
    path(d,[(29,196),(45,191),(62,196)],"#303040",3)
    # The same warm desk lamp and cool blue window carry through the original footage.
    path(d,[(375,152),(363,86),(336,27),(311,21)],"#1c2435",4)
    path(d,[(373,149),(361,86),(335,29)],"#8c807b",1)
    poly(d,[(301,17),(307,13),(320,15),(329,24),(299,25)],"#423a46")
    path(d,[(299,25),(328,24)],"#f2cb8b",3)
    box(d,149,158,235,6,"#b39785");box(d,148,158,236,2,"#e2bd99")
    box(d,150,164,234,5,"#594c5b");box(d,159,169,6,45,"#483f51")
    box(d,371,169,7,45,"#483f51")
    return p.resize(OUTPUT,NEAREST)


# Fixed set marks; the actual game capture fills this CRT at native 16:9.
SCREEN=(354,82,726,292)


def crt_shell(frame,content):
    d=ImageDraw.Draw(frame)
    d.rounded_rectangle((337,64,741,309),radius=12,fill="#292a39",outline="#1b2130",width=5)
    d.rounded_rectangle((340,66,737,301),radius=9,fill="#a49a94",outline="#c5b8a3",width=4)
    d.rounded_rectangle((348,76,732,297),radius=7,fill="#353a4c",outline="#6c6874",width=3)
    frame.paste(content.resize((SCREEN[2]-SCREEN[0],SCREEN[3]-SCREEN[1]),Image.Resampling.LANCZOS),SCREEN[:2])
    box(d,699,300,8,3,"#a7d8b4")
    box(d,515,309,46,5,"#7c7278");box(d,499,314,82,3,"#4e4754")


@lru_cache(maxsize=1)
def game_frames():
    atlas=Image.open(ART/"rooftop-hold.png").convert("RGB")
    if atlas.size!=(384,216*6):
        raise ValueError("Expected six 384x216 native motion-stage wing captures.")
    return [atlas.crop((0,n*216,384,(n+1)*216)) for n in range(6)]


def screen_menu(resting=False,selected=False):
    p=Image.new("RGB",(640,360),"#203847");d=ImageDraw.Draw(p)
    for y in range(3,360,8):box(d,0,y,640,2,"#253d4d")
    # The unresolved report is visible both before and after choosing a break.
    d.rounded_rectangle((77,57,564,128),radius=10,fill="#344551",outline="#53626b",width=2)
    d.ellipse((101,82,119,100),fill="#f6a088")
    lettering(d,(141,93),"待修 bug",37,"#f5d2b2","lm")
    lettering(d,(523,92),"1",42,"#ffe3bf","rm")
    bg="#a8e3bf" if selected or resting else "#355e60"
    fg="#203e43" if selected or resting else "#c9efce"
    d.rounded_rectangle((124,176,518,267),radius=11,fill="#162c38")
    d.rounded_rectangle((124,171,518,260),radius=11,fill=bg,outline="#98cdae",width=3)
    lettering(d,(320,214),"正在休息" if resting else "休息一下",49,fg)
    return p


def game_screen(elapsed):
    value=min(5,max(0,elapsed))
    atlas=game_frames()
    # At each full second the same five-star row fills in the shipped motion-stage renderer.
    if .08<=value<1:
        # Pose matching fills the towers immediately. Only the elapsed-time stars wait
        # for a full second in this six-frame sampling of the actual game renderer.
        active=atlas[0].copy()
        for x in (109,275):
            region=(x-12,122,x+13,190)
            active.paste(atlas[1].crop(region),region[:2])
        return active
    return atlas[int(value)]


def exercise_title(frame,complete):
    d=ImageDraw.Draw(frame)
    goal="挑战成功" if complete else "双臂平举 5 秒"
    width=round(d.textlength(goal,font=font(29)))+208
    d.rounded_rectangle((20,12,20+width,61),radius=8,
                        fill="#232b40",outline="#83ac9c",width=2)
    lettering(d,(34,36),"天台展翅",27,"#fff2dc","lm")
    d.line((160,23,160,49),fill="#657781",width=2)
    lettering(d,(177,36),goal,29,"#abe8bf","lm")


def timer(frame,elapsed):
    d=ImageDraw.Draw(frame);done=elapsed>=5;value=max(0,min(5,elapsed))
    # The timer advances only after both wrists have reached shoulder height.
    d.rounded_rectangle((341,337,741,401),radius=9,fill="#242c42",outline="#859d98",width=2)
    lettering(d,(360,364),"保持",24,"#e1e3d9","lm")
    track_x,track_y=424,357
    for i in range(5):
        x=track_x+i*39
        d.rounded_rectangle((x,track_y,x+32,track_y+20),radius=3,fill="#435665")
        fill=min(1,max(0,value-i))
        if fill:
            box(d,x+2,track_y+2,max(1,29*fill),17,"#abeabc")
    count=int(10*value)/10
    lettering(d,(719,365),f"{count:.1f} 秒",27,"#b9f2c6" if done else "#f3e5cd","rm")


def workload(t):
    if t<2.75:
        frame=workshop.typing(t)
        if .45<=t<.80:
            frame=camera(frame,117,160,173)
        elif t>=.80:
            advance=ease(.80,2.70,t)
            frame=camera(frame,180,110,mix(373,348,advance))
        minutes=18*60+30+round(120*ease(1.22,2.67,t))
        d=ImageDraw.Draw(frame)
        d.rounded_rectangle((611,16,745,58),radius=7,fill="#23283c",outline="#a8a1a1",width=2)
        lettering(d,(678,36),f"{minutes//60:02d}:{minutes%60:02d}",29,"#ffe0ae")
        if t<1.05:return speech(frame,"同事","还不下班？")
        return speech(frame,"开发者","修完这一个 bug 就走。")
    brace=bump(4.02,4.36,5.20,t)
    frame=workshop.sleeping(t-2.75,brace)
    if brace:
        pain_marks(frame,[(216,109,-1),(272,149,1)],brace*.87)
    f=ease(2.75,4.87,t)
    frame=camera(frame,mix(192,176,f),mix(108,115,f),mix(384,345,f))
    return speech(frame,"开发者","坐了两小时，肩和腰都酸了。",top=True)


def call_from_screen(t):
    frame=workshop.waking(t)
    leap=ease(.15,1.00,t)
    x=mix(324,205,leap)
    foot=mix(110,180,leap)-48*math.sin(math.pi*leap)
    scale=mix(.20,.73,ease(.04,.94,t))
    glint=math.sin(math.pi*ease(.10,.88,t))
    if glint>.04:
        d=ImageDraw.Draw(frame)
        for n,(dx,dy) in enumerate(((1,-1),(-1,-1),(1,1),(-1,0))):
            a=7+round(glint*(12+n*2));rx=643+dx*a;ry=186+dy*a
            d.line((rx,ry,rx+dx*4,ry+dy*4),fill="#ffdd88",width=3)
    stance="reach" if t<1.0 else "wave" if t<1.56 else "stretch"
    phase=ease(1.56,1.95,t) if stance=="stretch" else t*1.65
    robot_world(frame,stance,phase,x,foot,scale,angle=-10*math.sin(math.pi*leap),
                squash=1-.11*bump(.91,1.00,1.13,t))
    if t>1.05:speech(frame,"小电","站起来，展翅给首站充电！",top=True)
    return frame


def stretch_room(t):
    frame=studio().copy()
    copy_human=ease(11.20,12.50,t)
    content=camera_raise_frames()[round(copy_human*8)] if t<12.50 else game_screen(t-12.50)
    crt_shell(frame,content)
    wrists=cast.stretch(frame,87,197,copy_human)
    if t<12.32:pain_marks(frame,[(79,83,-1)],.63*(1-ease(11.25,12.32,t)))
    if t<14.2:tracking_points(frame,wrists)
    d=ImageDraw.Draw(frame)
    box(d,524,60,33,11,"#292c3b")
    d.ellipse((535,62,541,68),fill="#6e94a4")
    box(d,549,63,3,3,"#a0eab5")
    exercise_title(frame,t>=17.50)
    if t>=12.50:timer(frame,t-12.50)
    return frame


@lru_cache(maxsize=1)
def camera_raise_frames():
    atlas=Image.open(ART/"rooftop-raise.png").convert("RGB")
    return [atlas.crop((0,i*216,384,(i+1)*216)) for i in range(9)]


def tracking_points(frame,wrists):
    d=ImageDraw.Draw(frame)
    for x,y in wrists:
        d.ellipse((x-6,y-6,x+6,y+6),outline="#b8f7cf",width=2)
    d.rounded_rectangle((21,338,185,374),radius=6,fill="#233644",outline="#659887",width=1)
    d.ellipse((31,350,40,359),fill="#adf1bd")
    lettering(d,(50,356),"摄像头体感",21,"#ccf0d9","lm")


def camera_opt_in(t):
    frame=studio().copy()
    p=Image.new("RGB",(640,360),"#22273b");d=ImageDraw.Draw(p)
    lettering(d,(320,78),"天台展翅",45,"#f6eee0")
    d.rounded_rectangle((66,155,574,265),radius=14,fill="#bdff98" if t>.82 else "#a8e8b9")
    lettering(d,(319,209),"开启摄像头玩这关",45,"#203b31")
    crt_shell(frame,p)
    frame=camera(frame,267,108,249)
    arm,px,py=cast.pointing(False)
    approach=ease(.01,.87,t)
    leave=ease(.90,1.14,t)
    x=mix(115,408,approach)-113*leave
    y=mix(425,224,approach)+170*leave
    frame.paste(arm,(round(x-px),round(y-py)),arm)
    return frame


def relaxed_room(t,content=None):
    frame=studio().copy()
    crt_shell(frame,game_screen(5) if content is None else content)
    elapsed=t-16.75
    if elapsed<.65:
        hold=1-ease(.10,.65,elapsed)
        cast.resting(frame,.36*elapsed)
        pain_marks(frame,[(66,130,-1)],.60*hold)
        return camera(frame,101,133,183)
    cast.resting(frame,elapsed-.42)
    return camera(frame,132,101,mix(289,254,ease(.65,2.15,elapsed)))


def rest_choice(t):
    p=studio().copy()
    pressed=t>=21.20
    crt_shell(p,screen_menu(pressed,selected=20.97<=t<21.20))
    if t<20.03:
        cast.resting(p,t-19.35+1.70)
        p=camera(p,142,107,275)
        return p if t<19.68 else speech(p,"开发者","这个 bug，等会儿修。")
    # Match cut closer to his chosen control. An orange cuff connects his finger to his decision.
    p=camera(p,267,111,236)
    arm,px,py=cast.pointing(False)
    approach=ease(20.03,21.20,t)
    retreat=ease(21.40,22.01,t)
    x=mix(137,414,approach)-192*retreat
    y=mix(421,229,approach)+216*retreat
    if retreat<.985:p.paste(arm,(round(x-px),round(y-py)),arm)
    if t<21.58:speech(p,"开发者","这个 bug，等会儿修。")
    return p


def cactus(d,x,y):
    box(d,x-4,y-23,8,23,INK);box(d,x-2,y-21,4,20,"#85c195")
    path(d,[(x,y-8),(x-9,y-8),(x-9,y-16)],"#4e8277",4)
    path(d,[(x,y-14),(x+8,y-14),(x+8,y-20)],"#68a182",3)


@lru_cache(maxsize=4)
def drawing(name):
    from opening_rider import motion_cel
    src=motion_cel(name)
    padded=Image.new("RGBA",(src.width+20,src.height+20))
    padded.alpha_composite(src,(10,10))
    yy,xx=np.indices((padded.height,padded.width),dtype=np.float32)
    return np.array(padded),xx,yy,src.size


def action_drawing(im,pose,x,floor,size,phase,strength=1):
    """Expose the compact character's painted run, anticipation, apex and landing cels."""
    rgba,xx,yy,(w,h)=drawing(pose)
    leg=np.clip((yy-10-h*.55)/(h*.44),0,1)
    side=np.tanh((xx-10-w*.50)/6)
    reach=np.clip((np.abs(xx-10-w*.49)-w*.20)/(w*.27),0,1)*(1-leg)
    stride=math.sin(phase)*strength
    if pose=="run":
        dx=(6.5*leg*side+1.6*reach*side)*stride
        dy=4*leg*np.maximum(0,side*stride)+reach*math.cos(phase)
    else:
        dx=(2.1*leg*side+1.1*reach*side)*stride
        dy=1.6*leg*np.maximum(0,side*stride)+.7*reach*math.cos(phase)
    pic=Image.fromarray(cv2.remap(rgba,xx-dx,yy+dy,cv2.INTER_NEAREST,
                                   borderMode=cv2.BORDER_CONSTANT))
    scale=2*size
    pic=pic.resize((round(pic.width*scale),round(pic.height*scale)),NEAREST)
    origin=(round(2*x-(10+w*.5)*scale),round(2*floor-(10+h)*scale))
    im.paste(pic,origin,pic)
    px,py={"run":(76,51),"crouch":(59,66),"leap":(82,16),"land":(85,50)}[pose]
    # Track the animated palm instead of leading the hand with the signal.
    vx=round(px+10);vy=round(py+10)
    return x+(px-w*.5+dx[vy,vx])*size,floor+(py-h-dy[vy,vx])*size



def coach_body(d,x,y):
    poly(d,[(x,y+9),(x+8,y+2),(x+165,y+2),(x+174,y+9),(x+174,y+88),(x+170,y+95),
            (x+4,y+95),(x,y+89)],"#383749")
    box(d,x+3,y+11,168,76,"#cbb6a2")
    box(d,x+6,y+6,159,4,"#eee1c5");box(d,x+5,y+12,166,5,"#8b777e")
    for k in range(3):
        xx=x+11+k*53;box(d,xx,y+20,46,42,"#514854");box(d,xx+2,y+22,42,38,"#768da0")
        box(d,xx+4,y+24,36,15,"#a9b5b2");box(d,xx+4,y+56,38,3,"#a58d85")
        if k!=1:
            px=xx+19;py=y+39
            poly(d,[(px-7,py+12),(px-3,py+6),(px+5,py+6),(px+11,py+14),(px+12,py+18),(px-8,py+18)],"#5a737d")
            box(d,px-2,py-3,8,10,"#c3947e");box(d,px-3,py-4,10,4,"#5f4d56")
            box(d,px+6,py+1,2,2,"#ddba9b")
    box(d,x+3,y+66,168,6,"#a35c61");box(d,x+3,y+72,168,2,"#ebc184")
    box(d,x+6,y+87,162,4,"#7e6d71")
    for k in (24,138):
        d.ellipse((x+k,y+87,x+k+15,y+102),fill="#252b3b");d.ellipse((x+k+4,y+91,x+k+11,y+98),fill="#777683")
    box(d,x+59,y+22,2,39,"#c5ae98")


@lru_cache(maxsize=1)
def desert_plate():
    im=Image.new("RGB",(540,216));d=ImageDraw.Draw(im)
    for yy in range(216):
        f=yy/216;shade=tuple(round(mix(a,b,f)) for a,b in zip((192,128,133),(255,213,147)))
        box(d,0,yy,540,1,shade)
    d.ellipse((319,21,354,56),fill="#ffe4a8")
    for i,(x,y,w) in enumerate(((22,33,55),(124,55,77),(250,38,47),(430,28,66))):
        poly(d,[(x,y+4),(x+14,y+2),(x+19,y),(x+32,y),(x+38,y+2),(x+w,y+3),(x+w-1,y+5),(x,y+5)],"#e5ac96")
    palettes=(("#b9888a","#ac7d81"),("#c38b7a","#ab7774"),("#d6a085","#aa7a79"))
    for layer,(color,shade) in enumerate(palettes):
        rng=random.Random(317+layer);y=116+layer*15
        for j in range(-1,8):
            x=j*90+rng.randint(-15,20);h=rng.randint(29,53)-layer*4;w=rng.randint(59,96)
            pts=[(x,y),(x+15,y-h*.33),(x+25,y-h*.45),(x+32,y-h*.96),
                 (x+w*.59,y-h),(x+w*.64,y-h*.92),(x+w*.73,y-h*.38),(x+w,y),(x+w,y+20),(x,y+20)]
            poly(d,pts,color);poly(d,[pts[4],pts[5],pts[6],pts[7],(x+w*.74,y),(x+w*.56,y-h*.50)],shade)
    box(d,0,159,540,57,"#dfae88")
    rng=random.Random(616)
    for i in range(270):
        x=rng.randrange(540);y=rng.randint(157,216)
        box(d,x,y,rng.randrange(1,6),1,rng.choice(("#dda384","#c88b78","#f5c99c")))
    return im


def plate(n):
    x=n%2*384;y=n//2*216
    return PLATES.crop((x,y,x+384,y+216))


def pulse(d,x,y,scale=1,travel=True):
    """The same bright signal is handed on at each site."""
    r=round(6*scale);x=round(x);y=round(y)
    if travel:
        path(d,[(x-r*3,y+1),(x-r,y+1)],"#82c9af",max(1,r//3))
        box(d,x-r*4,y+1,r//2+1,1,"#ffe4a3")
    poly(d,[(x-r-2,y),(x,y-r-2),(x+r+2,y),(x,y+r+2)],"#254752")
    poly(d,[(x-r,y),(x,y-r),(x+r,y),(x,y+r)],"#83d8ac")
    poly(d,[(x-r//2,y),(x,y-r//2),(x+r//2,y),(x,y+r//2)],"#ffe4a6")


def stage_heading(frame,name,action):
    d=ImageDraw.Draw(frame)
    heading_w=round(d.textlength(name,font=font(32)))
    hint_w=round(d.textlength(action,font=font(24)))
    d.rounded_rectangle((18,12,heading_w+hint_w+68,65),radius=8,
                        fill="#232a3f",outline="#959c9c",width=2)
    lettering(d,(31,38),name,32,"#fff2dc","lm")
    x=heading_w+50
    d.line((x-5,25,x-5,52),fill="#6a7788",width=2)
    lettering(d,(x+5,39),action,24,"#b5e5c7","lm")


def cloud(d,x,y,w,color):
    poly(d,[(x,y),(x+w*.16,y-2),(x+w*.26,y-2),(x+w*.31,y-5),(x+w*.56,y-5),
            (x+w*.63,y-3),(x+w*.78,y-3),(x+w*.84,y-1),(x+w,y),(x+w,y+2),(x,y+2)],color)


@lru_cache(maxsize=1)
def highland_sky():
    im=Image.new("RGB",(384,216));d=ImageDraw.Draw(im)
    for y in range(216):
        k=min(1,y/177);c=tuple(round(mix(a,b,k)) for a,b in zip((69,111,149),(204,209,176)))
        box(d,0,y,384,1,c)
    d.ellipse((50,36,77,63),fill="#f4d7a3")
    for row,(base,light,dark) in enumerate(((153,"#9eabb7","#8a9ba7"),(180,"#7d94a0","#667f8e"))):
        rng=random.Random(509+row);x=-33
        while x<390:
            w=rng.randint(46,91);h=rng.randint(26,55);peak=x+w*.55
            poly(d,[(x,base),(peak,base-h),(x+w,base),(x+w,215),(x,215)],light)
            poly(d,[(peak,base-h),(peak-1,base-h*.66),(peak+10,base-h*.39),(x+w-8,base),(x+w,base)],dark)
            poly(d,[(peak-8,base-h+10),(peak,base-h),(peak+9,base-h+11),(peak+1,base-h+7)],"#dcdcca")
            x+=w-10
    for i in range(7):cloud(d,i*73-22,158+i%3*8,69,"#d7dccb")
    return im


def flight(t):
    from opening_rider import draw_deck, draw_rider
    im=highland_sky().copy();d=ImageDraw.Draw(im)
    # High clouds pass slowly; near clouds sweep across the lower edge as the glider gains height.
    for i in range(6):
        cloud(d,(i*93-26*t)%460-46,53+i%3*23,33+i*5,"#a5c7bf")
    for i in range(3):
        cloud(d,(i*183-98*t)%540-73,173+i%2*20,93,"#e0dfcd")
    for i in range(3):
        bx=74+i*57+6*t;by=78-(i%2)*12+2*math.sin(t*3+i)
        path(d,[(bx-6,by-2),(bx-2,by-1),(bx,by+1),(bx+3,by-2),(bx+7,by-3)],"#768a92")
    flap_time=min(t,2.32)+.10*ease(2.32,2.65,t)
    wing_phase=math.tau*(flap_time-.43)/.73
    boosts=sum(ease(at,at+.36,t) for at in (.68,1.39,2.15))
    x=70+191*ease(0,3.30,t);y=186-20*boosts+2*math.sin(wing_phase)
    pitch=-.035-.052*math.cos(wing_phase)
    draw_deck(d,x,y,pitch,"flight")
    for i in range(3):
        path(d,[(x-49-i*9,y+i*3),(x-64-i*9,y+i*3+2)],"#d8ebdc",2)
    # The aerial station receives the signal at the tip of the blue mountain flag.
    poly(d,[(307,216),(313,141),(325,116),(330,116),(346,147),(362,216)],"#7c8a8e")
    poly(d,[(330,116),(346,147),(362,216),(346,216),(335,157)],"#687d89")
    box(d,326,88,5,31,"#3b5865")
    poly(d,[(330,86),(347,90),(330,96)],"#f7cf82" if t>2.83 else "#897e8b")
    frame=im.resize(OUTPUT,NEAREST)
    draw_rider(frame,x-9,y-9*pitch,wing_phase,"flight",slope=pitch,scale=1.00)
    robot_world(frame,"flight",(flap_time-.43)/.73,x+29,y+29*pitch,.52,angle=-4)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    f=ease(2.53,3.16,t)
    if .45<=t<=3.14:pulse(d,mix(x+40,332,f),mix(y-11,88,f)-7*math.sin(f*math.pi))
    if t>3.11:path(d,[(333,88),(351,88),(363,75),(383,75)],"#a9ebbd",2)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def platform(t):
    im=plate(0);d=ImageDraw.Draw(im)
    box(d,0,34,384,4,"#635b72");box(d,0,38,384,1,"#b6a2a5")
    for x in (12,349):box(d,x,36,4,112,"#705f73")
    departure=ease(2.35,3.5,t);coach=97+122*departure
    for j in range(-3,3):coach_body(d,round(coach+j*177),48)
    # The passenger raises her arm after the developer waves, then the platform signal changes.
    px=coach+136;py=86;hand_y=py+10-22*ease(1.43,1.83,t)
    poly(d,[(px-12,104),(px-10,93),(px-5,89),(px+5,89),(px+12,97),(px+13,105)],"#937583")
    box(d,px-5,79,11,12,"#e9af87");box(d,px-6,77,12,5,"#4f4149")
    box(d,px-7,80,4,9,"#584651");box(d,px+2,83,2,2,"#534553")
    fingertip=px+15+4*math.sin(13*t)*ease(1.43,1.70,t)
    path(d,[(px+4,py+8),(px+10,py+9),(fingertip,hand_y)],"#735e76",5)
    box(d,fingertip-2,hand_y-3,5,6,"#f0bd94")
    box(d,308,77,4,79,"#444b52");box(d,303,61,14,20,"#343f48")
    d.ellipse((306,64,313,71),fill="#b0e8a8" if t>=2.14 else "#e8a185")
    d.ellipse((306,72,313,78),fill="#5b6c6b")
    box(d,0,150,384,66,"#857785");box(d,0,150,384,4,"#c5a48a")
    for j in range(32):box(d,j*13,159,8,2,"#edc08a")
    for j in range(14):path(d,[(j*32,166),(j*32-25,216)],"#706574")
    d.ellipse((67,185,113,190),fill="#675f70")
    frame=im.resize(OUTPUT,NEAREST)
    wave=ease(.38,.9,t)*(1-ease(2.34,3.34,t))
    cast.wave(frame,91,188,wave,(t-.72)*9)
    robot_world(frame,"wave",(t-.88),coach+85,115,.52,angle=-3*math.sin(t*4))
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    box(d,coach+58,109,52,5,"#af9184");box(d,coach+60,114,49,1,"#e6c5a8")
    relay=ease(1.90,2.35,t)
    pos=mix(308,coach+102,relay)
    if .45<=t<=3.14:pulse(d,pos,mix(67,60,relay),.84)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def snow_gate(d,x,y,size,touched):
    h=max(7,round(size*27));w=max(2,round(size*3))
    box(d,x,y-h,w,h,"#465766")
    offset=round(4*size) if touched else 0
    poly(d,[(x+w,y-h+1),(x+w+size*13,y-h+5+offset),(x+w,y-h+11)],"#99dfa7" if touched else "#e99277")
    box(d,x-4*size,y+h*.02,13*size,2,"#829f9f")


def slalom(t):
    from opening_rider import draw_deck, draw_rider
    im=plate(2);d=ImageDraw.Draw(im)
    width=384; horizon=100
    for i in range(15):
        z=(i/15+t*.41)%1; yy=horizon+109*z*z
        span=24+110*z*z;x=196+31*math.sin(t*3.3+.7*z)
        if i%2:
            box(d,x-span,yy,2+4*z,1+z,"#9cb7b1")
            box(d,x+span,yy,2+4*z,1+z,"#b8c8b6")
    # CameraRound's final three targets in a six-flag run are left, right, left.
    steer=-math.sin((t-.42)*math.pi/.84)
    skier=190+51*steer+12*ease(0,3.30,t)
    for j,at in enumerate((.85,1.65,2.50)):
        z=max(0,min(1.2,(t-at+1.52)/1.75)); yy=95+94*z*z
        side=-1 if j%2==0 else 1
        xx=192+side*(24+92*z*z)
        if t<at+.62:snow_gate(d,xx,yy,.38+.92*z,t>=at)
        if t<at+.52:snow_gate(d,xx-side*(23+56*z),yy-5,.38+.84*z,t>=at)
    for i in range(3):
        path(d,[(skier-41-i*6,213),(skier-33-i*6,202),(skier-22-i*4,190)],"#f1eddd",2)
    pitch=-.08+.044*steer
    draw_deck(d,skier,183,pitch,"ski")
    for i in range(7):
        spray=(t*1.9+i/7)%1
        box(d,skier-steer*(18+spray*32),187-14*math.sin(spray*math.pi),2+i%2,1+i%2,"#f6f0db")
    frame=im.resize(OUTPUT,NEAREST)
    draw_rider(frame,skier-8,183-8*pitch,t*5,"ski",steer=steer,slope=pitch,scale=1.06)
    robot_world(frame,"ski",t*.6,skier+29,183+29*pitch,.51,angle=-13*steer)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    relay=ease(2.74,3.46,t)
    if .45<=t<=3.14:pulse(d,mix(skier+32,379,relay),mix(171,113,relay),.83)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def music_station(t):
    im=plate(3);d=ImageDraw.Draw(im)
    colors=("#b6d9b7","#f4c793","#d8b5df","#93d3d0")
    times=(.60,1.15,1.70,2.25)
    keys=tuple(57+i*24 for i in range(10))
    # Last four targets in CameraRound's eight-note melody.
    xs=tuple(keys[i] for i in (1,8,4,5))
    box(d,39,113,259,78,"#353448");box(d,41,115,255,70,"#75657b")
    current=sum(t>=moment+.10 for moment in times)
    for i,x in enumerate(keys):
        active=xs.index(x) if x in xs else None
        press=0 if active is None else bump(times[active]-.12,times[active],times[active]+.22,t)
        dip=round(7*press)
        col="#ffda82" if active==current else "#e4d6be"
        box(d,x-11,130+dip,23,37,INK);box(d,x-9,132+dip,19,29,col)
        box(d,x-9,162+dip,19,3,"#a99590")
        if i in (0,1,3,4,5,7,8):box(d,x+6,129+dip,9,14,"#484252")
    for j,(x,col,at) in enumerate(zip(xs,colors,times)):
        box(d,x-16,123,31,3,col if t>=at else "#4d485e")
        if t>=at:
            path(d,[(x,119),(x,107-j*3),(291,107-j*3),(303,95-j*2)],col,2)
    frame=im.resize(OUTPUT,NEAREST)
    robot_world(frame,"nod",.2+.68*max(0,math.cos((t-.60)*math.tau/.55)),331,132,.68)
    hand,px,py=cast.pointing(True)
    path_x=track([(0,43),(.48,xs[0]),(.64,xs[0]),(1.04,xs[1]),(1.21,xs[1]),
                  (1.59,xs[2]),(1.76,xs[2]),(2.14,xs[3]),(2.32,xs[3]),(3.50,271)],t)
    height=126+19*max(bump(at-.11,at,at+.20,t) for at in times)
    frame.paste(hand,(round(path_x*2-px),round(height*2-py)),hand)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    if 2.25<t<=3.14:
        f=ease(2.25,3.27,t);pulse(d,mix(262,369,f),mix(116,85,f),.9)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def sand_run(t):
    pan=round(67*ease(0,3.5,t))
    im=desert_plate().crop((pan,0,pan+384,216));d=ImageDraw.Draw(im)
    for j in range(5):cactus(d,j*106+10-round(pan*.55),155+3*(j%2))
    x=69+193*ease(0,3.4,t)
    obstacle=227-77*ease(.2,3.5,t)
    d.ellipse((obstacle-16,181,obstacle+18,186),fill="#b58472")
    cactus(d,obstacle,182);cactus(d,obstacle+10,183)
    for j in (0,1):
        path(d,[(obstacle+j*10-3,162),(obstacle+j*10-5,160)],"#73625d")
    arc=math.sin(math.pi*np.clip((t-1.15)/1.25,0,1))
    floor=185-48*arc-2*(1-ease(.66,1.10,t))*abs(math.sin(t*12))
    d.ellipse((x-15+4*arc,183,x+15-4*arc,187),fill="#ae8271")
    botx=128+182*ease(0,3.42,t)
    botarc=math.sin(math.pi*np.clip((t-.67)/1.0,0,1))
    frame=im.resize(OUTPUT,NEAREST)
    robot_world(frame,"vault" if botarc>.10 else "wave",t*2,botx,184-37*botarc,.57,
                angle=-11*botarc+3*math.sin(t*8))
    pose="run" if t<.93 else "crouch" if t<1.19 else "leap" if t<2.38 else "land"
    hand_x,hand_y=action_drawing(frame,pose,x,floor,1.08,t*12,.64 if pose=="leap" else 1)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    handoff=ease(2.74,3.45,t)
    if .45<=t<=3.14:
        pulse(d,mix(hand_x+4,361,handoff),mix(hand_y-5,88,handoff)-9*math.sin(math.pi*handoff),.88)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def show_shoulder_input(frame,t):
    # The player stays at the desk; only the in-game runner leaves the ground.
    if t>=2.8:return
    lift=bump(.84,1.18,1.91,t)
    rise=round(12*lift)
    tile=Image.new("RGBA",(148,117))
    d=ImageDraw.Draw(tile)
    d.rounded_rectangle((0,0,147,116),radius=8,fill="#202c3c",outline="#9ca9a6",width=2)
    d.rounded_rectangle((21,59,122,107),radius=8,fill="#384755")
    for xx in range(14,134,7):
        d.line((xx,75,xx+3,75),fill="#788e92")
    portrait=cast.portrait()
    visible=portrait.crop((0,0,portrait.width,102-(25-rise)))
    tile.alpha_composite(visible,(33,25-rise))
    box(d,4,102,140,10,"#41515b");box(d,4,102,140,2,"#a4ab9a")
    box(d,12,9,7,7,"#93e8aa")
    lettering(d,(26,14),"体感",17,"#c6ead5","lm")
    for xx in (22,126):
        top=70-rise
        path(d,[(xx,82),(xx,top)],"#a1edb8",3)
        path(d,[(xx-5,top+5),(xx,top),(xx+5,top+5)],"#a1edb8",3)
    alpha=min(ease(0,.15,t),1-ease(2.52,2.80,t))
    if alpha<1:tile.putalpha(tile.getchannel("A").point(lambda v:round(v*alpha)))
    frame.paste(tile,(600,71),tile)


def lighthouse(d,x,y,on,side):
    poly(d,[(x-12,y),(x-5,y-54),(x+6,y-54),(x+12,y)],"#343c55")
    poly(d,[(x-8,y-1),(x-4,y-53),(x+1,y-53),(x+3,y-1)],"#d4ad95")
    poly(d,[(x+1,y-53),(x+4,y-53),(x+9,y-1),(x+3,y-1)],"#997a7c")
    for j in (19,33):box(d,x-6,y-j,14,5,"#ac6b69")
    box(d,x-9,y-67,19,15,"#30364b");box(d,x-6,y-65,13,9,"#ffe0a1" if on else "#828d9c")
    box(d,x-1,y-65,2,9,"#595d70")
    poly(d,[(x-11,y-67),(x,y-76),(x+11,y-67)],"#6c6a80")
    box(d,x-10,y-54,21,2,"#41495a")


def lookout(t):
    im=plate(0);d=ImageDraw.Draw(im)
    box(d,0,137,384,66,"#545b77")
    for i in range(45):
        x=(i*81+round(t*6))%384; y=139+(i*13)%48
        box(d,x,y,4+i%8,1,"#7b8291" if i%3 else "#91929d")
    left_on=t>=.82;right_on=t>=2.06
    beams=Image.new("RGBA",(384,216));b=ImageDraw.Draw(beams)
    if left_on:poly(b,[(50,85),(47,80),(183,27),(196,49)],(237,216,150,97))
    if right_on:poly(b,[(334,84),(337,79),(193,26),(180,48)],(183,226,202,102))
    im=Image.alpha_composite(im.convert("RGBA"),beams).convert("RGB");d=ImageDraw.Draw(im)
    for x,side,on in ((47,-1,left_on),(336,1,right_on)):
        poly(d,[(x-27,149),(x-15,142),(x-6,138),(x+19,145),(x+34,153)],"#565767")
        lighthouse(d,x,145,on,side)
    box(d,85,170,214,24,"#6e6779");box(d,80,169,226,3,"#b4968e")
    frame=im.resize(OUTPUT,NEAREST)
    yaw=-bump(.26,.82,1.49,t)+bump(1.50,2.06,2.95,t)
    cast.turn_or_nod(frame,145,223,"look",yaw,1.57)
    robot_world(frame,"look",yaw,228,181,1.01)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    if right_on and t<=3.14:
        f=ease(2.07,3.30,t);pulse(d,mix(191,375,f),mix(38,91,f),.86)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


def beat_room(t):
    im=plate(0);d=ImageDraw.Draw(im)
    for x in (10,84,168,249,373):
        box(d,x,35,5,115,"#424759");box(d,x+1,36,1,111,"#858292")
    box(d,0,36,384,3,"#3e465c");box(d,0,128,384,6,"#4c4c60")
    box(d,0,134,384,34,"#5a596d")
    path(d,[(198,166),(242,166),(257,151),(285,151),(285,143)],"#9c8d95",3)
    box(d,271,50,100,105,"#273340");box(d,274,53,94,98,"#4e5864")
    box(d,280,59,83,85,"#263f49")
    beats=(.85,1.62,2.42)
    nod=max(bump(at-.25,at,at+.29,t) for at in beats)
    count=sum(t>=at for at in beats)
    for j in range(3):
        col=("#e7a18a","#ebce92","#a9e0ba")[j] if j<count else "#4d6167"
        d.ellipse((290+j*22,84,308+j*22,102),fill="#202d3d")
        d.ellipse((293+j*22,87,305+j*22,99),fill=col)
        if j<count:box(d,295+j*22,88,7,2,"#f9e7b8")
        box(d,290+j*22,108,17,3,col)
    for j in range(15):
        h=2+round((2+count*3)*abs(math.sin(j*.9+t*5)))
        box(d,284+j*5,133-h,3,h,"#8bb6a4" if count else "#526976")
    box(d,0,168,384,48,"#43455c");box(d,0,168,384,3,"#938491")
    for j in range(7):box(d,27+j*54,174,24,4,"#737181")
    frame=im.resize(OUTPUT,NEAREST)
    cast.turn_or_nod(frame,104,220,"nod",nod,1.60)
    robot_world(frame,"nod",nod,211,175,.93)
    fg=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fg)
    if 3.00<t<=3.14:
        f=ease(3.0,3.48,t);path(d,[(347,118),(358,118),(365,111),(384,111)],"#aae5b7",2)
        pulse(d,mix(338,382,f),mix(120,111,f),.86)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    return frame


ROUTE=(
    ("老鹰起飞","扇翅升空",flight,2.95),("月台挥手","挥手送别",platform,2.36),
    ("雪岭穿梭","侧倾过旗门",slalom,2.55),("落日合奏","对准亮键下压",music_station,2.31),
    ("仙人掌跳跃","轻挺上身起跳",sand_run,2.43),("左右转头","对准两盏灯",lookout,2.06),
    ("节拍点头","点头合拍",beat_room,3.03))

# The montage shows the final repetitions in each round. These counters preserve
# the real targets. Turning registers at the side; nodding registers on return.
TARGETS=((8,(.85,1.52,2.30)),(10,(1.03,1.82)),(6,(.85,1.65,2.50)),(8,(.60,1.15,1.70,2.25)),
         (5,(2.40,)),(6,(.82,2.06)),(6,(1.11,1.91,2.71)))


def last_reps(frame,index,elapsed):
    target,checks=TARGETS[index]
    value=target-len(checks)+sum(elapsed>=v for v in checks)
    d=ImageDraw.Draw(frame)
    d.rounded_rectangle((628,15,747,60),radius=7,fill="#202a3c",outline="#838e96",width=2)
    lettering(d,(686,36),f"{value} / {target}",27,"#adf1bc" if value==target else "#f3e7d3")


def pass_signal(frame,index,elapsed):
    # The outgoing right-edge packet reappears at exactly the same height at the
    # next shot's left edge, then reaches that station's equipment.
    docks=((98,166),(307,68),(174,169),(83,124),(119,111),(191,134),(286,118))
    if elapsed<.45:
        f=ease(0,.45,elapsed)
        x=mix(-7,docks[index][0],f);y=mix(111,docks[index][1],f)
    elif elapsed>3.14:
        f=ease(3.14,3.50,elapsed)
        x=mix(338,393,f);y=mix((88,64,113,85,88,91,113)[index],111,f)
    else:return
    fg=Image.new("RGBA",(384,216));pulse(ImageDraw.Draw(fg),x,y,1.12)
    fg=fg.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)


def follow_action(frame,index,t):
    # Stay wide for each hand-off. In between, let the frame anticipate the moving
    # subject or look towards the passenger / station being activated.
    active=ease(.23,.79,t)*(1-ease(2.72,3.17,t))
    if active<.01:return frame
    if index==0:
        x=135+70*ease(.4,2.7,t);y=111;push=41
    elif index==1:
        x=139+62*ease(.9,1.85,t);y=111;push=56
    elif index==2:
        x=192-22*math.sin((t-.4)*math.pi/.84);y=142;push=43
    elif index==3:
        x=182+13*math.sin(t*5.5);y=129;push=34
    elif index==4:
        x=132+78*ease(.65,2.55,t);y=119-30*math.sin(math.pi*ease(1.15,2.4,t));push=36
    elif index==5:
        x=165+49*ease(1.1,2.15,t);y=105;push=21
    else:
        x=187+21*ease(1.2,2.75,t);y=112;push=23
    return camera(frame,mix(192,x,active),mix(108,y,active),384-push*active)


@lru_cache(maxsize=6)
def product_art(name):
    # Product imagery is cached for offline rendering. The recorded eight-action
    # CameraRound completion uses the trajectories in the project's camera-round test.
    return Image.open(ART/f"product-{name}.png").convert("RGB")


def fit_into(frame,pic,rect):
    x,y,w,h=rect;scale=min(w/pic.width,h/pic.height)
    resized=pic.resize((round(pic.width*scale),round(pic.height*scale)),Image.Resampling.LANCZOS)
    at=(round(x+(w-resized.width)/2),round(y+(h-resized.height)/2))
    frame.paste(resized,at)
    return at,scale


def pointer(draw,x,y,pressed):
    if pressed:
        draw.ellipse((x-12,y-12,x+12,y+12),outline="#a0ecc7",width=3)
    poly(draw,[(x,y),(x+1,y+20),(x+7,y+14),(x+12,y+22),(x+17,y+19),(x+12,y+11),(x+20,y+10)],"#23323d")
    poly(draw,[(x+2,y+3),(x+3,y+16),(x+8,y+11),(x+13,y+18),(x+14,y+17),(x+9,y+9),(x+15,y+9)],"#f5efda")


def product_epilogue(t):
    frame=Image.new("RGB",OUTPUT,"#171d2d")
    d=ImageDraw.Draw(frame)
    if t<52.10:
        pic=product_art("result")
        lettering(d,(29,32),"回血战报",36,"#f3ede1","lm")
        lettering(d,(734,32),"工位回血",23,"#b3d8c6","rm")
        if pic.height>pic.width:
            # Native exported 800x1000 poster plus two legible details from that very PNG.
            fit_into(frame,pic,(20,64,277,352))
            score=pic.crop((65,537,595,741))
            stats=pic.crop((68,769,702,870))
            frame.paste(score.resize((400,154),Image.Resampling.LANCZOS),(329,78))
            frame.paste(stats.resize((405,65),Image.Resampling.LANCZOS),(329,245))
            d.rounded_rectangle((321,334,522,390),radius=8,fill="#bded9e")
            d.rounded_rectangle((534,334,739,390),radius=8,fill="#373e4e",outline="#799588",width=2)
            lettering(d,(422,361),"保存战绩海报",25,"#23382b")
            lettering(d,(636,361),"邀请好友",25,"#eff2d9")
            goal=(643,360)
        else:
            at,scale=fit_into(frame,pic,(14,62,740,355))
            goal=(at[0]+pic.width*scale*.52,at[1]+pic.height*scale*.93)
        # The click targets an invitation action; the film does not claim a message was sent.
        if t>50.38:
            slide=ease(50.38,51.25,t)
            pointer(d,mix(688,goal[0],slide),mix(392,goal[1],slide),51.25<=t<51.52)
        return frame
    title="八张挑战卡带"
    lettering(d,(24,31),title,32,"#f3ede1","lm")
    mode=product_art("mode")
    fit_into(frame,mode,(388,9,356,48))
    # Show the actual playable cartridge selector, including each motion target.
    fit_into(frame,product_art("deck"),(16,66,736,282))
    speech(frame,"同事","下次算我一个！")
    return frame


def film_frame(t,frames=None):
    from opening_mission import mission_frame, route_strip
    if t<5.25:return workload(t)
    if t<6.75:return mission_frame(t-5.25)
    if t<8.75:return call_from_screen(t-6.75)
    if t<10.05:
        frame=rising((t-8.75)*1.9/1.3)
        return speech(frame,"小电","站起来，展翅给首站充电！") if t<9.50 else frame
    if t<11.20:return camera_opt_in(t-10.05)
    if t<18.00:return stretch_room(t)
    if t<42.50:
        offset=t-18
        index=min(6,int(offset/3.5));elapsed=offset-3.5*index
        name,action,shot,achieved=ROUTE[index]
        frame=shot(elapsed)
        pass_signal(frame,index,elapsed)
        frame=follow_action(frame,index,elapsed)
        if shot is sand_run:show_shoulder_input(frame,elapsed)
        stage_heading(frame,name,action)
        last_reps(frame,index,elapsed)
        return route_strip(frame,index+1+int(elapsed>=achieved))
    if t<44.50:return mission_frame(t-42.50,completed=8,finale=True)
    if t<46.85:return relaxed_room(t-44.50+16.75,mission_frame(1.95,completed=8,finale=True))
    if t<49.35:return rest_choice(t-46.85+19.35)
    return product_epilogue(t)


def render(source, soundtrack, encoder):
    output=ROOT/"cinema"; output.mkdir(exist_ok=True)
    target=output/"opening.mp4"
    from opening_mix import DURATION, mix_opening
    staging=tempfile.TemporaryDirectory(prefix="desk-opening-")
    mixed=Path(staging.name)/"opening.wav"
    mix_opening(encoder,soundtrack,mixed)
    next_video=output/"opening-render.mp4"
    process=subprocess.Popen([encoder,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
            "-s","768x432","-r",str(FPS),"-i","-","-i",str(mixed),"-map","0:v:0","-map","1:a:0",
            "-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-ar","48000",
            "-ac","2","-t",str(DURATION),"-movflags","+faststart",str(next_video)],stdin=subprocess.PIPE)
    try:
        for n in range(round(DURATION*FPS)):
            frame=film_frame(n/FPS).resize(OUTPUT,NEAREST)
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()
        if process.wait(): raise RuntimeError("ffmpeg could not encode the intro")
    next_video.replace(target)
    staging.cleanup()
    workshop.plate(1).save(output/"opening-poster.jpg",quality=95,subsampling=0)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path,nargs="?",help=argparse.SUPPRESS)
    parser.add_argument("--soundtrack", type=Path, default=ROOT/"audio/intro.mp3")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    opts=parser.parse_args()
    if not opts.ffmpeg:parser.error("Specify --ffmpeg or add ffmpeg to PATH")
    render(opts.source, opts.soundtrack, opts.ffmpeg)
