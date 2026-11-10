"""Cut the developer's five-second stretch with the approved Runway actor and real game frames.

Run: python tools/render_opening.py <downloaded ten-second Runway source.mp4> --soundtrack <intro.mp3>
Requires Pillow, NumPy, OpenCV and ffmpeg. The source Runway task is
aa849db5-701a-45b8-8c43-34a5e3e9192a. The release runs 22.5 seconds.
Set OPENING_CJK_FONT if a Chinese system font is not installed in a standard location.
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

ROOT = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web"
FPS = 24
OUTPUT = (768, 432)
INK, MINT = "#22263b", "#aef4bd"
TEAL = "#4d9797"
ROBOT = Image.open(ROOT / "art/stage-player.png").convert("RGBA")
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


def sprite(im, pic, center, feet, scale):
    p = pic.resize((round(pic.width*scale), round(pic.height*scale)), NEAREST)
    im.paste(p, (round(center - p.width/2), round(feet-p.height)), p)


def mix(a, b, f):
    return a + (b-a)*f


def endpoint(sx,sy,angle,length,side):
    a=math.radians(angle); return (sx+side*math.cos(a)*length,sy+math.sin(a)*length)


def robot(act,f):
    pic=Image.new("RGBA",(104,85));d=ImageDraw.Draw(pic);ox=14;oy=3
    phase=math.sin(2*math.pi*f)
    if act=="stretch":
        raise_arm=ease(0,1,f)
        angles=[(mix(72,0,raise_arm),mix(81,0,raise_arm))]*2
    elif act=="wave":
        angles=[(67,73),(-45,-101+phase*27)]
    elif act=="reach":
        angles=[(15,-23),(-44,-67)]
    elif act=="rest":
        angles=[(67,76),(59,71)]
    else:
        angles=[(20,-24),(-47,-74)]
    for i,(upper,lower) in enumerate(angles):
        side=2*i-1; a=(ox+(24 if i==0 else 54),52); b=endpoint(*a,upper,13,side); c=endpoint(*b,lower,12,side)
        path(d,[a,b,c],INK,7);path(d,[a,b],TEAL,4);path(d,[b,c],MINT,3)
        box(d,c[0]-3,c[1]-3,7,6,INK);box(d,c[0]-2,c[1]-2,5,4,"#94dfad")
    body=ROBOT.crop((78,0,156,78))
    pic.alpha_composite(body,(ox,oy))
    head=ROBOT.crop((0,0,78,78))
    dx=-2 if act in ("wave","reach") else 0
    dy=round(1.5*abs(phase)) if act=="wave" else 0
    pic.alpha_composite(head,(ox+dx,oy+dy)); return pic


ART = Path(__file__).resolve().parent / "opening_art"
PIVOTS = ((295,205),(398,205))
ELBOWS = ((219,205),(459,207))
NECK, HIP = (350,184), (349,346)


def masked(pic, rect):
    layer=Image.new("RGBA",pic.size)
    layer.paste(pic.crop(rect),rect[:2])
    return layer


@lru_cache(maxsize=1)
def rig():
    parts={key:Image.open(ART/f"developer-{key}.png").convert("RGBA")
           for key in ("body","head","left-arm","right-arm")}
    torso=parts["body"]
    parts["legs"]=masked(torso,(0,338,640,650))
    parts["shirt"]=masked(torso,(0,0,640,349))
    for i,(x0,x1) in enumerate(((0,349),(349,640))):
        parts[i,"thigh"]=masked(torso,(x0,338,x1,482))
        parts[i,"calf"]=masked(torso,(x0,465,x1,650))
    # Overlap the two pieces at each elbow; the actual sleeve pixels hide the rotation seam.
    for i,key in enumerate(("left-arm","right-arm")):
        elbow=ELBOWS[i][0]; arm=parts[key]
        upper=(elbow-6,0,640,650) if i==0 else (0,0,elbow+6,650)
        lower=(0,0,elbow+7,650) if i==0 else (elbow-7,0,640,650)
        parts[i,"upper"]=masked(arm,upper)
        parts[i,"lower"]=masked(arm,lower)
    return parts


def rot(pic,angle,pivot):
    return pic.rotate(angle,NEAREST,center=pivot) if abs(angle)>.2 else pic


def ease(start, stop, t):
    return smooth((t-start)/(stop-start))


def bump(start, peak, end, t):
    return ease(start,peak,t)*(1-ease(peak,end,t))


def person(kind, phase, weight, mood=None):
    """Pose the original actor with separate hips, planted legs, rib cage and neck."""
    r=rig(); sine=math.sin(phase); cosine=math.cos(phase)
    if kind=="stretch":
        extension=weight
        tilt=-3*(1-extension)+.65*sine
        head=3-2*extension+1.4*cosine
        lift=mix(76,0,extension)
        arms=((lift,lift+2*(1-extension)),(lift,lift-2*(1-extension)))
        thighs=(1,0)
        knees=(2+weight, -3)
    elif kind=="choose":
        tilt=-4*weight
        head=5-4*weight
        arms=((74,79),(mix(64,12,weight),mix(68,-9,weight)))
        thighs=(2,-1)
        knees=(4,-4)
    else:
        tilt=-8*weight
        head=3+7*(1-weight)
        arms=((77-55*weight,68+66*weight),(76-8*weight,82-25*weight))
        thighs=(3-6*weight,3+3*weight)
        knees=(4+8*weight,-7-4*weight)
    torso=Image.new("RGBA",r["body"].size)
    supporting_arm=None
    for i,(a,b) in enumerate(arms):
        sign=1-2*i
        limb=r[i,"upper"].copy()
        limb.alpha_composite(rot(r[i,"lower"],sign*(b-a),ELBOWS[i]))
        posed=rot(limb,sign*a,PIVOTS[i]);torso.alpha_composite(posed)
        if i==0 and kind=="relief":supporting_arm=posed
    torso.alpha_composite(r["shirt"])
    if supporting_arm is not None:torso.alpha_composite(supporting_arm)
    face=expression(mood or "neutral")
    torso.alpha_composite(rot(face,head,NECK))
    parts=Image.new("RGBA",torso.size)
    for i in (0,1):
        hip=((322,344),(370,344))[i];knee=((299,473),(389,473))[i]
        leg=r[i,"thigh"].copy()
        leg.alpha_composite(rot(r[i,"calf"],knees[i],knee))
        parts.alpha_composite(rot(leg,thighs[i],hip))
    parts.alpha_composite(rot(torso,tilt,HIP),(0,-round(7*weight) if kind=="relief" else 0))
    return parts


@lru_cache(maxsize=5)
def expression(mood):
    if mood=="neutral":return rig()["head"]
    frame=Image.new("RGBA",rig()["head"].size)
    face=Image.open(ART/f"developer-{mood}.png").convert("RGBA")
    face.thumbnail((90,125),Image.Resampling.LANCZOS)
    frame.alpha_composite(face,(349-face.width//2,188-face.height))
    return frame


def performer(im, x, floor, kind, phase, weight=1, size=.25, mood=None):
    frame=person(kind,phase,weight,mood); bbox=frame.getbbox()
    cropped=frame.crop(bbox)
    pic=cropped.resize((round(cropped.width*size*2),round(cropped.height*size*2)),Image.Resampling.LANCZOS)
    pos=(round(x*2+(bbox[0]-349)*size*2),round(floor*2-pic.height))
    im.paste(pic,pos,pic)


def robot_world(im,kind,phase,x,feet,scale,angle=0,squash=1):
    pic=robot(kind,phase).rotate(angle,NEAREST,center=(52,59))
    pic=pic.resize((round(pic.width*2*scale/squash),round(pic.height*2*scale*squash)),NEAREST)
    im.paste(pic,(round(2*x-pic.width/2),round(2*feet-pic.height)),pic)


def decode(source):
    capture=cv2.VideoCapture(str(source)); frames=[]
    if round(capture.get(cv2.CAP_PROP_FPS))!=24:
        raise ValueError("Expected the original 24 fps Runway shot.")
    for i in range(206):
        ok,bgr=capture.read()
        if not ok:raise ValueError(f"Missing source frame {i}")
        # Keep the warm highlights, dark hair and transparent glass exactly as photographed.
        frame=Image.fromarray(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
        frames.append(frame.resize(OUTPUT,Image.Resampling.LANCZOS))
    capture.release()
    return frames


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


def rising(t,frames):
    # The extreme left of the wide take isolates the approved performer. The crop ends at
    # x=177, before both the generator's second actor and the robot on its remaining set.
    frame_no=track([(0,190),(.26,192),(.64,195),(1.10,198),(1.9,202)],t)
    frame=frames[round(frame_no)].copy()
    gx=track([(190,140),(193,147),(194,147),(195,144),(196,144),(197,131),(198,132),
              (199,136),(200,137),(201,146),(202,153)],frame_no)
    gy=track([(190,129),(194,132),(196,135),(197,125),(198,120),(200,120),(202,113)],frame_no)
    s=.41; palma=endpoint(*endpoint(38,52,20,13,-1),-24,12,-1)
    bx=min(165,gx-(palma[0]-52)*s); botfoot=gy-(palma[1]-85)*s
    fx=Image.new("RGBA",(384,216))
    sprite(fx,robot("reach",t/1.9),bx,botfoot,s)
    fg=fx.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    width=mix(161,203,smooth(t/1.9));cy=mix(106,74,smooth((t-.2)/1.25))
    # Give the standing actor headroom without revealing any part of the second performer
    # on camera right. Only 26 guide pixels of the empty left wall extend into the composition.
    gutter=32
    plate=Image.new("RGB",(OUTPUT[0]+gutter*2,OUTPUT[1]))
    plate.paste(frame.crop((0,0,gutter*2,OUTPUT[1])).transpose(Image.Transpose.FLIP_LEFT_RIGHT),(0,0))
    plate.paste(frame,(gutter*2,0))
    left=177-width+gutter;top=cy-width*9/32
    return plate.transform(OUTPUT,Image.Transform.EXTENT,
        (left*2,top*2,(left+width)*2,(top+width*9/16)*2),Image.Resampling.BICUBIC)


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


def tense_back(im,amount):
    # Breathing lifts the orange shoulder and tightens the waist in the actual reference frame.
    yy,xx=np.indices((OUTPUT[1],OUTPUT[0]),dtype=np.float32)
    pull=9*amount*np.exp(-((xx-421)/86)**2-((yy-191)/55)**2)
    brace=3*amount*np.exp(-((xx-641)/56)**2-((yy-328)/52)**2)
    return Image.fromarray(cv2.remap(np.asarray(im),xx+brace,yy+pull,cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_REFLECT_101))


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
    ink="#1c2338"; color="#abebcc" if speaker=="小电" else "#f1bc87"
    draw.rounded_rectangle((left+3,y+4,left+w+3,y+58),radius=9,fill="#141a2a")
    draw.rounded_rectangle((left,y,left+w,y+54),radius=9,fill=ink,outline=color,width=2)
    if portrait:
        face=expression(portrait)
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


def workload(t,frames):
    if t<.5:
        return frames[round(t*25)].copy()
    if t<.80:
        return camera(frames[round(13+(t-.5)*45)],124,177,117)
    if t<2.75:
        n=round(track([(.8,20),(1.85,45),(2.75,62)],t))
        frame=camera(frames[n],201,110,mix(357,382,ease(.8,2.0,t)))
        if t>=1:speech(frame,"开发者","还差一个 bug。")
        return frame
    n=round(track([(2.75,63),(3.09,79),(3.50,106),(4.08,112),(4.38,117)],t))
    frame=frames[n].copy()
    if t>=4.07:
        frame=tense_back(frame,bump(4.07,4.45,5.25,t))
        pain_marks(frame,[(206,85,-1),(328,177,1)],.9)
        f=ease(4.07,5.25,t)
        frame=camera(frame,mix(192,209,f),115,mix(384,351,f))
    return speech(frame,"开发者","坐了两小时，肩和腰都酸了。",top=True,
                  portrait="wince" if t>=4.07 else None)


def call_from_screen(t,frames):
    n=round(track([(0,140),(.48,151),(1.26,166),(2.25,189)],t))
    frame=frames[min(n,151)].copy()
    if n>=166:
        mask=Image.new("L",OUTPUT)
        roi=[(384,0),(292,0),(292,75),(282,96),(282,138),(230,155),(207,172),(205,216),(384,216)]
        ImageDraw.Draw(mask).polygon([(2*x,2*y) for x,y in roi],fill=255)
        frame.paste(frames[n],(0,0),mask)
    leap=ease(.09,.9,t)
    x=mix(246,189,leap)
    foot=mix(96,167,leap)-39*math.sin(math.pi*leap)
    size=mix(.20,.85,ease(0,.80,t))
    robot_world(frame,"wave" if t>.90 else "reach",t*1.5,x,foot,size,
                angle=9*math.sin(math.pi*leap),squash=1-.10*bump(.82,.93,1.09,t))
    frame=camera(frame,211,110,354)
    if t>=1.05:speech(frame,"小电","起来，跟我把双臂打开。",top=True)
    return frame


def stretch_room(t):
    frame=studio().copy()
    copy_robot=ease(8.87,9.55,t)
    copy_human=ease(9.55,11,t)
    # Human and avatar stay on opposite sides of one fixed screen axis throughout the hold.
    if t<10.60:
        content=Image.new("RGB",(640,360),"#2a4a56")
        d=ImageDraw.Draw(content)
        for i in range(0,360,9):box(d,0,i,640,2,"#2c4e59")
    else:
        content=game_screen(max(0,t-11))
    crt_shell(frame,content)
    if t<10.95:
        home=ease(10.45,10.95,t)
        x=mix(265,270,home)
        y=mix(169,131,home)-15*math.sin(home*math.pi)
        if home<.96:
            robot_world(frame,"stretch",copy_robot,x,y,1.19*(1-.72*home),angle=-5*math.sin(math.pi*home))
    ph=t*1.7
    mood="surprise" if t<9.64 else "neutral" if t<15.4 else "grin"
    performer(frame,91,197,"stretch",ph,copy_human,.285,mood)
    if t<10.67:
        pain_marks(frame,[(79,83,-1)],.63*(1-ease(9.63,10.67,t)))
    if t<9.65:speech(frame,"小电","起来，跟我把双臂打开。")
    else:exercise_title(frame,t>=16)
    if t>=11:timer(frame,t-11)
    return frame


def relaxed_room(t):
    frame=studio().copy()
    crt_shell(frame,game_screen(5))
    elapsed=t-16.75
    if elapsed<.50:
        performer(frame,91,197,"stretch",t*1.7,1-ease(0,.50,elapsed),.285,"exhale")
    else:
        release=1-ease(.51,1.77,elapsed)
        performer(frame,91,197+2*(1-release),"relief",0,release,.285,
                  "exhale" if release>.30 else "grin")
        pain_marks(frame,[(82,122,-1)],.55*release)
    # A gentle push-in keeps the same desk and monitor visible while the expression changes.
    f=ease(.02,.83,elapsed)
    frame=camera(frame,mix(192,122,f),mix(108,95,f),mix(384,241,f))
    return frame


@lru_cache(maxsize=1)
def tapping_hand():
    arm=rig()["right-arm"]
    arm=arm.crop(arm.getbbox()).rotate(24,Image.Resampling.BICUBIC,expand=True)
    arm=arm.resize((round(arm.width*2.7),round(arm.height*2.7)),Image.Resampling.LANCZOS)
    alpha=np.asarray(arm.getchannel("A"))
    ys,xs=np.where(alpha>210);right=int(xs.max())
    y=int(np.median(ys[xs>right-5]))
    return arm,right,y


def rest_choice(t):
    p=studio().copy()
    pressed=t>=21.20
    crt_shell(p,screen_menu(pressed,selected=20.97<=t<21.20))
    if t<20.03:
        performer(p,91,199,"choose",0,ease(19.35,20.1,t)*.65,.285,"grin")
        return p if t<19.68 else speech(p,"开发者","这个 bug，等会儿修。")
    # Match cut closer to his chosen control. An orange cuff connects his finger to his decision.
    p=camera(p,267,111,236)
    arm,px,py=tapping_hand()
    approach=ease(20.03,21.20,t)
    retreat=ease(21.40,22.01,t)
    x=mix(137,414,approach)-192*retreat
    y=mix(421,229,approach)+216*retreat
    if retreat<.985:p.paste(arm,(round(x-px),round(y-py)),arm)
    if t<21.58:speech(p,"开发者","这个 bug，等会儿修。")
    return p


def film_frame(t,frames):
    if t<5.25:return workload(t,frames)
    if t<7.50:return call_from_screen(t-5.25,frames)
    if t<8.75:
        p=rising((t-7.50)*1.9/1.25,frames)
        return p
    if t<16.75:return stretch_room(t)
    if t<19.35:return relaxed_room(t)
    return rest_choice(t)


def render(source, soundtrack, encoder):
    runway=decode(source)
    output=ROOT/"cinema"; output.mkdir(exist_ok=True)
    target=output/"opening.mp4"
    from opening_mix import mix_opening
    staging=tempfile.TemporaryDirectory(prefix="desk-opening-")
    mixed=Path(staging.name)/"opening.wav"
    mix_opening(encoder,soundtrack,mixed)
    next_video=output/"opening-render.mp4"
    process=subprocess.Popen([encoder,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
            "-s","768x432","-r",str(FPS),"-i","-","-i",str(mixed),"-map","0:v:0","-map","1:a:0",
            "-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-ar","48000",
            "-ac","2","-t","22.5","-movflags","+faststart",str(next_video)],stdin=subprocess.PIPE)
    try:
        for n in range(round(22.5*FPS)):
            frame=film_frame(n/FPS,runway).resize(OUTPUT,NEAREST)
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()
        if process.wait(): raise RuntimeError("ffmpeg could not encode the intro")
    next_video.replace(target)
    staging.cleanup()
    runway[106].save(output/"opening-poster.jpg",quality=95,subsampling=0)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("--soundtrack", type=Path, default=ROOT/"audio/intro.mp3")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    opts=parser.parse_args()
    if not opts.ffmpeg:parser.error("Specify --ffmpeg or add ffmpeg to PATH")
    render(opts.source, opts.soundtrack, opts.ffmpeg)
