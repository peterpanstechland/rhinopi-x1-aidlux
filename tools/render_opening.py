"""Edit the approved Runway performance, articulated source cutouts and the game robot.

Run: python tools/render_opening.py <downloaded ten-second Runway source.mp4> --soundtrack <intro.mp3>
Requires Pillow, NumPy, OpenCV and ffmpeg. The source Runway task is
aa849db5-701a-45b8-8c43-34a5e3e9192a. The release runs 22.5 seconds.
"""

import argparse
import math
from functools import lru_cache
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web"
WIDTH, HEIGHT, FPS = 384, 216, 24
OUTPUT = (768, 432)
INK, MINT = "#22263b", "#aef4bd"
TEAL, SUN, CORAL = "#4d9797", "#ffe1a1", "#ff987f"
STAGE = Image.open(ROOT / "art/stage-plates.png").convert("RGB")
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
    angles = {
        "rescue":[(20,-24),(-47,-74)], "run":[(48,-8),(9,-53)],
        "lift":[(-38,-70),(-48,-75)], "point":[(70,55),(1,-15)],
        "wave":[(55,70),(-54,-102+phase*24)], "hold":[(67,62),(-12,-40)],
        "slip":[(-71,-100),(-45,-31)], "walk":[(47+phase*22,29),(45-phase*24,22)],
        "five":[(-32,-64),(58,43)], "strut":[(53+phase*26,20),(20-phase*30,-33)]
    }[act]
    for i,(upper,lower) in enumerate(angles):
        side=2*i-1; a=(ox+(24 if i==0 else 54),52); b=endpoint(*a,upper,13,side); c=endpoint(*b,lower,12,side)
        path(d,[a,b,c],INK,7);path(d,[a,b],TEAL,4);path(d,[b,c],MINT,3)
        box(d,c[0]-3,c[1]-3,7,6,INK);box(d,c[0]-2,c[1]-2,5,4,"#94dfad")
    body=ROBOT.crop((78,0,156,78))
    if act in ("walk","run","strut","lift"):
        pic.alpha_composite(body.crop((0,0,78,64)),(ox,oy))
        stride=phase if act!="lift" else 1
        for i,(x0,x1) in enumerate(((20,39),(39,58))):
            ankle=body.crop((x0,63,x1,74))
            turn=(1-2*i)*stride
            ankle=ankle.rotate(turn*19,NEAREST,center=(ankle.width//2,1))
            pic.alpha_composite(ankle,(ox+x0+round(3*turn),oy+63-round(max(0,turn)*3)))
    else:
        pic.alpha_composite(body,(ox,oy))
    head=ROBOT.crop((0,0,78,78));dx=-2 if act in ("five","hold","slip") else 1
    dy=round(abs(phase)*2) if act in ("walk","strut","run") else 1
    pic.alpha_composite(head,(ox+dx,oy+dy)); return pic


def cactus(d,x,y):
    box(d,x-4,y-23,8,23,INK);box(d,x-2,y-21,4,20,"#85c195")
    path(d,[(x,y-8),(x-9,y-8),(x-9,y-16)],"#4e8277",4)
    path(d,[(x,y-14),(x+8,y-14),(x+8,y-20)],"#68a182",3)


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
    if kind=="reach":
        tilt=-13;head=7;arms=((75,45),(6,-18-38*weight))
        thighs=(-13,16);knees=(-26,22)
    elif kind=="wave":
        tilt=-4+3*cosine;head=7+4*sine
        arms=((76+8*cosine,58),(24-61*weight,-15-84*weight+21*sine*weight))
        thighs=(3,1);knees=(3,-5+4*sine)
    else:
        tilt=-8*weight;head=3+7*(1-weight)
        arms=((77-55*weight,68+66*weight),(76-8*weight,82-25*weight))
        thighs=(3-6*weight,3+3*weight);knees=(4+8*weight,-7-4*weight)
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


@lru_cache(maxsize=4)
def drawing(name):
    src=Image.open(ART/f"developer-{name}.png").convert("RGBA")
    padded=Image.new("RGBA",(src.width+32,src.height+28))
    padded.alpha_composite(src,(16,14))
    yy,xx=np.indices((padded.height,padded.width),dtype=np.float32)
    return np.array(padded),xx,yy,src.size


def action_drawing(im,pose,x,floor,size,phase,strength=1):
    """The four poses use different silhouettes. Animate foot, head and hand follow-through
    inside each exposure, pinning the shirt and hips before projecting the drawing on its arc."""
    rgba,xx,yy,(w,h)=drawing(pose)
    stride=math.sin(phase)
    down=np.clip((yy-14-h*.48)/(h*.47),0,1)
    wings=np.clip((np.abs(xx-16-w*.54)-w*.15)/(w*.38),0,1)*(1-down)
    side=np.tanh((xx-16-w*.48)/12)
    flex=1 if pose=="run" else .40 if pose=="leap" else .56
    dx=(10*down*side+3*wings*side)*stride*flex*strength
    dy=(6*down*np.maximum(0,side*stride)+2*wings*math.cos(phase))*flex*strength
    warped=Image.fromarray(cv2.remap(rgba,xx-dx,yy+dy,cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT))
    factor=2*size
    pic=warped.resize((round(warped.width*factor),round(warped.height*factor)),Image.Resampling.LANCZOS)
    origin=(round(2*x-(16+w*.53)*factor),round(2*floor-(14+h)*factor))
    im.paste(pic,origin,pic)
    palm={"run":(162,56),"crouch":(152,117),"leap":(169,9),"land":(165,88)}[pose]
    return x+(palm[0]-w*.53)*size,floor+(palm[1]-h)*size


def robot_world(im,kind,phase,x,feet,scale,angle=0,squash=1):
    pic=robot(kind,phase).rotate(angle,NEAREST,center=(52,59))
    pic=pic.resize((round(pic.width*2*scale/squash),round(pic.height*2*scale*squash)),NEAREST)
    im.paste(pic,(round(2*x-pic.width/2),round(2*feet-pic.height)),pic)


def key_sprite():
    p=Image.new("RGBA",(32,25));d=ImageDraw.Draw(p)
    poly(d,[(1,8),(6,2),(26,1),(31,7),(30,19),(25,23),(4,23),(1,19)],"#35232c")
    poly(d,[(3,9),(8,4),(25,3),(28,7),(26,16),(5,17)],"#ffc16f")
    poly(d,[(4,17),(26,16),(28,8),(28,18),(24,21),(5,21)],"#ac603b")
    path(d,[(6,8),(10,5),(23,5)],"#ffe4aa")
    path(d,[(22,7),(21,12),(11,12)],"#50363d",2)
    poly(d,[(9,12),(15,8),(14,15)],"#50363d")
    return p


KEY=key_sprite()


def enter_key(im,x,y,scale=1,angle=0):
    pic=KEY.rotate(angle,NEAREST,expand=True)
    pic=pic.resize((max(1,round(pic.width*scale*2)),max(1,round(pic.height*scale*2))),NEAREST)
    im.paste(pic,(round(x*2-pic.width/2),round(y*2-pic.height/2)),pic)


# A six-pixel terminal font for the three diegetic messages on the CRT.
GLYPHS={
    "A":("0110","1001","1001","1111","1001","1001"),
    "B":("1110","1001","1110","1001","1001","1110"),
    "D":("1110","1001","1001","1001","1001","1110"),
    "G":("0111","1000","1011","1001","1001","0111"),
    "I":("111","010","010","010","010","111"),
    "K":("1001","1010","1100","1100","1010","1001"),
    "L":("1000","1000","1000","1000","1000","1111"),
    "O":("0110","1001","1001","1001","1001","0110"),
    "R":("1110","1001","1110","1100","1010","1001"),
    "U":("1001","1001","1001","1001","1001","0110"),
    "1":("010","110","010","010","010","111")," ":("00",)*6}


def terminal_text(d,cx,cy,label,col):
    widths=[len(GLYPHS[c][0])+1 for c in label];x=round(cx-sum(widths)/2)
    for c,w in zip(label,widths):
        for j,line in enumerate(GLYPHS[c]):
            for i,pixel in enumerate(line):
                if pixel=="1":d.point((x+i,cy+j),fill=col)
        x+=w


def display(frames,message):
    base=frames[148].copy();fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    poly(d,[(195,36),(302,35),(304,41),(304,101),(298,108),(196,108),(191,104),(191,44)],"#233e4c")
    for y in range(40,105,4):box(d,194,y,105,1,"#284753")
    col="#faad91" if message=="1 BUG" else "#d2edb6"
    box(d,203,52,9,2,"#577977");box(d,203,57,22,1,"#78938a")
    terminal_text(d,251,69,message,col)
    if message!="BRB":box(d,246,82,9,1,col)
    fg=fx.resize(OUTPUT,NEAREST);base.paste(fg,(0,0),fg)
    # Reconstruct the covered right corner from the unobstructed left CRT frame. The
    # display remains legible, and none of the performer's earlier silhouette is retained.
    reflected=base.crop((164*2,0,219*2,138*2)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    base.paste(reflected,(279*2,0))
    return base


def desk_close(frames, cap=True, hand_x=None, hand_y=131, bot_hand=0):
    # Cut back to precisely the same desk and slot when the reflex to press Return returns.
    base=camera(frames[151],141,151,128)
    cx,cy=214,150
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    poly(d,[(cx-21,cy-5),(cx-14,cy-14),(cx+20,cy-14),(cx+23,cy+4),
            (cx+17,cy+13),(cx-19,cy+13)],"#1d2937")
    box(d,cx-8,cy-7,14,11,"#5d6769");box(d,cx-4,cy-5,7,5,"#b5ac97")
    fg=fx.resize(OUTPUT,NEAREST);base.paste(fg,(0,0),fg)
    if cap:enter_key(base,cx,cy-2,1.39)
    if bot_hand:
        extension=ease(0,1,bot_hand)
        bx=mix(-49,153,extension)
        robot_world(base,"five",.5,bx,202,.82,angle=-8*extension)
        x=bx+61;y=147
        fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
        path(d,[(bx+17,177),(bx+34,171),(x-10,y+7)],INK,9)
        path(d,[(bx+17,176),(bx+34,170),(x-10,y+6)],"#509a91",5)
        box(d,bx+34,165,4,6,"#284c55")
        # Open game-robot palm, distinct fingers, lit mint silicone pads.
        poly(d,[(x-15,y+8),(x-17,y+2),(x-12,y-5),(x-7,y-4),(x-4,y-8),(x+1,y-6),
                (x+5,y-9),(x+10,y-6),(x+13,y-6),(x+16,y-2),(x+11,y+7),(x+3,y+11),(x-7,y+12)],"#1b363f")
        poly(d,[(x-13,y+4),(x-9,y-2),(x-6,y+1),(x-2,y-4),(x+1,y-2),(x+6,y-5),
                (x+9,y-2),(x+12,y-3),(x+12,y),(x+6,y+6),(x-5,y+9)],"#8dd2aa")
        path(d,[(x-3,y+4),(x+3,y+4),(x+6,y+1)],"#b5f1bc",2)
        fg=fx.resize(OUTPUT,NEAREST);base.paste(fg,(0,0),fg)
    if hand_x is not None:
        # Bright arm and skin both belong to the original performer. Its fingertips lead the cut.
        arm=rig()["right-arm"];arm=arm.crop(arm.getbbox()).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        arm=arm.resize((round(arm.width*1.94),round(arm.height*1.70)),Image.Resampling.LANCZOS)
        base.paste(arm,(round(hand_x*2),round(hand_y*2-arm.height*.44)),arm)
    return base


def workload(t,frames):
    if t<.55:
        return desk_close(frames,hand_x=mix(290,211,ease(.08,.49,t)),hand_y=142+4*ease(.4,.52,t))
    if t<.91:return camera(frames[13+round((t-.55)*40)],127,178,102)
    if t<1.19:return camera(frames[28+round((t-.91)*50)],177,145,161)
    if t<1.40:return camera(frames[146],72,96,128)
    if t<1.59:return camera(frames[39],128,178,81)
    if t<1.78:return desk_close(frames,hand_x=209,hand_y=147)
    if t<2.25:return camera(display(frames,"BUILD OK"),250,71,166)
    if t<2.55:return camera(frames[round(mix(49,61,(t-2.25)/.30))],224,112,311)
    if t<4.0:
        n=round(track([(2.55,63),(2.92,78),(3.18,91),(3.50,106),(4,106)],t))
        return frames[n].copy()
    if t<4.20:return camera(display(frames,"1 BUG"),247,72,157)
    return frames[round(mix(107,122,ease(4.82,5.15,t)))].copy()


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


def portal(t,frames):
    # The blue CRT is real, but the generated character in frames 154+ is never visible.
    n=round(track([(0,140),(.38,151),(2.57,166),(3.28,189)],t))
    clean=frames[min(n,151)].copy()
    if n>=166:
        mask=Image.new("L",OUTPUT); d=ImageDraw.Draw(mask)
        roi=[(384,0),(292,0),(292,75),(282,96),(282,138),(230,155),
             (207,172),(205,216),(384,216)]
        d.polygon([(2*x,2*y) for x,y in roi],fill=255)
        clean.paste(frames[n],(0,0),mask)
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    glow=math.sin(math.pi*min(1,t/.8))
    if .10<t<.8:
        for k in range(2):
            rx=(8+4*k)*glow
            d.ellipse((246-rx,71-rx*.65,246+rx,71+rx*.65),outline=(SUN,"#c6eac6",MINT)[k])
    jump=ease(.18,.75,t);tap=bump(.86,1.02,1.15,t)+bump(1.23,1.35,1.47,t)
    pry=bump(1.69,2.07,2.26,t);dash=ease(2.66,3.29,t)
    px=mix(246,181,jump)-8*pry-34*dash
    foot=mix(91,169,jump)-41*math.sin(math.pi*jump)+3*tap-8*pry
    scale=mix(.09,.73,ease(.08,.70,t))
    fg=fx.resize(OUTPUT,NEAREST);clean.paste(fg,(0,0),fg)
    if t>.09:
        stance="run" if dash>.04 else "lift" if t>2.07 else "point"
        robot_world(clean,stance,t*4,px,foot,scale,angle=-6*pry+3*tap+9*dash,
                    squash=1-.09*bump(.68,.76,.84,t)-.07*tap)
    if t<2.07:
        enter_key(clean,206,163-2*pry,.60,7*pry)
    else:
        up=ease(2.07,2.27,t)
        enter_key(clean,mix(206,px+16,up),mix(160,foot-48,up),.60,11*up)
    return camera(clean,210+5*jump,113,mix(384,318,ease(.62,2.45,t)))


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
    fx=Image.new("RGBA",(384,216)); d=ImageDraw.Draw(fx)
    sprite(fx,robot("rescue",t/1.9),bx,botfoot,s)
    fg=fx.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    enter_key(frame,bx+9,botfoot-21,.34,5)
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


def station(t):
    im=STAGE.crop((0,0,384,216));d=ImageDraw.Draw(im)
    for x in (9,344):
        box(d,x,34,5,123,"#585268");box(d,x+1,34,1,119,"#a3919e")
    box(d,0,29,384,5,"#4f4c64");box(d,0,34,384,2,"#b9a19d")
    depart=ease(.72,3.0,t)
    carriage=94+116*depart
    for j in range(-3,3):coach_body(d,round(carriage+j*177),42)
    # The robot has a seat in the departing car. Its partner stays on the platform.
    frame=im.resize(OUTPUT,NEAREST);botx=carriage+85
    wave=ease(.65,1.18,t)
    throw=ease(1.86,2.15,t)
    robot_world(frame,"slip" if t>1.88 else "wave" if wave>.1 else "hold",t*3,
                botx,108, .55,angle=3*math.sin(t*5)+9*bump(1.84,2.05,2.42,t))
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    box(d,carriage+60,102,48,5,"#a78c81");box(d,carriage+59,105,49,2,"#d9b7a0")
    box(d,0,142,384,4,"#463f51");box(d,0,147,384,69,"#917e86");box(d,0,148,384,2,"#dfbf96")
    for j in range(34):box(d,j*13-4,157,9,2,"#e5c17e")
    for j in range(12):path(d,[(j*40,162),(j*40-22,216)],"#796b79")
    x=mix(71,123,ease(.16,2.8,t));floor=191-2*abs(math.sin(t*7))*(1-wave)
    d.ellipse((x-18,189,x+19,193),fill="#6b6272")
    fg=fx.resize(OUTPUT,NEAREST);frame.paste(fg,(0,0),fg)
    kind="wave" if t<2.34 else "run"
    if kind=="run":action_drawing(frame,"run",x,floor,.76,t*12)
    else:performer(frame,x,floor,kind,t*5,wave,.265)
    # The head starts tracking first. Once the forearm comes up the shoulder can relax.
    if t<1.07:pain_marks(frame,[(x+16,floor-104,1)],1-ease(.38,1.07,t))
    if not throw:
        enter_key(frame,botx+18,79+math.sin(t*9)*3,.78,9*math.sin(t*8))
    else:
        arc=(t-1.86)/1.14
        x0=94+116*ease(.72,3,1.86)+103
        enter_key(frame,mix(x0,371,arc),78-41*math.sin(arc*math.pi)-10*arc,.78,10+56*arc)
    return frame


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


def desert(t):
    camera_move=round(67*ease(0,3.8,t))
    im=desert_plate().crop((camera_move,0,camera_move+384,216));d=ImageDraw.Draw(im)
    for j in range(5):
        cactus(d,j*119+8-round(camera_move*.57),154+j%3*4)
    # The near cactus crosses between the two take-off points, against a fixed horizon.
    obstacle=232-72*ease(.3,3.6,t)
    d.ellipse((obstacle-16,181,obstacle+22,185),fill="#bc8c77")
    cactus(d,obstacle,183);cactus(d,obstacle+11,182)
    x=73+171*ease(.02,3.68,t)
    foot=187; air=max(0,min(1,(t-1.82)/1.14))
    arc=math.sin(math.pi*air)
    bob=(1-ease(1.42,1.78,t))*3*abs(math.sin(t*12))
    floor=foot-47*arc-bob
    d.ellipse((x-(19-6*arc),foot,x+(19-6*arc),foot+4),fill="#aa8176")
    botx=146+199*ease(0,3.70,t); botair=max(0,min(1,(t-.78)/.94))
    bfoot=182-38*math.sin(math.pi*botair)-4*abs(math.sin(t*9))
    d.ellipse((botx-11,179,botx+12,182),fill="#b28377")
    frame=im.resize(OUTPUT,NEAREST)
    if t>=3.14:
        # Hold the return to comfort for the audible exhale. The left hand visibly lets go
        # of the lumbar area; the low shoulder and open chest finish the movement.
        f=ease(3.14,3.77,t)
        frame=desert_plate().crop((101,16,407,188)).resize(OUTPUT,NEAREST)
        performer(frame,190,272+6*f,"relief",0,1-f,.45,"exhale" if f<.70 else "grin")
        pain_marks(frame,[(176,148,-1)],.85*(1-f))
        robot_world(frame,"hold",t,308,201,.84,angle=-5)
        enter_key(frame,230+7*f,158+8*f,.81,10-8*f)
        return frame
    robot_world(frame,"lift" if 0<botair<1 else "run",t*8,botx,bfoot,.58,
                angle=-12*math.sin(math.pi*botair)+3*math.sin(t*9))
    pose="run" if t<1.52 else "crouch" if t<1.84 else "leap" if t<2.91 else "land"
    hx_attached,hy_attached=action_drawing(frame,pose,x,floor,.70,t*12, .65 if pose=="leap" else 1)
    if .0<t<1.47:pain_marks(frame,[(x-11,floor-61,-1)],.60)
    if t>2.86:pain_marks(frame,[(x-10,floor-59,-1)],.65*(1-ease(2.91,3.52,t)))
    if t<2.40:
        hx=track([(0,275),(.9,269),(1.50,244),(2.04,245),(2.4,hx_attached)],t)
        hy=track([(0,38),(.7,74),(1.30,104),(1.6,94),(2.0,70),(2.4,hy_attached-1)],t)
        enter_key(frame,hx,hy,.84,mix(45,-11,ease(0,2.4,t)))
    else:
        enter_key(frame,hx_attached+3,hy_attached-2,.82,-11+12*ease(2.4,3.4,t))
    return frame


def returned(t,frames):
    if t<.58:
        frame=desk_close(frames,cap=False)
        f=ease(0,.41,t);enter_key(frame,214,104+43*f,.80+.59*f,18*(1-f))
        return frame
    if t<1.41:return camera(display(frames,"BUILD OK"),249,72,174)
    return camera(display(frames,"1 BUG"),249,72,174)


def punchline(t,frames):
    # Reuse the opening camera. The viewer knows exactly where the finger expects the key.
    slide=ease(.58,.94,t); f=ease(.03,.73,t)
    hover=bump(.71,1.05,1.40,t)
    hit=ease(1.71,2.28,t);recoil=bump(2.28,2.38,2.52,t)
    x=mix(282,224,f)-6*hit+5*recoil
    y=112+15*f-5*hover+21*hit-8*recoil
    frame=desk_close(frames,cap=False,bot_hand=slide,hand_x=None)
    if slide<1:enter_key(frame,214+71*slide,148-18*math.sin(math.pi*slide),1.39,-14*slide)
    arm=rig()["right-arm"];arm=arm.crop(arm.getbbox()).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    arm=arm.resize((round(arm.width*1.94),round(arm.height*1.70)),Image.Resampling.LANCZOS)
    frame.paste(arm,(round(x*2),round(y*2-arm.height*.44)),arm)
    return frame


def exhale(t,frames):
    plate=camera(frames[0],90,50,178).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    f=ease(0,.82,t)
    performer(plate,170,361+5*f,"relief",0,.18*(1-f),.63,"grin" if t>.21 else "exhale")
    robot_world(plate,"wave",t*.5,296,190,.83,angle=-9+4*f)
    return plate


def reaction(frames,mood,t):
    plate=camera(frames[0],90,50,178).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if mood=="wince":
        performer(plate,186,277,"relief",0,1,.48,"wince")
        pain_marks(plate,[(160,73,-1),(161,130,-1)],.82+.18*math.cos(15*t))
    else:
        x=mix(181,190,ease(0,.42,t))
        performer(plate,x,324,"reach",0,.5,.55,"surprise")
        robot_world(plate,"run",t*12,306+27*ease(0,.42,t),193,.67,angle=9)
        enter_key(plate,326+27*ease(0,.42,t),157,.70,13)
    return plate


def empty_bench(frames):
    # The genuine CRT casing is symmetrical. Rebuild only its right lip from the clean left
    # edge, then leave the camera above the old foreground performer and his chair.
    clean=display(frames,"BRB")
    view=camera(clean,248,79,146)
    # The cap is left upside down on the lower bezel, clear of the terminal message.
    d=ImageDraw.Draw(view);d.ellipse((224,406,282,414),fill="#574d57")
    enter_key(view,126,197,.85,166)
    return view


def film_frame(t,runway):
    if t<5.15:
        if 4.20<=t<4.82:
            if t>=4.49:return reaction(runway,"wince",t-4.49)
            amount=bump(4.2,4.41,4.82,t)
            frame=tense_back(runway[106],amount)
            frame=pain_marks(frame,[(204,86,-1),(326,177,1)],.52+.48*amount)
            return camera(frame,mix(182,165,amount),124,mix(377,321,amount))
        return workload(t,runway)
    if t<8.43:
        if t>=7.95:return reaction(runway,"surprise",t-7.95)
        return portal(t-5.15,runway)
    if t<9.65:return rising((t-8.43)*1.9/1.22,runway)
    if t<12.65:return station(t-9.65)
    if t<16.45:return desert(t-12.65)
    if t<18.30:return returned(t-16.45,runway)
    if t<20.82:return punchline(t-18.30,runway)
    if t<22.0:return exhale(t-20.82,runway)
    return empty_bench(runway)


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
