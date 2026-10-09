"""Хват для проверки: кисть сдвинута вниз вдоль магазина (к пятке), пальцы заново обхватывают по касанию —
прорези с подавателем выше кисти открыты. Поза левой пишется в JSON (базисы костей) для build_clips.py.
blender --background <файл с хватом>.blend --python check_grip.py -- <json> <выход .blend> [сдвиг, м]"""
import json
import math
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:]
OUT_JSON, OUT_BLEND = args[0], args[1]
SLIDE = float(args[2]) if len(args) > 2 else 0.055
arms = bpy.data.objects["FPS_ArmsRig"]
skin = bpy.data.objects["FPS_Arms"]
for a in (arms,):
    if a.animation_data:
        a.animation_data.action = None
for pb in arms.pose.bones:
    pb.rotation_mode = "XYZ"
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
verts, polys = [], []
for name in ("Magazine_Body", "Magazine_Floorplate"):
    ob = bpy.data.objects[name].evaluated_get(dg)
    me = ob.to_mesh()
    b = len(verts)
    verts += [ob.matrix_world @ v.co for v in me.vertices]
    polys += [[b + i for i in p.vertices] for p in me.polygons]
    ob.to_mesh_clear()
BVH = BVHTree.FromPolygons(verts, polys)
groups = {g.name: g.index for g in skin.vertex_groups}


def verts_of(bones):
    ids = {groups[b] for b in bones if b in groups}
    return [v.index for v in skin.data.vertices if sum(g.weight for g in v.groups if g.group in ids) > 0.4]


def gap(ids):
    bpy.context.view_layer.update()
    d2 = bpy.context.evaluated_depsgraph_get()
    ob = skin.evaluated_get(d2)
    me = ob.to_mesh()
    worst = 1.0
    for i in ids:
        loc, _, _, d = BVH.find_nearest(ob.matrix_world @ me.vertices[i].co, 0.05)
        if loc is not None:
            worst = min(worst, d)
    ob.to_mesh_clear()
    return worst


AW = arms.matrix_world
ik = arms.pose.bones["ik_hand.L"]
axis = Vector((0.0, -0.25, -0.97)).normalized()      # вдоль магазина вниз (он изогнут вперёд)
m = ik.matrix.copy()
m.translation += AW.inverted().to_3x3() @ (axis * SLIDE)
ik.matrix = m
FINGERS = ["f_index", "f_middle", "f_ring", "f_pinky"]
for f in FINGERS:
    for j in (1, 2, 3):
        arms.pose.bones[f"{f}.0{j}.L"].matrix_basis = Matrix.Identity(4)
# ладонь не должна быть в магазине: если касается — отвести наружу (+X, от левой боковины)
palm = verts_of(["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L"])
moved = 0
while gap(palm) < 0.0004 and moved < 15:
    m = ik.matrix.copy()
    m.translation += AW.inverted().to_3x3() @ Vector((0.001, 0, 0))
    ik.matrix = m
    moved += 1
print("CHECKGRIP кисть отведена на", moved, "мм; ладонь, мм", round(gap(palm) * 1000, 2))
LIMITS = [math.radians(90), math.radians(105), math.radians(80)]
for f in FINGERS:
    chain = [f"{f}.01.L", f"{f}.02.L", f"{f}.03.L"]
    for j in range(3):
        pb = arms.pose.bones[chain[j]]
        ids = verts_of(chain[j:])
        if gap(ids) < 0.0006:
            continue
        curled = 0.0
        while curled < LIMITS[j]:
            pb.rotation_euler[0] += math.radians(1.0)
            curled += math.radians(1.0)
            if gap(ids) < 0.0006:
                break
        print("CHECKGRIP", chain[j], round(math.degrees(curled), 1), flush=True)
print("CHECKGRIP большой, мм", round(gap(verts_of(["thumb.01.L", "thumb.02.L", "thumb.03.L"])) * 1000, 2))
names = [pb.name for pb in arms.pose.bones if pb.name.endswith(".L") and not pb.name.endswith("_end")]
pose = {n: [list(r) for r in arms.pose.bones[n].matrix_basis] for n in names}
with open(OUT_JSON, "w", encoding="utf-8") as fh:
    json.dump(pose, fh)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("CHECKGRIP saved", OUT_JSON)
