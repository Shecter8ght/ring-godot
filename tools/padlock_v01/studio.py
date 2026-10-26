"""Owner-requested viewing studio. Only lights animate; the reviewed prop is untouched."""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['build','render','verify'])
parser.add_argument('--frame',type=int,default=74);parser.add_argument('--size',type=int,default=1500)
parser.add_argument('--samples',type=int,default=128)
parser.add_argument('--eevee-check',action='store_true')
parser.add_argument('--root',default=str(WORK))
parser.add_argument('--report-name',default='studio_v03.json')
parser.add_argument('--revision',choices=['v03','v04'],default='v03')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
root=Path(args.root);path=root/'models'/('padlock_'+args.revision+'_studio.blend')
if args.revision=='v04' and args.report_name=='studio_v03.json':args.report_name='studio_v04.json'

def aim(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def collection(name):
    col=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(col);return col

def move(obj,col):
    for old in tuple(obj.users_collection):old.objects.unlink(obj)
    col.objects.link(obj)

def area(name,position,target,energy,size_x,size_y,color,col,parent=None):
    data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='RECTANGLE'
    data.size=size_x;data.size_y=size_y;data.color=color
    obj=bpy.data.objects.new(name,data);col.objects.link(obj);obj.location=position
    aim(obj,target)
    if parent:obj.parent=parent
    return obj

def surface(name,color,roughness,grain):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    nodes=mat.node_tree.nodes;links=mat.node_tree.links
    bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value=(*color,1);bsdf.inputs['Roughness'].default_value=roughness
    tex=nodes.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=1100
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.24
    bump.inputs['Distance'].default_value=grain
    links.new(tex.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    return mat

def build():
    source=root/'models'/('padlock_'+args.revision+'_textured.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.context.scene
    for obj in list(bpy.data.objects):
        if obj.type in {'LIGHT','CAMERA'} or obj.name=='Studio_ground':bpy.data.objects.remove(obj,do_unlink=True)
    stage=collection('СТУДИЯ · подиум и фон')
    lights=collection('СВЕТ · статичный')
    moving=collection('БЛИК · анимация 1–240')
    cameras=collection('КАМЕРЫ · общий вид и детали')
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,-.0055))
    plinth=bpy.context.object;plinth.name='Графитовый подиум';plinth.dimensions=(.182,.132,.011)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    move(plinth,stage)
    bevel=plinth.modifiers.new('Мягкий край подиума','BEVEL');bevel.width=.0018;bevel.segments=6
    plinth.data.materials.append(surface('Графит · сатиновый камень',(.021,.026,.034),.46,.000018))
    for face in plinth.data.polygons:face.use_smooth=True
    weighted=plinth.modifiers.new('Плоские большие поверхности','WEIGHTED_NORMAL')
    weighted.keep_sharp=True
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.0111))
    floor=bpy.context.object;floor.name='Бесшовный тёмный фон';move(floor,stage)
    floor.data.materials.append(surface('Фон · угольный',(.009,.013,.020),.72,.000012))
    world=bpy.data.worlds.new('Studio dusk');world.use_nodes=True;scene.world=world
    background=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND')
    background.inputs['Color'].default_value=(.12,.16,.22,1);background.inputs['Strength'].default_value=.22
    area('01 · Тёплый мягкий ключ',(-.16,-.19,.235),(0,0,.060),3.5,.15,.065,(1.0,.92,.83),lights)
    area('02 · Холодный контур',(.13,.105,.16),(0,0,.072),3.8,.125,.024,(.69,.83,1.0),lights)
    area('03 · Верхний мягкий',(-.015,.015,.275),(0,0,.055),1.2,.13,.11,(.87,.93,1.0),lights)
    area('04 · Спокойное заполнение',(-.12,-.29,.075),(0,0,.055),.25,.20,.14,(.82,.90,1.0),lights)
    pivot=bpy.data.objects.new('БЛИК — Пробел / кадры 1–240',None);moving.objects.link(pivot)
    pivot.empty_display_type='CIRCLE';pivot.empty_display_size=.16;pivot.location=(0,0,.055)
    pivot['Как смотреть']='Пробел запускает движение световой полосы. Замок и камера неподвижны.'
    sweep=area('05 · Движущаяся световая полоса',(.08,-.24,-.035),(0,0,0),1.0,.16,.013,(1.0,.97,.91),moving,parent=pivot)
    for frame,degrees in ((1,-47),(120,47),(240,-47)):
        pivot.rotation_euler.z=math.radians(degrees);pivot.keyframe_insert(data_path='rotation_euler',index=2,frame=frame)
    scene.frame_start=1;scene.frame_end=240;scene.render.fps=24;scene.sync_mode='FRAME_DROP'
    for frame,label in ((1,'Блик слева'),(74,'Основной кадр'),(120,'Блик справа'),(180,'Обратно')):
        scene.timeline_markers.new(label,frame=frame)
    for name,position,target,lens in (
        ('01 · ОСНОВНОЙ КАДР',(-.22,-.48,.185),(0,0,.054),85),
        ('02 · Краска и скважина',(-.12,-.32,.095),(0,-.005,.033),100),
        ('03 · Контакт дужки',(.10,-.26,.135),(.024,0,.075),100),
        ('04 · Тыльная сторона',(.23,.46,.18),(0,0,.057),85),
    ):
        data=bpy.data.cameras.new(name);obj=bpy.data.objects.new(name,data);cameras.objects.link(obj)
        obj.location=position;aim(obj,target);data.type='PERSP';data.lens=lens;data.clip_start=.001;data.clip_end=100
        data.dof.use_dof=False
    scene.camera=bpy.data.objects['01 · ОСНОВНОЙ КАДР']
    scene.render.resolution_x=1500;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-1.35
    scene.view_settings.look='None'
    engines={i.identifier for i in scene.render.bl_rna.properties['engine'].enum_items}
    # EEVEE for immediate timeline inspection; the delivered still is rendered with Cycles.
    eevee=next((name for name in ('BLENDER_EEVEE','BLENDER_EEVEE_NEXT') if name in engines),None)
    scene.render.engine=eevee or 'CYCLES'
    if hasattr(scene,'eevee'):
        for prop,value in (('use_raytracing',True),('taa_samples',16),('taa_render_samples',64)):
            if hasattr(scene.eevee,prop):setattr(scene.eevee,prop,value)
    scene.cycles.device='CPU';scene.cycles.samples=128;scene.cycles.use_denoising=False
    scene.frame_set(74)
    for screen in bpy.data.screens:
        for viewport in screen.areas:
            if viewport.type=='VIEW_3D':
                space=viewport.spaces.active;space.shading.type='RENDERED'
                space.shading.use_scene_lights=True;space.shading.use_scene_world=True
                space.clip_start=.001;space.clip_end=100
                space.region_3d.view_perspective='CAMERA'
                space.overlay.show_overlays=False
    bpy.ops.object.select_all(action='DESELECT');pivot.select_set(True);bpy.context.view_layer.objects.active=pivot
    text=bpy.data.texts.new('НАЧНИ ЗДЕСЬ · свет и просмотр')
    text.write('Замок '+args.revision+' · студия\n\nПробел — запустить/остановить проход блика (кадры 1–240).\n'
               'Таймлайн можно двигать мышью. Анимируется только источник света.\n'
               'Ноль на цифровой клавиатуре — вид через активную камеру.\n'
               'В Outliner коллекция КАМЕРЫ содержит общий вид, краску/скважину, дужку и тыл.\n'
               'Для камеры: выбрать её и Ctrl+Num0.\n\n'
               'Для живого просмотра сохранён EEVEE с освещением сцены.\n'
               'Статичный PNG сделан в Cycles; глубина резкости и шумоподавление выключены, детали не размыты.\n'
               'Материал и геометрия замка совпадают с отдельным текстурным исходником.\n'
               'Поворот пустышки БЛИК вручную меняет положение полосы, её ключи видны на таймлайне.\n')
    scene['purpose']='Owner-requested lighting studio; light sweep only, no object animation or material change'
    scene['material_source']='padlock_'+args.revision+'_textured.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)
    print('STUDIO_SAVED',path,'realtime_engine',scene.render.engine,flush=True)

def verify():
    def asset_signature():
        result={}
        for obj in bpy.data.objects:
            if obj.get('stage')!='textured_highpoly_candidate':continue
            digest=hashlib.sha256()
            for vertex in obj.data.vertices:digest.update(struct.pack('<fff',*(obj.matrix_world@vertex.co)))
            result[obj.name]={'geometry':digest.hexdigest(),'vertices':len(obj.data.vertices),
                              'faces':len(obj.data.polygons),'material':obj.active_material.name}
        material=bpy.data.materials.get('Padlock_PBR_from_Painter')
        settings=[]
        for node in material.node_tree.nodes:
            inputs=[]
            for socket in node.inputs:
                if not hasattr(socket,'default_value'):continue
                value=socket.default_value
                if isinstance(value,(float,int,bool,str)):inputs.append((socket.name,value))
                elif hasattr(value,'__iter__'):inputs.append((socket.name,list(value)))
            settings.append({'name':node.name,'type':node.type,'inputs':inputs,
                             'image':node.image.filepath if node.type=='TEX_IMAGE' else None})
        return result,json.dumps(settings,sort_keys=True)
    bpy.ops.wm.open_mainfile(filepath=str(root/'models'/('padlock_'+args.revision+'_textured.blend')))
    source_signature=asset_signature()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    assert asset_signature()==source_signature,'Studio changed the reviewed geometry or material'
    scene=bpy.context.scene
    asset=[o for o in bpy.data.objects if o.get('stage')=='textured_highpoly_candidate']
    assert len(asset)==24 and all(o.animation_data is None for o in asset)
    assert bpy.data.objects['Padlock_ROOT'].animation_data is None
    positions=[]
    for frame in (1,74,120,180,240):
        scene.frame_set(frame)
        lamp=bpy.data.objects['05 · Движущаяся световая полоса']
        positions.append({'frame':frame,'position':list(lamp.matrix_world.translation)})
    assert (Vector(positions[0]['position'])-Vector(positions[2]['position'])).length>.2
    assert (Vector(positions[0]['position'])-Vector(positions[-1]['position'])).length<1e-6
    for image in bpy.data.images:
        if image.name.startswith(('Padlock_','reference_')):
            assert image.packed_file is not None and image.filepath.startswith('//')
            assert Path(bpy.path.abspath(image.filepath)).is_file()
    scene.frame_set(args.frame)
    (root/'checks'/args.report_name).write_text(json.dumps({'status':'PASS','file':str(path),
        'light_positions':positions,'asset_parts':len(asset),'light_only_animation':True,
        'frames':[1,240],'fps':scene.render.fps,'viewport_engine':scene.render.engine,
        'dof':scene.camera.data.dof.use_dof,'packed_relative_dependencies':True,
        'geometry_and_material_match_textured_source':True,'revision':args.revision},ensure_ascii=False,indent=2),encoding='utf-8')
    print('STUDIO_VERIFIED',len(asset),'parts; lighting sweep 1–240; packed relative images',flush=True)

if args.mode=='build':build()
else:
    verify()
    if args.mode=='render':
        scene=bpy.context.scene
        if not args.eevee_check:scene.render.engine='CYCLES'
        scene.cycles.device='CPU'
        scene.cycles.samples=args.samples;scene.cycles.use_denoising=False
        scene.render.resolution_x=args.size;scene.render.resolution_y=round(args.size*1100/1500)
        scene.render.filepath=str(root/('checks' if args.eevee_check else 'previews')/
                                  (('studio_eevee_'+args.revision+'_' if args.eevee_check else 'studio_'+args.revision+'_')+str(args.frame).zfill(3)+'.png'))
        bpy.ops.render.render(write_still=True)
        print('STUDIO_STILL',scene.render.filepath,flush=True)
