"""Чистка сеток после булевых sand3d и разбиения панелей генератора: грани нулевой площади, осколки разбиения
на «тройных» рёбрах, рёбра без граней, согласованный обход у панелей кабины."""
from __future__ import annotations

import bmesh
from mathutils import Vector


def clean(ob, verbose: bool = True) -> None:
    if ob.type != "MESH":
        return
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    changed = False
    zero = [f for f in bm.faces if f.calc_area() < 1e-10]
    if zero:
        # вершины, сошедшиеся в точку (углы проёмов после скругления), — слить только их
        bmesh.ops.remove_doubles(bm, verts=list({v for f in zero for v in f.verts}), dist=1e-5)
        zero = [f for f in bm.faces if f.is_valid and f.calc_area() < 1e-10]
        bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list({e for f in zero for e in f.edges}))
        changed = True
        if verbose:
            left = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
            print(f"  {ob.name}: нулевые грани убраны, осталось {left}")
    # осколки разбиения панелей генератора: треугольник в доли мм² на почти прямом участке контура даёт ребру третью
    # грань — убрать только такие (у принятых машин «Проспекта» они тоже бывают)
    tri3 = set()
    for e in bm.edges:
        if len(e.link_faces) > 2:
            small = min((f for f in e.link_faces if len(f.verts) == 3), key=lambda f: f.calc_area(), default=None)
            if small is not None and small.calc_area() < 2.5e-5:
                tri3.add(small)
    if tri3:
        bmesh.ops.delete(bm, geom=list(tri3), context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if e.is_wire], context="EDGES")
        changed = True
        if verbose:
            print(f"  {ob.name}: осколков разбиения убрано {len(tri3)}")
    if ob.name.startswith("Cab_") and (tri3 or any(not e.is_manifold and not e.is_boundary for e in bm.edges)):
        # после осколков у соседних граней бывает разный обход — выровнять, сохранив сторону «наружу»
        bm.faces.ensure_lookup_table()
        before = sum((f.normal * f.calc_area() for f in bm.faces), Vector())
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.normal_update()
        after = sum((f.normal * f.calc_area() for f in bm.faces), Vector())
        if before.dot(after) < 0:
            bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        changed = True
    if changed:
        bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
