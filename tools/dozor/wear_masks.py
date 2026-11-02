"""Geometry-local contacts × licensed ambientCG patterns, in the unchanged PainterUV.

Physical contact assumptions are explicit, not derived from the unfinished pistol pose.
No Veras/AR15 wear masks or hand contacts are reused.
"""
import pathlib,json,hashlib,shutil
import numpy as np
from PIL import Image,ImageFilter
from scipy.ndimage import maximum_filter
WORK=pathlib.Path(__file__).resolve().parents[2]/'_asset_src/dozor/wear'
LIB=pathlib.Path('E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures/ambientCG')
SOURCES={'prints':('Fingerprints002','Opacity'),'scratches':('Scratches002','Opacity'),
         'dust':('SurfaceImperfections007','Opacity')}
manifest=[];patterns={}
for name,(asset,channel) in SOURCES.items():
    src=next((LIB/asset).glob('*_2K-PNG_'+channel+'.png'))
    dest=WORK/'sources'/src.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    im=Image.open(src).convert('L');a=np.asarray(im,dtype=np.float32)/255
    if name=='prints':
        # Isolate a partial print, keeping the actual library ridge pattern.
        im=im.crop((30,990,390,1430));a=np.asarray(im,dtype=np.float32)/255
        a=np.clip((a-.12)/.62,0,1)
    elif name=='scratches':a=np.clip((a-.42)/.55,0,1)
    else:a=np.clip((a-.18)/.70,0,1)
    patterns[name]=a
    manifest.append({'asset':asset,'url':'https://ambientcg.com/view?id='+asset,
      'license':'CC0 1.0','license_url':'https://docs.ambientcg.com/license/',
      'original':str(dest),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
      'provenance':'library pattern; not claimed as photographed/scanned',
      'transform':'grayscale, levels; partial print crop (30,990,390,1430)' if name=='prints' else 'grayscale, levels'})

def sample(name,u,v,tile=True):
    a=patterns[name];h,w=a.shape
    if tile:u=u%1;v=v%1
    xx=np.clip(u*(w-1),0,w-1);yy=np.clip((1-v)*(h-1),0,h-1)
    x=xx.astype(int);y=yy.astype(int);x1=np.minimum(x+1,w-1);y1=np.minimum(y+1,h-1)
    dx=xx-x;dy=yy-y
    r=(a[y,x]*(1-dx)+a[y,x1]*dx)*(1-dy)+(a[y1,x]*(1-dx)+a[y1,x1]*dx)*dy
    return r if tile else r*((u>=0)&(u<=1)&(v>=0)&(v<=1))

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def window(a,b,x,edge=2):return smooth(a,a+edge,x)*(1-smooth(b-edge,b,x))
def delta(a,b):return (a-b+np.pi)%(2*np.pi)-np.pi

def raster(key,desc):
    size=desc['size'];pos=np.zeros((size,size,3),np.float32);ids=np.full((size,size),-1,np.int16)
    data=np.load(WORK/(key+'_triangles.npz'))
    for i,name in enumerate(desc['parts']):
        pp=data[f'p{i}'];uu=data[f'u{i}']*size-.5
        for p,t in zip(pp,uu):
            xmin=max(int(np.ceil(t[:,0].min())),0);xmax=min(int(np.floor(t[:,0].max())),size-1)
            ymin=max(int(np.ceil(t[:,1].min())),0);ymax=min(int(np.floor(t[:,1].max())),size-1)
            if xmin>xmax or ymin>ymax:continue
            d=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(d)<1e-10:continue
            y,x=np.mgrid[ymin:ymax+1,xmin:xmax+1]
            a=((t[1,1]-t[2,1])*(x-t[2,0])+(t[2,0]-t[1,0])*(y-t[2,1]))/d
            b=((t[2,1]-t[0,1])*(x-t[2,0])+(t[0,0]-t[2,0])*(y-t[2,1]))/d
            c=1-a-b;valid=(a>=-1e-5)&(b>=-1e-5)&(c>=-1e-5)
            yy=y[valid];xx=x[valid]
            pos[yy,xx]=a[valid,None]*p[0]+b[valid,None]*p[1]+c[valid,None]*p[2]
            ids[yy,xx]=i
        if i%15==0:print('raster',key,i,name,flush=True)
    ys,xs=np.nonzero(ids>=0)
    np.savez_compressed(WORK/(key+'_texels.npz'),ys=ys,xs=xs,pos=pos[ys,xs],obj=ids[ys,xs],size=size)
    return ys,xs,pos[ys,xs]*1000,ids[ys,xs]

reports={}
for key,desc in json.loads((WORK/'parts.json').read_text(encoding='utf-8')).items():
    cache=WORK/(key+'_texels.npz')
    if cache.exists():
        d=np.load(cache);ys,xs,p,oid=d['ys'],d['xs'],d['pos']*1000,d['obj']
    else:ys,xs,p,oid=raster(key,desc)
    size=desc['size'];x,y,z=p.T;r=np.hypot(x,y);th=np.arctan2(y,x)
    maps={n:np.zeros(len(p),np.float32) for n in ('prints','polish','scratches','dust')}
    fine=sample('dust',z/32+th*.12,(x+y)/22)
    scratch=sample('scratches',z/45,(th*r)/42)
    for i,name in enumerate(desc['parts']):
        sel=oid==i
        if key=='F1':
            if '.Body.ribbed_grip' in name:
                outer=smooth(11.65,12.10,r);contact=window(50,113,z,9)*outer
                coverage=.25+.75*(.5+.5*np.cos(th+1.9))
                maps['polish'][sel]=(contact*smooth(12.42,12.66,r)*coverage*(.55+.45*fine))[sel]
                # Three partial contact stamps, 12–17 mm physical size, no tiling.
                for center,angle,w,h in [(66,-1.6,13,16),(94,-2.55,12,15),(83,.8,14,17)]:
                    u=(z-center)/w+.5;v=delta(th,angle)*12.7/h+.5
                    fade=window(0,1,u,.12)*window(0,1,v,.12)
                    pr=sample('prints',u,v,False)*fade*contact
                    maps['prints'][sel]=np.maximum(maps['prints'][sel],pr[sel])
                maps['dust'][sel]=(contact*(1-smooth(12.04,12.48,r))*fine*.65)[sel]
            elif '.Button.primary_rubber' in name or '.Button.secondary_mode' in name:
                cx=-3.9 if 'primary' in name else 6.0
                d=np.hypot(x-cx,y)
                maps['polish'][sel]=((1-smooth(1.7,4.6,d))*smooth(140.3,142.4,z)*(.65+.35*fine))[sel]
            elif '.Head.hollow' in name or '.Tail.fluted' in name or '.Neck.' in name:
                outer=smooth(15.8,16.4,r) if '.Head.' in name else smooth(12.4,13.1,r)
                area=window(10,30,z,4) if '.Head.' in name else window(124,135,z,2)
                # Sparse handling marks, intact anodizing, no metal exposure.
                maps['scratches'][sel]=(outer*area*scratch*.48)[sel]
                edge=(np.exp(-((z-16.5)/.4)**2)+np.exp(-((z-130)/.5)**2))
                maps['dust'][sel]=(np.clip(edge,0,1)*outer*fine*.35)[sel]
            elif '.Clip.spring_steel' in name:
                maps['scratches'][sel]=(scratch*window(57,110,z,6)*.5)[sel]
                maps['polish'][sel]=(window(52,65,z,3)*fine*.4)[sel]
            elif '.Tail.recessed_switch_plate' in name:
                maps['dust'][sel]=(smooth(7.2,10.0,r)*fine*.4)[sel]
        else:
            if '.Ring.lower' in name or '.Ring.upper' in name or '.Liner.' in name:
                seat=(1-smooth(12.95,13.30,r))*smooth(12.3,12.65,r)*window(65,96,z,2)
                maps['polish'][sel]=(seat*(.35+.65*fine))[sel]
                maps['scratches'][sel]=(seat*scratch*.3)[sel]
                maps['dust'][sel]=((np.exp(-((z-65.5)/.65)**2)+np.exp(-((z-95.5)/.65)**2))*fine*.22)[sel]
            elif '.Clamp.fixed_jaw' in name or '.Clamp.moving_jaw' in name:
                seat=window(21.4,28.6,x,1)*window(8,11.3,np.abs(y),.8)
                maps['polish'][sel]=(seat*(.35+.65*fine))[sel]
                maps['scratches'][sel]=(seat*scratch*.4)[sel]
            elif '.Clamp.recoil_key' in name:
                maps['polish'][sel]=(.45*fine)[sel]
            elif '.Hinge.' in name or '.Lock.lower_lug' in name or '.Lock.upper_lug' in name:
                maps['dust'][sel]=(fine*window(66,94,z,3)*.3)[sel]
    reports[key]={}
    for effect,values in maps.items():
        image=np.zeros((size,size),np.uint8);image[ys,xs]=np.uint8(np.clip(values,0,1)*255+.5)
        image=maximum_filter(image,size=3) # one-texel UV seam padding, not a physical dilation
        path=WORK/(key+'_'+effect+'.png');Image.fromarray(np.flipud(image)).save(path)
        reports[key][effect]={'mask':str(path),'coverage_over_0.1':float((values>.1).mean()),'max':float(values.max())}
    print('MASKS',key,reports[key],flush=True)
(WORK/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(WORK/'masks.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
(WORK/'license.txt').write_text('CC0 1.0 — ambientCG. Primary source URLs and original SHA-256: sources.json.\nPatterns are not claimed to be photographs. Levels, partial crop and geometry-local projection: tools/dozor/wear_masks.py.\nContact: generic handheld geometry zones; actual ring and Picatinny seating. Pistol hand animation is not available and was not fabricated.\n',encoding='utf-8')
