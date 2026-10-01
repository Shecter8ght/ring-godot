"""Вогнутый плечевой торец ВСС и прилегающий резиновый затыльник на копии."""
from pathlib import Path
import argparse,hashlib,json,sys
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_stock_v3'
TARGETS=('Wood_stock_with_integral_grip','Ventilated_rubber_butt_pad')
PIN_TARGETS=('Wood_pin_-1_28','Wood_pin_1_28')
Z_CENTER=-.0675
Z_HALF=.0485
SAG=.009

def displacement(point, wood):
    # Одна кривая для дерева и резины сохраняет их посадку по всей высоте.
    t=(point.z-Z_CENTER)/Z_HALF
    bow=SAG*max(0.,1-t*t)
    if wood:
        f=min(1.,max(0.,(.048-point.x)/.029))
        bow*=f*f*(3-2*f)
    return bow

def snapshot(root):
    deps=bpy.context.evaluated_depsgraph_get();result={}
    for obj in root.children_recursive:
        if obj.type not in {'MESH','CURVE','FONT'}:continue
        evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
        positions=[tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        result[obj.name]={'parent':obj.parent.name,'positions':positions,'triangles':len(mesh.loop_triangles)}
        evaluated.to_mesh_clear()
    return result

def bend(obj,wood):
    deps=bpy.context.evaluated_depsgraph_get()
    obj.data=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
    obj.modifiers.clear()
    bm=bmesh.new();bm.from_mesh(obj.data)
    matrix=obj.matrix_world.copy();inverse=matrix.inverted()
    for vertex in bm.verts:vertex.co=matrix @ vertex.co
    if wood:
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            plane_co=Vector((.048,0,0)),plane_no=Vector((1,0,0)),dist=1e-8)
    for number in range(1,49):
        z=-.116+number*.00198
        faces=[face for face in bm.faces if not wood or max(v.co.x for v in face.verts)<.0480001]
        edges={edge for face in faces for edge in face.edges}
        verts={vertex for face in faces for vertex in face.verts}
        bmesh.ops.bisect_plane(bm,geom=list(verts)+list(edges)+faces,
            plane_co=Vector((0,0,z)),plane_no=Vector((0,0,1)),dist=1e-8)
    local_faces=[face for face in bm.faces if not wood or max(v.co.x for v in face.verts)<.0480001]
    bmesh.ops.triangulate(bm,faces=local_faces)
    for vertex in bm.verts:
        vertex.co.x+=displacement(vertex.co,wood)
        vertex.co=inverse @ vertex.co
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    for face in obj.data.polygons:face.use_smooth=abs(face.normal.y)<.97
    obj['shoulder_contour']='Shared concave vertical contour; visual asset, estimated from user correction'
    obj['shoulder_curve_sag_mm']=SAG*1000

def seat_wood(obj,pad):
    # Срезаем только прежний задний участок; окна и остальная форма остаются прежними.
    deps=bpy.context.evaluated_depsgraph_get()
    obj.data=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
    obj.modifiers.clear()
    bm=bmesh.new();bm.from_mesh(obj.data)
    matrix=obj.matrix_world.copy();inverse=matrix.inverted()
    for vertex in bm.verts:vertex.co=matrix @ vertex.co
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
        plane_co=Vector((.044,0,0)),plane_no=Vector((1,0,0)),dist=1e-8,clear_inner=True)
    boundary=[edge for edge in bm.edges if edge.is_boundary]
    assert boundary and all(abs(v.co.x-.044)<1e-6 for e in boundary for v in e.verts)
    first=boundary[0].verts[0];current=first;previous=None;ring=[]
    while True:
        ring.append(current)
        choices=[edge.other_vert(current) for edge in current.link_edges if edge in boundary and edge.other_vert(current)!=previous]
        next_vertex=choices[0];previous,current=current,next_vertex
        if current==first:break
        assert len(ring)<=len(boundary)
    assert len(ring)==len(boundary)
    back=[bm.verts.new(Vector((.016,v.co.y,v.co.z))) for v in ring]
    for i in range(len(ring)):
        j=(i+1)%len(ring);bm.faces.new((ring[i],ring[j],back[j],back[i]))
    bm.faces.new(tuple(reversed(back)))
    for number in range(1,49):
        faces=[f for f in bm.faces if max(v.co.x for v in f.verts)<.0440001]
        edges={e for f in faces for e in f.edges};verts={v for f in faces for v in f.verts}
        bmesh.ops.bisect_plane(bm,geom=list(verts)+list(edges)+faces,
            plane_co=Vector((0,0,-.116+number*.00198)),plane_no=Vector((0,0,1)),dist=1e-8)
    padverts=[pad.matrix_world @ v.co for v in pad.data.vertices]
    padtree=BVHTree.FromPolygons(padverts,[p.vertices[:] for p in pad.data.polygons])
    zlo=min(v.z for v in padverts)+.0015;zhi=max(v.z for v in padverts)-.0015
    for vertex in bm.verts:
        if vertex.co.x<.0440001:
            weight=min(1.,max(0.,(.044-vertex.co.x)/.028));weight=weight*weight*(3-2*weight)
            vertex.co.z+=weight*(min(zhi,max(zlo,vertex.co.z))-vertex.co.z)
            hit=padtree.ray_cast(Vector((.07,vertex.co.y,vertex.co.z)),Vector((-1,0,0)))
            assert hit[0] is not None,tuple(vertex.co)
            vertex.co.x+=weight*(hit[0].x-.016-.00001)
        vertex.co=inverse @ vertex.co
    bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if max((matrix @ v.co).x for v in f.verts)<.045])
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(obj.data);bm.free();obj.data.update()
    for face in obj.data.polygons:face.use_smooth=abs(face.normal.y)<.97
    obj['shoulder_contour']='Rear wood surface fitted to actual curved rubber; original windows retained'
    obj['shoulder_curve_sag_mm']=SAG*1000

def main():
    p=argparse.ArgumentParser();p.add_argument('--render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    RAW.mkdir(parents=True,exist_ok=True)
    source=ROOT/'_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v2.blend'
    output=ROOT/'_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v3.blend'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];before=snapshot(root)
    bend(bpy.data.objects['Ventilated_rubber_butt_pad'],False)
    seat_wood(bpy.data.objects['Wood_stock_with_integral_grip'],bpy.data.objects['Ventilated_rubber_butt_pad'])
    # Штифты на скруглённом заднем углу переносим внутрь дерева, чтобы не висели над фаской.
    for name in PIN_TARGETS:
        obj=bpy.data.objects[name]
        matrix=obj.matrix_world.copy();matrix.translation+=Vector((.006,0,-.003))
        matrix.translation.x+=displacement(matrix.translation,True)
        obj.matrix_world=matrix
    bpy.context.view_layer.update();after=snapshot(root)
    assert before.keys()==after.keys()
    unchanged=[]
    for name in before:
        if name in TARGETS+PIN_TARGETS:continue
        assert before[name]==after[name],name
        unchanged.append(name)
    B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    B.camera('Camera_Shoulder_Profile',(-.03,-.9,-.0675),(.036,0,-.0675),.15)
    B.camera('Camera_Shoulder_Rear',(-.23,-.14,-.01),(.012,0,-.0675),.16)
    B.camera('Camera_Shoulder_Fit',(-.03,-.5,.015),(.026,0,-.064),.17)
    B.save_scene(output)
    report={'status':'PASS','source':str(source),'source_sha256':digest,'output':str(output),
        'changed_parts':list(TARGETS+PIN_TARGETS),'unchanged_mesh_parts':len(unchanged),'parts':len(after),
        'evaluated_triangles':sum(data['triangles'] for data in after.values()),
        'bounds':B.report_bounds('VSS_Assembly'),'sag_mm':SAG*1000,'shape':'vertical shoulder concavity shared by wood and rubber',
        'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==digest}
    (RAW/'geometry-change.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    if a.render:
        B.render_views(RAW,'shape',[('profile','Camera_Shoulder_Profile',1150,1000),('rear','Camera_Shoulder_Rear',1150,1000),('fit','Camera_Shoulder_Fit',1300,1000)])
    print('VSS_SHOULDER_REFINED',json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
