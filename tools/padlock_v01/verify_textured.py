"""Reopen saved deliverable, compare its surface with the accepted master, render it."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
parser=argparse.ArgumentParser()
parser.add_argument('--root',default=str(WORK))
parser.add_argument('--views',default='front_34,rear_34,side,top_joint,keyhole_close')
parser.add_argument('--size',type=int,default=1000)
parser.add_argument('--side-light',action='store_true')
parser.add_argument('--audit-only',action='store_true')
parser.add_argument('--report-name',default=None)
parser.add_argument('--revision',choices=['v02','v03','v04'],default='v02')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.report_name is None:args.report_name='texture_verification'+('' if args.revision=='v02' else '_'+args.revision)+'.json'
root=Path(args.root)
master=root/'models'/'padlock_v01_geometry.blend'
expected_hash='5BE1E2579133AAC5C8B20ADA9228DD2D31875781B51928EE4CDAC2F1E335CA1C'
assert hashlib.sha256(master.read_bytes()).hexdigest().upper()==expected_hash
bpy.ops.wm.open_mainfile(filepath=str(master))
deps=bpy.context.evaluated_depsgraph_get()
original={}
for obj in bpy.data.objects:
    if obj.get('stage')!='untextured_geometry':continue
    evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
    original[obj.name]=([tuple(evaluated.matrix_world@v.co) for v in mesh.vertices],len(mesh.polygons))
    evaluated.to_mesh_clear()

target=root/'models'/('padlock_'+args.revision+'_textured.blend')
bpy.ops.wm.open_mainfile(filepath=str(target))
parts=[o for o in bpy.data.objects if o.get('stage')=='textured_highpoly_candidate']
assert {o.name for o in parts}==set(original)
checks=[];all_points=[]
for obj in parts:
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    source,faces=original[obj.name]
    assert len(points)==len(source) and len(obj.data.polygons)==faces
    tree=KDTree(len(source))
    for i,p in enumerate(source):tree.insert(Vector(p),i)
    tree.balance()
    distance=max(tree.find(p)[2] for p in points)
    assert distance<1e-7,(obj.name,distance)
    reverse=KDTree(len(points))
    for i,p in enumerate(points):reverse.insert(p,i)
    reverse.balance()
    distance=max(distance,max(reverse.find(Vector(p))[2] for p in source))
    assert distance<1e-7
    bm=bmesh.new();bm.from_mesh(obj.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges);bm.free()
    assert not nonmanifold,obj.name
    uv=obj.data.uv_layers.active
    assert uv and all(math.isfinite(c) and -1e-6<=c<=1+1e-6 for loop in uv.data for c in loop.uv)
    all_points.extend(points)
    checks.append({'mesh':obj.name,'vertices':len(points),'polygons':faces,
                   'surface_max_deviation_mm':distance*1000,'nonmanifold_edges':nonmanifold})

images=[]
for img in bpy.data.images:
    if not (img.name.startswith('reference_') or img.name.startswith('Padlock_')):continue
    path=Path(bpy.path.abspath(img.filepath))
    assert img.packed_file is not None and img.filepath.startswith('//') and path.is_file(),img.name
    row={'name':img.name,'path':img.filepath,'packed':True,'external_exists':True,
         'size':list(img.size),'colorspace':img.colorspace_settings.name}
    if img.name.startswith('Padlock_'):
        header=path.read_bytes()[:29]
        assert header[:8]==b'\x89PNG\r\n\x1a\n'
        row['png_bit_depth']=header[24]
        assert tuple(img.size)==(4096,4096)
        assert img.colorspace_settings.name==('sRGB' if 'basecolor' in img.name.lower() else 'Non-Color')
        assert row['png_bit_depth']==(16 if 'normal' in img.name.lower() else 8)
    images.append(row)
assert len(images)==(11 if args.revision=='v04' else 9),len(images)
material=parts[0].active_material
assert all(o.active_material==material for o in parts)
bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
assert bsdf.inputs['Base Color'].links[0].from_node.type=='TEX_IMAGE'
assert bsdf.inputs['Normal'].links[0].from_node.type=='NORMAL_MAP'
if args.revision=='v04':
    assert bsdf.inputs['Coat Weight'].is_linked and bsdf.inputs['Coat Roughness'].is_linked
    assert bsdf.inputs['Coat Normal'].links[0].from_node.type=='NORMAL_MAP'
bounds=[(max(p[i] for p in all_points)-min(p[i] for p in all_points))*1000 for i in range(3)]
report={'status':'PASS','file':str(target),'master_sha256':expected_hash,
        'bounds_mm':bounds,'parts':checks,'images':images,
        'geometry_preserved':True,'game_ready':False,
        'notes':['One 4K atlas; native Painter project retained with editable layers.',
                 'Dense evaluated copy of approved geometry; separate parametric master preserved.',
                 'Stamp is a non-verbal approximation because the reference text is illegible.']}
(root/'checks'/args.report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('TEXTURED_FILE_VERIFIED',len(parts),'parts;',len(images),'packed images; dimensions',bounds,flush=True)

scene=bpy.context.scene;scene.render.resolution_x=scene.render.resolution_y=args.size
scene.cycles.device='CPU';scene.cycles.samples=96;scene.cycles.use_denoising=False
if args.side_light:
    lamp=bpy.data.objects['Large_key'];lamp.location=(-.20,-.08,.16)
    lamp.rotation_euler=(Vector((0,0,.055))-lamp.location).to_track_quat('-Z','Y').to_euler()
    lamp.data.shape='DISK';lamp.data.size=.08
    for name in ('Broad_fill','Rear_fill'):bpy.data.objects[name].data.energy*=.22
    next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs['Strength'].default_value=.20
suffix='_side_light' if args.side_light else '_textured'
if args.revision!='v02':suffix+='_'+args.revision
for name in ([] if args.audit_only else filter(None,args.views.split(','))):
    scene.camera=bpy.data.objects[name]
    scene.render.filepath=str(root/'previews'/(name+suffix+'.png'))
    bpy.ops.render.render(write_still=True)
    print('SAVED_FILE_PREVIEW',name,suffix,flush=True)
