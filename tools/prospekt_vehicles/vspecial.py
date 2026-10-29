"""Транспорт «Проспекта», партия 2: навесное такси и полиции на принятый седан — только numpy (форма и игровая сетка).

Плафон «шашечки» и балка маячков ставятся по крыше той сборки, в которую идут: форма (build_special.py, крыша из
сохранённого .blend седана) и игровая сетка (game_kit.py, крыша из деталей того же качества). Одни и те же функции —
одинаковое положение в подробной форме, LOD0 для Painter и в источнике запекания.
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt
from engine_bay import rounded_block, tube


def roof_top(P: np.ndarray) -> tuple[float, float, float]:
    """Верх крыши по вершинам детали Roof (оси машины): середина по длине (y), высота там (z), полуширина плоской части."""
    yc = float(np.median(P[:, 1]))
    mid = P[np.abs(P[:, 1] - yc) < 0.12]
    z = float(mid[np.abs(mid[:, 0]) < 0.25][:, 2].max())
    flat = mid[mid[:, 2] > z - 0.03]
    return yc, z, float(np.abs(flat[:, 0]).max())


def roof_z(P: np.ndarray, y: float) -> float:
    """Верх крыши по середине ширины в сечении y."""
    near = P[(np.abs(P[:, 1] - y) < 0.05) & (np.abs(P[:, 0]) < 0.15)]
    return float(near[:, 2].max())


def taper(mesh, k_top: float, z0: float, z1: float):
    """Сужение по высоте вдоль Y (трапеция плафона): у низа ×1, у верха ×k_top."""
    V, F = mesh
    V = np.asarray(V, float).copy()
    t = np.clip((V[:, 2] - z0) / (z1 - z0), 0.0, 1.0)
    cy = (V[:, 1].min() + V[:, 1].max()) / 2
    V[:, 1] = cy + (V[:, 1] - cy) * (1.0 - (1.0 - k_top) * t)
    return V, F


def _knock(mesh, yc: float, z: float):
    """Сбитый плафон: опрокинулся назад через заднее ребро низа, развёрнут на 28° и сдвинут — лежит на крыше."""
    V, F = mesh
    p = np.array([0.0, yc + 0.075, z + 0.022])
    a, b = math.radians(-90.0), math.radians(28.0)
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    rz = np.array([[math.cos(b), -math.sin(b), 0], [math.sin(b), math.cos(b), 0], [0, 0, 1]])
    return (np.asarray(V, float) - p) @ (rz @ rx).T + p + np.array([0.06, 0.04, 0.0]), F


def taxi(yc: float, z: float, half: float, knocked: bool = False) -> list:
    """Плафон «шашечки»: трапеция 0,54 × 0,15 × 0,15 м поперёк крыши, торцы скруглены, четыре резиновые лапки-магнита,
    провод по крыше к стойке водителя. knocked — у битой: плафон опрокинут, провод оборван."""
    zb = z + 0.022
    body = taper(rounded_block((0.0, yc, zb + 0.075), 0.54, 0.15, 0.15, 0.03), 0.62, zb, zb + 0.15)
    feet = pt.merge([rounded_block((sx * 0.20, yc + sy * 0.045, z + 0.010), 0.07, 0.05, 0.022, 0.008)
                     for sx in (1, -1) for sy in (1, -1)])
    if knocked:
        return [("Taxi_Sign", "sign_plastic", _knock(body, yc, z)), ("Taxi_Sign_Feet", "rubber", _knock(feet, yc, z))]
    wire = tube([(0.27, yc, zb + 0.03), (0.32, yc - 0.05, z + 0.01), (half - 0.05, yc - 0.20, z - 0.005),
                 (half + 0.06, yc - 0.30, z - 0.06)], 0.0035, 6, 16)
    return [("Taxi_Sign", "sign_plastic", body), ("Taxi_Sign_Feet", "rubber", feet), ("Taxi_Sign_Wire", "trim_black", wire)]


def police(yc: float, z: float, half: float, ant: tuple[float, float]) -> list:
    """Балка маячков 1,10 × 0,28 × 0,13 м: основание, колпаки синий (слева, +X — сторона водителя) и красный,
    громкоговоритель между ними; два кронштейна поперёк крыши с крючками за проёмы дверей; антенна рации на крыше
    за балкой (ant — y, z её основания)."""
    zb = z + 0.045
    base = rounded_block((0.0, yc, zb + 0.025), 1.10, 0.28, 0.05, 0.02)
    lens_l = rounded_block((0.30, yc, zb + 0.090), 0.46, 0.25, 0.09, 0.035)
    lens_r = rounded_block((-0.30, yc, zb + 0.090), 0.46, 0.25, 0.09, 0.035)
    spk = rounded_block((0.0, yc - 0.01, zb + 0.085), 0.13, 0.22, 0.08, 0.025)
    brackets = []
    for sy in (-0.09, 0.09):
        brackets.append(rounded_block((0.0, yc + sy, z + 0.018), 2 * half - 0.10, 0.035, 0.012, 0.004))
        for sx in (1, -1):
            brackets.append(rounded_block((sx * 0.40, yc + sy, z + 0.032), 0.05, 0.05, 0.03, 0.01))
            brackets.append(tube([(sx * (half - 0.05), yc + sy, z + 0.018), (sx * (half + 0.02), yc + sy, z - 0.02),
                                  (sx * (half + 0.03), yc + sy, z - 0.10)], 0.006, 6, 10))
    ty, tz = ant
    antenna = pt.merge([rounded_block((0.0, ty, tz + 0.010), 0.06, 0.06, 0.022, 0.01),
                        tube([(0.0, ty, tz + 0.02), (0.0, ty + 0.01, tz + 0.70)], 0.0025, 6, 4)])
    return [("Police_Bar_Base", "trim_black", base), ("Police_Bar_Lens_L", "lamp_blue", lens_l),
            ("Police_Bar_Lens_R", "lamp_red", lens_r), ("Police_Bar_Speaker", "trim_black", spk),
            ("Police_Bar_Brackets", "steel_dark", pt.merge(brackets)), ("Police_Antenna", "trim_black", antenna)]


def accessories(kind: str, roof: np.ndarray, knocked: bool = False) -> list:
    """Навесное по вершинам крыши (оси машины): список (имя, материал, (V, F))."""
    yc, z, half = roof_top(roof)
    if kind == "taxi":
        return taxi(yc, z, half, knocked)
    return police(yc - 0.10, z, half, (yc + 0.40, roof_z(roof, yc + 0.40)))


def add_to_kit(kit: list, kind: str, knocked: bool = False) -> list:
    """Детали машины (имя, материал, V, F, узел) + навесное на крыше этой же сборки."""
    roof = np.vstack([np.asarray(V, float) for n, _, V, _, _ in kit if n == "Roof"])
    return kit + [(n, m, V, F, "body") for n, m, (V, F) in accessories(kind, roof, knocked)]
