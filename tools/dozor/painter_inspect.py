"""Read native Painter layer ownership and the three flat marking variants."""
import json,pathlib
import substance_painter.project as P
import substance_painter.textureset as TS
import substance_painter.layerstack as L
from substance_painter.textureset import ChannelType as CH
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
def describe(n):
    r={'name':n.get_name(),'type':type(n).__name__,'visible':n.is_visible()}
    if isinstance(n,L.GroupLayerNode):r['children']=[describe(c) for c in n.sub_layers()]
    elif isinstance(n,L.FillLayerNode):
        r['channels']=[str(c) for c in n.active_channels]
        r['geometry_scope_count']=len(n.get_geometry_mask_enabled_meshes())
        if n.get_name().startswith('Маркировка'):
            assert n.active_channels=={CH.BaseColor},r
    return r
data={'authoring':'Substance 3D Painter','native_editable':True,'sets':{}}
for t in TS.all_texture_sets():
    root=L.get_root_layer_nodes(t.get_stack())
    data['sets'][t.name()]=[describe(n) for n in root]
    factory=next(n for n in root if isinstance(n,L.GroupLayerNode))
    for group in factory.sub_layers():
        names=group.get_geometry_mask_enabled_meshes()
        assert names,group.get_name()
        assert all(set(ch.get_geometry_mask_enabled_meshes())<=set(names) for ch in group.sub_layers() if isinstance(ch,L.FillLayerNode))
data['markings_color_only']=True
(OUT/'checks/painter-native-layers.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS native layer trees;',len(data['sets']),'sets; flat colour-only markings; factory group scopes verified')
