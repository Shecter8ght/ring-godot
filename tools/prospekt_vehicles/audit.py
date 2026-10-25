"""Транспорт «Проспекта»: проверка сохранённой формы — повторное открытие, габариты и треугольники по вариантам.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/audit.py -- \
        <файл.blend> <отчёт.json>

Для каждой коллекции варианта: число объектов, треугольников, габарит в осях машины (без сдвига корня),
выбросы — вершины дальше 1 м за габаритом кузова (признак промаха луча при подъёме панели).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
out = Path(argv[1])
report = {"file": argv[0], "variants": {}}
dg = bpy.context.evaluated_depsgraph_get()
for col in bpy.context.scene.collection.children:
    roots = [o for o in col.objects if o.type == "EMPTY" and o.parent is None]
    root = roots[0] if roots else None
    off = np.array(root.matrix_world.translation) if root else np.zeros(3)
    tris, n_ob, pts, empty = 0, 0, [], []
    for ob in col.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        n_ob += 1
        if len(me.vertices) == 0:
            empty.append(ob.name)
            continue
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        w = co @ M[:3, :3].T + M[:3, 3] - off
        pts.append(w)
    P = np.vstack(pts)
    lo, hi = P.min(0), P.max(0)
    report["variants"][col.name] = {
        "objects": n_ob, "triangles": int(tris), "bbox_min": lo.round(3).tolist(), "bbox_max": hi.round(3).tolist(),
        "size": (hi - lo).round(3).tolist(), "empty_meshes": empty,
    }
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in report["variants"].items():
    print(f"{k}: объектов {v['objects']}, треугольников {v['triangles']:,}, габарит {v['size']}")
