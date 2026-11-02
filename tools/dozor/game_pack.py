"""PNG8 maps and bounded closest-HP fallback for missed projection fringe texels."""
import pathlib,json
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'assets/models/attachments/dozor';WORK=ROOT/'_asset_src/dozor/game'
SOURCE=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж/textures/working100')

def sample(path,uv):
    with Image.open(path) as im:a=np.asarray(im.convert('RGB'),np.float32)
    h,w=a.shape[:2];xx=np.clip(uv[:,0]*(w-1),0,w-1);yy=np.clip((1-uv[:,1])*(h-1),0,h-1)
    x=xx.astype(int);y=yy.astype(int);x1=np.minimum(x+1,w-1);y1=np.minimum(y+1,h-1)
    dx=(xx-x)[:,None];dy=(yy-y)[:,None]
    return (a[y,x]*(1-dx)+a[y,x1]*dx)*(1-dy)+(a[y1,x]*(1-dx)+a[y1,x1]*dx)*dy

report=[]
for atlas in ('F1','P'):
    with Image.open(WORK/('uv_coverage_'+atlas+'.png')) as im:uvmask=np.array(im.convert('L'))>128
    with Image.open(WORK/('hit_coverage_'+atlas+'.png')) as im:hit=np.array(im.convert('L'))>128
    rec=np.load(WORK/('nearest_'+atlas+'.npz'));y,x=rec['y'],rec['x'];uv=rec['uv']
    assert rec['distance'].max(initial=0)<=.00050001
    repaired=hit.copy();repaired[y,x]=True;interior=binary_erosion(uvmask,iterations=2)
    unresolved=int((interior&~repaired).sum())
    assert unresolved==0,(atlas,'Unresolved interior projection misses',unresolved)
    texset='DOZOR_F1' if atlas=='F1' else 'DOZOR_P'
    variants=('F1','F1M','F1S') if atlas=='F1' else ('P',)
    outputs=[]
    for variant in variants:
        values=sample(SOURCE/variant/(texset+'_baseColor.png'),uv)
        outputs.append((OUT/('dozor_'+variant.lower()+'_base_color.png'),values))
    orm=sample(SOURCE/atlas/(texset+'_occlusionRoughnessMetallic.png'),uv)
    outputs.append((OUT/('dozor_'+atlas.lower()+'_orm.png'),orm))
    tangent=sample(SOURCE/atlas/(texset+'_normal.png'),uv)/255*2-1
    tangent/=np.maximum(np.linalg.norm(tangent,axis=1,keepdims=True),1e-12)
    world=np.einsum('ni,nij->nj',tangent,rec['high_basis'])
    normal=np.einsum('nj,nij->ni',world,rec['low_basis'])
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
    outputs.append((OUT/('dozor_'+atlas.lower()+'_normal.png'),(normal*.5+.5)*255))
    for path,values in outputs:
        with Image.open(path) as im:a=np.array(im.convert('RGB'))
        a[y,x]=np.uint8(np.clip(values,0,255)+.5)
        Image.fromarray(a).save(path)
    report.append({'atlas':atlas,'closest_source_pixels':len(y),'max_distance_mm':float(rec['distance'].max(initial=0)*1000),
                   'unresolved_interior_pixels':unresolved,'remaining_boundary_pixels':int((uvmask&~repaired).sum()),
                   'normal_conversion':'accepted high tangent normal -> source world -> low tangent normal',
                   'method':'Actual closest accepted HP surface, within 0.5 mm; main surfaces retain the matched Cycles bake'})
(WORK/'pack.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PNG8 maps; nearest-source fringe transfer verified',report)
