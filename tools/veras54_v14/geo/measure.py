# ВЕРАС-54 v14: замеры и проверка сеток собранного .blend (только чтение).
#   blender --background <файл.blend> --python tools/veras54_v14/geo/measure.py -- [отчёт.json]
# Габариты — по включённым коллекциям в исходной позе (приклад разложен). По каждой детали — треугольники,
# открытые рёбра, рёбра с несогласованным обходом, знак объёма.
import json
import os
import sys

import bpy
import bmesh
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LENGTH = 940.0        # как у v13: затыльник X −235 … дульный срез X 705, приклад разложен
MAG = ("Magazine",)


def bounds(objs, dg):
    lo = np.full(3, 1e9); hi = np.full(3, -1e9)
    for o in objs:
        ev = o.evaluated_get(dg)
        M = np.array(ev.matrix_world)
        bb = np.array([[*c, 1.0] for c in ev.bound_box]) @ M.T
        lo = np.minimum(lo, bb[:, :3].min(axis=0)); hi = np.maximum(hi, bb[:, :3].max(axis=0))
    return lo * 1000, hi * 1000


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else None
    vl = bpy.context.view_layer
    dg = bpy.context.evaluated_depsgraph_get()
    vis = [o for o in vl.objects if o.type == "MESH" and o.visible_get()]
    lo, hi = bounds(vis, dg)
    barrel = [o for o in vis if o.name == "Barrel"]
    blo, bhi = bounds(barrel, dg) if barrel else (lo, hi)
    nomag = [o for o in vis if not o.name.startswith(MAG)]
    nlo, nhi = bounds(nomag, dg)
    rows = [
        ("Длина (затыльник — дульный срез)", hi[0] - lo[0], LENGTH),
        ("Задний торец затыльника, X", lo[0], -235.0),
        ("Дульный срез, X", hi[0], 705.0),
        ("Ствол от казённого среза до дульного среза (с дульным устройством)", hi[0] - blo[0], None),
        ("Ствол (казённый срез X 240 — торец X 606)", bhi[0] - blo[0], 366.0),
        ("Высота с магазином", hi[2] - lo[2], None),
        ("Высота без магазина", nhi[2] - nlo[2], None),
        ("Ширина (с рукояткой затвора)", hi[1] - lo[1], None),
        ("Правый край, Y", lo[1], None),
        ("Левый край, Y", hi[1], None),
    ]
    report = {"file": bpy.data.filepath, "dims": [], "objects": [], "problems": []}
    for name, val, ref in rows:
        dev = None if ref is None else (val - ref) / ref * 100
        report["dims"].append({"name": name, "mm": round(float(val), 1), "ref_mm": ref, "dev_pct": None if dev is None else round(float(dev), 2)})
        print(f"DIM {name}: {val:.1f} мм" + ("" if ref is None else f" (по источнику {ref:g}, отклонение {dev:+.2f} %)"))
    total = 0
    seen = set()
    for o in sorted(vl.objects, key=lambda q: q.name):
        if o.type != "MESH":
            continue
        me = o.data
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        if o.visible_get():
            total += nt
        if me.name in seen:
            continue
        seen.add(me.name)
        bm = bmesh.new(); bm.from_mesh(me)
        open_e = sum(1 for e in bm.edges if len(e.link_faces) < 2)
        multi = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        bad = sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous)
        vol = bm.calc_volume(signed=True) * 1e6
        bm.free()
        report["objects"].append({"name": o.name, "tris": nt, "open_edges": open_e, "multi_edges": multi, "flipped_edges": bad,
                                  "volume_cm3": round(vol, 3), "visible": bool(o.visible_get())})
        if open_e or multi or bad or vol <= 0:
            report["problems"].append(o.name)
            print(f"MESH_PROBLEM {o.name}: открытых {open_e}, тройных {multi}, несогласованных {bad}, объём {vol:.3f} см3")
    report["tris_visible"] = total
    report["objects_total"] = len([o for o in vl.objects if o.type == "MESH"])
    print("TRIS_VISIBLE", total, "OBJECTS", report["objects_total"], "PROBLEMS", len(report["problems"]))
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)


main()
