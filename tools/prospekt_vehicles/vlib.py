"""Транспорт «Проспекта»: общие помощники панелей — виды, швы, контуры, зеркало.

Панели строятся тем же способом, что у принятого купе Ильи: область на виде → ограниченное
разбиение Делоне → подъём лучами вида на поверхность поля, кромки завёрнуты внутрь (см.
tools/coupe_ilya/domain.py — модуль берётся оттуда без изменений). Здесь — виды под размеры
конкретной машины и шов, который берёт точки с разных видов.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

COUPE = Path(__file__).resolve().parent.parent / "coupe_ilya"
if str(COUPE) not in sys.path:
    sys.path.insert(0, str(COUPE))

from domain import View, domain_panel, loop_on_surface, _inside  # noqa: E402,F401
from surface import Surface, resample, spline2d, cut  # noqa: E402,F401


class ViewR(View):
    """Вид с запасом дальности: лучи плоского вида начинаются за reach метров от плоскости через начало
    координат (у купе — 3,5 м; автобус длиной 12 м целиком за ними не помещался)."""

    def __init__(self, *a, reach: float = 3.5, **kw) -> None:
        super().__init__(*a, **kw)
        self.reach = reach

    def rays(self, uv: np.ndarray):
        if self.planar:
            O = uv[:, :1] * self.u + uv[:, 1:2] * self.v - self.d * self.reach
            return O, np.broadcast_to(self.d, O.shape)
        return super().rays(uv)

    def lift(self, surf: Surface, uv: np.ndarray) -> np.ndarray:
        O, D = self.rays(uv)
        return surf.ray(O, np.ascontiguousarray(D), t_max=2 * self.reach + 1.0)


def make_views(spec: dict) -> dict[str, View]:
    """Виды под машину: плоские, цилиндры на углах носа и кормы, борт → крыша, стёкла по нормали."""
    reach = max(3.5, spec["length"] / 2 + 2.0)
    V = {k: ViewR(k, reach=reach) for k in View.PLANAR}
    y_n = spec["front"][len(spec["front"]) // 2][1]
    y_t = spec["rear"][len(spec["rear"]) // 2][1]
    lay = spec.get("views", {})
    V["rf"] = View("cyl", c=(0, y_n + lay.get("rf_back", 0.60), 0), a=(0, 0, 1), e0=(0, -1, 0))
    V["rr"] = View("cyl", c=(0, y_t - lay.get("rr_back", 0.62), 0), a=(0, 0, -1), e0=(0, 1, 0))
    V["rs"] = View("cyl", c=(lay.get("rs_x", 0.38), 0, lay.get("rs_z", 0.60)), a=(0, -1, 0), e0=(1, 0, 0))
    V["rx_rear"] = View("cyl", c=(0, lay.get("rxr_y", y_t - 0.55), lay.get("rxr_z", 0.70)), a=(1, 0, 0), e0=(0, 1, 0))
    V["rx_front"] = View("cyl", c=(0, lay.get("rxf_y", y_n + 0.40), lay.get("rxf_z", 0.50)), a=(1, 0, 0), e0=(0, 0, 1))
    for key in ("ws", "bl"):
        if key not in spec:
            continue
        pts = sorted(spec[key])
        (z0, y0), (z1, y1) = pts[0], pts[-1]
        dy, dz = (y1 - y0), (z1 - z0)
        n = math.hypot(dy, dz)
        vv = (0.0, dy / n, dz / n)                      # вдоль стекла вверх
        # нормаль стекла наружу смотрит вверх; луч — внутрь машины
        p = np.array([0.0, -dz, dy]) / n
        if p[2] < 0:
            p = -p
        V[key] = ViewR("plane", u=(1, 0, 0), v=vv, d=tuple(-p), reach=reach)
    for name, (c, a, e0) in lay.get("extra", {}).items():
        V[name] = View("cyl", c=c, a=a, e0=e0)
    return V


class Seam:
    """Шов: точки разных видов → на кузов → сглаживание на виде шва → плотная кривая на кузове.

    Точка — ("вид", u, v) или ("p", x, y, z). Концы ставятся точно (углы панелей сходятся).
    """

    def __init__(self, surf: Surface, views: dict, pts, view: str, n: int = 220, smooth: bool = True,
                 closed: bool = False) -> None:
        P = np.array([point3(surf, views, s) for s in pts])
        V = views[view]
        uv = V.to_uv(P)
        if closed:
            self.P = V.lift(surf, spline2d(uv, n + 1, closed=True)[:-1])
            return
        dense = spline2d(uv, n) if (smooth and len(uv) > 2) else _poly(uv, n)
        self.P = V.lift(surf, dense)
        self.P[0], self.P[-1] = P[0], P[-1]

    def reversed(self) -> np.ndarray:
        return self.P[::-1]


def point3(surf: Surface, views: dict, spec) -> np.ndarray:
    if spec[0] == "p":
        return surf.project(np.array([spec[1:4]], dtype=float))[0]
    return views[spec[0]].lift(surf, np.array([[spec[1], spec[2]]], dtype=float))[0]


def _poly(uv: np.ndarray, n: int) -> np.ndarray:
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(uv, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, uv[:, 0]), np.interp(t, d, uv[:, 1])]


def loop(parts: list[np.ndarray], tol: float = 0.012) -> np.ndarray:
    """Замкнуть цепочку кривых (конец каждой = начало следующей)."""
    out = []
    for i, c in enumerate(parts):
        nxt = parts[(i + 1) % len(parts)]
        gap = np.linalg.norm(c[-1] - nxt[0])
        if gap > tol:
            raise ValueError(f"швы не сходятся: кусок {i} → {i + 1}, разрыв {gap * 1000:.0f} мм")
        out.append(c[:-1])
    return np.vstack(out)


def mirror_curve(c: np.ndarray) -> np.ndarray:
    m = c.copy()
    m[:, 0] *= -1
    return m


def sym_loop(left: list[np.ndarray]) -> np.ndarray:
    """Симметричная панель: левая половина от оси до оси, правая — зеркально обратно."""
    return loop(left + [mirror_curve(c)[::-1] for c in reversed(left)])


def mirror_mesh(V: np.ndarray, F: list) -> tuple[np.ndarray, list]:
    W = V.copy()
    W[:, 0] *= -1
    return W, [tuple(f[::-1]) for f in F]


def arch_pt(yc: float, zc: float, r: float, phi_deg: float, view: str = "side"):
    """Точка дуги арки на виде сбоку: φ в градусах, 0 — назад (+Y), 90 — вверх."""
    a = math.radians(phi_deg)
    return (view, yc + r * math.cos(a), zc + r * math.sin(a))


def arch_pts(yc: float, zc: float, r: float, phi0: float, phi1: float, n: int = 9):
    return [arch_pt(yc, zc, r, p) for p in np.linspace(phi0, phi1, n)]


def phi_at_z(zc: float, r: float, z: float, front_side: bool) -> float:
    s = math.degrees(math.asin(max(-1.0, min(1.0, (z - zc) / r))))
    return 180.0 - s if front_side else s


def resample_closed(L: np.ndarray, step: float) -> np.ndarray:
    c = np.vstack([L, L[:1]])
    length = float(np.sum(np.linalg.norm(np.diff(c, axis=0), axis=1)))
    n = max(16, int(length / step))
    return resample(c, n + 1)[:-1]


def offset_loop(surf: Surface, view: View, L: np.ndarray, d: float, h: float = 0.01) -> np.ndarray:
    """Контур на кузове, сдвинутый внутрь своей области на d (по поверхности)."""
    return loop_on_surface(surf, view, L, h, d, False)


def fillet_poly(pts, r: float, closed: bool = False, n_arc: int = 8) -> np.ndarray:
    """Ломаная со скруглёнными углами (2D): прямые участки остаются прямыми, углы — дугами радиуса r.

    Радиус в каждом углу ограничен половиной соседних отрезков; r может быть списком по углам.
    """
    p = np.asarray(pts, dtype=float)
    n = len(p)
    rs = r if isinstance(r, (list, tuple)) else [r] * n
    out = []
    idx = range(n) if closed else range(1, n - 1)
    if not closed:
        out.append(p[0])
    for i in idx:
        a, b, c = p[i - 1], p[i], p[(i + 1) % n]
        u, v = a - b, c - b
        lu, lv = np.linalg.norm(u), np.linalg.norm(v)
        if lu < 1e-9 or lv < 1e-9:
            continue
        u, v = u / lu, v / lv
        ang = math.acos(max(-1.0, min(1.0, float(u @ v))))
        if ang > math.pi - 1e-3 or rs[i] <= 0:
            out.append(b)
            continue
        t = rs[i] / math.tan(ang / 2)
        t = min(t, lu * 0.48, lv * 0.48)
        rr = t * math.tan(ang / 2)
        p0, p1 = b + u * t, b + v * t
        bis = (u + v) / np.linalg.norm(u + v)
        cen = b + bis * (rr / math.sin(ang / 2))
        a0 = math.atan2(*(p0 - cen)[::-1])
        a1 = math.atan2(*(p1 - cen)[::-1])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(n_arc + 1):
            th = a0 + da * k / n_arc
            out.append(cen + rr * np.array([math.cos(th), math.sin(th)]))
    if not closed:
        out.append(p[-1])
    return np.array(out)


def lift_poly(surf: Surface, view: View, uv: np.ndarray, step: float = 0.004) -> np.ndarray:
    """Ломаная на виде → плотная кривая на кузове (равномерно по длине на виде)."""
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(uv, axis=0), axis=1))]
    n = max(8, int(d[-1] / step))
    t = np.linspace(0, d[-1], n)
    dense = np.c_[np.interp(t, d, uv[:, 0]), np.interp(t, d, uv[:, 1])]
    return view.lift(surf, dense)
