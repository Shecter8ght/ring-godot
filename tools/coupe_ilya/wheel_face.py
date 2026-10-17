"""Купе Ильи: лицевая часть литого диска одним телом — Y-образные спицы, закраина, ступица.

Поле расстояний с плавными объединениями (галтели как у отливки) → сетка marching cubes.
Спицы не «приставлены» к ободу: каждая пара растёт из общего ствола у ступицы и вливается
в закраину обода с расширением. Остальной обод (ручей, посадочные полки) — тело вращения в wheel.py.

Запуск (системный Python: numpy, scikit-image, trimesh):
    python -X utf8 tools/coupe_ilya/wheel_face.py [выход.npz] [шаг_м]
Координаты колеса: ось +X наружу, центр в нуле (как wheel.py).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from skimage import measure

sys.path.insert(0, str(Path(__file__).parent))
from fieldcore import smax, smin  # noqa: E402

OUT_DEFAULT = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\models\wheel_face_v02.npz")

N_PAIRS = 5
ARM_SPREAD = math.radians(9.5)      # лучи пары расходятся к ободу на ±9,5°
AXIAL_K = 1.25                      # сечение спицы глубже, чем шире (по оси колеса)
K_SPOKE = 0.010                     # галтель ствол — лучи
K_HUB = 0.012                       # спицы — ступица
K_RIM = 0.016                       # спицы — закраина обода
PCD_R = 0.056                       # окружность крепления (гайки)


def box2(px: np.ndarray, py: np.ndarray, hx: float, hy: float, r: float) -> np.ndarray:
    """Скруглённый прямоугольник в плоскости (x, r) — сечение тела вращения."""
    qx, qy = np.abs(px) - hx + r, np.abs(py) - hy + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def capsule_chain(X, Y, Z, pts: np.ndarray, radii: np.ndarray) -> np.ndarray:
    """Цепочка конусов со скруглением: путь pts (k×3), радиусы по точкам. Ось X сжата (сечение глубже)."""
    d = np.full(X.shape, 1e3, dtype=np.float32)
    Xs = X / AXIAL_K
    for i in range(len(pts) - 1):
        a, b = pts[i].copy(), pts[i + 1].copy()
        a[0] /= AXIAL_K
        b[0] /= AXIAL_K
        ab = b - a
        L2 = float(ab @ ab)
        t = np.clip(((Xs - a[0]) * ab[0] + (Y - a[1]) * ab[1] + (Z - a[2]) * ab[2]) / L2, 0, 1)
        cx, cy, cz = a[0] + t * ab[0], a[1] + t * ab[1], a[2] + t * ab[2]
        rad = radii[i] + t * (radii[i + 1] - radii[i])
        d = np.minimum(d, np.sqrt((Xs - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - rad)
    return d


def spoke_face_x(R: np.ndarray) -> np.ndarray:
    """Плоскость лица спиц по радиусу: повторяет вогнутый профиль (ступица утоплена), на 11 мм над осью спицы."""
    # одна гладкая кривая по всему радиусу (ствол и лучи) — без ступеньки на развилке
    s = np.clip((R - 0.078) / (0.246 - 0.078), 0, 1)
    return 0.080 + 0.034 * s ** 0.85 - 0.004 * np.sin(np.pi * s) + 0.011


def polar_pt(x: float, r: float, ang: float) -> np.ndarray:
    return np.array([x, r * math.cos(ang), r * math.sin(ang)])


def spoke_pair(X, Y, Z, base: float) -> np.ndarray:
    """Ствол от ступицы и два луча к ободу; профиль вогнутый (ступица утоплена)."""
    t = np.linspace(0, 1, 7)
    trunk = np.array([polar_pt(0.080 + 0.010 * s, 0.078 + 0.062 * s, base) for s in t])
    d = capsule_chain(X, Y, Z, trunk, 0.025 - 0.003 * t)
    for side in (-1, 1):
        s = np.linspace(0, 1, 13)
        rr = 0.128 + (0.246 - 0.128) * s
        xx = 0.090 + 0.024 * s ** 0.8 - 0.004 * np.sin(np.pi * s)
        aa = base + side * ARM_SPREAD * s ** 1.15
        arm = np.array([polar_pt(x, r, a) for x, r, a in zip(xx, rr, aa)])
        flare = np.clip((s - 0.80) / 0.20, 0, 1) ** 2
        d = smin(d, capsule_chain(X, Y, Z, arm, 0.0185 - 0.0030 * s + 0.0060 * flare), K_SPOKE)
    return d


def face_field(X, Y, Z) -> np.ndarray:
    R = np.sqrt(Y * Y + Z * Z)
    # закраина обода и внутренняя стенка у лица (с ней сливаются концы спиц)
    lip = box2(X - 0.1165, R - 0.2575, 0.0055, 0.0095, 0.004)
    wall = box2(X - 0.0990, R - 0.2470, 0.0185, 0.0035, 0.0018)
    rim = smin(lip, wall, 0.004)
    # ступица: диск с фаской и выпуклый колпачок
    hub = box2(X - 0.0700, R - 0.047, 0.011, 0.047, 0.008)
    cap = box2(X - 0.0835, R - 0.0165, 0.0060, 0.0165, 0.005)
    hub = smin(hub, cap, 0.006)
    spokes = np.full(X.shape, 1e3, dtype=np.float32)
    for p in range(N_PAIRS):
        spokes = np.minimum(spokes, spoke_pair(X, Y, Z, p * 2 * math.pi / N_PAIRS))
    # лицо спиц срезано гладкой поверхностью по их профилю (обточенный диск) и не выходит за закраину
    spokes = smax(spokes, X - np.minimum(spoke_face_x(R), 0.1185), 0.0035)
    spokes = smax(spokes, 0.060 - X, 0.003)
    body = smin(spokes, hub, K_HUB)
    body = smin(body, rim, K_RIM)
    # гнёзда гаек между парами спиц и центральное отверстие колпачка не нужно (колпачок цельный)
    for p in range(N_PAIRS):
        a = p * 2 * math.pi / N_PAIRS + math.pi / N_PAIRS
        cy, cz = PCD_R * math.cos(a), PCD_R * math.sin(a)
        seat = smax(np.sqrt((Y - cy) ** 2 + (Z - cz) ** 2) - 0.0118, 0.0665 - X, 0.002)
        body = smax(body, -seat, 0.0025)
    return body


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0016
    gx = np.arange(0.046, 0.140 + h / 2, h, dtype=np.float32)
    gy = np.arange(-0.272, 0.272 + h / 2, h, dtype=np.float32)
    F = np.empty((len(gx), len(gy), len(gy)), dtype=np.float32)
    Y, Z = np.meshgrid(gy, gy, indexing="ij")
    for i, x in enumerate(gx):
        F[i] = face_field(np.full_like(Y, x), Y, Z)
    verts, faces, _, _ = measure.marching_cubes(F, level=0.0, spacing=(h, h, h))
    verts += np.array([gx[0], gy[0], gy[0]])
    import trimesh
    mesh = trimesh.Trimesh(verts, faces, process=True)
    mesh.fix_normals()
    print(f"лицо диска: {len(mesh.vertices)} вершин, {len(mesh.faces)} треугольников, "
          f"габарит {mesh.extents.round(4)}, замкнуто {mesh.is_watertight}")
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, verts=np.asarray(mesh.vertices, np.float32), faces=np.asarray(mesh.faces, np.int32))
    print(out)


if __name__ == "__main__":
    main()
