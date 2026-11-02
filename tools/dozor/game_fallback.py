"""Closest-surface sampling for narrow LP/HP projection fringes (<=0.5 mm).

Uses the actual accepted HP UV, shading normal and tangent bases. No painted repair,
no borrowing texels from another island. Main surface maps remain the Cycles bake.
"""
import bpy,bmesh,pathlib,sys,json,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
REC=json.loads((WORK/'parts.json').read_text(encoding='utf-8'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));dg=bpy.context.evaluated_depsgraph_get()
names=list(REC['parts'])
with bpy.data.libraries.load(str(WORK/'dozor_lp.blend'),link=False) as (a,b):b.objects=list(names)
low=dict(zip(names,b.objects));sc=bpy.context.scene
for o in b.objects:sc.collection.objects.link(o)
def pixels(path):
    im=bpy.data.images.load(str(path));im.colorspace_settings.name='Non-Color';a=np.empty(im.size[0]*im.size[1]*4,np.float32)
    im.pixels.foreach_get(a);return a.reshape(im.size[1],im.size[0],4)[...,0]
def basis(me,indices,weights,matrix):
    n=sum((me.corner_normals[i].vector*w for i,w in zip(indices,weights)),Vector())
    t=sum((me.loops[i].tangent*w for i,w in zip(indices,weights)),Vector())
    n=(matrix.inverted().transposed()@n).normalized();t=(matrix@t).normalized();t=(t-n*t.dot(n)).normalized()
    sign=me.loops[indices[0]].bitangent_sign
    return np.array([tuple(t),tuple(n.cross(t)*sign),tuple(n)],np.float32)
def bary(point,vs):
    a,b,c=vs;v0=b-a;v1=c-a;v2=point-a
    d00=v0.dot(v0);d01=v0.dot(v1);d11=v1.dot(v1);d20=v2.dot(v0);d21=v2.dot(v1)
    den=max(d00*d11-d01*d01,1e-24);v=(d11*d20-d01*d21)/den;w=(d00*d21-d01*d20)/den
    return [1-v-w,v,w]
report={}
for key in ('F1','P'):
    size=SIZES[key];uvmask=pixels(WORK/('uv_coverage_'+key+'.png'))>.5
    missing=uvmask&(pixels(WORK/('hit_coverage_'+key+'.png'))<.5)
    rows=[];outside={}
    for name,rec in REC['parts'].items():
        if rec['atlas']!=key:continue
        obj=low[name];me=obj.data;me.calc_loop_triangles();me.calc_tangents(uvmap='GameUV');uv=me.uv_layers['GameUV']
        matches=[]
        for tri in me.loop_triangles:
            t=np.array([tuple(uv.data[i].uv) for i in tri.loops])*size-.5
            x0=max(0,int(np.ceil(t[:,0].min())));x1=min(size-1,int(np.floor(t[:,0].max())))
            y0=max(0,int(np.ceil(t[:,1].min())));y1=min(size-1,int(np.floor(t[:,1].max())))
            if x1<x0 or y1<y0:continue
            yy,xx=np.nonzero(missing[y0:y1+1,x0:x1+1]);yy+=y0;xx+=x0
            if not len(xx):continue
            d=(t[1,1]-t[2,1])*(t[0,0]-t[2,0])+(t[2,0]-t[1,0])*(t[0,1]-t[2,1])
            if abs(d)<1e-12:continue
            a=((t[1,1]-t[2,1])*(xx-t[2,0])+(t[2,0]-t[1,0])*(yy-t[2,1]))/d
            b0=((t[2,1]-t[0,1])*(xx-t[2,0])+(t[0,0]-t[2,0])*(yy-t[2,1]))/d
            good=(a>=-1e-6)&(b0>=-1e-6)&(a+b0<=1+1e-6)
            for y,x,aa,bb in zip(yy[good],xx[good],a[good],b0[good]):matches.append((int(y),int(x),tri,[aa,bb,1-aa-bb]))
        if not matches:continue
        sources=[]
        for srcname in rec['sources']:
            src=bpy.data.objects[srcname];hm=bpy.data.meshes.new_from_object(src.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
            bm=bmesh.new();bm.from_mesh(hm)
            changed=False
            if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces));changed=True
            ngons=[f for f in bm.faces if len(f.verts)>4]
            if ngons:bmesh.ops.triangulate(bm,faces=ngons);changed=True
            if changed:bm.to_mesh(hm)
            bm.free();hm.calc_loop_triangles();hm.calc_tangents(uvmap='PainterUV')
            verts=[src.matrix_world@v.co for v in hm.vertices]
            tree=BVHTree.FromPolygons(verts,[list(t.vertices) for t in hm.loop_triangles],all_triangles=True)
            sources.append((tree,hm,verts,src.matrix_world.to_3x3()))
        for y,x,tri,w in matches:
            p=obj.matrix_world@sum((me.vertices[i].co*float(v) for i,v in zip(tri.vertices,w)),Vector())
            found=None
            for tree,hm,verts,matrix in sources:
                point,_,idx,dist=tree.find_nearest(p)
                if point is not None and (found is None or dist<found[0]):found=(dist,point,idx,hm,verts,matrix)
            if found is None:continue
            if found[0]>.0005:
                outside.setdefault(name,[]).append(found[0]*1000);continue
            dist,point,idx,hm,verts,matrix=found;ht=hm.loop_triangles[idx];hw=bary(point,[verts[i] for i in ht.vertices])
            huv=sum((hm.uv_layers['PainterUV'].data[i].uv*float(v) for i,v in zip(ht.loops,hw)),Vector((0,0)))
            rows.append((y,x,tuple(huv),basis(hm,ht.loops,hw,matrix),basis(me,tri.loops,w,obj.matrix_world.to_3x3()),dist))
        for _,hm,_,_ in sources:bpy.data.meshes.remove(hm)
    yy=np.array([r[0] for r in rows],np.int32);xx=np.array([r[1] for r in rows],np.int32)
    np.savez_compressed(WORK/('nearest_'+key+'.npz'),y=size-1-yy,x=xx,
        uv=np.array([r[2] for r in rows],np.float32).reshape(-1,2),
        high_basis=np.array([r[3] for r in rows],np.float32).reshape(-1,3,3),
        low_basis=np.array([r[4] for r in rows],np.float32).reshape(-1,3,3),distance=np.array([r[5] for r in rows],np.float32))
    report[key]={'sampled_pixels':len(rows),'max_distance_mm':max((r[5] for r in rows),default=0)*1000,
                 'outside_half_mm':{k:{'count':len(v),'min_mm':min(v),'max_mm':max(v)} for k,v in outside.items()}}
    print('CLOSEST SOURCE',key,report[key],flush=True)
(WORK/'nearest-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
