"""Original physically scaled imperfection masks plus a licensed CC0 fingerprint."""
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex/textures/authoring'
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(1201026)
N = 8192
EXTENT_MM = 160.0
manifest = []


def save(image, name, purpose, source='Original synthetic mask; Codex, 2026-10-12'):
    path = OUT / name
    image.save(path, compress_level=6)
    manifest.append({'file':name, 'size':list(image.size), 'mode':image.mode,
                     'physical_extent_mm':EXTENT_MM, 'purpose':purpose,
                     'source':source, 'color_space':'Non-Color',
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    print('MASK_OK', name, image.size, flush=True)


def px(mm, n=N):
    return mm * n / EXTENT_MM


# A few irregular interrupted scratches, rather than a uniform noise carpet.
scratch = Image.new('L', (N,N), 0)
d = ImageDraw.Draw(scratch)
for i in range(430):
    x, y = RNG.uniform(0,N,2)
    angle = RNG.uniform(0,2*math.pi)
    length = px(RNG.uniform(.18, 4.0) if i<380 else RNG.uniform(3,11))
    width = max(1, round(px(RNG.uniform(.020,.075))))
    value = int(RNG.uniform(65,200))
    for step in range(6):
        if RNG.random()<.15:
            continue
        t0,t1 = step/6, min(1,(step+.8+RNG.uniform(0,.2))/6)
        d.line((x+math.cos(angle)*length*t0,y+math.sin(angle)*length*t0,
                x+math.cos(angle)*length*t1,y+math.sin(angle)*length*t1),fill=value,width=width)
save(scratch, 'micro_scratches_8k.png', '20-75 micron hairline abrasions, 0.2-11 mm long')

chip = Image.new('L', (4096,4096),0)
d = ImageDraw.Draw(chip)
for i in range(100):
    x,y = RNG.uniform(0,4096,2)
    radius = px(RNG.uniform(.08,.72),4096)
    pts=[]
    for j in range(12):
        a=j*math.pi/6
        r=radius*RNG.uniform(.35,1.1)
        pts.append((x+math.cos(a)*r,y+math.sin(a)*r))
    d.polygon(pts,fill=int(RNG.uniform(90,220)))
save(chip,'sparse_chips_4k.png','Sparse non-repeating 0.15-1.4 mm coating damage')

scuffs = Image.new('L',(4096,4096),0)
d=ImageDraw.Draw(scuffs)
for i in range(180):
    x,y=RNG.uniform(0,4096,2)
    angle=RNG.uniform(0,2*math.pi)
    length=px(RNG.uniform(.3,2.5),4096)
    for j in range(int(RNG.integers(2,6))):
        delta=RNG.uniform(-4,4)
        d.line((x+delta,y,x+delta+math.cos(angle)*length,y+math.sin(angle)*length),
               fill=int(RNG.uniform(40,140)),width=int(RNG.integers(1,3)))
save(scuffs,'short_scuffs_4k.png','Small groups of superficial direction-dependent marks')

field = np.zeros((2048,2048),np.float32)
for size,weight in [(7,.28),(19,.22),(53,.2),(181,.18),(541,.12)]:
    arr=RNG.random((size,size),dtype=np.float32)
    field+=np.asarray(Image.fromarray(arr,mode='F').resize((2048,2048),Image.Resampling.BICUBIC),np.float32)*weight
field=np.clip((field-.15)/.68,0,1)
save(Image.fromarray((field*65535).astype(np.uint16)).resize((4096,4096),Image.Resampling.BILINEAR),
     'nonuniform_storage_4k.png','16 bit multiscale staining field; no periodic waves')

# A height-aware identification band; its physical height is authored in Blender.
band = Image.new('L',(8192,4096),0)
ar=np.zeros((4096,8192),np.uint8)
for y in range(4096):
    z=(1-y/4095)*86.0
    edge_noise=np.asarray(Image.fromarray((RNG.random((1,256))*255).astype(np.uint8)).resize((8192,1),Image.Resampling.BICUBIC))[0]/255
    lo=80.2+(edge_noise-.5)*.27
    hi=84.3+(edge_noise-.5)*.22
    ar[y]=np.where((z>lo)&(z<hi),255,0)
band=Image.fromarray(ar)
save(band,'neck_band_8kx4k.png','Irregular edge yellow band 80.2-84.3 mm above body base')

font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',245)
stamp=Image.new('L',(2048,1024),0)
d=ImageDraw.Draw(stamp)
d.text((1024,330),'FUZE M10A3',font=font,fill=240,anchor='mm')
d.text((1024,660),'LOT R-102',font=font,fill=230,anchor='mm')
stamp_arr=np.asarray(stamp).copy()
loss=np.asarray(Image.fromarray((RNG.random((256,512))*255).astype(np.uint8)).resize(stamp.size,Image.Resampling.BICUBIC))
stamp_arr=np.where(loss>214,stamp_arr*.35,stamp_arr).astype(np.uint8)
save(Image.fromarray(stamp_arr),'lever_ink_marking_2k.png','Own ink stencil, fictional lot; 20 x 10 mm projection')

source=ROOT / '_asset_src/veras_texture_revision_v11/delivery/ВЕРАС-54/Актуальное/Текстуры/sources/Fingerprints003_4K-PNG_Opacity.png'
finger=Image.open(source).convert('L')
# Verified CC0 source, one naturally partial print near the lower middle.
crop=finger.crop((1960,2740,2520,3310))
crop=crop.resize((405,480),Image.Resampling.LANCZOS).rotate(-18,resample=Image.Resampling.BICUBIC,expand=True)
single=Image.new('L',(1024,1024),0)
single.paste(crop.resize((740,860),Image.Resampling.LANCZOS),(142,82))
save(single,'single_partial_print_1k.png','One CC0 partial print, projected on a 16 x 21 mm hand contact',
     'ambientCG Fingerprints003, CC0 1.0; crop, resize, rotation; https://ambientcg.com/view?id=Fingerprints003')
oily=Image.new('L',(4096,4096),0)
oily.paste(crop,(1750,1630))
oily.paste(crop.rotate(75,expand=True),(2230,2490))
save(oily,'partial_fingerprints_4k.png','Roughness only, two partial 16-19 mm prints',
     'ambientCG Fingerprints003, CC0 1.0; cropped/resized/rotated opacity; https://ambientcg.com/view?id=Fingerprints003')
sources=OUT.parent/'sources'
sources.mkdir(exist_ok=True)
shutil.copy2(source,sources/source.name)
(sources/'LICENSE.md').write_text('Fingerprints003 — ambientCG, CC0 1.0 Universal.\n'
    'https://ambientcg.com/view?id=Fingerprints003\nhttps://docs.ambientcg.com/license/\n'
    'Verified 2026-10-12. Original opacity retained; cropped, resized and rotated into a contact atlas.\n'
    'All other authoring masks are original synthetic work, not extracted from reference photographs.\n',encoding='utf8')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
print('ALL_MASKS_OK',len(manifest),flush=True)
