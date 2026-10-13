"""Keep K1's recessed windage legend and arrow visible beside its dial."""
from pathlib import Path
import json,math,sys
import bpy,bmesh,addon_utils
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from pm_engraving_geometry import solid_from_cap,stroke_cap,engraving_report
OUT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement/review_v09'
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
root=bpy.data.objects['PM_ReflexSight • asset root'];host=bpy.data.objects['Reflex | K1 one-piece rounded lower casting']
mw=root.matrix_world.copy();rotation=mw.to_quaternion().to_matrix();inverse=mw.inverted();normal=rotation@Vector((0,1,0))
record=json.loads((OUT/'Проверки/engraving.json').read_text(encoding='utf-8'))
if record.get('windage_visible_clearance'):raise RuntimeError('Windage clearance already completed; do not shrink the text again')
names=('windage','windage direction','windage arrow')
mods={name:next(m for m in host.modifiers if m.name=='ENGRAVE | '+name) for name in names}
for mod in mods.values():mod.show_viewport=False
bpy.context.view_layer.update();eo=host.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=eo.to_mesh()
base=BVHTree.FromPolygons([eo.matrix_world@v.co for v in mesh.vertices],[tuple(p.vertices) for p in mesh.polygons]);eo.to_mesh_clear()
def at(x,y,z):return mw.translation+rotation@Vector((x/1000,y/1000,z/1000))
master=bpy.data.objects['Reflex | Marking windage'];matrix=master.matrix_world.copy();matrix.translation=at(21.0,16.50,9.92);master.matrix_world=matrix
master.data.size*=.60/.90
arc=[at(17+4.65*math.cos(2.8-j*.55/64),16.58,13.9+4.65*math.sin(2.8-j*.55/64)) for j in range(65)]
forward=rotation@Vector((math.sin(2.25),0,-math.cos(2.25)));side=normal.cross(forward).normalized();p=arc[-1]
paths={'windage direction':arc,'windage arrow':[p-forward*.00055+side*.00023,p,p-forward*.00055-side*.00023]}
for name,points in paths.items():
    source=bpy.data.objects['Reflex | Marking '+name];inv=source.matrix_world.inverted()
    source.data.splines.clear();spline=source.data.splines.new('POLY');spline.points.add(len(points)-1)
    for point,co in zip(spline.points,points):point.co=(*tuple(inv@co),1)
bpy.context.view_layer.update()
for name in names:
    row=next(r for r in record['markings'] if r['source']=='Reflex | Marking '+name)
    source=bpy.data.objects[row['source']];cutter=bpy.data.objects[row['cutter']];depth=row['depth_mm']/1000
    center=source.matrix_world.translation.copy() if source.type=='FONT' else sum(paths[name],Vector())/len(paths[name])
    hit,hn,_,_=base.ray_cast(center+normal*.005,-normal,.020)
    assert hit is not None and hn.dot(normal)>.99,'No flat marking surface'
    plane=hit.dot(normal)
    if source.type=='FONT':
        temporary=source.copy();temporary.data=source.data.copy();S.collection.objects.link(temporary);temporary.hide_set(False)
        temporary.data.bevel_depth=0;temporary.data.extrude=0;temporary.data.resolution_u=24
        bpy.context.view_layer.update();eo=temporary.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=eo.to_mesh()
        vertices=[eo.matrix_world@v.co for v in mesh.vertices];faces=[tuple(p.vertices) for p in mesh.polygons]
        eo.to_mesh_clear();bpy.data.objects.remove(temporary,do_unlink=True)
        vertices=[p+normal*(plane-depth-p.dot(normal)) for p in vertices]
    else:vertices,faces=stroke_cap(source,normal,plane,depth)
    vertices,faces=solid_from_cap(vertices,faces,normal,depth)
    data=bpy.data.meshes.new('Engraving | visible '+name);data.from_pydata([inverse@p for p in vertices],[],faces);data.update()
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0;bm.to_mesh(data);bm.free();cutter.data=data
    bpy.context.view_layer.update();data.calc_loop_triangles();candidates=[]
    for tri in data.loop_triangles:
        points=[cutter.matrix_world@data.vertices[i].co for i in tri.vertices];cross=(points[1]-points[0]).cross(points[2]-points[0])
        if cross.length>2e-12 and cross.normalized().dot(normal)>.99:candidates.append((cross.length,sum(points,Vector())/3))
    candidates.sort(key=lambda pair:pair[0],reverse=True);selected=[]
    for _,point in candidates:
        if all((point-q).length>.00008 for q in selected):selected.append(point)
        if len(selected)==8:break
    assert len(selected)>=2
    row.update(normal=list(normal),surface_plane=plane,samples=[list(p) for p in selected],normal_local=list((inverse.to_3x3()@normal).normalized()),
        plane_point_local=list(inverse@(normal*plane)),samples_local=[list(inverse@p) for p in selected])
    mods[name].show_viewport=True
bpy.context.view_layer.update();fresh=engraving_report(record);assert fresh['pass_engraving']
record['windage_visible_clearance']='Legend at x21 z9.92 mm; upper-left arrow radius4.65 mm outside4.08 mm dial bezel'
(OUT/'Проверки/engraving.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Проверки/windage_clearance.json').write_text(json.dumps(fresh,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v09.blend'))
print('PM_WINDAGE_VISIBLE',fresh['pass_engraving'],flush=True)
