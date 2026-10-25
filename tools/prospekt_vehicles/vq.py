"""Транспорт «Проспекта»: качество сборки — подробная форма (для запекания) или игровая сетка LOD0.

Та же раскладка и те же формулы, меняется только плотность: шаг сетки панелей, число шагов завёрнутой кромки,
деление тел вращения, скругления блоков, шаг накладок вдоль кузова, профиль шины. set_quality("low") подменяет
помощники в модулях генератора (и купе Ильи, откуда они взяты) — вызывать до сборки, обратно — set_quality("high").
"""
from __future__ import annotations

import math
import sys

import numpy as np

Q = dict(name="high", h=1.0, roll=3, seg=96, nr=4, nc=4, strip=0.006, tube_sec=14, tube_samples=40, liner=(64, 12))
LOW = dict(name="low", h=6.0, roll=1, seg=24, nr=1, nc=1, strip=0.06, tube_sec=6, tube_samples=10, liner=(14, 2))
HIGH = dict(Q)
_ORIG: dict = {}


def low() -> bool:
    return Q["name"] == "low"


def _orig(mod, name):
    key = (mod.__name__, name)
    if key not in _ORIG:
        _ORIG[key] = getattr(mod, name)
    return _ORIG[key]


def set_quality(name: str) -> None:
    import engine_bay
    import interior
    import parts as pt
    import wheel
    Q.clear()
    Q.update(LOW if name == "low" else HIGH)
    rb0 = _orig(engine_bay, "rounded_block")
    tube0 = _orig(engine_bay, "tube")
    rev0 = _orig(wheel, "revolve")
    rr0 = _orig(pt, "rounded_rect")
    strip0 = _orig(pt, "strip_on_surface")
    liner0 = _orig(pt, "wheel_liner")

    def rounded_block(c, sx, sy, sz, r, n_r=4):
        return rb0(c, sx, sy, sz, r, min(n_r, Q["nr"]))

    def tube(points, radius, n_sec=14, samples=40):
        return tube0(points, radius, min(n_sec, Q["tube_sec"]), min(samples, Q["tube_samples"]))

    def revolve(profile, seg=96, closed=False, phase=0.0):
        return rev0(profile, seg if seg <= 8 else min(seg, Q["seg"]), closed, phase)

    def rounded_rect(w, h, r, n_corner=4):
        return rr0(w, h, r, min(n_corner, Q["nc"]))

    def strip_on_surface(surf, P, width, thick, lift, r=None):
        if not low():
            return strip0(surf, P, width, thick, lift, r)
        from surface import resample
        length = float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))
        P = resample(P, max(4, int(length / Q["strip"]) + 1))
        Nrm = surf.normal(P)
        T = np.gradient(P, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
        B = np.cross(Nrm, T)
        hw_, ht_ = width / 2, thick / 2
        sec = np.array([(hw_, ht_), (-hw_, ht_), (-hw_, -ht_), (hw_, -ht_)])
        path = P + Nrm * (lift + thick / 2)
        return pt.loft(path, B, Nrm, sec, cap=True)

    def wheel_liner(yc, zc, r=0.405, x_in=0.50, x_out=0.955, phi0=-24.0, phi1=204.0):
        if not low():
            return liner0(yc, zc, r, x_in, x_out, phi0, phi1)
        na, nx = Q["liner"]
        ph = np.radians(np.linspace(phi0, phi1, na))
        xs = np.linspace(x_in, x_out, nx)
        V = np.vstack([np.c_[np.full(len(ph), x), yc + r * np.cos(ph), zc + r * np.sin(ph)] for x in xs])
        n = len(ph)
        F = [(i * n + j + 1, i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1) for i in range(nx - 1) for j in range(n - 1)]
        W = np.vstack([np.c_[np.full(n, x_in), yc + rr * np.cos(ph), zc + rr * np.sin(ph)] for rr in (r, r * 0.55)])
        b = len(V)
        F += [(b + j, b + j + 1, b + n + j + 1, b + n + j) for j in range(n - 1)]
        return np.vstack([V, W]), F

    patches = {
        "rounded_block": rounded_block, "tube": tube, "revolve": revolve,
    }
    for mname in ("carparts", "vbus", "interior", "engine_bay", "wheel"):
        m = sys.modules.get(mname)
        if m is None:
            continue
        for k, fn in patches.items():
            if hasattr(m, k):
                setattr(m, k, fn)
    pt.rounded_rect = rounded_rect
    pt.strip_on_surface = strip_on_surface
    pt.wheel_liner = wheel_liner
    # модули, которые взяли помощники по имени при импорте
    for mname in ("carparts", "vbus"):
        m = sys.modules.get(mname)
        if m is not None and hasattr(m, "rounded_rect"):
            m.rounded_rect = rounded_rect


def tire_profile_low(R: float, W: float, rim_r: float):
    """Профиль шины для игровой сетки: боковина, плечо и протектор без канавок (они — в карте нормалей)."""
    H = R - rim_r
    hw = W / 2
    side = [(0.82, 0.04), (0.97, 0.30), (1.00, 0.52), (0.95, 0.80), (0.86, 0.93)]
    prof = [(-k * hw, rim_r + q * H) for k, q in side]
    prof += [(-0.78 * hw, R - 0.006), (-0.40 * hw, R), (0.40 * hw, R), (0.78 * hw, R - 0.006)]
    prof += [(k * hw, rim_r + q * H) for k, q in reversed(side)]
    prof += [(0.82 * hw, rim_r + 0.004), (-0.82 * hw, rim_r + 0.004)]
    return prof
