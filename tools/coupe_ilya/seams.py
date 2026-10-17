"""Купе Ильи: швы панелей — кривые на кузове из точек, заданных на разных видах.

Точка шва — ("вид", u, v): сбоку ("side": Y, Z), сверху ("top": X, Y), спереди ("front": X, Z),
сзади ("rear": X, Z) или ("p", x, y, z) — прямо в пространстве. Каждая точка поднимается на
кузов своим лучом; шов сглаживается на «виде шва» (где он ложится без складок) и снова
поднимается на кузов. Контур панели — замкнутая цепочка швов; соседние панели берут один и
тот же шов, и каждая отступает от него в свою сторону — зазор получается ровным.
"""
from __future__ import annotations

import numpy as np

from domain import View
from surface import Surface, spline2d

VIEWS = {k: View(k) for k in View.PLANAR}
# Цилиндрические виды для заворачивающих панелей
VIEWS["rf"] = View("cyl", c=(0, -1.55, 0), a=(0, 0, 1), e0=(0, -1, 0))        # перёд → левый борт
VIEWS["rr"] = View("cyl", c=(0, 1.60, 0), a=(0, 0, -1), e0=(0, 1, 0))         # корма → левый борт
VIEWS["rs"] = View("cyl", c=(0.40, 0, 0.55), a=(0, -1, 0), e0=(1, 0, 0))      # левый борт → верх
VIEWS["rx_rear"] = View("cyl", c=(0, 1.95, 0.62), a=(1, 0, 0), e0=(0, 1, 0))   # корма: верх, торец, низ
VIEWS["rx_front"] = View("cyl", c=(0, -1.75, 0.45), a=(1, 0, 0), e0=(0, 0, 1))  # верх → перёд

# Плоские виды по нормали к стёклам: луч почти перпендикулярен стеклу (лобовое ~27°, заднее ~18° к горизонту)
VIEWS["ws"] = View("plane", u=(1, 0, 0), v=(0, 0.89101, 0.45399),
                   d=(0, 0.45399, -0.89101))
VIEWS["bl"] = View("plane", u=(1, 0, 0), v=(0, -0.95106, 0.30902),
                   d=(0, -0.30902, -0.95106))


def point3(surf: Surface, spec) -> np.ndarray:
    """Одна точка шва на кузове."""
    if spec[0] == "p":
        return surf.project(np.array([spec[1:4]], dtype=float))[0]
    return VIEWS[spec[0]].lift(surf, np.array([[spec[1], spec[2]]], dtype=float))[0]


def mirror_spec(spec):
    """Точка на правом борту (X → −X)."""
    k = spec[0]
    if k in ("top", "front", "rear", "bottom"):
        return (k, -spec[1], spec[2])
    if k == "p":
        return ("p", -spec[1], spec[2], spec[3])
    if k == "side":
        return ("side_r", spec[1], spec[2])
    return spec


class Seam:
    """Шов: точки → на кузов → сглаживание на виде шва → плотная кривая на кузове."""

    def __init__(self, surf: Surface, pts, view: str, n: int = 260, smooth: bool = True,
                 closed: bool = False) -> None:
        P = np.array([point3(surf, s) for s in pts])
        V = VIEWS[view]
        uv = V.to_uv(P)
        # Разрыв угла на цилиндрическом виде не нужен: швы короче полуоборота
        if closed:
            self.P = V.lift(surf, spline2d(uv, n + 1, closed=True)[:-1])
            return
        dense = spline2d(uv, n) if (smooth and len(uv) > 2) else _poly(uv, n)
        self.P = V.lift(surf, dense)
        self.P[0], self.P[-1] = P[0], P[-1]      # концы — точно в углах

    def reversed(self) -> np.ndarray:
        return self.P[::-1]


def _poly(uv: np.ndarray, n: int) -> np.ndarray:
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(uv, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, uv[:, 0]), np.interp(t, d, uv[:, 1])]


def loop(parts: list[np.ndarray]) -> np.ndarray:
    """Замкнуть цепочку кривых (конец каждой = начало следующей) без повторов в углах."""
    out = []
    for i, c in enumerate(parts):
        nxt = parts[(i + 1) % len(parts)]
        gap = np.linalg.norm(c[-1] - nxt[0])
        if gap > 0.01:
            raise ValueError(f"швы не сходятся: кусок {i} → {i + 1}, разрыв {gap * 1000:.0f} мм")
        out.append(c[:-1])
    return np.vstack(out)
