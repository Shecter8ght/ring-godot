"""Транспорт «Проспекта»: повреждения формы — для вариантов «Битый» и «Сгоревший» (только numpy).

Деформации применяются к готовым деталям (вершинам), а не к полю: панели сохраняют зазоры и кромки,
как у настоящей мятой машины. Шум — сглаженный решёточный (повторяемый по зерну), не случайные иглы.
"""
from __future__ import annotations

import math

import numpy as np


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Noise3:
    """Сглаженный решёточный шум: значения в узлах решётки шага scale, между узлами — плавно (квинтика)."""

    def __init__(self, seed: int, size: int = 64) -> None:
        rng = np.random.default_rng(seed)
        self.g = rng.uniform(-1.0, 1.0, (size, size, size))
        self.n = size

    def __call__(self, P: np.ndarray, scale: float) -> np.ndarray:
        q = P / scale + 17.3
        i = np.floor(q).astype(int)
        f = q - i
        u = f * f * f * (f * (f * 6 - 15) + 10)
        n = self.n
        out = np.zeros(len(P))
        for dx in (0, 1):
            wx = u[:, 0] if dx else 1 - u[:, 0]
            for dy in (0, 1):
                wy = u[:, 1] if dy else 1 - u[:, 1]
                for dz in (0, 1):
                    wz = u[:, 2] if dz else 1 - u[:, 2]
                    out += wx * wy * wz * self.g[(i[:, 0] + dx) % n, (i[:, 1] + dy) % n, (i[:, 2] + dz) % n]
        return out

    def fbm(self, P: np.ndarray, scale: float, octaves: int = 3) -> np.ndarray:
        s, a, out, norm = scale, 1.0, np.zeros(len(P)), 0.0
        for k in range(octaves):
            out += a * self(P + k * 3.7, s)
            norm += a
            s *= 0.5
            a *= 0.5
        return out / norm


def vertex_normals(V: np.ndarray, F: list) -> np.ndarray:
    N = np.zeros_like(V)
    for f in F:
        if len(f) < 3:
            continue
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        n = np.cross(b - a, c - a)
        for i in f:
            N[i] += n
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def vertex_normals_fast(V: np.ndarray, F: list) -> np.ndarray:
    """То же, векторно: многоугольники разбиты веером на треугольники."""
    tris = []
    for f in F:
        for k in range(1, len(f) - 1):
            tris.append((f[0], f[k], f[k + 1]))
    if not tris:
        return np.zeros_like(V)
    T = np.array(tris)
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, T[:, k], n)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


# --- удар спереди ---------------------------------------------------------------------------------

def crash_front(V: np.ndarray, spec: dict, depth: float, side: float, noise: Noise3, amp: float = 0.025) -> np.ndarray:
    """Лобовой удар со смещением к борту side (+1 — левый): перёд вдавлен назад, сильнее со стороны удара,
    смятие гаснет к стойке A; поверх — мятость шумом (складки металла)."""
    s = spec
    y_n = float(s["front"][len(s["front"]) // 2][1])
    y_stop = s["lay"]["door_f_y"] - 0.05
    hw = s["width"] / 2
    u = np.clip((V[:, 0] * side + hw) / (2 * hw), 0, 1)          # 0 — дальний борт, 1 — борт удара
    across = 0.35 + 0.65 * u ** 1.6
    w = 1.0 - smoothstep(y_n, y_stop, V[:, 1])                    # 1 у носа → 0 у стойки A
    push = depth * across * w ** 1.4
    out = V.copy()
    out[:, 1] += push
    # металл, сжатый вдоль, выпучивается вверх и вбок складками
    fold = noise.fbm(V * np.array([1.0, 1.8, 1.0]), 0.26, 2)
    out[:, 2] += amp * fold * w * across
    out[:, 0] += amp * 0.6 * noise.fbm(V + 5.0, 0.15, 2) * w * across
    return out


def hood_buckle(V: np.ndarray, y0: float, y1: float, height: float, side: float, hw: float) -> np.ndarray:
    """Капот «домиком»: поперечная складка вверх между y0 и y1, выше со стороны удара."""
    t = np.clip((V[:, 1] - y0) / (y1 - y0), 0, 1)
    tent = np.sin(math.pi * t) ** 1.5
    lean = 0.6 + 0.4 * np.clip((V[:, 0] * side + hw) / (2 * hw), 0, 1)
    out = V.copy()
    out[:, 2] += height * tent * lean
    return out


def droop(V: np.ndarray, x0: float, side: float, amount: float, y_lim: float | None = None) -> np.ndarray:
    """Оторванный угол бампера провис: к борту side за x0 опускается по квадрату."""
    d = np.clip(V[:, 0] * side - x0, 0, None)
    out = V.copy()
    k = amount * (d / max(1e-3, (np.abs(V[:, 0]).max() - x0))) ** 2
    out[:, 2] -= k
    out[:, 1] -= k * 0.35
    return out


def dent(V: np.ndarray, center, radius: float, depth: float, direction) -> np.ndarray:
    """Вмятина: точки в радиусе уходят по direction (внутрь), с плавным краем и пологой серединой."""
    c = np.asarray(center, float)
    d = np.linalg.norm(V - c, axis=1)
    w = (1 - smoothstep(0.0, radius, d)) ** 1.3
    return V + np.outer(w * depth, np.asarray(direction, float))


def sag(V: np.ndarray, center_xy, radius: float, depth: float) -> np.ndarray:
    """Просадка вниз пятном (крыша после пожара, «лужей» по центру)."""
    c = np.asarray(center_xy, float)
    d = np.linalg.norm((V[:, :2] - c) / np.array([radius * 0.75, radius]), axis=1)
    w = np.clip(1 - d ** 2, 0, None) ** 1.5
    out = V.copy()
    out[:, 2] -= depth * w
    return out


def warp(V: np.ndarray, noise: Noise3, amp: float, scale: float, normals: np.ndarray) -> np.ndarray:
    """Волнистость листа (нагрев): сдвиг вдоль нормали плавным шумом."""
    return V + normals * (amp * noise.fbm(V, scale, 2))[:, None]


def melt(V: np.ndarray, noise: Noise3, z_top: float, amount: float) -> np.ndarray:
    """Пластик потёк: точки опускаются тем сильнее, чем ниже от z_top и чем дальше от середины, с шумом."""
    out = V.copy()
    h = np.clip(z_top - V[:, 2], 0, None)
    k = amount * (0.4 + 0.6 * smoothstep(0.0, 0.25, h)) * (0.6 + 0.4 * (noise(V, 0.12) + 1) / 2)
    out[:, 2] -= k * (0.5 + 0.5 * np.abs(V[:, 0]) / max(np.abs(V[:, 0]).max(), 1e-3))
    return out


# --- стекло ---------------------------------------------------------------------------------------

def shards_along(P: np.ndarray, inward: np.ndarray, normal: np.ndarray, seed: int, max_len: float = 0.08,
                 thick: float = 0.004):
    """Осколки, оставшиеся в рамке разбитого окна: зубья вдоль кромки, острые, неровной длины."""
    rng = np.random.default_rng(seed)
    n = len(P)
    V, F = [], []
    i = 0
    while i < n - 2:
        step = int(rng.integers(2, 6))
        j = min(i + step, n - 1)
        a, b = P[i], P[j]
        ln = max_len * rng.uniform(0.15, 1.0) ** 1.5
        tip = (a + b) / 2 + inward[(i + j) // 2] * ln + (b - a) * rng.uniform(-0.4, 0.4)
        nn = normal[(i + j) // 2] * thick / 2
        base = len(V)
        V += [a - nn, b - nn, tip - nn, a + nn, b + nn, tip + nn]
        F += [(base, base + 1, base + 2), (base + 3, base + 5, base + 4), (base, base + 3, base + 4, base + 1),
              (base + 1, base + 4, base + 5, base + 2), (base + 2, base + 5, base + 3, base)]
        i = j
    return np.array(V), F


def crack_glass(V: np.ndarray, center, radius: float, depth: float, direction) -> np.ndarray:
    """Лобовое после удара головой/камнем: стекло прогнулось пятном (трещины — отделкой)."""
    return dent(V, center, radius, depth, direction)


# --- колёса -----------------------------------------------------------------------------------------

def flat_tire(V: np.ndarray, R: float, drop: float) -> np.ndarray:
    """Спущенная шина (оси колеса: X — ось, Z — вверх): низ сплющен на drop, боковины выпучены."""
    out = V.copy()
    z_floor = -R + drop
    below = out[:, 2] < z_floor
    h = np.clip(z_floor - V[:, 2], 0, None)
    out[below, 2] = z_floor - h[below] * 0.08
    # выпучивание боковин у пятна
    r = np.sqrt(V[:, 1] ** 2 + V[:, 2] ** 2)
    low = smoothstep(-0.2 * R, -R, V[:, 2])
    bulge = drop * 0.6 * low * smoothstep(0.55 * R, 0.85 * R, r)
    out[:, 0] += np.sign(V[:, 0]) * bulge
    return out
