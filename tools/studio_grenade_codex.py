"""Редактируемая предметная студия вокруг согласованной модели гранаты."""
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'_asset_src/grenade_codex'
FILE=OUT/'Grenade_MkII_Studio_v06.blend'
PREVIEW=OUT/'Grenade_MkII_PBR_Preview_v06.blend'
RENDERS=OUT/'previews/studio'
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

SHOTS=[
    ('01_hero',(.19,-.33,.205),(0,0,.049),105,3200,4000,1),
    ('02_landscape',(.27,-.59,.28),(0,0,.045),85,3840,2160,1),
    ('03_head_and_mark',(.085,-.155,.185),(.006,0,.093),105,3200,3200,1),
    ('04_cast_detail',(.10,-.17,.089),(.002,-.005,.043),105,3200,3200,1),
    ('05_sun_slnshk',(.006,-.025,.22),(.003,0,.111),105,3200,3200,1),
    ('06_reverse_portrait',(-.19,.33,.20),(0,0,.049),105,3200,4000,1),
    ('07_low_angle',(.18,-.40,.135),(0,0,.055),100,3840,2880,1),
    ('08_split_pin_detail',(-.085,.155,.168),(.0115,.007,.099),105,3200,3200,1),
    ('09_visual_motion',(.27,-.43,.26),(.020,-.016,.075),70,3840,2560,54),
    ('10_opposite_profile',(-.23,-.24,.17),(0,0,.062),95,3200,4000,1),
]


def aim(ob,target):
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()


def into_collection(ob,collection):
    for old in list(ob.users_collection): old.objects.unlink(ob)
    collection.objects.link(ob)


def material(name,color,roughness,grain=False):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    nt=mat.node_tree
    p=nt.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=roughness
    if grain:
        tc=nt.nodes.new('ShaderNodeTexCoord')
        noise=nt.nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value=3800
        noise.inputs['Detail'].default_value=2
        bump=nt.nodes.new('ShaderNodeBump')
        bump.inputs['Distance'].default_value=.000038
        bump.inputs['Strength'].default_value=.38
        nt.links.new(tc.outputs['Object'],noise.inputs['Vector'])
        nt.links.new(noise.outputs['Fac'],bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'],p.inputs['Normal'])
    return mat


def configure(scene):
    scene.render.engine='CYCLES'
    scene.cycles.device='GPU'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.samples=int(os.environ.get('GRENADE_STUDIO_SAMPLES','512'))
    scene.cycles.use_denoising=False
    scene.cycles.adaptive_threshold=.004
    scene.cycles.max_bounces=10
    scene.cycles.diffuse_bounces=4
    scene.cycles.glossy_bounces=6
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.image_settings.color_depth='16'
    scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=.10


def set_shot(scene,row):
    name,pos,target,lens,width,height,frame=row
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    scene.camera.location=pos
    aim(scene.camera,target)
    scene.camera.data.lens=lens
    scene.render.resolution_x=width
    scene.render.resolution_y=height
    scene.render.filepath=str(RENDERS/(name+'.png'))


def build():
    T.P.native()
    bpy.ops.wm.open_mainfile(filepath=str(T.MASTER))
    scene=bpy.context.scene
    scene.frame_set(1)
    before={o.name:(o.data.name,list(o.matrix_world)) for o in scene.objects if o.type=='MESH'}
    for ob in list(scene.objects):
        if ob.type in {'CAMERA','LIGHT'}: bpy.data.objects.remove(ob,do_unlink=True)
    studio=bpy.data.collections.new('STUDIO • lights and backdrop')
    scene.collection.children.link(studio)
    scene.world=bpy.data.worlds.new('Studio • subtle neutral environment')
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.08,.09,.10,1)
    bg.inputs['Strength'].default_value=.20
    # Плавный изгиб фона убирает линию горизонта за предметом.
    profile=[(-1.2,-.0146),(.20,-.0146)]
    radius=.20
    for i in range(1,49):
        theta=(math.pi/2)*i/48
        profile.append((.20+radius*math.sin(theta),-.0146+radius*(1-math.cos(theta))))
    profile.append((.40,1.10))
    verts=[(x,y,z) for y,z in profile for x in [-1.5,1.5]]
    faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(profile)-1)]
    me=bpy.data.meshes.new('Seamless curved studio sweep')
    me.from_pydata(verts,[],faces)
    me.update()
    backdrop=bpy.data.objects.new('STUDIO • seamless graphite backdrop',me)
    studio.objects.link(backdrop)
    backdrop.data.materials.append(material('Studio • matte graphite',(.007,.010,.014),.64))
    for p in me.polygons: p.use_smooth=True
    # Подставка входит в студию; исходные сетки гранаты сохраняются.
    bpy.ops.mesh.primitive_cylinder_add(vertices=192,radius=.065,depth=.014,location=(0,0,-.00735))
    base=bpy.context.object
    base.name='STUDIO • charcoal mineral pedestal'
    into_collection(base,studio)
    base.data.materials.append(material('Studio • fine charcoal mineral',(.010,.012,.016),.48,True))
    bevel=base.modifiers.new('Soft 1.2 mm display edge','BEVEL')
    bevel.width=.0012
    bevel.segments=5
    for p in base.data.polygons: p.use_smooth=True
    for name,pos,energy,width,height,color,target in [
        ('KEY • large warm softbox',(-.30,-.26,.40),3.4,.23,.34,(1,.945,.87),(0,0,.058)),
        ('FILL • restrained neutral',(.08,-.35,.18),1.05,.20,.22,(.96,.98,1),(0,0,.055)),
        ('RIM • cool vertical strip',(.24,.07,.20),3.0,.035,.24,(.78,.88,1),(0,0,.066)),
        ('EDGE • rear softbox',(-.11,.22,.26),2.6,.12,.18,(1,.97,.93),(0,0,.065)),
        ('TOP • stencil and shoulder',(.015,-.03,.42),.60,.12,.16,(1,1,1),(0,0,.105)),
    ]:
        data=bpy.data.lights.new(name,'AREA')
        data.energy=energy
        data.shape='RECTANGLE'
        data.size=width
        data.size_y=height
        data.color=color
        ob=bpy.data.objects.new(name,data)
        studio.objects.link(ob)
        ob.location=pos
        aim(ob,target)
    camera=bpy.data.objects.new('CAMERA • 105 mm product portrait',bpy.data.cameras.new('Product portrait • crisp focus'))
    studio.objects.link(camera)
    scene.camera=camera
    camera.data.type='PERSP'
    camera.data.sensor_width=36
    camera.data.sensor_fit='HORIZONTAL'
    camera.data.clip_start=.001
    camera.data.clip_end=20
    camera.data.dof.use_dof=False
    configure(scene)
    set_shot(scene,SHOTS[0])
    for name,(data,matrix) in before.items():
        ob=bpy.data.objects[name]
        assert ob.data.name==data and list(ob.matrix_world)==matrix,name
    for ob in bpy.context.selected_objects: ob.select_set(False)
    root=bpy.data.objects['CTRL_Grenade']
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.clip_start=.001
                space.overlay.show_overlays=False
                space.shading.type='MATERIAL'
                for prop in ['use_scene_lights','use_scene_world','use_scene_lights_render','use_scene_world_render']:
                    if hasattr(space.shading,prop): setattr(space.shading,prop,True)
                space.region_3d.view_perspective='CAMERA'
                space.region_3d.view_camera_zoom=5
    RENDERS.mkdir(parents=True,exist_ok=True)
    scene.render.filepath='//previews/studio/01_hero.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False)
    report={'file':str(FILE),'style':'graphite product studio; warm key, cool edge; neutral fill',
            'unchanged_asset_meshes':list(before),'lights':5,'samples':scene.cycles.samples,'asset_materials':'native UCUPaint',
            'denoising':False,'depth_of_field':False,'shots':[row[0] for row in SHOTS]}
    (OUT/'checks/studio_setup_v06.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('STUDIO_BUILD_OK',FILE,flush=True)


def render():
    T.P.native()
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    scene=bpy.context.scene
    scene.frame_set(1)
    configure(scene)
    selected=sys.argv[sys.argv.index('--')+2:] if '--' in sys.argv else []
    rows=[]
    for row in SHOTS:
        if selected and row[0] not in selected: continue
        set_shot(scene,row)
        print('STUDIO_RENDER_BEGIN',row[0],flush=True)
        bpy.ops.render.render(write_still=True)
        rows.append({'file':row[0]+'.png','size':[row[4],row[5]],'samples':scene.cycles.samples,
                     'sha256':hashlib.file_digest(open(scene.render.filepath,'rb'),'sha256').hexdigest()})
        print('STUDIO_RENDER_OK',row[0],flush=True)
    (OUT/'checks/studio_renders_v06.json').write_text(json.dumps(rows,indent=2),encoding='utf8')


if __name__=='__main__':
    mode=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build'
    {'build':build,'render':render}[mode]()
