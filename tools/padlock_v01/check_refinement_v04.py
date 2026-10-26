"""Measure exported finish/contact changes and preserve all previous native sources."""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
for rel,checksum in json.loads((WORK/'checks'/'v04_baseline.json').read_text(encoding='utf-8')).items():
    assert hashlib.sha256((WORK/rel).read_bytes()).hexdigest()==checksum,rel

def image(folder,name):return np.asarray(Image.open(WORK/'textures'/folder/(name+'.png')))
def mask(name):return image('contact_v04',name).astype(np.float32)/65535.
def quantile(values):return np.round(np.quantile(values,[.1,.5,.9])/255.,4).tolist()

before=image('export_v03','Padlock_baseColor').astype(np.int16)
after=image('export_v04','Padlock_baseColor').astype(np.int16)
size=before.shape[0]
occupancy=Image.new('L',(size,size),0);draw=ImageDraw.Draw(occupancy)
for item in json.loads((WORK/'checks'/'uv_layout.json').read_text(encoding='utf-8')):
    if not item['mesh'].startswith(('Front_cheek','Rear_cheek')):continue
    for polygon in item['polygons']:
        draw.polygon([(u*size,(1-v)*size) for u,v in polygon],fill=255)
occupied=np.asarray(occupancy.filter(ImageFilter.MinFilter(9)))>0
contact=np.zeros((size,size),bool)
for name in ('body_edges','key_steel','key_dents','key_lips','key_scratches','corner_grime','corner_dust'):
    contact|=mask(name)>.0001
# Replaced v03 contacts can legitimately reveal the original oxide beneath them.
for name in ('body_edges','keyhole'):
    contact|=image('contact_v03',name)>0
contact=np.asarray(Image.fromarray((contact*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(11)))>0
protected=occupied&~contact
delta=np.abs(after-before).max(axis=2)
assert protected.any()
print('PROTECTED_BODY_COLOR_DELTA',np.quantile(delta[protected],[.5,.99,.999,1]).tolist(),
      'fraction >1',float(np.mean(delta[protected]>1)),flush=True)
assert int(delta[protected].max())<=5 and float(np.mean(delta[protected]>1))<.0005,'Broad unrequested body recolor'

orm=image('export_v04','Padlock_occlusionRoughnessMetallic')
coat=image('export_v04','Padlock_coat')
paint=protected&(mask('paint_finish')>.75)&(before[:,:,2]-before[:,:,0]>25)
assert paint.any()
weight=quantile(coat[:,:,0][paint]);roughness=quantile(coat[:,:,1][paint])
assert weight[1]>.5,'Varnish weight is too weak'
assert roughness[2]-roughness[0]>.04,'Varnish is too uniform'
steel=mask('shackle_steel')>.85
steel_rough=quantile(orm[:,:,1][steel])
assert steel_rough[2]-steel_rough[0]>.035,'Bare shackle steel is too uniform'

report={'status':'PASS','previous_v03_and_master_unchanged':True,
        'body_color_max_delta_outside_contact_and_dirt_masks_8bit':int(delta[protected].max()),
        'body_color_fraction_delta_above_one_code':float(np.mean(delta[protected]>1)),
        'coat_weight_on_paint_p10_p50_p90':weight,
        'coat_roughness_on_paint_p10_p50_p90':roughness,
        'shackle_steel_roughness_p10_p50_p90':steel_rough,
        'notes':'Data checks supplement the unchanged-light studio and macro visual review.'}
(WORK/'checks'/'refinement_v04.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
