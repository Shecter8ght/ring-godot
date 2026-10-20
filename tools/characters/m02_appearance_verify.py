"""Reopen M02 appearance and check portability, preserved anatomy and groom binding."""
import argparse
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys

import addon_utils
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def mesh_points(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    points=[evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    return points


def root_distances(body,groom):
    bpy.context.view_layer.update()
    deps=bpy.context.evaluated_depsgraph_get()
    bvh=BVHTree.FromObject(body,deps)
    result={}
    for obj in groom:
        # Sample roots across each whole groom, including the jaw and temples.
        indices=list(range(0,len(obj.data.curves),max(1,len(obj.data.curves)//40)))
        to_body=body.matrix_world.inverted() @ obj.matrix_world
        positions=obj.data.attributes['position'].data
        distances=[]
        for i in indices:
            first=obj.data.curve_offset_data[i].value
            point=to_body @ positions[first].vector
            near,normal,_,distance=bvh.find_nearest(point)
            assert near is not None
            distances.append(distance*abs(body.matrix_world.to_scale().x))
        result[obj.name]=max(distances)
    return result


def verify(path,render=False):
    report=json.loads((path.parent/'appearance_report.json').read_text(encoding='utf-8'))
    source=Path(report['source'])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['source_sha256'],'Source was changed'
    bpy.ops.wm.open_mainfile(filepath=str(path))
    body=bpy.data.objects['M02_Body_Head']
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    groom=[bpy.data.objects[item['name']] for item in report['groom']]
    assert len(body.data.vertices)==13380 and len(body.data.polygons)==13378
    assert body.data.shape_keys and len(body.data.shape_keys.key_blocks)==2
    bm=bmesh.new()
    bm.from_mesh(body.data)
    bad_edges=sum(not edge.is_manifold for edge in bm.edges)
    nonquads=sum(len(face.verts)!=4 for face in bm.faces)
    bm.free()
    assert bad_edges==0 and nonquads==0
    for obj in groom:
        assert obj.type=='CURVES' and len(obj.data.curves)>0
        assert obj.parent==rig and obj.parent_bone=='head'
        assert all(math.isfinite(value) for item in obj.data.attributes['position'].data for value in item.vector)
        assert all(item.value>0 and math.isfinite(item.value) for item in obj.data.attributes['radius'].data)
    images=[image for image in bpy.data.images if image.source=='FILE' and image.filepath]
    assert all(image.packed_file and image.packed_file.size>0 for image in images)
    skin=body.active_material
    bsdf=next(n for n in skin.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    assert all(bsdf.inputs[name].is_linked for name in ['Base Color','Roughness','Normal'])
    for image in images:
        # Reading must remain possible from packed data with unavailable external paths.
        image.filepath='//__packed_portability_check__/'+image.name
    if render:
        prefs=bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type='OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use=device.type=='OPTIX'
        bpy.context.scene.cycles.samples=48
        bpy.context.scene.render.filepath=str(path.parent/'reopened_head.png')
        bpy.ops.render.render(write_still=True)
    roots_rest=root_distances(body,groom)
    assert max(roots_rest.values())<0.006,roots_rest
    bone=rig.pose.bones['head']
    original=bone.matrix_basis.copy()
    bone.rotation_mode='XYZ'
    bone.rotation_euler.y+=0.22
    bpy.context.view_layer.update()
    roots_turned=root_distances(body,groom)
    assert max(roots_turned.values())<0.006,roots_turned
    bone.matrix_basis=original
    bpy.context.view_layer.update()
    deformation=[]
    rest=mesh_points(body)
    for name,angle in [('lowerarm01.L',0.9),('lowerleg01.L',0.9),('finger2-1.L',0.5)]:
        bone=rig.pose.bones[name]
        original=bone.matrix_basis.copy()
        bone.rotation_mode='XYZ'
        bone.rotation_euler.x+=angle
        bpy.context.view_layer.update()
        posed=mesh_points(body)
        maximum=max((a-b).length for a,b in zip(rest,posed))
        assert maximum>0.002 and all(math.isfinite(x) for p in posed for x in p)
        deformation.append({'bone':name,'max_displacement_m':maximum})
        bone.matrix_basis=original
        bpy.context.view_layer.update()
    # Compare the stored base cage and UV coordinates with the accepted source.
    with bpy.data.libraries.load(str(source),link=False) as (source_data,destination):
        destination.objects=['M02_Body_Head']
    original_body=destination.objects[0]
    assert all((a.co-b.co).length<1e-7 for a,b in zip(body.data.vertices,original_body.data.vertices))
    assert all((a.uv-b.uv).length<1e-7 for a,b in zip(body.data.uv_layers.active.data,original_body.data.uv_layers.active.data))
    module='bl_ext.blender_org.ucupaint'
    bpy.context.preferences.use_preferences_save=False
    if module not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    U=importlib.import_module(module)
    group=next(n for n in skin.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    layers=group.node_tree.yp.layers
    assert len(layers)>=10 and all(layer.enable for layer in layers)
    pores=next(layer for layer in layers if layer.name.startswith('06 |'))
    normal_index=next(i for i,ch in enumerate(group.node_tree.yp.channels) if ch.type=='NORMAL')
    assert U.common.get_entity_prop_value(pores.channels[normal_index],'bump_distance')>0
    result={'status':'PASS','file':str(path),'blender':bpy.app.version_string,
        'source_sha256':report['source_sha256'],'source_cage_and_uv_preserved':True,
        'nonmanifold_edges':bad_edges,'nonquad_faces':nonquads,'shape_keys':2,
        'packed_images':len(images),'native_ucupaint_layers':len(layers),
        'groom_strands':{obj.name:len(obj.data.curves) for obj in groom},
        'maximum_root_distance_rest_m':roots_rest,'maximum_root_distance_turned_m':roots_turned,
        'deformation':deformation,'portability_render_without_ucupaint':render}
    (path.parent/'appearance_verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('M02_APPEARANCE_VERIFY '+json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    parser.add_argument('--render',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    verify(args.file.resolve(),args.render)
