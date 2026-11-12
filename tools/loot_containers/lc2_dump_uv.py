"""v02: выгрузка развёртки открытых состояний из RING_Loot_Containers_uv_v01.blend в JSON — для растеризации структурных карт
(строчки, сварные точки, швы) в системном Python.

  blender --background <uv_v01.blend> --python tools/loot_containers/lc2_dump_uv.py -- <выход.json>
Для каждого набора: объекты открытого состояния с именем, числом треугольников, габаритом (м) и полигонами UV (списки пар) +
площадь в м² по 3D, чтобы получить плотность пикс/мм у каждого острова.
"""
import json
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
res = {}
for game in ("lc_safe", "lc_cell", "lc_gun", "lc_file", "lc_cash", "lc_bag", "lc_aid"):
    coll = bpy.data.collections[game]
    items = []
    for ob in coll.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        uvl = me.uv_layers.active
        if uvl is None:
            continue
        polys = []
        for p in me.polygons:
            uv = [list(uvl.data[li].uv) for li in p.loop_indices]
            polys.append({"uv": uv, "area": p.area})
        items.append({"name": ob.name, "n": len(me.polygons), "dim": list(ob.dimensions), "polys": polys,
                      "mats": len(me.materials)})
    res[game] = items
    print(game, len(items))
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(res, f)
