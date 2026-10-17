"""Купе Ильи: детали поверх панелей — решётка, знак, рёбра воздухозаборников, губа, накладки,
ручки, номера, выхлоп, дворники, днище.

Всё строится от той же поверхности (поле BodyField): рёбра и накладки идут по кузову, а не
висят ровными брусками. Сечения скруглены (никаких голых коробок). Только numpy; разбиение
плоских фигур (знак, задники проёмов) — mathutils в Blender.
"""
from __future__ import annotations

import math

import numpy as np

from domain import View, _inside
from seams import VIEWS, Seam
from surface import Surface, resample, spline2d


# --- Общие построители --------------------------------------------------------------------------

def rounded_rect(w: float, h: float, r: float, n_corner: int = 4) -> np.ndarray:
    """Сечение: скруглённый прямоугольник w×h (по осям u, v), обход против часовой."""
    r = min(r, w / 2 * 0.999, h / 2 * 0.999)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for k in range(n_corner + 1):
            a = math.radians(a0 + 90 * k / n_corner)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


def loft(path: np.ndarray, U: np.ndarray, Vv: np.ndarray, section, cap: bool = True, scale=None):
    """Труба вдоль path: сечение section(i) (k×2) в осях U[i], Vv[i]. Возвращает V, F (четырёхугольники)."""
    n = len(path)
    rings = []
    for i in range(n):
        sec = section(i) if callable(section) else section
        s = 1.0 if scale is None else scale[i]
        rings.append(path[i] + s * (sec[:, :1] * U[i] + sec[:, 1:2] * Vv[i]))
    k = len(rings[0])
    V = np.vstack(rings)
    F = []
    for i in range(n - 1):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            F.append((a, b, b + k, a + k))
    if cap:
        c0 = len(V)
        V = np.vstack([V, rings[0].mean(0), rings[-1].mean(0)])
        for j in range(k):
            F.append((c0, (j + 1) % k, j))
            F.append((c0 + 1, (n - 1) * k + j, (n - 1) * k + (j + 1) % k))
    return V, F


def frames(path: np.ndarray, up: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Касательная T и два поперечных направления (N — ближе к up)."""
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    up = np.broadcast_to(up, path.shape)
    B = np.cross(T, up)
    B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
    N = np.cross(B, T)
    return T, N, B


def merge(parts: list[tuple[np.ndarray, list]]) -> tuple[np.ndarray, list]:
    Vs, Fs, base = [], [], 0
    for V, F in parts:
        Vs.append(V)
        Fs += [tuple(i + base for i in f) for f in F]
        base += len(V)
    return np.vstack(Vs), Fs


def strip_on_surface(surf: Surface, P: np.ndarray, width: float, thick: float, lift: float,
                     r: float | None = None) -> tuple[np.ndarray, list]:
    """Накладка вдоль кривой на кузове: ширина по поверхности, толщина наружу, скруглённое сечение."""
    P = resample(P, max(8, int(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)) / 0.006)))
    Nrm = surf.normal(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    B = np.cross(Nrm, T)
    sec = rounded_rect(width, thick, r if r is not None else thick * 0.45)
    path = P + Nrm * (lift + thick / 2)
    return loft(path, B, Nrm, sec, cap=True)


def poly_mesh(poly2d: np.ndarray, holes2d: list[np.ndarray] = ()) -> tuple[np.ndarray, list]:
    """Плоская фигура (с дырами) → треугольники (mathutils)."""
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    loops = [poly2d] + list(holes2d)
    verts = np.vstack(loops)
    edges, base = [], 0
    for L in loops:
        edges += [(base + i, base + (i + 1) % len(L)) for i in range(len(L))]
        base += len(L)
    res = delaunay_2d_cdt([Vector((float(a), float(b))) for a, b in verts], edges, [], 0, 1e-9, True)
    out_v = np.array([[v.x, v.y] for v in res[0]])
    tris = np.array([f for f in res[2] if len(f) == 3])
    cent = out_v[tris].mean(1)
    tris = tris[_inside(cent, loops)]
    return out_v, [tuple(t) for t in tris]


def extrude_badge(poly_list: list[np.ndarray], depth: float, bevel: float, origin: np.ndarray,
                  ax_u: np.ndarray, ax_v: np.ndarray, ax_n: np.ndarray) -> tuple[np.ndarray, list]:
    """Плоский знак: контуры (метры, в плоскости u,v) → объём с фаской по лицу, наружу по ax_n."""
    parts = []
    for poly in poly_list:
        poly = np.asarray(poly, dtype=float)
        if poly_area(poly) < 0:
            poly = poly[::-1]
        inner = offset_poly(poly, -bevel)
        fv, ff = poly_mesh(inner)
        n = len(poly)
        def place(p2, h):
            return origin + p2[:, :1] * ax_u + p2[:, 1:2] * ax_v + h * ax_n
        V = [place(poly, 0.0), place(poly, depth - bevel), place(inner, depth)]
        F = []
        for ring in range(2):
            for j in range(n):
                a, b = ring * n + j, ring * n + (j + 1) % n
                F.append((a, b, b + n, a + n))
        base = 3 * n
        V.append(place(fv, depth))
        # лицо: вершины разбиения внутреннего контура совпадают по порядку с inner
        F += [tuple(base + i for i in t) for t in ff]
        parts.append((np.vstack(V), F))
    return merge(parts)


def poly_area(p: np.ndarray) -> float:
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def offset_poly(p: np.ndarray, d: float) -> np.ndarray:
    """Сдвиг выпуклого/почти выпуклого многоугольника (против часовой) на d (минус — внутрь)."""
    n = len(p)
    out = []
    for i in range(n):
        a, b, c = p[i - 1], p[i], p[(i + 1) % n]
        e1, e2 = b - a, c - b
        n1 = np.array([e1[1], -e1[0]]) / np.linalg.norm(e1)
        n2 = np.array([e2[1], -e2[0]]) / np.linalg.norm(e2)
        m = n1 + n2
        m /= np.linalg.norm(m)
        out.append(b + m * d / max(np.dot(m, n1), 0.3))
    return np.array(out)


# --- Детали ---------------------------------------------------------------------------------------

WEDGE_SVG = ([(70, 70), (230, 70), (199.1, 128), (100.9, 128)], [(108.4, 142), (191.6, 142), (150, 220)])


def wedge_polys(width: float) -> list[np.ndarray]:
    """Знак «Клин» (вариант 2): верхняя трапеция и нижний треугольник, ширина width, центр (0,0)."""
    k = width / 160.0
    return [np.array([((x - 150) * k, (145 - y) * k) for x, y in poly]) for poly in WEDGE_SVG]


def badge(origin, normal, up, width: float, depth: float = 0.007):
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    u = np.cross(np.asarray(up, float), n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return extrude_badge(wedge_polys(width), depth, min(0.0015, depth * 0.3), np.asarray(origin, float), u, v, n)


def outline_z_range(outline_xz: list[tuple[float, float]], x: float) -> tuple[float, float] | None:
    """Пересечение вертикали x с замкнутым контуром (вид спереди): низ и верх."""
    c = spline2d(outline_xz, 600, closed=True)
    zs = []
    for i in range(len(c) - 1):
        (x0, z0), (x1, z1) = c[i], c[i + 1]
        if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
            zs.append(z0 + (x - x0) * (z1 - z0) / (x1 - x0))
    return (min(zs), max(zs)) if len(zs) >= 2 else None


def outline_x_range(outline_xz, z: float):
    c = spline2d(outline_xz, 600, closed=True)
    xs = []
    for i in range(len(c) - 1):
        (x0, z0), (x1, z1) = c[i], c[i + 1]
        if (z0 - z) * (z1 - z) <= 0 and z0 != z1:
            xs.append(x0 + (z - z0) * (x1 - x0) / (z1 - z0))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


def grille_slats(surf: Surface, outline_xz, n_slats: int = 13, t: float = 0.017, depth: float = 0.055,
                 recess: float = 0.014, margin: float = 0.012):
    """Вертикальные рёбра решётки по лицу бампера (концепт: толстые, со скруглённым лицом)."""
    F_view = VIEWS["front"]
    xs_all = [p[0] for p in outline_xz]
    x0, x1 = min(xs_all), max(xs_all)
    parts = []
    for x in np.linspace(x0 + 0.045, x1 - 0.045, n_slats):
        zr = outline_z_range(outline_xz, x)
        if zr is None:
            continue
        zb, zt = zr[0] + margin, zr[1] - margin
        zz = np.linspace(zb, zt, max(6, int((zt - zb) / 0.01)))
        P = F_view.lift(surf, np.c_[np.full(len(zz), x), zz]) + np.array([0, recess, 0])
        U = np.broadcast_to(np.array([1.0, 0, 0]), P.shape)       # толщина — поперёк
        Vv = np.broadcast_to(np.array([0, 1.0, 0]), P.shape)      # глубина — назад
        sec = rounded_rect(t, depth, t * 0.48, 5)
        sec[:, 1] += depth / 2                                     # лицо ребра — в точке P
        parts.append(loft(P, U, Vv, sec))
    return merge(parts)


def horizontal_fins(surf: Surface, outline_xz, zs: list[float], t: float = 0.009, depth: float = 0.06,
                    recess: float = 0.010, margin: float = 0.010, view: str = "front"):
    """Горизонтальные лопатки в проёме (воздухозаборник): идут по лицу бампера от края до края."""
    V_ = VIEWS[view]
    parts = []
    for z in zs:
        xr = outline_x_range(outline_xz, z)
        if xr is None:
            continue
        xx = np.linspace(xr[0] + margin, xr[1] - margin, 60)
        S = V_.lift(surf, np.c_[xx, np.full(len(xx), z)])
        nrm = surf.normal(S)
        P = S - nrm * recess
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U = np.cross(nrm, T)                                       # вверх по лицу
        U /= np.linalg.norm(U, axis=1, keepdims=True)
        sec = rounded_rect(t, depth, t * 0.48, 4)[:, ::-1].copy()  # (глубина, толщина)
        sec[:, 0] += depth / 2                                     # от лица бампера внутрь
        parts.append(loft(P, -nrm, U, sec[:, [0, 1]]))
    return merge(parts)


def backing(surf: Surface, view: View, loop3: np.ndarray, depth: float, h: float = 0.012):
    """Задник проёма: та же фигура, утопленная на depth (тёмная сетка / соты)."""
    uv = view.to_uv(loop3)
    pv, pf = poly_mesh(resample(np.vstack([uv, uv[:1]]), max(40, int(len(uv) / 2)))[:-1])
    P = view.lift(surf, pv)
    return P - surf.normal(P) * depth, [f[::-1] for f in pf]


# --- Зеркало (левое) — по чертежу CLE: план POLYLINE182, вид спереди 107, сбоку 200 -----------------
# По X (от двери к кончику): перёд и зад корпуса (Y), низ и верх (Z)
MIRROR_X = np.array([0.848, 0.870, 0.900, 0.940, 0.975, 1.005, 1.022, 1.032, 1.037])
MIRROR_YF = np.array([-0.470, -0.486, -0.484, -0.470, -0.450, -0.420, -0.392, -0.360, -0.330])
MIRROR_YR = np.array([-0.352, -0.340, -0.326, -0.309, -0.297, -0.287, -0.284, -0.288, -0.300])
MIRROR_ZB = np.array([1.000, 0.996, 0.994, 0.993, 0.996, 1.002, 1.012, 1.025, 1.040])
MIRROR_ZT = np.array([1.118, 1.134, 1.137, 1.130, 1.118, 1.100, 1.084, 1.068, 1.052])


def mirror_parts(surf: Surface):
    """Корпус (сечения поперёк длины, скруглённые сильнее спереди), стекло на плоском заду, ножка к двери."""
    xs = np.linspace(MIRROR_X[0], MIRROR_X[-1], 30)
    yf, yr = np.interp(xs, MIRROR_X, MIRROR_YF), np.interp(xs, MIRROR_X, MIRROR_YR)
    zb, zt = np.interp(xs, MIRROR_X, MIRROR_ZB), np.interp(xs, MIRROR_X, MIRROR_ZT)
    path = np.c_[xs, (yf + yr) / 2, (zb + zt) / 2]
    U = np.broadcast_to(np.array([0, 1.0, 0]), path.shape)        # вдоль машины: + назад
    Vv = np.broadcast_to(np.array([0, 0, 1.0]), path.shape)

    def sec(i):
        w, h = yr[i] - yf[i], zt[i] - zb[i]
        base = rounded_rect(w, h, min(w, h) * 0.42, 6)
        # перёд (минус по U) — пухлее: сдвигаем переднюю половину по дуге
        bulge = np.clip(-base[:, 0] / (w / 2), 0, 1) ** 2 * 0.0
        base[:, 0] -= bulge
        return base
    housing = loft(path, U, Vv, sec, cap=True)
    # Стекло: плоскость чуть утоплена в заднюю кромку корпуса
    gx = np.linspace(xs[1], xs[-4], 18)
    gz0 = np.interp(gx, xs, zb) + 0.012
    gz1 = np.interp(gx, xs, zt) - 0.012
    gy = np.interp(gx, xs, yr) + 0.0008
    rows = 10
    G = []
    for j in range(rows):
        t = j / (rows - 1)
        G.append(np.c_[gx, gy, gz0 + (gz1 - gz0) * t])
    G = np.array(G)                                               # [rows, len(gx), 3]
    gv = G.reshape(-1, 3)
    n = len(gx)
    gf = [(j * n + i + 1, j * n + i, (j + 1) * n + i, (j + 1) * n + i + 1) for j in range(rows - 1) for i in range(n - 1)]
    glass = (gv, gf)
    # Ножка: от двери под корпусом, обтекаемое сечение
    door_pt = VIEWS["side"].lift(surf, np.array([[-0.420, 0.925]]))[0]
    top_pt = np.array([0.905, -0.405, 1.002])
    t = np.linspace(0, 1, 14)[:, None]
    mid = (door_pt + top_pt) / 2 + np.array([0.02, 0, -0.01])
    P = (1 - t) ** 2 * door_pt + 2 * (1 - t) * t * mid + t ** 2 * top_pt
    T, N, B = frames(P, np.array([0, 1.0, 0]))
    arm = loft(P, N, B, rounded_rect(0.055, 0.022, 0.010, 4), cap=True)
    return housing, glass, arm


def wheel_liner(yc: float, zc: float, r: float = 0.405, x_in: float = 0.50, x_out: float = 0.955,
                phi0: float = -24.0, phi1: float = 204.0):
    """Подкрылок: свод над колесом (часть цилиндра вокруг оси колеса) и внутренняя стенка."""
    ph = np.radians(np.linspace(phi0, phi1, 64))
    xs = np.linspace(x_in, x_out, 12)
    V = []
    for x in xs:
        V.append(np.c_[np.full(len(ph), x), yc + r * np.cos(ph), zc + r * np.sin(ph)])
    V = np.vstack(V)
    n = len(ph)
    F = [(i * n + j + 1, i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1) for i in range(len(xs) - 1) for j in range(n - 1)]
    # внутренняя стенка: кольцевой сектор от r до 0.6 r на x_in
    W = []
    for rr in np.linspace(r, r * 0.55, 6):
        W.append(np.c_[np.full(n, x_in), yc + rr * np.cos(ph), zc + rr * np.sin(ph)])
    W = np.vstack(W)
    base = len(V)
    F += [(base + i * n + j, base + i * n + j + 1, base + (i + 1) * n + j + 1, base + (i + 1) * n + j)
          for i in range(5) for j in range(n - 1)]
    return np.vstack([V, W]), F


def under_tray(field, z: float = 0.196, y0: float = -2.12, y1: float = 2.26, wheel_y: float = 1.4355):
    """Плоское днище под кузовом с вырезами под колёса (план — по ширине кузова, с запасом внутрь)."""
    ys = np.linspace(y0, y1, 220)
    half = np.interp(ys, field.ys, field.plan.v) * 0.90
    half = np.minimum(half, 0.84)
    for c in (-wheel_y, wheel_y):
        m = np.abs(ys - c) < 0.44
        half[m] = np.minimum(half[m], 0.49)
    half = np.maximum(half, 0.05)
    left = np.c_[half, ys]
    right = np.c_[-half[::-1], ys[::-1]]
    poly = np.vstack([left, right])
    pv, pf = poly_mesh(poly[::-1] if poly_area(poly) < 0 else poly)
    V = np.c_[pv[:, 0], pv[:, 1], np.full(len(pv), z)]
    return V, [f[::-1] for f in pf]


def wiper(surf: Surface, p0_top: tuple, p1_top: tuple, pivot_top: tuple):
    """Дворник: щётка по низу лобового стекла и рычаг от оси у короба."""
    top = VIEWS["top"]
    blade_line = top.lift(surf, np.linspace(np.array(p0_top), np.array(p1_top), 40))
    blade = strip_on_surface(surf, blade_line, 0.018, 0.011, 0.002, r=0.004)
    mid = blade_line[len(blade_line) // 2]
    piv = top.lift(surf, np.array([pivot_top]))[0]
    arm_line = np.linspace(piv, mid, 20)
    arm_line = surf.project(arm_line)
    arm = strip_on_surface(surf, arm_line, 0.016, 0.008, 0.014, r=0.003)
    return merge([blade, arm])


def headlamp_inner(surf: Surface, lamp_loop: np.ndarray, view, top_edge: np.ndarray):
    """Начинка фары: отражатель (задник), полоса дневного света вдоль верхней кромки, две линзы."""
    back = backing(surf, view, lamp_loop, 0.045)
    L = lamp_loop
    # полоса ДХО: по верхней кромке фары (по порядку шва), ниже на 1,2 см и утоплена на 8 мм
    top = resample(top_edge, 90)[6:-6]
    c = L.mean(0)
    top = surf.project(top + 0.25 * (c - top))                    # к середине фары, под стекло
    nrm = surf.normal(top)
    drl_line = top - nrm * 0.012
    drl = loft(drl_line, *frames(drl_line, np.array([0, 0, 1.0]))[1:], rounded_rect(0.008, 0.006, 0.0028, 3))
    # две линзы проекторов в нижней половине
    lenses = []
    lo = L[L[:, 2] < np.quantile(L[:, 2], 0.5)]
    xs = np.quantile(lo[:, 0], [0.30, 0.62])
    for x in xs:
        near = L[np.argsort(np.abs(L[:, 0] - x))[:6]]
        c = near.mean(0)
        c[2] = np.quantile(L[:, 2], 0.40)
        nn = surf.normal(c[None])[0]
        c = c - nn * 0.022
        P = np.array([c - nn * 0.04, c])
        P = np.linspace(P[0], P[1], 6)
        T, N, B = frames(P, np.array([0, 0, 1.0]))
        circ = np.c_[np.cos(np.linspace(0, 2 * math.pi, 24, endpoint=False)),
                     np.sin(np.linspace(0, 2 * math.pi, 24, endpoint=False))] * 0.022
        lenses.append(loft(P, N, B, circ, cap=True))
    return back, drl, merge(lenses)



def fins_in_loop(surf: Surface, view: View, loop3: np.ndarray, zs: list[float], t: float = 0.009,
                 depth: float = 0.06, recess: float = 0.010, margin: float = 0.014):
    """Горизонтальные лопатки строго внутри проёма: края берутся из контура на виде (v = высота)."""
    uv = view.to_uv(loop3)
    parts = []
    for z in zs:
        us = []
        n = len(uv)
        for i in range(n):
            (u0, v0), (u1, v1) = uv[i], uv[(i + 1) % n]
            if (v0 - z) * (v1 - z) <= 0 and v0 != v1:
                us.append(u0 + (z - v0) * (u1 - u0) / (v1 - v0))
        if len(us) < 2:
            continue
        u_lo, u_hi = min(us), max(us)
        # отступ от краёв проёма — в метрах по поверхности: перевести через длину дуги
        uu = np.linspace(u_lo, u_hi, 80)
        S = view.lift(surf, np.c_[uu, np.full(len(uu), z)])
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(S, axis=0), axis=1))]
        keep = (d > margin) & (d < d[-1] - margin)
        S = S[keep]
        if len(S) < 3:
            continue
        nrm = surf.normal(S)
        P = S - nrm * recess
        T = np.gradient(P, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)
        U = np.cross(nrm, T)
        U /= np.linalg.norm(U, axis=1, keepdims=True)
        sec = rounded_rect(t, depth, t * 0.48, 4)[:, ::-1].copy()
        sec[:, 0] += depth / 2
        parts.append(loft(P, -nrm, U, sec[:, [0, 1]]))
    return merge(parts)
