"""Купе Ильи: панель как область на виде (внешний контур и проёмы) → сетка на кузове.

Работает в Python Blender: ограниченное разбиение Делоне — mathutils.geometry.delaunay_2d_cdt.
Порядок: контуры (по осевой зазора) переносятся на кузов, сдвигаются внутрь панели на
полузазор и радиус кромки, внутри ставится равномерная сетка точек вида, всё разбивается
на треугольники и поднимается на поверхность лучами вида. По каждому контуру — завёрнутая
внутрь кромка (как у штампованной панели), у проёмов — стенка вглубь.
"""
from __future__ import annotations

import numpy as np

from surface import Surface, resample, spline2d


class View:
    """Проекция области: uv на виде ↔ точка кузова (лучом вида).

    Плоский вид: uv — координаты на плоскости, луч вдоль направления вида (внутрь машины).
    Цилиндрический: вокруг оси (точка c, направление a); u = угол·r0 от опорного направления e0
    к e1 = a×e0, v — координата вдоль оси; луч из-за кузова к оси. Подходит для панелей,
    которые заворачивают (крыло с борта на верх, бампер с переда на борт, крышка багажника).
    """

    PLANAR = {
        "side": ((0, 1, 0), (0, 0, 1), (-1, 0, 0)),
        "side_r": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
        "top": ((1, 0, 0), (0, 1, 0), (0, 0, -1)),
        "front": ((1, 0, 0), (0, 0, 1), (0, 1, 0)),
        "rear": ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
        "bottom": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    }

    def __init__(self, kind: str, c=(0, 0, 0), a=(0, 0, 1), e0=(0, -1, 0), r0: float = 1.0,
                 u=None, v=None, d=None) -> None:
        self.kind = kind
        self.planar = kind in self.PLANAR or kind == "plane"
        if kind in self.PLANAR:
            u, v, d = (np.array(t, dtype=float) for t in self.PLANAR[kind])
            self.u, self.v, self.d = u, v, d
        elif kind == "plane":
            # свой плоский вид: u, v — оси на плоскости, d — направление луча (внутрь машины)
            self.u = np.array(u, float) / np.linalg.norm(u)
            self.v = np.array(v, float) / np.linalg.norm(v)
            self.d = np.array(d, float) / np.linalg.norm(d)
        else:
            self.c = np.array(c, dtype=float)
            self.a = np.array(a, dtype=float) / np.linalg.norm(a)
            e0 = np.array(e0, dtype=float)
            e0 = e0 - self.a * (e0 @ self.a)
            self.e0 = e0 / np.linalg.norm(e0)
            self.e1 = np.cross(self.a, self.e0)
            self.r0 = r0

    def to_uv(self, P: np.ndarray) -> np.ndarray:
        if self.planar:
            return np.c_[P @ self.u, P @ self.v]
        q = P - self.c
        th = np.arctan2(q @ self.e1, q @ self.e0)
        return np.c_[th * self.r0, q @ self.a]

    def rays(self, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.planar:
            O = uv[:, :1] * self.u + uv[:, 1:2] * self.v - self.d * 3.5
            return O, np.broadcast_to(self.d, O.shape)
        th = uv[:, 0] / self.r0
        out = np.cos(th)[:, None] * self.e0 + np.sin(th)[:, None] * self.e1
        O = self.c + uv[:, 1:2] * self.a + out * 3.0
        return O, -out

    def lift(self, surf: Surface, uv: np.ndarray) -> np.ndarray:
        O, D = self.rays(uv)
        return surf.ray(O, np.ascontiguousarray(D))


def _signed_area(uv: np.ndarray) -> float:
    x, y = uv[:, 0], uv[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _inside(uv_pts: np.ndarray, loops: list[np.ndarray]) -> np.ndarray:
    """Чётно-нечётное правило по всем контурам (внешний и проёмы)."""
    res = np.zeros(len(uv_pts), dtype=bool)
    x, y = uv_pts[:, 0], uv_pts[:, 1]
    for L in loops:
        xa, ya = L[:, 0], L[:, 1]
        xb, yb = np.roll(xa, -1), np.roll(ya, -1)
        for i in range(len(L)):
            cond = (ya[i] > y) != (yb[i] > y)
            xi = xa[i] + (y - ya[i]) * (xb[i] - xa[i]) / (yb[i] - ya[i] + 1e-30)
            res ^= cond & (x < xi)
    return res


def _dist_to_loops(uv_pts: np.ndarray, loops: list[np.ndarray]) -> np.ndarray:
    d = np.full(len(uv_pts), np.inf)
    for L in loops:
        a, b = L, np.roll(L, -1, axis=0)
        ab = b - a
        for i in range(len(L)):
            t = np.clip(((uv_pts - a[i]) @ ab[i]) / max(ab[i] @ ab[i], 1e-12), 0, 1)
            d = np.minimum(d, np.linalg.norm(uv_pts - (a[i] + t[:, None] * ab[i]), axis=1))
    return d


def _seg_cross(a, b, c, d):
    """Пересечение отрезков ab и cd: параметр на ab или None."""
    r, q = b - a, d - c
    den = r[0] * q[1] - r[1] * q[0]
    if abs(den) < 1e-14:
        return None
    w = c - a
    t = (w[0] * q[1] - w[1] * q[0]) / den
    u = (w[0] * r[1] - w[1] * r[0]) / den
    return t if (0 < t < 1 and 0 < u < 1) else None


def untangle(uv: np.ndarray, P: np.ndarray) -> np.ndarray:
    """Убрать самопересечения замкнутого контура: из двух частей петли остаётся длинная."""
    uv, P = uv.copy(), P.copy()
    changed = True
    while changed:
        changed = False
        n = len(uv)
        # Быстрый отбор пар по рамкам отрезков
        a, b = uv, np.roll(uv, -1, axis=0)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        for i in range(n):
            cand = np.where((lo[:, 0] <= hi[i, 0]) & (hi[:, 0] >= lo[i, 0]) &
                            (lo[:, 1] <= hi[i, 1]) & (hi[:, 1] >= lo[i, 1]))[0]
            for j in cand:
                if j <= i + 1 or (i == 0 and j == n - 1):
                    continue
                t = _seg_cross(a[i], b[i], a[j], b[j])
                if t is None:
                    continue
                inner = j - i            # точки i+1..j — петля «внутри»
                X_uv = a[i] + t * (b[i] - a[i])
                X_p = P[i] + t * (P[(i + 1) % n] - P[i])
                if inner <= n - inner:
                    uv = np.vstack([uv[:i + 1], X_uv[None], uv[j + 1:]])
                    P = np.vstack([P[:i + 1], X_p[None], P[j + 1:]])
                else:
                    uv = np.vstack([X_uv[None], uv[i + 1:j + 1]])
                    P = np.vstack([X_p[None], P[i + 1:j + 1]])
                changed = True
                break
            if changed:
                break
    return P


def loop_on_surface(surf: Surface, view: View, design_uv, h: float, inset: float,
                    is_hole: bool, smooth: bool = True) -> np.ndarray:
    """Контур по точкам вида → на кузове, сдвинут на inset внутрь материала панели."""
    d = np.asarray(design_uv, dtype=float)
    if d.shape[1] == 3:
        # Контур уже на кузове (из швов): плотно по длине, uv — по виду разбиения
        P = resample(np.vstack([d, d[:1]]), 1201)[:-1]
        uv = view.to_uv(P)
    else:
        uv = spline2d(d, 901, closed=True)[:-1] if smooth else resample(np.vstack([d, d[:1]]), 901)[:-1]
        P = view.lift(surf, uv)
    # Направление «в материал» на виде: внешний контур — внутрь области, проём — наружу из проёма
    area = _signed_area(uv)
    t = np.roll(uv, -1, axis=0) - np.roll(uv, 1, axis=0)
    left = np.c_[-t[:, 1], t[:, 0]]
    left /= np.maximum(np.linalg.norm(left, axis=1, keepdims=True), 1e-12)
    into = left if area > 0 else -left          # внутрь области контура
    if is_hole:
        into = -into
    eps = 0.004
    P2 = view.lift(surf, uv + into * eps)
    T = P2 - P
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Pi = surf.project(P + T * inset)
    # Острые углы при отступе дают петли — отрезать их (на виде разбиения)
    Pi = untangle(view.to_uv(Pi), Pi)
    # Равномерно по длине в пространстве, шаг ~0.7 h
    closed = np.vstack([Pi, Pi[:1]])
    length = float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))
    n = max(12, int(length / (0.7 * h)))
    return resample(closed, n + 1)[:-1]


def fit_smooth(view: View, V: np.ndarray, deg: int) -> tuple[np.ndarray, float]:
    """Точки → гладкая поверхность: расстояние вдоль луча вида как многочлен степени deg от uv.

    Стекло гнут по простой поверхности; поле кузова несёт мелкие волны профиля с чертежа и места
    сопряжений — на стекле в отражении это видно как искажения. Возвращает точки и наибольший сдвиг.
    """
    uv = view.to_uv(V)
    O, D = view.rays(uv)
    D = np.broadcast_to(D, V.shape)
    t = ((V - O) * D).sum(1)
    c = uv.mean(0)
    sc = np.maximum(np.ptp(uv, axis=0) / 2, 1e-6)
    q = (uv - c) / sc
    A = np.stack([q[:, 0] ** i * q[:, 1] ** j for i in range(deg + 1) for j in range(deg + 1 - i)], 1)
    coef, *_ = np.linalg.lstsq(A, t, rcond=None)
    tf = A @ coef
    return O + tf[:, None] * D, float(np.abs(tf - t).max())


def despike(surf: Surface, V: np.ndarray, tris: np.ndarray, first: int, limit: float) -> tuple[np.ndarray, int]:
    """Внутренние точки, которые луч вида поднял не на тот лист поверхности, — на кузов по соседям.

    Пример: у основания заднего стекла поле в месте обреза кабины образует узкую щель с «плавником»;
    лучи одного ряда крышки багажника цеплялись за него, и ряд вставал на 2 см выше — складка,
    «зубцы» в отражениях. Точка дальше limit от среднего соседей — выброс: ставим её в среднее
    надёжных соседей (между соседними рядами; на само поле не проецируем — там та же щель).
    Контуры (индексы < first) не трогаем. Включается для панели явно: на бамперах и фарах
    резкие ступени поля законны.
    """
    n = len(V)
    if n <= first or not len(tris):
        return V, 0
    V = V.copy()
    e = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.vstack([e, e[:, ::-1]])
    flagged = np.zeros(n, dtype=bool)
    for _ in range(4):
        w = (~flagged[e[:, 1]]).astype(float)
        acc = np.zeros((n, 3))
        cnt = np.zeros(n)
        np.add.at(acc, e[:, 0], V[e[:, 1]] * w[:, None])
        np.add.at(cnt, e[:, 0], w)
        mean = acc / np.maximum(cnt, 1)[:, None]
        dev = np.linalg.norm(V - mean, axis=1)
        bad = (np.arange(n) >= first) & (cnt > 0) & (dev > limit)
        if not bad.any():
            break
        V[bad] = mean[bad]
        flagged |= bad
    return V, int(flagged.sum())


def domain_panel(surf: Surface, view: View, outer, holes=(), h: float = 0.012, gap: float = 0.0045,
                 roll_r: float = 0.003, flange: float = 0.012, roll_steps: int = 3,
                 hole_depth: float | None = None, smooth: bool = True, fit_deg: int | None = None,
                 fit_blend: float = 0.0, despike_limit: float | None = None):
    """Панель: (вершины, грани). hole_depth — глубина стенки проёма (по умолчанию как отбортовка).

    despike_limit — убрать выбросы луча дальше этого расстояния от соседей (см. despike).

    fit_deg — для стёкол: поверхность панели подгоняется многочленом этой степени (см. fit_smooth).
    """
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt

    inset = gap / 2 + roll_r
    loops3 = [loop_on_surface(surf, view, outer, h, inset, False, smooth)]
    for hl in holes:
        loops3.append(loop_on_surface(surf, view, hl, h, inset, True, smooth))
    loops_uv = [view.to_uv(L) for L in loops3]
    # Внутренние точки — шахматная сетка вида, не ближе 0.6 h к контурам
    allb = np.vstack(loops_uv)
    lo, hi = allb.min(0), allb.max(0)
    gx = np.arange(lo[0], hi[0], h)
    gy = np.arange(lo[1], hi[1], h * 0.866)
    pts = []
    for k, yv in enumerate(gy):
        off = (h / 2) if k % 2 else 0.0
        pts.append(np.c_[gx + off, np.full(len(gx), yv)])
    grid = np.vstack(pts)
    grid = grid[_inside(grid, loops_uv)]
    grid = grid[_dist_to_loops(grid, loops_uv) > 0.6 * h]
    # Ограниченное Делоне: рёбра контуров обязательны
    verts_uv = np.vstack(loops_uv + [grid])
    edges, base = [], 0
    for L in loops_uv:
        n = len(L)
        edges += [(base + i, base + (i + 1) % n) for i in range(n)]
        base += n
    res = delaunay_2d_cdt([Vector((float(a), float(b))) for a, b in verts_uv], edges, [], 0, 1e-9, True)
    out_v, _, out_f, orig_v = res[0], res[1], res[2], res[3]
    if len(out_v) != len(verts_uv):
        raise RuntimeError(f"разбиение изменило число вершин: {len(verts_uv)} → {len(out_v)}")
    tris = np.array([f for f in out_f if len(f) == 3])
    cent = verts_uv[tris].mean(1)
    tris = tris[_inside(cent, loops_uv)]
    # Подъём на кузов: контуры — уже на поверхности, внутренние точки — лучами вида
    nb = sum(len(L) for L in loops_uv)
    V = np.vstack(loops3 + [view.lift(surf, grid)]) if len(grid) else np.vstack(loops3)
    if despike_limit:
        V, n_spikes = despike(surf, V, tris, nb, despike_limit)
        print(f"    выбросов луча убрано: {n_spikes}")
    if fit_deg:
        Vf, dev = fit_smooth(view, V, fit_deg)
        if fit_blend > 0:
            # у краёв — к проёму кузова (кромки стекла совпадают с панелями), внутри — гладкая поверхность
            dist = np.zeros(len(V))
            if len(grid):
                dist[nb:] = _dist_to_loops(grid, loops_uv)
            w = np.clip(dist / fit_blend, 0, 1)
            w = w * w * (3 - 2 * w)
            Vf = V + (Vf - V) * w[:, None]
        V = Vf
        print(f"    стекло: подгонка степени {fit_deg}, наибольший сдвиг {dev * 1000:.1f} мм")
        cut, out_loops = 0, []
        for L in loops3:
            out_loops.append(V[cut:cut + len(L)])
            cut += len(L)
        loops3 = out_loops
    # Грани наружу: сначала все — в одну сторону по обходу на виде, потом вся панель — по большинству
    # нормалей поля (по одной грани нельзя: у тонких мест поля нормаль смотрит вбок и грань переворачивается)
    a_uv = verts_uv[tris]
    ccw = ((a_uv[:, 1, 0] - a_uv[:, 0, 0]) * (a_uv[:, 2, 1] - a_uv[:, 0, 1])
           - (a_uv[:, 1, 1] - a_uv[:, 0, 1]) * (a_uv[:, 2, 0] - a_uv[:, 0, 0])) > 0
    tris = np.where(ccw[:, None], tris, tris[:, ::-1])
    nrm = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
    sn = surf.normal(V[tris].mean(1))
    if ((nrm * sn).sum(1) < 0).mean() > 0.5:
        tris = tris[:, ::-1]
    faces = [tuple(t) for t in tris]
    # Направленные рёбра треугольников: по ним ориентируем кромки
    tri_edges = {}
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            tri_edges[(a, b)] = True
    Vlist = [V]
    nV = len(V)
    base = 0
    for li, L in enumerate(loops3):
        n = len(L)
        idx = np.arange(base, base + n)
        base += n
        N = surf.normal(L)
        t = np.roll(L, -1, axis=0) - np.roll(L, 1, axis=0)
        Tout = np.cross(t, N)
        Tout /= np.maximum(np.linalg.norm(Tout, axis=1, keepdims=True), 1e-12)
        # Наружу из материала: в сторону, где нет треугольников панели
        cnt = V[idx] - Tout * 0.002
        if _inside(view.to_uv(cnt), loops_uv).mean() < 0.5:
            Tout = -Tout
        depth = flange if (li == 0 or hole_depth is None) else hole_depth
        rings = []
        for s in range(1, roll_steps + 1):
            th = np.pi / 2 * s / roll_steps
            rings.append(L + roll_r * np.sin(th) * Tout - roll_r * (1 - np.cos(th)) * N)
        rings.append(L + roll_r * Tout - (roll_r + depth) * N)
        R = np.vstack(rings)
        rbase = nV
        Vlist.append(R)
        nV += len(R)
        for i in range(n):
            a, b = idx[i], idx[(i + 1) % n]
            # Ребро a→b принадлежит треугольнику панели — кромка обходит его в обратную сторону
            fwd = (a, b) in tri_edges
            r0a, r0b = rbase + i, rbase + (i + 1) % n
            q = (b, a, r0a, r0b) if fwd else (a, b, r0b, r0a)
            faces.append(q)
            for k in range(len(rings) - 1):
                ka, kb = rbase + k * n + i, rbase + k * n + (i + 1) % n
                q = (kb, ka, ka + n, kb + n) if fwd else (ka, kb, kb + n, ka + n)
                faces.append(q)
    return np.vstack(Vlist), faces
