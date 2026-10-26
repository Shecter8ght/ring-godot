"""Read back custom references after reopening; distinguish API behavior from broken links."""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.source as O

assert P.file_path().endswith('padlock_v05_textured.spp')
rows=[]
def info(src,owner):
    if not isinstance(src,O.SourceReference):return
    try:channel=str(src.referenced_channel)
    except Exception:channel='mono anchor mask'
    rows.append({'owner':owner,'source_uid':src.uid(),'anchor':src.anchor.get_name() if src.anchor else None,'channel':channel})
def walk(nodes):
    for n in nodes:
        if isinstance(n,L.GroupLayerNode):walk(n.sub_layers())
        for e in n.mask_effects()+n.content_effects():
            if isinstance(e,L.AnchorPointEffectNode):rows.append({'anchor_name':e.get_name(),'uid':e.uid(),'parent':n.get_name()})
            elif isinstance(e,L.FillEffectNode):info(e.get_source(None),n.get_name())
            elif isinstance(e,L.GeneratorEffectNode):
                src=e.get_source()
                for k in src.image_inputs:info(src.get_source(k),n.get_name()+':'+k)
walk([n for n in L.get_root_layer_nodes(T.all_texture_sets()[0].get_stack()) if n.get_name().startswith('V05 ·')])
Path('E:/Games/RING-godot/_asset_src/padlock_v01/checks/v05_anchor_diagnostics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
