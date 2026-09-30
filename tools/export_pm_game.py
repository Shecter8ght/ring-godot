"""Blender CLI: сохранённый PM v5 -> игровая копия и glb, без изменения исходника.

blender --factory-startup --background PM_Highpoly_v5.blend --python tools/export_pm_game.py -- --output DIR
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys, time
from pathlib import Path
import bpy, bmesh
from mathutils import Matrix, Vector

ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--skip-bake',action='store_true')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=Path(args.output).resolve();OUT.mkdir(parents=True,exist_ok=True)
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
root_src=bpy.data.objects['PM_CONTROLS • select me']
originals=list(bpy.data.objects);dg=bpy.context.evaluated_depsgraph_get()
game_collection=bpy.data.collections.new('PM_GAME');scene.collection.children.link(game_collection)
source_pivots={key:bpy.data.objects[name].matrix_world.translation.copy() for key,name in {'Trigger':'Trigger • pivot','Hammer':'Hammer • pivot','Safety':'Safety • pivot','Suppressor':'Suppressor • removal'}.items()}
# Равномерная корректировка длины по заданию 161 мм; высота и ширина сохранены.
SX=161.0/161.5
GRIP=Vector((.0495,0,.0495))
MAP=Matrix(((0,-1,0,0),(SX,0,0,-GRIP.x*SX),(0,0,1,-GRIP.z),(0,0,0,1)))
def point(v): return MAP@Vector(v)
def log(text): print('PM_EXPORT: '+text,flush=True)
def tri(o): o.data.calc_loop_triangles();return len(o.data.loop_triangles)
def active(o):
    bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.hide_viewport=False;o.hide_render=False;o.select_set(True);bpy.context.view_layer.objects.active=o
def clean_poles(o):
    # Нулевая точка lathe содержит совпадающие вершины: Decimate иначе оставляет веер.
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-8)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-10)
    bm.to_mesh(o.data);bm.free();o.data.validate(clean_customdata=False);o.data.update()
def decimate(o,budget):
    n=tri(o)
    if n<=budget:return
    active(o);m=o.modifiers.new('Game topology budget','DECIMATE');m.ratio=max(.00005,budget/n);m.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=m.name)
    if tri(o)>budget*1.07:
        m=o.modifiers.new('Final budget','DECIMATE');m.ratio=budget/tri(o);m.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=m.name)

def owner(o):
    p=o.parent
    while p:
        if p.name=='Safety • pivot':return 'Safety'
        if p.name=='Slide • translation':return 'Slide'
        if p.name=='Hammer • pivot':return 'Hammer'
        if p.name=='Trigger • pivot':return 'Trigger'
        if p.name.startswith('Magazine round'):return 'Rounds'
        if p.name=='Magazine • extraction':return 'Magazine'
        if p.name=='Suppressor • removal':return 'Suppressor'
        p=p.parent
    if o.name.startswith('Barrel |'):return 'Barrel'
    if o.name.startswith(('Slide catch |','Catch |')):return 'SlideStop'
    return 'Frame'

def round_number(o):
    p=o.parent
    while p:
        if p.name.startswith('Magazine round'):
            return int(p.name.removeprefix('Magazine round').strip())
        p=p.parent
    return 0

def budget(o):
    n=o.name
    if n=='Bakelite | one-piece rounded grip':return 5400
    if n.startswith('Slide | continuous'):return 5500
    if n.startswith('Frame | traced'):return 3200
    if n.startswith('Trigger guard'):return 1000
    if n.startswith('Muzzle | circular'):return 1000
    if n.startswith('Muzzle | recessed'):return 480
    if n.startswith('Slide | curved'):return 300
    if n.startswith('Barrel |'):return 640
    if n.startswith('Suppressor | continuous'):return 900
    if n.startswith('Suppressor | central'):return 750
    if n.startswith('Suppressor | eccentric'):return 500
    if n.startswith('Suppressor | aperture'):return 350
    if n.startswith('Suppressor | short'):return 350
    if n.startswith('Suppressor | fine'):return 96
    if 'brass outer case' in n:return 150
    if 'rounded copper nose' in n:return 96
    if 'primer disk' in n:return 24
    if n.startswith('Magazine | parallel'):return 1200
    if n.startswith('Magazine | decorative'):return 220
    if n.startswith('Hammer |'):return 700
    if n.startswith('Trigger |'):return 450
    if n.startswith('Safety | slim'):return 250
    if n.startswith('Safety | rounded pivot'):return 120
    if n.startswith('Safety | raised'):return 120
    if n.startswith('Bakelite | moulded star'):return 220
    if n.startswith('Bakelite |'):return 160
    if n.startswith('Rear sight | continuous'):return 350
    if n.startswith('Front sight |'):return 200
    if n.startswith(('Luminous point','Sight socket')):return 48
    if n.startswith(('Grip |','Backstrap |')):return 100
    if n.startswith(('Frame pin','Pin centre')):return 40
    if n.startswith('Frame | lanyard'):return 120
    if n.startswith('Slide catch'):return 220
    return min(tri(o) if o.type=='MESH' else 1000,96)

low=[];records=[];detail_sources=[]
for o in originals:
    if o.type not in ('MESH','CURVE','FONT') or not o.parent:continue
    if o.name.startswith('Animation |'):continue
    if o.name.startswith(('Highpoly | clean diamond','Highpoly | visible crossed')):
        detail_sources.append(o);continue
    e=o.evaluated_get(dg);me=bpy.data.meshes.new_from_object(e,preserve_all_data_layers=True,depsgraph=dg)
    q=bpy.data.objects.new('GAME_'+o.name,me);game_collection.objects.link(q);q.matrix_world=o.matrix_world.copy()
    q['owner']=owner(o);q['source_name']=o.name;q['round_number']=round_number(o)
    if q['round_number']:clean_poles(q)
    decimate(q,budget(o));low.append(q);records.append({'source':o.name,'owner':q['owner'],'triangles':tri(q)})
    log(o.name+' -> '+str(tri(q)))

log('UV atlas '+str(sum(tri(o) for o in low))+' triangles')
for o in low:
    for m in o.data.materials:
        if m and not m.get('pm_bake_copy'):
            pass
# Копии материалов не меняют исходную сцену и дают общую текстуру атласа.
material_copies={}
for o in low:
    for i,m in enumerate(o.data.materials):
        if m:
            if m.name not in material_copies:
                cp=m.copy();cp.name='GAME_'+m.name;cp['pm_bake_copy']=True;material_copies[m.name]=cp
            o.data.materials[i]=material_copies[m.name]
bpy.ops.object.select_all(action='DESELECT')
for o in low:o.select_set(True)
bpy.context.view_layer.objects.active=low[0]
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.002,area_weight=.3)
bpy.ops.object.mode_set(mode='OBJECT')

size=2048
base=bpy.data.images.new('PM_BaseColor',width=size,height=size,alpha=False)
rough=bpy.data.images.new('PM_Roughness',width=size,height=size,alpha=False);rough.colorspace_settings.name='Non-Color'
normal=bpy.data.images.new('PM_Normal',width=size,height=size,alpha=False);normal.colorspace_settings.name='Non-Color'
metal=bpy.data.images.new('PM_Metallic',width=size,height=size,alpha=False);metal.colorspace_settings.name='Non-Color'
normal.generated_color=(.5,.5,1,1)

if not args.skip_bake:
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8;scene.cycles.use_denoising=False
    scene.render.bake.margin=8;scene.render.bake.normal_space='TANGENT';scene.render.bake.use_clear=True;scene.render.bake.use_selected_to_active=False
    # Только выбранные игровые сетки запекаются; студия не влияет на EMIT/normal.
    for o in originals:o.hide_render=True
    bake_nodes={};saved_links={};principled={}
    for m in material_copies.values():
        nt=m.node_tree;bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED');out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');principled[m.name]=bs
        tex=nt.nodes.new('ShaderNodeTexImage');tex.image=base;nt.nodes.active=tex;bake_nodes[m.name]=tex
        emit=nt.nodes.new('ShaderNodeEmission');saved_links[m.name]=(out,emit)
    def select_low():
        bpy.ops.object.select_all(action='DESELECT')
        for o in low:o.select_set(True);o.hide_render=False
        bpy.context.view_layer.objects.active=low[0]
    for channel,im in [('Base Color',base),('Roughness',rough),('Metallic',metal)]:
        for m in material_copies.values():
            nt=m.node_tree;bs=principled[m.name];out,emit=saved_links[m.name];inp=bs.inputs[channel]
            for link in list(emit.inputs['Color'].links):nt.links.remove(link)
            if inp.is_linked:nt.links.new(inp.links[0].from_socket,emit.inputs['Color'])
            else:
                value=inp.default_value
                emit.inputs['Color'].default_value=tuple(value) if channel=='Base Color' else (value,value,value,1)
            nt.links.new(emit.outputs[0],out.inputs['Surface']);bake_nodes[m.name].image=im;nt.nodes.active=bake_nodes[m.name]
        select_low();log('Bake '+channel);bpy.ops.object.bake(type='EMIT')
    for m in material_copies.values():
        nt=m.node_tree;out,emit=saved_links[m.name];nt.links.new(principled[m.name].outputs['BSDF'],out.inputs['Surface']);bake_nodes[m.name].image=normal;nt.nodes.active=bake_nodes[m.name]
    select_low();log('Bake shader normals');bpy.ops.object.bake(type='NORMAL')
    scene.render.bake.use_selected_to_active=True;scene.render.bake.use_clear=False;scene.render.bake.cage_extrusion=.0015
    # Перенос рельефа ромбов и накатки из настоящей highpoly-геометрии.
    for prefix,src_prefix in [('Bakelite | one-piece rounded grip','Highpoly | clean diamond'),('Suppressor | central knurled sleeve','Highpoly | visible crossed')]:
        target=next(o for o in low if o['source_name']==prefix)
        highs=[o for o in originals if o.name==prefix or o.name.startswith(src_prefix)]
        # cage_extrusion задаётся в локальных единицах; root исходника имеет scale ~0.08.
        # Переводим нужные 1.5 мм в пространство активной lowpoly-сетки.
        scene.render.bake.cage_extrusion=.0015/min(abs(v) for v in target.matrix_world.to_scale())
        active(target)
        for o in highs:o.hide_render=False;o.hide_set(False);o.select_set(True)
        log('Bake highpoly detail '+prefix);bpy.ops.object.bake(type='NORMAL')
        for o in highs:o.hide_render=True
    scene.render.bake.use_selected_to_active=False

# Итоговые glTF-совместимые Principled: атлас цвета, ORM и tangent normal.
import numpy as np
orm=bpy.data.images.new('PM_ORM',width=size,height=size,alpha=False);orm.colorspace_settings.name='Non-Color'
r=np.asarray(rough.pixels[:],dtype=np.float32).reshape(-1,4);m=np.asarray(metal.pixels[:],dtype=np.float32).reshape(-1,4)
packed=np.ones_like(r);packed[:,1]=r[:,0];packed[:,2]=m[:,0];orm.pixels.foreach_set(packed.reshape(-1));orm.update()
for name,im in [('pm_base_color.png',base),('pm_normal.png',normal),('pm_orm.png',orm)]:
    im.filepath_raw=str(OUT/name);im.file_format='PNG';im.save();im.pack()
for material in material_copies.values():
    old=principled[material.name] if not args.skip_bake else next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    emission=list(old.inputs['Emission Color'].default_value);strength=old.inputs['Emission Strength'].default_value
    nt=material.node_tree;nt.nodes.clear();bs=nt.nodes.new('ShaderNodeBsdfPrincipled');out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    t=nt.nodes.new('ShaderNodeTexImage');t.image=base;nt.links.new(t.outputs['Color'],bs.inputs['Base Color'])
    t=nt.nodes.new('ShaderNodeTexImage');t.image=orm;sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(t.outputs['Color'],sep.inputs[0]);nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
    t=nt.nodes.new('ShaderNodeTexImage');t.image=normal;nm=nt.nodes.new('ShaderNodeNormalMap');nt.links.new(t.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs[0],bs.inputs['Normal'])
    bs.inputs['Emission Color'].default_value=emission;bs.inputs['Emission Strength'].default_value=strength

def empty(name,parent=None,world=None):
    o=bpy.data.objects.new(name,None);game_collection.objects.link(o);o.empty_display_size=.008
    o.parent=parent;o.location=Vector(world) if world is not None else Vector((0,0,0))
    # До чтения matrix_world новая пустышка должна пройти depsgraph update.
    bpy.context.view_layer.update();return o
PM=empty('PM');PM['asset_id']='wpn_hg_01';PM['units']='metres';PM['source_sha256']=SOURCE_HASH
pivots={'Frame':GRIP,'Slide':GRIP,'Barrel':Vector((-.07985524,0,.11253256)),'Trigger':source_pivots['Trigger'],'Hammer':source_pivots['Hammer'],'Safety':source_pivots['Safety'],'SlideStop':Vector((.023, -.011,.091)),'MagCatch':Vector((.066,0,.0085)),'Magazine':Vector((.042,0,.081)),'Suppressor':Vector((-.08065,0,.11253256))}
groups={key:empty(key,None,point(pos)) for key,pos in pivots.items()}
for key,o in groups.items():
    mw=o.matrix_world.copy();o.parent=groups['Slide'] if key=='Safety' else PM;o.matrix_world=mw;o['part']=key
round_group=empty('Rounds',groups['Magazine'])
bpy.context.view_layer.update()
for o in low:
    world=o.matrix_world.copy();o.data.transform(MAP@world);o.matrix_world=Matrix.Identity(4)
    parent=round_group if o['owner']=='Rounds' else groups[o['owner']]
    o.data.transform(parent.matrix_world.inverted());o.parent=parent;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Identity(4)
    o.name=o['source_name'].replace(' | ','_').replace(' • ','_').replace(' ','_').replace('·','')
    # Меши уже содержат applied evaluated-модификаторы; никакого driver/action в игре.
    o.animation_data_clear()

# В исходном демонстрационном ассете защёлка пятки не была выделена; отдельная малая деталь.
bpy.ops.mesh.primitive_cube_add(size=1,location=point((.067,0,.0065)))
latch=bpy.context.object;latch.name='MagCatch_Latch';latch.dimensions=(.008,.003,.0025)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bev=latch.modifiers.new('Latch edge radius','BEVEL');bev.width=.00045;bev.segments=2;bpy.ops.object.modifier_apply(modifier=bev.name)
material=bpy.data.materials.new('PM_Latch_Steel');material.use_nodes=True;bs=material.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.035,.042,.048,1);bs.inputs['Metallic'].default_value=.85;bs.inputs['Roughness'].default_value=.3;latch.data.materials.append(material)
mw=latch.matrix_world.copy();latch.parent=groups['MagCatch'];latch.matrix_world=mw
for c in list(latch.users_collection):c.objects.unlink(latch)
game_collection.objects.link(latch);low.append(latch)

def join_owner(key,objs):
    if not objs:return
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();objs[0].name=key+'_Mesh'
    return objs[0]
meshes=[]
for key in groups:
    objs=[o for o in low if o.parent==groups[key]]
    # Join удаляет все выбранные объекты кроме active: убираем ссылки до операции.
    low=[o for o in low if o not in objs];q=join_owner(key,objs)
    if q:meshes.append(q)
# Каждый патрон остаётся отдельным дочерним Mesh у Rounds: риг скрывает их поштучно.
# Источник пронумерован от нижнего к верхнему патрону; такой порядок нужен и игре.
for number in range(1,9):
    objs=[o for o in low if o.parent==round_group and o['round_number']==number]
    low=[o for o in low if o not in objs];q=join_owner(f'Round_{number:02}',objs)
    if not q:raise RuntimeError(f'Не найден игровой патрон {number}')
    q.name=f'Round_{number:02}';q['round_number']=number;meshes.append(q)
# Укоротить только задний торец визуального ствола до 93 мм, дульный срез сохранён.
barrel=next(o for o in meshes if o.parent==groups['Barrel'])
worldverts=[barrel.matrix_world@v.co for v in barrel.data.vertices];ymin=min(v.y for v in worldverts);ymax=max(v.y for v in worldverts)
for v in barrel.data.vertices:
    w=barrel.matrix_world@v.co;w.y=ymin+(w.y-ymin)*(.093/(ymax-ymin));v.co=barrel.matrix_world.inverted()@w

marker_positions={'Muzzle':(-.08172864,0,.11253256),'MuzzleSuppressed':(-.2402039,0,.11253256),'SightFront':(-.0727,0,.12675),'SightRear':(.0614,0,.12675)}
for name,pos in marker_positions.items():
    p=groups['Slide'] if name.startswith('Sight') else PM
    o=empty(name,None,point(pos));mw=o.matrix_world.copy();o.parent=p;o.matrix_world=mw
lodroot=empty('PM_LOD1',PM);lodgroups={}
for key,source in groups.items():
    o=source.copy();o.name=key+'_LOD1';game_collection.objects.link(o);lodgroups[key]=o
for key,o in lodgroups.items():
    mw=groups[key].matrix_world.copy();o.parent=lodgroups['Slide'] if key=='Safety' else lodroot;o.matrix_world=mw
lodrounds=empty('Rounds_LOD1',lodgroups['Magazine'])
lodmeshes=[]
total=sum(tri(o) for o in meshes)
for source in meshes:
    o=source.copy();o.data=source.data.copy();game_collection.objects.link(o);o.name=source.name+'_LOD1'
    mw=source.matrix_world.copy();o.parent=lodrounds if source.parent==round_group else lodgroups[source.parent.name];o.matrix_world=mw
    # Бюджет всего LOD < 5k, включая опциональный глушитель и патроны.
    clean_poles(o);decimate(o,max(16,int(tri(source)*4200/total)));o.data.validate(clean_customdata=False);lodmeshes.append(o)

for o in list(originals):bpy.data.objects.remove(o,do_unlink=True)
for a in list(bpy.data.actions):
    if a.users==0:bpy.data.actions.remove(a)
bpy.ops.outliner.orphans_purge(do_recursive=True)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1.0;scene.frame_start=1;scene.frame_end=1;scene.frame_set(1)
scene.camera=None;bpy.ops.object.select_all(action='DESELECT')
for o in game_collection.objects:o.select_set(True);o.hide_render=False;o.hide_set(False)
bpy.context.view_layer.objects.active=PM
save=OUT/'PM_Highpoly_v5_game.blend';bpy.ops.wm.save_as_mainfile(filepath=str(save))
bpy.ops.export_scene.gltf(filepath=str(OUT/'pm.glb'),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False)
def gltf(v):return [v.x,v.z,-v.y]
bounds={}
for label,items in [('base',[o for o in meshes if o.parent!=groups['Suppressor']]),('with_suppressor',meshes)]:
    vs=[o.matrix_world@v.co for o in items for v in o.data.vertices];lo=Vector([min(v[i] for v in vs) for i in range(3)]);hi=Vector([max(v[i] for v in vs) for i in range(3)]);bounds[label]={'min_blender':list(lo),'max_blender':list(hi),'size_gltf_mm':[(hi.x-lo.x)*1000,(hi.z-lo.z)*1000,(hi.y-lo.y)*1000]}
report={'schema_version':1,'source':str(SOURCE),'source_sha256_before':SOURCE_HASH,'source_sha256_after':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'rest_frame':1,'root':'PM','lod_root':'PM_LOD1','axes':'+Z muzzle, +Y up, -X shooter right','triangles':{'first_person':sum(tri(o) for o in meshes),'third_person':sum(tri(o) for o in lodmeshes)},'bounds':bounds,'joints':{key:{'position_gltf_m':gltf(o.matrix_world.translation),'rotation_axis_gltf':[1,0,0]} for key,o in groups.items()},'markers_gltf_m':{name:gltf(bpy.data.objects[name].matrix_world.translation) for name in marker_positions},'magazine_extract_direction':[0,-.9903,-.139],'barrel_length_m':.093,'baked_maps':['pm_base_color.png','pm_normal.png','pm_orm.png'],'source_reductions':records,'notes':['Artist-authored exterior animation asset, not engineering geometry.','Grip markers omitted: existing pistol grip profile is used.','Heel latch is a small new separate game detail.']}
report_path=OUT/'export_manifest.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
log(json.dumps(report['triangles'])+' saved '+str(OUT/'pm.glb'))
assert report['source_sha256_before']==report['source_sha256_after']
assert report['triangles']['first_person']<=40000,report['triangles']
assert report['triangles']['third_person']<=5000,report['triangles']
