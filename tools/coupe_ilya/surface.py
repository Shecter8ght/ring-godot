"""Купе Ильи: точки и кривые на поверхности кузова (поле BodyField).

Проекция на поверхность — шаги Ньютона по градиенту поля; луч до поверхности — шаги по
значению поля (оно близко к расстоянию) и деление отрезка. Кривые с видов (сбоку, сверху,
спереди, сзади) переносятся на кузов лучом вдоль оси вида.
"""
from __future__ import annotations

import numpy as np


class Surface:
    def __init__(self, field, arches: bool = True) -> None:
        self.field = field
        self.arches = arches

    def f(self, P: np.ndarray) -> np.ndarray:
        return self.field.eval(P[..., 0], P[..., 1], P[..., 2], arches=self.arches)

    def grad(self, P: np.ndarray, eps: float = 4e-4) -> np.ndarray:
        g = np.empty_like(P)
        for k in range(3):
            d = np.zeros(3)
            d[k] = eps
            g[..., k] = (self.f(P + d) - self.f(P - d)) / (2 * eps)
        return g

    def normal(self, P: np.ndarray) -> np.ndarray:
        g = self.grad(P)
        return g / np.maximum(np.linalg.norm(g, axis=-1, keepdims=True), 1e-9)

    def project(self, P: np.ndarray, iters: int = 30, max_step: float = 0.02) -> np.ndarray:
        """Ближайшая точка поверхности (Ньютон вдоль градиента, шаг не больше max_step)."""
        P = P.copy()
        for _ in range(iters):
            v = self.f(P)
            g = self.grad(P)
            d = (v / np.maximum((g * g).sum(-1), 1e-9))[..., None] * g
            n = np.linalg.norm(d, axis=-1, keepdims=True)
            P -= d * np.minimum(1.0, max_step / np.maximum(n, 1e-12))
            if np.abs(v).max() < 1e-6:
                break
        return P

    def ray(self, O: np.ndarray, D: np.ndarray, t_max: float = 4.0) -> np.ndarray:
        """Первая точка поверхности на луче O + t·D (D — единичный)."""
        O = np.atleast_2d(O).astype(float)
        D = np.broadcast_to(D, O.shape).astype(float)
        t = np.zeros(len(O))
        done = np.zeros(len(O), dtype=bool)
        prev_t = t.copy()
        for _ in range(400):
            P = O + t[:, None] * D
            v = self.f(P)
            hit = v < 1e-4
            done |= hit
            if done.all():
                break
            step = np.where(done, 0.0, np.maximum(v * 0.7, 1e-4))
            prev_t = np.where(done, prev_t, t)
            t = np.where(done, t, np.minimum(t + step, t_max))
        # Уточнить делением между последним «снаружи» и «внутри»
        lo, hi = prev_t, t
        for _ in range(30):
            mid = (lo + hi) / 2
            inside = self.f(O + mid[:, None] * D) < 0
            hi = np.where(inside, mid, hi)
            lo = np.where(inside, lo, mid)
        return O + hi[:, None] * D


# --- Кривые с видов ---------------------------------------------------------------------------

def spline2d(pts: list[tuple[float, float]], n: int = 400, closed: bool = False) -> np.ndarray:
    """Гладкая кривая через точки (центростремительный Кэтмелл — Ром), n точек равномерно по длине."""
    p = np.asarray(pts, dtype=float)
    if len(p) < 3:
        return resample(p, n)
    if closed:
        ext = np.vstack([p[-1:], p, p[:2]])
    else:
        ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        t0 = 0.0
        t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5 + 1e-9
        t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5 + 1e-9
        t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5 + 1e-9
        t = np.linspace(t1, t2, 24, endpoint=False)[:, None]
        a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
        b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
        out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    out.append(ext[-2][None] if not closed else ext[1][None])
    return resample(np.vstack(out), n)


def polyline2d(pts: list[tuple[float, float]], n: int = 400) -> np.ndarray:
    """Ломаная без сглаживания (прямые участки), n точек по длине."""
    p = np.asarray(pts, dtype=float)
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, p[:, 0]), np.interp(t, d, p[:, 1])]


def from_side(surf: Surface, yz: np.ndarray, side: float = 1.0) -> np.ndarray:
    """Вид сбоку (Y, Z) → кузов: луч от борта внутрь по X. side=+1 — левый борт (+X)."""
    O = np.c_[np.full(len(yz), 1.4 * side), yz[:, 0], yz[:, 1]]
    return surf.ray(O, np.array([-side, 0.0, 0.0]))


def from_top(surf: Surface, xy: np.ndarray) -> np.ndarray:
    """План (X, Y) → кузов: луч сверху вниз."""
    O = np.c_[xy[:, 0], xy[:, 1], np.full(len(xy), 2.0)]
    return surf.ray(O, np.array([0.0, 0.0, -1.0]))


def from_front(surf: Surface, xz: np.ndarray) -> np.ndarray:
    """Вид спереди (X, Z) → кузов: луч от носа назад (+Y)."""
    O = np.c_[xz[:, 0], np.full(len(xz), -3.0), xz[:, 1]]
    return surf.ray(O, np.array([0.0, 1.0, 0.0]))


def from_rear(surf: Surface, xz: np.ndarray) -> np.ndarray:
    """Вид сзади (X, Z) → кузов: луч от кормы вперёд (−Y)."""
    O = np.c_[xz[:, 0], np.full(len(xz), 3.2), xz[:, 1]]
    return surf.ray(O, np.array([0.0, -1.0, 0.0]))


def resample(c: np.ndarray, n: int) -> np.ndarray:
    """Равномерно по длине дуги, n точек (3D или 2D)."""
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, c[:, k]) for k in range(c.shape[1])], axis=1)


def cut(c: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Кусок кривой между ближайшими к точкам a и b вершинами (в порядке кривой)."""
    ia = int(np.argmin(np.linalg.norm(c - a, axis=1)))
    ib = int(np.argmin(np.linalg.norm(c - b, axis=1)))
    return c[ia:ib + 1] if ia <= ib else c[ib:ia + 1][::-1]
