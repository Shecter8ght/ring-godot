"""Verify the original stays intact and rust outside contacts retains its color."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
baseline=json.loads((WORK/'checks'/'v03_baseline.json').read_text(encoding='utf-8'))
for path,expected in baseline.items():
    assert hashlib.sha256((WORK/path).read_bytes()).hexdigest()==expected,path

saved_before=np.asarray(Image.open(WORK/'textures'/'export'/'Padlock_baseColor.png').convert('RGB'),dtype=np.int16)
reference=WORK/'checks'/'v02_roundtrip'/'Padlock_baseColor.png'
before=np.asarray(Image.open(reference).convert('RGB'),dtype=np.int16) if reference.exists() else saved_before
after=np.asarray(Image.open(WORK/'textures'/'export_v03'/'Padlock_baseColor.png').convert('RGB'),dtype=np.int16)
size=before.shape[0]
occupancy=Image.new('L',(size,size),0);draw=ImageDraw.Draw(occupancy)
for item in json.loads((WORK/'checks'/'uv_layout.json').read_text(encoding='utf-8')):
    if not item['mesh'].startswith(('Front_cheek','Rear_cheek')):continue
    for polygon in item['polygons']:
        draw.polygon([(u*size,(1-v)*size) for u,v in polygon],fill=255)
occupied=np.asarray(occupancy.filter(ImageFilter.MinFilter(9)))>0
contact=np.zeros((size,size),bool)
for name in ('body_edges','keyhole'):
    contact|=np.asarray(Image.open(WORK/'textures'/'contact_v03'/(name+'.png')))>0
contact=np.asarray(Image.fromarray((contact*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11)))>0
protected=occupied&~contact
delta=np.abs(after-before).max(axis=2)
print('BODY_COLOR_DELTA',np.quantile(delta[protected],[.5,.99,.999,1.]).tolist(),
      'pixels >1:',int(np.count_nonzero(protected&(delta>1))),flush=True)
blue=protected&(before[:,:,2]-before[:,:,0]>25)
old_orm=np.asarray(Image.open(WORK/'textures'/'export'/'Padlock_occlusionRoughnessMetallic.png'))
new_orm=np.asarray(Image.open(WORK/'textures'/'export_v03'/'Padlock_occlusionRoughnessMetallic.png'))
def q(values):return np.round(np.quantile(values,[.1,.5,.9])/255,4).tolist()
old_r=q(old_orm[:,:,1][blue]);new_r=q(new_orm[:,:,1][blue])
print('PAINT_ROUGHNESS',old_r,new_r,flush=True)
# Perceptual preservation check, not a claim of byte-identical recomputation:
# permit sparse differences below 2% of 8-bit code range, reject any broad recolor.
changed_fraction=float(np.mean(delta[protected]>1))
assert int(delta[protected].max())<=5 and changed_fraction<.0005,'Unrequested body recolor'
assert new_r[1]<old_r[1]-.1,'Paint finish did not change roughness enough to be readable'
report={'status':'PASS','v02_files_unchanged':list(baseline),
        'baseline_reexport_max_delta_8bit':int(np.abs(before-saved_before)[occupied].max()),
        'body_color_max_delta_outside_contact_masks_8bit':int(delta[protected].max()),
        'body_color_fraction_delta_above_one_code':changed_fraction,
        'paint_roughness_p10_p50_p90_before':old_r,'paint_roughness_p10_p50_p90_v03':new_r,
        'checks':'Original master/SPP/maps unchanged; approved body rust color protected; paint has a separate varying finish'}
(WORK/'checks'/'refinement_v03.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
