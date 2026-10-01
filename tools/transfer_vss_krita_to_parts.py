"""Проверенный атлас -> прежние детали ВСС, с сохранением дерева и их трансформов."""
from pathlib import Path
import json,sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'_asset_src/vss_textured/VSS_Vintorez_Picatinny'

def build_lookup(obj):
    mesh=obj.data;mesh.calc_loop_triangles();vertices=[obj.matrix_world @ v.co for v in mesh.vertices]
    faces=[t.vertices[:] for t in mesh.loop_triangles];uv=mesh.uv_layers.active.data
    data=[([vertices[i] for i in t.vertices],[Vector(uv[i].uv) for i in t.loops]) for t in mesh.loop_triangles]
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),data

def projected_uv(point,points,uvs):
    a,b,c=points;v0,v1,v2=b-a,c-a,point-a
    d00,d01,d11=v0.dot(v0),v0.dot(v1),v1.dot(v1);den=d00*d11-d01*d01
    if abs(den)<1e-22:return uvs[0]
    v=(d11*v2.dot(v0)-d01*v2.dot(v1))/den;w=(d00*v2.dot(v1)-d01*v2.dot(v0))/den
    return uvs[0]*(1-v-w)+uvs[1]*v+uvs[2]*w

def main():
    candidate=FOLDER/'VSS_Vintorez_Picatinny_Textured.blend'
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    lookups={name:build_lookup(bpy.data.objects[name]) for name in ('Metal_Polymer','Wood')}
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v2.blend'))
    with bpy.data.libraries.load(str(candidate),link=False) as (source,target):
        target.materials=['VSS_Krita_Metal_Polymer','VSS_Krita_Wood']
    mats={name:mat for name,mat in zip(('Metal_Polymer','Wood'),target.materials)}
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];parts=[o for o in root.children_recursive if o.type in {'MESH','CURVE','FONT'}]
    deps=bpy.context.evaluated_depsgraph_get();max_distance=0.; uv_outside=0;worst=[]
    for obj in parts:
        atlas='Wood' if any(m and 'walnut' in m.name for m in obj.data.materials) else 'Metal_Polymer'
        tree,data=lookups[atlas];mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        positions=[E.MAP @ obj.matrix_world @ v.co for v in mesh.vertices]
        if obj.type!='MESH':
            old=obj;obj=bpy.data.objects.new(old.name+'_Textured',mesh)
            for collection in old.users_collection:collection.objects.link(obj)
            obj.parent=old.parent;obj.matrix_world=old.matrix_world.copy()
            bpy.data.objects.remove(old,do_unlink=True)
        else:obj.modifiers.clear();obj.data=mesh
        layer=mesh.uv_layers.new(name='Krita_Atlas');mesh.uv_layers.active=layer;layer.active_render=True
        mesh.calc_loop_triangles()
        for face in mesh.loop_triangles:
            center=sum((positions[i] for i in face.vertices),Vector())/3
            hit=tree.find_nearest(center);max_distance=max(max_distance,hit[3])
            if hit[3]>.00005:worst.append({'part':obj.name,'distance_mm':hit[3]*1000})
            tri,tex=data[hit[2]]
            for index in face.loops:
                uv=projected_uv(positions[mesh.loops[index].vertex_index],tri,tex)
                layer.data[index].uv=uv
                uv_outside+=any(c<-.01 or c>1.01 for c in uv)
        mesh.materials.clear();mesh.materials.append(mats[atlas])
        for face in mesh.polygons:face.material_index=0
    # После join неплоский n-gon может получить другую диагональ, при прежних вершинах.
    # Допустим только субмиллиметровый перенос UV; геометрия берётся из прежнего evaluated mesh.
    if max_distance>.00035 or uv_outside:raise RuntimeError(str({'max_surface_distance':max_distance,'UV_outside':uv_outside}))
    bpy.context.view_layer.update();B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    bpy.context.scene['texture_source']='Krita 5.3.4; native part tree retained'
    B.save_scene(FOLDER/'VSS_Vintorez_Picatinny_Textured_Editable.blend')
    B.render_views(FOLDER,'editable',[('beauty','Camera_Beauty_Right',1800,800),('receiver','Camera_Receiver_Detail',1300,850)])
    (FOLDER/'parts-transfer.json').write_text(json.dumps({'status':'PASS','parts':len(parts),'max_surface_distance_m':max_distance,'UV_outside':uv_outside,
        'worst_projections':sorted(worst,key=lambda x:x['distance_mm'],reverse=True)[:8],
        'preserved':'original parent tree/transforms; evaluated geometry; modifiers evaluated in texture copy; original retained'},indent=2),encoding='utf-8')
    print('VSS_KRITA_PARTS_TRANSFER_PASS',len(parts),flush=True)
if __name__=='__main__':main()
