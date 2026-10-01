"""Модели -> неизменённая геометрия, UV и геометрические подсказки Krita."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src'/'vss_textured'
ITEMS={
 'VSS_Vintorez_Picatinny': ('vss_picatinny/VSS_Vintorez_Picatinny_v2.blend',None),
 'PSO_VSS_4x24': ('vss_optics/PSO_VSS_4x24.blend','vss_optics/export/PSO_VSS_4x24/PSO_VSS_4x24_Game.blend'),
 'Rail_4x32': ('vss_optics/Rail_4x32.blend','vss_optics/export/Rail_4x32/Rail_4x32_Game.blend'),
 'Magazine_939_10_Empty': ('vss_mag_ammo/Magazine_939_10_Empty.blend','vss_mag_ammo/export/Magazine_939_10_Empty/Magazine_939_10_Empty_Game.blend'),
 'Magazine_939_10_Loaded': ('vss_mag_ammo/Magazine_939_10_Loaded.blend','vss_mag_ammo/export/Magazine_939_10_Loaded/Magazine_939_10_Loaded_Game.blend'),
 'Cartridge_939_SP5': ('vss_mag_ammo/Cartridge_939_SP5.blend','vss_mag_ammo/export/Cartridge_939_SP5/Cartridge_939_SP5_Game.blend'),
}

def source_lookup(root):
    vertices=[]; faces=[]; surface=[]; info=[]; keys={}
    deps=bpy.context.evaluated_depsgraph_get()
    for obj in root.children_recursive:
        if obj.type not in {'MESH','FONT','CURVE'}: continue
        evaluated=obj.evaluated_get(deps); mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles(); start=len(vertices)
        vertices.extend(E.MAP @ obj.matrix_world @ v.co for v in mesh.vertices)
        for tri in mesh.loop_triangles:
            mat=mesh.materials[tri.material_index]; key=(obj.name,mat.name)
            if key not in keys:
                bsdf=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
                keys[key]=len(info)
                info.append({'object':obj.name,'material':mat.name,
                    'color':list(bsdf.inputs['Base Color'].default_value[:3]) if bsdf else [.1,.1,.1],
                    'roughness':bsdf.inputs['Roughness'].default_value if bsdf else .5,
                    'metallic':bsdf.inputs['Metallic'].default_value if bsdf else 0})
            faces.append(tuple(start+v for v in tri.vertices)); surface.append(keys[key])
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),surface,info

def describe(obj,tree,surface,info,folder,resolution):
    mesh=obj.data; mesh.calc_loop_triangles(); uv=mesh.uv_layers.active.data
    positions=np.array([[*(obj.matrix_world @ v.co)] for v in mesh.vertices],dtype=np.float32)
    face_positions=[]; face_uv=[]; ids=[]
    for tri in mesh.loop_triangles:
        points=positions[list(tri.vertices)]
        hit=tree.find_nearest(Vector(points.mean(axis=0))); ids.append(surface[hit[2]])
        face_positions.append(points); face_uv.append([uv[i].uv[:] for i in tri.loops])
    np.savez_compressed(folder/(obj.name+'_geometry.npz'),
        positions=np.array(face_positions,dtype=np.float32),uv=np.array(face_uv,dtype=np.float32),
        ids=np.array(ids,dtype=np.int32),indices=np.array([tri.vertices[:] for tri in mesh.loop_triangles],dtype=np.int32))
    (folder/(obj.name+'_surfaces.json')).write_text(json.dumps({'resolution':resolution,
        'surfaces':info,'axes_blender_game':'x=sourceY,y=-sourceX,z=sourceZ',
        'geometry':obj.name+'_geometry.npz'},ensure_ascii=False,indent=2),encoding='utf-8')

def rifle_atlas(root,folder):
    parts=[o for o in root.children_recursive if o.type in {'MESH','FONT','CURVE'}]
    group=bpy.data.collections.new('Texture_Atlas'); bpy.context.scene.collection.children.link(group)
    root.name='VSS_Source'; game=bpy.data.objects.new('VSS_Vintorez_Picatinny',None); group.objects.link(game)
    game['variant']='Classic wooden VSS; own Picatinny rail; no scope'
    game['asset_type']='visual_weapon'; game['axes_gltf']='+Z forward, +Y up, -X right'
    stock=[]; metal=[]
    for obj in parts:
        mats=[m.name for m in obj.data.materials if m]
        (stock if any('walnut' in m for m in mats) else metal).append(obj)
    meshes=[]
    for name,items in [('Metal_Polymer',metal),('Wood',stock)]:
        body=E.joined(items,name,group,game); E.active(body)
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.008,area_weight=.5,correct_aspect=True,scale_to_bounds=True)
        bpy.ops.object.mode_set(mode='OBJECT'); meshes.append(body)
    for obj in parts: obj.hide_render=True; obj.hide_set(True)
    for body in meshes:
        scene=bpy.context.scene; scene.render.engine='CYCLES'; scene.cycles.samples=8
        scene.cycles.device='CPU'; scene.render.bake.margin=16
        image=bpy.data.images.new(body.name+'_normal',width=4096,height=4096,alpha=False); image.colorspace_settings.name='Non-Color'
        nodes=[]
        for mat in body.data.materials:
            node=mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image=image; mat.node_tree.nodes.active=node; nodes.append((mat,node))
        E.active(body); bpy.ops.object.bake(type='NORMAL')
        image.filepath_raw=str(folder/(body.name+'_normal_before.png')); B.enum_set(image,'file_format','PNG'); image.save()
        for mat,node in nodes: mat.node_tree.nodes.remove(node)
    keep={game,*game.children_recursive}
    for obj in list(bpy.data.objects):
        if obj not in keep and obj.type not in {'LIGHT','CAMERA'}: bpy.data.objects.remove(obj,do_unlink=True)
        elif obj.type in {'LIGHT','CAMERA'}: obj.matrix_world=E.MAP @ obj.matrix_world
    return meshes

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--id',required=True,choices=ITEMS)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]); folder=RAW/args.id; folder.mkdir(parents=True,exist_ok=True)
    native_path,game_path=ITEMS[args.id]; native=ROOT/'_asset_src'/native_path
    bpy.ops.wm.open_mainfile(filepath=str(native)); bpy.context.view_layer.update()
    tree,surfaces,info=source_lookup(bpy.data.objects[args.id])
    if game_path:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/'_asset_src'/game_path))
        bodies=[o for o in bpy.context.scene.objects if o.name=='Body']
        for body in bodies:
            mat=body.data.materials[0]
            normal=next(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and 'normal' in n.image.name.lower())
            normal.filepath_raw=str(folder/(body.name+'_normal_before.png')); B.enum_set(normal,'file_format','PNG'); normal.save()
    else: bodies=rifle_atlas(bpy.data.objects[args.id],folder)
    bpy.context.view_layer.update()
    for obj in bodies: describe(obj,tree,surfaces,info,folder,4096 if not game_path else 2048)
    (folder/'prepare.json').write_text(json.dumps({'id':args.id,'native':str(native),
        'native_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),
        'before_bounds':E.bounds([o for o in bpy.context.scene.objects if o.type=='MESH']),
        'atlas_objects':[o.name for o in bodies]},indent=2),encoding='utf-8')
    B.save_scene(folder/(args.id+'_UV.blend')); print('VSS_TEXTURE_PREPARED '+args.id,flush=True)
if __name__=='__main__': main()
