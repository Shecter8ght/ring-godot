"""Inspect actual stack channels and the normal export recipe."""
import json
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.export as X
from pathlib import Path

if not P.is_in_edition_state():raise RuntimeError('Project not ready')
st=T.all_texture_sets()[0].get_stack()
info={'channels':{str(k):str(v.format()) for k,v in st.all_channels().items()}}
for preset in X.list_predefined_export_presets():
    if preset.name=='glTF PBR Metal Roughness':
        info['gltf_outputs']=preset.list_output_maps(st)
for preset in X.list_resource_export_presets():
    if preset.resource_id.name=='Blender (Principled BSDF)':
        info['blender_outputs']=preset.list_output_maps()
out=Path('E:/Games/RING-godot/_asset_src/padlock_v01/checks/painter_channels.json')
out.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(info,ensure_ascii=False))
