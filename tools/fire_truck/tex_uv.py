"""Пожарная АЦ: производственная развёртка формы (high-poly) по наборам текстур (tex_sets.SETS).

Порядок:
1. Одинаковые копии одного набора и слота (колёса, петли, крепёж — sand3d копирует сетку) связываются одной сеткой:
   развёртка и текстура у них общие, в атласе место одно.
2. Каждой детали — материал набора `FT_<набор>` (метка формы остаётся в свойстве `ft_mat`, слот отделки — `ft_slot`);
   кузов и верхняя полоса разрезаются на левую и правую половины (`body_L` / `body_R`).
3. Скрытые грани — лучами: в «Целой» и в «Отсеках открытых» отдельно (стёкла и линзы лучам не мешают); грань видна,
   если хоть в одном варианте хоть один луч из полусферы над ней уходит из машины. Скрытым (ниши под облицовкой,
   изнанки листов, верх полосы под настилом) — сторона острова × 0,1 (норма модуля asset_kit.uv).
4. На набор: острова по изломам (Smart UV 60°) → швы по их границам → развёртка с наименьшим растяжением, где вышло
   ровнее проекции → укладка asset_kit.uv.layout (ровная плотность, отступ 12 px на 4K, привязка к пикселю) →
   проверка растром (verify).

blender --background <FireTanker_geometry_v06.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/tex_uv.py -- [out.blend] [набор,набор]
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from asset_kit import uv as kit_uv  # noqa: E402
import tex_sets as T  # noqa: E402

UV = T.UV
ANGLE = 60.0
VIS_MIN_AREA = 0.3          # м² — детали меньше считаются видимыми целиком (лучи не нужны)
VIS_MAX_POLYS = 90000
RAY_LEN = 6.0
CLOSED, OPEN = "Целая", "Отсеки открыты"


def log(*a):
    print(*a, flush=True)


def mesh_objects():
    return [o for o in bpy.data.objects if o.type == "MESH"]


def centre(o):
    me = o.data
    if not me.vertices:
        return o.matrix_world.translation
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    c = co.reshape(-1, 3).mean(0)
    return o.matrix_world @ Vector(c.tolist())


def check_mat(o) -> str:
    for s in o.material_slots:
        if s.material:
            return s.material.name
    return ""


def assign(objs) -> dict:
    """Набор и слот каждой детали (свойства ft_set, ft_slot, ft_mat); кузов и полоса — 'split'."""
    for o in objs:
        st = T.set_of(o.name)
        if st is None:
            c = centre(o)
            st = T.by_place(c.x, c.y, c.z)
        o["ft_set"] = st
        o["ft_mat"] = check_mat(o)
        o["ft_slot"] = T.slot_of(o.name, o["ft_mat"], st) if st != "split" else "paint_red"
    return {}


def link_duplicates(objs) -> int:
    """Одинаковые сетки (в своих осях) одного набора и слота — одной сеткой."""
    groups = defaultdict(list)
    for o in objs:
        if o["ft_set"] == "split":
            continue
        me = o.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        key = (o["ft_set"], o["ft_slot"], len(me.vertices), len(me.polygons),
               hashlib.md5(np.round(co, 4).tobytes()).hexdigest())
        groups[key].append(o)
    n = 0
    for g in groups.values():
        meshes = {o.data for o in g}
        if len(meshes) < 2:
            continue
        keep = g[0].data
        for o in g[1:]:
            if o.data is not keep:
                o.data = keep
                n += 1
    return n


def split_body() -> list:
    """Кузов и верхняя полоса — на левую и правую половины отдельными деталями (материал по стороне)."""
    out = []
    for name in list(T.SPLIT):
        o = bpy.data.objects.get(name)
        if o is None:
            continue
        me = o.data
        mw = o.matrix_world
        left, right = T.SPLIT[name]
        mats = []
        for st in (left, right):
            m = bpy.data.materials.get("FT_" + st) or bpy.data.materials.new("FT_" + st)
            mats.append(m)
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        idx = [0 if T.face_set(name, (mw @ p.center).x) == left else 1 for p in me.polygons]
        me.polygons.foreach_set("material_index", idx)
        me.update()
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
        for p in list(bpy.context.selected_objects):
            pm = p.data
            # после разделения Blender может убрать неиспользуемые слоты — сторону решает сам материал граней
            mi = pm.polygons[0].material_index if len(pm.polygons) else 0
            mname = pm.materials[mi].name if mi < len(pm.materials) and pm.materials[mi] else "FT_" + left
            st = left if mname == "FT_" + left else right
            pm.materials.clear()
            pm.materials.append(mats[0 if st == left else 1])
            pm.polygons.foreach_set("material_index", [0] * len(pm.polygons))
            p.name = f"{name}_{'L' if st == left else 'R'}"
            pm.name = p.name
            p["ft_set"], p["ft_slot"], p["ft_mat"] = st, "paint_red" if name == "body" else "paint_white", ""
            out.append(p)
    return out


EDGE_MAX = 1.0              # м: рёбра длиннее (профиль, лонжерон, полоса — одна грань во всю длину) делятся


def subdivide_long(objs) -> int:
    """Длинные рёбра — на отрезки не длиннее EDGE_MAX (сетка с заполнением): у выдавленных профилей sand3d одна грань
    идёт на 5–7 м, такой остров нельзя разрезать по граням, и укладчик ужимает под него весь набор. Форма та же
    (грани плоские), пометки острых рёбер копируются на части."""
    import bmesh
    n = 0
    done = set()
    for o in objs:
        me = o.data
        if me in done or not len(me.edges):
            continue
        done.add(me)
        sc = max(o.matrix_world.to_scale())
        bm = bmesh.new()
        bm.from_mesh(me)
        groups = {}
        for e in bm.edges:
            if any(len(f.verts) > 4 for f in e.link_faces):
                continue                 # ребро многоугольника (грань с вырезом): сетка с заполнением рвёт его через проём
            k = int(math.ceil(e.calc_length() * sc / EDGE_MAX)) - 1
            if k >= 1:
                groups.setdefault(min(k, 12), []).append(e)
        if groups:
            for k, es in sorted(groups.items(), reverse=True):
                es = [e for e in es if e.is_valid]
                if es:
                    bmesh.ops.subdivide_edges(bm, edges=es, cuts=k, use_grid_fill=True)
                    n += len(es)
            bm.to_mesh(me)
            me.update()
        bm.free()
    return n


def set_materials(objs) -> None:
    for o in objs:
        st = o["ft_set"]
        m = bpy.data.materials.get("FT_" + st) or bpy.data.materials.new("FT_" + st)
        me = o.data
        if len(me.materials) == 1 and me.materials[0] == m:
            continue
        me.materials.clear()
        me.materials.append(m)
        if len(me.polygons):
            me.polygons.foreach_set("material_index", [0] * len(me.polygons))


def _dirs(n: int = 26):
    out = []
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1 - z * z))
        out.append(Vector((math.cos(g * i) * r, math.sin(g * i) * r, z)))
    return out


def _bvh(objs):
    """Одно дерево BVH на все треугольники деталей (в мировых координатах): луч — микросекунды, а не перебор
    тысячи деталей, как у scene.ray_cast."""
    from mathutils.bvhtree import BVHTree
    V, P, base = [], [], 0
    for o in objs:
        me = o.data
        n = len(me.vertices)
        if not n or not len(me.polygons):
            continue
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        M = np.array(o.matrix_world, np.float64)
        co = co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        V.append(co)
        P.append(tri.reshape(-1, 3) + base)
        base += n
    V = np.concatenate(V)
    P = np.concatenate(P)
    return BVHTree.FromPolygons(V.tolist(), P.tolist(), all_triangles=True), len(P)


def visibility(objs) -> dict:
    """Классы граней (kit_uv.VISIBLE / HIDDEN) лучами в обоих вариантах; ключ — сетка (у связанных копий общая:
    грань видна, если видна хоть у одной копии). Стёкла и линзы лучам не мешают."""
    dirs = _dirs()
    cand = []
    for o in objs:
        me = o.data
        if o.get("ft_set") in ("glass", "wheels") or len(me.polygons) > VIS_MAX_POLYS:
            continue
        sc = o.matrix_world.to_scale()
        if sum(p.area for p in me.polygons) * abs(sc.x * sc.y * sc.z) ** (2 / 3) < VIS_MIN_AREA:
            continue
        cand.append(o)
    seen = defaultdict(set)
    t0 = time.time()
    rays = 0
    for var in (CLOSED, OPEN):
        coll = bpy.data.collections[var]
        in_var = [o for o in coll.all_objects if o.type == "MESH" and o.get("ft_set") != "glass"]
        names = {o.name for o in in_var}
        bvh, ntri = _bvh(in_var)
        log(f"  лучи: дерево «{var}» — {ntri:,} треугольников, {time.time() - t0:.0f} с")
        for o in cand:
            if o.name not in names:
                continue
            me = o.data
            mw = o.matrix_world
            nm = mw.to_3x3().inverted().transposed()
            vis = seen[me.name]
            for p in me.polygons:
                if p.index in vis:
                    continue
                n = (nm @ p.normal).normalized()
                c = mw @ p.center + n * 4e-4
                for d in [n] + [d for d in dirs if d.dot(n) > 0.15]:
                    rays += 1
                    if bvh.ray_cast(c, d, RAY_LEN)[0] is None:
                        vis.add(p.index)
                        break
        del bvh
        log(f"  лучи: вариант «{var}» готов, {rays:,} лучей, {time.time() - t0:.0f} с")
    out = {}
    for o in cand:
        me = o.data
        if me.name in out:
            continue
        cls = np.full(len(me.polygons), kit_uv.HIDDEN, np.int32)
        v = list(seen[me.name])
        if v:
            cls[v] = kit_uv.VISIBLE
        out[me.name] = cls
    hid = sum(int((c == kit_uv.HIDDEN).sum()) for c in out.values())
    tot = sum(len(c) for c in out.values())
    log(f"  скрытых граней {hid:,} из {tot:,} у {len(out)} деталей")
    return out


def _uv(me):
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[UV].uv.foreach_get("vector", a)
    return a.reshape(-1, 2).astype(np.float64)


def _set_uv(me, uv):
    me.uv_layers[UV].uv.foreach_set("vector", uv.astype(np.float32).ravel())
    me.update()


def _stretch(m, isl, uv):
    q = uv[m.tri[isl.tris]]
    a2 = 0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1]) - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))
    a3 = m.tri_a3[isl.tris]
    ok = a3 > 1e-12
    if not ok.any():
        return 0.0, 0.0
    w = a3[ok] / a3[ok].sum()
    s = np.sign(np.median(a2[ok])) or 1.0
    flip = float(w[(a2[ok] * s) <= 0].sum())
    r = np.sqrt(np.abs(a2[ok]) / a3[ok])
    med = np.median(r[r > 0]) if (r > 0).any() else 1.0
    bad = float(w[np.abs(np.log(np.maximum(r, 1e-12) / med)) > math.log(1.25)].sum())
    return bad, flip


SPARSE_FILL = 0.45          # остров занимает меньше этой доли своей коробки (рамка вокруг ниш, лист с проёмами) —
SPARSE_LONG = 0.5           # и длиннее 0,5 м — режется на клетки CELL_M: иначе укладчик тратит на коробку пол-атласа
CELL_M = 0.6


def split_sparse(m, isl, uv) -> int:
    """Редкий остров — на клетки CELL_M по его развёртке (в метрах): грани клетки сдвигаются в UV, общие кромки
    соседних клеток получают разные UV — это шов, дальше каждая клетка укладывается своим островом."""
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    a3 = m.tri_a3[isl.tris].sum()
    if a2 <= 1e-14 or a3 <= 1e-9:
        return 0
    k = math.sqrt(a3 / a2)
    p = uv[isl.loops] * k
    lo, hi = p.min(0), p.max(0)
    w, h = hi - lo
    if max(w, h) < SPARSE_LONG or a3 / max(w * h, 1e-12) > SPARSE_FILL:
        return 0
    pos = {int(li): (float(x), float(y)) for li, (x, y) in zip(isl.loops, p)}
    cells = set()
    for pi in isl.polys:
        ls, lt = int(m.ls[pi]), int(m.lt[pi])
        cx = sum(pos[li][0] for li in range(ls, ls + lt)) / lt
        cy = sum(pos[li][1] for li in range(ls, ls + lt)) / lt
        ix, iy = int((cx - lo[0]) / CELL_M), int((cy - lo[1]) / CELL_M)
        cells.add((ix, iy))
        uv[ls:ls + lt, 0] += 3.0 * ix
        uv[ls:ls + lt, 1] += 3.0 * iy
    return len(cells)


LONG_M = 1.5                # лента длиннее (скругления по периметру кузова, лонжероны, профили, тетивы, протектор)
#                             режется поперёк своей оси на куски не длиннее: иначе укладчик ужимает весь набор под неё


def split_long(m, isl, uv) -> int:
    """Длинная лента — на куски не длиннее LONG_M вдоль её главной оси (как у ГРАНЬ-15); куски разнесены в UV."""
    q = uv[m.tri[isl.tris]]
    a2 = np.abs(0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                       - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))).sum()
    a3 = m.tri_a3[isl.tris].sum()
    if a2 <= 1e-14 or a3 <= 1e-12:
        return 0
    p = (uv[isl.loops] - uv[isl.loops].mean(0)) * math.sqrt(a3 / a2)
    if len(p) < 3:
        return 0
    w, v = np.linalg.eigh(np.cov(p.T))
    t_loop = p @ v[:, int(np.argmax(w))]
    span = float(t_loop.max() - t_loop.min())
    nb = int(math.ceil(span / LONG_M))
    if nb <= 1:
        return 0
    pos = {int(li): float(t) for li, t in zip(isl.loops, t_loop)}
    t0 = float(t_loop.min())
    for pi in isl.polys:
        ls, lt = int(m.ls[pi]), int(m.lt[pi])
        tc = sum(pos[li] for li in range(ls, ls + lt)) / lt
        b = min(nb - 1, int((tc - t0) / span * nb))
        uv[ls:ls + lt, 0] += 3.0 * b
        uv[ls:ls + lt, 1] -= 3.0 * b
    return nb


def unwrap(um) -> tuple:
    for o in um:
        me = o.data
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name=UV)
    kit_uv.smart_unwrap(um, uv=UV, angle=math.radians(ANGLE))
    proj = {o.name: _uv(o.data) for o in um}
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.mark_seam(clear=True)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    kept = total = 0
    for o in um:
        m = kit_uv._Mesh(o, UV)
        un = m.uv.copy()
        pj = proj[o.name]
        res = un.copy()
        for isl in kit_uv.islands_of([m]):
            b1, f1 = _stretch(m, isl, un)
            b0, f0 = _stretch(m, isl, pj)
            total += 1
            if f1 > 0.001 or b1 > b0 + 0.02:
                res[isl.loops] = pj[isl.loops]
                kept += 1
        m.uv = res
        for isl in kit_uv.islands_of([m]):
            n = split_sparse(m, isl, res)
            if n > 1:
                log(f"   {o.name}: редкий остров {len(isl.polys)} граней → {n} клеток")
        m.uv = res
        for isl in kit_uv.islands_of([m]):
            n = split_long(m, isl, res)
            if n > 1:
                log(f"   {o.name}: лента {len(isl.polys)} граней → {n} кусков")
        _set_uv(o.data, res)
    return kept, total


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = a[0] if a else T.UV_BLEND
    only = a[1].split(",") if len(a) > 1 else None
    os.makedirs(T.WORK, exist_ok=True)
    t0 = time.time()
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    objs = mesh_objects()
    assign(objs)
    n_link = link_duplicates(objs)
    log(f"связано копий: {n_link}")
    halves = split_body()
    objs = mesh_objects()
    set_materials([o for o in objs if o.get("ft_set") not in (None, "split")])
    log(f"наборы назначены, кузов разрезан: {[o.name for o in halves]}, {time.time() - t0:.0f} с")
    log(f"длинных рёбер поделено: {subdivide_long(objs):,}")
    import fix_ngons                    # деление сеткой рвёт грани с вырезом на многоугольники «через проём»
    log(f"перетриангулировано граней через проём: {fix_ngons.fix(objs, verbose=False)}")
    cls = visibility(objs)
    by_set = defaultdict(list)
    seen = set()
    for o in objs:
        if o.data in seen:
            continue
        seen.add(o.data)
        by_set[o["ft_set"]].append(o)
    report = {}
    for st, (res, title) in T.SETS.items():
        if only and st not in only:
            continue
        um = by_set.get(st, [])
        if not um:
            log(f"SET {st}: деталей нет")
            continue
        t1 = time.time()
        kept, total = unwrap(um)
        classes = [cls.get(o.data.name, np.full(len(o.data.polygons), kit_uv.VISIBLE, np.int32)) for o in um]
        rep = kit_uv.layout(um, res, uv=UV, classes=classes, stack=False, margin=T.PADDING_PX, group_margin=6,
                            log=lambda *x: log("  ", *x))
        ver = kit_uv.verify(um, res, uv=UV, margin=T.PADDING_PX, group_margin=6)
        report[st] = dict(title=title, res=res, meshes=len(um), islands=rep.get("islands"), fill=rep.get("fill"),
                          px_mm=rep.get("px_mm"), projection_kept=f"{kept}/{total}", verify=ver,
                          sec=round(time.time() - t1))
        log("SET", st, json.dumps(report[st], ensure_ascii=False, default=str))
    with open(f"{T.WORK}/uv_report{'_' + '_'.join(only) if only else ''}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, default=str)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    log("SAVED", out, f"{time.time() - t0:.0f} с")


if __name__ == "__main__":
    main()
