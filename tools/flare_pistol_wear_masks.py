"""Original synthetic wear masks in physical millimetres; no reference pixels copied."""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(sys.argv[1]) if len(sys.argv)>1 else (ROOT if Path(__file__).parent.name=="source" else ROOT/"_asset_src"/"flare_pistol_codex")
DEST=OUT/"textures"/"worn_v01"
CHECK=OUT/"checks"/"texturing_v01"
DEST.mkdir(parents=True,exist_ok=True)
guides=json.loads((CHECK/"projection_guides.json").read_text(encoding="utf-8"))


def inward(pts):
    pts=np.asarray(pts,dtype=float)
    before=pts-np.roll(pts,1,axis=0)
    after=np.roll(pts,-1,axis=0)-pts
    before/=np.linalg.norm(before,axis=1)[:,None]
    after/=np.linalg.norm(after,axis=1)[:,None]
    n0=np.column_stack((-before[:,1],before[:,0]))
    n1=np.column_stack((-after[:,1],after[:,0]))
    normal=n0+n1
    normal/=np.linalg.norm(normal,axis=1)[:,None]
    normal/=np.maximum(.35,np.sum(normal*n0,axis=1))[:,None]
    return normal


def smooth(lo,hi,x):
    t=np.clip((x-lo)/(hi-lo),0,1)
    return t*t*(3-2*t)


def contact_mask():
    size=(4096,2792)
    im=Image.new("L",size,0)
    draw=ImageDraw.Draw(im)
    rng=random.Random(80321)
    xmin,xmax,zmin,zmax=guides["extent_mm"]
    sx,sz=size[0]/(xmax-xmin),size[1]/(zmax-zmin)
    def point(x,z): return ((x-xmin)*sx,(zmax-z)*sz)
    pts=np.asarray(guides["frame_profile_v01"],dtype=float)
    normals=inward(pts)
    x,z=pts[:,0],pts[:,1]
    r=1.15+((4.6+1.4*(1-smooth(-56,-40,x)))-1.15)*(1-smooth(-18,0,x))*smooth(11,25,z)*(1-smooth(94,108,z))
    rail=pts+normals*(r*.45)[:,None]
    remaining=0
    wearing=False
    for i in range(len(rail)):
        a,b=rail[i],rail[(i+1)%len(rail)]
        if min(a[0],b[0]) > -4:
            continue
        length=np.linalg.norm(b-a)
        for t in np.arange(0,1,.16/max(length,.16)):
            remaining-=.16
            if remaining<=0:
                wearing=not wearing
                remaining=rng.uniform(.65,3.6) if wearing else rng.uniform(.5,3.8)
            if not wearing or rng.random()<.16: continue
            p=a*(1-t)+b*t
            n=normals[i]*(1-t)+normals[(i+1)%len(rail)]*t
            p+=n*rng.uniform(-.10,.10)
            width=rng.uniform(.065,.23)
            tangent=(b-a)/max(length,1e-8)
            across=np.array((-tangent[1],tangent[0]))
            span=rng.uniform(.28,.74)
            vertices=[p-tangent*span*.5-across*width*.4,
                      p+tangent*span*.30-across*width*.6,
                      p+tangent*span*.50+across*width*.25,
                      p+across*width*.55,
                      p-tangent*span*.45+across*width*.35]
            draw.polygon([point(*q) for q in vertices],fill=rng.randint(205,255))
            if rng.random()<.045:
                vertices=[p+tangent*u+across*v for u,v in [(-.12,-.10),(.33,-.14),(.24,.23),(-.19,.15)]]
                draw.polygon([point(*q) for q in vertices],fill=rng.randint(190,245))
    # Aperture edge, both sides: explicit projection guide follows its actual contour.
    pts=np.asarray(guides["guard_profile"],dtype=float)
    rail=pts-inward(pts)*.95
    for i,a in enumerate(rail):
        b=rail[(i+1)%len(rail)]
        if rng.random()<.19:continue
        draw.line([point(*a),point(*b)],fill=rng.randint(130,235),width=max(1,int(rng.uniform(.08,.20)*sx)))
    im.save(DEST/"frame_contact_guide_v01.png")


def scratches(filename,seed,count,through=False):
    size=4096
    im=Image.new("L",(size,size),0)
    draw=ImageDraw.Draw(im)
    rng=random.Random(seed)
    px=size/200. # physically 200 mm, not arbitrary normalized UV noise.
    for i in range(count):
        centre=np.array((rng.uniform(0,200),rng.uniform(0,200)))
        angle=rng.uniform(-math.pi,math.pi)
        direction=np.array((math.cos(angle),math.sin(angle)))
        normal=np.array((-direction[1],direction[0]))
        length=rng.uniform(.7,7.5) if through else rng.uniform(.4,10.0)
        width=rng.uniform(.06,.16) if through else rng.uniform(.035,.095)
        alpha=rng.randint(170,255) if through else rng.randint(65,230)
        for j in range(5):
            p=centre+direction*length*(j/5-.5)+normal*rng.uniform(-.03,.03)
            q=centre+direction*length*((j+1)/5-.5)+normal*rng.uniform(-.03,.03)
            if rng.random()<(.12 if through else .045):continue
            draw.line([tuple(p*px),tuple(q*px)],fill=alpha,width=max(1,round(width*px)))
    im.save(DEST/filename)


def fractures():
    """Short interrupted branches with rare chips, not a global crack network."""
    size=4096
    im=Image.new("L",(size,size),0)
    draw=ImageDraw.Draw(im)
    rng=random.Random(280123)
    px=size/200.
    for i in range(1050):
        p=np.array((rng.uniform(0,200),rng.uniform(0,200)))
        angle=rng.uniform(-math.pi,math.pi)
        nodes=[p.copy()]
        for j in range(rng.randint(2,6)):
            angle+=rng.uniform(-.8,.8)
            q=p+np.array((math.cos(angle),math.sin(angle)))*rng.uniform(.28,.95)
            if rng.random()>.16:
                draw.line([tuple(p*px),tuple(q*px)],fill=rng.randint(140,245),width=rng.choice((1,2,2,3)))
            p=q
            nodes.append(p.copy())
        if rng.random()<.34:
            p=nodes[rng.randrange(len(nodes))]
            q=p+np.array((math.cos(angle+1.2),math.sin(angle+1.2)))*rng.uniform(.3,1.0)
            draw.line([tuple(p*px),tuple(q*px)],fill=rng.randint(120,205),width=1)
        if rng.random()<.28:
            p=nodes[rng.randrange(len(nodes))]*px
            radii=[rng.uniform(.06,.27)*px for j in range(6)]
            poly=[(p[0]+r*math.cos(j*math.pi/3),p[1]+r*math.sin(j*math.pi/3)) for j,r in enumerate(radii)]
            draw.polygon(poly,fill=rng.randint(140,240))
    im.save(DEST/"paint_fractures_v01.png")


contact_mask()
scratches("scratches_fine_v01.png",98211,1080)
scratches("scratches_through_v01.png",12363,180,True)
fractures()
manifest=[]
for path in sorted(DEST.glob("*.png")):
    with Image.open(path) as image:
        manifest.append({"file":path.name,"size":list(image.size),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                         "kind":"original synthetic authoring mask","color_space":"Non-Color",
                         "source":"Codex seeded strokes; millimetre projection of saved model","license":"authored for owner of RING; no copied third-party pixels"})
(DEST/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print("WEAR_MASKS_READY",len(manifest),flush=True)
