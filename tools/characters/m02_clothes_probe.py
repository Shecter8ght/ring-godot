"""Measure the accepted body for original clothing drafts, without changing it."""
import bpy
import json
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('E:/Models Blender/RING_NPC_2026-10-20_v01/M02_Appearance_v05/M02_Appearance_v05.blend')
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
body=bpy.data.objects['M02_Body_Head']
rig=bpy.data.objects['M02_New_Anatomical_Rig']
ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh=ev.to_mesh()
points=[ev.matrix_world @ v.co for v in mesh.vertices]
bvh=BVHTree.FromPolygons(points,[tuple(p.vertices) for p in mesh.polygons])
ev.to_mesh_clear()
result={'bones':{},'torso':{},'arm':{},'leg':{}}
for name in ['upperarm01.L','lowerarm01.L','thigh.L','upperleg01.L','lowerleg01.L','foot.L','toe1-1.L','neck01','spine02','pelvis']:
    if name in rig.data.bones:
        bone=rig.data.bones[name]
        result['bones'][name]={'head':list(rig.matrix_world @ bone.head_local),'tail':list(rig.matrix_world @ bone.tail_local)}
def ys(x,z):
    hits=[]
    for y,direction in [(-1,(0,1,0)),(1,(0,-1,0))]:
        point,*_=bvh.ray_cast(Vector((x,y,z)),Vector(direction))
        hits.append(list(point) if point else None)
    return hits
for z in [0.88,0.93,1.0,1.08,1.16,1.24,1.30,1.35,1.40,1.45,1.48,1.50]:
    result['torso'][str(z)]={str(x):ys(x,z) for x in [0,0.1,0.18,0.21]}
for x in [.22,.28,.34,.40,.44]:
    result['arm'][str(x)]={str(z):ys(x,z) for z in [1.36,1.40,1.44,1.48]}
for z in [.08,.15,.22,.30,.48,.65,.78,.86,.95,1.04]:
    row=[p for p in points if abs(p.z-z)<.004 and p.x>0]
    result['leg'][str(z)]={'bounds':[[min(p[i] for p in row),max(p[i] for p in row)] for i in [0,1]] if row else None,'surfaces':ys(.10,z)}
out=ROOT/'_asset_src/npc_m02/custom_clothes_work'
out.mkdir(parents=True,exist_ok=True)
(out/'measurements.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('M02_CLOTHES_MEASURED '+json.dumps(result['bones']))
