"""Turn v08's visible marking layouts into actual recessed geometry in v09.

The native master keeps editable Boolean operands and hidden lettering sources.
The source .blend is never overwritten. Run on the saved PM v08 assembly.
"""
from pathlib import Path
import hashlib, json, math
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v09'
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
for name in ('01_ПМ','02_Крепление','03_Коллиматор','Превью','Проверки'):(OUT/name).mkdir(parents=True,exist_ok=True)
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
previous=json.loads((ROOT/'review_v08/Проверки/revision_manifest.json').read_text(encoding='utf-8'))
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
rig=bpy.data.objects['PM_CONTROLS • select me'];optic=bpy.data.objects['PM_ReflexSight • asset root']
collection=bpy.data.collections.new('09a • Engraving sources — hidden');bpy.data.collections['09 • Reflex sight — separate asset'].children.link(collection)
HOSTS={key:bpy.data.objects['Reflex | K1 '+name] for key,name in [
    ('body','one-piece rounded lower casting'),('left','contoured side cheek -1'),('right','contoured side cheek 1'),
    ('hood','deep arched protective hood'),('cover','hinged round battery cover')]}

def tree(host):
    dg=bpy.context.evaluated_depsgraph_get();eo=host.evaluated_get(dg);me=eo.to_mesh()
    result=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return result

base_trees={key:tree(host) for key,host in HOSTS.items()}
sources=[o for o in bpy.data.objects if o.name.startswith('Reflex | Marking ')];rows=[]

def target(source):
    name=source.name.removeprefix('Reflex | Marking ')
    if name.startswith(('brand -1','model -1')):return 'left',Vector((0,-1,0))
    if name.startswith(('brand 1','model 1')):return 'right',Vector((0,1,0))
    if name.startswith('brand emblem'):return 'hood',Vector((0,-1 if name.endswith('-1') else 1,0))
    if name=='battery voltage':return 'cover',Vector((0,0,1))
    if name.startswith('elevation'):return 'body',Vector((0,0,1))
    if name.startswith('windage'):return 'body',Vector((0,1,0))
    if name=='front brand':return 'body',Vector((-1,0,0))
    return 'body',Vector((0,-1,0))

def hide_source(o,role):
    o['PM engraving helper']=True;o['Engraving role']=role;o.hide_render=True;o.hide_set(True)
    collection.objects.link(o)
    for c in list(o.users_collection):
        if c!=collection:c.objects.unlink(o)

from pm_engraving_geometry import solid_from_cap,stroke_cap

for source in sources:
    host_key,normal=target(source);host=HOSTS[host_key];name=source.name.removeprefix('Reflex | Marking ')
    # Keep these small layouts on the planar side wall, clear of its chamfer.
    if name=='windage':
        matrix=source.matrix_world.copy();matrix.translation.z+=.00020;source.matrix_world=matrix
    elif name.startswith('windage '):
        matrix=source.matrix_world.copy();matrix.translation.z-=.00080;source.matrix_world=matrix
    bpy.context.view_layer.update()
    temporary=source.copy();temporary.data=source.data.copy();S.collection.objects.link(temporary)
    temporary.hide_render=False;temporary.hide_set(False)
    text=source.data.body if source.type=='FONT' else name
    if source.type=='FONT':
        depth=.00009 if name.startswith(('brand ','front brand')) else .000045
        temporary.data.extrude=0;temporary.data.bevel_depth=0;temporary.data.resolution_u=24
    else:depth=.000040 if name.startswith('brand emblem') else .000025
    bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();eo=temporary.evaluated_get(dg)
    me=eo.to_mesh();vertices=[eo.matrix_world@v.co for v in me.vertices];faces=[tuple(p.vertices) for p in me.polygons]
    eo.to_mesh_clear();bpy.data.objects.remove(temporary,do_unlink=True)
    if not vertices:raise RuntimeError('Empty engraving source: '+source.name)
    centre=sum(vertices,Vector())/len(vertices)
    if source.type=='FONT':centre=source.matrix_world.translation.copy()
    hit,hit_normal,_,_=base_trees[host_key].ray_cast(centre+normal*.005,-normal,.020)
    if hit is None or abs(hit_normal.dot(normal))<.90:raise RuntimeError('No suitable marking face for '+source.name)
    plane=hit.dot(normal)
    if source.type=='FONT':
        vertices=[p+normal*(plane-depth-p.dot(normal)) for p in vertices]
    else:
        vertices,faces=stroke_cap(source,normal,plane,depth)
    vertices,faces=solid_from_cap(vertices,faces,normal,depth)
    inverse=optic.matrix_world.inverted();data=bpy.data.meshes.new('Engraving | '+name)
    data.from_pydata([tuple(inverse@p) for p in vertices],[],faces);data.update()
    bm=bmesh.new();bm.from_mesh(data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    topology=dict(boundary=sum(e.is_boundary for e in bm.edges),overfull=sum(len(e.link_faces)>2 for e in bm.edges),volume=bm.calc_volume(signed=True))
    print('PM_CUTTER_TOPOLOGY',name,topology,flush=True)
    if topology['boundary'] or topology['overfull'] or topology['volume']<=0:raise RuntimeError('Non-solid engraving operand '+name)
    bm.to_mesh(data);bm.free()
    cutter=bpy.data.objects.new('Engraving | cutter '+name,data);collection.objects.link(cutter)
    cutter.parent=optic;cutter.matrix_parent_inverse=Matrix.Identity(4);cutter.matrix_basis=Matrix.Identity(4)
    cutter['PM engraving helper']=True;cutter['Engraving role']='Boolean operand';cutter['Depth mm']=depth*1000
    cutter['Source']=source.name;cutter['Text']=text;cutter.display_type='WIRE';cutter.hide_render=True
    mod=host.modifiers.new('ENGRAVE | '+name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.context.view_layer.objects.active=host
    # Original radii precede the engraving; surface normals follow the cuts.
    while host.modifiers.find(mod.name)>0 and host.modifiers[host.modifiers.find(mod.name)-1].type=='WEIGHTED_NORMAL':
        bpy.ops.object.modifier_move_up(modifier=mod.name)
    hide_source(source,'Editable lettering master' if source.type=='FONT' else 'Editable symbol master')
    cutter.hide_set(True);bpy.context.view_layer.update()
    # Cap triangles provide points inside glyph strokes, avoiding counters and
    # the spaces between letters. Tube samples lie near the bottom of each groove.
    data.calc_loop_triangles();samples=[]
    for triangle in data.loop_triangles:
        pts=[cutter.matrix_world@data.vertices[i].co for i in triangle.vertices]
        cross=(pts[1]-pts[0]).cross(pts[2]-pts[0]);area=cross.length/2
        if area<1e-12 or cross.normalized().dot(normal)<.90:continue
        samples.append((area,sum(pts,Vector())/3))
    samples.sort(key=lambda pair:pair[0],reverse=True);selected=[]
    for area,p in samples:
        if all((p-q).length>.00012 for q in selected):selected.append(p)
        if len(selected)==8:break
    if len(selected)<2:raise RuntimeError('No reliable stroke samples for '+source.name)
    rows.append(dict(source=source.name,cutter=cutter.name,host=host.name,text=text,depth_mm=depth*1000,
        normal=list(normal),surface_plane=plane,samples=[list(p) for p in selected],
        normal_local=list((inverse.to_3x3()@normal).normalized()),
        plane_point_local=list(inverse@(normal*plane)),samples_local=[list(inverse@p) for p in selected]))
    print('PM_ENGRAVING',name,host.name,depth*1000,flush=True)

for host in HOSTS.values():host['Engraved markings']=True
optic['Markings']='Actual recessed Boolean geometry; hidden editable masters and operands'
action=rig.animation_data.action
if action:
    action.use_fake_user=True;action=action.copy();action.name='Geometry inspection v09';action.use_fake_user=True;rig.animation_data.action=action
S.frame_set(1);bpy.context.view_layer.update()
check=[];final_trees={host.name:tree(host) for host in HOSTS.values()}
for row in rows:
    normal=Vector(row['normal']);t=final_trees[row['host']];depth=row['depth_mm']/1000;measurements=[]
    for point in row['samples']:
        p=Vector(point);hit,_,_,_=t.ray_cast(p+normal*.004,-normal,.015)
        measured=(row['surface_plane']-hit.dot(normal))*1000 if hit else None
        measurements.append(dict(depth_mm=measured,pass_depth=measured is not None and depth*.60<=measured/1000<=depth*1.40))
    row['measurements']=measurements;row['pass_engraving']=all(m['pass_depth'] for m in measurements);check.append(row)
    print('PM_ENGRAVING_DEPTH',row['text'],row['pass_engraving'],[m['depth_mm'] for m in measurements],flush=True)
record=dict(source=previous['source'],source_sha256=previous['source_sha256'],parent_geometry=str(SOURCE),parent_sha256=SOURCE_HASH,
    revision='v09',changes=['Все надписи, эмблемы и стрелки ЗОРИН К-1 выполнены настоящими утопленными вырезами: крупные буквы 0,09 мм, мелкие 0,045 мм, символы 0,025–0,040 мм'],
    inherited_changes=previous['changes']+previous['inherited_changes'],texture_approval=False,brand='ЗОРИН',model='К-1',
    optic_sources=previous['optic_sources'],unchanged_fingerprints=previous['unchanged_fingerprints'],
    non_optic_geometry_unchanged=True,unchanged_meshes=previous['unchanged_meshes'],fit_note=previous['fit_note'])
(OUT/'Проверки/engraving.json').write_text(json.dumps(dict(markings=check,pass_engraving=all(r['pass_engraving'] for r in check),visible_marking_objects=0),ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
if not all(r['pass_engraving'] for r in check):raise RuntimeError('Engraving depth check failed; candidate not saved')
note=bpy.data.texts.new('ЗОРИН К-1 • утопленные надписи v09')
note.write('Надписи/стрелки/эмблемы вырезаны реальными Boolean DIFFERENCE. Источники FONT/Curve и Mesh-резаки скрыты в 09a.\nДля изменения надписи обновить резак после правки FONT; автоматической связи FONT → Mesh нет.\nРадиусы исходного корпуса стоят до вырезов, нормали после. Производственная UV/UCUPaint не начаты.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v09.blend'))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_V09_SAVED',len(rows),str(OUT/'01_ПМ/PM_Geometry_v09.blend'),flush=True)
