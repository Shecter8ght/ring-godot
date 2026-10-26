"""Sources and PNG fields for v04; no previous revision is overwritten."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01';OUT=WORK/'textures'/'contact_v04';OUT.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','png']);args=parser.parse_args()
if args.mode=='prepare':
    owners=Path('E:/Models Blender/Маски_АЛЬФА')
    files={'edge_chips.png':owners/'24_Износ_кромок_до_металла'/'Кромка_05_Прямая_мелкие_сколы.png',
           'grain_chips.png':WORK/'textures'/'sources'/'chips.png',
           'dust_alpha.png':owners/'03_Пыль_и_частицы'/'Пыль_редкая_01.png'}
    manifest=[]
    for name,source in files.items():
        shutil.copy2(source,OUT/name)
        manifest.append({'source':str(source),'copy':name,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest(),
                         'rights':'Owner alpha library; not asserted CC0'})
    (OUT/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=['models/padlock_v01_geometry.blend','models/padlock_v03_textured.blend','models/padlock_v03_studio.blend',
           'painter/padlock_v03_textured.spp']+['textures/export_v03/'+n for n in ('Padlock_baseColor.png','Padlock_normal.png','Padlock_occlusionRoughnessMetallic.png')]
    baseline={p:hashlib.sha256((WORK/p).read_bytes()).hexdigest() for p in paths}
    check=WORK/'checks'/'v04_baseline.json'
    if check.exists():assert json.loads(check.read_text(encoding='utf-8'))==baseline
    else:check.write_text(json.dumps(baseline,indent=2),encoding='utf-8')
else:
    for source in OUT.glob('*.npy'):
        field=np.load(source).astype(np.float32)
        Image.fromarray(np.round(np.clip(field,0,1)*65535).astype(np.uint16)).save(source.with_suffix('.png'))
    shutil.copy2(WORK/'textures'/'contact_v03'/'paint_finish.png',OUT/'paint_finish.png')
    print('V04_MASKS_READY',OUT,flush=True)
