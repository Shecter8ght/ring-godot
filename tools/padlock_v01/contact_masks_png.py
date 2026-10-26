"""Prepare source alphas and finish masks; run before/after the Blender rasterizer."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','png'])
args=parser.parse_args()
folder=WORK/'textures'/'contact_v03';folder.mkdir(exist_ok=True)
if args.mode=='prepare':
    baseline_path=WORK/'checks'/'v03_baseline.json'
    baseline={name:hashlib.sha256((WORK/name).read_bytes()).hexdigest() for name in (
        'models/padlock_v01_geometry.blend','models/padlock_v02_textured.blend',
        'painter/padlock_v02_textured.spp','textures/export/Padlock_baseColor.png',
        'textures/export/Padlock_normal.png','textures/export/Padlock_occlusionRoughnessMetallic.png')}
    if baseline_path.exists():assert json.loads(baseline_path.read_text(encoding='utf-8'))==baseline
    else:baseline_path.write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    original=Path('E:/Models Blender/Маски_АЛЬФА/24_Износ_кромок_до_металла/Кромка_02_Прямая_прерывистая_полировка.png')
    target=WORK/'textures'/'sources'/'contact_edge.png';shutil.copy2(original,target)
    (folder/'sources.json').write_text(json.dumps({'source':str(original),'copy':'../sources/contact_edge.png',
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'rights':'Owner alpha library; not asserted CC0'},
        ensure_ascii=False,indent=2),encoding='utf-8')
else:
    for name in ('shackle','keyhole','body_edges'):
        field=np.load(folder/(name+'.npy'))
        mask=Image.fromarray(np.round(np.clip(field,0,1)*65535).astype(np.uint16))
        mask.save(folder/(name+'.png'))
    base=np.asarray(Image.open(WORK/'textures'/'export'/'Padlock_baseColor.png').convert('RGB'),dtype=np.float32)/255
    blue=np.clip((base[:,:,2]-base[:,:,0]-.025)/.075,0,1)
    # Only surviving visible blue binder receives the finish. Brown oxide stays matte.
    Image.fromarray(np.round(blue*65535).astype(np.uint16)).save(folder/'paint_finish.png')
    print('CONTACT_MASKS_READY',folder,flush=True)
