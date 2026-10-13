"""Собственные маски литья и осадка в реальном масштабе; фото владельца — только референсы."""
import hashlib, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex/texture_v08/textures/authoring'
FINAL='final' in sys.argv
SIZE=8192 if FINAL else 4096
EXTENT=160. if FINAL else 80.
PX=SIZE/EXTENT
RNG=np.random.default_rng(812307)
OUT.mkdir(parents=True,exist_ok=True)
def noise(cell_mm, amplitude):
    n=max(4,round(EXTENT/cell_mm))
    v=np.clip(RNG.normal(.5,.18,(n,n)),0,1)
    image=Image.fromarray(np.uint8(v*255)).resize((SIZE,SIZE),Image.Resampling.BICUBIC)
    return (np.asarray(image,dtype=np.float32)/255-.5)*amplitude
height=noise(3.0,.000070)+noise(.45,.000060)+noise(.14,.000045)+noise(.060,.000018)
# Выступы и впадины литья различаются по размерам и распределению.
for kind,density in [('nodule',.20),('pit',.14)]:
    count=round(EXTENT**2*density)
    for _ in range(count):
        x,y=RNG.uniform(0,SIZE,2)
        radius=RNG.uniform(.08,.44) if kind=='nodule' else RNG.uniform(.06,.25)
        if RNG.random()<.025:radius*=2
        rx=radius*PX; ry=rx*RNG.uniform(.60,1.45)
        x0,x1=max(0,int(x-rx*1.2)),min(SIZE,int(x+rx*1.2)+1)
        y0,y1=max(0,int(y-ry*1.2)),min(SIZE,int(y+ry*1.2)+1)
        xx=(np.arange(x0,x1)[None,:]-x)/rx; yy=(np.arange(y0,y1)[:,None]-y)/ry
        q=np.sqrt(xx*xx+yy*yy)*(1+.10*np.sin(9*np.arctan2(yy,xx)+x))
        blob=np.maximum(0,1-q*q)**2
        amplitude=RNG.uniform(.000035,.000125) if kind=='nodule' else -RNG.uniform(.000045,.000180)
        height[y0:y1,x0:x1]+=blob.astype(np.float32)*amplitude
# Короткие наплывы литья имеют неровные границы и малую высоту.
flow=Image.new('L',(SIZE,SIZE),0);d=ImageDraw.Draw(flow)
for _ in range(round(EXTENT**2*.012)):
    x,y=RNG.uniform(0,SIZE,2); angle=RNG.uniform(0,math.tau); length=RNG.uniform(.7,2.8)*PX
    d.line([(x,y),(x+math.cos(angle)*length*.5,y+math.sin(angle)*length*.5+PX*.12),(x+math.cos(angle)*length,y+math.sin(angle)*length)],fill=int(RNG.integers(80,240)),width=max(1,round(RNG.uniform(.05,.13)*PX)))
flow=flow.filter(ImageFilter.GaussianBlur(.06*PX))
height+=np.asarray(flow,dtype=np.float32)/255*.000095
height_file=f'casting_relief_{SIZE//1024}k_16bit.png'
# Полный диапазон карты соответствует 0,8 мм; это не глубина каждой раковины.
encoded=np.uint16(np.clip(.5+height/.0008,0,1)*65535)
Image.fromarray(encoded).save(OUT/height_file,compress_level=6)
del encoded,height
particles=Image.new('L',(SIZE,SIZE),0);d=ImageDraw.Draw(particles)
for _ in range(round(EXTENT**2*1.10)):
    x,y=RNG.uniform(0,SIZE,2);r=RNG.uniform(.023,.10)*PX
    if RNG.random()<.018:r*=2.0
    pts=[(x+math.cos(a)*r*RNG.uniform(.6,1.3),y+math.sin(a)*r*RNG.uniform(.6,1.3)) for a in np.linspace(0,math.tau,6,endpoint=False)]
    d.polygon(pts,fill=int(RNG.integers(145,255)))
particles=particles.filter(ImageFilter.GaussianBlur(.3))
particles_file=f'deposit_grains_{SIZE//1024}k.png';particles.save(OUT/particles_file)
# Маска истирания создана самостоятельно; пиксели фото не заимствуются.
scuffs=Image.new('L',(SIZE,SIZE),0);d=ImageDraw.Draw(scuffs)
for _ in range(round(EXTENT**2*.0032)):
    x,y=RNG.uniform(0,SIZE,2);r=RNG.uniform(.45,1.9)*PX
    phases=RNG.uniform(0,math.tau,4)
    angles=np.linspace(0,math.tau,256,endpoint=False)
    radii=r*(.85+.22*np.sin(3*angles+phases[0])+.16*np.sin(7*angles+phases[1])+.075*np.sin(19*angles+phases[2])+.055*np.sin(47*angles+phases[3]))
    pts=[(x+math.cos(a)*q,y+math.sin(a)*q*.70) for a,q in zip(angles,radii)]
    d.polygon(pts,fill=255)
scuffs=scuffs.filter(ImageFilter.GaussianBlur(.023*PX))
scuffs_file=f'contact_breaks_{SIZE//1024}k.png';scuffs.save(OUT/scuffs_file)
rows=[]
for name in [height_file,particles_file,scuffs_file]:
    path=OUT/name; rows.append({'file':name,'size':[SIZE,SIZE],'extent_mm':EXTENT,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source':'Original Codex mask; no pixels extracted from owner photographs','license':'Project original'})
(OUT/f'manifest_{SIZE//1024}k.json').write_text(json.dumps({'seed':812307,'height_span_mm':.8,'grain_diameter_mm':[.046,.20],'maps':rows},indent=2),encoding='utf8')
print('CAST_MAPS_READY',SIZE,EXTENT,flush=True)


