"""Native surface/detail revision on saved PM 20-v02; accepted mesh stays intact."""
from pathlib import Path
import sys,ast,json,hashlib,shutil,importlib,importlib.util,math
import bpy,addon_utils,numpy as np
from mathutils import Color,Vector
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing';REV=ROOT/'revision_20_v03'
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/15_Текстуры_v2_20_на_проверку')
ORIGINAL=LIB/'01_ПМ/PM_Textures_20_v02.blend';SOURCE=REV/'approved/PM_20_v02_SOURCE.blend'
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'study';assert MODE in ('study','finish')
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SOURCE.parent.mkdir(parents=True,exist_ok=True)
if not SOURCE.exists():
    entry=next(r for r in json.loads((LIB/'package_manifest.json').read_text(encoding='utf-8'))['files'] if r['file']=='01_ПМ/PM_Textures_20_v02.blend')
    assert digest(ORIGINAL)==entry['sha256'],'Published source changed; inspect it before using'
    shutil.copy2(ORIGINAL,SOURCE)
assert digest(SOURCE)==digest(ORIGINAL)
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint');assert U.common.get_current_version_str()=='2.4.9'
SKILL=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing')
spec=importlib.util.spec_from_file_location('pm_native_helpers',SKILL/'scripts/ucupaint_helpers.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));S=bpy.context.scene;S.frame_set(1)
rig=bpy.data.objects['PM_CONTROLS • select me'];CONDITION=20;UV='PMWearUV'
for k in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[k]=0.
rig.update_tag();bpy.context.view_layer.update()
parsed=ast.parse((PROJECT/'tools/author_pm_pbr.py').read_text(encoding='utf-8'))
for node in parsed.body:
    if isinstance(node,ast.FunctionDef) and node.name in {'layer','noise','vmask','edge'}:exec(compile(ast.Module(body=[node],type_ignores=[]),'native_pm_api','exec'))
base_layer=layer
def layer(*a,**kw):
    l=base_layer(*a,**kw)
    if l.type=='NOISE':l.enable_uniform_scale=False;H.sync_property(U,l,'scale',Vector(kw.get('stretch',(1,1,1))))
    return l
base_noise=noise
def noise(*a,**kw):
    m=base_noise(*a,**kw);H.sync_property(U,m,'translation',Vector(m.translation));return m
def native(m):return next(n for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node)
def channels(l,values,distance=.000004):
    for root,c in zip(l.id_data.yp.channels,l.channels):
        value=values.get(root.name);c.enable=value is not None
        if value is None:continue
        if value!='source':
            c.override=True;c.override_type='DEFAULT';H.sync_property(U,c,'override_color' if root.type=='RGB' else 'override_value',Color(value) if root.type=='RGB' else value)
        if root.type=='NORMAL':H.sync_property(U,c,'bump_distance',distance);H.sync_property(U,c,'bump_midlevel',.5)
def data_layer(t,label,im,values,amount=1.,distance=.000004,uv='PMDetailUV'):
    l=U.Layer.add_new_layer(t,label,'IMAGE',-1,'MIX','OVERLAY','BUMP_MAP','UV',uv,image=im,use_designated_idx=True,designated_index=0)
    channels(l,values,distance);H.sync_property(U,l,'intensity_value',amount);return l
def image_mask(l,im,uv='PMDetailUV'):
    return U.Mask.add_new_mask(l,'Физический рисунок отдельных частиц / дефектов','IMAGE','UV',uv,image=im,socket_input_name='Color')
def cavity(l):
    vmask(l,'PM_CutReservoir')
    vmask(l,'PM_CutFace')
    m=U.Mask.add_new_mask(l,'Укрытые сопряжения стенок настоящих вырезов','AO','Object',UV,ao_distance=.00048)
    importlib.import_module(U.__name__+'.MaskModifier').add_new_mask_modifier(m,'INVERT')
    return m

details=json.loads((PROJECT/'_asset_src/pm_refinement/review_v11/Проверки/repairs_geometry.json').read_text(encoding='utf-8'))
hc=np.asarray(details['hammer']['center_xz_mm']);riginv=np.asarray(rig.matrix_world.inverted(),dtype=np.float32)
def physical_attributes(o):
    me=o.data;count=len(me.vertices);raw=np.empty(count*3,np.float32);me.vertices.foreach_get('co',raw)
    mw=np.asarray(o.matrix_world,np.float32);world=(raw.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]);mm=world*1000
    local=world@riginv[:3,:3].T+riginv[:3,3];x,y,z=mm.T
    cavity_mask=np.zeros(count);mould=np.zeros(count);exposed=np.ones(count)
    if o.name.startswith('Slide |'):
        phase=(local[:,0]+np.tan(.205)*(local[:,2]-1.310)-.175)/.034
        nearest=np.rint(phase);distance=np.abs(phase-nearest)*.034*abs(rig.scale.x)*1000
        cavity_mask=np.clip((.62-distance)/.18,0,1)*np.clip((13.35-np.abs(y))/.66,0,1)*((nearest>=0)&(nearest<=12)&(z>97)&(z<117)&(np.abs(local[:,1])>.1537))
    elif o.name.startswith('Hammer |'):
        delta=mm[:,[0,2]]-hc;radius=np.linalg.norm(delta,axis=1);angles=np.arctan2(delta[:,1],delta[:,0])
        for row in details['hammer']['grooves']:
            diff=np.abs((angles-math.radians(row['angle_deg'])+np.pi)%(2*np.pi)-np.pi)
            field=np.clip((math.radians(6.4)-diff)/math.radians(1.6),0,1)*np.clip((row['radius_mm']-.32-radius)/.80,0,1)*(radius>2.5)
            cavity_mask=np.maximum(cavity_mask,field)
    elif o.name.startswith(('Bakelite |','Grip ','Lanyard |')):
        mould=.18+.65*np.exp(-((x-45)/23)**2-((z-70)/15)**2)+.4*np.exp(-((x-65)/16)**2-((z-28)/23)**2)
    if o.name.startswith('Frame |'):
        # Recessed lettering is protected compared to the external frame edges.
        for row in json.loads((PROJECT/'_asset_src/pm_refinement/review_v11/Проверки/engraving.json').read_text(encoding='utf-8'))['markings']:
            if row['host']!=o.name:continue
            cutter=bpy.data.objects[row['cutter']];corners=np.asarray([tuple(cutter.matrix_world@Vector(v)) for v in cutter.bound_box])*1000
            lo=corners.min(axis=0);hi=corners.max(axis=0);cx,cz=(lo[[0,2]]+hi[[0,2]])*.5
            g=np.exp(-((x-cx)/max(2,(hi[0]-lo[0])*.75))**4-((z-cz)/max(2,(hi[2]-lo[2])*.9))**4)
            exposed=np.minimum(exposed,1-.90*g)
    idx=np.empty(len(me.loops),np.int32);me.loops.foreach_get('vertex_index',idx)
    polygon_index=np.empty(len(me.loops),np.int32)
    centers=np.empty(len(me.polygons)*3,np.float32);me.polygons.foreach_get('center',centers)
    centers_world=centers.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]
    centers_local=centers_world@riginv[:3,:3].T+riginv[:3,3]
    pn=np.empty(len(me.polygons)*3,np.float32);me.polygons.foreach_get('normal',pn)
    pn=pn.reshape(-1,3)@np.linalg.pinv(mw[:3,:3]);pn/=np.maximum(np.linalg.norm(pn,axis=1)[:,None],1.e-8)
    for f in me.polygons:polygon_index[f.loop_start:f.loop_start+f.loop_total]=f.index
    cut_faces=np.zeros(len(me.polygons))
    if o.name.startswith('Slide |'):
        cy=np.abs(centers_local[:,1]);cz=centers_world[:,2]*1000
        cut_faces=((cy>.1537)&(cy<.162)&(cz>97)&(cz<116)).astype(np.float32)
    elif o.name.startswith('Hammer |'):
        cut_faces=(np.abs(pn[:,1])<.55).astype(np.float32)
    if o.name.startswith(('Slide |','Hammer |')):
        ca=me.color_attributes.get('PM_CutFace') or me.color_attributes.new(name='PM_CutFace',type='BYTE_COLOR',domain='CORNER')
        vals=np.ones((len(idx),4),np.float32);vals[:,:3]=cut_faces[polygon_index,None];ca.data.foreach_set('color',vals.ravel())
    uv_values=np.column_stack((x/20+(y>0)*.187,z/20+(y>0)*.367))
    if o.name.startswith('Hammer |'):
        theta=np.arctan2(z-hc[1],x-hc[0]);radius=np.hypot(z-hc[1],x-hc[0]);uv_values=np.column_stack((theta*4.42/20,(y+5)/20))
    uv=me.uv_layers.get('PMDetailUV') or me.uv_layers.new(name='PMDetailUV');uv.data.foreach_set('uv',np.asarray(uv_values[idx],np.float32).ravel())
    if o.name.startswith('Hammer |'):
        values=uv_values[idx].copy()
        # Caps, radial walls and cylindrical floors each need a nondegenerate
        # two-dimensional physical projection, chosen per real polygon.
        for f in me.polygons:
            sl=slice(f.loop_start,f.loop_start+f.loop_total);vi=idx[sl];n=pn[f.index]
            if abs(n[1])>.55:values[sl]=np.column_stack((x[vi]/20,z[vi]/20))
            else:
                c=centers_world[f.index]*1000;rad=Vector((c[0]-hc[0],c[2]-hc[1])).normalized()
                if abs(n[0]*rad.x+n[2]*rad.y)<.55:values[sl]=np.column_stack((radius[vi]/20,(y[vi]+5)/20))
        uv.data.foreach_set('uv',np.asarray(values,np.float32).ravel())
    for name,field in [('PM_CutReservoir',cavity_mask),('PM_MouldRelief',np.clip(mould,0,1)),('PM_EdgeExposure',exposed)]:
        a=me.color_attributes.get(name) or me.color_attributes.new(name=name,type='BYTE_COLOR',domain='POINT');v=np.ones((count,4),np.float32);v[:,:3]=field[:,None];a.data.foreach_set('color',v.ravel())
    me.update();return float(np.max(cavity_mask)),int(np.count_nonzero(cavity_mask>.25))

selected=[];attribute_report={}
for o in bpy.data.objects:
    if o.type!='MESH' or o.name.startswith(('Studio','Reference','Animation','Suppressor')):continue
    if any(m and m.name.startswith('ПМ • 20 •') for m in o.data.materials):
        selected.append(o);attribute_report[o.name]=physical_attributes(o)
used={m for o in selected for m in o.data.materials if m and m.name.startswith('ПМ • 20 •')}
maps=json.loads((REV/'maps/manifest.json').read_text(encoding='utf-8'));images={}
for row in maps['images']:
    path=REV/row['file'];assert digest(path)==row['sha256'];im=bpy.data.images.load(str(path),check_existing=True);im.name=f"PM_20_v03_{row['kind']}_{row['purpose']}";im.colorspace_settings.name='Non-Color';im.pack();images[row['kind'],row['purpose']]=im
alpha_images={}
for row in maps['alpha_sources']:
    im=bpy.data.images.load(str(REV/row['copied_file']),check_existing=True);im.name=f"PM_20_v03_owner_alpha_{row['index']}";im.colorspace_settings.name='Non-Color';im.pack();alpha_images[row['index']]=im

for m in sorted(used,key=lambda m:m.name):
    # Native layer creation uses the active mesh/material for UV and vcol setup.
    owner=next(o for o in selected if m in list(o.data.materials))
    bpy.context.view_layer.objects.active=owner;owner.active_material_index=list(owner.data.materials).index(m)
    t=native(m).node_tree;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    resin='фенопласт' in m.name;metal=any(word in m.name for word in ('затвор','рамка','скобы','спуска','курка','воронё','анодирован','крепёж'))
    if resin:
        p.inputs['Coat Weight'].default_value=.40
        m.node_tree.links.new(native(m).outputs['Normal'],p.inputs['Coat Normal'])
        base=next(l for l in t.yp.layers if l.name.startswith('00 •'));ri=next(i for i,c in enumerate(t.yp.channels) if c.name=='Roughness');H.sync_property(U,base.channels[ri],'override_value',.18)
        l=layer(t,'60 • Неровности пресс-формы, 3–8 мм',height='source',kind='NOISE',scale=18,distance=.00045,amount=.78,stretch=(.8,1,1.45));vmask(l,'PM_MouldRelief')
        l=layer(t,'61 • Редкие положительные наплывы формовки',height=.66,distance=.00090,amount=.78);vmask(l,'PM_MouldRelief');noise(l,'Нерегулярные локальные наплывы',35,.52,.72)
        l=layer(t,'62 • Мелкая плотная фактура прессованной смолы',height='source',kind='NOISE',scale=1250,distance=.000006,amount=.58)
        # Resin remains dielectric; wear never reveals silver metal.
    elif metal:
        for l in t.yp.layers:
            if l.name.startswith('31 • Прерывистые'):l.enable=False
        layer(t,'60 • Мелкая шероховатость обработанного металла',height='source',kind='NOISE',scale=650,distance=.000010 if 'затвор' in m.name else .000007,amount=.78)
        l=data_layer(t,'61 • Редкие небольшие раковины стали',images['pits','height'],{'Normal':'source'},.68,.00014)
        image_mask(l,images['pits','footprint'])
        l=layer(t,'62 • Затёртые до стали открытые острые кромки',(.19,.21,.23),1,.31,height=.485,amount=.75,distance=.000014)
        edge(l,.00027);vmask(l,'PM_EdgeExposure');noise(l,'Прерывистый контакт и отдельные угловые сколы',1150,.42,.67)
        l=layer(t,'63 • Отдельные сколы тёмного защитного слоя',(.26,.28,.30),1,.40,height=.44,amount=.82,distance=.000020)
        edge(l,.00065);vmask(l,'PM_EdgeExposure');image_mask(l,alpha_images[38]);noise(l,'Нерегулярный разрыв края износа',490,.38,.68)
        if 'затвор' in m.name or 'курка' in m.name:
            l=layer(t,'70 • Уплотнённый тёмный осадок в вырезах',(.035,.025,.015),0,.84,height=.55,amount=.68,distance=.000040);cavity(l);image_mask(l,alpha_images[21]);noise(l,'Неравномерное накопление в защищённых углублениях',780,.26,.71)
            l=layer(t,'71 • Тонкая сухая пыль в насечках',(.090,.072,.043),0,.89,height=.54,amount=.48,distance=.000020);cavity(l);image_mask(l,alpha_images[18])
            l=data_layer(t,'72 • Частицы кожи, пыли и грязи в насечках',images['particles','height'],{'Color':(.24,.20,.13),'Metallic':0,'Roughness':.88,'Normal':'source'},.92,.00014)
            image_mask(l,images['particles','footprint']);vmask(l,'PM_CutReservoir');vmask(l,'PM_CutFace')
        # Thin clear oil response follows the editable native Roughness output.
        # Dry rough deposits consequently receive no clear film.
        g=native(m);remap=m.node_tree.nodes.new('ShaderNodeMapRange');remap.label='Тонкая прозрачная масляная плёнка';remap.inputs['From Min'].default_value=.23;remap.inputs['From Max'].default_value=.43;remap.inputs['To Min'].default_value=.18;remap.inputs['To Max'].default_value=0;remap.clamp=True
        m.node_tree.links.new(g.outputs['Roughness'],remap.inputs['Value']);m.node_tree.links.new(remap.outputs['Result'],p.inputs['Coat Weight']);p.inputs['Coat IOR'].default_value=1.46;p.inputs['Coat Roughness'].default_value=.14
        m.node_tree.links.new(g.outputs['Normal'],p.inputs['Coat Normal'])
    else:continue
    m['Surface revision']='20-v03';H.reconnect(U,t)

rig['PBR revision']='20-v03';rig['Texture stage']='20% v03: mould relief, steel microstructure, edge wear and protected deposits; owner review'
note=bpy.data.texts['ПМ • как смотреть текстуры'];note.clear();note.write('ПМ / КОРС-9 — 20%, текстуры v03\nРельеф формовки фенопласта и более чёткий глянец.\nМелкая шероховатость стали, редкие раковины, износ до металла на острых кромках.\nЧастицы кожи/пыли/грязи в настоящих насечках затвора и курка.\nОтпечатки пальцев и ладоней v02 сохранены. Принятая форма v11 и риг сохранены.\nДефект нижних углов корпуса прицела остаётся отложенным. Только 20%, кандидат для проверки.\n')
for o in bpy.context.selected_objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig;S.render.engine='CYCLES'
folder=REV/('work' if MODE=='study' else 'candidate');folder.mkdir(parents=True,exist_ok=True)
path=folder/('PM_20_v03_MaterialStudy.blend' if MODE=='study' else 'PM_Textures_20_v03.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(path))
all_used={m for o in bpy.data.objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes}
names=[m.name for m in all_used if any(n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node for n in m.node_tree.nodes)]
(REV/'checks').mkdir(parents=True,exist_ok=True)
report=dict(condition=20,revision='20-v03',file=str(path),materials=sorted(names),source=str(ORIGINAL),source_sha256=digest(ORIGINAL),geometry_changed=False,owner_accepted=False,attribute_regions=attribute_report,physical_map_manifest=str(REV/'maps/manifest.json'))
(REV/'checks/authoring.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_20_V03_SAVED',path,'cavity regions',[(n,v) for n,v in attribute_report.items() if v[0]>0],flush=True)
