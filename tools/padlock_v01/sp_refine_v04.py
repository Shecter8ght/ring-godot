"""Native OpenPBR varnish plus mixed causal wear and protected dust; retain older layers."""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.resource as R
import substance_painter.js as JS
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01');CH=T.ChannelType
allowed={(WORK/'painter'/('padlock_'+v+'_textured.spp')).as_posix().casefold() for v in ('v03','v04')}
if not P.is_in_edition_state() or P.file_path().replace('\\','/').casefold() not in allowed:
    raise RuntimeError('Wrong or unready project')
ts=T.all_texture_sets()[0];assert ts.name()=='Padlock';st=ts.get_stack()
for node in L.get_root_layer_nodes(st):
    if node.get_name().startswith('V04 ·'):L.delete_node(node)
assert len(L.get_root_layer_nodes(st))==25
for node in L.get_root_layer_nodes(st):
    if node.get_name().startswith(tuple('V03 · '+str(i).zfill(2) for i in range(3,8))):node.set_visible(False)
for channel,fmt in ((CH.CoatWeight,T.ChannelFormat.L16F),(CH.CoatRoughness,T.ChannelFormat.L16F),
                    (CH.CoatNormal,T.ChannelFormat.RGB16F),(CH.CoatColor,T.ChannelFormat.RGB16F)):
    if not st.has_channel(channel):st.add_channel(channel,fmt)
JS.evaluate('alg.shaders.setParameters(0, {"coatEnabled":true, "coatIoR":1.6})')
marker=WORK/'sp_jobs'/'_v04_ready.txt';marker.unlink(missing_ok=True)
channels={**S.CHAN,'coat':CH.CoatWeight,'coatrough':CH.CoatRoughness,'coatnormal':CH.CoatNormal,'coatcolor':CH.CoatColor}

def fill(title,pos,**values):
    node=L.insert_fill(pos);node.set_name('V04 · '+title);node.active_channels={channels[k] for k in values}
    for name,value in values.items():
        source=S.rid(value,'u:procedural') if isinstance(value,str) else S._val(value,data=name!='color')
        node.set_source(channels[name],source)
    if 'height' in values and not isinstance(values['height'],str):node.set_blending_mode(L.BlendingMode.Normal,CH.Height)
    return node

def above(node):return L.InsertPosition.above_node(node)
def bitmap(name):return R.import_project_resource((WORK/'textures'/'contact_v04'/name).as_posix(),R.Usage.TEXTURE).identifier()
def mask(node,name):
    S.mask_black(node);f=L.insert_fill(L.InsertPosition.inside_node(node,L.NodeStack.Mask))
    f.set_source(None,bitmap(name));f.set_projection_mode(L.ProjectionMode.UV);return f

n=fill('00 Лак — чистые каналы и ровная нормаль',above(L.get_root_layer_nodes(st)[0]),
       coat=0.,coatrough=.22,coatnormal=(.5,.5,1.),coatcolor=(1.,1.,1.))
n=fill('01 Сохранившийся глянцевый лак',above(n),rough=.18,coat=.90,coatrough=.10)
mask(n,'paint_finish.png')
n=fill('02 Неравномерные матовые пятна в лаке',above(n),rough=.40,coat=.40,coatrough=.32)
base=mask(n,'paint_finish.png')
S.mask_proc(n,'noise_grunge_map_013/grunge_map_013',{'balance':.50,'contrast':.55},scale=.35,
            above=base,blend=L.BlendingMode.Multiply);S.lop(n,.85)
n=fill('03 Краска в остатках на ножках дужки',above(n),color=(.35,.52,.55),metal=0.,rough=.43,height=.526,coat=.50,coatrough=.22)
mask(n,'shackle_paint.png')
n=fill('04 Разорванные продольные задиры дужки',above(n),color=(.65,.66,.63),metal=1.,rough=.19,height=.499,coat=0.)
n.set_source(CH.SpecularRoughness,bitmap('contact_roughness.png'))
n.set_source(CH.Height,bitmap('steel_microheight.png'))
n.set_projection_mode(L.ProjectionMode.UV)
mask(n,'shackle_steel.png')
n=fill('05 Разбитые кромки и увеличенные сколы',above(n),color=(.65,.64,.61),metal=1.,rough=.24,height=.496,coat=0.)
n.set_source(CH.SpecularRoughness,bitmap('contact_roughness.png'));n.set_projection_mode(L.ProjectionMode.UV)
mask(n,'body_edges.png')
n=fill('06 Скважина — участки выбитого покрытия',above(n),color=(.65,.66,.63),metal=1.,rough=.20,height=.500,coat=0.)
n.set_source(CH.SpecularRoughness,bitmap('contact_roughness.png'));n.set_projection_mode(L.ProjectionMode.UV)
mask(n,'key_steel.png')
n=fill('07 Углубления тычков и раковин',above(n),color=(.42,.41,.38),metal=1.,rough=.35,height=.474,coat=0.)
mask(n,'key_dents.png')
n=fill('08 Отблески на забитых краях раковин',above(n),color=(.70,.69,.66),metal=1.,rough=.20,height=.5015,coat=0.)
mask(n,'key_lips.png')
n=fill('09 Борозды и царапины от ключа',above(n),color=(.64,.65,.62),metal=1.,rough=.18,height=.490,coat=0.)
mask(n,'key_scratches.png')
n=fill('10 Тёмная грязь в защищённых сопряжениях',above(n),color=(.22,.19,.15),metal=0.,rough=.92,coat=0.)
base=mask(n,'corner_grime.png')
g=S.mask_generator(n,'mg_dirt/mg_dirt',{'dirt_level':.62,'dirt_contrast':.55,'grunge_amount':.25,
                    'Grunge_Scale':3,'Use_Triplanar':1,'edges_masking':.65},above=base)
g.set_blending_mode(L.BlendingMode.Multiply);S.lop(n,.88)
n=fill('11 Редкая осевшая пыль в уголках',above(n),color=(.43,.40,.34),metal=0.,rough=.96,coat=0.)
base=mask(n,'corner_dust.png')
f=L.insert_fill(L.InsertPosition.above_node(base));f.set_source(None,bitmap('dust_alpha.png'))
S.triplanar(f,4.0);f.set_blending_mode(L.BlendingMode.Multiply);S.lop(n,.82)
print('V04_NATIVE_LAYERS',len(L.get_root_layer_nodes(st)))

def save_native():
    P.save_as((WORK/'painter'/'padlock_v04_textured.spp').as_posix(),P.ProjectSaveMode.Full)
    (WORK/'checks'/'painter_v04_channels.json').write_text(json.dumps({
        'channels':{str(k):str(v.format()) for k,v in st.all_channels().items()},
        'shader':JS.evaluate('alg.shaders.shaderInstancesToObject()'),
        'layers':[(node.get_name(),node.is_visible()) for node in L.get_root_layer_nodes(st)]},ensure_ascii=False,indent=2),encoding='utf-8')
    return {'saved':P.file_path(),'layers':len(L.get_root_layer_nodes(st)),
            'next':'Reopen the saved project before sp_export_v04.py'}

S.when_idle(save_native,'_v04_saved.txt')
