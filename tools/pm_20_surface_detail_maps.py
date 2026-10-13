"""Small physical data tiles for pits and positive dry skin/dust particles.

Prototype tiles are inspected on actual grooves before expanding the finish.
PNG16 height: midpoint .5, coding span 0.14 mm. These are artistic masks.
"""
from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_texturing'
REV=ROOT/'revision_20_v03';OUT=REV/'maps';OUT.mkdir(parents=True,exist_ok=True)
PX=1536;SPAN=20.;rng=np.random.default_rng(200313);records=[]
def tile(kind,count,min_mm,max_mm):
    mask=Image.new('L',(PX,PX));draw=ImageDraw.Draw(mask)
    height=np.zeros((PX,PX),dtype=np.float32)
    for i in range(count):
        cx,cy=rng.uniform(8,PX-8,2);size=rng.uniform(min_mm,max_mm)*PX/SPAN
        theta=rng.uniform(0,6.283);n=int(rng.integers(5,10))
        angles=np.sort(rng.uniform(0,6.283,n));aspect=rng.uniform(.40,1.1)
        radii=rng.uniform(.55,1.1,n)*size*.5
        pts=[(cx+np.cos(theta)*np.cos(a)*r-np.sin(theta)*np.sin(a)*r*aspect,cy+np.sin(theta)*np.cos(a)*r+np.cos(theta)*np.sin(a)*r*aspect) for a,r in zip(angles,radii)]
        patch=Image.new('L',(PX,PX));ImageDraw.Draw(patch).polygon(pts,fill=255)
        local=np.asarray(patch.filter(ImageFilter.GaussianBlur(.60)),dtype=np.float32)/255
        lift=rng.uniform(18,65) if kind=='particles' else -rng.uniform(10,35)
        height+=local*lift
        draw.polygon(pts,fill=int(rng.integers(170,256)))
    mask_path=OUT/f'{kind}_footprint.png';mask.save(mask_path)
    encoded=np.uint16(np.clip(.5+height/140,0,1)*65535)
    hp=OUT/f'{kind}_height16.png';Image.fromarray(encoded).save(hp)
    for purpose,path in [('footprint',mask_path),('height',hp)]:
        records.append(dict(file=path.relative_to(REV).as_posix(),kind=kind,purpose=purpose,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),size=[PX,PX],physical_span_mm=SPAN,coding_span_um=140 if purpose=='height' else None,midpoint=.5 if purpose=='height' else None,color_space='Non-Color',origin='Original seeded irregular physical data tile; not a scan'))
tile('particles',1250,.065,.31)
tile('pits',24,.075,.28)
alphas=json.loads((ROOT/'sources/alpha_manifest.json').read_text(encoding='utf-8'));selected=[]
for index in (18,21,38):
    row=alphas[index].copy();dst=REV/'sources/alphas'/row['relative'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(row['source'],dst)
    assert hashlib.sha256(dst.read_bytes()).hexdigest()==row['sha256']
    selected.append(dict(row,index=index,copied_file=dst.relative_to(REV).as_posix()))
(OUT/'manifest.json').write_text(json.dumps(dict(images=records,alpha_sources=selected,seed=200313,limits='Particles positive only; pits negative only; all footprints restricted to physical cavity/edge masks in native UCUPaint.'),ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_20_SURFACE_TILES_READY',len(records),'physical data maps',flush=True)
