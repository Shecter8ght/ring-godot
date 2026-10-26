"""Inspect installed filter controls on a disposable group; never save the probe."""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.layerstack as L
import substance_painter.textureset as T
import sp_lib as S

assert P.file_path().endswith('padlock_v05_textured.spp') and not P.is_busy()
st=T.all_texture_sets()[0].get_stack();report={}
with L.ScopedModification('Read filter controls; discard probe'):
    group=L.insert_group(L.InsertPosition.from_textureset_stack(st));group.set_name('TEMP V05 API PROBE')
    try:
        layer=S.fill('probe',L.InsertPosition.inside_node(group,L.NodeStack.Substack),rough=.5)
        S.mask_black(layer)
        for name in ('highpass/highpass','blur/blur','warp/warp','sharpen/sharpen','height_to_normal/height_to_normal'):
            try:
                f=L.insert_filter_effect(L.InsertPosition.inside_node(layer,L.NodeStack.Mask),S.rid(name,'u:filter'))
                context='mask'
            except ValueError:
                f=L.insert_filter_effect(L.InsertPosition.inside_node(layer,L.NodeStack.Content),S.rid(name,'u:filter'))
                context='content'
            report[name]={'context':context,'parameters':f.get_source().get_parameters()};L.delete_node(f)
        g=S.mask_generator(layer,'mg_dirt/mg_dirt')
        src=g.get_source();report['dirt']=src.get_parameters();report['dirt_image_inputs']=src.image_inputs
    finally:L.delete_node(group)
Path('E:/Games/RING-godot/_asset_src/padlock_v01/checks/v05_filter_controls.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
