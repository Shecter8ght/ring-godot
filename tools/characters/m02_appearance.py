"""Author M02 skin and groom on a separate native Blender candidate.

The accepted geometry file is read only. Runs in a separate factory Blender.
Native UCUPaint layers, a reversible face shape and native hair curves remain editable.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import sys

import addon_utils
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/npc_m02'
SOURCE = Path('E:/Models Blender/RING_NPC_2026-10-20_v01/M02_Geometry_v06/M02_Body_Head_Geometry_v06.blend')
DATA = Path(os.environ['APPDATA']) / 'Blender Foundation/Blender/5.2/extensions/.user/blender_org/mpfb/data'
U = None


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def smooth(lo, hi, x):
    t = clamp((x-lo)/(hi-lo))
    return t*t*(3-2*t)


def gaussian(x, center, width):
    return math.exp(-((x-center)/width)**2)


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.active_material_index = 0


def enable_paint():
    global U
    bpy.context.preferences.use_preferences_save = False
    name = 'bl_ext.blender_org.ucupaint'
    if name not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module = name
    addon_utils.enable(name, default_set=False, persistent=False)
    U = importlib.import_module(name)
    assert U.common.get_current_version_str() == '2.4.9'


def sync(entity, name, value):
    if name == 'override_color':
        from mathutils import Color
        value = Color(value)
    setattr(entity, name, value)
    U.common.set_entity_prop_value(entity, name, value)
    actual = U.common.get_entity_prop_value(entity, name)
    wanted = [value] if isinstance(value, (float, int)) else list(value)
    found = [actual] if isinstance(actual, (float, int)) else list(actual)[:len(wanted)]
    assert all(abs(a-b)<1e-5 for a,b in zip(wanted,found)), (name,wanted,found)


def attr_mask(body, name, function):
    attr = body.data.color_attributes.get(name) or body.data.color_attributes.new(name, 'FLOAT_COLOR', 'CORNER')
    values = [clamp(function(body.matrix_world @ v.co)) for v in body.data.vertices]
    flat = np.array([(values[loop.vertex_index],)*3+(1.0,) for loop in body.data.loops],dtype=np.float32).ravel()
    attr.data.foreach_set('color',flat)
    return name


def face_front(p):
    return smooth(-0.085,-0.130,p.y) * smooth(1.51,1.55,p.z)


def beard_mask(p):
    # Cheeks/jaw and the moustache band; keep lips and the nose clear.
    a = abs(p.x)
    jaw = smooth(1.53,1.552,p.z) * (1-smooth(1.609+0.30*a,1.627+0.30*a,p.z))
    jaw *= 1-smooth(0.068,0.079,a)
    lips = math.exp(-((p.x/0.031)**4 + ((p.z-1.603)/0.008)**4))
    moustache = gaussian(p.z,1.614,0.0048)*smooth(0.004,0.010,a)*(1-smooth(0.027,0.034,a))
    nose = gaussian(p.x,0,0.018)*smooth(1.612,1.625,p.z)
    return clamp(max(jaw*(1-lips)*(1-nose),moustache)*face_front(p))


def scalp_mask(p):
    if p.z<1.605 or abs(p.x)>0.096 or p.y<-0.163:
        return 0.0
    # Pinnae must stay bare, including their upper rim and the front of the ear.
    ear=((abs(p.x)-0.084)/0.030)**2+((p.y+0.037)/0.034)**2+((p.z-1.652)/0.035)**2
    ear_clearance=smooth(1.00,1.15,ear)
    if ear_clearance==0:
        return 0.0
    # Smooth hairline: nape -> above the ear -> temples -> forehead.
    if p.y>-0.025:
        boundary = 1.617
    elif p.y>-0.070:
        boundary = 1.617 + smooth(-0.025,-0.070,p.y)*0.076
    elif p.y>-0.110:
        boundary = 1.693
    else:
        boundary = 1.693 + smooth(-0.110,-0.148,p.y)*0.034
        boundary += 0.004*gaussian(abs(p.x),0.046,0.017)
    boundary+=0.0011*math.sin(125*p.x+85*p.y)
    return smooth(boundary-0.0015,boundary+0.0025,p.z)*ear_clearance


def refine_face(body):
    body.shape_key_add(name='Basis')
    key = body.shape_key_add(name='M02 — adult face refinement')
    inverse = body.matrix_world.inverted()
    displacements=[]
    for i,vertex in enumerate(body.data.vertices):
        p=body.matrix_world @ vertex.co
        if p.z<1.53 or p.z>1.72 or p.y>-0.102:
            continue
        front=face_front(p)
        side=-1 if p.x<0 else 1
        # Millimetre-scale corrections, each retained in a shape key.
        cheeks=gaussian(abs(p.x),0.046,0.019)*gaussian(p.z,1.629,0.024)*front
        chin=gaussian(abs(p.x),0.024,0.019)*gaussian(p.z,1.568,0.016)*front
        corners=gaussian(abs(p.x),0.026,0.009)*gaussian(p.z,1.601,0.010)*front
        upperlid=gaussian(abs(p.x),0.030,0.018)*gaussian(p.z,1.6715,0.0032)*front
        nostril=gaussian(abs(p.x),0.013,0.009)*gaussian(p.z,1.625,0.009)*front
        delta=Vector((side*(-0.0010*cheeks+0.0009*chin+0.0006*nostril),
                      0.0010*cheeks-0.0006*chin,
                      0.0012*corners-0.0007*upperlid))
        # Very small asymmetry of the nasal bridge, as in the selected M02 direction.
        delta.x += 0.00045*gaussian(p.x,0,0.013)*gaussian(p.z,1.646,0.016)*front
        key.data[i].co=inverse @ (p+delta)
        displacements.append(delta.length)
    key.value=1.0
    body['face_refinement']='Reversible shape: cheeks, relaxed mouth corners, upper lids, chin and subtle nasal asymmetry.'
    return max(displacements)


def new_material(name):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    return mat


def make_skin(body):
    activate(body)
    mat=new_material('M02 | Skin — editable UCUPaint')
    body.data.materials.clear()
    body.data.materials.append(mat)
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bsdf.inputs['Roughness'].default_value=0.55
    bsdf.inputs['IOR'].default_value=1.42
    bsdf.inputs['Specular IOR Level'].default_value=0.32
    bsdf.inputs['Subsurface Weight'].default_value=0.10
    bsdf.inputs['Subsurface Radius'].default_value=(1.0,0.46,0.23)
    bsdf.inputs['Subsurface Scale'].default_value=0.0009
    bsdf.inputs['Diffuse Roughness'].default_value=0.12
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='M02 | Skin authoring',color=True,metallic=False,
        roughness=True,normal=True,ao=False,switch_to_material_view=False,target_bsdf_name=bsdf.name)
    group=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree=group.node_tree
    uv=body.data.uv_layers.active.name
    normal=next(c for c in tree.yp.channels if c.type=='NORMAL')
    normal.enable_smooth_bump=False
    normal.main_uv=uv
    unit=abs(body.matrix_world.to_scale().x)

    def layer(name,color=None,rough=None,height=None,source='COLOR',image=None,amount=1.0,distance=0.00003):
        tree.yp.halt_update=True
        ly=U.Layer.add_new_layer(tree,name,source,-1,'MIX','OVERLAY','BUMP_MAP',
            'UV' if image else 'Object',uv,image=image,use_designated_idx=True,designated_index=0)
        tree.yp.halt_update=False
        values={'Color':color,'Roughness':rough,'Normal':height}
        for root,ch in zip(tree.yp.channels,ly.channels):
            value=values[root.name]
            ch.enable=value is not None
            if value is None:
                continue
            if value!='source':
                ch.override=True
                ch.override_type='DEFAULT'
                sync(ch,'override_color' if root.type=='RGB' else 'override_value',value)
            if root.type=='NORMAL':
                sync(ch,'bump_distance',distance/unit)
                sync(ch,'bump_midlevel',0.5)
        sync(ly,'intensity_value',amount)
        return ly

    def masked(ly,name):
        return U.Mask.add_new_mask(ly,name,'VCOL','Object',uv,vcol_name=name)

    texture=bpy.data.images.load(str(DATA/'skins/young_caucasian_male2/young_lightskinned_male_diffuse2.png'),check_existing=True)
    texture.colorspace_settings.name='sRGB'
    layer('01 | CC0 skin colour base',color='source',rough=0.54,source='IMAGE',image=texture)
    mature=bpy.data.images.load(str(DATA/'skins/middleage_caucasian_male/middleage_lightskinned_male_diffuse.png'),check_existing=True)
    mature.colorspace_settings.name='sRGB'
    head=attr_mask(body,'M02_Adult_Face_Texture',lambda p:smooth(1.52,1.57,p.z))
    ly=layer('01b | Adult facial colour detail',color='source',source='IMAGE',image=mature,amount=0.34)
    masked(ly,head)
    legs=attr_mask(body,'M02_Leg_Tone_Balance',lambda p:1-smooth(0.72,0.90,p.z))
    ly=layer('01c | Lower-body scan tone balance',color='source',source='IMAGE',image=texture,amount=0.80)
    masked(ly,legs)
    importlib.import_module(U.__name__+'.Modifier').add_new_modifier(ly,'HUE_SATURATION')
    modifier=ly.modifiers[0]
    modifier_tree=U.common.get_mod_tree(ly)
    grade=modifier_tree.nodes[modifier.huesat]
    grade.inputs['Saturation'].default_value=0.72
    grade.inputs['Value'].default_value=1.36
    cheeks=attr_mask(body,'M02_Warm_Zones',lambda p:face_front(p)*(gaussian(abs(p.x),0.044,0.024)*gaussian(p.z,1.637,0.023)+0.35*gaussian(p.x,0,0.016)*gaussian(p.z,1.632,0.014)))
    ly=layer('02 | Warm cheeks and nose',color=(0.32,0.10,0.062),amount=0.075)
    masked(ly,cheeks)
    lowerlids=attr_mask(body,'M02_Lower_Lids',lambda p:face_front(p)*gaussian(abs(p.x),0.031,0.019)*gaussian(p.z,1.653,0.005))
    ly=layer('02b | Restrained lower-lid tone',color=(0.18,0.095,0.065),amount=0.10)
    masked(ly,lowerlids)
    stubble=attr_mask(body,'M02_Stubble_Region',beard_mask)
    ly=layer('03 | Shaved beard undertone',color=(0.105,0.087,0.072),rough=0.60,amount=0.16)
    masked(ly,stubble)
    oily=attr_mask(body,'M02_T_Zone',lambda p:face_front(p)*max(gaussian(p.x,0,0.040)*gaussian(p.z,1.711,0.028),gaussian(p.x,0,0.018)*gaussian(p.z,1.640,0.023)))
    ly=layer('04 | Forehead and nose — softer roughness',rough=0.42,amount=0.70)
    masked(ly,oily)
    lips=attr_mask(body,'M02_Lips',lambda p:face_front(p)*math.exp(-((p.x/0.029)**4+((p.z-1.603)/0.0050)**4)))
    ly=layer('05 | Natural lip moisture',rough=0.41,amount=0.55)
    masked(ly,lips)
    ly=layer('06 | Skin pores — fine relief',height='source',source='NOISE',distance=0.000045,amount=0.65)
    src=U.common.get_layer_source(ly)
    src.inputs['Scale'].default_value=2900*unit
    src.inputs['Detail'].default_value=2.0
    src.inputs['Roughness'].default_value=0.65
    ly=layer('07 | Fine variation of roughness',rough=0.60,source='NOISE',amount=0.16)
    noise=U.Mask.add_new_mask(ly,'Small surface variation','NOISE','Object',uv)
    U.common.get_mask_source(noise).inputs['Scale'].default_value=450*unit
    scalp=attr_mask(body,'M02_Scalp_Root_Coverage',scalp_mask)
    ly=layer('08 | Dark roots beneath the groom',color=(0.033,0.022,0.014),rough=0.65,amount=0.85)
    masked(ly,scalp)
    U.input_outputs.check_all_channel_ios(tree.yp,reconnect=True)
    U.input_outputs.check_start_end_root_ch_nodes(tree)
    for ly in tree.yp.layers:
        U.node_connections.reconnect_layer_nodes(ly)
    U.node_connections.reconnect_yp_nodes(tree)
    mat.diffuse_color=(0.54,0.31,0.20,1)
    mat['authoring']='Native UCUPaint 2.4.9; original CC0 MakeHuman skin maps plus independently editable skin masks and microrelief.'
    return tree


def hair_material(name,melanin=0.85,redness=0.08,roughness=0.46):
    mat=new_material(name)
    tree=mat.node_tree
    tree.nodes.clear()
    out=tree.nodes.new('ShaderNodeOutputMaterial')
    hair=tree.nodes.new('ShaderNodeBsdfHairPrincipled')
    hair.model='CHIANG'
    hair.parametrization='MELANIN'
    hair.inputs['Melanin'].default_value=melanin
    hair.inputs['Melanin Redness'].default_value=redness
    hair.inputs['Roughness'].default_value=roughness
    hair.inputs['Radial Roughness'].default_value=0.48
    hair.inputs['Random Color'].default_value=0.08
    hair.inputs['Random Roughness'].default_value=0.12
    hair.inputs['Coat'].default_value=0.15
    if 'Brow' in name:
        hair.parametrization='COLOR'
        hair.inputs['Color'].default_value=(0.018,0.011,0.006,1.0)
        hair.inputs['Coat'].default_value=0.0
    info=tree.nodes.new('ShaderNodeHairInfo')
    tree.links.new(info.outputs['Random'],hair.inputs['Random'])
    tree.links.new(hair.outputs[0],out.inputs['Surface'])
    mat.diffuse_color=(0.075,0.040,0.021,1)
    return mat


def refine_eyes(body):
    eyes=bpy.data.objects['M02_Eyes']
    mat=eyes.active_material
    tree=mat.node_tree
    bsdf=next(n for n in tree.nodes if n.type=='BSDF_PRINCIPLED')
    texture=next(n for n in tree.nodes if n.type=='TEX_IMAGE')
    hsv=next(n for n in tree.nodes if n.type=='HUE_SAT')
    hsv.inputs['Hue'].default_value=0.5
    hsv.inputs['Saturation'].default_value=0.90
    hsv.inputs['Value'].default_value=1.0
    tree.links.new(hsv.outputs['Color'],bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value=0.25
    bsdf.inputs['IOR'].default_value=1.38
    bsdf.inputs['Specular IOR Level'].default_value=0.45
    bsdf.inputs['Coat Weight'].default_value=0.65
    bsdf.inputs['Coat Roughness'].default_value=0.045
    bsdf.inputs['Coat IOR'].default_value=1.376
    texture.image.colorspace_settings.name='sRGB'
    mat.name='M02 | Brown eyes — wet surface'
    # Keep the original alpha lashes but reduce their distance from the eyelids.
    lashes=bpy.data.objects['M02_Eyelashes']
    deps=bpy.context.evaluated_depsgraph_get()
    bvh=BVHTree.FromObject(body,deps)
    to_body=body.matrix_world.inverted() @ lashes.matrix_world
    from_body=to_body.inverted()
    for vertex in lashes.data.vertices:
        point=to_body @ vertex.co
        nearest,normal,_,distance=bvh.find_nearest(point)
        if nearest is not None and distance>0.0015:
            vertex.co=from_body @ (nearest+(point-nearest).normalized()*0.0015)
    lashes.data.update()


def surface_sampler(obj,predicate):
    deps=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(deps)
    mesh=evaluated.to_mesh()
    mesh.calc_loop_triangles()
    triangles=[]
    cumulative=[]
    total=0.0
    uv=mesh.uv_layers.active
    for tri in mesh.loop_triangles:
        points=[evaluated.matrix_world @ mesh.vertices[i].co for i in tri.vertices]
        center=sum(points,Vector())/3
        if predicate(center)<=0.01:
            continue
        cross=(points[1]-points[0]).cross(points[2]-points[0])
        area=cross.length*0.5
        if area<1e-12:
            continue
        total+=area
        cumulative.append(total)
        tex=[uv.data[i].uv.copy() for i in tri.loops] if uv else None
        triangles.append((points,cross.normalized(),tex))
    evaluated.to_mesh_clear()
    assert triangles,obj.name
    def sample(rng):
        points,normal,uv=triangles[bisect.bisect_left(cumulative,rng.random()*total)]
        r1=math.sqrt(rng.random())
        r2=rng.random()
        weights=(1-r1,r1*(1-r2),r1*r2)
        p=sum((point*w for point,w in zip(points,weights)),Vector())
        tex=sum((u*w for u,w in zip(uv,weights)),Vector((0,0))) if uv else None
        return p,normal,tex
    return sample


def curves_object(name,paths,radii,mat,col,rig):
    curve=bpy.data.hair_curves.new(name)
    curve.add_curves([len(path) for path in paths])
    curve.attributes['position'].data.foreach_set('vector',np.asarray([p for path in paths for p in path],dtype=np.float32).ravel())
    radius=curve.attributes.new('radius','FLOAT','POINT')
    radius.data.foreach_set('value',np.asarray(radii,dtype=np.float32).ravel())
    obj=bpy.data.objects.new(name,curve)
    col.objects.link(obj)
    curve.materials.append(mat)
    # Curves are authored in world metres and follow the anatomical head bone.
    world=obj.matrix_world.copy()
    obj.parent=rig
    obj.parent_type='BONE'
    obj.parent_bone='head'
    obj.matrix_world=world
    obj['strand_count']=len(paths)
    obj['authoring']='Native editable hair curves, generated on the evaluated M02 skin surface; separate from body topology.'
    return obj


def make_groom(body,rig,density=1.0):
    col=bpy.data.collections.new('07_M02_Hair_and_Stubble')
    bpy.context.scene.collection.children.link(col)
    for name in ['M02_Separate_Short_Hair','M02_Eyebrows']:
        obj=bpy.data.objects[name]
        obj.hide_render=True
        obj.hide_set(True)
    rng=random.Random(20261020)
    hairmat=hair_material('M02 | Chestnut hair fibres')
    darkmat=hair_material('M02 | Brow and stubble fibres',0.91,0.05,0.51)
    bpy.context.view_layer.update()
    sample=surface_sampler(body,scalp_mask)
    paths=[]
    radii=[]
    target=int(64000*density)
    while len(paths)<target:
        root,n,_=sample(rng)
        if rng.random()>scalp_mask(root):
            continue
        top=smooth(1.695,1.765,root.z)
        length=(0.010+0.024*top)*rng.uniform(0.64,1.25)
        flow=Vector((0.75,0.5,-0.06)) if top>0.35 else Vector((0,0.26,-1))
        flow-=n*flow.dot(n)
        if flow.length<0.1:
            flow=Vector((1,0,0))
            flow-=n*flow.dot(n)
        flow.normalize()
        transverse=n.cross(flow).normalized()
        clump_phase=180*root.x+210*root.y+91*root.z
        turn=0.45*math.sin(clump_phase)+rng.gauss(0,0.18)
        flow=(flow+transverse*turn).normalized()
        root=root+n*rng.uniform(0.0001,0.00035)
        lift=0.45+0.35*top+rng.uniform(-0.10,0.20)
        path=[]
        root_radius=rng.uniform(0.000043,0.000065)
        for j in range(10):
            t=j/9
            bend=math.sin(math.pi*t)*0.10+0.05*t*t
            point=root+flow*(length*t)+n*(length*(lift*t-0.45*t*t))
            point+=transverse*(length*bend*math.sin(clump_phase+3*t))
            point+=n*(length*0.055*math.sin(t*7+clump_phase)*t)
            path.append(point)
            radii.append(root_radius*(1-0.96*t)**0.6)
        paths.append(path)
    objects=[curves_object('M02_Groom_Chestnut_Short',paths,radii,hairmat,col,rig)]

    sample=surface_sampler(body,beard_mask)
    paths=[]
    radii=[]
    while len(paths)<int(11500*density):
        root,n,_=sample(rng)
        if rng.random()>beard_mask(root)*rng.uniform(0.8,1.3):
            continue
        length=rng.uniform(0.00045,0.0013)
        downward=Vector((0,0,-1))
        tangent=downward-n*downward.dot(n)
        tangent.normalize()
        tip=root+n*length*0.72+tangent*length*0.60
        paths.append([root+n*0.00008,root+n*length*0.45+tangent*length*0.18,tip])
        radius=rng.uniform(0.000030,0.000045)
        radii.extend([radius,radius*0.70,radius*0.12])
    objects.append(curves_object('M02_Groom_Short_Stubble',paths,radii,darkmat,col,rig))

    brow=bpy.data.objects['M02_Eyebrows']
    brow.hide_set(False)
    sample=surface_sampler(brow,lambda p:1)
    texture=next(image for image in bpy.data.images if image.name.startswith('eyebrow001'))
    pixels=np.asarray(texture.pixels[:],dtype=np.float32).reshape(texture.size[1],texture.size[0],4)
    paths=[]
    radii=[]
    attempts=0
    while len(paths)<int(2200*density) and attempts<200000:
        attempts+=1
        root,n,uv=sample(rng)
        x=int(clamp(uv.x)* (texture.size[0]-1))
        y=int(clamp(uv.y)* (texture.size[1]-1))
        if rng.random()>pixels[y,x,3]*0.92:
            continue
        side=-1 if root.x<0 else 1
        direction=Vector((side*0.75,-0.1,0.48*(1-smooth(0.015,0.052,abs(root.x)))))
        direction-=n*direction.dot(n)
        direction.normalize()
        length=rng.uniform(0.0020,0.0041)
        root+=n*0.00005
        paths.append([root,root+direction*length*0.55+n*0.0005,root+direction*length+n*0.0003])
        radius=rng.uniform(0.000032,0.000048)
        radii.extend([radius,radius*0.72,radius*0.08])
    brow.hide_set(True)
    objects.append(curves_object('M02_Groom_Natural_Eyebrows',paths,radii,darkmat,col,rig))
    return objects


def setup_render(out,samples):
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=samples
    scene.cycles.use_denoising=True
    scene.cycles.adaptive_threshold=0.03
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use=device.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    scene.cycles.max_bounces=8
    scene.cycles.diffuse_bounces=3
    scene.cycles.glossy_bounces=4
    scene.cycles.transmission_bounces=6
    scene.view_settings.exposure=-0.15
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    scene.render.film_transparent=False
    scene.render.use_file_extension=True
    scene.world.node_tree.nodes.get('Background').inputs[1].default_value=0.25
    bpy.data.objects['Studio_Floor'].hide_render=True
    for name,power in [('Large_Key',300),('Soft_Fill',80),('Shoulder_Separation',150)]:
        bpy.data.objects[name].data.energy=power
    bpy.data.objects['Large_Key'].data.size=1.4
    # Perspective portrait, matching the face reference better than a telecentric close-up.
    for name,pos,target,lens in [
        ('Camera_Head_Front',(0,-1.00,1.665),(0,-0.028,1.665),85),
        ('Camera_Head_ThreeQuarter',(0.59,-0.89,1.68),(0,-0.028,1.665),85),
        ('Camera_Head_Profile',(1.0,-0.035,1.675),(0,-0.035,1.665),85),
    ]:
        camera=bpy.data.objects[name]
        camera.location=pos
        camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type='PERSP'
        camera.data.lens=lens
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.shading.type='MATERIAL'
                area.spaces.active.region_3d.view_distance=0.65
                area.spaces.active.region_3d.view_location=(0,-0.035,1.66)
    return scene


def build(args):
    out=WORK/args.version
    out.mkdir(parents=True,exist_ok=True)
    source=args.source.resolve()
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    enable_paint()
    body=bpy.data.objects['M02_Body_Head']
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    delta=refine_face(body)
    tree=make_skin(body)
    bpy.context.view_layer.update()
    refine_eyes(body)
    groom=make_groom(body,rig,args.density)
    scene=setup_render(out,args.samples)
    activate(body)
    scene.camera=bpy.data.objects['Camera_Head_ThreeQuarter']
    scene.render.resolution_x=1200
    scene.render.resolution_y=1400
    scene.render.resolution_percentage=100
    readme=bpy.data.texts.get('00_READ_ME') or bpy.data.texts.new('00_READ_ME')
    readme.clear()
    readme.use_fake_user=True
    readme.write('M02 — skin and groom candidate.\n'
        'The v06 geometry source remains unchanged. Face refinement is a reversible shape key.\n'
        'Skin: native UCUPaint 2.4.9, CC0 MakeHuman skin maps, separate roughness, warm zones, stubble undertone and pore relief.\n'
        'Hair, eyebrows and short stubble: native editable hair curves, following the anatomical head bone.\n'
        'Look in Cycles Rendered for the full hair shader. All file images are packed.\n'
        'This is a visual review candidate, not a game export.\n')
    bpy.ops.file.pack_all()
    filename=out/('M02_Appearance_'+args.version.replace('appearance_','')+'.blend')
    if not args.no_save:
        bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False)
    report={
        'file':str(filename),'source':str(source),'source_sha256':source_hash,
        'ucupaint':U.common.get_current_version_str(),'blender':bpy.app.version_string,
        'face_shape_max_delta_m':delta,'skin_layers':[l.name for l in tree.yp.layers],
        'groom':[{'name':o.name,'type':o.type,'strands':o['strand_count']} for o in groom],
        'image_count':len([im for im in bpy.data.images if im.source=='FILE']),
        'renderer':scene.render.engine,'device':scene.cycles.device,
    }
    (out/'appearance_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('M02_APPEARANCE_BUILT '+json.dumps(report,ensure_ascii=False),flush=True)
    cameras={'head_front':'Camera_Head_Front','head_three_quarter':'Camera_Head_ThreeQuarter',
        'head_profile':'Camera_Head_Profile','body_front':'Camera_Body_Front','body_back':'Camera_Body_Back'}
    for view in args.render.split(','):
        if not view:
            continue
        scene.camera=bpy.data.objects[cameras[view]]
        scene.render.resolution_x,scene.render.resolution_y=(1200,1400) if view.startswith('head') else (1536,1536)
        scene.render.filepath=str(out/(view+'.png'))
        bpy.ops.render.render(write_still=True)
        print('M02_RENDER_DONE '+view,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--version',default='appearance_v05')
    parser.add_argument('--render',default='head_three_quarter,head_front')
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--density',type=float,default=1.0)
    parser.add_argument('--no-save',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    build(parser.parse_args(argv))
