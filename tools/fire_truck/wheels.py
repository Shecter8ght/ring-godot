"""Колёса: шина 11R22.5 с протектором и стальной дисковый обод 22,5″ на 10 шпилек.

Колесо строится осью вдоль Z (revolve: X — радиус, Y — вдоль оси), наружная сторона — +Z;
на машину его кладёт chassis.py.
"""
from __future__ import annotations

import math

import lib
import spec as S
from lib import s3d

R = S.TYRE_D / 2
BEAD_R = 0.2858                # посадочный диаметр 22,5″
HALF_W = S.TYRE_W / 2
PCD = 0.335                    # 10 шпилек по окружности 335 мм
N_STUDS = 10


def tyre():
    """Шина: боковины с выпуклостью, плечо, беговая дорожка; продольные канавки и ламели плеча."""
    hw = HALF_W
    # боковина: у обода — выступающее защитное кольцо, дальше выпуклость и плечо
    side_out = [(BEAD_R, -hw + 0.03), (BEAD_R + 0.030, -hw + 0.010), (0.328, -hw - 0.006), (0.346, -hw - 0.006),
                (0.356, -hw + 0.002), (0.40, -hw - 0.004), (0.47, -hw + 0.004), (R - 0.022, -hw + 0.022), (R, -hw + 0.048)]
    side_in = [(r, -a) for r, a in reversed(side_out)]
    sec = side_out + side_in
    fil_out = [0, 0.006, 0.004, 0.004, 0.006, 0.0, 0.03, 0.02, 0.012]
    t = s3d.revolve("tyre", s3d.poly(sec, fillet=fil_out + list(reversed(fil_out))))
    # продольные канавки протектора
    grooves = []
    for a in (-0.082, -0.028, 0.028, 0.082):
        g = s3d.revolve("groove", s3d.poly([(R - 0.016, a - 0.006), (R + 0.01, a - 0.009), (R + 0.01, a + 0.009),
                                            (R - 0.016, a + 0.006)]))
        grooves.append(g)
    # поперечные ламели по плечам: по 56 на оборот, наискось
    n = 56
    for k in range(n):
        ang = 360.0 * k / n
        for sgn in (-1, 1):
            blade = s3d.box("blade", 0.007, 0.034, 0.045)
            z = sgn * (hw - 0.055)
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            grooves.append(s3d.at(blade, x=(R + 0.005) * c, y=(R + 0.005) * s, z=z - 0.0225,
                                  rz=ang + 90 + sgn * 12))
    for k in range(64):
        ang = 360.0 * (k + 0.5) / 64
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        for z0, z1 in ((-0.072, -0.040), (-0.018, 0.018), (0.040, 0.072)):
            sipe = s3d.box("sipe", 0.0028, 0.022, z1 - z0)
            grooves.append(s3d.at(sipe, x=(R + 0.002) * c, y=(R + 0.002) * s, z=z0, rz=ang + 90))
    s3d.cut(t, grooves)
    lib.rubber(t)
    return t


def rim(dish: float = 0.135):
    """Обод с диском: обод — оборот сечения, диск на `dish` от середины обода к наружной стороне,
    в диске центральное отверстие, 10 отверстий под шпильки и 10 вентиляционных окон."""
    hw = 0.105                      # полуширина обода 8,25″
    r_out = BEAD_R + 0.018
    sec = [(r_out, -hw), (r_out + 0.004, -hw + 0.008), (BEAD_R - 0.004, -hw + 0.016), (BEAD_R - 0.03, -0.02),
           (BEAD_R - 0.03, 0.03), (BEAD_R - 0.004, hw - 0.016), (r_out + 0.004, hw - 0.008), (r_out, hw),
           (r_out - 0.008, hw), (BEAD_R - 0.012, hw - 0.02), (BEAD_R - 0.038, 0.03), (BEAD_R - 0.038, -0.02),
           (BEAD_R - 0.012, -hw + 0.024), (r_out - 0.008, -hw)]
    shell = s3d.revolve("rim", s3d.poly(sec, fillet=[0.004, 0.003, 0.01, 0.01, 0.01, 0.01, 0.003, 0.004,
                                                     0.002, 0.008, 0.008, 0.008, 0.008, 0.002]))
    # наружный край диска заходит в колодец обода на 1 см — сплошное перекрытие для булева
    disc_sec = [(0.11, dish - 0.006), (0.205, dish - 0.006), (0.235, dish - 0.03), (BEAD_R - 0.024, 0.0),
                (BEAD_R - 0.024, -0.012), (0.230, dish - 0.042), (0.205, dish - 0.018), (0.11, dish - 0.018)]
    disc = s3d.revolve("disc", s3d.poly(disc_sec, fillet=[0, 0.01, 0.02, 0.0, 0.0, 0.02, 0.01, 0]))
    s3d.hole(disc, 0.026, on=s3d.ring(N_STUDS, PCD / 2, on=s3d.Frame((0, 0, dish))))
    s3d.hole(disc, 0.065, on=s3d.ring(N_STUDS, 0.218, start=18, on=s3d.Frame((0, 0, dish))))
    s3d.join(shell, disc)
    lib.steel_dark(shell)
    return shell


def valve():
    """Вентиль: латунный стержень с колпачком, торчит из диска между окнами."""
    stem = s3d.cylinder("valve_stem", 0.011, 0.045)
    cap = s3d.at(s3d.cylinder("valve_cap", 0.014, 0.014), z=0.045)
    s3d.join(stem, cap)
    s3d.material(stem, "brass")
    import math as _m
    a = _m.radians(36.0)
    return s3d.at(stem, x=0.245 * _m.cos(a), y=0.245 * _m.sin(a), z=0.10)


def hub(front: bool):
    """Ступица снаружи диска: фланец, шпильки с гайками, колпак (перед) или фланец полуоси (зад)."""
    flange = s3d.cylinder("hub", 0.40 if not front else 0.38, 0.016)
    top = s3d.Frame((0, 0, 0.013))       # гайки и шпильки утоплены во фланец на 3 мм — без касания плоскостями
    nuts = s3d.at(s3d.extrude("nut", s3d.polygon(6, 0.038), 0.026), on=s3d.ring(N_STUDS, PCD / 2, on=top))
    studs = s3d.at(s3d.cylinder("stud", 0.022, 0.05), on=s3d.ring(N_STUDS, PCD / 2, on=top))
    parts = [flange]
    s3d.join(flange, nuts, studs)
    if front:
        cap = s3d.at(s3d.dome("hubcap", 0.20, 0.07), z=0.026)
        boss = s3d.at(s3d.cylinder("hubboss", 0.21, 0.03), z=0.0)
        s3d.join(flange, boss, cap)
    else:
        axle = s3d.at(s3d.cylinder("axleflange", 0.24, 0.045), z=0.012)
        bolts = s3d.at(s3d.extrude("abolt", s3d.polygon(6, 0.024), 0.016),
                       on=s3d.ring(8, 0.09, start=22.5, on=s3d.Frame((0, 0, 0.054))))
        s3d.join(flange, axle, bolts)
    lib.steel_dark(flange)
    return parts[0]


def wheel(name: str, front: bool, outer: bool = True):
    """Колесо целиком: шина, обод, ступица; outer — диском наружу (у спаренного внутреннее колесо развёрнуто)."""
    t = tyre()
    r = rim()
    h = s3d.at(hub(front), z=0.135 - 0.006) if outer else None
    parts = [t, r] + ([h, valve()] if h is not None else [])
    g = s3d.group(name, *parts)
    if not outer:
        s3d.at(g, rx=180)
    return g
