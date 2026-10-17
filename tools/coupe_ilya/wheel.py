"""Купе Ильи: колесо в сборе — шина 265/35 R20, диск 20" с пятью сдвоенными спицами, ступица,
гайки, колпачок со знаком, тормозной диск и суппорт.

Координаты колеса: ось вращения +X (наружу от машины), центр в нуле. Только numpy.
Колесо одно на все четыре места (решение для игры) — то же, что найденный предмет car_wheel.
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt

TIRE_R = 0.3468               # 0,254 + 0,35·0,265
TIRE_W = 0.265
RIM_R = 0.254                 # посадочный радиус 20"
SEG = 144                     # деление по окружности


def revolve(profile: list[tuple[float, float]], seg: int = SEG, closed: bool = False, phase: float = 0.0):
    """Профиль (x вдоль оси, r) → тело вращения вокруг X. closed — замкнуть профиль."""
    prof = np.asarray(profile, dtype=float)
    k = len(prof)
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False) + phase
    V = np.zeros((seg * k, 3))
    for i, ang in enumerate(a):
        V[i * k:(i + 1) * k, 0] = prof[:, 0]
        V[i * k:(i + 1) * k, 1] = prof[:, 1] * math.cos(ang)
        V[i * k:(i + 1) * k, 2] = prof[:, 1] * math.sin(ang)
    F = []
    kk = k if closed else k - 1
    for i in range(seg):
        i2 = (i + 1) % seg
        for j in range(kk):
            j2 = (j + 1) % k
            F.append((i * k + j, i * k + j2, i2 * k + j2, i2 * k + j))
    return V, F


def tire():
    """Шина: боковины с выпуклостью, плечи, протектор с четырьмя продольными канавками."""
    hw = TIRE_W / 2
    side = [(0.115, 0.256), (0.124, 0.264), (0.131, 0.278), (0.134, 0.293), (0.132, 0.310), (0.126, 0.325),
            (0.117, 0.336)]
    prof = [(-x, r) for x, r in side]
    # плечо и протектор: канавки на ±0,030 и ±0,072
    tread = []
    xs = np.linspace(-0.108, 0.108, 49)
    for x in xs:
        r = TIRE_R
        for gc in (-0.072, -0.030, 0.030, 0.072):
            d = abs(x - gc)
            if d < 0.0055:
                r = TIRE_R - 0.007 * (1 - (d / 0.0055) ** 4)
        # скругление плеча
        if abs(x) > 0.098:
            r -= (abs(x) - 0.098) ** 2 * 18
        tread.append((x, r))
    prof += [(-0.108, 0.3425)] + tread + [(0.108, 0.3425)]
    prof += [(x, r) for x, r in reversed(side)]
    # внутренняя сторона (к ободу): замыкаем по закраине
    prof += [(0.108, 0.252), (-0.108, 0.252)]
    return revolve(prof, SEG, closed=True)


def rim_barrel(with_face_lip: bool = False):
    """Обод: внутренняя закраина, посадочные полки, ручей; тонкая стенка (обе стороны видны).

    Наружная закраина — часть литого лица диска (wheel_face.py); with_face_lip — для запасного вида без него.
    """
    if with_face_lip:
        outer = [(-0.122, 0.262), (-0.114, 0.255), (-0.092, 0.252), (-0.045, 0.229), (0.030, 0.229),
                 (0.080, 0.252), (0.104, 0.255), (0.111, 0.263), (0.117, 0.267), (0.122, 0.264), (0.121, 0.250)]
        inner = [(0.108, 0.247), (0.078, 0.246), (0.030, 0.223), (-0.045, 0.223), (-0.090, 0.246),
                 (-0.116, 0.249), (-0.124, 0.257)]
    else:
        outer = [(-0.122, 0.262), (-0.114, 0.255), (-0.092, 0.252), (-0.045, 0.229), (0.030, 0.229),
                 (0.080, 0.252), (0.106, 0.255), (0.110, 0.2535)]
        inner = [(0.104, 0.2465), (0.078, 0.246), (0.030, 0.223), (-0.045, 0.223), (-0.090, 0.246),
                 (-0.116, 0.249), (-0.124, 0.257)]
    return revolve(outer + inner, SEG, closed=True)


def spokes(n_pairs: int = 5):
    """Пять пар спиц, сходящихся у ступицы (Y-образные), с вогнутостью к центру."""
    out = []
    for p in range(n_pairs):
        base = p * 2 * math.pi / n_pairs
        for side in (-1, 1):
            t = np.linspace(0, 1, 26)
            r = 0.078 + (0.243 - 0.078) * t
            x = 0.068 + 0.044 * (t ** 0.75) - 0.006 * np.sin(math.pi * t)      # вогнутый профиль спицы
            ang = base + side * np.radians(3.0 + 8.0 * t ** 1.2)              # расходятся к ободу
            P = np.c_[x, r * np.cos(ang), r * np.sin(ang)]
            T = np.gradient(P, axis=0)
            T /= np.linalg.norm(T, axis=1, keepdims=True)
            radial = np.c_[np.zeros_like(r), np.cos(ang), np.sin(ang)]
            tang = np.cross(np.array([1.0, 0, 0]), radial)
            # оси сечения: ширина — по окружности, толщина — по оси колеса (с поправкой на наклон)
            Nn = np.cross(tang, T)
            Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
            w = 0.040 - 0.013 * t
            h = 0.040 - 0.018 * t

            def sec(i, w=w, h=h):
                s = pt.rounded_rect(w[i], h[i], min(w[i], h[i]) * 0.35, 3)
                s[:, 1] -= h[i] * 0.35                                       # лицо спицы — снаружи
                return s
            out.append(pt.loft(P, tang, Nn, sec, cap=True))
    return pt.merge(out)


def hub():
    """Ступица: ровная площадка под гайки и выпуклый колпачок."""
    prof = [(0.040, 0.0), (0.040, 0.090), (0.062, 0.090), (0.070, 0.086), (0.072, 0.040), (0.078, 0.036),
            (0.084, 0.030), (0.088, 0.018), (0.089, 0.0)]
    return revolve(prof, 72, closed=False)


def lug_nuts(n: int = 5, pcd_r: float = 0.0560):
    """Гайки: шестигранник с фасками (вращение шестью гранями) на окружности крепления."""
    prof = [(0.0665, 0.0), (0.0665, 0.0105), (0.073, 0.0110), (0.081, 0.0110), (0.084, 0.0085), (0.0845, 0.0)]
    nut_v, nut_f = revolve(prof, 6, closed=False, phase=math.pi / 6)
    out = []
    for i in range(n):
        a = i * 2 * math.pi / n + math.pi / n
        V = nut_v.copy()
        V[:, 1] += pcd_r * math.cos(a)
        V[:, 2] += pcd_r * math.sin(a)
        out.append((V, nut_f))
    return pt.merge(out)


def brake_disc():
    """Вентилируемый тормозной диск 370 мм с колоколом (два кольца и щель между ними)."""
    outer_ring = [(-0.036, 0.120), (-0.036, 0.185), (-0.024, 0.185), (-0.024, 0.120)]
    inner_ring = [(-0.012, 0.120), (-0.012, 0.185), (0.000, 0.185), (0.000, 0.120)]
    hat = [(0.000, 0.120), (0.010, 0.112), (0.030, 0.100), (0.036, 0.090), (0.036, 0.040), (0.030, 0.040),
           (0.030, 0.088), (0.022, 0.100), (0.004, 0.112), (-0.004, 0.120)]
    a = revolve(outer_ring, SEG, closed=True)
    b = revolve(inner_ring, SEG, closed=True)
    c = revolve(hat, 96, closed=True)
    # лопатки вентиляции между кольцами
    vanes = []
    for i in range(36):
        ang = i * 2 * math.pi / 36
        P = np.array([[-0.018, 0.122 * math.cos(ang), 0.122 * math.sin(ang)],
                      [-0.018, 0.183 * math.cos(ang + 0.12), 0.183 * math.sin(ang + 0.12)]])
        T = P[1] - P[0]
        T /= np.linalg.norm(T)
        U = np.cross(np.array([1.0, 0, 0]), T)
        vanes.append(pt.loft(np.linspace(P[0], P[1], 4), np.broadcast_to(U, (4, 3)),
                             np.broadcast_to(np.array([1.0, 0, 0]), (4, 3)), pt.rounded_rect(0.005, 0.012, 0.002, 2)))
    return pt.merge([a, b, c] + vanes)


def caliper(angle_deg: float = 115.0):
    """Суппорт: скруглённый корпус, охватывающий край диска на дуге ~55°."""
    t = np.linspace(-0.48, 0.48, 18)
    ang = math.radians(angle_deg) + t
    r = 0.168
    P = np.c_[np.full_like(t, -0.018), r * np.cos(ang), r * np.sin(ang)]
    radial = np.c_[np.zeros_like(t), np.cos(ang), np.sin(ang)]
    axial = np.broadcast_to(np.array([1.0, 0, 0]), P.shape)

    def sec(i):
        k = 1.0 - 0.35 * (abs(t[i]) / 0.48) ** 3                          # концы корпуса тоньше
        return pt.rounded_rect(0.072 * k, 0.050, 0.014, 4)
    return pt.loft(P, axial, radial, sec, cap=True)


def center_badge():
    return pt.badge(np.array([0.0893, 0.0, 0.0]), (1, 0, 0), (0, 0, 1), 0.036, depth=0.0025)


FACE_NPZ = r"E:\Models Blender\VEHICLES\Купе Ильи\models\wheel_face_v02.npz"


def wheel_parts(face_npz: str | None = FACE_NPZ) -> list[tuple[str, str, np.ndarray, list]]:
    """Части колеса: (имя, материал, вершины, грани) в осях колеса.

    Лицо диска — литое тело из wheel_face.py (спицы, закраина, ступица одним куском); если файла нет —
    запасной вид: отдельные спицы и ступица.
    """
    import os
    if face_npz and os.path.exists(face_npz):
        z = np.load(face_npz)
        face = [("Rim_Face", "rim_black", z["verts"].astype(float), [tuple(f) for f in z["faces"]])]
        barrel = rim_barrel(False)
    else:
        face = [("Rim_Spokes", "rim_black", *spokes()), ("Rim_Hub", "rim_black", *hub())]
        barrel = rim_barrel(True)
    return [
        ("Tire", "rubber", *tire()),
        ("Rim_Barrel", "rim_black", *barrel),
    ] + face + [
        ("Lug_Nuts", "chrome_dark", *lug_nuts()),
        ("Center_Badge", "chrome", *center_badge()),
        ("Brake_Disc", "brake_steel", *brake_disc()),
        ("Caliper", "caliper", *caliper()),
    ]
