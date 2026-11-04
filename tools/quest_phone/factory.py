"""Factory-new graphite finish on the accepted v02, native UCUPaint 2.4.9.

Run in background Blender: --python tools/quest_phone/factory.py -- build|render|check [views...]
No accepted mesh, transform, modifier or rig is changed.
"""
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/quest_phone'
SOURCE=WORK/'models/QuestPhone_v02.blend'
FINAL=WORK/'models/QuestPhone_factory_v01.blend'
SPEC=WORK/'finish-spec.json'

def load_ucup():
    bpy.context.preferences.use_preferences_save=False
    addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
    u=importlib.import_module('bl_ext.blender_org.ucupaint')
    assert u.common.get_current_version_str()=='2.4.9'
    return u

def linear(c):
    return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4

def sync(u,entity,prop,value):
    setattr(entity,prop,value)
    u.common.set_entity_prop_value(entity,prop,value)
    actual=u.common.get_entity_prop_value(entity,prop)
    if isinstance(value,(int,float)):
        assert abs(actual-value)<1e-6,(prop,actual,value)

def reconnect(u,tree):
    u.input_outputs.check_all_channel_ios(tree.yp,reconnect=True)
    u.input_outputs.check_start_end_root_ch_nodes(tree)
    for layer in tree.yp.layers:
        u.node_connections.reconnect_layer_nodes(layer)
    u.node_connections.reconnect_yp_nodes(tree)

def stack(u,mat,recipe):
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and mat.name in o.data.materials)
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    obj.active_material_index=list(obj.data.materials).index(mat)
    nt=mat.node_tree
    bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='Заводская отделка · '+recipe['code'],color=True,
        metallic=True,roughness=True,normal=True,ao=False,switch_to_material_view=False,target_bsdf_name=bs.name)
    tree=next(n.node_tree for n in nt.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree['finish_code']=recipe['code']
    tree['recipe_json']=json.dumps(recipe,ensure_ascii=False)
    base=recipe['base']
    # UCUPaint COLOR source stores linear color; the catalogue defines sRGB.
    tree.yp.halt_update=True
    layer=u.Layer.add_new_layer(tree,'01 · Заводская основа','COLOR',-1,'MIX','MIX','BUMP_MAP','Object',
                               solid_color=tuple(linear(v) for v in base['color']))
    tree.yp.halt_update=False
    for index,channel in enumerate(tree.yp.channels):
        ch=layer.channels[index]
        if channel.name in ('Metallic','Roughness'):
            ch.override=True
            sync(u,ch,'override_value',base['metal' if channel.name=='Metallic' else 'rough'])
        elif channel.name=='Normal':
            ch.enable=False
    grain=recipe.get('grain')
    if grain and grain.get('rough'):
        tree.yp.halt_update=True
        g=u.Layer.add_new_layer(tree,'02 · Микроструктура '+str(grain['mm'])+' мм','NOISE',2,
                               'OVERLAY','MIX','BUMP_MAP','Object')
        tree.yp.halt_update=False
        for i,ch in enumerate(g.channels):
            ch.enable=i==2
        g.channels[2].blend_type='OVERLAY'
        sync(u,g.channels[2],'intensity_value',grain['rough'])
        src=u.common.get_layer_source(g)
        src.inputs['Scale'].default_value=1000./grain['mm']
        src.inputs['Detail'].default_value=0.
        tree['grain_note']='Cell spacing in local metres, unit scale; smooth Noise, no threshold or height.'
    r=recipe.get('render') or {}
    for key,socket in [('ior','IOR'),('transmission','Transmission Weight'),('coat','Coat Weight')]:
        if key in r:bs.inputs[socket].default_value=r[key]
    if 'thin_film' in r:
        bs.inputs['Thin Film Thickness'].default_value=r['thin_film'][0]
        bs.inputs['Thin Film IOR'].default_value=r['thin_film'][1]
    mat.diffuse_color=(*(linear(v) for v in base['color']),1.)
    mat['finish_code']=recipe['code']
    reconnect(u,tree)
    return tree

def point(ob,target,up=(0,1,0)):
    forward=(Vector(target)-ob.location).normalized()
    right=forward.cross(Vector(up)).normalized()
    real_up=right.cross(forward).normalized()
    ob.rotation_euler=Matrix((right,real_up,-forward)).transposed().to_euler()

def studio():
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=64
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=12
    scene.cycles.transmission_bounces=10
    # Use the available GPU without modifying user preferences on disk.
    prefs=bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type='OPTIX';prefs.get_devices()
        for d in prefs.devices:d.use=d.type!='CPU'
        if any(d.use for d in prefs.devices):scene.cycles.device='GPU'
    except Exception:pass
    world=bpy.data.worlds.new('Студия · отражения HDRI')
    world.use_nodes=True;scene.world=world
    nt=world.node_tree;nt.nodes.clear()
    env=nt.nodes.new('ShaderNodeTexEnvironment')
    hdr=Path(bpy.utils.resource_path('LOCAL'))/'datafiles/studiolights/world/studio.exr'
    env.image=bpy.data.images.load(str(hdr));env.image.pack()
    bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.55
    out=nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(env.outputs['Color'],bg.inputs['Color'])
    camera_bg=nt.nodes.new('ShaderNodeBackground')
    camera_bg.inputs['Color'].default_value=(.16,.17,.19,1.)
    rays=nt.nodes.new('ShaderNodeLightPath')
    mix=nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(rays.outputs['Is Camera Ray'],mix.inputs[0])
    nt.links.new(bg.outputs[0],mix.inputs[1]);nt.links.new(camera_bg.outputs[0],mix.inputs[2])
    nt.links.new(mix.outputs[0],out.inputs[0])
    col=bpy.data.collections.new('Студия отделки');scene.collection.children.link(col)
    for name,pos,power,size,size_y in [
        ('Ключ спереди',(-.19,.18,.28),1.6,.15,.30),
        ('Ключ сзади',(.16,.16,-.25),1.44,.11,.32),
        ('Узкий блик',(-.14,-.02,-.10),.48,.025,.22),
        ('Торец',(.18,-.15,.03),.64,.08,.18),
        ('Отражение в камерах',(-.06,.14,-.30),.22,.065,.10)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power
        data.shape='RECTANGLE';data.size=size;data.size_y=size_y
        ob=bpy.data.objects.new(name,data);col.objects.link(ob);ob.location=pos;point(ob,(0,0,0))
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=0.
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.render.resolution_percentage=100
    cam=scene.camera;cam.location=(-.085,.045,-.30);point(cam,(0,0,-.002))
    cam.data.type='ORTHO';cam.data.ortho_scale=.197;cam.data.clip_start=.001
    scene.render.resolution_x=1000;scene.render.resolution_y=1250
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                sp=area.spaces.active;sp.shading.type='RENDERED'
                sp.shading.use_scene_world_render=True;sp.shading.use_scene_lights_render=True
                sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                sp.region_3d.view_location=(0,0,0);sp.region_3d.view_distance=.23;sp.clip_start=.001

def build():
    spec=json.loads(SPEC.read_text(encoding='utf8'))
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==spec['source']['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    u=load_ucup()
    # The geometry prototype shared a diagnostic opaque material with the front.
    # Camera windows need their own transmitting material, without moving their meshes.
    cover=bpy.data.materials.new('Защитное стекло камер');cover.use_nodes=True
    for ob in bpy.data.objects:
        if ob.type=='MESH' and ob.name.startswith('12 · '):
            ob.data.materials.clear();ob.data.materials.append(cover)
    catalog=json.loads((ROOT/'tools/asset_kit/finish/finishes.json').read_text(encoding='utf8'))
    recipes={f['code']:f for f in catalog['finishes']}
    # Small polymers: base only; phone parts are not large cast weapon furniture.
    for slot in spec['slots']:
        recipe=dict(recipes[slot['finish']]);recipe.update(slot['overrides'])
        for name in slot['parts']:
            stack(u,bpy.data.materials[name],recipe)
    studio()
    root=bpy.data.objects['QuestPhone']
    root['stage']='factory candidate v01; geometry accepted v02'
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=bpy.data.objects['02 · Задняя панель']
    bpy.context.view_layer.objects.active.select_set(True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(FINAL))
    print('FACTORY_SAVED',FINAL)

def check():
    bpy.ops.wm.open_mainfile(filepath=str(FINAL));u=load_ucup()
    report=dict(blender=bpy.app.version_string,ucupaint=u.common.get_current_version_str(),materials=[])
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.users:continue
        trees=[n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node]
        if not trees:continue
        tree=trees[0];recipe=json.loads(tree['recipe_json'])
        base=next(l for l in tree.yp.layers if l.type=='COLOR')
        actual_color=u.common.get_layer_source(base).outputs[0].default_value
        assert all(abs(a-linear(b))<1e-6 for a,b in zip(actual_color,recipe['base']['color']))
        values={}
        for i,ch in enumerate(tree.yp.channels):
            if ch.name in ('Metallic','Roughness'):
                value=u.common.get_entity_prop_value(base.channels[i],'override_value')
                assert abs(value-recipe['base']['metal' if ch.name=='Metallic' else 'rough'])<1e-6
                values[ch.name]=value
        bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        assert all(bs.inputs[s].is_linked for s in ['Base Color','Metallic','Roughness'])
        report['materials'].append(dict(name=mat.name,code=tree['finish_code'],layers=[l.name for l in tree.yp.layers],
            channels=values,transmission=bs.inputs['Transmission Weight'].default_value,ior=bs.inputs['IOR'].default_value))
    report['images']=[dict(name=i.name,packed=bool(i.packed_file)) for i in bpy.data.images if i.source=='FILE']
    assert len(report['materials'])==10,len(report['materials'])
    assert all(i['packed'] for i in report['images'])
    (WORK/'checks/factory_native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('FACTORY_CHECK_OK',len(report['materials']))

def glass_test():
    """Temporary checker behind the actual closed camera window; both faces, no save."""
    bpy.ops.wm.open_mainfile(filepath=str(FINAL));load_ucup()
    sc=bpy.context.scene
    glass=bpy.data.objects['12 · Основная · Стекло']
    for ob in sc.objects:
        if ob.type=='MESH':ob.hide_render=ob!=glass
    center=glass.matrix_world.translation.copy()
    bpy.ops.mesh.primitive_plane_add(size=.015,location=center)
    plane=bpy.context.object
    mat=bpy.data.materials.new('ВРЕМЕННАЯ шахматная подложка');mat.use_nodes=True
    plane.data.materials.append(mat);nt=mat.node_tree
    tex=nt.nodes.new('ShaderNodeTexChecker');tex.inputs['Scale'].default_value=5.
    tex.inputs['Color1'].default_value=(.04,.4,.03,1)
    tex.inputs['Color2'].default_value=(.5,.02,.01,1)
    nt.links.new(tex.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])
    sc.render.resolution_x=sc.render.resolution_y=450
    sc.camera.data.ortho_scale=.016
    for side in [-1,1]:
        plane.location=center+Vector((0,0,-side*.0007))
        sc.camera.location=center+Vector((0,0,side*.04))
        point(sc.camera,center)
        sc.render.filepath=str(WORK/f'checks/glass_{side}.png')
        bpy.ops.render.render(write_still=True)
    print('GLASS_BOTH_FACES_RENDERED')

def render(views):
    bpy.ops.wm.open_mainfile(filepath=str(FINAL));load_ucup()
    scene=bpy.context.scene;cam=scene.camera
    shots={'back':((-.075,.04,-.30),(0,0,-.002),.197,1000,1250),
           'front':((.06,-.04,.30),(0,0,0),.197,1000,1250),
           'camera_macro':((-.01,.074,-.12),(.018,.06,-.006),.062,1100,1000),
           'bottom':((.028,-.12,.045),(0,-.072,0),.067,1300,850)}
    for name in views or shots:
        eye,target,scale,w,h=shots[name];cam.location=eye;point(cam,target,up=(0,0,1) if name=='bottom' else (0,1,0))
        cam.data.ortho_scale=scale
        scene.render.resolution_x=w;scene.render.resolution_y=h
        scene.render.filepath=str(WORK/f'previews/quest_phone_factory_v01_{name}.png')
        bpy.ops.render.render(write_still=True)
        print('FACTORY_RENDERED',name)

if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    if args[0]=='build':build()
    elif args[0]=='check':check()
    elif args[0]=='render':render(args[1:])
    elif args[0]=='glass':glass_test()
    else:raise ValueError(args)
