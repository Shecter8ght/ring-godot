"""Купе Ильи: салон в общих чертах — то, что видно сквозь стёкла и на снимках.

Руль слева (+X), 2+2 места. Экраны приборов и центральный — в двух видах: светятся, когда
аккумулятор поставлен (заказ: «загорается приборная панель»), и тёмные без него.
Формы — скруглённые блоки и сечения по профилю; только numpy.
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt
from engine_bay import rounded_block, tube


def rot(V: np.ndarray, rx: float = 0.0, ry: float = 0.0, rz: float = 0.0, about=(0, 0, 0)) -> np.ndarray:
    a = np.asarray(about, float)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return (V - a) @ (Rz @ Ry @ Rx).T + a


def seat(x: float, y: float, z: float, width: float = 0.52, back_h: float = 0.62, tilt: float = 0.36, rear: bool = False):
    """Кресло: подушка с боковыми валиками, спинка с наклоном и валиками, подголовник."""
    parts = []
    cush = rounded_block((x, y, z), width, 0.52, 0.12, 0.05)
    parts.append(cush)
    for s in (-1, 1):
        parts.append(rounded_block((x + s * (width / 2 - 0.05), y, z + 0.05), 0.10, 0.50, 0.12, 0.045))
    bz = z + 0.06 + back_h / 2
    by = y + 0.24
    back = rounded_block((x, by, bz), width, 0.12, back_h, 0.05)
    back = (rot(back[0], rx=-tilt, about=(x, by, z + 0.06)), back[1])
    parts.append(back)
    for s in (-1, 1):
        b = rounded_block((x + s * (width / 2 - 0.05), by - 0.04, bz - 0.05), 0.10, 0.12, back_h * 0.75, 0.045)
        parts.append((rot(b[0], rx=-tilt, about=(x, by, z + 0.06)), b[1]))
    if not rear:
        hr = rounded_block((x, by + 0.02, z + 0.06 + back_h + 0.10), width * 0.55, 0.10, 0.20, 0.045)
        parts.append((rot(hr[0], rx=-tilt, about=(x, by, z + 0.06)), hr[1]))
    return pt.merge(parts)


def dashboard():
    """Торпедо: сечение по профилю (верх к стеклу, лицо к салону), вдоль всей ширины; дефлекторы."""
    xs = np.linspace(-0.74, 0.74, 60)
    # профиль в плоскости YZ: от основания лобового стекла по верху вниз к коленям
    prof = np.array([(-0.86, 1.005), (-0.70, 1.010), (-0.56, 1.000), (-0.48, 0.975), (-0.45, 0.93),
                     (-0.47, 0.85), (-0.52, 0.72), (-0.56, 0.62), (-0.62, 0.58), (-0.80, 0.58)])
    prof = pt.spline2d(prof, 40)
    V, F = [], []
    n = len(prof)
    for i, x in enumerate(xs):
        k = 1.0 - 0.10 * (abs(x) / 0.74) ** 4                     # к краям торпедо чуть уже
        V.append(np.c_[np.full(n, x), -0.86 + (prof[:, 0] + 0.86) * k, prof[:, 1]])
    V = np.vstack(V)
    F = [(i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j) for i in range(len(xs) - 1) for j in range(n - 1)]
    vents = []
    from wheel import revolve
    for vx in (-0.62, -0.20, 0.20, 0.62):
        v, f = revolve([(0.0, 0.0), (0.0, 0.040), (0.010, 0.046), (0.016, 0.046), (0.016, 0.035), (0.004, 0.030),
                        (0.004, 0.0)], 32, closed=False)
        v = v[:, [1, 0, 2]] * np.array([1, -1, 1])                # ось — вдоль машины, к салону
        v += np.array([vx, -0.462, 0.905])
        vents.append((v, f))
    return (V, F), pt.merge(vents)


def screens():
    """Приборный экран за рулём и вертикальный центральный (лица — отдельно, для свечения)."""
    cl_c = np.array([0.38, -0.53, 1.005])
    ce_c = np.array([0.0, -0.50, 0.80])
    frames = [rounded_block(cl_c, 0.34, 0.02, 0.12, 0.008), rounded_block(ce_c, 0.20, 0.02, 0.28, 0.008)]
    faces = [rounded_block(cl_c + np.array([0, 0.011, 0]), 0.32, 0.002, 0.105, 0.004),
             rounded_block(ce_c + np.array([0, 0.011, 0]), 0.185, 0.002, 0.265, 0.004)]
    fr = pt.merge(frames)
    fr = (rot(fr[0], rx=0.12, about=(0, -0.52, 0.9)), fr[1])
    fc = pt.merge(faces)
    fc = (rot(fc[0], rx=0.12, about=(0, -0.52, 0.9)), fc[1])
    return fr, fc


def steering_wheel(x: float = 0.38, y: float = -0.36, z: float = 0.93, tilt: float = 0.40):
    """Руль: обод (тор), три спицы, ступица со знаком, кожух колонки."""
    from wheel import revolve
    R, r = 0.185, 0.017
    ang = np.linspace(0, 2 * math.pi, 18, endpoint=False)
    prof = [(r * math.cos(a), R + r * math.sin(a)) for a in ang]
    rim = revolve(prof, 64, closed=True)                          # ось вращения — X (потом развернём)
    hub = rounded_block((0, 0, 0), 0.045, 0.11, 0.11, 0.035)
    spokes = [rounded_block((0, 0, -0.10), 0.025, 0.05, 0.17, 0.012),
              rounded_block((0, -0.10, 0.0), 0.025, 0.17, 0.045, 0.012),
              rounded_block((0, 0.10, 0.0), 0.025, 0.17, 0.045, 0.012)]
    sw = pt.merge([rim, hub] + spokes)
    V = sw[0][:, [1, 0, 2]]                                       # ось руля — вдоль Y
    V = rot(V, rx=tilt)
    V += np.array([x, y, z])
    column = rounded_block((x, y - 0.14, z - 0.06), 0.08, 0.20, 0.08, 0.03)
    column = (rot(column[0], rx=tilt, about=(x, y, z)), column[1])
    badge = pt.badge(np.array([x, y + 0.024 * math.cos(tilt), z + 0.024 * math.sin(tilt)]),
                     (0, math.cos(tilt), math.sin(tilt)), (0, -math.sin(tilt), math.cos(tilt)), 0.045, depth=0.003)
    return pt.merge([(V, sw[1]), column]), badge


def console():
    """Центральный тоннель с подлокотником."""
    return pt.merge([rounded_block((0.0, 0.02, 0.44), 0.22, 1.00, 0.28, 0.05),
                     rounded_block((0.0, 0.42, 0.61), 0.20, 0.34, 0.07, 0.03),
                     rounded_block((0.0, -0.32, 0.62), 0.16, 0.30, 0.04, 0.015)])


def door_cards():
    """Обивка дверей: плита по внутренней стороне двери с подлокотником и карманом."""
    parts = []
    for s in (1, -1):
        parts.append(rounded_block((s * 0.79, -0.05, 0.69), 0.05, 1.25, 0.56, 0.02))
        parts.append(rounded_block((s * 0.75, 0.05, 0.70), 0.07, 0.60, 0.05, 0.02))
        parts.append(rounded_block((s * 0.775, -0.35, 0.48), 0.05, 0.45, 0.12, 0.02))
        parts.append(rounded_block((s * 0.76, 0.95, 0.66), 0.07, 0.55, 0.50, 0.03))    # задние боковины
    return pt.merge(parts)


def floor():
    return rounded_block((0.0, 0.25, 0.27), 1.50, 2.20, 0.03, 0.01)


def headliner(surf, roof_mesh):
    """Потолок: панель крыши, утопленная внутрь на 3 см."""
    V, F = roof_mesh
    nrm = surf.normal(V)
    return V - nrm * 0.03, [f[::-1] for f in F]


def interior_parts():
    seats = pt.merge([seat(0.37, 0.18, 0.47), seat(-0.37, 0.18, 0.47),
                      seat(0.33, 0.98, 0.42, width=0.48, back_h=0.52, tilt=0.30, rear=True),
                      seat(-0.33, 0.98, 0.42, width=0.48, back_h=0.52, tilt=0.30, rear=True)])
    dash, vents = dashboard()
    fr, faces = screens()
    sw, sw_badge = steering_wheel()
    return {
        "Seats": ("leather", seats),
        "Dashboard": ("interior_soft", dash),
        "Dash_Vents": ("chrome_dark", vents),
        "Screens_Frame": ("trim_gloss_black", fr),
        "Steering_Wheel": ("leather", sw),
        "Steering_Badge": ("chrome", sw_badge),
        "Console": ("interior_soft", console()),
        "Door_Cards": ("interior_soft", door_cards()),
        "Floor": ("carpet", floor()),
        "_screen_faces": faces,
    }
