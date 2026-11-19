# ВЕРАС-54 v14: пересечения деталей в собранном .blend во всех позах рига.
#   blender --background <файл.blend> --python tools/veras54_v14/geo/check_overlaps.py -- [--depth 0.25] [--json отчёт.json]
#       [--set ползунок=значение,… (своя поза «custom»)] [--show коллекция,… (включить выключенные)] [поза …]
# Для каждой позы (part_rig.POSES, плюс исходная «rest_pose») и каждой пары деталей с пересекающимися габаритами
# считает вершины одной детали, ушедшие в тело другой глубже depth мм. «Внутри» — по двум признакам сразу: ближайшая
# точка поверхности смотрит нормалью от вершины И луч из вершины пересекает поверхность нечётное число раз
# (одна нормаль ближайшего треугольника ошибается у тонких листов и на вырожденных треугольниках).
# Пары, которым положено сидеть друг в друге (ось в отверстии, ствол во вкладыше, патроны в магазине), — в ALLOW_PREFIX.
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import part_rig  # noqa: E402
except ImportError:      # рига ещё нет — проверяется только исходная поза
    part_rig = None

# пары по началу имён (у перенесённых из v13 деталей имена длинные, с «•»)
ALLOW_PREFIX = [
    # посадки «ось в отверстии» и детали, которым положено сидеть друг в друге (отчёты исполнителей узлов)
    ("Barrel", "Receiver"), ("Barrel", "Muzzle_"), ("Barrel", "Gas_Block"), ("Barrel", "Barrel_Collar"), ("Barrel", "Handguard"),
    ("Gas_Tube", "Gas_Block"), ("Gas_Tube_Pins", "Gas_"), ("Gas_Block_Pins", "Gas_Block"), ("Gas_Block_Pins", "Barrel"),
    ("Front_Sight_Post", "Gas_Block"), ("Muzzle_", "Muzzle_"), ("Bolt carrier • gas piston", "Bolt_Carrier"),
    ("Mag_Catch_Axle", "Trigger_Guard"), ("Mag_Catch_Axle", "Mag_Catch"), ("Hinge_Pin", "Hinge_"), ("Hinge_Pin", "Stock_Knuckle"),
    ("Stock_Screws", "Stock_"), ("Stock_Tube", "Stock_"), ("Sling_Stud", "Stock_Body"), ("Side_Rail_", "Handguard_Upper"),
    ("Handguard_Latch", "Handguard_Upper"), ("Cover_Rear_Block", "Dust_Cover"), ("Side_Rail_Screws", "Side_Rail_"),
    ("Side_Rail_Screws", "Handguard_Upper"), ("Rear_Sight_Axle", "Rear_Sight_"), ("Rear_Sight_Yoke", "Rear_Sight_"),
    ("Rear_Sight_Knob", "Rear_Sight_"), ("Rear_Sight_Button", "Rear_Sight_Slider"),
    ("Hinge_Latch", "Hinge_Spring"),      # защёлка шарнира сжимает свою пружину (пружина приводом не сжимается)
    ("Bolt_Extractor", "Bolt"), ("Magazine • loaded", "Magazine • loaded"),
    # зуб выбрасывателя заходит за казённый срез: выемки под него в стволе (тело вращения) нет, место закрыто вкладышем
    ("Barrel", "Bolt_Extractor"),
    ("Magazine_Follower", "Magazine_Spring"),     # пружина магазина приводом не сжимается
    # цикл перезаряжания: гильза в чашечке затвора и под зубом выбрасывателя, удар об отражатель, патрон в патроннике;
    # вылетающая гильза и досылаемый патрон идут по условным путям — их пересечения с коробкой и крышкой не считаются
    ("Chambered_", "Bolt"), ("Chambered_", "Barrel"), ("Chambered_", "Chambered_"), ("Chambered_", "Ejector"),
    ("Chambered_", "Receiver"), ("Chambered_", "Dust_Cover"), ("Chambered_", "Selector_Lever"),
    ("Magazine • loaded case 1", "Bolt"), ("Magazine • loaded projectile 1", "Barrel"), ("Magazine • loaded case 1", "Barrel"),
    ("Magazine • loaded case 1", "Magazine_Body"), ("Magazine • loaded projectile 1", "Magazine_Body"),
    ("Magazine • loaded case 1", "Receiver"), ("Magazine • loaded projectile 1", "Receiver"),
]


def allowed(a, b):
    for p, q in ALLOW_PREFIX:
        if (a.startswith(p) and b.startswith(q)) or (a.startswith(q) and b.startswith(p)):
            return True
    return False


DIRS = [Vector((0.321, 0.557, 0.766)).normalized(), Vector((-0.613, 0.214, -0.760)).normalized()]
# позы, в которых часть деталей не участвует (поза → начала имён)
SKIP_IN_POSE = {}


def world_data(o, dg):
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    M = ev.matrix_world
    V = np.empty(len(me.vertices) * 3, np.float64); me.vertices.foreach_get("co", V)
    V = V.reshape(-1, 3)
    R = np.array(M.to_3x3()); t = np.array(M.translation)
    W = V @ R.T + t
    me.calc_loop_triangles()
    T = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", T)
    tris = T.reshape(-1, 3)
    ev.to_mesh_clear()
    return W, tris


def make_tree(W, tris):
    a, b, c = W[tris[:, 0]], W[tris[:, 1]], W[tris[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-14
    n[ok] /= ln[ok][:, None]
    tree = BVHTree.FromPolygons([Vector(v) for v in W], [tuple(int(k) for k in t) for t in tris])
    return tree, n, ok


def parity_inside(tree, p):
    """Луч из точки: нечётное число пересечений по обоим направлениям — точка внутри замкнутой оболочки."""
    for d in DIRS:
        cnt = 0; o = Vector(p)
        for _ in range(64):
            hit = tree.ray_cast(o, d)
            if hit[0] is None:
                break
            cnt += 1
            o = hit[0] + d * 2e-6
        if cnt % 2 == 0:
            return False
    return True


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    depth = 0.25; out = None; only = []; custom = None; show = []
    i = 0
    while i < len(argv):
        if argv[i] == "--depth": depth = float(argv[i + 1]); i += 2
        elif argv[i] == "--json": out = argv[i + 1]; i += 2
        elif argv[i] == "--show":
            show = argv[i + 1].split(","); i += 2
        elif argv[i] == "--set":
            custom = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in argv[i + 1].split(",")}; i += 2
        else: only.append(argv[i]); i += 1
    ctrl = bpy.data.objects.get("VERAS54_Controls")
    defaults = {k: d for k, _, d in part_rig.SLIDERS} if (part_rig and ctrl) else {}
    poses = {"rest_pose": {}}
    if defaults:
        poses.update(part_rig.POSES)
    if custom is not None:
        poses["custom"] = custom; only.append("custom")
    vl = bpy.context.view_layer
    # выключенные по умолчанию коллекции проверяются по просьбе
    def walk(lc):
        yield lc
        for c in lc.children:
            yield from walk(c)
    for lc in walk(vl.layer_collection):
        if lc.name in show:
            lc.exclude = False
    vl.update()
    objs = [o for o in vl.objects if o.type == "MESH" and o.visible_get()]
    rows = []
    base = None
    for pose, vals in poses.items():
        if only and pose not in only and pose != "rest_pose":
            continue
        for k, d in defaults.items():
            if k in ctrl:
                ctrl[k] = float(vals.get(k, d))
        if defaults:
            ctrl.update_tag()
        vl.update()
        dg = bpy.context.evaluated_depsgraph_get(); dg.update()
        data = {}
        for o in objs:
            W, tris = world_data(o, dg)
            if len(tris) == 0:
                continue
            data[o.name] = (W, tris, W.min(axis=0), W.max(axis=0))
        names = sorted(n for n in data if not n.startswith(SKIP_IN_POSE.get(pose, ("\0",))))
        trees = {}
        moved = None
        if pose != "rest_pose":
            # в позе проверяются только пары, где хоть одна деталь сдвинулась
            moved = {n for n in names if np.abs(data[n][0] - base[n][0]).max() > 1e-6}
        else:
            base = data
            if only and "rest_pose" not in only:
                continue
        for ia, a in enumerate(names):
            Wa, ta, lo_a, hi_a = data[a]
            for b in names[ia + 1:]:
                if allowed(a, b):
                    continue
                if moved is not None and a not in moved and b not in moved:
                    continue
                Wb, tb, lo_b, hi_b = data[b]
                if np.any(lo_a > hi_b + 1e-4) or np.any(lo_b > hi_a + 1e-4):
                    continue
                worst = 0.0; n_in = 0; at = None
                for (q, Wp, Wq, tq, lo_q, hi_q) in ((b, Wa, Wb, tb, lo_b, hi_b), (a, Wb, Wa, ta, lo_a, hi_a)):
                    sel = np.all((Wp >= lo_q) & (Wp <= hi_q), axis=1)
                    if not sel.any():
                        continue
                    if q not in trees:
                        trees[q] = make_tree(Wq, tq)
                    tree, nrm, ok = trees[q]
                    pts = Wp[sel]
                    if len(pts) > 5000:
                        pts = pts[:: len(pts) // 5000 + 1]
                    for v in pts:
                        loc, _n, idx, dist = tree.find_nearest(Vector(v))
                        if loc is None or dist < depth * 0.001 or not ok[idx]:
                            continue
                        if float((v - np.array(loc)) @ nrm[idx]) >= 0.0:
                            continue
                        if not parity_inside(tree, v):
                            continue
                        n_in += 1
                        if dist > worst:
                            worst = dist; at = v
                if n_in:
                    rows.append({"pose": pose, "a": a, "b": b, "verts": n_in, "depth_mm": round(worst * 1000, 2),
                                 "at_mm": [round(float(x) * 1000, 1) for x in at]})
    rows.sort(key=lambda r: -r["depth_mm"])
    for r in rows:
        print(f"OVERLAP {r['pose']:13s} {r['a']:22s} × {r['b']:22s} глубина {r['depth_mm']:6.2f} мм, вершин {r['verts']:5d}, около {r['at_mm']}")
    print("PAIRS", len(rows))
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)


main()
