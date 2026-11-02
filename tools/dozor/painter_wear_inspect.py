"""Reopen audit: native separate wear groups and untouched factory hierarchy."""
import json,pathlib
import substance_painter.textureset as TS
import substance_painter.layerstack as L
from substance_painter.textureset import ChannelType as CH
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
GROUP='Этап 2 — износ'
baseline=json.loads((OUT/'checks/working100-native-layers.json').read_text(encoding='utf-8'))
def tree(n):
    r={'name':n.get_name(),'type':type(n).__name__,'visible':n.is_visible()}
    if isinstance(n,L.GroupLayerNode):r['children']=[tree(c) for c in n.sub_layers()]
    elif isinstance(n,L.FillLayerNode):
        r['channels']=sorted(str(c) for c in n.active_channels)
        r['meshes']=sorted(n.get_geometry_mask_enabled_meshes())
    return r
report={}
for t in TS.all_texture_sets():
    roots=L.get_root_layer_nodes(t.get_stack())
    assert [tree(n) for n in roots if n.get_name()!=GROUP]==baseline['factory_tree'][t.name()]
    groups=[n for n in roots if n.get_name()==GROUP]
    if t.name()=='DOZOR_LENS':assert not groups;continue
    assert len(groups)==1 and groups[0].is_visible()
    children=groups[0].sub_layers()
    assert len(children)==(4 if t.name()=='DOZOR_F1' else 3)
    for n in children:
        assert isinstance(n,L.FillLayerNode) and n.has_mask()
        assert CH.Height not in n.active_channels and CH.Normal not in n.active_channels
    report[t.name()]=[tree(n) for n in groups]
(OUT/'checks/working100-native-reopen.json').write_text(json.dumps({'status':'PASS','factory_tree_unchanged':True,'wear_groups':report,'lens_untouched':True},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS reopened native Painter: factory hierarchy unchanged, wear separate and masked, no wear Height/Normal')
