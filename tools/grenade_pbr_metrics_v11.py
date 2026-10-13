"""Read-only image metrics for actual task-3 manufacturing height/roughness.

No new textures, image editing, normal generation, libraries or asset exports.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'_asset_src/grenade_codex/materials_v11_stage3'
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10b_Task2_На_проверку')


def main():
    rows = []
    for family,path,distance,extent in [
        ('body','textures/authoring/casting_relief_8k_16bit.png',.0008,(.160,.160)),
        ('head','textures/manufacturing/head_manufacturing_height_16.png',.000080,(.0512,.0512)),
        ('lever','textures/manufacturing/lever_manufacturing_height_16.png',.000012,(.0512,.0512)),
        ('wire','textures/manufacturing/wire_manufacturing_height_16.png',.000006,(.064,.0064)),
    ]:
        with Image.open(BASE/path) as image:
            array = np.asarray(image,dtype=np.float32)/65535
        h = (array-.5)*distance
        # Measured map height, not a claim about displaced geometry or the final
        # sum of all Bump layers. All accepted height images stay unchanged.
        row = {'family':family,'source':path,'size':list(reversed(h.shape)),
               'distance_um':distance*1e6,'midlevel':.5,
               'texel_um':[extent[0]/h.shape[1]*1e6,extent[1]/h.shape[0]*1e6],
               'height_min_um':float(h.min()*1e6),'height_max_um':float(h.max()*1e6),
               'height_rms_um':float(h.std()*1e6),'bit_depth':16,'color_space':'Non-Color'}
        del array,h
        if family!='body':
            path=f'textures/manufacturing/{family}_manufacturing_roughness_16.png'
            with Image.open(BASE/path) as image:
                rough=np.asarray(image,dtype=np.float32)/65535
            row['roughness_map']={'source':path,'min':float(rough.min()),'max':float(rough.max()),
                                  'mean':float(rough.mean()),'std':float(rough.std()),
                                  'note':'Actual source map; mixed through native layer amount .21, not final material roughness'}
            del rough
        rows.append(row)
        print('PBR_MAP',family,'RMS_um',round(row['height_rms_um'],4),flush=True)
    out=WORK/'checks/map_metrics.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'scope':'Read-only manufacturing maps; accepted density/relief retained',
                               'maps':rows},ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
