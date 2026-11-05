# «Осока»: сверка игровой сетки с принятой high-poly и файл для владельца. Открыть игровую сетку, добавить принятую
# форму скрытой коллекцией «Принятая форма (high-poly)» (имена с «_HP», свой риг), по каждой детали — отклонение
# поверхностей в покое: high → игровая (что игровая потеряла) и игровая → high (что выступает); сохранить файл.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <игровая.blend> --python tools/osoka/game_compare.py -- <принятая.blend> <выход.blend>
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

HP_COLL = "Принятая форма (high-poly)"


def world_mesh(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    vs = [oe.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    oe.to_mesh_clear()
    return vs, polys


def bvh_tree(o, dg, max_edge=0.02):
    """Дерево для поиска ближайшей точки: длинные грани (труба — 1.5 м на 6 мм) дробятся по max_edge м — на них
    find_nearest ошибался на 0.7…1.5 мм вдоль грани (сверка v01: «труба мимо» при радиальном совпадении 0.1 мм)."""
    import bmesh
    oe = o.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(oe.to_mesh())
    oe.to_mesh_clear()
    bm.transform(oe.matrix_world)
    for _ in range(8):
        long_ = [e for e in bm.edges if e.calc_length() > max_edge]
        if not long_:
            break
        bmesh.ops.subdivide_edges(bm, edges=long_, cuts=1, use_grid_fill=False)
        bmesh.ops.triangulate(bm, faces=bm.faces)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def dists(src_vs, tree, cap=40000):
    step = max(1, len(src_vs) // cap)
    out = []
    worst = None
    for v in src_vs[::step]:
        hit = tree.find_nearest(v)
        if hit[0] is not None:
            d = hit[3] * 1000.0
            out.append(d)
            if worst is None or d > worst[0]:
                worst = (d, tuple(round(c * 1000.0, 1) for c in v))
    out.sort()
    if not out:
        return 0.0, 0.0, None
    return out[-1], out[int(len(out) * 0.95)], worst[1]


def surface_samples(o, dg, cap=30000):
    """Точки по площади граней (не только вершины): широкая грань, перекрывшая выемку, вершин внутри выемки не имеет —
    замер по вершинам её не видел (щека спуска, сверка v01)."""
    import math
    import random
    rnd = random.Random(7)
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    me.calc_loop_triangles()
    mw = oe.matrix_world
    tris = []
    total = 0.0
    for lt in me.loop_triangles:
        a, b, c = (mw @ me.vertices[i].co for i in lt.vertices)
        ar = (b - a).cross(c - a).length * 0.5
        tris.append((a, b, c, ar))
        total += ar
    oe.to_mesh_clear()
    if total <= 0:
        return []
    per = cap / total
    out = []
    for a, b, c, ar in tris:
        n = per * ar
        k = int(n) + (1 if rnd.random() < n - int(n) else 0)
        for _ in range(k):
            u, w = rnd.random(), rnd.random()
            if u + w > 1.0:
                u, w = 1.0 - u, 1.0 - w
            out.append(a + (b - a) * u + (c - a) * w)
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    hp_path, out_path = argv[0], argv[1]
    lp_names = [o.name for o in bpy.data.objects]
    with bpy.data.libraries.load(hp_path, link=False) as (src, dst):
        names = [str(n) for n in src.objects]
        dst.objects = list(names)          # Blender заменяет содержимое этого списка объектами — имена держим отдельно
    coll = bpy.data.collections.new(HP_COLL)
    bpy.context.scene.collection.children.link(coll)
    pairs = []
    for name, ob in zip(names, dst.objects):
        if ob is None:
            continue
        coll.objects.link(ob)
        ob.name = name + "_HP"
        if ob.type == "MESH" and name in lp_names:
            pairs.append((name, ob.name))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    rows = []
    for lp, hp in pairs:
        a = bpy.data.objects[lp]; b = bpy.data.objects[hp]
        lv, lpoly = world_mesh(a, dg)
        hv, hpoly = world_mesh(b, dg)
        if not lpoly or not hpoly:
            continue
        lt = bvh_tree(a, dg)
        ht = bvh_tree(b, dg)
        h_max, h_95, h_at = dists(hv + surface_samples(b, dg), lt, cap=60000)
        l_max, l_95, l_at = dists(lv + surface_samples(a, dg), ht, cap=60000)
        rows.append((max(h_max, l_max), lp, h_max, h_95, l_max, l_95, h_at if h_max >= l_max else l_at))
    rows.sort(reverse=True)
    for r in rows:
        print(f"DEV | {r[1]} | high→игр max {r[2]:.2f} p95 {r[3]:.2f} | игр→high max {r[4]:.2f} p95 {r[5]:.2f} | где {r[6]}")
    # принятая форма — скрыта (включать в Outliner для сравнения)
    lc = bpy.context.view_layer.layer_collection.children[HP_COLL]
    lc.hide_viewport = True
    coll.hide_render = True
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_path), compress=True)
    print("SAVED", out_path)


main()
