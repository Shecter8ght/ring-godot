"""Развёртка подробной копии принятой формы для отдельного проекта Painter."""
import json
import math
from pathlib import Path

import bpy
import bmesh
import numpy as np
import importlib.util

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/"_asset_src"/"padlock_v01"
APPROVED=WORK/"models"/"padlock_v01_geometry.blend"


def hidden_face(obj,face):
    name=obj.name
    c=face.calc_center_median()
    if name.endswith("_shaft") or name.endswith("_seat"):return True
    if name.startswith("Front_cheek"):return c.y>-0.010 and face.normal.y>0.8
    if name.startswith("Rear_cheek"):return c.y<0.010 and face.normal.y<-0.8
    if name.startswith("Body_perimeter"):
        if abs(face.normal.y)>.8:return True
        return c.x*face.normal.x+(c.z-.035)*face.normal.z<0
    if "front_pressed" in name:return face.normal.y>.8
    if "rear_peened" in name or name.endswith("_head"):return face.normal.y<-.8
    return False


def make_seams(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    zmin=min(v.co.z for v in bm.verts)
    xmax=max(v.co.x for v in bm.verts)
    name=obj.name
    for edge in bm.edges:
        edge.seam=False
        if len(edge.link_faces)!=2:
            edge.seam=True;continue
        cats=[1 if f.normal.y>.95 else -1 if f.normal.y<-.95 else 0 for f in edge.link_faces]
        if cats[0]!=cats[1] or edge.calc_face_angle()>math.radians(55):edge.seam=True
        mid=(edge.verts[0].co+edge.verts[1].co)/2
        delta=edge.verts[1].co-edge.verts[0].co
        if name.startswith("Shackle"):
            ids=[v.index for v in edge.verts]
            if all(i%64==0 for i in ids) or all(i//64==0 for i in ids) or all(i//64==144 for i in ids):edge.seam=True
        elif name.startswith(("Front_cheek","Rear_cheek","Body_perimeter")):
            if mid.z<zmin+.0004 and abs(mid.x)<.002:edge.seam=True
            if abs(delta.y)>.7*(abs(delta.x)+abs(delta.z)):
                angle=math.atan2(mid.z-.035,mid.x)
                if abs(math.sin(2*angle))<.045:edge.seam=True
            if name.startswith("Front_cheek") and abs(delta.y)>abs(delta.x)+abs(delta.z):
                if (mid.z<.0083 and abs(mid.x-.0008)<.0005) or (mid.z<.0472 and mid.z>.046 and abs(mid.x-.0341)<.0005):edge.seam=True
        elif abs(delta.y)>abs(delta.x)+abs(delta.z) and mid.x>xmax-1e-5:
            edge.seam=True
    bm.to_mesh(obj.data);bm.free()
    if not obj.data.uv_layers:obj.data.uv_layers.new(name="UVMap")


def shrink_hidden_islands(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    uv=bm.loops.layers.uv.active
    adjacency={f.index:set() for f in bm.faces}
    vertex_uv={}
    for face in bm.faces:
        for loop in face.loops:
            co=loop[uv].uv
            key=(loop.vert.index,round(co.x,7),round(co.y,7))
            vertex_uv.setdefault(key,[]).append(face.index)
    for items in vertex_uv.values():
        for face in items:adjacency[face].update(items)
    visited=set()
    for face in bm.faces:
        if face.index in visited:continue
        component=[];todo=[face.index]
        while todo:
            i=todo.pop()
            if i in visited:continue
            visited.add(i);component.append(bm.faces[i]);todo.extend(adjacency[i]-visited)
        if sum(hidden_face(obj,f) for f in component)<len(component)*.85:continue
        loops=[loop for f in component for loop in f.loops]
        center=sum((loop[uv].uv.copy() for loop in loops),loops[0][uv].uv.copy()*0)/len(loops)
        factor=.16 if obj.name.endswith(("_shaft","_seat")) else .28
        for loop in loops:loop[uv].uv=center+(loop[uv].uv-center)*factor
    bm.to_mesh(obj.data);bm.free()


def straighten_shackle(obj):
    # Дужка — развёртываемая труба: её U-образный изгиб не должен гнуть UV-остров.
    mesh=obj.data;data=mesh.uv_layers.active.data
    distances=[]
    for ring in range(145):
        if ring<=24:value=(88.8-59.8)*ring/24
        elif ring<=120:value=29+math.pi*25*(ring-24)/96
        else:value=29+math.pi*25+29*(ring-120)/24
        distances.append(value*.001)
    circumference=math.pi*.0124
    for face in mesh.polygons:
        if len(face.vertices)==4:
            js=[mesh.loops[i].vertex_index%64 for i in face.loop_indices]
            seam=0 in js and 63 in js
            for loop_index,j in zip(face.loop_indices,js):
                vertex=mesh.loops[loop_index].vertex_index
                half=0 if max(mesh.loops[i].vertex_index//64 for i in face.loop_indices)<=72 else 1
                data[loop_index].uv=(.03+half*.09+circumference*(64 if seam and j==0 else j)/64,
                                     .03+distances[vertex//64]-half*distances[72])
        else:
            end=mesh.loops[face.loop_start].vertex_index//64
            for loop_index in face.loop_indices:
                j=mesh.loops[loop_index].vertex_index%64
                a=2*math.pi*j/64
                data[loop_index].uv=(.055+(.018 if end else 0)+.0062*math.cos(a),.01+.0062*math.sin(a))


def projection_on_profile(points,profile):
    p=np.asarray(points);a=np.asarray(profile)*.001
    keep=np.linalg.norm(a-np.roll(a,1,axis=0),axis=1)>1e-10
    a=a[keep];b=np.roll(a,-1,axis=0);d=b-a
    lengths=np.linalg.norm(d,axis=1);cumulative=np.r_[0,np.cumsum(lengths)]
    t=np.clip(((p[:,None,:]-a[None,:,:])*d[None,:,:]).sum(axis=2)/(lengths**2)[None,:],0,1)
    delta=p[:,None,:]-a[None,:,:]-t[:,:,None]*d[None,:,:]
    dist=(delta*delta).sum(axis=2);ids=dist.argmin(axis=1);row=np.arange(len(points))
    return cumulative[ids]+t[row,ids]*lengths[ids],dist[row,ids],cumulative[-1]


def planar_and_strip_uv(obj,build):
    mesh=obj.data;uv=mesh.uv_layers.active.data
    points=[(v.co.x,v.co.z) for v in mesh.vertices]
    if obj.name.startswith("Body_perimeter"):
        profiles=[build.scaled_profile(build.body_profile(),.961),build.scaled_profile(build.body_profile(),.895)]
    else:
        small=[(34.1+1.65*math.cos(i*2*math.pi/96),48.5+1.65*math.sin(i*2*math.pi/96)) for i in range(96)]
        profiles=[build.body_profile(),build.key_profile(),small]
    projected=[projection_on_profile(points,profile) for profile in profiles]
    groups={}
    def put(face,key,coordinates):
        group=groups.setdefault(key,len(groups))
        offset=(.03+.18*(group%5),.03+.18*(group//5))
        for li,co in zip(face.loop_indices,coordinates):uv[li].uv=(offset[0]+co[0],offset[1]+co[1])
    for face in mesh.polygons:
        ids=list(face.vertices);coords=[mesh.vertices[i].co for i in ids]
        center=sum(coords,coords[0]*0)/len(coords)
        if obj.name.startswith("Body_perimeter"):
            bore=next((x for x in (-.025,.025) if abs(math.hypot(center.x-x,center.y)-.0066)<.00035 and center.z>.05 and abs(face.normal.z)<.45),None)
            if bore is not None:
                angles=[math.atan2(c.y,c.x-bore)%(2*math.pi) for c in coords]
                half=int((math.atan2(center.y,center.x-bore)%(2*math.pi))//math.pi)
                if max(angles)-min(angles)>math.pi:angles=[a+2*math.pi if a<math.pi else a for a in angles]
                put(face,("bore",bore,half),[(.0066*(a-half*math.pi),c.z-.05) for a,c in zip(angles,coords)])
                continue
        if abs(face.normal.y)>.5:
            put(face,("cap",1 if face.normal.y>0 else -1),[(c.x+.042,c.z+.001) for c in coords])
            continue
        profile_index=min(range(len(profiles)),key=lambda k:float(np.mean(projected[k][1][ids])))
        s,dist,length=projected[profile_index]
        values=[float(s[i]) for i in ids]
        if max(values)-min(values)>length/2:values=[v+length if v<length/2 else v for v in values]
        count=4 if profile_index<2 else 1
        piece=int((sum(values)/len(values))//(length/count))
        put(face,("wall",profile_index,piece),[(value-piece*length/count,c.y+.014) for value,c in zip(values,coords)])


def main():
    bpy.ops.wm.open_mainfile(filepath=str(APPROVED))
    root=bpy.data.objects["Padlock_ROOT"]
    root["accepted_geometry_sha256"]="5BE1E2579133AAC5C8B20ADA9228DD2D31875781B51928EE4CDAC2F1E335CA1C"
    root["status"]="Accepted shape; evaluated high-poly copy for UV and Painter; editable geometry master retained separately"
    parts=[o for o in bpy.data.objects if o.get("stage")=="untextured_geometry"]
    deps=bpy.context.evaluated_depsgraph_get()
    snapshots={o.name:bpy.data.meshes.new_from_object(o.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps) for o in parts}
    mat=bpy.data.materials.new("Padlock")
    mat.diffuse_color=(.24,.24,.24,1)
    for obj in parts:
        obj.modifiers.clear()
        obj.data=snapshots[obj.name]
        obj.data.materials.clear();obj.data.materials.append(mat)
        for p in obj.data.polygons:p.material_index=0
        obj["stage"]="accepted_shape_highpoly_texture_copy"
        make_seams(obj)
    cutters=bpy.data.collections.get("Construction | editable cutters")
    if cutters:
        for obj in list(cutters.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(cutters)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.unwrap(method="ANGLE_BASED",margin=.001)
    bpy.ops.object.mode_set(mode="OBJECT")
    spec=importlib.util.spec_from_file_location("padlock_builder",Path(__file__).with_name("build.py"))
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    for obj in parts:
        if obj.name.startswith(("Front_cheek","Rear_cheek","Body_perimeter")):planar_and_strip_uv(obj,builder)
    straighten_shackle(next(o for o in parts if o.name.startswith("Shackle")))
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in parts:shrink_hidden_islands(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    pack={"rotate":True,"scale":True,"margin_method":"FRACTION","margin":12/4096}
    prop=bpy.ops.uv.pack_islands.get_rna_type().properties.get("rotate_method")
    if prop and "AXIS_ALIGNED" in {i.identifier for i in prop.enum_items}:pack["rotate_method"]="AXIS_ALIGNED"
    bpy.ops.uv.pack_islands(**pack)
    bpy.ops.object.mode_set(mode="OBJECT")
    area=0;details=[];layout=[]
    for obj in parts:
        mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data
        a=0
        for tri in mesh.loop_triangles:
            p,q,r=[uv[i].uv for i in tri.loops]
            a+=abs((q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x))/2
        area+=a
        details.append({"mesh":obj.name,"uv_area":a,"triangles":len(mesh.loop_triangles)})
        layout.append({"mesh":obj.name,"polygons":[[list(uv[i].uv) for i in p.loop_indices] for p in mesh.polygons]})
    (WORK/"checks"/"uv_stats.json").write_text(json.dumps({"resolution":4096,"padding_px":12,"uv_area_sum":area,"parts":details},indent=2),encoding="utf-8")
    (WORK/"checks"/"uv_layout.json").write_text(json.dumps(layout),encoding="utf-8")
    (WORK/"painter").mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/"models"/"padlock_v02_texture_source.blend"),relative_remap=False)
    bpy.ops.export_scene.fbx(filepath=str(WORK/"painter"/"padlock_highpoly_uv.fbx"),use_selection=True,
        object_types={"MESH"},use_mesh_modifiers=False,add_leaf_bones=False,apply_unit_scale=True,
        axis_forward="-Z",axis_up="Y")
    print("PADLOCK_UV_READY",len(parts),"fill",round(area,4),flush=True)


if __name__=="__main__":main()
