"""20% PM contact history, using the owner's alpha library at physical scale.

Only data maps are authored. Reference photos are never sampled as textures.
No scratching stencil is used: the owner rejected the left slide hatch marks.
"""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image,ImageChops,ImageFilter
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v02'
OUT=REV/'masks';OUT.mkdir(parents=True,exist_ok=True)
SOURCES=json.loads((ROOT/'sources/alpha_manifest.json').read_text(encoding='utf-8'))
SIZES={'side':(8192,4096),'top':(4096,2048),'back':(2048,4096),'front':(2048,4096)}
cache={};used=set();records=[];placements=[]
rng=np.random.default_rng(202013)
def alpha(index):
    used.add(index)
    if index not in cache:
        with Image.open(SOURCES[index]['source']) as im:
            a=im.convert('L');signal=a.point(lambda p:0 if p<8 else p)
            bbox=signal.getbbox()
            # Remove black padding so footprint_mm refers to the real finger pad.
            if index<=10 and bbox:
                a=a.crop((max(0,bbox[0]-14),max(0,bbox[1]-14),min(a.width,bbox[2]+14),min(a.height,bbox[3]+14)))
            cache[index]=a
    return cache[index].copy()
def coords(projection,center,side=0):
    if projection=='side':return ((center[0]+82)*4096/166+side*4096,(175-center[1])*4096/175,4096/166,4096/175)
    if projection=='top':return ((center[0]+82)*4096/166,(25-center[1])*2048/50,4096/166,2048/50)
    return ((center[0]+20)*2048/40,(100-center[1])*4096/100,2048/40,4096/100)
def stamp(canvas,index,center,size,angle,strength,projection='side',side=0,cause='',crop=None):
    a=alpha(index)
    if crop:a=a.crop(tuple(round(v*a.size[i%2]) for i,v in enumerate(crop)))
    if index>10:
        yy,xx=np.mgrid[0:a.height,0:a.width].astype(np.float32)
        env=np.maximum(np.sin(np.pi*xx/(a.width-1))*np.sin(np.pi*yy/(a.height-1)),0)**.75
        a=Image.fromarray(np.uint8(np.asarray(a,dtype=np.float32)*env))
    cx,cy,sx,sy=coords(projection,center,side)
    a=a.resize((max(1,round(size[0]*sx)),max(1,round(size[1]*sy))),Image.Resampling.LANCZOS)
    a=a.rotate(angle,Image.Resampling.BICUBIC,expand=True).point(lambda v:round(v*strength))
    pad=Image.new('L',canvas.size);pad.paste(a,(round(cx-a.width/2),round(cy-a.height/2)))
    canvas.paste(ImageChops.lighter(canvas,pad))
    placements.append(dict(alpha=index,projection=projection,side=side,center_mm=center,footprint_mm=size,degrees=angle,strength=strength,cause=cause,crop=crop))
maps={(purpose,pr):Image.new('L',SIZES[pr]) for purpose,pr in [('fingerprints','side'),('fingerprints','top'),('fingerprints','back'),('wear','side'),('wear','top'),('resin_polish','side'),('palms','side'),('palms','back'),('index_rest','side'),('trigger_fingerprints','side'),('trigger_fingerprints','front')]}
for side in (0,1):
    # Repeated handling of the front half; prints remain partial and overlapping.
    pads=[(-72,105),(-65,113),(-59,107),(-54,117),(-48,109),(-41,104),(-34,115),(-29,108),(-22,117),(-17,104),(-9,113),(-3,107)]
    for j,(x,z) in enumerate(pads):
        stamp(maps['fingerprints','side'],[10,0,1,3,8,2][(j+side)%6],(x+rng.uniform(-2,2),z+rng.uniform(-1.3,1.3)),
              (rng.uniform(8.5,13),rng.uniform(12,19)),rng.uniform(-65,65),rng.uniform(.54,.90),'side',side,'Finger pads during front-slide handling')
    # Three wraps of the hand, with several contacts on the smooth upper panel.
    pads=[(29,62),(40,70),(50,79),(60,67),(68,75),(33,49),(47,53),(60,52),(69,43),(30,34),(43,38),(54,32),(65,26),(37,18),(51,15),(65,10)]
    for j,(x,z) in enumerate(pads):
        stamp(maps['fingerprints','side'],[0,10,2,1,3,9,4][(j+side*2)%7],(x+rng.uniform(-2.5,2.5),z+rng.uniform(-2,2)),
              (rng.uniform(9,14),rng.uniform(13,20)),rng.uniform(-80,75),rng.uniform(.53,.89),'side',side,'Repeated grip contact; smoother oil film')
    # Thumb contacts on both cheeks of the rounded hammer.
    for j,(x,z) in enumerate(((68.5,115),(74,110),(77,115.3))):
        stamp(maps['fingerprints','side'],[10,0,3][j],(x,z),(7.5,10),rng.uniform(-30,60),.85,'side',side,'Thumb contact on hammer cheek')
    # Irregular loss of bluing in the real side rubbing areas. No scratches.
    for x,z,w,h,power in [(-67,104,23,15,.73),(-32,100,43,7,.52),(21,103,36,9,.62),(55,109,33,17,.75),(68,94,19,13,.72),(-22,85,31,10,.52)]:
        stamp(maps['wear','side'],37,(x+(1.3 if side else 0),z),(w,h),rng.uniform(-12,12),power,'side',side,'Holster and hand rubbing; constrained by geometry and contact field')
    for x,z,w,h in [(41,71,22,19),(64,61,15,25),(39,15,17,15),(57,39,28,34)]:
        stamp(maps['resin_polish','side'],37,(x,z),(w,h),rng.uniform(-40,40),.53,'side',side,'Moderate resin contact polish; same polymer substrate')
for j,(x,y) in enumerate([(-73,-4),(-61,5),(-49,-3),(-37,4),(-26,-4),(-15,5),(-5,-2)]):
    stamp(maps['fingerprints','top'],[10,1,3,0][j%4],(x,y),(11,15),rng.uniform(-80,80),rng.uniform(.61,.88),'top',cause='Handling across front slide crown')
for j,x in enumerate((66,72,77)):
    stamp(maps['fingerprints','top'],[10,0,3][j],(x,0),(9,12),35-j*32,.83,'top',cause='Thumb rolling across hammer crown; actual grooves retained')
for x,z in [(68,110),(0,81)]:
    # Back projection coordinates are Y/Z; only rounded rear-facing surfaces use it.
    if x:
        stamp(maps['fingerprints','back'],10,(0,z-15),(10,12),18,.82,'back',cause='Thumb over rounded hammer back (projection offset handled by UV)')
for j,(y,z) in enumerate([(-7,74),(6,68),(-6,54),(6,43),(-4,31),(5,19)]):
    stamp(maps['fingerprints','back'],[0,10,3][j%3],(y,z),(11,17),rng.uniform(-45,45),.71,'back',cause='Palm and finger pads on wraparound backstrap')
for x,y,w,h in [(-67,0,20,23),(-29,0,29,22),(46,0,29,18)]:
    stamp(maps['wear','top'],37,(x,y),(w,h),7,.52,'top',cause='Exposed crown rubbing')
# Five supplied palm variants: crop the broad palm/thenar region rather than
# printing a little complete hand silhouette on a narrow grip.
for side,palms in [(0,[(11,43,66,42,36,-18),(12,57,46,45,43,21),(14,51,24,39,34,-8)]),
                   (1,[(13,45,66,44,33,16),(15,58,44,46,45,-12),(11,48,23,38,31,27)])]:
    for index,x,z,w,h,ang in palms:
        stamp(maps['palms','side'],index,(x,z),(w,h),ang,.82,'side',side,'Broad palm and thenar contact on the grip; oil smears',crop=(.17,.46,.85,.96))
for index,y,z,w,h,ang in [(12,0,54,32,47,8),(14,2,28,30,38,-12)]:
    stamp(maps['palms','back'],index,(y,z),(w,h),ang,.73,'back',cause='Broad palm wrapping around the backstrap',crop=(.17,.46,.85,.96))
# Right-hand index rests above the trigger, on the frame and below the ejection
# window. There is no matching left-side copy of these contact placements.
for index,x,z,ang in [(10,-7,94,90),(3,-22,92,83),(1,-37,94,96),(10,-9,101,88),(8,-28,100,76)]:
    stamp(maps['index_rest','side'],index,(x,z),(8.5,19),ang,.84,'side',1,'Right-hand extended index: frame/slide below ejection port')
for index,x,z,ang in [(10,-11,79,7),(3,-9,83,-22)]:
    for side in (0,1):stamp(maps['trigger_fingerprints','side'],index,(x,z),(8,13),ang,.83,'side',side,'Index contact on the curved trigger')
stamp(maps['trigger_fingerprints','front'],10,(0,80),(10,17),12,.91,'front',cause='Index pad on the forward-facing trigger contact surface')
for (purpose,projection),im in maps.items():
    path=OUT/f'PM_20_v02_{projection}_{purpose}.png';im.save(path,compress_level=6)
    records.append(dict(file=path.relative_to(REV).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),purpose=purpose,projection=projection,size=im.size,color_space='Non-Color',channel='luminance'))
source_rows=[]
for index in sorted(used):
    row=SOURCES[index].copy();src=Path(row['source']);target=REV/'sources/alphas'/row['relative'];target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,target);assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
    row['index']=index;row['copied_file']=target.relative_to(REV).as_posix();source_rows.append(row)
(OUT/'manifest.json').write_text(json.dumps(dict(images=records,placements=placements,source_alphas=source_rows,limits='Artistic contact masks; no measured scan claim; no scratch stencil'),ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_20_CONTACT_MASKS',len(records),'maps',len(placements),'contact placements',len(source_rows),'owner alphas')
