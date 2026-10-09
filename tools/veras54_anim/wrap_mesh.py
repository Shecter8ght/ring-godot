"""Обхват магазина по сетке перчатки: проникновение и касание — по вершинам деформированной сетки рук
(вершины пальца — по весам его костей). Сгиб — вокруг локальной X («+» к ладони, как в боевом хвате).
blender --background <хват>.blend --python wrap_mesh.py -- <выход .blend>"""
import math
import sys

import bpy
from mathutils.bvhtree import BVHTree

OUT = sys.argv[sys.argv.index("--") + 1]
CONTACT = 0.0006     # касание: вершина ближе 0.6 мм к поверхности
STEP = math.radians(1.0)
LIMITS = [math.radians(90), math.radians(105), math.radians(80)]
FINGERS = ["f_index", "f_middle", "f_ring", "f_pinky"]

arms = bpy.data.objects["FPS_ArmsRig"]
skin = bpy.data.objects["FPS_Arms"]
print("MESH вершин", len(skin.data.vertices))


def mag_bvh() -> BVHTree:
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for name in ("Magazine_Body", "Magazine_Floorplate"):
        ob = bpy.data.objects[name].evaluated_get(dg)
        me = ob.to_mesh()
        b = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        polys += [[b + i for i in p.vertices] for p in me.polygons]
        ob.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


BVH = mag_bvh()
groups = {g.name: g.index for g in skin.vertex_groups}


def verts_of(bones: list) -> list:
    ids = {groups[b] for b in bones if b in groups}
    out = []
    for v in skin.data.vertices:
        w = sum(g.weight for g in v.groups if g.group in ids)
        if w > 0.4:
            out.append(v.index)
    return out


def gap(ids: list) -> float:
    """Наименьший зазор по вершинам (м); < 0 — вершина внутри магазина."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ob = skin.evaluated_get(dg)
    me = ob.to_mesh()
    mw = ob.matrix_world
    worst = 1.0
    for i in ids:
        p = mw @ me.vertices[i].co
        loc, nrm, _, d = BVH.find_nearest(p, 0.05)
        if loc is None:
            continue
        worst = min(worst, d)
    ob.to_mesh_clear()
    return worst


THUMB = verts_of(["thumb.01.L", "thumb.02.L", "thumb.03.L"])
PALM = verts_of(["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L"])
print("MESH исходно: большой", round(gap(THUMB) * 1000, 1), "мм, ладонь", round(gap(PALM) * 1000, 1), "мм")
for f in FINGERS:
    chain = [f"{f}.01.L", f"{f}.02.L", f"{f}.03.L"]
    for j in range(3):
        pb = arms.pose.bones[chain[j]]
        ids = verts_of(chain[j:])
        curled = 0.0
        if gap(ids) < CONTACT:
            print("MESH", chain[j], "уже касается — без изменений", flush=True)
            continue
        while curled < LIMITS[j]:
            pb.rotation_euler[0] += STEP
            curled += STEP
            if gap(ids) < CONTACT:
                break
        print("MESH", chain[j], "сгиб", round(math.degrees(curled), 1), "зазор", round(gap(ids) * 1000, 2), "мм", flush=True)
print("MESH итог: большой", round(gap(THUMB) * 1000, 1), "мм, ладонь", round(gap(PALM) * 1000, 1), "мм")
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("MESH saved", OUT)
