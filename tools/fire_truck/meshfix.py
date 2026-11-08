"""Чистка сеток после булевых sand3d и разбиения панелей генератора: грани нулевой площади, осколки разбиения
на «тройных» рёбрах, рёбра без граней, согласованный обход у панелей кабины."""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

CHAMFER_ANGLE = math.radians(35.0)     # острее — ребро получает фаску; ступени скруглений sand3d мельче
CHAMFER_MAX = 0.0025                   # фаска не шире 2,5 мм
CHAMFER_FRAC = 0.12                    # и не шире доли самого тонкого габарита детали
CHAMFER_FACES = 40000                  # сетки тяжелее не трогать
CHAMFER_SKIP = ("tyre", "tread", "suction_hose", "rim")   # резина и гофра — только пометка острых рёбер; обод
                                                           # (слитые обод и диск фаской не берутся) — зенковка отверстий
SHARP_MARK_ANGLE = math.radians(55.0)  # острее и без пометки — пометить: ступени скруглений и гофры положе


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
            small = min(e.link_faces, key=lambda f: f.calc_area(), default=None)       # треугольник или четырёхугольник
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


def _bad(bm) -> tuple:
    """Сколько рёбер не на двух гранях (кроме края открытой оболочки) и граней нулевой площади."""
    nm = sum(1 for e in bm.edges if len(e.link_faces) > 2 or (len(e.link_faces) == 0))
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    return nm, zero


def chamfer(ob, done: set, verbose: bool = False, failed: list | None = None) -> int:
    """Небольшая скруглённая фаска (2 сегмента) на острых рёбрах детали: свет даёт блик по кромке, как у настоящего
    металла и пластика. Сначала рёбра острее SHARP_MARK_ANGLE без пометки «острое» помечаются (иначе гладкое затенение
    перетекает через угол — градиент по всей грани); фаска — на всех помеченных рёбрах острее CHAMFER_ANGLE. Панели
    генератора (Cab_*) — листы со своими кромками, их не трогать; шины и гофра — только пометка. Если фаска портит сетку
    (третья грань на ребре, нулевые грани), пробуется вдвое и вчетверо уже, потом деталь остаётся без фаски.
    Возвращает число рёбер с фаской."""
    if ob.type != "MESH" or ob.name.startswith("Cab_") or ob.data in done:
        return 0
    done.add(ob.data)
    me = ob.data
    if len(me.polygons) == 0:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    marked = 0
    for e in bm.edges:
        if e.smooth and len(e.link_faces) == 2 and e.calc_face_angle(0.0) > SHARP_MARK_ANGLE:
            e.smooth = False
            marked += 1
    dims = [d / max(s, 1e-9) for d, s in zip(ob.dimensions, ob.scale)]
    dmin = min(d for d in dims if d > 1e-6) if any(d > 1e-6 for d in dims) else 0.0
    w = min(CHAMFER_MAX, CHAMFER_FRAC * dmin)
    skip = (len(me.polygons) > CHAMFER_FACES or w < 0.0003
            or any(ob.name.startswith(n) for n in CHAMFER_SKIP))
    edges = [] if skip else [e for e in bm.edges if not e.smooth and len(e.link_faces) == 2
                             and e.calc_face_angle(0.0) > CHAMFER_ANGLE]
    if not edges:
        if marked:
            bm.to_mesh(me)
            me.update()
        bm.free()
        return 0
    bm.edges.index_update()
    before = _bad(bm)
    ok = False
    for k, wk in enumerate((w, w * 0.5, w * 0.25)):
        work = bm.copy()
        ids = {e.index for e in edges}
        work.edges.ensure_lookup_table()
        sel = [work.edges[j] for j in ids]
        try:
            res = bmesh.ops.bevel(work, geom=sel + list({v for e in sel for v in e.verts}), offset=wk,
                                  offset_type="OFFSET", segments=2, profile=0.5, affect="EDGES", clamp_overlap=True)
            # у сходящихся фасок (узкие клинья) бывают грани нулевой площади — слить их вершины
            zero = [f for f in work.faces if f.calc_area() < 1e-10]
            if zero:
                bmesh.ops.remove_doubles(work, verts=list({v for f in zero for v in f.verts}), dist=1e-5)
                zero = [f for f in work.faces if f.is_valid and f.calc_area() < 1e-10]
                bmesh.ops.dissolve_degenerate(work, dist=1e-6, edges=list({e for f in zero for e in f.edges}))
            after = _bad(work)
            ok = after[0] <= before[0] and after[1] <= before[1]
        except Exception as e:                                     # bmesh отказался — попробовать уже
            ok = False
            if verbose:
                print(f"  {ob.name}: фаска {wk * 1000:.2f} мм не вышла ({e})")
        if ok:
            # затенение: фаска — гладкая полоса, её граница с плоскими гранями — острая; плоские грани остаются
            # плоскими (как harden normals), а по кромке идёт мягкий блик
            bev = {f for f in res["faces"] if f.is_valid}
            for f in bev:
                f.smooth = True
            for f in bev:
                for e in f.edges:
                    e.smooth = all(g in bev for g in e.link_faces)
            work.to_mesh(me)
            work.free()
            break
        work.free()
    if not ok:
        bm.to_mesh(me)                                             # без фаски, но с пометкой острых рёбер
        if failed is not None:
            failed.append(ob.name)
        if verbose:
            print(f"  {ob.name}: фаска испортила бы сетку — оставлено без неё")
    bm.free()
    me.update()
    return len(edges) if ok else 0
