"""Sparse aged lint/web strands requested by the owner; separate from the 24 accepted meshes."""
import math
import bpy
from mathutils import Vector

# t: distance along the shackle centreline from its left socket; s: around tube.
# Millimetres. Most strands sit above the sliding contact, a few cling near a socket.
STRANDS=[
 ('right_old_web_A',[(100.0,9.2),(101.4,10.0),(102.6,9.7),(104.0,10.6),(105.2,10.4)],.025,.06),
 ('right_old_web_B',[(102.8,10.1),(104.0,10.4),(104.8,11.1),(106.3,11.0)],.018,.04),
 ('right_caught_loop',[(104.0,12.0),(104.6,12.8),(105.7,12.7),(106.1,11.8),(105.4,11.5),(104.8,12.0)],.030,.12),
 ('right_dust_bound',[(107.0,10.3),(107.6,11.0),(108.7,10.9),(109.2,11.8)],.026,.025),
 ('left_clinging_A',[(12.5,10.5),(13.6,11.3),(15.1,11.0),(16.5,11.7),(18.0,11.1)],.023,.04),
 ('left_clinging_B',[(15.1,10.6),(15.9,11.2),(16.8,10.8),(17.3,11.5)],.016,.025),
 ('arch_sparse',[(55.0,10.2),(56.0,11.0),(57.6,10.6),(58.6,11.2)],.020,.04),
 ('socket_sheltered',[(115.0,17.4),(115.8,18.1),(117.0,17.8),(117.6,18.6)],.025,.025)]

def analytic(t,s):
    first=19.8;arc=math.pi*25
    if t<first:c=Vector((-25,0,69+t));radial=Vector((-1,0,0))
    elif t<first+arc:
        angle=math.pi-(t-first)/25
        c=Vector((25*math.cos(angle),0,88.8+25*math.sin(angle)))
        radial=Vector((math.cos(angle),0,math.sin(angle)))
    else:c=Vector((25,0,88.8-(t-first-arc)));radial=Vector((1,0,0))
    phi=s/39.*2*math.pi-math.pi
    return (c+6.2*(math.cos(phi)*radial+math.sin(phi)*Vector((0,1,0))))*.001

def apply():
    name='V05 · старые пыльные волокна'
    previous=bpy.data.collections.get(name)
    if previous:
        for o in list(previous.objects):bpy.data.objects.remove(o,do_unlink=True)
        bpy.data.collections.remove(previous)
    col=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(col)
    material=bpy.data.materials.get('V05 · матовые загрязнённые волокна') or bpy.data.materials.new('V05 · матовые загрязнённые волокна')
    material.use_nodes=True;bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value=(.28,.265,.22,1);bsdf.inputs['Roughness'].default_value=.88
    bsdf.inputs['Metallic'].default_value=0.;bsdf.inputs['IOR'].default_value=1.46
    shackle=bpy.data.objects['Shackle_forged_closed'];root=bpy.data.objects['Padlock_ROOT']
    inverse=shackle.matrix_world.inverted();deps=bpy.context.evaluated_depsgraph_get();ev=shackle.evaluated_get(deps)
    for label,path,radius,lift in STRANDS:
        data=bpy.data.curves.new(label,'CURVE');data.dimensions='3D';data.resolution_u=12
        data.bevel_depth=radius*.001;data.bevel_resolution=2;data.use_fill_caps=True
        spline=data.splines.new('BEZIER');spline.bezier_points.add(len(path)-1)
        for i,((t,s),point) in enumerate(zip(path,spline.bezier_points)):
            guess=analytic(t,s);ok,nearest,normal,_=ev.closest_point_on_mesh(inverse@guess)
            assert ok,label
            envelope=(0.,.5,1.,.5,0.,.2)[i%6]
            position=shackle.matrix_world@(nearest+normal*(radius+lift*envelope)*.001)
            point.co=position;point.handle_left_type=point.handle_right_type='AUTO'
            point.radius=.65 if i in (0,len(path)-1) else 1.
        obj=bpy.data.objects.new('Fiber · '+label,data);col.objects.link(obj);obj.parent=root
        obj['stage']='surface_deposit_fibers';obj['base_geometry_changed']=False
        data.materials.append(material)
    print('V05_FIBERS_ADDED',len(STRANDS),'separate curves; accepted meshes untouched',flush=True)

if __name__=='__main__':
    from pathlib import Path
    target=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'/'models'/'padlock_v05_textured.blend'
    bpy.ops.wm.open_mainfile(filepath=str(target));apply();bpy.ops.wm.save_as_mainfile(filepath=str(target),relative_remap=False)
