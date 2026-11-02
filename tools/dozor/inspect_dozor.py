import bpy
import bmesh
from mathutils.geometry import tessellate_polygon
dg=bpy.context.evaluated_depsgraph_get()
for name in ['F1.Bezel.tip_0','F1.Button.dot','F1.Clip.spring_steel','P.Liner.lower','P.Lock.hex_socket_head']:
    ob=bpy.data.objects[name];ev=ob.evaluated_get(dg);me=ev.to_mesh()
    bm=bmesh.new();bm.from_mesh(me)
    areas=[f.calc_area()*1e6 for f in bm.faces]
    zeros=sum(v<=1e-10 for v in areas)
    print(name,'faces',len(areas),'bmesh_zero',zeros,'min_mm2',min(areas),flush=True)
    # Numerically stable tessellation in mm, near the origin.
    stable_zero=0
    for poly in me.polygons:
        pts=[me.vertices[i].co.copy()*1000 for i in poly.vertices]
        center=pts[0].copy();pts=[v-center for v in pts]
        ts=tessellate_polygon([pts])
        ar=0
        for a,b,c in ts:
            if isinstance(a,int):a,b,c=pts[a],pts[b],pts[c]
            ar+=(b-a).cross(c-a).length*.5
        stable_zero+=ar<=1e-10
    print('stable_mm_tessellation_zero',stable_zero,flush=True)
    bm.free();ev.to_mesh_clear()
