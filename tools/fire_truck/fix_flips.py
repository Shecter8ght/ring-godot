"""Пожарная АЦ: вывернутые треугольники в плоских панелях — развернуть.

На стадии развёртки (перетриангуляция граней с вырезом, fix_ngons.py) в многоугольнике «замочной скважиной»
(панель с дверцей отсека) ухо могло лечь против обхода: треугольник смотрит внутрь, в рендере — чёрный клин на
дверце (левый и правый борт у ниши за дверью экипажа, замечено на проверке износа 2026-11-08). Признак: у
треугольника есть соседи по вершинам в той же плоскости (та же панель), и почти все они смотрят в другую сторону.
Развёртка и карты не меняются — меняется только обход граней.

Второй дефект того же места: грани одной детали лежат друг на друге в одной плоскости (дверца отсека и панель борта
под ней, треугольник-заплатка поверх обеих). В Cycles такая пара затеняет сама себя — чёрный клин и после разворота.
Наложения только ищутся и печатаются (`-- проверка деталь …`); правка (`наложения`) — опыт: вырезание ear clip-ом
и подъём меньшей грани чёрный клин дверцы ниши не убрали (2026-11-08, длинные треугольники захватывают край, общие
вершины тянут соседей) — в файле развёртки он остаётся до пересборки панелей бортов из принятой формы.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/fire_truck/fix_flips.py [-- проверка] [деталь …]
(наложения ищутся только у названных деталей: перебор всей машины — часы)
"""
from __future__ import annotations

import sys

import bmesh
import bpy


def flips(me, plane_mm=1.0):
    """Треугольники, развёрнутые против своей панели. Опора — исходные грани (4 и больше вершин: их перетриангуляция
    не трогала) и уже проверенные треугольники: ориентация расходится от опоры волной по соседям в той же плоскости,
    иначе соседние вывернутые треугольники «голосуют» друг за друга."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    tol = plane_mm / 1000.0
    trusted = {f.index for f in bm.faces if len(f.verts) > 3}
    todo = {f.index for f in bm.faces if len(f.verts) == 3 and f.calc_area() > 1e-7}
    flip = set()

    def normal(i):
        n = bm.faces[i].normal
        return -n if i in flip else n

    changed = True
    while changed and todo:
        changed = False
        for i in list(todo):
            f = bm.faces[i]
            n = f.normal
            c = f.calc_center_median()
            same = opp = 0.0
            for v in f.verts:
                for g in v.link_faces:
                    j = g.index
                    if j == i or j not in trusted:
                        continue
                    gn = normal(j)
                    d = n.dot(gn)
                    if abs(d) < 0.995 or abs((g.calc_center_median() - c).dot(n)) > tol:
                        continue
                    if d > 0:
                        same += g.calc_area()
                    else:
                        opp += g.calc_area()
            if same + opp == 0:
                continue
            if opp > same:
                flip.add(i)
            todo.discard(i)
            trusted.add(i)
            changed = True
    return bm, sorted(flip)


def _samples(tris):
    """Точки проверки грани: центр и середины «центр — угол» каждого её треугольника."""
    out = []
    for a, b, c in tris:
        m = (a + b + c) / 3
        out += [m, (m + a) / 2, (m + b) / 2, (m + c) / 2]
    return out


def overlaps(me, plane_mm=1.0):
    """Копланарные грани, лежащие друг на друге (в Cycles такая пара затеняет сама себя — чёрное пятно).
    Возвращает: delete — грани, целиком накрытые другими; cut — {большая грань: [меньшие поверх неё]}."""
    from mathutils.geometry import intersect_point_tri
    from mathutils.kdtree import KDTree
    me.calc_loop_triangles()
    co = [v.co for v in me.vertices]
    tris = {}
    for t in me.loop_triangles:
        tris.setdefault(t.polygon_index, []).append(tuple(co[i] for i in t.vertices))
    cent = [(pi, (a + b + c) / 3) for pi, ts in tris.items() for a, b, c in ts]
    kd = KDTree(len(cent))
    for k, (pi, c) in enumerate(cent):
        kd.insert(c, k)
    kd.balance()
    tri_of = [(pi, tris[pi][j]) for pi, ts in tris.items() for j in range(len(ts))]
    tol = plane_mm / 1000.0
    delete, cut = set(), {}
    for pi, ts in tris.items():
        p = me.polygons[pi]
        if p.area < 1e-6:
            continue
        n = p.normal
        pts = _samples(ts)
        r = max((q - p.center).length for t in ts for q in t) + 0.01
        cover = {}
        for q in pts:
            for _, k, _d in kd.find_range(q, r):
                qi, tri = tri_of[k]
                if qi == pi:
                    continue
                qn = me.polygons[qi].normal
                if n.dot(qn) < 0.995 or abs((tri[0] - q).dot(n)) > tol:
                    continue
                if intersect_point_tri(q - n * n.dot(q - tri[0]), *tri) is not None:
                    cover.setdefault(qi, set()).add(id(q))
                    break
        if not cover:
            continue
        covered = len(set().union(*cover.values())) / len(pts)
        if covered > 0.9:
            delete.add(pi)
        else:
            for qi in cover:
                if me.polygons[qi].area < p.area:
                    cut.setdefault(pi, set()).add(qi)
    # пара «накрыта целиком» — удалять только одну из взаимно накрывающих: меньшую оставить
    for pi in list(delete):
        for qi in list(delete):
            if qi != pi and qi in delete and pi in delete and abs(me.polygons[qi].area - me.polygons[pi].area) < 1e-9:
                delete.discard(max(pi, qi))
    for pi in delete:
        cut.pop(pi, None)
    return delete, cut


def fix_overlap(me, delete, cut):
    """Накрытые целиком грани — прочь; большая грань под меньшей — на треугольники ear clip, и её треугольники,
    лежащие на меньшей (две и больше из четырёх точек проверки внутри), — прочь."""
    from mathutils.geometry import intersect_point_tri
    me.calc_loop_triangles()
    co = [v.co for v in me.vertices]
    tris = {}
    for t in me.loop_triangles:
        tris.setdefault(t.polygon_index, []).append(tuple(co[i].copy() for i in t.vertices))
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    kill = [bm.faces[i] for i in delete]
    big = [(bm.faces[i], [t for q in qs if q not in delete for t in tris.get(q, [])]) for i, qs in cut.items()
           if i not in delete]
    for f, under in big:
        n = f.normal.copy()
        res = bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="EAR_CLIP")
        for t in res["faces"]:
            pts = _samples([tuple(v.co for v in t.verts)])
            hits = sum(1 for q in pts
                       if any(intersect_point_tri(q - n * n.dot(q - tri[0]), *tri) is not None for tri in under))
            if hits >= 2:
                kill.append(t)
    if kill:
        bmesh.ops.delete(bm, geom=list(set(kill)), context="FACES_ONLY")
    bm.to_mesh(me)
    me.update()
    bm.free()
    return len(set(kill))


def main():
    check = "проверка" in sys.argv
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = {a for a in args if a not in ("проверка", "наложения")}
    total = 0
    done = set()
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        me = o.data
        if me in done:
            continue
        done.add(me)
        bm, bad = flips(me)
        if bad:
            print(f"  {o.name}: вывернуто {len(bad)}", flush=True)
            total += len(bad)
            if not check:
                bmesh.ops.reverse_faces(bm, faces=[bm.faces[i] for i in bad], flip_multires=False)
                bm.to_mesh(me)
                me.update()
        bm.free()
    print("ИТОГО вывернутых", total)
    over = 0
    done = set()
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name in only]:
        me = o.data
        if me in done:
            continue
        done.add(me)
        delete, cut = overlaps(me)
        if delete or cut:
            print(f"  {o.name}: накрытых целиком {len(delete)}, больших под меньшими {len(cut)}", flush=True)
            over += len(delete) + len(cut)
            if not check and "наложения" in args:
                print(f"    удалено треугольников и граней {fix_overlap(me, delete, cut)}", flush=True)
    print("ИТОГО наложений", over)
    total += over
    if not check and total:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
        print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
