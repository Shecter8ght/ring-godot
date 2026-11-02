"""Native Painter factory groups, catalogue numbers, flat per-variant marking layers."""
import os,json,pathlib,copy
import substance_painter.layerstack as L
import substance_painter.textureset as TS
import substance_painter.resource as R
from substance_painter.textureset import ChannelType as CH
ROOT=pathlib.Path('E:/Games/RING-godot')
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
WORK=ROOT/'_asset_src/dozor/painter'
spec=json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))
meshmap=json.loads((WORK/'painter_meshes.json').read_text(encoding='utf-8'))
codes={s['id']:s['finish'] for s in spec['slots']}
layers={}
for texset in TS.all_texture_sets():
    name=texset.name();st=texset.get_stack();parts=[]
    for sid,per_set in meshmap['slots'].items():
        names=per_set.get(name,[])
        if not names:continue
        code=codes[sid]
        if code:
            parts.append({'finish':code,'meshes':names})
        else:
            # Microscopic functional LED ceramic and phosphor, separate from body finish.
            custom={'code':'LED-CERAMIC','title':'Техническая керамика LED','kind':'coating',
                    'base':{'color':[.78,.78,.72],'rough':.48,'metal':0},'grain':None,
                    'edges':None,'cavity':None,'gradients':None}
            parts.append({'finish':custom,'meshes':names})
    density=meshmap['sets'][name]['px_per_mm_2K']*(2 if name=='DOZOR_F1' else .25 if name=='DOZOR_LENS' else 1)
    bbox=143 if name=='DOZOR_F1' else 55 if name=='DOZOR_P' else 27
    print(sp_finish.build_set(name,parts,density,bbox))
    factory=next(n for n in L.get_root_layer_nodes(st) if isinstance(n,L.GroupLayerNode))
    # Geometry scope belongs on the group as well as its fill layers: an empty
    # normal-blended substack otherwise contributes default channels outside it.
    for sub in factory.sub_layers():
        code=sub.get_name().split(' — ',1)[0]
        selected=[]
        for part in parts:
            pc=part['finish']['code'] if isinstance(part['finish'],dict) else part['finish']
            if pc==code:selected+=part['meshes']
        assert selected,(name,code)
        sp_lib.only_meshes(sub,selected)
    # Ordinary lettering only changes colour, never Height/Normal or floating geometry.
    variants=('F1','F1M','F1S') if name=='DOZOR_F1' else ('P',) if name=='DOZOR_P' else ()
    layers[name]={}
    for variant in variants:
        layer=sp_lib.fill('Маркировка • '+variant,L.InsertPosition.from_textureset_stack(st),color=(.72,.73,.73))
        layer.add_mask(L.MaskBackground.Black)
        path=WORK/(name+'_'+variant+'_mark.png')
        rid=R.import_project_resource(str(path),R.Usage.TEXTURE,name=name+'_'+variant+'_mark_v1').identifier()
        mask=L.insert_fill(L.InsertPosition.inside_node(layer,L.NodeStack.Mask));mask.set_source(None,rid)
        mask.set_projection_mode(L.ProjectionMode.UV)
        layer.set_visible(variant in ('F1','P'))
        layers[name][variant]=layer
    # The small LED die is phosphor even when switched off, not an emissive light.
    if name=='DOZOR_F1':
        die=sp_lib.fill('LED • люминофор, выключен',L.InsertPosition.from_textureset_stack(st),color=(.76,.63,.22),rough=.5,metal=0)
        sp_lib.only_meshes(die,[m for m in st.material().all_mesh_names() if 'LED_die' in m])
print('DOZOR native factory layer stacks built')
def save_project():
    path=OUT/'painter/DOZOR_factory_v01.spp'
    sp_finish.save_as(str(path))
    return str(path)
sp_lib.when_idle(save_project,'_dozor_saved.txt')
