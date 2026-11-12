"""Articulated pixel artwork for Xiaodian, shared by the opening and the game.

Run this module to rebuild the web sprite sheets and the lobby portrait.
"""

import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw


ART = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web/art"
INK, DEEP, DARK = "#42142b", "#395c51", "#609575"
TEAL, JADE = "#83ad79", "#b5ce8b"
NEAREST = Image.Resampling.NEAREST
CELL = 48


def polygon(draw, points, color):
    draw.polygon([(round(x), round(y)) for x, y in points], fill=color)


def link(draw, start, end, width, color):
    draw.line([tuple(map(round, point)) for point in (start, end)], fill=color, width=width)


def stamp(image, part, x, y):
    image.alpha_composite(part, (round(x), round(y)))


@lru_cache(maxsize=1)
def reference_parts():
    source=Path(__file__).resolve().parent / "opening_art/arcade-partner.png"
    with Image.open(source) as atlas:
        return tuple(atlas.crop((i*CELL,0,(i+1)*CELL,CELL)).convert("RGBA") for i in range(4))


@lru_cache(maxsize=4)
def head(profile, blink=False):
    """The transmitter, vent slots and both eyes are painted in the approved cast drawing."""
    face=reference_parts()[0].copy()
    if blink:
        # The eyes form two separate ivory islands in the dark screen.
        d=ImageDraw.Draw(face)
        for island in (
            [(9,29),(11,24),(14,22),(18,23),(20,25),(19,28),(17,33),(15,35),(10,35),(9,34)],
            [(21,32),(23,26),(27,24),(30,25),(32,27),(32,31),(30,35),(28,38),(23,39),(21,37)],
        ):
            d.polygon(island,fill="#133323")
        for x,y in ((14,30),(26,32)):
            d.line([(x-3,y+1),(x-2,y-1),(x,y-2),(x+2,y-2),(x+3,y-1)],fill="#ffefaa",width=2)
    if not profile:
        return face
    narrow=face.transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((42,46),NEAREST)
    pic=Image.new("RGBA",(CELL,CELL))
    stamp(pic,narrow,5,2)
    return pic


@lru_cache(maxsize=2)
def torso(profile):
    body=reference_parts()[1]
    return body.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if profile else body


def boot(image, x, ground, near):
    shoe=reference_parts()[2]
    if not near:
        shoe=shoe.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    shoe=shoe.crop(shoe.getbbox())
    stamp(image,shoe,x-shoe.width//2,ground+1-shoe.height)


def leg(image,hip,knee,foot,near):
    d=ImageDraw.Draw(image)
    ankle=(foot[0],foot[1]-5)
    link(d,hip,knee,8,INK); link(d,knee,ankle,7,INK)
    link(d,hip,knee,5,TEAL if near else DARK)
    link(d,knee,ankle,4,DARK if near else DEEP)
    x,y=map(round,knee)
    d.rounded_rectangle((x-3,y-2,x+3,y+2),radius=2,fill=JADE if near else TEAL)
    boot(image,*foot,near)


def arm(image,chain,near=True):
    d=ImageDraw.Draw(image)
    a,b,h=chain
    link(d,a,b,7,INK); link(d,b,h,6,INK)
    link(d,a,b,4,TEAL if near else DARK)
    link(d,b,h,3,JADE if near else TEAL)
    glove=reference_parts()[3].crop(reference_parts()[3].getbbox())
    if near: glove=glove.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    stamp(image,glove,h[0]-glove.width//2,h[1]-glove.height//2)


def scarf(d,x,y,flutter,side=-1):
    def at(points):
        return [(x+side*dx,y+dy) for dx,dy in points]
    polygon(d,at([(0,0),(5,1),(13,-2+flutter),(19,-3+flutter),(23,-1+flutter),
                  (20,2+flutter),(21,5+flutter),(14,4+flutter),(9,6),(4,5),
                  (12,6+flutter),(15,9+flutter),(10,10+flutter),(7,12+flutter),
                  (2,8),(-2,5)]),INK)
    polygon(d,at([(1,2),(6,2),(14,-1+flutter),(21,-1+flutter),
                  (18,2+flutter),(19,3+flutter),(14,2+flutter),(8,5),(2,4)]),"#f05325")
    polygon(d,at([(1,5),(5,5),(11,7+flutter),(13,9+flutter),
                  (8,9+flutter),(7,10+flutter),(3,8)]),"#ca3823")

def two_angles(x,y,upper,lower,side):
    def point(p,angle,length):
        a=math.radians(angle)
        return p[0]+side*length*math.cos(a),p[1]+length*math.sin(a)
    elbow=point((x,y),upper,12)
    return (x,y),elbow,point(elbow,lower,12)


def robot(act,f,bank=0):
    """Return a 104x85 pose. The board stays under the boots through each recoil."""
    pic=Image.new("RGBA",(104,85));d=ImageDraw.Draw(pic)
    wave=math.sin(math.tau*f)
    if act in ("flight","ski"):
        push=(1+wave)*.5
        edge=max(-1,min(1,bank/13))
        hip=(48+3*edge,63+5*push)
        neck=(hip[0]+13,hip[1]-15)
        back=(32,83);front=(64,81)
        leg(pic,(hip[0]-5,hip[1]),(35-4*push,67+3*push),back,False)
        leg(pic,(hip[0]+3,hip[1]),(65+3*push,66+4*push),front,True)
        flutter=round(3*wave-2)
        scarf(d,neck[0]-5,neck[1]-3,flutter)
        back_arm=((hip[0]+3,hip[1]-11),(40,hip[1]-10+3*wave),(27,hip[1]-13+7*wave))
        fore_arm=((hip[0]+15,hip[1]-14),(67+push,hip[1]-8),(76+push,hip[1]-13-6*wave))
        arm(pic,back_arm,False)
        stamp(pic,torso(True),hip[0]-20,hip[1]-26)
        stamp(pic,head(True),neck[0]-22,neck[1]-43)
        arm(pic,fore_arm)
        return pic
    land=max(0,min(1,f)) if act=="land" else 0
    dip=max(0,min(1,f)) if act=="nod" else 0
    yaw=max(-1,min(1,f)) if act=="look" else 0
    hip=(52,65+round(2*dip+2*land))
    neck=(52+round(2*yaw),hip[1]-23)
    feet=((41,83),(63,83))
    if act=="vault":
        hip=(52,59);neck=(54,38);feet=((34,74),(65,68))
        knees=((34,61),(69,54))
    else:
        knees=((41,73+land),(61,72+land))
    for i in range(2):
        leg(pic,(hip[0]+(2*i-1)*6,hip[1]),knees[i],feet[i],bool(i))
    phases={"wave":((58,77),(-52,-101+wave*24)),
            "reach":((20,-30),(-32,-64)), "vault":((-24,-52),(-52,-80)),
            "rest":((56,80),(59,74)), "look":((54,78),(58,76)),
            "nod":((53,80),(61,62))}
    if act=="stretch":
        lift=max(0,min(1,f))
        angles=((64*(1-lift),80*(1-lift)),)*2
    else: angles=phases.get(act,phases["rest"])
    arms=[two_angles(hip[0]+(2*i-1)*11,hip[1]-17,*angles[i],2*i-1) for i in range(2)]
    arm(pic,arms[0],False)
    scarf(d,neck[0]+9,neck[1]+4,round(wave) if act in ("wave","reach") else 0,side=1)
    stamp(pic,torso(False),hip[0]-23,hip[1]-27)
    blink=act=="wave" and .74<f%2.5<.83
    head_pic=head(abs(yaw)>.42,blink)
    if yaw<-.42:head_pic=head_pic.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if dip:
        head_pic=head_pic.resize((CELL,round(CELL*(1-.15*dip))),NEAREST)
    stamp(pic,head_pic,neck[0]-24+round(yaw*4),neck[1]-42+round(6*dip))
    arm(pic,arms[1])
    return pic


def robot_world(im,kind,phase,x,feet,scale,angle=0,squash=1):
    pic=robot(kind,phase,angle)
    if angle and kind not in ("ski","flight"):
        pic=pic.rotate(angle,NEAREST,center=(52,75))
    pic=pic.resize((round(pic.width*2*scale/squash), round(pic.height*2*scale*squash)),NEAREST)
    im.paste(pic,(round(2*x-pic.width/2),round(2*feet-pic.height)),pic)


def bake():
    parts=Image.new("RGBA",(8*CELL,CELL))
    for i,part in enumerate((head(False),head(True),torso(False),torso(True),
                             reference_parts()[2],reference_parts()[3],head(False,True),head(True,True))):
        stamp(parts,part,i*CELL,0)
    parts.save(ART/"partner-parts.png",optimize=True)
    # The board compositor expects 78-pixel cells, with its neck at (38,48).
    board=Image.new("RGBA",(156,78))
    stamp(board,head(False),14,2)
    body=Image.new("RGBA",(78,78));d=ImageDraw.Draw(body)
    leg(body,(33,57),(28,62),(26,70),False)
    leg(body,(43,57),(46,62),(50,70),True)
    scarf(d,48,45,1,side=1);stamp(body,torso(False),15,34)
    stamp(board,body,78,0);board.save(ART/"stage-player.png",optimize=True)
    portrait=robot("rest",0)
    portrait.crop(portrait.getbbox()).save(ART/"bot.png",optimize=True)


if __name__ == "__main__":
    bake()
