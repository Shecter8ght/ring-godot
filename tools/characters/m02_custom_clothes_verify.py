"""Reopen original M02 clothing; check construction, modules and initial rig fit.

Pose screenshots are internal diagnostics, not animation deliverables.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector


def evaluated_points(obj):
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    points=[evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    evaluated.to_mesh_clear()
    assert all(math.isfinite(value) for point in points for value in point),obj.name
    return points


def boundaries(obj):
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    edges=[edge for edge in bm.edges if edge.is_boundary]
    nonmanifold=sum(not edge.is_manifold and not edge.is_boundary for edge in bm.edges)
    degenerate=sum(face.calc_area()<1e-12 for face in bm.faces)
    pool=set(edges)
    count=0
    while pool:
        stack=[pool.pop()]
        count+=1
        while stack:
            edge=stack.pop()
            for vertex in edge.verts:
                for next_edge in vertex.link_edges:
                    if next_edge in pool:
                        pool.remove(next_edge)
                        stack.append(next_edge)
    bm.free()
    return {'boundary_components':count,'nonmanifold_nonboundary_edges':nonmanifold,'zero_area_faces':degenerate}


def global_rotate(rig,name,axis,angle):
    bone=rig.pose.bones[name]
    pivot=bone.head.copy()
    bone.matrix=Matrix.Translation(pivot) @ Matrix.Rotation(angle,4,axis) @ Matrix.Translation(-pivot) @ bone.matrix
    bpy.context.view_layer.update()


def verify_assets(path):
    report=json.loads((path.parent/'clothes_report.json').read_text(encoding='utf-8'))
    results=[]
    for item in report['separate_assets']:
        file=path.parent/item['file']
        bpy.ops.wm.open_mainfile(filepath=str(file))
        collection=bpy.data.collections[item['native_collection_asset']]
        rig=bpy.data.objects['M02_New_Anatomical_Rig']
        controls=bpy.data.objects['M02_Clothing_Controls']
        assert collection.asset_data
        assert rig.name in collection.objects and controls.name in collection.objects
        assert rig.parent==controls
        assert 'M02_Body_Head' not in bpy.data.objects
        meshes=[obj for obj in collection.objects if obj.type=='MESH']
        assert len(meshes)==item['mesh_objects']
        bpy.context.view_layer.update()
        assert all(not obj.hide_render and not obj.hide_viewport for obj in meshes),item
        for obj in meshes:
            assert obj.parent==rig
            assert next(modifier for modifier in obj.modifiers if modifier.type=='ARMATURE').object==rig
            assert len(evaluated_points(obj))>0
        results.append({'file':str(file),'mesh_objects':len(meshes),'self_contained_collection_asset':True})
    return results


def verify(path,render,diagnostic_dir):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    report=json.loads((path.parent/'clothes_report.json').read_text(encoding='utf-8'))
    source=Path(report['source'])
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['source_sha256']
    body=bpy.data.objects['M02_Body_Head']
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    controls=bpy.data.objects['M02_Clothing_Controls']
    parts=[bpy.data.objects[item['name']] for item in report['parts']]
    original_groups={group.index:group.name for group in body.vertex_groups}
    for obj in parts:
        assert obj.parent==rig,obj.name
        armature=next((modifier for modifier in obj.modifiers if modifier.type=='ARMATURE'),None)
        assert armature and armature.object==rig,obj.name
        names={group.index:group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            total=sum(group.weight for group in vertex.groups
                if names[group.group] in rig.data.bones and rig.data.bones[names[group.group]].use_deform)
            assert .98<total<1.02,(obj.name,vertex.index,total)
        assert len(evaluated_points(obj))>0
    construction={name:boundaries(bpy.data.objects[name]) for name in ['M02_Custom_TShirt','M02_Custom_Work_Trousers']}
    assert construction['M02_Custom_TShirt']['boundary_components']==4,construction
    assert construction['M02_Custom_Work_Trousers']['boundary_components']==3,construction
    assert all(item['nonmanifold_nonboundary_edges']==0 and item['zero_area_faces']==0 for item in construction.values()),construction
    modules={}
    visible_count=len(evaluated_points(body))
    for key,prefix in [('shirt','01_Original_TShirt_M02'),('trousers','02_Original_Work_Trousers_M02'),('boots','03_Original_Work_Boots_M02')]:
        col=bpy.data.collections[prefix]
        controls[key]=False
        controls.update_tag()
        bpy.context.view_layer.update()
        assert all(obj.hide_render and obj.hide_viewport for obj in col.objects),key
        mask=body.modifiers['Clothing | hide anatomy under '+key]
        assert not mask.show_render and not mask.show_viewport,key
        modules[key]={'objects':len(col.objects),'independent_toggle':True}
        controls[key]=True
        controls.update_tag()
        bpy.context.view_layer.update()
        assert not next(obj for obj in col.objects if obj.name in ['M02_Custom_TShirt','M02_Custom_Work_Trousers'] or 'shaped outsole' in obj.name).hide_render,key
    with bpy.data.libraries.load(str(source),link=False) as (_,destination):
        destination.objects=['M02_Body_Head']
    source_body=destination.objects[0]
    assert len(body.data.vertices)==len(source_body.data.vertices)==13380
    assert all((a.co-b.co).length<1e-7 for a,b in zip(body.data.vertices,source_body.data.vertices))
    assert all(tuple(a.vertices)==tuple(b.vertices) for a,b in zip(body.data.polygons,source_body.data.polygons))
    assert all((a.uv-b.uv).length<1e-7 for a,b in zip(body.data.uv_layers.active.data,source_body.data.uv_layers.active.data))
    assert len(body.data.shape_keys.key_blocks)==len(source_body.data.shape_keys.key_blocks)
    for a,b in zip(body.data.shape_keys.key_blocks,source_body.data.shape_keys.key_blocks):
        assert a.name==b.name and abs(a.value-b.value)<1e-7
        assert all((x.co-y.co).length<1e-7 for x,y in zip(a.data,b.data))
    bpy.data.objects.remove(source_body,do_unlink=True)
    images=[image for image in bpy.data.images if image.source=='FILE' and image.filepath]
    assert all(image.packed_file and image.packed_file.size>0 for image in images)
    rest={obj.name:evaluated_points(obj) for obj in parts}
    saved_pose={bone.name:bone.matrix_basis.copy() for bone in rig.pose.bones}
    diagnostic_dir.mkdir(parents=True,exist_ok=True)
    poses=[]
    for name,rotations in [
        ('arms_down',[('upperarm01.L','Y',1.05),('upperarm01.R','Y',-1.05)]),
        ('limb_flex',[('upperleg01.L','X',-.80),('lowerleg01.L','X',1.15),('lowerarm01.L','Z',-.85)]),
    ]:
        for bone_name,axis,angle in rotations: global_rotate(rig,bone_name,axis,angle)
        distances={}
        for obj in parts:
            points=evaluated_points(obj)
            assert len(points)==len(rest[obj.name])
            distances[obj.name]=max((a-b).length for a,b in zip(rest[obj.name],points))
        assert max(distances.values())>.05,(name,distances)
        assert max(distances.values())<1.6,(name,distances)
        poses.append({'pose':name,'maximum_displacement_m':max(distances.values())})
        if render:
            scene=bpy.context.scene
            scene.cycles.samples=32
            prefs=bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type='OPTIX'
            prefs.get_devices()
            for device in prefs.devices: device.use=device.type=='OPTIX'
            scene.camera=bpy.data.objects['Custom_Clothes_ThreeQuarter']
            scene.render.filepath=str(diagnostic_dir/(name+'.png'))
            bpy.ops.render.render(write_still=True)
        for bone in rig.pose.bones: bone.matrix_basis=saved_pose[bone.name]
        bpy.context.view_layer.update()
    result={'status':'PASS','file':str(path),'source_sha256':report['source_sha256'],
        'source_body_topology_uv_and_all_shape_keys_preserved':True,
        'construction':construction,'modules':modules,'packed_character_images':len(images),
        'all_clothing_vertices_have_normalized_rig_weights':True,
        'internal_pose_checks':poses,'visible_evaluated_body_vertices_with_masks':visible_count,
        'limitation':'Initial weight transfer and static pose checks; full animation corrections, final UV/PBR and game preparation are later stages.'}
    (diagnostic_dir/'clothes_verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('M02_CUSTOM_CLOTHES_VERIFY '+json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path)
    parser.add_argument('--render',action='store_true')
    parser.add_argument('--diagnostic-dir',type=Path)
    parser.add_argument('--assets',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    path=args.file.resolve()
    diagnostics=args.diagnostic_dir.resolve() if args.diagnostic_dir else path.parent/'verification'
    verify(path,args.render,diagnostics)
    if args.assets:
        assets=verify_assets(path)
        report=json.loads((diagnostics/'clothes_verification.json').read_text(encoding='utf-8'))
        report['separate_assets_reopened']=assets
        (diagnostics/'clothes_verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print('M02_INDIVIDUAL_ASSETS_VERIFY '+json.dumps(assets,ensure_ascii=False),flush=True)
