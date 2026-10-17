"""Купе Ильи: панели кузова — четырёхсторонние лоскуты на поверхности и завёрнутые кромки.

Лоскут строится по четырём кромкам (лоскут Кунса), внутренние точки ложатся на поверхность
и выравниваются. Кромка панели заворачивается внутрь (радиус r, затем отбортовка вглубь) —
так выглядит настоящий зазор между панелями. Результат — четырёхугольная сетка (OBJ).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from surface import Surface, resample


def coons(bottom: np.ndarray, right: np.ndarray, top: np.ndarray, left: np.ndarray) -> np.ndarray:
    """Сетка [nv, nu, 3]. bottom/top — слева направо (nu), left/right — снизу вверх (nv)."""
    nu, nv = len(bottom), len(left)
    u = np.linspace(0, 1, nu)[None, :, None]
    v = np.linspace(0, 1, nv)[:, None, None]
    P00, P10, P01, P11 = bottom[0], bottom[-1], top[0], top[-1]
    return ((1 - v) * bottom[None] + v * top[None] + (1 - u) * left[:, None] + u * right[:, None]
            - ((1 - u) * (1 - v) * P00 + u * (1 - v) * P10 + (1 - u) * v * P01 + u * v * P11))


def relax(surf: Surface, G: np.ndarray, iters: int = 6, k: float = 0.5) -> np.ndarray:
    """Выровнять шаг сетки внутри (края на месте), каждый раз возвращая точки на поверхность."""
    G = G.copy()
    for _ in range(iters):
        avg = (G[:-2, 1:-1] + G[2:, 1:-1] + G[1:-1, :-2] + G[1:-1, 2:]) / 4
        G[1:-1, 1:-1] += k * (avg - G[1:-1, 1:-1])
        G[1:-1, 1:-1] = surf.project(G[1:-1, 1:-1])
    return G


def boundary_loop(G: np.ndarray) -> np.ndarray:
    """Граница сетки по кругу без повторов: низ →, правый край ↑, верх ←, левый ↓."""
    return np.vstack([G[0, :-1], G[:-1, -1], G[-1, :0:-1], G[:0:-1, 0]])


def loop_frames(surf: Surface, L: np.ndarray, inner_hint: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Нормаль поверхности и направление «наружу из панели» в касательной плоскости."""
    N = surf.normal(L)
    t = np.roll(L, -1, axis=0) - np.roll(L, 1, axis=0)
    T = np.cross(t, N)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    if np.mean(((L - inner_hint) * T).sum(1)) < 0:
        T = -T
    return N, T


def inset_curves(surf: Surface, curves: list[np.ndarray], delta: float) -> list[np.ndarray]:
    """Сдвинуть четыре кромки (низ, право, верх, лево) внутрь панели на delta по поверхности."""
    b, r, t, l = curves
    loop = np.vstack([b[:-1], r[:-1], t[::-1][:-1], l[::-1][:-1]])
    center = loop.mean(0)
    N, T = loop_frames(surf, loop, center)
    # В углах — по биссектрисе, с поправкой на угол
    moved = surf.project(loop - T * delta)
    nb, nr, nt = len(b) - 1, len(r) - 1, len(t) - 1
    B = np.vstack([moved[:nb], moved[nb:nb + 1]])
    R = np.vstack([moved[nb:nb + nr], moved[nb + nr:nb + nr + 1]])
    Tt = np.vstack([moved[nb + nr:nb + nr + nt], moved[(nb + nr + nt) % len(moved):(nb + nr + nt) % len(moved) + 1]])[::-1]
    Lf = np.vstack([moved[nb + nr + nt:], moved[:1]])[::-1]
    return [B, R, Tt, Lf]


class MeshBuilder:
    """Набор объектов с четырёхугольными гранями для OBJ."""

    def __init__(self) -> None:
        self.objects: list[tuple[str, str, np.ndarray, list[tuple[int, ...]]]] = []

    def add(self, name: str, material: str, V: np.ndarray, F: list[tuple[int, ...]]) -> None:
        self.objects.append((name, material, V, F))

    def write_obj(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Купе Ильи — панели (tools/coupe_ilya)"]
        base = 1
        for name, mat, V, F in self.objects:
            lines.append(f"o {name}")
            lines.append(f"usemtl {mat}")
            lines += [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in V]
            lines.append("s 1")
            lines += ["f " + " ".join(str(base + i) for i in f) for f in F]
            base += len(V)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def grid_faces(nv: int, nu: int, offset: int = 0, flip: bool = False) -> list[tuple[int, ...]]:
    F = []
    for i in range(nv - 1):
        for j in range(nu - 1):
            a = offset + i * nu + j
            q = (a, a + 1, a + nu + 1, a + nu)
            F.append(q[::-1] if flip else q)
    return F


def ring_faces(n: int, rings: int, offset: int, flip: bool = False) -> list[tuple[int, ...]]:
    """Грани между соседними замкнутыми кольцами по n точек."""
    F = []
    for k in range(rings - 1):
        for i in range(n):
            a = offset + k * n + i
            b = offset + k * n + (i + 1) % n
            # Обход против соседней грани сетки по общему ребру — нормали в одну сторону
            q = (b, a, a + n, b + n)
            F.append(q[::-1] if flip else q)
    return F


def panel(surf: Surface, curves: list[np.ndarray], nu: int, nv: int, gap: float = 0.004,
          roll_r: float = 0.003, flange: float = 0.012, roll_steps: int = 3,
          relax_iters: int = 6) -> tuple[np.ndarray, list[tuple[int, ...]]]:
    """Панель по четырём кромкам по осевой линии зазора: лоскут + завёрнутая кромка."""
    b, r, t, l = [resample(c, n) for c, n in zip(curves, (nu, nv, nu, nv))]
    b, r, t, l = inset_curves(surf, [b, r, t, l], gap / 2 + roll_r)
    b, r, t, l = [resample(c, n) for c, n in zip((b, r, t, l), (nu, nv, nu, nv))]
    # Углы должны совпадать после сдвига
    r[0], r[-1] = b[-1], t[-1]
    l[0], l[-1] = b[0], t[0]
    G = coons(b, r, t, l)
    G[1:-1, 1:-1] = surf.project(G[1:-1, 1:-1])
    G = relax(surf, G, relax_iters)
    V = [G.reshape(-1, 3)]
    # Ориентация граней — наружу по полю
    c = G[nv // 2, nu // 2]
    n_face = np.cross(G[nv // 2, nu // 2 + 1] - c, G[nv // 2 + 1, nu // 2] - c)
    flip = float(np.dot(n_face, surf.normal(c[None])[0])) < 0
    F = grid_faces(nv, nu, 0, flip)
    # Завёрнутая кромка: кольца от края лоскута вниз-наружу, затем отбортовка
    L = boundary_loop(G)
    N, T = loop_frames(surf, L, G[nv // 2, nu // 2])
    n = len(L)
    rings = []
    for s in range(1, roll_steps + 1):
        th = np.pi / 2 * s / roll_steps
        rings.append(L + roll_r * np.sin(th) * T - roll_r * (1 - np.cos(th)) * N)
    rings.append(L + roll_r * T - (roll_r + flange) * N)
    # Кольцо 0 — сама граница лоскута: индексы её вершин в сетке
    idx = np.arange(nv * nu).reshape(nv, nu)
    loop_idx = np.concatenate([idx[0, :-1], idx[:-1, -1], idx[-1, :0:-1], idx[:0:-1, 0]])
    base = nv * nu
    V.append(np.vstack(rings))
    # Первое кольцо граней: граница сетки → первое кольцо скругления
    for i in range(n):
        a, b2 = loop_idx[i], loop_idx[(i + 1) % n]
        c2, d2 = base + (i + 1) % n, base + i
        q = (b2, a, d2, c2)
        F.append(q if not flip else q[::-1])
    F += ring_faces(n, len(rings), base, flip)
    return np.vstack(V), F
