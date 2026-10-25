"""«Проспект», ограждения и город: проверка сохранённой формы — повторное открытие, треугольники и габарит
каждого варианта (вычисленная сетка, с фасками), открытые кромки и вырожденные грани по объектам.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/audit.py -- \
        <файл.blend> <отчёт.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
out = Path(argv[1])
report = {"file": argv[0], "variants": {}}
dg = bpy.context.evaluated_depsgraph_get()
for col in bpy.context.scene.collection.children:
    roots = [o for o in col.objects if o.type == "EMPTY" and o.parent is None]
    off = np.array(roots[0].matrix_world.translation) if roots else np.zeros(3)
    tris, pts, objs = 0, [], {}
    for ob in col.objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        tris += nt
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        if len(co):
            pts.append(co @ M[:3, :3].T + M[:3, 3] - off)
        bm = bmesh.new()
        bm.from_mesh(me)
        boundary = sum(1 for e in bm.edges if e.is_boundary)
        nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
        degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
        bm.free()
        ev.to_mesh_clear()
        objs[ob.name] = {"triangles": nt, "boundary_edges": boundary, "nonmanifold_edges": nonman,
                         "degenerate_faces": degenerate, "materials": [m.name for m in ob.data.materials if m]}
    P = np.vstack(pts) if pts else np.zeros((1, 3))
    lo, hi = P.min(0), P.max(0)
    report["variants"][col.name] = {"triangles": int(tris), "bbox_min": lo.round(3).tolist(),
                                    "bbox_max": hi.round(3).tolist(), "size": (hi - lo).round(3).tolist(), "objects": objs}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in report["variants"].items():
    print(f"{k}: треугольников {v['triangles']:,}, габарит {v['size']}, от {v['bbox_min']} до {v['bbox_max']}")
    for name, o in v["objects"].items():
        flag = "" if not (o["nonmanifold_edges"] or o["degenerate_faces"]) else "  <-- неманифолд/вырожд."
        print(f"   {name}: {o['triangles']:,} тр., открытых кромок {o['boundary_edges']}, неманифолд {o['nonmanifold_edges']}, "
              f"вырожд. {o['degenerate_faces']}{flag}")
