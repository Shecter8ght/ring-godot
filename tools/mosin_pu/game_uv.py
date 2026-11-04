"""Мосин ПУ, игровая развёртка варианта fp: швы, минимальное растяжение, укладка общим модулем tools/asset_kit/uv.py.

Вызывается из game_lp.py (unwrap); отдельно — переразвернуть готовую игровую сетку без пересборки деталей и лучей:
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_uv.py -- [атлас …]
(читает и перезаписывает _asset_src/mosin_pu_game/fp/lp/Mosin_Game_LP.blend и parts.json: развёртка, uv_layout,
texel_px_mm; классы видимости граней — атрибут lp_class, который пишет game_lp.py).

Швы:
1. острые рёбра (больше 60°) и край — швы (game_lp.mark_sharp);
2. разрезы по детали (CUTS): ложа — поперёк на отрезки (каждый разворачивается «рукавом» вокруг сечения со швом снизу —
   почти прямоугольник; половинки по средней линии ложились хуже: силуэт приклада не складывается), стыки — там,
   где их закрывает металл или они внизу; длинное (ствол, шомпол, накладка) — поперёк на отрезки: остров длиннее
   атласа ужимает весь атлас;
3. дорезка до «дисков» (retopo_lib.auto_seams): дёшево — по скрытому, снизу и по изломам.
Развёртка — «по углам» (ABF; SLIM Blender здесь сплющивал); острова-решётки (тела вращения, полосы) выпрямляются в прямоугольники
(straighten), отрезки ложи — «рукавом» по сечениям (sleeve_unwrap: строка — сечение, u — длина дуги от низа, v — x);
укладка — kit_uv.layout (плотность по видимости и глазу, внахлёст одинакового мелкого, группы разрыва с половинным
отступом, привязка к пикселю, «меньше пустоты под островом»), проверка отступов — kit_uv.verify.
Итог 2026-11-04 (25 802 треугольника): дерево 69 %, сталь 62 %, прицел 67 %, патрон 75 % (было 41 / 37 / 48 / —),
сплющено больше чем вдвое — до 2,1 % площади видимого. «Рукав» ложи давал 72–77 %, но тянул дерево больше чем в 1,3 раза
— у отрезков с вырезами и пазом он отбрасывается проверкой. Ниже нормы 80 %: у стали ~10 % атласа — отступы 12 px
у сотен мелких деталей; крупные плоские куски (щёчки магазинной коробки, скоба, основание кронштейна) и изогнутые
полосы укладка не сводит без ручных швов.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import retopo_lib as RT  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LP_DIR = ROOT / '_asset_src/mosin_pu_game/fp/lp'
log = lambda *a: print('MOSIN_UV', *a, flush=True)

# глаз камеры от первого лица в осях винтовки (дуло +X): от бедра и в прицеле ПУ (как tools/asset_kit/uv_check.py)
EYES = [kit_uv.Eye((-0.48, 0.09, 0.11), name='бедро'), kit_uv.Eye((-0.27, 0.008, 0.0512), kit_uv.ADS_K, 'прицел')]
SHARP = math.radians(60)
# разрезы по деталям игры: halves — левая и правая половины (знак y центра грани); x — поперёк, м (оси винтовки)
CUTS = {
    # ложа: приклад (до шейки), шейка с гнездом коробки, цевьё; поперёк — под хвостовиком (−170), за кольцом коробки
    # (0), у начала накладки (+200) и под задним кольцом цевья (+420)
    'Frame_Wood_Stock': dict(halves=False, x=(-0.255, -0.170, 0.0, 0.200, 0.420)),
    'Frame_Wood_Handguard': dict(halves=False, x=(0.40,)),
    'Frame_Steel': dict(halves=False, x=(0.25, 0.47)),
}
CLASS_ATTR = 'lp_class'          # 0 видимая, 1 просторная скрытая, 2 скрытая (game_lp.py)


def reset_seams(o) -> None:
    """Швы — только острые рёбра и край (повторная развёртка начинается с того же, что game_lp.mark_sharp)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for e in bm.edges:
        e.seam = (not e.is_manifold) or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > SHARP)
    bm.to_mesh(o.data)
    bm.free()


def cut_seams(o) -> int:
    rule = dict(CUTS.get(o.name, {}))
    env = os.environ.get('MOSIN_UV_X_' + o.name.split('.')[0])     # пробы разрезов: MOSIN_UV_X_Frame_Wood_Stock=-0.3,0.1
    if env:
        rule['x'] = tuple(float(v) for v in env.split(','))
    if not rule:
        return 0
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n = 0
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.seam:
            continue
        c1, c2 = (f.calc_center_median() for f in e.link_faces)
        cut = rule.get('halves') and (c1.y > 0) != (c2.y > 0)
        cut = cut or any((c1.x - x) * (c2.x - x) < 0 for x in rule.get('x', ()))
        if cut:
            e.seam = True
            n += 1
    bm.to_mesh(o.data)
    bm.free()
    return n


def stretch(f, uvs) -> tuple:
    """Растяжение грани развёрткой: (масштаб — корень площадей UV / 3D, анизотропия σmax / σmin якобиана). Якобиан —
    по треугольникам веера грани, вырожденные (меньше 5 % площади грани: три вершины почти на одной прямой) не в счёт;
    анизотропия — наибольшая. Площадь одна не видит сплющивания: грань 12 × 73 мм ложилась в 17 × 504 пикселя."""
    vs = [l.vert.co for l in f.loops]
    area = f.calc_area()
    if area < 1e-14:
        return 1.0, 1.0
    a2 = 0.5 * abs(sum(uvs[i][0] * uvs[(i + 1) % len(uvs)][1] - uvs[(i + 1) % len(uvs)][0] * uvs[i][1] for i in range(len(uvs))))
    worst = 1.0
    for k in range(1, len(vs) - 1):
        e1, e2 = vs[k] - vs[0], vs[k + 1] - vs[0]
        nrm = e1.cross(e2)
        if nrm.length * 0.5 < 0.05 * area or e1.length < 1e-12:
            continue
        ax = e1.normalized()
        ay = nrm.normalized().cross(ax)
        P = np.array([[e1.dot(ax), e2.dot(ax)], [e1.dot(ay), e2.dot(ay)]])
        u0 = np.array(uvs[0], float)
        Q = np.column_stack([np.array(uvs[k], float) - u0, np.array(uvs[k + 1], float) - u0])
        try:
            s = np.linalg.svd(Q @ np.linalg.inv(P), compute_uv=False)
        except np.linalg.LinAlgError:
            continue
        worst = max(worst, 99.0 if s[1] < 1e-12 else float(s[0] / s[1]))
    return math.sqrt(max(a2, 0.0) / area), worst


def stretch_report(objs) -> dict:
    """Доля площади граней, сплющенных развёрткой больше чем в 1,5 и 2 раза (видимые грани)."""
    tot = a15 = a20 = 0.0
    for o in objs:
        cls = classes_of(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for f in bm.faces:
            if cls[f.index] != kit_uv.VISIBLE:
                continue
            a = f.calc_area()
            _, an = stretch(f, [l[uvl].uv[:] for l in f.loops])
            tot += a
            a15 += a if an > 1.5 else 0.0
            a20 += a if an > 2.0 else 0.0
        bm.free()
    return {'over_1_5': round(a15 / max(tot, 1e-12), 4), 'over_2': round(a20 / max(tot, 1e-12), 4)}


def island_ok(scales, anisos, max_ratio: float, max_aniso: float, areas=None) -> bool:
    """Остров годится: масштаб по граням расходится не больше max_ratio (5–95 %), сплющивание у 95 % площади — не больше
    max_aniso, у 99,5 % — не больше 2."""
    r = np.array(scales, float)
    an = np.array(anisos, float)
    w = np.ones(len(r)) if areas is None else np.array(areas, float)
    keep = r > 0
    if not keep.any():
        return False
    r, an, w = r[keep], an[keep], w[keep]

    def wq(x, q):
        o = np.argsort(x)
        c = np.cumsum(w[o]) / w.sum()
        return float(x[o][min(len(x) - 1, int(np.searchsorted(c, q)))])
    med = wq(r, 0.5)
    return (wq(r, 0.95) / med <= max_ratio and med / max(wq(r, 0.05), 1e-12) <= max_ratio
            and wq(an, 0.95) <= max_aniso and wq(an, 0.995) <= 2.0)


def straighten(o, max_ratio: float = 1.22) -> tuple:
    """Острова-решётки (только четырёхугольники, сетка без полюсов внутри) — в прямоугольник: столбцы и строки по
    средней длине своих рёбер (как Follow Active Quads с «средней длиной»). Если плотность по граням расходится больше
    max_ratio (конус, сильный изгиб) — остров остаётся как развернул SLIM. Возврат — (выпрямлено, всего островов)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    uvl = bm.loops.layers.uv['GameUV']
    # острова: связь через рёбра без шва
    seen = set()
    islands = []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack, isl = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            isl.append(f)
            for e in f.edges:
                if e.seam or len(e.link_faces) != 2:
                    continue
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        islands.append(isl)
    done = 0
    for isl in islands:
        if len(isl) < 2 or any(len(f.verts) != 4 for f in isl):
            continue
        res = _grid(isl)
        if res is None:
            continue
        corner, cols, rows = res                      # corner[(face, вершина)] = (i, j); длины рёбер по столбцам и строкам
        U = np.concatenate([[0.0], np.cumsum([np.mean(cols[i]) if cols.get(i) else 0.0 for i in range(min(cols), max(cols) + 1)])])
        V = np.concatenate([[0.0], np.cumsum([np.mean(rows[j]) if rows.get(j) else 0.0 for j in range(min(rows), max(rows) + 1)])])
        i0, j0 = min(cols), min(rows)
        # проверка: масштаб по граням и сплющивание (якобиан), не только площадь
        scales, anisos = [], []
        new = {}
        for f in isl:
            pts = []
            for l in f.loops:
                i, j = corner[(f.index, l.vert.index)]
                pts.append((U[i - i0], V[j - j0]))
            sc, an = stretch(f, pts)
            scales.append(sc)
            anisos.append(an)
            new[f.index] = pts
        if not island_ok(scales, anisos, max_ratio, 1.15, [f.calc_area() for f in isl]):
            continue
        for f in isl:
            for l, p in zip(f.loops, new[f.index]):
                l[uvl].uv = p
        done += 1
    bm.to_mesh(o.data)
    bm.free()
    return done, len(islands)


def _grid(isl):
    """Целые координаты углов граней острова-решётки (обход по рёбрам без шва) и длины рёбер по столбцам / строкам.
    Координаты — у углов граней, не у вершин: у трубки, разрезанной одним швом, вершины шва стоят на обоих краях
    полосы. None — не решётка (полюс, закрученная полоса, противоречие)."""
    fset = {f.index for f in isl}
    corner = {}
    f0 = isl[0]
    for l, ij in zip(f0.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        corner[(f0.index, l.vert.index)] = ij
    queue = [f0]
    placed = {f0.index}
    while queue:
        f = queue.pop()
        for e in f.edges:
            if e.seam or len(e.link_faces) != 2:
                continue
            g = e.link_faces[0] if e.link_faces[1] is f else e.link_faces[1]
            if g.index not in fset:
                continue
            a, b = e.verts
            pa, pb = corner[(f.index, a.index)], corner[(f.index, b.index)]
            # внутрь f — от ребра к двум другим углам f; у g — в обратную сторону
            others = [corner[(f.index, v.index)] for v in f.verts if v not in e.verts]
            d = (others[0][0] - pa[0] + others[1][0] - pb[0], others[0][1] - pa[1] + others[1][1] - pb[1])
            step = (-int(np.sign(d[0])), -int(np.sign(d[1])))
            if abs(step[0]) + abs(step[1]) != 1:
                return None
            want = {a.index: pa, b.index: pb}
            for v in g.verts:
                if v.index in want:
                    continue
                nb = [w for w in (x.other_vert(v) for x in v.link_edges if g in x.link_faces) if w.index in (a.index, b.index)]
                if len(nb) != 1:
                    return None
                p = want[nb[0].index]
                want[v.index] = (p[0] + step[0], p[1] + step[1])
            if g.index in placed:
                if any(corner[(g.index, v.index)] != want[v.index] for v in g.verts):
                    return None
                continue
            for v in g.verts:
                corner[(g.index, v.index)] = want[v.index]
            placed.add(g.index)
            queue.append(g)
    if len(placed) != len(isl):
        return None
    cols, rows = {}, {}
    for f in isl:
        for e in f.edges:
            pa, pb = corner[(f.index, e.verts[0].index)], corner[(f.index, e.verts[1].index)]
            if pa[1] == pb[1]:
                cols.setdefault(min(pa[0], pb[0]), []).append(e.calc_length())
            elif pa[0] == pb[0]:
                rows.setdefault(min(pa[1], pb[1]), []).append(e.calc_length())
            else:
                return None
    if not cols or not rows:
        return None
    return corner, cols, rows


SLEEVE = ('Frame_Wood_Stock',)


def bottom_seam(o) -> int:
    """Шов по низу посередине (грани смотрят вниз, центры по разные стороны от y = 0): ложа симметрична."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    n = 0
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.seam:
            continue
        f1, f2 = e.link_faces
        if f1.normal.z < -0.3 and f2.normal.z < -0.3 and f1.calc_center_median().y * f2.calc_center_median().y < 0:
            e.seam = True
            n += 1
    bm.to_mesh(o.data)
    bm.free()
    return n


SLEEVE_BIN = 0.003                    # сечения ложи — по x с шагом 3 мм


def sleeve_unwrap(o, max_ratio: float = 1.3) -> tuple:
    """Ложа «рукавом»: строка развёртки — сечение x = const, u — длина дуги по выпуклой оболочке сечения от низа
    (посередине — 0), v — x. Сечения поперёк оси разворачиваются по своей длине, а не изгибаются, как у SLIM: отрезок
    ложи между разрезами — почти прямоугольник. Остров с растяжением по граням больше max_ratio (вогнутый паз под
    пальцы: оболочка его не повторяет) остаётся от SLIM. (Длина дуги по вершинам самого сечения острова пробовалась —
    у обрезанных швами и вырезами рядов выходит хуже: 8 островов из 49 против 35.)"""
    from mathutils.geometry import convex_hull_2d
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    uvl = bm.loops.layers.uv['GameUV']
    TWO = 2 * math.pi
    co = np.array([v.co[:] for v in bm.verts])
    keys = np.round(co[:, 0] / SLEEVE_BIN).astype(int)
    prof = {}
    for k in np.unique(keys):
        pts = co[keys == k][:, 1:]
        if len(pts) < 3:
            continue
        c = pts.mean(0)
        hull = pts[convex_hull_2d([tuple(p) for p in pts])]
        phi = np.mod(np.arctan2(hull[:, 1] - c[1], hull[:, 0] - c[0]) + math.pi / 2, TWO)   # от низа (−90°)
        order = np.argsort(phi)
        h = hull[order]
        seg = np.linalg.norm(np.diff(np.vstack([h, h[:1]]), axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg[:-1])])
        P = float(seg.sum())
        ph = phi[order]
        prof[k] = (c, np.concatenate([ph - TWO, ph, ph + TWO]), np.concatenate([s - P, s, s + P]), P)
    ks = np.array(sorted(prof))

    def u_of(p, ref=None):
        k = int(ks[np.argmin(np.abs(ks - int(round(p[0] / SLEEVE_BIN))))])
        c, ph, s, P = prof[k]
        f = (math.atan2(p[2] - c[1], p[1] - c[0]) + math.pi / 2) % TWO
        if ref is not None:
            while f - ref > math.pi:
                f -= TWO
            while ref - f > math.pi:
                f += TWO
        w = math.floor(f / TWO)
        return float(np.interp(f - w * TWO, ph, s)) + w * P - P / 2, f
    seen, islands = set(), []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        st, isl = [f0], []
        seen.add(f0.index)
        while st:
            f = st.pop()
            isl.append(f)
            for e in f.edges:
                if e.seam or len(e.link_faces) != 2:
                    continue
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        st.append(g)
        islands.append(isl)
    done = 0
    for isl in islands:
        # ветвь угла — по центру острова: острова не переходят шов по низу
        cen = np.mean([f.calc_center_median()[:] for f in isl], axis=0)
        _, ref = u_of(cen)
        new, scales, anisos = {}, [], []
        for f in isl:
            _, fref = u_of(f.calc_center_median()[:], ref)
            pts = [(u_of(l.vert.co[:], fref)[0], l.vert.co.x) for l in f.loops]
            sc, an = stretch(f, pts)
            scales.append(sc)
            anisos.append(an)
            new[f.index] = pts
        if not island_ok(scales, anisos, max_ratio, 1.3, [f.calc_area() for f in isl]):
            continue
        # свой сдвиг у каждого острова: на разрезе обе стороны дают те же (u, x), и укладка (связь по UV) склеила бы
        # отрезки в один остров
        for f in isl:
            for l, p in zip(f.loops, new[f.index]):
                l[uvl].uv = (p[0] + 3.0 * done, p[1])
        done += 1
    bm.to_mesh(o.data)
    bm.free()
    return done, len(islands)


def classes_of(o) -> np.ndarray:
    me = o.data
    cls = np.full(len(me.polygons), kit_uv.VISIBLE, np.int32)
    if CLASS_ATTR in me.attributes:
        raw = np.zeros(len(me.polygons), np.int32)
        me.attributes[CLASS_ATTR].data.foreach_get('value', raw)
        cls[raw == 1] = kit_uv.ROOMY
        cls[raw == 2] = kit_uv.HIDDEN
    return cls


def unwrap(objs, size: int, eye: bool = True) -> dict:
    classes = []
    for o in objs:
        cls = classes_of(o)
        classes.append(cls)
        hid = set(np.nonzero(cls != kit_uv.VISIBLE)[0].tolist())
        cuts = cut_seams(o)
        if o.name.split('.')[0] in SLEEVE:
            cuts += bottom_seam(o)

        def cost(e, hid=hid):
            f1, f2 = e.link_faces
            n = (f1.normal + f2.normal).normalized()
            k = 0.05 if (f1.index in hid and f2.index in hid) else 0.15 + 0.5 + 0.5 * n.z
            crease = min(1.0, e.calc_face_angle(0.0) / math.radians(45))
            return e.calc_length() * k * (1.0 - 0.6 * crease) + 1e-9
        added = RT.auto_seams(o.data, cost)
        log('seams', o.name, 'cuts', cuts, 'to discs', added)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        if 'GameUV' not in o.data.uv_layers:
            o.data.uv_layers.new(name='GameUV')
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    # «по углам» (ABF): SLIM (MINIMUM_STRETCH) Blender 5.2 на этих сетках ломался — у стебля с гребнем 68 % площади
    # сплющено больше чем вдвое (ABF — 9 %, конформная — 11 %), гребень с клеймом ложился полосой 17 × 504 пикселя
    bpy.ops.uv.unwrap(method=os.environ.get('MOSIN_UV_METHOD', 'ANGLE_BASED'), fill_holes=True, correct_aspect=True,
                      margin=0.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in objs:
        log('straighten', o.name, *straighten(o))
        if o.name.split('.')[0] in SLEEVE:
            log('sleeve', o.name, *sleeve_unwrap(o))
    # «меньше пустоты под островом» — у прицела +2 % к «ниже и левее», у стали и дерева так же
    opts = {'score': 'waste'}
    for kv in os.environ.get('MOSIN_UV_LAYOUT', '').split(','):        # пробы укладки: score=top,order=side
        if '=' in kv:
            k, v = kv.split('=', 1)
            opts[k] = v if k in ('score', 'order') else float(v)
    rep = kit_uv.layout(objs, size, classes=classes, eyes=EYES if eye else [], log=log, **opts)
    kit_uv.harden_on_seams(objs)
    rep['verify'] = kit_uv.verify(objs, size)
    rep['stretch'] = stretch_report(objs)
    log('stretch', rep['stretch'])
    log('verify', rep['verify'])
    return rep


def texel(objs, size) -> tuple:
    a3 = a2 = 0.0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for f in bm.faces:
            a3 += f.calc_area() * 1e6
            uv = [l[uvl].uv for l in f.loops]
            for i in range(1, len(uv) - 1):
                a2 += abs((uv[i].x - uv[0].x) * (uv[i + 1].y - uv[0].y) - (uv[i + 1].x - uv[0].x) * (uv[i].y - uv[0].y)) / 2
        bm.free()
    return round(math.sqrt(a2 * size * size / max(a3, 1e-9)), 2), round(a2, 3)


def main() -> None:
    want = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    rec = json.loads((LP_DIR / 'parts.json').read_text(encoding='utf-8'))
    bpy.context.preferences.use_preferences_save = False
    bpy.ops.wm.open_mainfile(filepath=str(LP_DIR / 'Mosin_Game_LP.blend'))
    # детали — в осях винтовки, как в game_lp (родители-пустышки без поворота): мировые координаты сеток
    for atlas, size in rec['atlas_size'].items():
        if want and atlas not in want:
            continue
        keys = [g for g, v in rec['groups'].items() if rec['uv_atlas'].get(v['atlas'], v['atlas']) == atlas]
        objs = [bpy.data.objects[k] for k in keys]
        moved = {}
        for o in objs:                         # развёртка и лучи глаза — в мировых координатах
            moved[o.name] = (o.parent, o.matrix_parent_inverse.copy(), o.matrix_world.copy())
            o.data.transform(o.matrix_world)
            o.parent = None
            o.matrix_world = o.matrix_world.Identity(4)
        for o in objs:
            reset_seams(o)
        rep = unwrap(objs, size, eye=atlas != 'Ammo')
        for o in objs:                         # назад под узлы
            parent, mpi, mw = moved[o.name]
            o.data.transform(mw.inverted())
            o.parent = parent
            o.matrix_parent_inverse = mpi
            o.matrix_world = mw
        rec.setdefault('uv_layout', {})[atlas] = {k: v for k, v in rep.items() if k not in ('tries', 'eyes')}
        rec['texel_px_mm'][atlas] = texel(objs, size)
        log('atlas', atlas, 'fill', rep['fill'], 'px/mm', rep['px_mm'])
    (LP_DIR / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(LP_DIR / 'Mosin_Game_LP.blend'))
    log('SAVED')


if __name__ == '__main__':
    main()
