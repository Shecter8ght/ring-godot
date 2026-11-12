"""АСТЕН-919, клипы рук: чтение полей расстояний (tools/asten919/clips/hand_sdf.py) — numpy, работает и внутри Blender.

    g = Grid.load("static")
    d = g.dist(points_mm)        # (N, 3) в осях исходника, мм → расстояние до поверхности, мм (< 0 — внутри)
"""
from pathlib import Path

import numpy as np

SDF_DIR = Path(__file__).resolve().parents[3] / "_asset_src/asten919/anim/sdf"
FAR = 25.0


class Grid:
    def __init__(self, sdf, h, lo):
        self.sdf = np.asarray(sdf, np.float32)
        self.h = float(h)
        self.lo = np.asarray(lo, np.float64)
        self.n = np.array(self.sdf.shape)

    @classmethod
    def load(cls, name):
        d = np.load(SDF_DIR / f"{name}.npz")
        return cls(d["sdf"], d["h"], d["lo"])

    def dist(self, pts):
        """Трилинейная выборка; за пределами сетки — FAR."""
        p = (np.asarray(pts, np.float64).reshape(-1, 3) - self.lo) / self.h
        ok = np.all((p >= 0) & (p <= self.n - 1.001), axis=1)
        q = np.clip(p, 0, self.n - 1.001)
        i = np.floor(q).astype(int)
        f = (q - i).astype(np.float32)
        s = self.sdf
        x, y, z = i[:, 0], i[:, 1], i[:, 2]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        c00 = s[x, y, z] * (1 - fx) + s[x + 1, y, z] * fx
        c10 = s[x, y + 1, z] * (1 - fx) + s[x + 1, y + 1, z] * fx
        c01 = s[x, y, z + 1] * (1 - fx) + s[x + 1, y, z + 1] * fx
        c11 = s[x, y + 1, z + 1] * (1 - fx) + s[x + 1, y + 1, z + 1] * fx
        out = (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz
        out[~ok] = FAR
        return out

    def grad(self, pts, e=0.3):
        """Направление «наружу» в точках (единичное)."""
        p = np.asarray(pts, np.float64).reshape(-1, 3)
        g = np.stack([self.dist(p + d) - self.dist(p - d) for d in (np.array([e, 0, 0]), np.array([0, e, 0]), np.array([0, 0, e]))], axis=1)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-6)
