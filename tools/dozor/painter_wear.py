"""Separate native, toggleable working-100 wear group over accepted factory layers."""
import pathlib,json
import substance_painter.layerstack as L
import substance_painter.textureset as TS
import substance_painter.resource as R
import substance_painter.project as P
from substance_painter.textureset import ChannelType as CH
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
WORK=pathlib.Path('E:/Games/RING-godot/_asset_src/dozor/wear')
GROUP='Этап 2 — износ'
assert json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))['accepted']
assert (OUT/'painter/DOZOR_working100_v01.spp').exists(),'Save a separate copy before editing'
assert pathlib.Path(P.file_path()).resolve()==(OUT/'painter/DOZOR_working100_v01.spp').resolve(),'Only edit the separate working copy'

def tree(n):
    r={'name':n.get_name(),'type':type(n).__name__,'visible':n.is_visible()}
    if isinstance(n,L.GroupLayerNode):r['children']=[tree(c) for c in n.sub_layers()]
    elif isinstance(n,L.FillLayerNode):
        r['channels']=sorted(str(c) for c in n.active_channels)
        r['meshes']=sorted(n.get_geometry_mask_enabled_meshes())
    return r

baseline={t.name():[tree(n) for n in L.get_root_layer_nodes(t.get_stack()) if n.get_name()!=GROUP] for t in TS.all_texture_sets()}
audit={}
mask_report=json.loads((WORK/'masks.json').read_text(encoding='utf-8'))
for t in TS.all_texture_sets():
    key={'DOZOR_F1':'F1','DOZOR_P':'P'}.get(t.name())
    if key is None:continue # protected lens and reflector receive no invented contact
    st=t.get_stack()
    for n in L.get_root_layer_nodes(st):
        if n.get_name()==GROUP:L.delete_node(n)
    group=L.insert_group(L.InsertPosition.from_textureset_stack(st));group.set_name(GROUP)
    for channel in st.all_channels():group.set_blending_mode(L.BlendingMode.Passthrough,channel)
    pos=L.InsertPosition.inside_node(group,L.NodeStack.Substack)
    audit[t.name()]=[]
    for effect,title,delta,color,cop in [
        ('polish','Контакт — мягкая полировка',-.075,(.96,.96,.96),.35),
        ('prints','Ручной контакт — частичные отпечатки',-.16,(.91,.91,.91),.4),
        ('scratches','Обращение — редкие поверхностные риски',.095,(.94,.94,.94),.30),
        ('dust','Защищённые углубления — следы пыли',.16,(.15,.145,.13),.28)]:
        if mask_report[key][effect]['max']==0:continue
        layer=sp_lib.fill(title,pos,color=color,rough=abs(delta),**({'metal':0} if effect=='dust' else {}))
        layer.set_blending_mode(L.BlendingMode.Subtract if delta<0 else L.BlendingMode.LinearDodge,CH.SpecularRoughness)
        layer.set_blending_mode(L.BlendingMode.Normal if effect=='dust' else L.BlendingMode.Multiply,CH.BaseColor)
        layer.set_opacity(cop,CH.BaseColor)
        if effect=='dust':layer.set_opacity(.25,CH.Metallic)
        layer.add_mask(L.MaskBackground.Black)
        path=WORK/(key+'_'+effect+'.png')
        rid=R.import_project_resource(str(path),R.Usage.TEXTURE,name='DOZOR_WORK100_'+key+'_'+effect).identifier()
        mask=L.insert_fill(L.InsertPosition.inside_node(layer,L.NodeStack.Mask));mask.set_source(None,rid)
        mask.set_projection_mode(L.ProjectionMode.UV)
        assert CH.Height not in layer.active_channels and CH.Normal not in layer.active_channels
        audit[t.name()].append({'effect':effect,'name':title,'roughness_delta':delta,'color_opacity':cop,'mask':str(path),'channels':sorted(str(c) for c in layer.active_channels)})
        pos=L.InsertPosition.above_node(layer)
    assert baseline[t.name()]==[tree(n) for n in L.get_root_layer_nodes(st) if n.get_name()!=GROUP]

(OUT/'checks/working100-native-layers.json').write_text(json.dumps({'factory_tree_preserved':True,'factory_tree':baseline,'wear':audit,'height_normal_untouched':True,'group':GROUP},ensure_ascii=False,indent=2),encoding='utf-8')
sp_lib.when_idle(lambda:sp_finish.save_as(str(OUT/'painter/DOZOR_working100_v01.spp')),'_wear_layers_saved.txt')
print('Native working100 groups built; factory roots unchanged; no wear Height/Normal')
