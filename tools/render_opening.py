"""Edit the approved Runway performance, articulated source cutouts and the game robot.

Run: python tools/render_opening.py <downloaded ten-second Runway source.mp4> --soundtrack <intro.mp3>
Requires Pillow, NumPy, OpenCV and ffmpeg. The source Runway task is
aa849db5-701a-45b8-8c43-34a5e3e9192a. The finisher uses the game's hit and reward cues.
"""

import argparse
import math
from functools import lru_cache
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web"
WIDTH, HEIGHT, FPS = 384, 216, 24
OUTPUT = (768, 432)
INK, DARK, MINT = "#22263b", "#151829", "#aef4bd"
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


def star(d, x, y, radius, color):
    box(d, x-radius, y, radius*2+1, 1, color)
    box(d, x, y-radius, 1, radius*2+1, color)


def smooth(t):
    t = min(1, max(0, t))
    return t*t*(3-2*t)


def sprite(im, pic, center, feet, scale):
    p = pic.resize((round(pic.width*scale), round(pic.height*scale)), NEAREST)
    im.paste(p, (round(center - p.width/2), round(feet-p.height)), p)


def mix(a, b, f):
    return a + (b-a)*f


def between(a, b, f):
    return (mix(a[0],b[0],f),mix(a[1],b[1],f))


def endpoint(sx,sy,angle,length,side):
    a=math.radians(angle); return (sx+side*math.cos(a)*length,sy+math.sin(a)*length)


def arm_angles(act,f):
    phase=math.sin(2*math.pi*f)
    if act=="wings":
        v=61*(1-smooth(f*4)); return [(v,v),(v,v)]
    if act=="flap": return [(phase*34,phase*46),(phase*34,phase*46)]
    if act=="wave": return [(67,64),(-39,-127+phase*35)]
    if act=="lean": return [(42,68+phase*10),(42,68-phase*10)]
    if act=="piano":return [(69,54+phase*14),(69,54-phase*14)]
    if act=="hands_up":return [(58-94*max(0,phase),56-108*max(0,phase))]*2
    if act=="finish":return [(67,72),(-45,-70)]
    return [(63,78),(63,78)]


def robot(act,f):
    pic=Image.new("RGBA",(104,85));d=ImageDraw.Draw(pic);ox=14;oy=3
    phase=math.sin(2*math.pi*f)
    angles=arm_angles(act,f)
    if act=="finish":angles=angles[::-1]
    if act=="rescue":angles=[(20,-24),(-47,-74)]
    for i,(upper,lower) in enumerate(angles):
        side=2*i-1; a=(ox+(24 if i==0 else 54),52); b=endpoint(*a,upper,13,side); c=endpoint(*b,lower,12,side)
        path(d,[a,b,c],INK,7);path(d,[a,b],TEAL,4);path(d,[b,c],MINT,3)
        box(d,c[0]-3,c[1]-3,7,6,INK);box(d,c[0]-2,c[1]-2,5,4,"#94dfad")
    pic.alpha_composite(ROBOT.crop((78,0,156,78)),(ox,oy))
    head=ROBOT.crop((0,0,78,78));dx=round(phase*5) if act=="turn" else 0
    dy=round(max(0,phase)*5) if act=="nod" else 0
    pic.alpha_composite(head,(ox+dx,oy+dy)); return pic


def cactus(d,x,y):
    box(d,x-4,y-23,8,23,INK);box(d,x-2,y-21,4,20,"#85c195")
    path(d,[(x,y-8),(x-9,y-8),(x-9,y-16)],"#4e8277",4)
    path(d,[(x,y-14),(x+8,y-14),(x+8,y-20)],"#68a182",3)


def stage(act,phase):
    moods={"wings":1,"flap":1,"wave":0,"lean":2,"piano":3,"hands_up":1,"turn":0,"nod":3,"finish":0}
    n=moods[act]; x=n%2*WIDTH;y=n//2*HEIGHT
    im=STAGE.crop((x,y,x+WIDTH,y+HEIGHT));d=ImageDraw.Draw(im)
    beat=math.sin(2*math.pi*phase)
    if act=="wave":
        for i in range(7):
            x=round(i*68-75*phase)-24
            box(d,x,116,67,38,"#51485c");box(d,x+1,117,65,31,"#d2b8a8");box(d,x,139,67,4,"#b57375")
            for j in range(4):
                box(d,x+j*13+4,120,10,11,"#6d7884");box(d,x+j*13+5,121,8,5,SUN)
    elif act=="lean":
        for i in range(6):
            x=(i*84-round(phase*74))%420-20;y=132+i%3*23
            box(d,x,y-18,2,18,INK);poly(d,[(x+1,y-18),(x+15,y-16),(x+1,y-12)],CORAL)
    elif act=="hands_up":
        for i in range(4):cactus(d,int(400* (1-phase)+i*101)%423-18,181)
    elif act in ("turn","nod"):
        for i in range(6):
            x=37+i*9 if i<3 else 309+(i-3)*9; y=124 if act=="turn" else 118 + (i%3)*8
            box(d,x,y,8,6,INK);box(d,x+1,y+1,6,4,SUN if i<int(phase*7) else "#9b7b8f")
    elif act in ("wings","flap"):
        for side in (-1,1):
            x=192+side*154;box(d,x,136,9,38,INK)
            for i in range(6):box(d,x+2,166-i*5,5,3,MINT if i<phase*7 else "#718190")
    lift=round(14*max(0,beat)) if act=="hands_up" else round(6*max(0,-beat)) if act=="flap" else 0
    shift=round(beat*15) if act=="lean" else 0
    left=125+shift;right=261+shift;hop=0
    robot_pic=robot(act,phase)
    if act=="finish":
        contact=smooth(phase/.42)*(1-smooth((phase-.65)/.25))
        left+=31*contact;right-=29*contact;hop=50*contact
    for xx in (left,right):d.ellipse((xx-23,181,xx+23,185),fill="#575368")
    if act=="finish":
        # Bring the in-game palm precisely to the developer's leading hand.
        goalx,goaly=human_hand(left,184-lift,act,phase)
        palma=endpoint(*endpoint(38,52,-45,13,-1),-70,12,-1)
        right=mix(right,goalx-(palma[0]-52)*1.37,contact)
        robotfoot=mix(193-lift-hop,goaly-(palma[1]-85)*1.37,contact)
    else: robotfoot=193-lift-hop
    if act=="piano":
        for x0,top in ((77,115),(217,152)):
            for legx in (x0+10,x0+76):
                path(d,[(legx,top+8),(legx+4,180)],INK,3)
            box(d,x0-2,top,96,14,INK)
            for i in range(10):
                box(d,x0+i*9,top+2,8,10,SUN if i==int(phase*10)%10 else "#e7d7bc")
                if i%5 in (0,1,3):box(d,x0+i*9+6,top+1,4,6,INK)
    sprite(im,robot_pic,right,robotfoot,1.37)
    foreground=Image.new("RGBA",(WIDTH,HEIGHT))
    d=ImageDraw.Draw(foreground)
    if act=="piano":
        # The front lip and keys sit in front of the two waists, directly under the moving hands.
        for x0,top in ((77,115),(217,152)):
            box(d,x0-2,top+2,96,12,INK)
            for i in range(10):
                box(d,x0+i*9,top+2,8,9,SUN if i==int(phase*10)%10 else "#e7d7bc")
                if i%5 in (0,1,3):box(d,x0+i*9+6,top+2,4,4,INK)
    if act=="finish":
        # Energy bridges the two raised hands as the adventure is handed back to the player.
        for i in range(17):
            x=26+(43*i)%339;y=28+(31*i+round(24*phase))%103
            star(d,x,y,1+i%2,(SUN,MINT,CORAL)[i%3])
        if .40<phase<.68:
            star(d,goalx,goaly,5+round(2*math.sin(math.pi*phase)),SUN)
            for i in range(8):
                a=i*math.pi/4;r=9+round((phase-.4)*20)
                box(d,goalx+r*math.cos(a),goaly+r*math.sin(a),2,2,MINT)
    result=im.resize(OUTPUT,NEAREST)
    draw_human(result,left,184-lift,act,phase)
    fg=foreground.resize(OUTPUT,NEAREST)
    result.paste(fg,(0,0),fg)
    return result


ACTS = ["wings","flap","wave","lean","piano","hands_up","turn","nod"]


ART = Path(__file__).resolve().parent / "opening_art"
PIVOTS = ((295,205),(398,205))
ELBOWS = ((219,205),(459,207))
NECK, HIP = (350,184), (349,346)
ACTOR_SCALE = .287


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


def actor_pose(act,f):
    """All eight moves use the exact photographed performer, including his original face."""
    r=rig(); phase=math.sin(math.tau*f); torso=Image.new("RGBA",r["body"].size)
    angles=arm_angles(act,f)
    if act=="finish":angles=[angles[0],(-5,-30)]
    for i,(upper,lower) in enumerate(angles):
        sign=1-2*i
        limb=r[i,"upper"].copy()
        limb.alpha_composite(rot(r[i,"lower"],sign*(lower-upper),ELBOWS[i]))
        torso.alpha_composite(rot(limb,sign*upper,PIVOTS[i]))
    torso.alpha_composite(r["shirt"])
    head=r["head"]
    if act=="nod":
        nod=(1-math.cos(math.tau*f))/2
        # Pitch reduces the visible height of both lenses and cheeks while the collar stays fixed.
        rect=head.getbbox(); crop=head.crop(rect)
        h=round(crop.height*(1-.20*nod)); crop=crop.resize((crop.width,h),NEAREST)
        crop=rot(crop,-8*nod,(crop.width//2,h-9))
        torso.alpha_composite(crop,(rect[0]+round(5*nod),rect[3]-h+round(nod*3)))
    elif act=="turn":
        # The front-facing likeness comes from the same performance, with a slight three-quarter
        # perspective already present in the original. Reverse that perspective on the left beat.
        yaw=phase; rect=head.getbbox(); crop=head.crop(rect)
        if yaw<-.17:crop=crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        w=round(crop.width*(1-.10*abs(yaw)))
        crop=crop.resize((w,crop.height),NEAREST)
        torso.alpha_composite(crop,(round(rect[0]+(rect[2]-rect[0]-w)/2+yaw*5),rect[1]))
    else:
        torso.alpha_composite(head)
    if act=="lean":torso=rot(torso,-phase*13,HIP)
    elif act=="flap":torso=rot(torso,phase*2,HIP)
    result=r["legs"].copy()
    if act=="hands_up":
        result=Image.new("RGBA",result.size)
        spring=max(0,phase)
        for i in (0,1):
            side=2*i-1; hip=((322,344),(370,344))[i];knee=((299,473),(389,473))[i]
            leg=r[i,"thigh"].copy()
            leg.alpha_composite(rot(r[i,"calf"],-side*27*spring,knee))
            result.alpha_composite(rot(leg,side*13*spring,hip))
    result.alpha_composite(torso)
    return result


def draw_human(im,cx,feet,act,f):
    actor=actor_pose(act,f); scale=ACTOR_SCALE*2
    x=round(cx*2-349*scale);y=round(feet*2-612*scale)
    pic=actor.resize((round(actor.width*scale),round(actor.height*scale)),Image.Resampling.LANCZOS)
    im.paste(pic,(x,y),pic)


def human_hand(cx,feet,act,f):
    upper,lower=(-5,-30) if act=="finish" else arm_angles(act,f)[1]
    # Contact the knuckles, just before the original extended fingertips.
    b=endpoint(*PIVOTS[1],upper,61,1);p=endpoint(*b,lower-9,110,1)
    return (cx+(p[0]-349)*ACTOR_SCALE,feet+(p[1]-612)*ACTOR_SCALE)


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


def night(t,frames):
    if t<1.18:
        # The scope and CRT are untouched footage from the same night-shift set.
        f=smooth(t/1.18)
        return camera(frames[142+int(7*f)],mix(68,92,f),100,mix(133,194,f))
    if t<2.4:
        # Insert of the physical board, soldering station, keyboard and the programmer's hands.
        f=smooth((t-1.18)/1.22)
        return camera(frames[round(9+23*f)],mix(121,150,f),mix(163,152,f),mix(167,209,f))
    if t<5.0:
        f=(t-2.4)/2.6
        return camera(frames[min(62,round(f*62))],193,111,mix(384,352,smooth(f)))
    # At 6.8 s this shot lands on frame 106, the user's approved keyframe, at original framing.
    index=round(track([(5,63),(5.62,78),(6.2,90),(6.78,106),(7.4,117)],t))
    return frames[index].copy()


def bullet(t,frames):
    # Revisit three actual performance poses while the foreground sparks and camera orbit independently.
    i=min(2,int(t/1.5));f=(t%1.5)/1.5;drift=smooth(f)
    if i==0:
        im=frames[60].copy();cx,cy,width=mix(243,253,drift),110,mix(271,252,drift)
        anchor=(297,165)
    elif i==1:
        im=frames[106].copy();cx,cy,width=mix(150,166,drift),125,mix(299,318,drift)
        anchor=(332,187)
    else:
        im=frames[round(mix(87,132,drift))].copy();cx,cy,width=mix(269,249,drift),154,mix(244,282,drift)
        anchor=(335,186)
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx);ax,ay=anchor
    # Three low-intensity arcs orbit the lumbar point; no overlays cross the face.
    for k in range(3):
        radius=10+8*k; a=round(30+f*60+k*27)
        d.arc((ax-radius,ay-radius*.63,ax+radius,ay+radius*.63),a,a+85,
              fill=("#e4bc82","#f39777","#d17871")[k],width=1)
    for k in range(6):
        a=(k*.13+.25*t)*math.tau
        x=ax+(22+3*k)*math.cos(a);y=ay+(10+2*k)*math.sin(a)
        box(d,x,y,2,1,SUN if k%3==0 else CORAL)
    fx=fx.resize(OUTPUT,NEAREST);im.paste(fx,(0,0),fx)
    return camera(im,cx,cy,width)


def portal(t,frames):
    # The blue CRT is real, but the generated character in frames 154+ is never visible.
    n=round(track([(0,140),(.50,151),(1.65,166),(3.1,189)],t))
    clean=frames[min(n,151)].copy()
    if n>=166:
        mask=Image.new("L",OUTPUT); d=ImageDraw.Draw(mask)
        roi=[(384,0),(292,0),(292,75),(282,96),(282,138),(230,155),
             (207,172),(205,216),(384,216)]
        d.polygon([(2*x,2*y) for x,y in roi],fill=255)
        clean.paste(frames[n],(0,0),mask)
    fx=Image.new("RGBA",(384,216));d=ImageDraw.Draw(fx)
    glow=math.sin(math.pi*min(1,t/2.12))
    if .10<t<1.94:
        for k in range(3):
            rx=(8+4*k)*glow
            d.ellipse((246-rx,71-rx*.65,246+rx,71+rx*.65),outline=(SUN,"#c6eac6",MINT)[k])
    jump=smooth((t-.46)/1.5)
    px=mix(246,185,jump);foot=mix(91,164,jump)-56*math.sin(math.pi*jump)
    scale=mix(.08,.83,smooth((t-.16)/1.45))
    if t>.15:sprite(fx,robot("rescue",jump),px,foot,scale)
    if .32<t<1.85:
        for k in range(8):
            a=k*math.pi/4; rad=9+22*((t*.83+k/8)%1)
            star(d,246+rad*math.cos(a),71+.63*rad*math.sin(a),1,(MINT,SUN)[k%2])
    fg=fx.resize(OUTPUT,NEAREST);clean.paste(fg,(0,0),fg)
    return camera(clean,207+8*math.sin(math.pi*jump),110,mix(384,346,smooth(t/3.1)))


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
    if .32<t<.72:star(d,gx,gy,2,MINT)
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


def film_frame(t,runway):
    if t<7.4:return night(t,runway)
    if t<11.9:return bullet(t-7.4,runway)
    if t<15:return portal(t-11.9,runway)
    if t<16.9:return rising(t-15,runway)
    if t<29.7:
        offset=(t-16.9)/1.6
        return stage(ACTS[min(7,int(offset))],offset%1)
    return stage("finish",(t-29.7)/2.3)


def render(source, soundtrack, encoder):
    runway=decode(source)
    output=ROOT/"cinema"; output.mkdir(exist_ok=True)
    target=output/"opening.mp4"
    audio = ROOT/"audio"
    filters = (
        "[1:a]aresample=48000,atempo=0.97,volume=0.80,apad,atrim=duration=32,"
        "afade=t=in:d=0.16,afade=t=out:st=31.0:d=1.0[theme];"
        "[2:a]atrim=duration=0.44,volume=0.33,afade=t=out:st=0.26:d=0.18,adelay=30680:all=1[hit];"
        "[3:a]atrim=duration=1.04,volume=0.32,afade=t=out:st=0.57:d=0.47,adelay=30860:all=1[win];"
        "[theme][hit][win]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.89:level=0[mix]"
    )
    process=subprocess.Popen([encoder,"-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
            "-s","768x432","-r",str(FPS),"-i","-","-i",str(soundtrack),"-i",str(audio/"hit.mp3"),
            "-i",str(audio/"reward.mp3"),"-filter_complex",filters,"-map","0:v:0","-map","[mix]",
            "-c:v","libx264","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-ar","48000",
            "-ac","2","-t","32","-movflags","+faststart",str(target)],stdin=subprocess.PIPE)
    try:
        for n in range(32*FPS):
            frame=film_frame(n/FPS,runway).resize(OUTPUT,NEAREST)
            process.stdin.write(frame.tobytes())
    finally:
        process.stdin.close()
        if process.wait(): raise RuntimeError("ffmpeg could not encode the intro")
    runway[106].save(output/"opening-poster.jpg",quality=95,subsampling=0)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("--soundtrack", type=Path, default=ROOT/"audio/intro.mp3")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    opts=parser.parse_args()
    if not opts.ffmpeg:parser.error("Specify --ffmpeg or add ffmpeg to PATH")
    render(opts.source, opts.soundtrack, opts.ffmpeg)
