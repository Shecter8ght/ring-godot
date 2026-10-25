"""Repair projected UV folds without changing model geometry."""
import math
import bpy
import numpy as np
from mathutils import Vector
from uv_check import audit


def pack(objects):
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objects:
        ob.data.uv_layers.active=ob.data.uv_layers['BakeUV']
        ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True,shape_method='CONVEX',margin_method='ADD',margin=.003)
    bpy.ops.object.mode_set(mode='OBJECT')


def repair(objects):
    original=audit(objects,details=True)
    current=original
    history=[]
    for attempt in range(10):
        if current['passed']:
            break
        bad=set(current['repair_triangles'])
        offset=0
        n=0
        for ob in objects:
            me=ob.data
            me.calc_loop_triangles()
            uv=me.uv_layers['BakeUV']
            # Match the existing atlas density. Projecting repaired faces in raw
            # metres would let a few damaged islands consume most of a car atlas.
            density=[]
            for tri in me.loop_triangles:
                q=np.array([tuple(uv.data[j].uv) for j in tri.loops])
                p=[ob.matrix_world@me.vertices[v].co for v in tri.vertices]
                world_area=(p[1]-p[0]).cross(p[2]-p[0]).length
                uv_area=abs(float(np.cross(q[1]-q[0],q[2]-q[0])))
                if uv_area>1e-14 and world_area>1e-12:
                    density.append(math.sqrt(uv_area/world_area))
            scale=float(np.median(density)) if density else .1
            for i,t in enumerate(me.loop_triangles):
                if offset+i not in bad:
                    continue
                p=[ob.matrix_world@me.vertices[v].co for v in t.vertices]
                x=(p[1]-p[0]).normalized()
                z=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
                y=z.cross(x)
                coords=np.array([[(v-p[0]).dot(x),(v-p[0]).dot(y)] for v in p])
                # Tiny physical slivers still need a finite bake island.
                coords-=coords.min(axis=0)
                coords*=scale
                size=np.maximum(coords.max(axis=0),1e-10)
                coords*=np.maximum(1,.00002/size)
                coords[:,0]+=2+(n%40)*.2
                coords[:,1]+=2+(n//40)*.2
                for loop,co in zip(t.loops,coords):
                    uv.data[loop].uv=co
                n+=1
            offset+=len(me.loop_triangles)
        pack(objects)
        current=audit(objects,details=True)
        history.append(dict(iteration=attempt+1,separated_triangles=n,remaining=len(current['repair_triangles'])))
    for ob in objects:
        ob.data.uv_layers.active=ob.data.uv_layers['BakeUV']
        ob.data.uv_layers['BakeUV'].active_render=True
    current.pop('repair_triangles',None)
    current['repair_history']=history
    current['initial_overlaps']=original['overlap_pairs']
    current['initial_zero_uv']=original['zero_area_triangles']
    if not current['passed']:
        raise RuntimeError('UV repair failed: '+str(current))
    return current


def thicken_islands(objects,size,pixels=6):
    """Finite texel width for long wire strips; geometry and old UVs stay intact."""
    counts=[]
    for iteration in range(3):
        changed=0
        for ob in objects:
            bm=__import__('bmesh').new(); bm.from_mesh(ob.data)
            bm.faces.ensure_lookup_table()
            layer=bm.loops.layers.uv['BakeUV']
            parents=list(range(len(bm.faces)))
            def find(i):
                while parents[i]!=i:
                    parents[i]=parents[parents[i]]; i=parents[i]
                return i
            for edge in bm.edges:
                if len(edge.link_faces)!=2:continue
                a,b=edge.link_faces
                aa={l.vert.index:tuple(l[layer].uv) for l in a.loops if l.vert in edge.verts}
                bb={l.vert.index:tuple(l[layer].uv) for l in b.loops if l.vert in edge.verts}
                if aa==bb:parents[find(a.index)]=find(b.index)
            groups={}
            for face in bm.faces:groups.setdefault(find(face.index),[]).extend(face.loops)
            for loops in groups.values():
                uv=np.array([tuple(l[layer].uv) for l in loops])
                center=uv.mean(axis=0)
                _,vectors=np.linalg.eigh((uv-center).T@(uv-center))
                local=(uv-center)@vectors
                extent=local.max(axis=0)-local.min(axis=0)
                factors=np.maximum(1,(pixels/size)/np.maximum(extent,1e-10))
                if max(factors)<1.01:continue
                result=(local*factors)@vectors.T+center
                for loop,co in zip(loops,result):loop[layer].uv=co
                changed+=1
            bm.to_mesh(ob.data); bm.free()
        if not changed:break
        pack(objects); counts.append(changed)
    return counts
