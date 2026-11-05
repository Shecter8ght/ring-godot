# ПП по мотивам KRISS Vector: пересечения деталей в положениях управления (BVH по оценённым сеткам в мире).
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/smg03/check_overlaps.py [-- состояние,…]
# Пары — все детали с пересекающимися габаритами (кроме деталей одного узла: патроны друг с другом, головки осей с
# корпусом-хозяином — они намеренно утоплены на 0.4 мм). Печатает пары с пересекающимися гранями и область (мм).
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STATES = {
    "rest": {},
    "bolt_half": {"bolt": 0.5}, "bolt_back": {"bolt": 1.0},
    "ch_swing": {"charging_handle": 0.2}, "ch_back": {"charging_handle": 1.0},
    "trigger": {"trigger": 1.0}, "safe": {"safety": 1.0},
    "sel_2": {"selector": 0.5}, "sel_auto": {"selector": 1.0},
    "mag_release": {"mag_release": 1.0}, "mag_half_out": {"mag_out": 0.3, "mag_release": 1.0},
    "mag30": {"mag30": 1.0},
    "sights_down": {"front_sight": 0.0, "rear_sight": 0.0}, "sights_half": {"front_sight": 0.5, "rear_sight": 0.5},
    "stock_half": {"stock_fold": 0.5, "stock_latch": 1.0}, "stock_folded": {"stock_fold": 1.0},
    "buttons": {"bolt_release": 1.0, "side_buttons": 1.0},
}


def group(name):
    for p in ("Magazine13_round", "Magazine30_round"):
        if name.startswith(p):
            return p
    return name


def main():
    only = sys.argv[sys.argv.index("--") + 1].split(",") if "--" in sys.argv else None
    ctrl = bpy.data.objects["SMG03_Controls"]
    base = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    for st, vals in STATES.items():
        if only and st not in only:
            continue
        for k, v in base.items():
            ctrl[k] = v
        for k, v in vals.items():
            ctrl[k] = v
        ctrl.update_tag()
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        objs = []
        for o in bpy.data.objects:
            if o.type != "MESH":
                continue
            oe = o.evaluated_get(dg)
            if oe.hide_viewport or not o.visible_get():
                continue
            me = oe.to_mesh()
            vs = [oe.matrix_world @ v.co for v in me.vertices]
            polys = [tuple(p.vertices) for p in me.polygons]
            oe.to_mesh_clear()
            if not vs:
                continue
            lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            objs.append((o.name, lo, hi, vs, polys, o.get("owner")))
        trees = {}
        bad = []
        for i in range(len(objs)):
            for j in range(i + 1, len(objs)):
                a, b = objs[i], objs[j]
                if group(a[0]) == group(b[0]):
                    continue
                # детали одного узла (owner — список через запятую) и головки осей с корпусами — намеренно утоплены
                ao, bo = (a[5] or "").split(","), (b[5] or "").split(",")
                if b[0] in ao or a[0] in bo or (set(ao) & set(bo) & {a[0], b[0]}):
                    continue
                if set(ao) & set(bo) - {"", "Receiver", "Receiver", "Receiver"}:
                    continue
                hous = ("Receiver", "Receiver", "Receiver")
                if (a[0].startswith("Pin_") and b[0] in hous) or (b[0].startswith("Pin_") and a[0] in hous):
                    continue
                if any(a[1][k] > b[2][k] or b[1][k] > a[2][k] for k in range(3)):
                    continue
                for o in (a, b):
                    if o[0] not in trees:
                        trees[o[0]] = BVHTree.FromPolygons(o[3], o[4], all_triangles=False, epsilon=0.0)
                ov = trees[a[0]].overlap(trees[b[0]])
                if ov:
                    pts = [a[3][a[4][k][0]] for k, _ in ov]
                    lo = [round(min(p[k] for p in pts) * 1000, 1) for k in range(3)]
                    hi = [round(max(p[k] for p in pts) * 1000, 1) for k in range(3)]
                    bad.append(f"{a[0]}×{b[0]}:{len(ov)} {lo}..{hi}")
        print("STATE", st, "|", "\n   ".join(bad) if bad else "чисто")


main()
