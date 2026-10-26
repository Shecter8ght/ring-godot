"""Store v05 data fields, preserving the useful paint pattern with local authored corrections."""
from pathlib import Path
import numpy as np
from PIL import Image
import cv2

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01';OUT=WORK/'textures'/'fields_v05'
for path in OUT.glob('*.npy'):
    value=np.load(path).astype(np.float32);assert np.isfinite(value).all(),path
    if path.stem=='enamel_coverage':
        original=Image.open(WORK/'textures'/'padlock_paint_mask.png').convert('L')
        original=np.asarray(original.resize((value.shape[1],value.shape[0]),Image.Resampling.LANCZOS),np.float32)/255.
        shackle=np.load(OUT/'shackle_enamel_coverage.npy').astype(np.float32)
        variation=np.load(OUT/'varnish_wear.npy').astype(np.float32)
        breakup=np.clip((variation-.50)/.25,0,1);breakup=breakup*breakup*(3-2*breakup)
        value=np.maximum(original*(.95+.05*value),shackle*breakup)
    if path.stem=='enamel_brush_height':
        value=.526+.003*(np.load(OUT/'varnish_wear.npy').astype(np.float32)-.5)
    Image.fromarray(np.round(np.clip(value,0,1)*65535).astype(np.uint16)).save(path.with_suffix('.png'))
# Independent, very shallow waviness of the aged enamel film. Slopes are bounded
# to 0.025 (less than 2.1 degrees combined); oxide normals remain in the base layer.
film=np.load(OUT/'varnish_wear.npy').astype(np.float32)
film=cv2.GaussianBlur(film,(0,0),2.)
dy,dx=np.gradient(film);occupied=np.load(OUT/'oxide_tone.npy')>.05
p95=max(float(np.percentile(np.hypot(dx,dy)[occupied],95)),1e-6)
nx=np.clip(-dx*(.014/p95),-.025,.025);ny=np.clip(dy*(.014/p95),-.025,.025)
normal=np.stack((nx,ny,np.ones_like(nx)),axis=-1);normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
packed=np.round((normal*.5+.5)*65535).astype(np.uint16)
ok,png=cv2.imencode('.png',packed[:,:,::-1]);assert ok
(OUT/'coat_film_normal.png').write_bytes(png.tobytes())
print('V05_FIELDS_PNG_READY',OUT)
