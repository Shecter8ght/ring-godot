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

    def __init__(self, kind: str, c=(0, 0, 0), a=(0, 0, 1), e0=(0, -1, 0), r0: float = 1.0) -> None:
        self.kind = kind
        if kind in self.PLANAR:
            u, v, d = (np.array(t, dtype=float) for t in self.PLANAR[kind])
            self.u, self.v, self.d = u, v, d
        else:
            self.c = np.array(c, dtype=float)
            self.a = np.array(a, dtype=float) / np.linalg.norm(a)
            e0 = np.array(e0, dtype=float)
            e0 = e0 - self.a * (e0 @ self.a)
            self.e0 = e0 / np.linalg.norm(e0)
            self.e1 = np.cross(self.a, self.e0)
            self.r0 = r0

    def to_uv(self, P: np.ndarray) -> np.ndarray:
        if self.kind in self.PLANAR:
            return np.c_[P @ self.u, P @ self.v]
        q = P - self.c
        th = np.arctan2(q @ self.e1, q @ self.e0)
        return np.c_[th * self.r0, q @ self.a]

    def rays(self, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.kind in self.PLANAR:
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


def domain_panel(surf: Surface, view: View, outer, holes=(), h: float = 0.012, gap: float = 0.0045,
                 roll_r: float = 0.003, flange: float = 0.012, roll_steps: int = 3,
                 hole_depth: float | None = None, smooth: bool = True):
    """Панель: (вершины, грани). hole_depth — глубина стенки проёма (по умолчанию как отбортовка)."""
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
    # Грани наружу
    nrm = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
    sn = surf.normal(V[tris].mean(1))
    tris = np.where(((nrm * sn).sum(1) < 0)[:, None], tris[:, ::-1], tris)
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
