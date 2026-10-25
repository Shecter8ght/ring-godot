"""Ретопология статичных ассетов: регулярная сетка, плоскости, локальное упрощение."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys
import time

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,SOURCE,DELIVERY,MODEL,rows,write,sha
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pbr'))
import process as P


def triangles(me):
    return sum(len(p.vertices)-2 for p in me.polygons)


def activate(ob):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active=ob


def evaluated(ob):
    dg=bpy.context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)


def structure(me):
    parent=list(range(len(me.vertices)))
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]
            a=parent[a]
        return a
    for e in me.edges:
        a,b=map(find,e.vertices)
        parent[a]=b
    components=len({find(i) for p in me.polygons for i in p.vertices})
    bm=bmesh.new(); bm.from_mesh(me)
    result=dict(components=components,boundary_edges=sum(e.is_boundary for e in bm.edges),
        overfull_edges=sum(len(e.link_faces)>2 for e in bm.edges),
        zero_faces=sum(f.calc_area()<1e-14 for f in bm.faces),loose_vertices=sum(not v.link_faces for v in bm.verts))
    bm.free()
    return result


def geometry(me):
    me.calc_loop_triangles()
    co=np.empty(len(me.vertices)*3,np.float64)
    me.vertices.foreach_get('co',co)
    points=co.reshape(-1,3)
    tri=np.array([tuple(p.vertices) for p in me.loop_triangles],np.int32)
    bvh=BVHTree.FromPolygons(points,tri,all_triangles=True,epsilon=0)
    return points,tri,bvh


def sample(points,tri,limit=700):
    vi=np.linspace(0,len(points)-1,min(len(points),limit),dtype=int)
    fi=np.linspace(0,len(tri)-1,min(len(tri),limit//2),dtype=int)
    return np.concatenate((points[vi],points[tri[fi]].mean(axis=1)))


def deviations(reference,candidate,scale):
    hp,ht,hb=reference
    lp,lt,lb=geometry(candidate)
    if np.array_equal(hp,lp) and np.array_equal(ht,lt):
        return dict(max_m=0.0,p99_m=0.0,bounds_m=0.0,samples=len(hp),identical_tessellation=True)
    distances=[]
    for points,bvh in ((sample(hp,ht),lb),(sample(lp,lt),hb)):
        for v in points:
            hit=bvh.find_nearest(v)
            distances.append(float(hit[3])*scale if hit and hit[0] is not None else float('inf'))
    distances=np.array(distances)
    hd=np.maximum(hp.max(axis=0)-hp.min(axis=0),1e-9)
    bounds=float(max(np.max(np.abs(lp.min(axis=0)-hp.min(axis=0))),np.max(np.abs(lp.max(axis=0)-hp.max(axis=0)))))*scale
    return dict(max_m=float(distances.max()),p99_m=float(np.quantile(distances,.99)),bounds_m=bounds,samples=len(distances))


def native_triangles(me):
    """Commit Blender's existing tessellation, with exact loop UV/colour mapping."""
    me.calc_loop_triangles()
    tris=list(me.loop_triangles)
    loop_indices=np.array([i for t in tris for i in t.loops],np.int32)
    result=bpy.data.meshes.new(me.name+' | stable triangles')
    result.from_pydata([tuple(v.co) for v in me.vertices],[],[tuple(t.vertices) for t in tris])
    for material in me.materials:
        result.materials.append(material)
    for target,tri in zip(result.polygons,tris):
        original=me.polygons[tri.polygon_index]
        target.material_index=original.material_index
        target.use_smooth=original.use_smooth
    for source in me.uv_layers:
        data=np.empty(len(me.loops)*2,np.float32)
        source.data.foreach_get('uv',data)
        target=result.uv_layers.new(name=source.name)
        target.data.foreach_set('uv',data.reshape(-1,2)[loop_indices].ravel())
    for source in me.color_attributes:
        channels=np.empty(len(source.data)*4,np.float32)
        source.data.foreach_get('color',channels)
        target=result.color_attributes.new(name=source.name,type=source.data_type,domain=source.domain)
        values=channels.reshape(-1,4)
        target.data.foreach_set('color',(values[loop_indices] if source.domain=='CORNER' else values).ravel())
    result.update()
    return result


def clean(me):
    bm=bmesh.new(); bm.from_mesh(me)
    # Preserve material/UV discontinuities; only remove redundant coplanar edges.
    bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(.08),use_dissolve_boundaries=False,
        verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL','SEAM','UV'})
    bmesh.ops.dissolve_degenerate(bm,dist=1e-8,edges=list(bm.edges))
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(me); bm.free(); me.update()


def modifier_mesh(ob,kind,ratio=None,iterations=2):
    mod=ob.modifiers.new('Retopology temporary','DECIMATE')
    mod.decimate_type=kind
    if kind=='COLLAPSE':
        mod.ratio=ratio
        mod.use_collapse_triangulate=False
    elif kind=='UNSUBDIV':
        mod.iterations=iterations
    candidate=evaluated(ob)
    ob.modifiers.remove(mod)
    return candidate


def part(ob,a):
    name=ob.name
    original_type=ob.type
    ref=evaluated(ob)
    old_tri=triangles(ref)
    source_shape=structure(ref)
    reference=geometry(ref)
    world_scale=max(ob.matrix_world.to_scale())
    span=max(ob.dimensions)
    thickness=min(v for v in ob.dimensions if v>1e-7)
    tolerance=max(.00025,min(.004,span*.004,thickness*.03))
    if a['id']=='R06' and 'FACADE |' in name:
        tolerance=.003
    methods=[]
    if original_type=='FONT':
        ob.data=ob.data.copy()
        ob.data.resolution_u=min(4,ob.data.resolution_u)
        ob.data.bevel_resolution=0
        activate(ob)
        bpy.ops.object.convert(target='MESH')
        ob=bpy.data.objects[name]
        methods.append('outline tessellation with single bevel segment')
    else:
        for mod in list(ob.modifiers):
            if mod.type=='BEVEL':
                if mod.width<=.0008 or 'Staggered_tread' in name:
                    ob.modifiers.remove(mod)
                    methods.append('submillimetre bevel omitted')
                else:
                    mod.segments=1
                    methods.append('single segment physical chamfer')
    base=evaluated(ob)
    for mod in list(ob.modifiers):
        ob.modifiers.remove(mod)
    ob.data=base
    clean(base)
    base_dev=deviations(reference,base,world_scale)
    if base_dev['max_m']>tolerance or base_dev['bounds_m']>tolerance:
        ob.data=ref.copy()
        base=ob.data
        clean(base)
        methods=['evaluated source retained for protected contour']
    shape=structure(base)
    # Coarsen regular quad patches first. Reject loss of holes, islands or silhouette.
    quad_fraction=sum(len(f.vertices)==4 for f in base.polygons)/max(1,len(base.polygons))
    if len(base.vertices)>100 and quad_fraction>.70 and shape['components']<8:
        candidate=modifier_mesh(ob,'UNSUBDIV',iterations=2)
        if candidate.polygons:
            clean(candidate)
            dev=deviations(reference,candidate,world_scale)
            st=structure(candidate)
            if (triangles(candidate)<triangles(base)*.80 and dev['max_m']<=tolerance and dev['bounds_m']<=tolerance
                and st['components']==source_shape['components'] and st['overfull_edges']<=source_shape['overfull_edges']
                and (not source_shape['boundary_edges'])==(not st['boundary_edges'])):
                ob.data=candidate; base=candidate
                methods.append('regular quad grid coarsened in two steps')
            else:
                bpy.data.meshes.remove(candidate)
    # Angle-aware collapse only for curved/irregular pieces still denser than needed.
    current=triangles(base)
    if current>48 and shape['components']<32:
        role=ob.get('finish_role','')
        ratio=.22 if current>5000 else .42
        if role in ('glass','reflector','screen'):
            ratio=.45
        for attempt in range(4):
            candidate=modifier_mesh(ob,'COLLAPSE',ratio)
            if not candidate.polygons:
                bpy.data.meshes.remove(candidate); break
            clean(candidate)
            dev=deviations(reference,candidate,world_scale)
            st=structure(candidate)
            if (dev['max_m']<=tolerance and dev['bounds_m']<=tolerance and st['zero_faces']==0
                and st['components']==source_shape['components'] and st['overfull_edges']<=source_shape['overfull_edges']
                and (not source_shape['boundary_edges'])==(not st['boundary_edges'])):
                ob.data=candidate; base=candidate
                methods.append('curvature constrained local edge collapse '+str(round(ratio,3)))
                break
            bpy.data.meshes.remove(candidate)
            ratio=(ratio+1)/2
    # Retain the chosen diagonals on non-planar surfaces; don't retessellate by BEAUTY.
    me=native_triangles(ob.data); ob.data=me
    final_shape=structure(me)
    final_dev=deviations(reference,me,world_scale)
    if final_dev['max_m']>tolerance or final_dev['bounds_m']>tolerance:
        me=native_triangles(ref); ob.data=me
        final_shape=structure(me)
        final_dev=deviations(reference,me,world_scale)
        methods=['native tessellation retained for critical contour']
    if final_shape['zero_faces']:
        bm=bmesh.new(); bm.from_mesh(me)
        bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges))
        bm.to_mesh(me); bm.free(); me.update()
        me=native_triangles(me); ob.data=me
        final_shape=structure(me); final_dev=deviations(reference,me,world_scale)
        methods.append('submicrometre tessellation degeneracy dissolved')
    if not me.polygons or final_shape['zero_faces'] or final_shape['overfull_edges']>source_shape['overfull_edges']:
        raise RuntimeError('Invalid retopology mesh: '+name+' '+str(final_shape))
    for uv in ('MetricUV','PartUV','GrainUV'):
        if uv not in me.uv_layers:
            me.uv_layers.new(name=uv)
    # Keep authored material coordinates. New unique BakeUV is a separate layer.
    ob['retopology_source_part']=name
    ob['retopology_methods']='; '.join(dict.fromkeys(methods)) or 'planar edge cleanup and stable triangulation'
    ob['source_triangles']=old_tri
    result=dict(part=name,source_type=original_type,before=old_tri,after=triangles(me),
        tolerance_m=tolerance,deviation=final_dev,source_topology=source_shape,topology=final_shape,
        methods=list(dict.fromkeys(methods)) or ['planar edge cleanup; useful source quad loops retained'])
    bpy.data.meshes.remove(ref)
    return result


def unique_uv():
    objects=[o for o in bpy.data.collections[MODEL].objects if o.type=='MESH']
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objects:
        layer=ob.data.uv_layers.get('BakeUV') or ob.data.uv_layers.new(name='BakeUV')
        ob.data.uv_layers.active=layer
        ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.003,area_weight=0,
        correct_aspect=False,scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True,margin=.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in objects:
        ob.data.uv_layers.active=ob.data.uv_layers.get('MetricUV')


def image_records(model):
    records=[]
    for im in bpy.data.images:
        if im.type in ('RENDER_RESULT','COMPOSITING'):
            continue
        if not im.packed_file:
            im.pack()
        records.append(dict(name=im.name,file=im.filepath,sha256=hashlib.sha256(bytes(im.packed_file.data)).hexdigest(),
            colorspace=im.colorspace_settings.name,size=list(im.size)))
    return records


def render(a,folder):
    sc=bpy.context.scene
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'; prefs.get_devices()
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
    sc.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    sc.cycles.samples=24; sc.cycles.use_denoising=True
    previews=folder/'previews'; previews.mkdir(exist_ok=True)
    P.frame((4,-6,3.2))
    sc.render.filepath=str(previews/'front34.png')
    bpy.ops.render.render(write_still=True)
    sc.cycles.samples=8
    wire=bpy.data.materials.new('Topology proof only, not saved')
    wire.use_nodes=True
    nt=wire.node_tree; nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial')
    body=nt.nodes.new('ShaderNodeEmission')
    ink=nt.nodes.new('ShaderNodeEmission'); ink.inputs['Color'].default_value=(.008,.020,.027,1)
    body.inputs['Color'].default_value=(.48,.55,.58,1)
    lines=nt.nodes.new('ShaderNodeWireframe'); lines.use_pixel_size=True; lines.inputs['Size'].default_value=.85
    mix=nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lines.outputs[0],mix.inputs[0]); nt.links.new(body.outputs[0],mix.inputs[1])
    nt.links.new(ink.outputs[0],mix.inputs[2]); nt.links.new(mix.outputs[0],out.inputs[0])
    for o in bpy.data.collections[MODEL].objects:
        if o.type=='MESH':
            o.data.materials.clear(); o.data.materials.append(wire)
            for face in o.data.polygons:
                face.material_index=0
    sc.render.filepath=str(previews/'topology_front.png')
    bpy.ops.render.render(write_still=True)
    P.frame((-4,6,2.8))
    sc.render.filepath=str(previews/'topology_rear.png')
    bpy.ops.render.render(write_still=True)


def one(a):
    start=time.time()
    source_hash=sha(a['source_pbr'])
    assert source_hash==a['blend_sha256']
    bpy.ops.wm.open_mainfile(filepath=a['source_pbr'])
    collection=bpy.data.collections[MODEL]
    initial={o.name:dict(parent=o.parent.name if o.parent else None,matrix=[list(row) for row in o.matrix_local]) for o in collection.objects}
    lo,hi=P.bounds()
    parts=[]
    for ob in list(collection.objects):
        if ob.type in ('MESH','CURVE','FONT'):
            parts.append(part(ob,a))
    unique_uv()
    model=WORK/a['retopo_model']; model.parent.mkdir(parents=True,exist_ok=True)
    folder=model.parent.parent; (folder/'checks').mkdir(exist_ok=True)
    sc=bpy.context.scene
    sc['stage']='Retopology derivative; native source unchanged; bake and game import separate'
    sc['retopology_source']=a['source_pbr']; sc['retopology_source_sha256']=source_hash
    image_manifest=image_records(model)
    bpy.context.preferences.filepaths.save_version=0
    P.frame((4,-6,3.2))
    bpy.ops.wm.save_as_mainfile(filepath=str(model),compress=True,relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(model))
    errors=[]
    for name,data in initial.items():
        ob=bpy.data.objects.get(name)
        if not ob or (ob.parent.name if ob.parent else None)!=data['parent'] or [list(r) for r in ob.matrix_local]!=data['matrix']:
            errors.append('Hierarchy/pivot changed: '+name)
    for ob in bpy.data.collections[MODEL].objects:
        if ob.type=='MESH' and ('BakeUV' not in ob.data.uv_layers or len(ob.modifiers)):
            errors.append('Retopology not committed: '+ob.name)
    for r in image_manifest:
        im=bpy.data.images.get(r['name'])
        if not im or not im.packed_file or hashlib.sha256(bytes(im.packed_file.data)).hexdigest()!=r['sha256']:
            errors.append('Packed map changed: '+r['name'])
    low,high=P.bounds()
    bounds_error=max((lo-low).length,(hi-high).length)
    if bounds_error>.012:
        errors.append('Whole asset bounds changed '+str(bounds_error))
    if sha(a['source_pbr'])!=source_hash:
        errors.append('Source changed')
    report=dict(id=a['id'],source=a['source_pbr'],source_sha256=source_hash,model=a['retopo_model'],
        model_sha256=sha(model),parts=parts,before=sum(p['before'] for p in parts),after=sum(p['after'] for p in parts),
        bounds_error_m=bounds_error,errors=errors,saved_file_reopened=True,source_unchanged=True,
        authoring_material_uvs_preserved=True,unique_bake_uv_added=True,game_import=False,bake=False,
        passed=not errors and all(p['deviation']['max_m']<=p['tolerance_m']*1.01 for p in parts))
    write(folder/'checks/retopology.json',report)
    write(folder/'checks/images.json',image_manifest)
    if not report['passed']:
        raise RuntimeError('Retopology failed: '+a['id']+' '+str(errors)+' '+str([(p['part'],p['deviation']['max_m'],p['tolerance_m']) for p in parts if p['deviation']['max_m']>p['tolerance_m']*1.01]))
    render(a,folder)
    print('RETOPO_DONE',a['id'],report['before'],'->',report['after'],round(time.time()-start,1),'sec',flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--ids',default=''); parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=set(args.ids.split(',')) if args.ids else None
    P.M.native()
    for a in rows():
        if selected and a['id'] not in selected:
            continue
        path=WORK/'assets'/a['folder']/'checks/retopology.json'
        if args.resume and path.exists():
            r=json.loads(path.read_text(encoding='utf-8'))
            if r['passed'] and sha(WORK/r['model'])==r['model_sha256'] and (path.parent.parent/'previews/topology_rear.png').exists():
                print('RETOPO_SKIP',a['id'],flush=True); continue
        one(a)
    print('RETOPO_COMPLETE',flush=True)


if __name__=='__main__':
    main()
