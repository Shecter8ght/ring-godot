# «Осока»: пересечения деталей в положениях подвижных узлов (BVH по оценённым сеткам в мире).
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup <файл.blend> --python tools/osoka/check_overlaps.py [-- состояние,…]
# В покое детали намеренно утоплены друг в друга (накладка на трубе, бобышки крышек, хомуты, литьё и спусковая коробка)
# — эти пары печатаются один раз как «стыки». Для каждого положения печатаются только НОВЫЕ пары — задевание при
# движении — и пары стыков, у которых площадь касания выросла больше чем вдвое.
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STATES = {
    "rest": {},
    "caps_half": {"front_cap": 0.3, "rear_cap": 0.3}, "caps_off": {"front_cap": 1.0, "rear_cap": 1.0},
    "detach_half": {"launcher_detach": 0.35}, "detach": {"launcher_detach": 1.0},
    "power_half": {"power_out": 0.4}, "power_out": {"power_out": 1.0},
    "lever_half": {"lever": 0.5}, "lever": {"lever": 1.0},
    "trigger": {"trigger": 1.0}, "button": {"button": 1.0}, "plunger": {"plunger": 1.0},
    "sights_half": {"front_sight": 0.5, "rear_sight": 0.5}, "sights_down": {"front_sight": 0.0, "rear_sight": 0.0},
    "dust_half": {"dust_cover": 0.4}, "dust_open": {"dust_cover": 1.0},
    "fins_in_tube_half": {"fins": 0.0, "missile_out": 0.0},
    # ракету выдвигают при снятых крышках (через надетую она проходит — так и задумано: крышки снимают перед пуском)
    "missile_half_out": {"missile_out": 0.5, "front_cap": 1.0, "rear_cap": 1.0},
    "missile_out_fins": {"missile_out": 1.0, "fins": 1.0, "front_cap": 1.0, "rear_cap": 1.0},
    "fins_half_out": {"missile_out": 1.0, "fins": 0.5, "front_cap": 1.0, "rear_cap": 1.0},
}


def collect():
    dg = bpy.context.evaluated_depsgraph_get()
    objs = []
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get():
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        vs = [oe.matrix_world @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        oe.to_mesh_clear()
        if not vs:
            continue
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        objs.append((o.name, lo, hi, vs, polys))
    return objs


def pairs(objs):
    trees = {}
    out = {}
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
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
                out[tuple(sorted((a[0], b[0])))] = (len(ov), lo, hi)
    return out


def main():
    only = sys.argv[sys.argv.index("--") + 1].split(",") if "--" in sys.argv else None
    ctrl = bpy.data.objects["OSOKA_Controls"]
    base = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    rest = None
    for st, vals in STATES.items():
        if only and st not in only and st != "rest":
            continue
        for k, v in base.items():
            ctrl[k] = v
        for k, v in vals.items():
            ctrl[k] = v
        ctrl.update_tag()
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        pr = pairs(collect())
        if st == "rest":
            rest = pr
            print("STATE rest | стыков:", len(pr))
            for k, (n, lo, hi) in sorted(pr.items()):
                print("   JOINT", "×".join(k), n, lo, "..", hi)
            continue
        new = []
        for k, (n, lo, hi) in sorted(pr.items()):
            if k not in rest:
                new.append(f"{'×'.join(k)}:{n} {lo}..{hi}")
            elif n > 2 * rest[k][0] + 8:
                new.append(f"{'×'.join(k)}: рост {rest[k][0]}→{n} {lo}..{hi}")
        print("STATE", st, "|", "\n   ".join(new) if new else "чисто")
    for k, v in base.items():
        ctrl[k] = v


main()
