"""«Проспект», ограждения и город: помощники игровой версии (Blender) — объекты LOD0, развёртка по наборам, FBX.

Игровые детали собирает функция game() модуля генератора: объект = одна деталь, свойства tex_set (набор текстур
Painter = материал), mat (материал детали — по нему маски Painter: сетки FBX «<набор>__<материал>») и part.
Одинаковые детали вариантов — один блок данных (общая развёртка): у открытого гаража створки — те же сетки, что у
закрытого, повёрнутые; в FBX Painter уходит только первый пользователь блока.
Материалы без Painter: Razor, Barbed, Rebar (плиточные карты проволоки и прутка, wire_textures.py), Glass (прозрачный без карт).
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
import numpy as np

import clib as C

NO_PAINTER = ("Razor", "Barbed", "Rebar", "Glass", "GlassDark", "Lamp")


def set_material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        rgb = {"Razor": (0.7, 0.72, 0.72), "Barbed": (0.5, 0.5, 0.5), "Glass": (0.2, 0.26, 0.27)}.get(name, (0.6, 0.6, 0.58))
        m.diffuse_color = (*rgb, 1.0)
    return m


def part(mb: C.MB, name: str, tex_set: str, mat: str, col, parent=None, sharp: float = 40.0,
         smooth: bool = True, weld: float = 0.0) -> bpy.types.Object:
    """Деталь LOD0 из построителя: один материал (набор), без фасок; гладко с острыми рёбрами круче sharp.
    weld — сварка совпадающих вершин (только для цельной оболочки: у раздельных кусков сварка портит сетку)."""
    for i in range(len(mb.S)):
        mb.S[i] = smooth
    mb.M = ["concrete"] * len(mb.M)
    ob = mb.build(f"{tex_set}__{mat}__{name}", col, parent, bevel=0.0, sharp=sharp, weld=weld)
    ob.data.materials.clear()
    ob.data.materials.append(set_material(tex_set))
    ob["tex_set"], ob["mat"], ob["part"] = tex_set, mat, name
    return ob


def instance(src: bpy.types.Object, col, parent, M=None) -> bpy.types.Object:
    """Та же сетка (общая развёртка) в другом варианте; M — 4×4 (numpy) в координатах варианта."""
    ob = bpy.data.objects.new(src.name.split("__")[0] + "__" + src["mat"] + "__" + src["part"], src.data)
    col.objects.link(ob)
    ob.parent = parent
    if M is not None:
        from mathutils import Matrix
        ob.matrix_basis = Matrix(np.asarray(M).tolist())
    else:
        ob.matrix_basis = src.matrix_basis.copy()
    for k in ("tex_set", "mat", "part"):
        ob[k] = src[k]
    return ob


def triangulate(ob) -> None:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(ob.data)
    bm.free()


UV_FILL_MIN = 0.80            # нормы развёртки (навык godot-asset-preparation, владелец 2026-10-25): заполнение атласа
MARGIN_PX = 12                # отступ между островами, пикселей атласа (игровые модели с мипами и LOD)


def _select(objs) -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object and bpy.context.object.mode != "OBJECT" else None
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def unwrap(objs, size=2048, angle: float = 45.0, margin_px: int = MARGIN_PX) -> dict:
    """Общая развёртка набора по нормам: швы на жёстких рёбрах (умная проекция, порог 45° — фаски не режет),
    ровная плотность (предметы обходят кругом), упаковка островов по осям (прямоугольники остаются прямыми) с
    отступом margin_px пикселей атласа, сдвиг островов к целому пикселю. Возвращает заполнение и плотность.

    size — сторона атласа или (ширина, высота): прямоугольный атлас (2:1) для двух больших сторон плиты — квадрат
    их не вмещает без пустоты. У детали свойство uv: "keep" — развёртка уже задана модулем (полосы гофры, ленты),
    только упаковка; число — свой порог умной проекции (обломки, рваные кромки — крупнее острова)."""
    if not objs:
        return {}
    W, H = (size, size) if isinstance(size, int) else (int(size[0]), int(size[1]))
    groups: dict = {}
    for o in objs:
        groups.setdefault(o.get("uv", angle), []).append(o)
    for key, grp in groups.items():
        if key == "keep":
            continue
        _select(grp)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(float(key)), island_margin=0.0, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    _select(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        density_rules(o)
    start = [_uv_get(o) for o in objs]
    best, best_fill = None, -1.0
    for shape in ("CONCAVE", "CONVEX", "AABB"):              # лучшая из трёх укладок встроенного упаковщика
        for o, a in zip(objs, start):
            _uv_set(o, a)
        _pack(objs, W, H, margin_px, shape)
        fill = uv_stats(objs, (W, H))["fill"]
        if fill > best_fill:
            best, best_fill = [_uv_get(o) for o in objs], fill
    for o, a in zip(objs, start):                            # своя укладка прямоугольников (острова почти все — коробки)
        _uv_set(o, a)
    skyline_pack(objs, W, H, margin_px)
    fill = uv_stats(objs, (W, H))["fill"]
    if fill > best_fill:
        best, best_fill = [_uv_get(o) for o in objs], fill
    for o, a in zip(objs, best):
        _uv_set(o, a)
    for o in objs:
        snap_islands(o, (W, H))
    return uv_stats(objs, (W, H))


def _islands_of(objs) -> list:
    """Острова набора: (объект, индексы петель, рамка в единицах развёртки)."""
    out = []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv.active
        for isl in uv_islands(bm, uv):
            li = [lp.index for f in isl for lp in f.loops]
            pts = np.array([lp[uv].uv[:] for f in isl for lp in f.loops])
            lo, hi = pts.min(0), pts.max(0)
            out.append((o, li, lo, hi))
        bm.free()
    return out


# порядки укладки: длинная сторона, площадь, периметр, высота — у разных наборов лучшим оказывается разный
SKYLINE_ORDERS = (lambda r: -max(r), lambda r: -r[0] * r[1], lambda r: -(r[0] + r[1]), lambda r: -min(r))


def _skyline_fit(rects: list, W: int, H: int, order_key=SKYLINE_ORDERS[0]) -> list | None:
    """Укладка прямоугольников (w, h в пикселях, уже с отступом) по линии горизонта, низ-лево, с поворотом на 90°.
    Возвращает [(x, y, повёрнут)] или None, если не влезло."""
    sky = [[0, 0, W]]                                      # отрезки горизонта: x, высота, ширина
    pos = [None] * len(rects)
    order = sorted(range(len(rects)), key=lambda i: order_key(rects[i]))
    for i in order:
        best = None
        for rot in (False, True):
            w, h = (rects[i][1], rects[i][0]) if rot else rects[i]
            if w > W or h > H:
                continue
            for k in range(len(sky)):
                x = sky[k][0]
                if x + w > W:
                    break
                # высота опоры — максимум горизонта на отрезке [x, x + w)
                y, wl, j = 0, w, k
                while wl > 0 and j < len(sky):
                    y = max(y, sky[j][1])
                    wl -= sky[j][2]
                    j += 1
                if y + h > H:
                    continue
                key = (y + h, x)
                if best is None or key < best[0]:
                    best = (key, x, y, w, h, rot)
        if best is None:
            return None
        _key, x, y, w, h, rot = best
        pos[i] = (x, y, rot)
        # обновить горизонт: отрезок [x, x + w) поднять до y + h
        new = []
        for sx, sy, sw in sky:
            a0, a1 = sx, sx + sw
            if a1 <= x or a0 >= x + w:
                new.append([sx, sy, sw])
                continue
            if a0 < x:
                new.append([a0, sy, x - a0])
            if a1 > x + w:
                new.append([x + w, sy, a1 - (x + w)])
        new.append([x, y + h, w])
        new.sort(key=lambda s: s[0])
        merged = []
        for s in new:
            if merged and merged[-1][1] == s[1] and merged[-1][0] + merged[-1][2] == s[0]:
                merged[-1][2] += s[2]
            else:
                merged.append(s)
        sky = merged
    return pos


def _hull(pts: np.ndarray) -> np.ndarray:
    """Выпуклая оболочка точек (монотонная цепь), против часовой."""
    P = np.unique(np.round(pts, 9), axis=0)
    if len(P) < 3:
        return P

    def half(seq):
        out = []
        for q in seq:
            while len(out) > 1 and np.cross(out[-1] - out[-2], q - out[-2]) <= 0:
                out.pop()
            out.append(q)
        return out
    lo, hi = half(P), half(P[::-1])
    return np.array(lo[:-1] + hi[:-1])


def _straighten(o, li, lo, hi):
    """Косой остров (тонкая полоса кромки ската, наклонный торец) — повернуть к наименьшей рамке: рамка косой полосы
    почти пуста и съедает атлас. Острова, которые и так лежат по осям (стены, листы), не трогаются."""
    a = _uv_get(o).reshape(-1, 2)
    pts = a[li]
    h = _hull(pts)
    if len(h) < 3:
        return o, li, lo, hi
    box = float(np.prod(hi - lo))
    best, best_ang = box, 0.0
    for k in range(len(h)):
        e = h[(k + 1) % len(h)] - h[k]
        ang = math.atan2(e[1], e[0])
        c, s = math.cos(-ang), math.sin(-ang)
        r = h @ np.array([[c, s], [-s, c]])
        area = float(np.prod(r.max(0) - r.min(0)))
        if area < best:
            best, best_ang = area, ang
    if best > 0.8 * box:
        return o, li, lo, hi
    c, s = math.cos(-best_ang), math.sin(-best_ang)
    ctr = (lo + hi) / 2
    pts = (pts - ctr) @ np.array([[c, s], [-s, c]]) + ctr
    a[li] = pts
    _uv_set(o, a.ravel())
    return o, li, pts.min(0), pts.max(0)


def skyline_pack(objs, W: int, H: int, margin_px: int) -> None:
    """Своя укладка островов набора: рамки островов (с отступом margin_px) — по линии горизонта в атлас W × H пикселей,
    масштаб — наибольший, при котором всё влезает (двоичный поиск); угол острова — в целом пикселе."""
    isl = _islands_of(objs)
    if not isl:
        return
    isl = [_straighten(*it) for it in isl]
    size = [hi - lo for _o, _li, lo, hi in isl]
    # половинный отступ (навык: куски одной детали из одного материала, разделённые разрывами, — 6 px вместо 12):
    # у деталей со свойством uv_half рамка острова — с половиной отступа, между двумя такими — 6 px, с прочими — 9
    pads = [margin_px // 2 if o.get("uv_half") else margin_px for o, _li, _lo, _hi in isl]
    fit = None
    for key in SKYLINE_ORDERS:                               # наибольший масштаб из всех порядков укладки
        lo_s, hi_s = (fit[0] if fit else 0.0), 4.0 * max(W, H) / max(max(s) for s in size)
        for _ in range(26):
            s = (lo_s + hi_s) / 2
            rects = [(int(np.ceil(d[0] * s)) + m, int(np.ceil(d[1] * s)) + m) for d, m in zip(size, pads)]
            res = _skyline_fit(rects, W, H, key)
            if res is None:
                hi_s = s
            else:
                lo_s, fit = s, (s, res)
    if fit is None:
        return
    s, res = fit
    by_obj: dict = {}
    for (o, li, lo, hi), (x, y, rot), m in zip(isl, res, pads):
        by_obj.setdefault(o.name, (o, []))[1].append((li, lo, hi, x, y, rot, m))
    for o, items in by_obj.values():
        a = _uv_get(o).reshape(-1, 2)
        for li, lo, hi, x, y, rot, m in items:
            p = (a[li] - lo) * s                                 # пиксели от угла острова
            if rot:
                p = np.c_[(hi[1] - lo[1]) * s - p[:, 1], p[:, 0]]   # поворот на 90°
            p += np.array([x + m / 2, y + m / 2])
            a[li] = p / np.array([W, H])
        _uv_set(o, a.ravel())


def _uv_get(o) -> np.ndarray:
    uv = o.data.uv_layers.active.data
    a = np.empty(len(uv) * 2)
    uv.foreach_get("uv", a)
    return a


def _uv_set(o, a: np.ndarray) -> None:
    o.data.uv_layers.active.data.foreach_set("uv", a)


def _pack(objs, W: int, H: int, margin_px: int, shape: str) -> None:
    _select(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin_method="FRACTION", margin=margin_px / min(W, H), rotate=True,
                            rotate_method="AXIS_ALIGNED", shape_method=shape, scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    if W != H:
        # прямоугольный атлас: острова уже повёрнуты по осям; сжать U под пропорцию и уложить заново без поворота
        for o in objs:
            a = _uv_get(o)
            a[0::2] *= H / W
            _uv_set(o, a)
        _select(objs)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.pack_islands(margin_method="FRACTION", margin=margin_px / min(W, H), rotate=False,
                                shape_method=shape, scale=True)
        bpy.ops.object.mode_set(mode="OBJECT")


# Плотность по видимости (норма навыка): скрытое — малая доля, видимое вскользь — меньше. Правило — (ось, знак,
# порог, множитель): острова, у которых средняя нормаль по оси со знаком больше порога. Общее правило — низ
# (на земле не виден); детали добавляют свои свойством uv_rules (JSON) — у плиты торцы-стыки и верх.
DENSITY_RULES = [["z", -1, 0.7, 0.3]]


def density_rules(ob) -> None:
    import json
    rules = json.loads(ob.get("uv_rules", "[]")) + DENSITY_RULES
    k_obj = float(ob.get("uv_scale", 1.0))              # общий множитель детали (мелочь на земле и т. п.)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    ax = {"x": 0, "y": 1, "z": 2}
    for isl in uv_islands(bm, uv):
        n = sum((f.normal * f.calc_area() for f in isl), start=isl[0].normal * 0.0)
        if n.length < 1e-9:
            continue
        n = n.normalized()
        k = k_obj
        for a, sgn, thr, kr in rules:
            if n[ax[a]] * sgn > thr:
                k *= kr
                break
        if k != 1.0:
            loops = [lp for f in isl for lp in f.loops]
            c = sum((lp[uv].uv for lp in loops), start=loops[0][uv].uv * 0.0) / len(loops)
            for lp in loops:
                lp[uv].uv = c + (lp[uv].uv - c) * k
    bm.to_mesh(ob.data)
    bm.free()


def uv_islands(bm: bmesh.types.BMesh, uv) -> list:
    """Острова развёртки: грани, связанные ребром с непрерывной развёрткой."""
    parent = {f.index: f.index for f in bm.faces}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        same = True
        for v in e.verts:
            a = [lp[uv].uv for lp in f0.loops if lp.vert == v][0]
            b = [lp[uv].uv for lp in f1.loops if lp.vert == v][0]
            if (a - b).length > 1e-6:
                same = False
                break
        if same:
            parent[find(f0.index)] = find(f1.index)
    groups: dict = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return list(groups.values())


def snap_islands(ob, size) -> None:
    """Сдвиг каждого острова так, чтобы его угол лёг на целый пиксель атласа (кромки по рядам пикселей)."""
    W, H = (size, size) if isinstance(size, int) else size
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    if uv is None:
        bm.free()
        return
    for isl in uv_islands(bm, uv):
        loops = [lp for f in isl for lp in f.loops]
        u0 = min(lp[uv].uv.x for lp in loops)
        v0 = min(lp[uv].uv.y for lp in loops)
        du = (round(u0 * W) - u0 * W) / W
        dv = (round(v0 * H) - v0 * H) / H
        for lp in loops:
            lp[uv].uv.x += du
            lp[uv].uv.y += dv
    bm.to_mesh(ob.data)
    bm.free()


def uv_stats(objs, size) -> dict:
    """Заполнение атласа (доля площади UV под островами) и плотность текселей, пикс/м."""
    W, H = (size, size) if isinstance(size, int) else size
    a_uv, a_3d = 0.0, 0.0
    for o in objs:
        me = o.data
        uv = me.uv_layers.active.data
        S = np.array(o.matrix_world.to_3x3())
        for p in me.polygons:
            pts = [uv[li].uv for li in p.loop_indices]
            s = 0.0
            for k in range(len(pts)):
                x0, y0 = pts[k]
                x1, y1 = pts[(k + 1) % len(pts)]
                s += x0 * y1 - x1 * y0
            a_uv += abs(s) * 0.5
            a_3d += p.area * abs(np.linalg.det(S)) ** (2 / 3)
    fill = a_uv
    texel = math.sqrt(W * H * a_uv / a_3d) if a_3d > 0 else 0.0
    return {"fill": round(fill, 3), "px_m": round(texel, 1), "low": fill < UV_FILL_MIN}


def strip_uv(ob, length_period: float, v0: float = 0.0, v1: float = 1.0, strips=None) -> None:
    """Развёртка полос-лент (вершины парами поперёк, полосы подряд; strips — число пар в каждой, по умолчанию одна):
    U — длина вдоль полосы / период плитки, V — поперёк."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    n = len(co) // 2
    mid = (co[0::2] + co[1::2]) / 2
    u_of = np.zeros(n)
    k = 0
    for m in (strips or [n]):                    # полосы подряд: длина считается заново в каждой
        seg = mid[k:k + m]
        u_of[k:k + m] = np.r_[0, np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))] / length_period
        k += m
    u_of = np.repeat(u_of, 2)
    v_of = np.tile([v0, v1], n)
    for li, loop in enumerate(me.loops):
        vi = loop.vertex_index
        uv[li].uv = (u_of[vi], v_of[vi])


def box_unwrap(ob, bias=(1.0, 1.0, 1.0)) -> None:
    """Коробочная проекция в метрах: грань — на плоскость оси, к которой ближе её нормаль (bias — перевес осей X, Y, Z:
    у плиты лицо с откосами рамки и пирамидами уходит целиком на X). Острова — связные грани одной оси; дальше
    только упаковка (свойство uv = "keep")."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    b = np.asarray(bias, float)
    for p in me.polygons:
        n = np.array(p.normal[:])
        k = int(np.argmax(np.abs(n) * b))
        s = 1.0 if n[k] >= 0 else -1.0
        for li in p.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            if k == 0:
                uv[li].uv = (s * y, z)
            elif k == 1:
                uv[li].uv = (-s * x, z)
            else:
                uv[li].uv = (x, s * y)
    ob["uv"] = "keep"


def prism_strip_uv(ob, chunks: list, piece: float = 0.0) -> None:
    """Выпрямленная развёртка выдавленных профилей (C.prism подряд; chunks — число вершин каждой призмы = 2 кольца
    по n точек): боковые грани — одной полосой, U — длина по контуру профиля (гофролист разворачивается в прямоугольник
    вместе с изнанкой), V — длина выдавливания; торцы — плоской проекцией профиля. piece > 0 — длинная полоса режется
    по U на куски не длиннее piece метров (длинный остров иначе упирается в край атласа). Дальше — только упаковка."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    u_of, v_of, ring_of = np.zeros(len(co)), np.zeros(len(co)), np.full(len(co), -1)
    cap_uv, perim = {}, {}
    k = 0
    for c, nv in enumerate(chunks):
        n = nv // 2
        r0, r1 = co[k:k + n], co[k + n:k + 2 * n]
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([r0, r0[:1]]), axis=0), axis=1))]
        h = float(np.linalg.norm(r1[0] - r0[0]))
        ax = (r1[0] - r0[0]) / max(h, 1e-9)
        e1 = r0[1] - r0[0] if n > 1 else np.array([1.0, 0, 0])
        e1 = e1 - ax * (e1 @ ax)
        e1 /= max(np.linalg.norm(e1), 1e-9)
        e2 = np.cross(ax, e1)
        for i in range(n):
            for j, ring in ((k + i, 0), (k + n + i, 1)):
                u_of[j], v_of[j], ring_of[j] = s[i], h * ring, c
                cap_uv[j] = ((co[j] - r0[0]) @ e1, (co[j] - r0[0]) @ e2)
        perim[c] = s[-1]                                   # полный обвод контура (замыкающая грань)
        k += nv
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        if len(idx) > 4 or len(set(ring_of[idx])) > 1:        # торец (n-угольник) — плоская проекция
            for li, i in zip(p.loop_indices, idx):
                uv[li].uv = cap_uv.get(i, (0.0, 0.0))
            continue
        us = [u_of[i] for i in idx]
        c = ring_of[idx[0]]
        wrap = max(us) - min(us) > perim[c] * 0.5          # замыкающая грань контура: ноль — в конец
        for li, i in zip(p.loop_indices, idx):
            uu = u_of[i] + (perim[c] if wrap and u_of[i] < perim[c] * 0.5 else 0.0)
            uv[li].uv = (uu, v_of[i])
    if piece > 0:                                          # разрезать длинные полосы по U на куски
        split_islands_uv(ob, piece)
    ob["uv"] = "keep"


def split_islands_uv(ob, piece: float) -> None:
    """Разрез по U: грани, у которых середина развёртки в куске номер k (по piece), сдвигаются по V на k·1000."""
    me = ob.data
    uv = me.uv_layers.active.data
    for p in me.polygons:
        us = [uv[li].uv[0] for li in p.loop_indices]
        kk = int((sum(us) / len(us)) // piece)
        if kk:
            for li in p.loop_indices:
                uv[li].uv = (uv[li].uv[0], uv[li].uv[1] + 1000.0 * kk)


def grid_uv(ob, chunks: list, cols: list, closed: bool = False) -> None:
    """Развёртка сеток, построенных рядами (C.loft подряд; chunks — вершин в каждой, cols — точек в ряду): U — длина
    вдоль ряда, V — длина поперёк рядов (по средней линии). Скругления, своды, оболочки — одной выпрямленной полосой."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    u_of, v_of = np.zeros(len(co)), np.zeros(len(co))
    k = 0
    for nv, m in zip(chunks, cols):
        rows = nv // m
        g = co[k:k + rows * m].reshape(rows, m, 3)
        su = np.r_[0, np.cumsum(np.linalg.norm(np.diff(g.mean(axis=0), axis=0), axis=1))]
        sv = np.r_[0, np.cumsum(np.linalg.norm(np.diff(g.mean(axis=1), axis=0), axis=1))]
        u_of[k:k + rows * m] = np.tile(su, rows)
        v_of[k:k + rows * m] = np.repeat(sv, m)
        k += nv
    for p in me.polygons:
        for li in p.loop_indices:
            i = me.loops[li].vertex_index
            uv[li].uv = (u_of[i], v_of[i])
    ob["uv"] = "keep"


def split_islands(ob, group_of) -> None:
    """Разрезать острова по группам граней (group_of(центр грани) → номер): кусок с большой дырой (плита с проломом)
    режется на прямоугольники вокруг неё — укладка по рамкам не теряет площадь дыры. Разрез — сдвиг развёртки
    группы далеко за атлас (упаковщик всё равно переложит)."""
    me = ob.data
    uv = me.uv_layers.active.data
    for p in me.polygons:
        g = group_of(np.array(p.center[:]))
        if g:
            for li in p.loop_indices:
                uv[li].uv = (uv[li].uv[0] + 1000.0 * g, uv[li].uv[1])


def tubes_uv(ob, chunks: list, sides: int, period: float) -> None:
    """Развёртка трубок (C.tube подряд; chunks — число вершин каждой): U — длина вдоль оси / период плитки,
    V — по окружности 0…1 (шов — по первой образующей). Для плиточного материала прутка (Rebar)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    u_of = np.zeros(len(co))
    v_of = np.zeros(len(co))
    k = 0
    for n in chunks:
        rings = n // sides
        cen = co[k:k + n].reshape(rings, sides, 3).mean(axis=1)
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))] / period
        u_of[k:k + n] = np.repeat(s, sides)
        v_of[k:k + n] = np.tile(np.arange(sides) / sides, rings)
        k += n
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        vs = [v_of[i] for i in idx]
        wrap = max(vs) - min(vs) > 0.5                     # грань через шов: первые вершины — с V = 1
        for li, i in zip(p.loop_indices, idx):
            vv = v_of[i] + (1.0 if wrap and v_of[i] < 0.5 else 0.0)
            uv[li].uv = (u_of[i], vv)


def unique_by_data(objs):
    seen, out = set(), []
    for o in objs:
        if o.data.name in seen:
            continue
        seen.add(o.data.name)
        out.append(o)
    return out


def merged_copy(objs, name: str, mat_name: str, col) -> bpy.types.Object:
    """Слитая копия деталей в мировых координатах (для FBX Painter): одна сетка «<набор>__<материал>»."""
    bm = bmesh.new()
    for o in objs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()
    me.materials.append(set_material(mat_name))
    for p in me.polygons:
        p.material_index = 0
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def export_fbx(objs, path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE", use_mesh_modifiers=True,
                             axis_forward="-Z", axis_up="Y", object_types={"MESH"}, bake_anim=False)


def tris(ob) -> int:
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)
