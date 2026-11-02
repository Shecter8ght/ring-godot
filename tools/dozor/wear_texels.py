"""Read-only extraction of evaluated PainterUV triangles in each asset root's axes.

The accepted source is not saved. No hand pose or game wear data is invented.
"""
import bpy,json,pathlib
import numpy as np
ROOT=pathlib.Path('E:/Games/RING-godot/_asset_src/dozor/wear')
ROOT.mkdir(parents=True,exist_ok=True)
dg=bpy.context.evaluated_depsgraph_get()
report={}
for key,rootname in [('F1','DOZOR_F1_ROOT'),('P','DOZOR_P_ROOT')]:
    inv=bpy.data.objects[rootname].matrix_world.inverted()
    parts=[];arrays={}
    for ob in sorted(bpy.data.objects,key=lambda o:o.name):
        if ob.type!='MESH' or not ob.name.startswith(key+'.'):continue
        if key=='F1' and not any(s in ob.name for s in ('.Body.','.Head.','.Neck.','.Tail.','.Button.','.Clip.','.Bezel.')):continue
        me=bpy.data.meshes.new_from_object(ob.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
        me.calc_loop_triangles()
        co=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',co)
        co=co.reshape(-1,3);mat=np.asarray(inv@ob.matrix_world)
        co=(co@mat[:3,:3].T+mat[:3,3]).astype(np.float32)
        uv=np.empty(len(me.loops)*2,np.float32);me.uv_layers['PainterUV'].data.foreach_get('uv',uv)
        uv=uv.reshape(-1,2)
        vi=np.empty(len(me.loop_triangles)*3,np.int32);me.loop_triangles.foreach_get('vertices',vi)
        li=np.empty(len(me.loop_triangles)*3,np.int32);me.loop_triangles.foreach_get('loops',li)
        idx=len(parts);parts.append(ob.name)
        arrays[f'p{idx}']=co[vi.reshape(-1,3)]
        arrays[f'u{idx}']=uv[li.reshape(-1,3)]
        bpy.data.meshes.remove(me)
    np.savez_compressed(ROOT/(key+'_triangles.npz'),**arrays)
    report[key]={'parts':parts,'size':4096 if key=='F1' else 2048}
    print(key,len(parts),'parts',sum(len(a) for n,a in arrays.items() if n.startswith('p')),'triangles',flush=True)
(ROOT/'parts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('READ ONLY extraction complete',flush=True)
