"""Refine only the owner's 20% PM, preserving the accepted v11 mesh and rig.

Native UCUPaint material study precedes the contact atlases and review package.
Use Blender --background --factory-startup --python-exit-code 1 --python ...
-- study|finish. This never edits the v01 source or the 100/60% files.
"""
from pathlib import Path
import ast, sys, json, hashlib, importlib, importlib.util
import bpy, addon_utils, numpy as np
from mathutils import Color, Vector

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'_asset_src/pm_texturing'
REV=ROOT/'revision_20_v02'
SKILL=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing')
SOURCE=ROOT/'candidate/20/PM_Textures_20_v01.blend'
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'study'
assert MODE in ('study','finish')
CONDITION=20; UV='PMWearUV'; TOP='PMTopUV'; CREATED=[]
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint')
spec=importlib.util.spec_from_file_location('pm_ucupaint_helpers',SKILL/'scripts/ucupaint_helpers.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
assert U.common.get_current_version_str()=='2.4.9'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.context.scene;S.frame_set(1)
rig=bpy.data.objects['PM_CONTROLS • select me']
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[key]=0.
rig.update_tag();bpy.context.view_layer.update()
FRAME=bpy.data.objects['Frame | traced flowing silhouette']

# Reuse the previously checked native API helpers without executing v01 authoring.
helper_names={'activate','stack','layer','noise','vmask','edge','in_parent'}
parsed=ast.parse((PROJECT/'tools/author_pm_pbr.py').read_text(encoding='utf-8'))
for node in parsed.body:
    if isinstance(node,ast.FunctionDef) and node.name in helper_names:
        exec(compile(ast.Module(body=[node],type_ignores=[]),'native_pm_helpers','exec'))

_layer_v01=layer
def layer(*args,**kwargs):
    l=_layer_v01(*args,**kwargs)
    if l.type=='NOISE':
        # Uniform-scale preference otherwise bypasses the three-axis mapping.
        l.enable_uniform_scale=False
        H.sync_property(U,l,'scale',Vector(kwargs.get('stretch',(1,1,1))))
    return l

_noise_v01=noise
def noise(l,name,scale,lo=None,hi=None,shift=None):
    m=_noise_v01(l,name,scale,lo,hi,shift)
    H.sync_property(U,m,'translation',Vector(m.translation))
    if scale<=135:
        n=U.common.get_mask_tree(m).nodes[m.source]
        n.inputs['Detail'].default_value=5.;n.inputs['Roughness'].default_value=.69
    return m

def group(material):
    return next(n.node_tree for n in material.node_tree.nodes
                if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node)

for m in bpy.data.materials:
    if not m.use_nodes:continue
    native=[n.node_tree for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node]
    if not native:continue
    # Keep the previous editable stacks as a fallback in this new file.
    m.use_fake_user=True
    if 'воронёная сталь' in m.name or 'бакелит' in m.name or 'анодированный алюминий' in m.name:
        for l in native[0].yp.layers:
            if l.name.startswith(('21 •','22 •','23 •')) and ('анодированный' not in m.name or l.name.startswith('23 •')):
                l.enable=False
        m['v02 replacement']='Separate reference-based steels and phenolic resin; v01 flat rubs/edge outlines/scratch decal disabled.'

def coordinates(o):
    me=o.data; count=len(me.vertices)
    raw=np.empty(count*3,dtype=np.float32);me.vertices.foreach_get('co',raw)
    mw=np.asarray(o.matrix_world,dtype=np.float32)
    world=(raw.reshape(-1,3)@mw[:3,:3].T+mw[:3,3])*1000
    x,y,z=world.T
    if o.name.startswith('Slide |'):
        contact=.20+.47*np.exp(-((x+43)/49)**2-((z-110)/19)**2)+.44*np.exp(-((x-55)/27)**2-((z-109)/18)**2)
    elif o.name.startswith('Frame |'):
        contact=.12+.58*np.exp(-((x-61)/28)**2-((z-88)/22)**2)+.24*np.exp(-((x+24)/38)**2-((z-83)/16)**2)
    elif o.name.startswith(('Bakelite |','Grip ')):
        contact=.48+.36*np.exp(-((x-52)/26)**2-((z-44)/43)**2)
    else:contact=np.full(count,.75)
    a=me.color_attributes.get('PM_WearCause') or me.color_attributes.new(name='PM_WearCause',type='BYTE_COLOR',domain='POINT')
    vals=np.ones((count,4),dtype=np.float32);vals[:,:3]=np.clip(contact,0,1)[:,None]
    a.data.foreach_set('color',vals.ravel());me.update()
    norm=np.empty(count*3,dtype=np.float32);me.vertices.foreach_get('normal',norm)
    norm=norm.reshape(-1,3)@np.linalg.pinv(mw[:3,:3]);norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1.e-8)
    rear=np.maximum(norm[:,0],0)**3
    a=me.color_attributes.get('PM_BackSurface') or me.color_attributes.new(name='PM_BackSurface',type='BYTE_COLOR',domain='POINT')
    vals[:,:3]=rear[:,None];a.data.foreach_set('color',vals.ravel())
    idx=np.empty(len(me.loops),dtype=np.int32);me.loops.foreach_get('vertex_index',idx)
    vz=z-15 if o.name.startswith('Hammer |') else z
    uv=me.uv_layers.get('PMBackUV') or me.uv_layers.new(name='PMBackUV')
    uv.data.foreach_set('uv',np.asarray(np.column_stack(((y+20)/40,vz/100))[idx],dtype=np.float32).ravel());me.update()
    reach=np.clip((z-110)/3.5,0,1) if o.name.startswith('Hammer |') else np.ones(count)
    for name,data in [('PM_FrontHalf',np.clip((1-x)/3,0,1)),('PM_SkinReach',reach),('PM_FrontSurface',np.maximum(-norm[:,0],0)**3)]:
        a=me.color_attributes.get(name) or me.color_attributes.new(name=name,type='BYTE_COLOR',domain='POINT')
        vals[:,:3]=data[:,None];a.data.foreach_set('color',vals.ravel())
    me.update()

def varied(t,label,color,rough,scale,lo,hi,amount=1.,metal=1,contact=False):
    l=layer(t,label,color,metal,rough,amount=amount)
    if contact:vmask(l,'PM_WearCause')
    noise(l,label+' • собственная неоднородность',scale,lo,hi)
    return l

def steel(label,kind):
    is_slide=kind=='slide'; is_guard=kind in ('guard','trigger'); is_hammer=kind=='hammer'
    base=(.016,.019,.020) if is_slide else ((.10,.107,.11) if is_guard else ((.020,.016,.013) if is_hammer else (.011,.009,.0075)))
    rough=.48 if is_slide else (.46 if is_guard else (.46 if is_hammer else .54))
    m,t,p=stack('v02 • '+label,base,1,rough)
    layer(t,'00 • Сталь с остатками старого воронения',base,1,rough)
    layer(t,'10 • Мелкое зерно обработанной стали',height='source',kind='NOISE',scale=1600 if is_slide else 2100,distance=5.e-6 if is_slide else 2.6e-6,amount=.85)
    layer(t,'11 • Тонкие следы шлифования',height='source',kind='NOISE',scale=2600,distance=1.5e-6,stretch=(.17,1,3.5),amount=.30)
    if is_slide:
        layer(t,'11b • Микрофактура тёмного защитного покрытия',height='source',kind='NOISE',scale=1200,distance=.0000035,amount=.42)
    varied(t,'12 • Шероховатость ослабленного покрытия',None,min(.70,rough+.11),420,.32,.68,.52)
    if not is_guard:
        varied(t,'20 • Слабые переходы оттенка заводского воронения',(.024,.028,.027) if is_slide else (.024,.019,.014),.52 if is_slide else .59,62,.30,.69,.28)
        varied(t,'21 • Сохранившееся тёмное заводское покрытие',(.012,.015,.016) if is_slide else (.008,.007,.0055),.54,32,.36,.63,.23)
        varied(t,'22 • Очень мелкая неоднородность защитного слоя',(.022,.023,.020),.57,1200,.49,.71,.16)
        l=varied(t,'23 • Редкие микровпадины потемневшего металла',(.012,.013,.010),.67,2800,.72,.84,.20,metal=0)
        ch=next(c for r,c in zip(t.yp.channels,l.channels) if r.type=='NORMAL')
        ch.enable=True;ch.override=True;ch.override_type='DEFAULT'
        H.sync_property(U,ch,'override_value',.43);H.sync_property(U,ch,'bump_distance',.000010);H.sync_property(U,ch,'bump_midlevel',.5)
    else:
        varied(t,'20 • Остатки покрытия в менее затронутых местах',(.046,.039,.029),.57,95,.47,.68,.55)
    contact_color=(.035,.039,.035) if is_slide else ((.25,.27,.29) if is_guard else (.029,.026,.021))
    varied(t,'30 • Маслянистое выцветание и полировка в местах хвата',contact_color,.36 if is_slide else .38,48,.35,.69,.30 if is_slide else (.86 if is_guard else .34),contact=True)
    l=layer(t,'31 • Прерывистые потёртости выпуклых фасок',(.17,.19,.20),1,.35,amount=.44 if not is_guard else .65)
    edge(l,.00056 if is_slide else .00038);vmask(l,'PM_WearCause');noise(l,'Прерывание контакта на фасках',1550,.46,.72)
    varied(t,'32 • Локальная гладкая полировка от кожи',None,.35 if is_slide else .32,140,.42,.73,.31,contact=True)
    H.reconnect(U,t);return m

def barrel():
    m,t,p=stack('v02 • гладкая сатиновая сталь ствола',(.38,.43,.48),1,.29)
    layer(t,'00 • Холодная оружейная сталь',(.38,.43,.48),1,.29)
    layer(t,'10 • Очень тонкая обработка ствола',height='source',kind='NOISE',scale=3300,distance=.0000008,stretch=(.10,1,1),amount=.52)
    varied(t,'11 • Мягкое различие сатиновой шероховатости',None,.36,420,.28,.71,.40)
    varied(t,'20 • Слабая полировка от движения затвора',None,.24,190,.46,.74,.38)
    H.reconnect(U,t);return m

def resin():
    m,t,p=stack('v02 • тёмно-бордовый фенопласт',(.041,.0035,.0043),0,.29)
    p.inputs['Coat Weight'].default_value=.22;p.inputs['Coat Roughness'].default_value=.25
    g=next(n for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree==t)
    m.node_tree.links.new(g.outputs['Roughness'],p.inputs['Coat Roughness'])
    layer(t,'00 • Красно-бордовая фенольная масса',(.041,.0035,.0043),0,.29)
    varied(t,'10 • Тёмные включения в смоле',(.018,.0017,.0018),.32,110,.35,.68,.43,metal=0)
    varied(t,'11 • Красно-коричневые переходы пигмента',(.069,.0070,.0040),.30,330,.48,.74,.22,metal=0)
    layer(t,'12 • Едва заметная фактура прессования',height='source',kind='NOISE',scale=2700,distance=.0000009,amount=.6)
    varied(t,'20 • Полировка гладких контактных участков',None,.23,140,.32,.64,.37,metal=0,contact=True)
    l=layer(t,'21 • Умеренная потёртость выступов фенопласта',(.072,.010,.008),0,.31,amount=.29)
    edge(l,.00025);vmask(l,'PM_WearCause');noise(l,'Раздельная потёртость смоляных кромок',2300,.45,.70)
    l=layer(t,'30 • Тёмные защищённые промежутки насечки',(.008,.0010,.0008),0,.52,amount=.72)
    mask=U.Mask.add_new_mask(l,'Впадины настоящей ромбовидной насечки','AO','Object',UV,ao_distance=.00072)
    importlib.import_module(U.__name__+'.MaskModifier').add_new_mask_modifier(mask,'INVERT')
    noise(l,'Неполное отложение в основании насечки',730,.24,.68)
    H.reconnect(U,t);return m

materials={'slide':steel('тёмный воронёный затвор','slide'), 'frame':steel('потемневшая рамка','frame'),
           'guard':steel('светлая контактная сталь скобы','guard'), 'trigger':steel('сатиновая контактная сталь спуска','trigger'), 'hammer':steel('контактная сталь курка и органов управления','hammer'),
           'barrel':barrel(),'resin':resin()}

def family(o):
    n=o.name
    if n.startswith(('Bakelite |','Grip ','Lanyard |')):return 'resin'
    if n.startswith('Slide |') or n.startswith(('Front sight |','Rear sight |')):return 'slide'
    if n.startswith('Trigger guard |'):return 'guard'
    if n.startswith('Trigger |'):return 'trigger'
    if n.startswith('Barrel |') or n=='Muzzle | recessed steel rim':return 'barrel'
    if n.startswith(('Hammer |','Slide catch |','MagCatch |')):return 'hammer'
    if n.startswith('Safety |') and 'enamel' not in n:return 'hammer'
    if n.startswith(('Frame |','Magazine |')) or o.get('PM geometry helper'):return 'frame'
    return None

assignments={}
for o in bpy.data.objects:
    if o.type!='MESH':continue
    f=family(o)
    if not f:continue
    coordinates(o);assignments[o.name]=f
    for i,old in enumerate(o.data.materials):
        if old and (old.name.startswith('ПМ • 20 •') or old.name.startswith('Check |')):
            o.data.materials[i]=materials[f]

# Real engraving operands inherit their host's body material, keeping enamel.
record=json.loads((PROJECT/'_asset_src/pm_refinement/review_v11/Проверки/engraving.json').read_text(encoding='utf-8'))
for row in record['markings']:
    host=bpy.data.objects[row['host']];f=family(host)
    if f:
        cutter=bpy.data.objects[row['cutter']]
        for i,m in enumerate(cutter.data.materials):
            if m and m.name.startswith('ПМ • 20 •'):cutter.data.materials[i]=materials[f]

if MODE=='finish':
    # Contact atlases are authored only after inspecting the small material study.
    data=json.loads((REV/'masks/manifest.json').read_text(encoding='utf-8'))
    images={}
    for row in data['images']:
        path=REV/row['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
        im=bpy.data.images.load(str(path),check_existing=True);im.name='PM_20_v02_'+row['purpose']+'_'+row['projection']
        im.colorspace_settings.name='Non-Color';im.pack();images[row['purpose'],row['projection']]=im
    def mapped(t,label,im,projection,color=None,metal=None,rough=None,height=None,amount=1.,distance=.000004):
        l=layer(t,label,color,metal,rough,height,amount=amount,distance=distance)
        mask=U.Mask.add_new_mask(l,'Локальная история контакта принятой поверхности','IMAGE','UV',{'side':UV,'top':TOP,'back':'PMBackUV','front':'PMBackUV'}[projection],image=im,socket_input_name='Color')
        U.common.get_mask_tree(mask).nodes[mask.source].extension='CLIP'
        vmask(l,{'side':'PM_SideSurface','top':'PM_TopSurface','back':'PM_BackSurface','front':'PM_FrontSurface'}[projection]);return l
    for key in ('slide','frame','hammer'):
        t=group(materials[key])
        for projection in ('side','top'):
            l=mapped(t,'33 • Маслянистые разводы и контактная полировка — '+projection,images['wear',projection],projection,rough=.30,amount=.48)
            vmask(l,'PM_WearCause')
        H.reconnect(U,t)
    t=group(materials['resin'])
    mapped(t,'32 • Раздельные умеренные потёртости фенопласта',images['resin_polish','side'],'side',(.055,.007,.005),0,.24,amount=.39)
    for key in ('slide','resin','hammer'):
        t=group(materials[key])
        projections=('side','top','back') if key in ('resin','hammer') else ('side','top')
        for projection in projections:
            l=mapped(t,'40 • Масляные отпечатки кожи — '+projection,images['fingerprints',projection],projection,color=(.029,.0024,.0032) if key=='resin' else None,rough=.18 if key!='resin' else .10,amount=.96)
            if key=='slide':vmask(l,'PM_FrontHalf')
            if key=='hammer':vmask(l,'PM_SkinReach')
            U.Mask.add_new_mask(l,'Доступность поверхности для кожи; впадины защищены','AO','Object',UV,ao_distance=.00052)
        H.reconnect(U,t)
    for key in ('frame','slide'):
        t=group(materials[key])
        l=mapped(t,'42 • Следы вытянутого указательного пальца справа',images['index_rest','side'],'side',rough=.21,amount=.90)
        U.Mask.add_new_mask(l,'Доступная боковая поверхность рамки и затвора','AO','Object',UV,ao_distance=.0005)
        H.reconnect(U,t)
    t=group(materials['trigger'])
    for projection in ('side','front'):
        l=mapped(t,'40 • Масляные отпечатки пальца на спуске — '+projection,images['trigger_fingerprints',projection],projection,rough=.18,amount=.95)
        U.Mask.add_new_mask(l,'Контакт кожи со спусковым крючком','AO','Object',UV,ao_distance=.0003)
    H.reconnect(U,t)
    t=group(materials['resin'])
    for projection in ('side','back'):
        l=mapped(t,'43 • Широкие следы ладони и растирания масла — '+projection,images['palms',projection],projection,color=(.014,.0012,.0015),rough=.09,amount=.86)
        U.Mask.add_new_mask(l,'Контакт ладони с выступающими поверхностями','AO','Object',UV,ao_distance=.0005)
    H.reconnect(U,t)

rig['Texture stage']='20% v02: reference-based material revision; prepared for owner review'
rig['PBR revision']='20-v02'
rig['Deferred geometry']='Owner postponed lower left/right lens housing corner defect until after texture acceptance.'
note=bpy.data.texts['ПМ • как смотреть текстуры'];note.clear()
note.write('ПМ / КОРС-9 — состояние 20%, доработка v02\nМатериалы переработаны по новым референсам владельца.\nСтали затвора, рамки, скобы и ствола разделены. Фенопласт полуглянцевый, бордовый.\nПрежняя геометрия v11, гравировка и ручные контролы сохранены.\nСостояния 100/60 не изменялись. Дефект нижних углов корпуса прицела пока отложен.\nНастоящие слои UCUPaint 2.4.9. Это кандидат для проверки владельцем.\n')
for o in bpy.context.selected_objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
S.render.engine='CYCLES'
for im in bpy.data.images:
    if im.type not in ('RENDER_RESULT','COMPOSITING') and not im.packed_file:im.pack()
folder=REV/'work' if MODE=='study' else REV/'candidate';folder.mkdir(parents=True,exist_ok=True)
path=folder/('PM_20_v02_MaterialStudy.blend' if MODE=='study' else 'PM_Textures_20_v02.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(path))
used=set(m for o in bpy.data.objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes)
native=[m.name for m in used if any(n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node for n in m.node_tree.nodes)]
report=dict(condition=20,revision='20-v02',mode=MODE,file=str(path),materials=sorted(native),assignments=assignments,
            source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),geometry_changed=False,
            approved_geometry_sha256=hashlib.sha256((ROOT/'approved/PM_Geometry_v11_APPROVED.blend').read_bytes()).hexdigest(),
            owner_accepted=False,blender=bpy.app.version_string,ucupaint=U.common.get_current_version_str())
(REV/'checks').mkdir(parents=True,exist_ok=True)
(REV/'checks'/('study_authoring.json' if MODE=='study' else 'authoring.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_20_V02_SAVED',path,'native materials',len(native),flush=True)
