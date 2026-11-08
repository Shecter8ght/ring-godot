"""Проверка формы пожарной машины: габариты по коллекциям, сетка каждой детали (открытые и неразделённые
рёбра, вырожденные грани, свободные вершины). Панели кабины генератора (Cab_*) — листы с отбортовкой: открытые
кромки у них задуманы и считаются отдельно.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background <файл.blend> --python tools/fire_truck/audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
REPORT = Path(argv[0]) if argv else None


def world_bbox(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


bad = []
sheets = []
total_tris = 0
summary: dict = {"file": bpy.data.filepath, "collections": {}}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    degen = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    total_tris += sum(len(f.verts) - 2 for f in bm.faces)
    if ob.name.startswith("Cab_") and not (nonman or degen or loose):
        sheets.append(ob.name)
    elif boundary or nonman or degen or loose:
        bad.append((ob.name, boundary, nonman, degen, loose))
    bm.free()

for name in ("Целая", "Отсеки открыты"):
    col = bpy.data.collections.get(name)
    if col is None:
        continue
    objs = list(col.all_objects)
    lo, hi = world_bbox(objs)
    body = [o for o in objs if not o.name.startswith(("mirror", "kerb", "cab_antenna", "antenna"))]
    blo, bhi = world_bbox(body)
    summary["collections"][name] = {"objects": len(objs), "size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
                                    "size_no_mirrors_m": [round(bhi.x - blo.x, 3), round(bhi.y - blo.y, 3), round(bhi.z - blo.z, 3)],
                                    "y": [round(lo.y, 3), round(hi.y, 3)], "z": [round(lo.z, 3), round(hi.z, 3)]}
    print(f"{name}: объектов {len(objs)}; габарит {hi.x - lo.x:.3f} × {hi.y - lo.y:.3f} × {hi.z - lo.z:.3f} м "
          f"(без зеркал и антенн {bhi.x - blo.x:.3f} × {bhi.y - blo.y:.3f} × {bhi.z - blo.z:.3f}); "
          f"Y {lo.y:.2f}…{hi.y:.2f}, Z {lo.z:.3f}…{hi.z:.3f}")
print(f"треугольников в файле: {total_tris:,}")
sc = bpy.context.scene
stray = sorted(o.name for o in sc.objects if all(c == sc.collection for c in o.users_collection))
print(f"деталей вне коллекций вариантов: {len(stray)}" + (f" — {', '.join(stray[:8])}" if stray else ""))
summary["stray_objects"] = stray
print(f"листовых панелей кабины (кромки открыты намеренно): {len(sheets)}")
print(f"деталей с замечаниями: {len(bad)}")
for name, b, n, d, l in sorted(bad, key=lambda r: -(r[1] + r[2] + r[3])):
    print(f"  {name}: открытых рёбер {b}, неразделённых {n}, вырожденных граней {d}, свободных вершин {l}")
summary["triangles"] = total_tris
summary["sheet_panels"] = sheets
summary["parts_with_issues"] = [dict(zip(("name", "boundary", "non_manifold", "degenerate", "loose"), r)) for r in bad]
if REPORT:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("отчёт:", REPORT)
