"""Исправление пространства цвета после загрузки PNG с сохранением байтов карт."""
import importlib.util
import json
from pathlib import Path
import bpy

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'_asset_src/grenade_codex'
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
T.P.native()
manifest=json.loads((OUT/'textures/pbr_v06/manifest.json').read_text())
report=[]
for file in ['Grenade_MkII_UCUPaint_Codex_v06.blend','Grenade_MkII_PBR_Preview_v06.blend','Grenade_MkII_Studio_v06.blend']:
    bpy.ops.wm.open_mainfile(filepath=str(OUT/file))
    rows=[]
    for row in manifest:
        im=bpy.data.images[row['file']]
        expected='sRGB' if row['channel']=='BaseColor' else 'Non-Color'
        before=im.colorspace_settings.name
        im.colorspace_settings.name=expected
        assert im.colorspace_settings.name==expected
        rows.append({'image':im.name,'before':before,'after':expected})
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/file),relative_remap=False)
    report.append({'file':file,'images':rows})
    print('MAP_SPACES_REPAIRED',file,flush=True)
(OUT/'checks/map_space_repair_v06.json').write_text(json.dumps(report,indent=2))
