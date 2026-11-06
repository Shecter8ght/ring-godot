# -*- coding: utf-8 -*-
"""Карта «Вертолёт» — предложение v05 «плотина над долиной» (Claude, 2026-11-06, по замыслу владельца), на обсуждение.

Речка с гор на юге упирается в арочную плотину 260 м и стоит высоким водохранилищем; ниже плотины — долина с озером и вся
игровая часть: с лесопилки, санатория, из посёлка плотина возвышается над головой. Вода из озера уходит через низкий
водослив на северном конце. Машзал и ОРУ — у подножия, на уровне озера; гребень — высота над всей долиной.
  python -X utf8 tools/mission_helicopter_v05.py [plans] [data]
plans — схемы и расчёты (пути, уход к выходам, окна вертолёта, пустые отрезки, углы на плотину) → docs/plans/
mission_helicopter_v05_*.png; data — серый стенд tools/heli_study.tscn: data/terrain/heli_v05_*, data/blockouts/heli_v05*.json.
Рельеф — аналитический набросок для замеров, не готовая форма; сюжет и места — предложения (docs/design/mission_helicopter.md).
"""
import json
import math
import sys
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / 'docs' / 'plans'
FONT = 'C:/Windows/Fonts/arial.ttf'
BOLD = 'C:/Windows/Fonts/arialbd.ttf'
INK = '#24372e'
MUTED = '#52685b'
PAPER = '#f4f1e7'
ORANGE = '#bd642f'
RED = '#a8322a'
ROAD = '#6f7468'
TRAIL = '#f1e2b8'
EXTRA = (150, 95, 55)

SPRINT_MIX = 4.4      # бег с передышками без груза: 5,2 м/с, спринт ~36 с, затем шаг до порога 25 %
WALK = 1.82
HELI_SPEED = 42.0     # ~150 км/ч
MANPADS_RANGE = 1000.0
STATIC_RANGE = 2500.0
LIFT_SEC = 75.0       # лифт в теле плотины, 260 м

VIS = (-1000.0, 1000.0, -1500.0, 1500.0)      # видимый мир 2 × 3 км
WALKABLE = (-650.0, 650.0, -1050.0, 560.0)    # где ходят: долина с озером, плотина и её гребень — 1,3 × 1,6 км
CELL = 2.0
STEP = 4.0                                     # шаг карты высот стенда
Y_OFFSET = 300.0                               # стенд: озеро на 300 м мира
CREST = 260.0                                  # гребень над уровнем озера
RES_LEVEL = 255.0                              # водохранилище выше плотины
FOOT = -8.0                                    # подошва плотины у русла
WEIR_Z = -745.0                                # водослив на северном конце озера
TOE_Z = 365.0                                  # озеро кончается у машзала

# Нижнее озеро (z, x): от водослива до подножия плотины.
WEST = np.array([(-745, -70), (-650, -140), (-520, -190), (-350, -215), (-200, -225), (-60, -200), (60, -215),
                 (150, -265), (230, -250), (300, -170), (365, -90)], float)
EAST = np.array([(-745, 70), (-640, 150), (-480, 210), (-300, 230), (-120, 215), (20, 200), (100, 240),
                 (200, 235), (280, 175), (365, 90)], float)
# Арка: верховая грань выпукла к водохранилищу (на юг), центр кривизны — в долине.
APEX = 480.0
CHORD_HALF = 245.0
SAG = 50.0
R_ARC = (CHORD_HALF ** 2 + SAG ** 2) / (2 * SAG)
CZ = APEX - R_ARC
RES_AXIS = np.array([(430, 0), (650, -30), (800, 20), (1000, -20), (1200, 30), (1500, 0)], float)
RES_HALF = np.array([(430, 240), (600, 270), (800, 250), (1000, 220), (1300, 200), (1500, 180)], float)
NORTH_RIVER = np.array([(-1500, 30), (-1300, -20), (-1100, 10), (-900, -15), (-760, 0)], float)

# Места (x, z, высота от уровня озера)
VILLAGE = (-380, -250, 30)
SAWMILL = (-320, 160, 12)
WAREHOUSE = (-480, -650, 150)
SAN = (380, 80, 60)
S1 = (320, -50, 55)
S2 = (470, 170, 70)
AD = (420, 380, 300)
HALL = (0, 395, 2)
YARD = (-110, 340, 3)
SWITCH = (140, 330, 6)
SERVICE = (250, 290, 20)
A = (-640, -880, 200)
B = (600, -850, 200)
N = (0, -1040, -10)
W = (-600, 0, 150)
D = (620, 280, 220)
C = (-275, 415, 260.3)

PADS = [
    (VILLAGE[0], VILLAGE[1], VILLAGE[2], 80, 160),
    (SAWMILL[0], SAWMILL[1], SAWMILL[2], 60, 120),
    (WAREHOUSE[0], WAREHOUSE[1], WAREHOUSE[2], 70, 140),
    (SAN[0], SAN[1], SAN[2], 60, 110),
    (S1[0], S1[1], S1[2], 40, 85),
    (S2[0], S2[1], S2[2], 40, 85),
    (245, 100, 1.2, 12, 35),                     # пляж под санаторием
    (AD[0], AD[1], AD[2], 60, 110),
    (0, 330, 3, 150, 230),                       # ровная терраса у подножия: машзал, двор, ОРУ, завод — плотина видна до основания
    (YARD[0], YARD[1], YARD[2], 30, 60),
    (SWITCH[0], SWITCH[1], SWITCH[2], 40, 70),
    (SERVICE[0], SERVICE[1], SERVICE[2], 30, 60),
    (-225, 305, 6, 40, 80),                      # площадка бетонного завода у подножия
    (-245, 398, 8, 25, 55),                      # вагон-городок строителей
    (-262, 420, 260.3, 18, 45),                  # полки на уровне гребня у примыканий (низовая сторона концов арки)
    (262, 420, 260.3, 18, 45),
]
# Долины и врезанные дороги (x, z, высота дна), полуширина, крутизна бортов.
VALLEYS = [
    ([(-200, -650, 3), (-400, -720, 120), (A[0], A[1], A[2]), (-800, -1200, 330)], 30, 0.9),
    ([(200, -600, 3), (420, -700, 120), (B[0], B[1], B[2]), (800, -1200, 330)], 30, 0.9),
    ([(-225, -250, 0), (VILLAGE[0], VILLAGE[1], VILLAGE[2]), (-560, -300, 180), (-800, -350, 400)], 22, 1.0),
    ([(-300, 60, 10), (-460, 30, 90), (W[0], W[1], W[2]), (-800, -30, 330)], 25, 1.0),
    ([(SAN[0], SAN[1] + 70, 60), (480, 230, 130), (D[0], D[1], D[2]), (800, 330, 330)], 25, 1.0),
    # серпантины с долины на полки у гребня (в стенде — вырезанные в склоне дороги)
    ([(-320, 200, 12), (-360, 300, 90), (-330, 370, 170), (-262, 420, 260.3)], 6, 1.3),
    ([(380, 150, 60), (380, 270, 130), (330, 360, 200), (262, 420, 260.3)], 6, 1.3),
    ([(262, 420, 260.3), (340, 400, 285), (AD[0], AD[1], AD[2])], 8, 1.2),
]


def clip(a, lo=0.0, hi=1.0):
    return np.clip(a, lo, hi)


def smooth(e0, e1, x):
    t = clip((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def arc_z(x, r=R_ARC):
    """Верховая грань (r = R) или любая другая дуга того же центра: z точки на дуге радиуса r."""
    x = np.asarray(x, float)
    return CZ + np.sqrt(np.maximum(r ** 2 - x ** 2, 0.0))


def mount_of(axm):
    return 350 * clip((axm - 260) / 440) ** 1.35 + 650 * clip((axm - 700) / 300) ** 1.6


def heights(X, Z):
    """Высоты от уровня озера; маски нижнего озера и водохранилища."""
    ax = np.abs(X)
    wig = (45 * np.sin(Z / 260 + 0.7 + np.sign(X) * 1.3) + 25 * np.sin(Z / 110 + np.sign(X))) * (1 - 0.7 * smooth(300, 470, Z))
    # долина сужается к плотине: борта у арки поднимаются на высоту гребня в 200 м от русла
    s = 1 + 1.6 * smooth(220, 470, np.minimum(Z, 480.0))
    mount = mount_of(np.maximum(ax + wig, 0) * s)
    mount = mount + (22 * np.sin(X / 83 + Z / 61) + 14 * np.sin(X / 41 - Z / 57)) * clip(mount / 250)
    noise = 6 * np.sin(X / 37 + Z / 53) + 4 * np.sin(X / 19 - Z / 27) + 10 * np.sin(X / 151 + Z / 97)
    xw = np.interp(Z, WEST[:, 0], WEST[:, 1])
    xe = np.interp(Z, EAST[:, 0], EAST[:, 1])
    d = np.where(X < xw, xw - X, np.where(X > xe, X - xe, 0.0))
    below = Z < WEIR_Z
    xrn = np.interp(Z, NORTH_RIVER[:, 0], NORTH_RIVER[:, 1])
    d = np.where(below, np.maximum(np.abs(X - xrn) - 13, 0), d)
    toe = Z > TOE_Z
    d = np.where(toe, np.maximum(ax - 30, 0), d)
    base = np.where(below, -8 - (WEIR_Z - Z) * 0.012, np.where(toe, 2.0, 0.0))
    near = 6 * clip(d / 30) + 0.06 * d
    hn = np.maximum(base + near, mount) + noise * clip(d / 80)
    upstream = Z > arc_z(np.minimum(ax, CHORD_HALF))
    rr = np.abs(X - np.interp(Z, RES_AXIS[:, 0], RES_AXIS[:, 1]))
    wr = np.interp(Z, RES_HALF[:, 0], RES_HALF[:, 1])
    hu = np.maximum(RES_LEVEL + 7 + 1.6 * (rr - wr), mount + noise * clip((rr - wr) / 80))
    res = upstream & (rr < wr)
    hu = np.where(res, 150.0, hu)
    h = np.where(upstream, hu, hn)
    for pts, w0, slope in VALLEYS:
        for a, b in zip(pts, pts[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            t = clip(((X - a[0]) * dx + (Z - a[1]) * dz) / (dx * dx + dz * dz))
            dist = np.hypot(X - a[0] - t * dx, Z - a[1] - t * dz)
            carve = a[2] + t * (b[2] - a[2]) + slope * np.maximum(dist - w0, 0)
            h = np.where(res, h, np.minimum(h, carve))
    for px, pz, py, r0, r1 in PADS:
        w = 1 - smooth(r0, r1, np.hypot(X - px, Z - pz))
        h = np.where(res, h, h * (1 - w) + py * w)
    lake = (~upstream) & (X > xw) & (X < xe) & (Z > WEIR_Z) & (Z < TOE_Z)
    inside = np.minimum(X - xw, xe - X)
    h = np.where(lake, -np.minimum(1.2 + inside * 0.3, 25.0), h)
    return h, lake, res


xs = np.arange(VIS[0], VIS[1], CELL) + CELL / 2
zs = np.arange(VIS[2], VIS[3], CELL) + CELL / 2
GX, GZ = np.meshgrid(xs, zs)
H, LAKE, RES = heights(GX, GZ)


def h_at(x, z):
    fx = (x - VIS[0]) / CELL - 0.5
    fz = (z - VIS[2]) / CELL - 0.5
    i0 = int(np.clip(math.floor(fx), 0, H.shape[1] - 2))
    j0 = int(np.clip(math.floor(fz), 0, H.shape[0] - 2))
    tx = min(max(fx - i0, 0.0), 1.0)
    tz = min(max(fz - j0, 0.0), 1.0)
    a = H[j0, i0] * (1 - tx) + H[j0, i0 + 1] * tx
    b = H[j0 + 1, i0] * (1 - tx) + H[j0 + 1, i0 + 1] * tx
    v = a * (1 - tz) + b * tz
    # над водой линия обзора идёт по воде, а не по дну
    if RES[int(np.clip(round(fz), 0, H.shape[0] - 1)), int(np.clip(round(fx), 0, H.shape[1] - 1))]:
        return RES_LEVEL
    return max(v, 0.0) if LAKE[int(np.clip(round(fz), 0, H.shape[0] - 1)), int(np.clip(round(fx), 0, H.shape[1] - 1))] else v


def crest(x_from, x_to, n=14):
    """Точки по середине гребня (5 м от верховой грани) на высоте гребня."""
    return [(float(x), float(arc_z(abs(x), R_ARC - 5)), CREST) for x in np.linspace(x_from, x_to, n)]


# ---------- маршруты ----------
W_SERP = [(-320, 200, 12), (-360, 300, 90), (-330, 370, 170), (-262, 420, 260.3)]
E_SERP = [(262, 420, 260.3), (330, 360, 200), (380, 270, 130), (380, 150, 60)]
TOE = [(-110, 340, 3), (-50, 360, 2), (50, 360, 2), (140, 330, 6)]
V_TO_SAW = [VILLAGE, (-300, -80, 20), (-280, 80, 15), SAWMILL]
R_TOE = V_TO_SAW + [(-200, 300, 5)] + TOE + [(300, 220, 40), SAN]
R_WEIR = [VILLAGE, (-280, -450, 20), (-150, -700, 8), (-80, -745, 6), (80, -745, 6), (180, -650, 10), (280, -400, 25),
          (300, -150, 35), (330, -20, 50), SAN]
R_CREST = V_TO_SAW + W_SERP + crest(-238, 238) + E_SERP + [SAN]
R_LIFT_A = V_TO_SAW + [(-200, 300, 5), (-110, 340, 3), (-60, 410, 2)]
R_LIFT_B = [(-60, 410, CREST)] + crest(-60, 60, 4) + [(60, 410, CREST)]
R_LIFT_C = [(60, 410, 2), (140, 330, 6), (300, 220, 40), SAN]
R_W_WAREHOUSE = [W, (-460, 30, 90), (-380, -100, 40), VILLAGE, (-420, -420, 80), (-470, -560, 130), WAREHOUSE]
R_B_AD = [B, (560, -500, 230), (560, 0, 220), (540, 250, 240), (500, 330, 270), AD]
R_B_SAN = [B, (420, -700, 120), (200, -600, 3), (280, -400, 25), (300, -150, 35), (330, -20, 50), SAN]
R_N_WEIR = [N, (0, -800, -8), (0, -745, 6)]
R_WH_VILLAGE = [WAREHOUSE, (-470, -560, 130), (-420, -420, 80), VILLAGE]

TRAVEL = [
    ('Посёлок → санаторий низом, по мосту у машзала', [R_TOE], 0.0),
    ('Посёлок → санаторий через водослив (север)', [R_WEIR], 0.0),
    ('Посёлок → санаторий через гребень серпантинами', [R_CREST], 0.0),
    ('Посёлок → санаторий через гребень лифтами', [R_LIFT_A, R_LIFT_B, R_LIFT_C], LIFT_SEC * 2),
    ('Заход W → склад ПЗРК (через посёлок)', [R_W_WAREHOUSE], 0.0),
    ('Заход B → старая ПВО (по хребту)', [R_B_AD], 0.0),
    ('Заход B → санаторий (берегом)', [R_B_SAN], 0.0),
    ('Заход N → водослив', [R_N_WEIR], 0.0),
]
ESCAPES = [
    ('Старая ПВО → D', [[AD, (500, 330, 270), (560, 300, 240), D]], 0.0),
    ('Санаторий → D', [[SAN, (SAN[0], SAN[1] + 70, 60), (480, 230, 130), D]], 0.0),
    ('Посёлок → W', [[VILLAGE, (-380, -100, 40), (-460, 30, 90), W]], 0.0),
    ('Посёлок → A через склад', [list(reversed(R_WH_VILLAGE)) + [(-560, -780, 180), A]], 0.0),
    ('Лесопилка → W', [[SAWMILL, (-300, 60, 10), (-460, 30, 90), W]], 0.0),
    ('Середина гребня → C (тоннель у гребня)', [crest(0, -238, 7) + [C]], 0.0),
    ('Мост у машзала → D', [[(0, 360, 2), (140, 330, 6), (300, 220, 40), (480, 230, 130), D]], 0.0),
    ('Водослив → N', [list(reversed(R_N_WEIR))], 0.0),
    ('Восточный берег (K2) → B', [[(220, -450, 3), (420, -700, 120), B]], 0.0),
]


def length3(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def climb(path):
    return sum(max(0.0, b[2] - a[2]) for a, b in zip(path, path[1:]))


def route_row(name, parts, extra):
    m = sum(length3(p) for p in parts)
    up = sum(climb(p) for p in parts)
    return name, m, up, m / SPRINT_MIX + extra, m / WALK + extra


# ---------- вертолёт: вверх по долине над озером, через гребень, над водохранилищем в горы ----------
HELI = [(0, -1700, 330), (0, -1100, 220), (-10, -745, 170), (10, -400, 150), (-10, 0, 150), (10, 200, 200),
        (0, 380, 290), (0, 480, 320), (-20, 700, 330), (20, 1000, 340), (0, 1700, 360)]


def sample_route(route, step):
    pts = []
    for a, b in zip(route, route[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(n):
            t = i / n
            pts.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
    pts.append(route[-1])
    return pts


def los(eye, tgt):
    dist = math.dist(eye, tgt)
    n = max(4, int(dist / 6))
    for i in range(2, n):
        t = i / n
        x = eye[0] + (tgt[0] - eye[0]) * t
        z = eye[1] + (tgt[1] - eye[1]) * t
        y = eye[2] + (tgt[2] - eye[2]) * t
        if VIS[0] < x < VIS[1] and VIS[2] < z < VIS[3] and h_at(x, z) > y - 1.0:
            return False
    return True


HELI_PTS = sample_route(HELI, HELI_SPEED)    # одна точка — одна секунда


def window(eye, rng):
    lock = run = best = 0
    for p in HELI_PTS:
        ok = math.dist(eye, p) <= rng and los(eye, p)
        lock += ok
        run = run + 1 if ok else 0
        best = max(best, run)
    return lock, best


def best_spot(x0, z0, radius, up):
    """Смотровая — у бровки: из точек вокруг (x0, z0) берём ту, откуда вертолёт виден дольше."""
    best = (-1, x0, z0)
    for dx in range(-radius, radius + 1, 20):
        for dz in range(-radius, radius + 1, 40):
            x, z = x0 + dx, z0 + dz
            if not (WALKABLE[0] <= x <= WALKABLE[1] and WALKABLE[2] <= z <= WALKABLE[3]):
                continue
            lock, _ = window((x, z, h_at(x, z) + up), MANPADS_RANGE)
            if lock > best[0]:
                best = (lock, x, z)
    return best[1], best[2]


V1 = best_spot(-540, -300, 80, 1.7)
V3 = best_spot(540, -250, 80, 1.7)
AD_BROW = best_spot(AD[0], AD[1], 60, 1.7)
RELAY = (565, -560)    # ретранслятор на восточном хребте (остановка 12, запасной блок для ПВО)
CREST_MID = (0.0, float(arc_z(0, R_ARC - 5)))
SHOOTERS = [
    ('Середина гребня (+260 над озером)', CREST_MID[0], CREST_MID[1], CREST + 1.7, MANPADS_RANGE, True),
    ('Старая ПВО у бровки, комплекс 2,5 км', AD_BROW[0], AD_BROW[1], 4.0, STATIC_RANGE, False),
    ('Старая ПВО у бровки, ПЗРК с плеча', AD_BROW[0], AD_BROW[1], 1.7, MANPADS_RANGE, False),
    ('Крыша жилого корпуса санатория', S1[0], S1[1], 12.0, MANPADS_RANGE, False),
    ('Лесопилка, берег', -240, 160, 1.7, MANPADS_RANGE, False),
    ('Посёлок, берег', -250, -250, 1.7, MANPADS_RANGE, False),
    ('Водослив', 0, WEIR_Z, 7.7, MANPADS_RANGE, True),
    ('Мост у машзала', 0, 360, 3.7, MANPADS_RANGE, True),
    ('Смотровая V1, западный хребет', V1[0], V1[1], 1.7, MANPADS_RANGE, False),
    ('Смотровая V3, восточный хребет', V3[0], V3[1], 1.7, MANPADS_RANGE, False),
]


def heli_rows():
    inside = sum(1 for p in HELI_PTS if WALKABLE[0] <= p[0] <= WALKABLE[1] and WALKABLE[2] <= p[1] <= WALKABLE[3])
    rows = []
    for name, ex, ez, up, rng, absolute in SHOOTERS:
        eye = (ex, ez, up if absolute else h_at(ex, ez) + up)
        lock, best = window(eye, rng)
        rows.append((name, lock, best))
    return inside, rows


def dam_angles():
    """Как высоко над горизонтом видно гребень из мест долины: угол на середину гребня и расстояние."""
    out = []
    for name, (x, z, y) in (('лесопилки', SAWMILL), ('санатория', SAN), ('посёлка', VILLAGE), ('водослива', (0, WEIR_Z, 6)),
                            ('моста у машзала', (0, 360, 2))):
        dist = math.hypot(CREST_MID[0] - x, CREST_MID[1] - z)
        out.append((name, dist, math.degrees(math.atan2(CREST - y - 1.7, dist))))
    return out


# ---------- постройки и остановки (одни и те же для схемы и стенда) ----------
def box(x, z, w, l, h, mat='building', yaw=0.0, base=None, group=''):
    return {'kind': 'box', 'x': x, 'z': z, 'w': w, 'l': l, 'h': h, 'yaw': yaw, 'base': base, 'mat': mat, 'group': group}


def cyl(x, z, r, h, mat='concrete', base=None, group=''):
    return {'kind': 'cyl', 'x': x, 'z': z, 'r': r, 'h': h, 'base': base, 'mat': mat, 'group': group}


def ring_wing(cx, cz, start_deg, end_deg, radius, group, mat='building'):
    """Крыло S-корпуса — дуга из коробок номерной полосы (8 м) и коридора (3 м), 3 этажа."""
    parts = []
    steps = 12
    for i in range(steps):
        a = math.radians(start_deg + (end_deg - start_deg) * (i + 0.5) / steps)
        seg = 2 * math.pi * radius * abs(end_deg - start_deg) / 360 / steps
        parts.append(box(round(cx + radius * math.cos(a), 1), round(cz + radius * math.sin(a), 1), 11.0, round(seg + 0.6, 1),
                         11.5, mat, round(-math.degrees(a), 1), None, group))
    return parts


EXTRAS = [
    (8, 'Водоприёмная башня в водохранилище: мостик с гребня, шахта к машзалу', 'L', (120, 540), (165, 545)),
    (9, 'Бетонный завод стройки у подножия: силосы, транспортёр', 'L', (-230, 300), (-275, 270)),
    (10, 'Кабель-кран: башни на полках у гребня, трос с бадьёй над долиной', 'M', (0, 418), (60, 395)),
    (11, 'Водонапорная башня посёлка, вид на озеро и плотину', 'S', (-470, -180), (-515, -170)),
    (12, 'Пожарная вышка (запад) и ретранслятор (восток, запасной блок)', 'S', (-570, -60), (-610, -95)),
    (13, 'Служебный городок ГЭС: пульт — блок для ПВО, автобаза — топливо', 'M–L', SERVICE[:2], (300, 255)),
    (14, 'ЛЭП от ОРУ вверх по склону к выходу D', 'S', (390, 310), (390, 355)),
    (15, 'Ж/д ветка вдоль западного берега к выходу N, вагоны у лесопилки', 'M', (-280, 70), (-235, 40)),
    (16, 'КПП части ПВО на дороге к складу, его держат мародёры', 'S', (-440, -520), (-395, -530)),
    (17, 'Казармы части у старой ПВО', 'M', (475, 370), (520, 350)),
    (18, 'Терренкур санатория: тропа с беседками к восточному хребту', 'S', (470, -20), (515, -20)),
    (19, 'Пирс, лодочная станция и пляжное кафе санатория', 'S', (225, 105), (195, 145)),
    (20, 'Дебаркадер у водослива: весь вид вверх по долине', 'S', (0, -660), (45, -630)),
    (21, 'Рыбацкие домики и гидропост на каменистом берегу (K2)', 'S', (250, -470), (300, -490)),
    (22, 'Пункт сбора «эвакуации»: автобусы, палатки, сумки — сюжет', 'S–M', (-340, -30), (-395, -5)),
    (23, 'Лодочная станция посёлка: запасное топливо', 'S', (-245, -260), (-205, -290)),
    (24, 'Делянка лесорубов на склоне над посёлком (K1)', 'S', (-530, -380), (-485, -395)),
    (25, 'Вагон-городок строителей у подножия (K3 рядом)', 'S', (-250, 395), (-300, 410)),
    (26, 'Штольни в склонах у подножия плотины', 'S', (-120, 425), (-160, 455)),
    (27, 'Колокольня затопленного села в водохранилище — по решению владельца', '—', (-60, 700), (-110, 700)),
    (28, 'Водозабор санатория: насосная у воды, трубы вверх по склону', 'S', (262, -260), (310, -270)),
    (29, 'Огороды и сараи на северной окраине посёлка', 'S', (-220, -560), (-175, -575)),
    (30, 'Пост на дороге к перевалу B: вагончик, шлагбаум, брошенная машина', 'S', (380, -690), (380, -645)),
]


def structures():
    s = []
    # 1 посёлок
    for i in range(12):
        col, row = i % 2, i // 2
        x = -440 + col * 70 + (row % 2) * 12
        z = -345 + row * 38
        s.append(box(x - 4, z - 2, 10, 8, 6.5, 'house', 0, None, 'посёлок'))
        s.append(box(x + 9, z + 7, 4, 5, 2.6, 'wood', 0, None, 'посёлок'))
    s.append(box(-330, -200, 20, 12, 7.5, 'building', 0, None, 'посёлок'))
    # 2 лесопилка
    s += [box(-330, 172, 60, 20, 9, 'metal_shed', 0, None, 'лесопилка'), box(-385, 200, 28, 14, 6, 'wood', 0, None, 'лесопилка')]
    s += [box(-390 + i * 16, 132, 9, 24, 3, 'logs', 0, None, 'лесопилка') for i in range(4)]
    # 3 склад ПЗРК
    for a, b in (((-560, -710), (-400, -710)), ((-400, -710), (-400, -600)), ((-400, -600), (-560, -600)),
                 ((-560, -600), (-560, -710))):
        s.append({'kind': 'wall', 'a': list(a), 'b': list(b), 'h': 2.6, 't': 0.25, 'mat': 'concrete', 'group': 'склад'})
    s += [box(-510 + i * 50, -660, 40, 14, 7, 'military', 0, None, 'склад') for i in range(3)]
    s.append(box(-415, -695, 4, 4, 12, 'wood', 0, None, 'склад'))
    # 4 старая ПВО
    s.append(cyl(AD[0], AD[1], 6, 9, 'metal', None, 'ПВО'))
    for ang in range(0, 360, 90):
        s.append(box(round(AD[0] + 38 * math.cos(math.radians(ang + 45)), 1), round(AD[1] + 38 * math.sin(math.radians(ang + 45)), 1),
                     7, 7, 2.5, 'military', ang, None, 'ПВО'))
    # 5 санаторий: главный, S-корпус 1, S-корпус 2 на ремонте
    s.append(box(420, 80, 26, 100, 13, 'building', 0, None, 'санаторий'))
    for (cx, cz, _), mat in ((S1, 'building'), (S2, 'concrete')):
        s += ring_wing(cx, cz - 30, 40, 320, 25, 'санаторий', mat)
        s += ring_wing(cx, cz + 30, 220, 500, 25, 'санаторий', mat)
        s.append(box(cx, cz, 24, 20, 13, mat, 0, None, 'санаторий'))
    # 7 у подножия: машзал, двор, ОРУ, мост через отводящий канал
    s.append(box(HALL[0], HALL[1], 130, 26, 28, 'concrete', 0, None, 'ГЭС'))
    s += [box(-120, 330, 30, 18, 7, 'building', 0, None, 'ГЭС'), box(-90, 355, 24, 12, 5, 'metal_shed', 0, None, 'ГЭС')]
    for i in range(4):
        for j in range(3):
            s.append(box(SWITCH[0] - 45 + i * 30, SWITCH[1] - 30 + j * 30, 6, 4, 5, 'metal', 0, None, 'ГЭС'))
    s.append({'kind': 'deck', 'a': [-55, 362], 'b': [55, 362], 'y': 2.4, 'w': 6.0, 't': 0.8, 'mat': 'concrete', 'group': 'ГЭС'})
    # водослив на северном конце озера: тело, проезд по верху, затворы
    s.append(box(0, WEIR_Z, 190, 14, 18, 'concrete', 0, -12, 'водослив'))
    s += [box(x, WEIR_Z - 3, 3, 4, 5, 'metal', 0, 6, 'водослив') for x in (-45, -15, 15, 45)]
    # 8 водоприёмная башня в водохранилище, мостик с гребня
    s.append(cyl(120, 540, 8, 122, 'concrete', 150, 'остановки'))
    s.append({'kind': 'deck', 'a': [120, float(arc_z(120)) - 2], 'b': [120, 532], 'y': CREST + 0.5, 'w': 3.0, 't': 0.6,
              'mat': 'concrete', 'group': 'остановки'})
    # 9 бетонный завод
    s += [cyl(x, 290, 6, 28, 'concrete', None, 'остановки') for x in (-252, -236, -220)]
    s.append(box(-230, 318, 44, 20, 12, 'metal_shed', 0, None, 'остановки'))
    s.append({'kind': 'beam', 'a': [-220, 292, 30], 'b': [-140, 360, 14], 'r': 1.5, 'mat': 'metal', 'group': 'остановки'})
    # 10 кабель-кран на полках у гребня
    for x in (-268, 268):
        s.append(box(x, 418, 4, 4, 40, 'metal', 0, None, 'остановки'))
    s.append({'kind': 'tower_cable', 'a': [-268, 418], 'b': [268, 418], 'top': 40, 'r': 0.12, 'mat': 'metal', 'group': 'остановки'})
    s.append(box(0, 418, 3, 3, 3, 'metal', 0, 280, 'остановки'))
    # 11 водонапорная башня, 12 пожарная вышка и ретранслятор
    s += [cyl(-470, -180, 2.5, 18, 'concrete', None, 'остановки'), cyl(-470, -180, 5, 6, 'metal', 'top+18', 'остановки')]
    s.append(box(-570, -60, 4, 4, 25, 'wood', 0, None, 'остановки'))
    s += [box(RELAY[0], RELAY[1], 2, 2, 40, 'metal', 0, None, 'остановки'),
          box(RELAY[0] + 6, RELAY[1], 4, 3, 3, 'building', 0, None, 'остановки')]
    # 13 служебный городок ГЭС
    s += [box(SERVICE[0], SERVICE[1], 40, 18, 10, 'building', 0, None, 'остановки'),
          box(SERVICE[0] + 38, SERVICE[1] - 15, 26, 14, 6, 'metal_shed', 0, None, 'остановки'),
          box(SERVICE[0] - 20, SERVICE[1] + 35, 16, 8, 4, 'building', 0, None, 'остановки')]
    # 14 ЛЭП
    towers = [(SWITCH[0] + 45, SWITCH[1]), (240, 335), (340, 322), (440, 305), (540, 292), (600, 286)]
    for t in towers[1:-1]:
        s.append(box(t[0], t[1], 2.2, 2.2, 30, 'metal', 0, None, 'остановки'))
    s.append({'kind': 'tower_cable', 'a': list(towers[1]), 'b': list(towers[-2]), 'top': 29, 'r': 0.08, 'mat': 'metal',
              'group': 'остановки', 'via': [list(t) for t in towers[2:-2]]})
    # 15 ж/д: вагоны у лесопилки
    s += [box(-280 - k * 2, 100 - k * 25, 3.2, 14, 4, 'metal', 0, None, 'остановки') for k in range(3)]
    # 16 КПП, 17 казармы, 18 беседки терренкура
    s += [box(-440, -520, 4, 3, 3, 'building', 0, None, 'остановки'), box(-440, -510, 10, 0.3, 1.1, 'metal', 0, None, 'остановки')]
    s += [box(470, 345, 34, 12, 7, 'military', 0, None, 'остановки'), box(482, 405, 30, 12, 7, 'military', 0, None, 'остановки')]
    s += [box(x, z, 4, 4, 3, 'wood', 0, None, 'остановки') for x, z in ((440, 10), (470, -20), (500, -100))]
    # 19 пирс, лодочная, кафе; 20 дебаркадер у водослива; 21 рыбацкие домики, гидропост
    s += [box(215, 105, 58, 3, 0.6, 'wood', 0, 0.3, 'остановки'), box(252, 70, 14, 10, 5, 'wood', 0, None, 'остановки'),
          box(268, 132, 12, 10, 4, 'building', 0, None, 'остановки')]
    s += [box(0, -660, 40, 12, 4, 'metal', 0, -0.6, 'остановки'), box(-95, -655, 150, 2.2, 0.5, 'wood', 0, 0.0, 'остановки')]
    s += [box(250, -480, 8, 6, 3, 'wood', 0, None, 'остановки'), box(256, -456, 8, 6, 3, 'wood', 0, None, 'остановки'),
          cyl(230, -500, 1, 3, 'metal', None, 'остановки')]
    # 22 пункт сбора; 23 лодочная станция посёлка; 24 делянка; 25 вагон-городок
    s += [box(x, -30, 2.5, 12, 3.2, 'bus', 0, None, 'остановки') for x in (-300, -288)]
    s += [box(x, z, 4, 4, 2.5, 'tent', 0, None, 'остановки') for x, z in ((-350, -40), (-338, -28), (-355, -18), (-343, -50))]
    s += [box(-245, -260, 14, 10, 4, 'wood', 0, None, 'остановки'), box(-222, -260, 26, 2.5, 0.6, 'wood', 0, 0.3, 'остановки')]
    s += [box(x, -380, 10, 4, 2, 'logs', 0, None, 'остановки') for x in (-550, -530, -510)]
    s += [box(-250, z, 22, 9, 3.5, 'wood', 0, None, 'остановки') for z in (380, 398, 416)]
    # 29 огороды и сараи; 30 пост у перевала
    s += [box(-220 + dx, -560 + dz, 6, 4, 2.6, 'wood', 0, None, 'остановки') for dx, dz in ((0, 0), (18, 12), (-14, 20))]
    s += [box(-205, -585, 10, 4, 2.2, 'tent', 0, None, 'остановки')]
    s += [box(380, -690, 3, 7, 3, 'metal_shed', 0, None, 'остановки'), box(392, -680, 9, 0.3, 1.1, 'metal', 0, None, 'остановки'),
          box(372, -665, 2, 4.5, 1.5, 'bus', 0, None, 'остановки')]
    # 28 водозабор санатория: насосная и труба к корпусам
    s.append(box(262, -260, 12, 9, 5, 'building', 0, None, 'остановки'))
    s.append({'kind': 'beam', 'a': [268, -255, 4], 'b': [S1[0] - 10, S1[1] - 25, S1[2] + 1], 'r': 0.4, 'mat': 'metal', 'group': 'остановки'})
    # боны в водохранилище перед гребнем
    xr = float(np.interp(575, RES_AXIS[:, 0], RES_AXIS[:, 1]))
    wr = float(np.interp(575, RES_HALF[:, 0], RES_HALF[:, 1]))
    s += [box(round(x, 1), 575, 2.4, 1.2, 0.6, 'buoy', 0, RES_LEVEL - 0.2, 'боны') for x in np.arange(xr - wr + 4, xr + wr - 2, 6)]
    return s


# ---------- рисование ----------
def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


class Sheet:
    def __init__(self, size):
        self.im = Image.new('RGB', size, PAPER)
        self.d = ImageDraw.Draw(self.im)

    def text(self, xy, text, size=24, fill=INK, bold=False, anchor=None):
        self.d.text(xy, text, font=font(size, bold), fill=fill, spacing=6, anchor=anchor)

    def wrapped(self, xy, text, width=40, size=22, fill=INK, bold=False):
        lines = textwrap.wrap(text, width=width)
        self.text(xy, '\n'.join(lines), size, fill, bold)
        return len(lines) * (size + 6)

    def dashed(self, pts, fill, width=3, dash=(14, 10)):
        phase = 0.0
        period = dash[0] + dash[1]
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            pos = 0.0
            while pos < seg:
                on = phase < dash[0]
                step = min((dash[0] - phase) if on else (period - phase), seg - pos)
                if on:
                    p = (a[0] + (b[0] - a[0]) * pos / seg, a[1] + (b[1] - a[1]) * pos / seg)
                    q = (a[0] + (b[0] - a[0]) * (pos + step) / seg, a[1] + (b[1] - a[1]) * (pos + step) / seg)
                    self.d.line([p, q], fill=fill, width=width)
                pos += step
                phase = (phase + step) % period


def colorize():
    stops_h = [-30, 0, 60, 150, 260, 360, 520, 900]
    stops_c = [(214, 224, 196), (214, 224, 196), (196, 214, 174), (172, 196, 150), (160, 182, 142), (170, 172, 150),
               (178, 176, 166), (214, 212, 206)]
    h = H
    rgb = np.stack([np.interp(h, stops_h, [c[k] for c in stops_c]) for k in range(3)], -1)
    gz, gx = np.gradient(h, CELL)
    n = np.stack([-gx, np.ones_like(h), -gz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    light = np.array([-0.55, 0.65, -0.52])
    light /= np.linalg.norm(light)
    rgb *= (0.55 + 0.6 * np.clip((n * light).sum(-1), 0, 1))[..., None]
    water = LAKE | RES
    for step, dark in ((50, 0.88), (250, 0.7)):
        c = np.floor(h / step)
        edge = np.zeros_like(h, bool)
        edge[:, 1:] |= c[:, 1:] != c[:, :-1]
        edge[1:, :] |= c[1:, :] != c[:-1, :]
        rgb[edge & ~water] *= dark
    rgb[LAKE] = (143, 184, 189)
    rgb[RES] = (120, 165, 178)
    core = (GX >= WALKABLE[0]) & (GX <= WALKABLE[1]) & (GZ >= WALKABLE[2]) & (GZ <= WALKABLE[3])
    paper = np.array([228, 225, 214], float)
    rgb[~core] = rgb[~core] * 0.45 + paper * 0.55
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')


ROADS = [
    [A, (-560, -780), WAREHOUSE, (-470, -560), (-420, -420), VILLAGE, (-300, -80), (-280, 80), SAWMILL, (-200, 300),
     YARD, (-50, 360), (50, 360), SWITCH, (300, 220), SAN, (330, -20), (300, -150), (280, -400), (200, -600),
     (420, -700), B],
    [VILLAGE, (-280, -450), (-150, -700), (-80, -745), (80, -745), (180, -650), (200, -600)],
    [(0, -745), (0, -800), N],
    [(-280, 80), (-300, 60), (-460, 30), W],
    [SAN, (SAN[0], SAN[1] + 70), (480, 230), D],
    [(-262, 420), C],
]
SERPENTINES = [W_SERP, E_SERP, [(262, 420), (340, 400), AD]]
TRAILS = [
    [A, (-600, -600), V1, (-560, -100), (-570, -60), (-540, 100), W],
    [B, (560, -500), V3, (560, 0), (540, 250), (500, 330), AD],
    [(SAN[0] + 20, SAN[1] - 60), (440, 10), (470, -20), (500, -100), V3],
    [(240, 120), (290, 110), (330, 95)],
    [VILLAGE, (-470, -300), V1],
]
RAIL = [(-130, 345), (-240, 250), (-270, 80), (-290, -100), (-260, -400), (-150, -700), (-90, -900), (-60, -1100)]


def plan_sheet():
    s = Sheet((1660, 2400))
    s.text((60, 32), 'ВЕРТОЛЁТ · ПРЕДЛОЖЕНИЕ v05 · ПЛОТИНА НАД ДОЛИНОЙ', 40, bold=True)
    s.text((60, 94), 'Claude · 06.11.2026 · по замыслу владельца, на обсуждение · все места v02 на месте', 23, ORANGE)
    s.text((60, 132), 'Речка с гор → водохранилище +255 → плотина 260 м → озеро 0 м → водослив. Ходят по долине 1,3 × 1,6 км.', 22)
    x0, y0, k = 60, 200, 0.5

    def p(x, z):
        return (x0 + (x - VIS[0]) * k, y0 + (z - VIS[2]) * k)

    s.im.paste(colorize(), (x0, y0))
    d = s.d
    d.line([p(x, z) for z, x in NORTH_RIVER], fill=(120, 168, 176), width=7, joint='curve')
    d.line([p(0, 412), p(0, 366)], fill=(120, 168, 176), width=8)
    s.dashed([p(WALKABLE[0], WALKABLE[2]), p(WALKABLE[1], WALKABLE[2]), p(WALKABLE[1], WALKABLE[3]),
              p(WALKABLE[0], WALKABLE[3]), p(WALKABLE[0], WALKABLE[2])], INK, 4, (18, 10))
    d.rectangle([p(VIS[0], VIS[2]), p(VIS[1], VIS[3])], outline=MUTED, width=2)
    for r in ROADS:
        d.line([p(q[0], q[1]) for q in r], fill=ROAD, width=5, joint='curve')
    for r in SERPENTINES:
        s.dashed([p(q[0], q[1]) for q in r], ROAD, 5, (10, 5))
    for t in TRAILS:
        s.dashed([p(q[0], q[1]) for q in t], TRAIL, 4, (10, 7))
    d.line([p(*q) for q in RAIL], fill=(70, 60, 50), width=2)
    # плотина: тело арки сверху (от низовой грани у подошвы до верховой)
    ang = math.asin(CHORD_HALF / R_ARC)
    outer = [p(R_ARC * math.sin(a), CZ + R_ARC * math.cos(a)) for a in np.linspace(-ang, ang, 40)]
    inner = [p((R_ARC - 60) * math.sin(a), CZ + (R_ARC - 60) * math.cos(a)) for a in np.linspace(ang, -ang, 40)]
    d.polygon(outer + inner, fill=(226, 224, 216), outline=INK)
    d.line([p(-95, WEIR_Z), p(95, WEIR_Z)], fill=(226, 224, 216), width=9)
    d.line([p(-95, WEIR_Z), p(95, WEIR_Z)], fill=INK, width=2)
    # постройки — те же коробки, что в стенде
    for st in structures():
        kind = st['kind']
        if kind == 'box':
            yaw = math.radians(st['yaw'])
            hw, hl = st['w'] / 2, st['l'] / 2
            pts = []
            for cx, cz in ((-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)):
                rx = cx * math.cos(yaw) + cz * math.sin(yaw)
                rz = -cx * math.sin(yaw) + cz * math.cos(yaw)
                pts.append(p(st['x'] + rx, st['z'] + rz))
            d.polygon(pts, fill=(236, 228, 205), outline=(130, 110, 82))
        elif kind == 'cyl':
            c = p(st['x'], st['z'])
            r = max(2.0, st['r'] * k)
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(215, 212, 205), outline=INK)
        elif kind in ('deck', 'wall', 'beam'):
            d.line([p(st['a'][0], st['a'][1]), p(st['b'][0], st['b'][1])], fill=(120, 95, 70), width=3)
        elif kind == 'tower_cable':
            d.line([p(*st['a']), p(*st['b'])], fill=(60, 60, 60), width=1)
    hp = [p(q[0], q[1]) for q in sample_route(HELI, 10) if VIS[2] + 5 <= q[1] <= VIS[3] - 5]
    s.dashed(hp, ORANGE, 5, (22, 12))
    for a, b in ((HELI[2], HELI[3]), (HELI[4], HELI[5]), (HELI[8], HELI[9])):
        a, b = p(a[0], a[1]), p(b[0], b[1])
        ang2 = math.atan2(b[1] - a[1], b[0] - a[0])
        tip = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d.polygon([tip, (tip[0] - 18 * math.cos(ang2 - 0.45), tip[1] - 18 * math.sin(ang2 - 0.45)),
                   (tip[0] - 18 * math.cos(ang2 + 0.45), tip[1] - 18 * math.sin(ang2 + 0.45))], fill=ORANGE)
    for name, (x, z) in (('K1', (-560, -450)), ('K2', (220, -450)), ('K3', (170, 250))):
        c = p(x, z)
        d.line([c[0] - 10, c[1] - 10, c[0] + 10, c[1] + 10], fill=RED, width=5)
        d.line([c[0] - 10, c[1] + 10, c[0] + 10, c[1] - 10], fill=RED, width=5)
        s.text((c[0] + 12, c[1] - 12), name, 20, RED, True)
    for name, (x, z) in (('V1', V1), ('V3', V3)):
        c = p(x, z)
        d.polygon([(c[0], c[1] - 9), (c[0] - 8, c[1] + 6), (c[0] + 8, c[1] + 6)], fill=INK)
        s.text((c[0] + 10, c[1] - 6), name, 16, INK, True)
    for name, (x, z, _), entry in (('A', A, False), ('B', B, True), ('N', N, True), ('W', W, True), ('D', D, False),
                                   ('C', C, False)):
        c = p(x, z)
        d.rectangle([c[0] - 10, c[1] - 10, c[0] + 10, c[1] + 10], fill=ORANGE if entry else PAPER, outline=ORANGE, width=3)
        s.text((c[0] + 14, c[1] - 13), name, 22, ORANGE, True)
    for n, label, _, _, (lx, lz) in EXTRAS:
        c = p(lx, lz)
        d.ellipse([c[0] - 12, c[1] - 12, c[0] + 12, c[1] + 12], fill=EXTRA, outline=PAPER, width=2)
        s.text(c, str(n), 15, PAPER, True, 'mm')
    for n, (x, z) in ((1, (-280, -330)), (2, (-250, 210)), (3, (-575, -580)), (4, (480, 410)), (5, (470, 40)), (6, (0, 505)),
                      (7, (-40, 430))):
        c = p(x, z)
        d.ellipse([c[0] - 17, c[1] - 17, c[0] + 17, c[1] + 17], fill=INK, outline=PAPER, width=2)
        s.text(c, str(n), 22, PAPER, True, 'mm')
    s.text(p(-90, -250), 'ОЗЕРО · 0 м', 24, (40, 90, 100), True)
    s.text(p(-180, 900), 'ВОДОХРАНИЛИЩЕ +255', 22, (30, 80, 100), True)
    s.text(p(-80, WEIR_Z - 40), 'водослив', 17, INK, True)
    s.text(p(-960, 1460), 'горы и водохранилище — видом, не ходим', 18, MUTED)
    nx, ny = p(930, -1440)
    d.line([nx, ny + 50, nx, ny], fill=INK, width=4)
    d.polygon([(nx, ny - 14), (nx - 9, ny + 4), (nx + 9, ny + 4)], fill=INK)
    s.text((nx - 8, ny - 42), 'С', 22, INK, True)
    sx, sy = 80, y0 + 1500 + 34
    d.line([sx, sy, sx + 250, sy], fill=INK, width=4)
    for i, lab in ((0, '0'), (125, '250'), (250, '500 м')):
        d.line([sx + i, sy - 8, sx + i, sy + 8], fill=INK, width=3)
        s.text((sx + i - 8, sy + 14), lab, 20)
    lx, ly = 1110, 200
    s.text((lx, ly), 'ДОЛИНА ПОД ПЛОТИНОЙ', 24, INK, True)
    ly += 40
    items = [
        ('1 · Посёлок', 'Посёлок эксплуатационников ГЭС, 12 участков, +30.'),
        ('2 · Лесопилка', 'У залива под плотиной, +12: стена в 260 м над головой.'),
        ('3 · Склад ПЗРК', 'Склад части ПВО в висячей долине, +150.'),
        ('4 · Старая ПВО', 'Уступ у плотины, +300: над долиной и подножием.'),
        ('5 · Санаторий', 'Санаторий энергосистемы, недавно перестроен; окна на плотину. S-корпус 2 — на ремонте.'),
        ('6 · Плотина', 'Арка 260 м, гребень ~490 м; лифт и лестницы внутри, серпантины к полкам у гребня.'),
        ('7 · ГЭС у подножия', 'Машзал, двор, ОРУ, мост через отводящий канал — на уровне озера.'),
    ]
    for head, body in items:
        s.text((lx, ly), head, 22, INK, True)
        ly += 28
        ly += s.wrapped((lx, ly), body, 42, 19, MUTED) + 10
    ly += 4
    s.text((lx, ly), 'ПЕРЕХОДЫ МЕЖДУ БЕРЕГАМИ', 22, INK, True)
    ly += 32
    for body in ('Мост у машзала — центр, под взглядом с гребня.', 'Водослив на севере — длинный обход по воде.',
                 'Гребень +260 — лифт или серпантины; высота над всем.'):
        ly += s.wrapped((lx, ly), '· ' + body, 44, 19, MUTED) + 4
    ly += 12
    legend = [
        ('line', ORANGE, 'Пролёт: вверх по долине, через гребень'),
        ('x', RED, 'K1–K3: лесистый склон, берег, подножие'),
        ('sqf', ORANGE, 'B, N, W: заходы и выходы'),
        ('sq', ORANGE, 'A, D, C: только выходы'),
        ('line', ROAD, 'дороги; пунктир — серпантины'),
        ('dash', (205, 180, 120), 'тропы'),
        ('ext', EXTRA, '8–30: остановки между местами'),
    ]
    for kind, col, label in legend:
        if kind == 'line':
            d.line([lx, ly + 10, lx + 46, ly + 10], fill=col, width=5)
        elif kind == 'dash':
            s.dashed([(lx, ly + 10), (lx + 46, ly + 10)], col, 4, (10, 7))
        elif kind == 'x':
            d.line([lx + 12, ly + 1, lx + 30, ly + 19], fill=col, width=4)
            d.line([lx + 12, ly + 19, lx + 30, ly + 1], fill=col, width=4)
        elif kind in ('sq', 'sqf'):
            d.rectangle([lx + 12, ly + 1, lx + 30, ly + 19], outline=col, width=3, fill=col if kind == 'sqf' else PAPER)
        elif kind == 'ext':
            d.ellipse([lx + 9, ly - 1, lx + 33, ly + 21], fill=col)
        s.text((lx + 58, ly - 2), label, 19)
        ly += 30
    ly += 16
    s.text((lx, ly), 'ГРЕБЕНЬ НАД ГОЛОВОЙ', 22, INK, True)
    ly += 32
    for name, dist, deg in dam_angles():
        ly += s.wrapped((lx, ly), f'· с {name}: {dist:.0f} м, на {deg:.0f}° над горизонтом', 44, 19, MUTED) + 4
    s.text((540, y0 + 1500 + 26), 'Рельеф — схема для замеров, не готовая форма. Деревья не нарисованы.', 19, MUTED)
    top = y0 + 1500 + 90
    s.text((60, top), 'ОСТАНОВКИ МЕЖДУ МЕСТАМИ · 8–30 · S — домик или площадка, M — несколько построек, L — крупное', 21, INK, True)
    top += 40
    for i, (n, label, cost, _, _) in enumerate(EXTRAS):
        col, row = divmod(i, 12)
        x = 60 + col * 790
        y = top + row * 34
        d.ellipse([x, y, x + 24, y + 24], fill=EXTRA)
        s.text((x + 12, y + 12), str(n), 14, PAPER, True, 'mm')
        s.text((x + 34, y + 1), f'{label} · {cost}', 18)
    s.im.save(PLANS / 'mission_helicopter_v05_plan.png')
    a, b = p(WALKABLE[0] - 20, WALKABLE[2] - 20), p(WALKABLE[1] + 20, WALKABLE[3] + 30)
    core = s.im.crop((int(a[0]), int(a[1]), int(b[0]), int(b[1])))
    core.resize((core.width * 2, core.height * 2), Image.LANCZOS).save(PLANS / 'mission_helicopter_v05_plan_core.png')


def sections_sheet(travel, escapes, heli):
    s = Sheet((1800, 2400))
    d = s.d
    s.text((60, 32), 'ВЕРТОЛЁТ · v05 · РАЗРЕЗЫ В НАСТОЯЩЕМ МАСШТАБЕ И РАСЧЁТЫ', 38, bold=True)
    s.text((60, 92), 'Горизонталь и вертикаль одинаковые. Долина ниже плотины, водохранилище выше.', 23, ORANGE)

    def section(top, left, pts_xz, k, ymin, ymax, title, extra=None, span=None):
        s.text((left, top), title, 24, INK, True)
        top += 40
        hgt = (ymax - ymin) * k
        prof = []
        for i, (x, z) in enumerate(pts_xz):
            prof.append((left + i * CELL * k, top + (ymax - min(h_at(x, z), ymax)) * k))
        base = top + hgt
        d.polygon(prof + [(prof[-1][0], base), (prof[0][0], base)], fill=(184, 196, 166))
        d.line(prof, fill=(90, 110, 90), width=2)
        for yv in range(int(math.ceil(ymin / 100) * 100), int(ymax) + 1, 100):
            yy = top + (ymax - yv) * k
            d.line([left - 8, yy, left, yy], fill=MUTED, width=2)
            s.text((left - 60, yy - 10), f'{yv:+d}' if yv else '0', 16, MUTED)
        if extra:
            extra(left, top, k, ymax)
        return base

    za = np.arange(VIS[2], VIS[3], CELL)
    axis = []
    for z in za:
        if z < WEIR_Z:
            axis.append((float(np.interp(z, NORTH_RIVER[:, 0], NORTH_RIVER[:, 1])), z))
        elif z < TOE_Z:
            axis.append((float((np.interp(z, WEST[:, 0], WEST[:, 1]) + np.interp(z, EAST[:, 0], EAST[:, 1])) / 2), z))
        elif z < 480:
            axis.append((0.0, z))
        else:
            axis.append((float(np.interp(z, RES_AXIS[:, 0], RES_AXIS[:, 1])), z))

    def extra_a(left, top, k, ymax):
        def P(z, y):
            return (left + (z - VIS[2]) * k, top + (ymax - y) * k)
        lake_bed = [P(z, -min(1.2 + 0.3 * 150 * math.sin(math.pi * (z - WEIR_Z) / (TOE_Z - WEIR_Z)), 25)) for z in
                    range(int(WEIR_Z), int(TOE_Z), 10)]
        d.polygon([P(WEIR_Z, 0)] + lake_bed + [P(TOE_Z, 0)], fill=(150, 188, 192))
        d.line([P(WEIR_Z, 0), P(TOE_Z, 0)], fill=(70, 120, 130), width=3)
        d.polygon([P(480, RES_LEVEL), P(480, 150), P(1500, 150), P(1500, RES_LEVEL)], fill=(130, 172, 184))
        d.line([P(480, RES_LEVEL), P(1500, RES_LEVEL)], fill=(70, 120, 130), width=3)
        d.polygon([P(480, CREST), P(470, CREST), P(420, FOOT), P(480, FOOT)], fill=(205, 205, 198), outline=INK)
        for gy in (60, 130, 200):
            d.rectangle([P(470 - (CREST - gy) * 0.19, gy + 3), P(478, gy - 3)], fill=INK)
        d.rectangle([P(382, 30), P(408, FOOT)], fill=(220, 214, 200), outline=INK)
        d.rectangle([P(WEIR_Z - 7, 6), P(WEIR_Z + 7, -12)], fill=(205, 205, 198), outline=INK)
        hp = [P(q[1], q[2]) for q in sample_route(HELI, 10) if VIS[2] <= q[1] <= VIS[3]]
        s.dashed(hp, ORANGE, 4, (18, 10))
        for z in (WALKABLE[2], WALKABLE[3]):
            s.dashed([P(z, 560), P(z, -40)], INK, 2, (8, 8))
        s.text(P(-500, 30), 'озеро 0 м', 19, (40, 90, 100), True)
        s.text(P(700, 290), 'водохранилище +255', 19, (30, 80, 100), True)
        s.text(P(300, 300), 'гребень +260', 18, INK, True)
        s.text(P(150, 80), 'машзал', 18, INK)
        s.text(P(WEIR_Z - 60, 40), 'водослив', 18, INK)
        s.text(P(-1450, 420), 'пролёт: над озером +150, через гребень на +320', 19, ORANGE)

    bottom = section(140, 120, axis, 0.55, -60, 620, 'А · Вдоль долины: водослив → озеро → плотина → водохранилище (север слева)',
                     extra_a)
    kb = 0.42
    xs_ = np.arange(VIS[0], VIS[1], CELL)

    def extra_b(left, top, k, ymax):
        def P(x, y):
            return (left + (x - VIS[0]) * k, top + (ymax - y) * k)
        d.polygon([P(-265, 0), P(-200, -20), P(200, -20), P(240, 0)], fill=(150, 188, 192))
        for x in (WALKABLE[0], WALKABLE[1]):
            s.dashed([P(x, 900), P(x, -40)], INK, 2, (8, 8))
        s.text(P(-560, 120), 'лесопилка +12', 17, INK, True)
        s.text(P(260, 160), 'санаторий +60', 17, INK, True)

    def extra_c(left, top, k, ymax):
        def P(x, y):
            return (left + (x - VIS[0]) * k, top + (ymax - y) * k)
        # арка у гребня перекрывает теснину: силуэт плотины в этом сечении
        d.polygon([P(-245, CREST), P(245, CREST), P(70, FOOT), P(-70, FOOT)], fill=(215, 213, 205), outline=INK)
        s.text(P(-180, CREST + 40), 'гребень +260, ~490 м', 17, INK, True)
        s.text(P(-120, 120), 'плотина', 17, INK)

    top2 = bottom + 40
    end_b = section(top2, 120, [(x, 160.0) for x in xs_], kb, -60, 900, 'Б · Поперёк долины: лесопилка — озеро — санаторий (z +160)',
                    extra_b)
    end_c = section(top2, 120 + 2000 * kb + 110, [(x, 452.0) for x in xs_], kb, -60, 900, 'В · Поперёк у плотины (z +450)', extra_c)
    y = max(end_b, end_c) + 50

    def table(y, title, head, rows, widths):
        s.text((60, y), title, 25, INK, True)
        y += 38
        x = 60
        for h_, w in zip(head, widths):
            s.text((x, y), h_, 19, MUTED, True)
            x += w
        y += 30
        for r in rows:
            x = 60
            for v, w in zip(r, widths):
                s.text((x, y), v, 20)
                x += w
            y += 30
        return y + 16

    rows = [(n, f'{m / 1000:.2f} км', f'{up:.0f} м', f'{tr / 60:.1f} мин', f'{tw / 60:.1f} мин') for n, m, up, tr, tw in travel]
    y = table(y, 'Пути пешком (бег с передышками 4,4 м/с · шаг 1,82 м/с; лифт — 75 с)',
              ('Путь', 'длина', 'подъём', 'бегом', 'шагом'), rows, (760, 180, 160, 170, 170))
    rows = [(n, f'{m:.0f} м', f'{up:.0f} м', f'{tr / 60:.1f} мин', f'{tw / 60:.1f} мин') for n, m, up, tr, tw in escapes]
    y = table(y, 'Уход после выстрела к ближайшему выходу', ('Откуда → куда', 'длина', 'подъём', 'бегом', 'шагом'),
              rows, (760, 180, 160, 170, 170))
    inside, hrows = heli
    rows = [(n, f'{lock} с', f'{run} с') for n, lock, run in hrows]
    y = table(y, f'Вертолёт 42 м/с: над долиной {inside} с за пролёт (без деревьев):',
              ('Позиция пуска', 'всего за пролёт', 'дольше всего подряд'), rows, (760, 300, 300))
    s.text((60, y - 6), 'ПЗРК — 1 км, стационарный комплекс — 2,5 км (предложение). Лес сократит окна у берега.', 19, MUTED)
    s.im.save(PLANS / 'mission_helicopter_v05_sections.png')


def gap_check():
    """Самый длинный кусок основных путей, где до ближайшего места или остановки дальше 150 м."""
    marks = [VILLAGE, SAWMILL, WAREHOUSE, AD, SAN, S1, S2, HALL, YARD, SWITCH, SERVICE, A, B, N, W, D, C, (0, WEIR_Z, 0)]
    marks = [(m[0], m[1]) for m in marks] + [e[3] for e in EXTRAS if e[0] != 27] + [(q[0], q[1]) for q in crest(-238, 238, 10)]
    marks += [(q[0], q[1]) for q in W_SERP + E_SERP] + [V1, V3, RELAY]
    out = []
    for name, parts, _ in TRAVEL + ESCAPES:
        worst = run = 0.0
        for part in parts:
            pts = sample_route(part, 10)
            for a, b in zip(pts, pts[1:]):
                near = min(math.hypot(b[0] - m[0], b[1] - m[1]) for m in marks)
                run = run + math.hypot(b[0] - a[0], b[1] - a[1]) if near > 150 else 0.0
                worst = max(worst, run)
        out.append((name, worst))
    return out


# ---------- данные стенда ----------
SPECIES = ['spruce_a', 'spruce_b', 'spruce_young', 'pine', 'pine_slim', 'birch']


def polyline_distance(X, Z, lines):
    best = np.full(X.shape, 1e9)
    for line in lines:
        pts = [(float(q[0]), float(q[1])) for q in line]
        for a, b in zip(pts, pts[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            t = np.clip(((X - a[0]) * dx + (Z - a[1]) * dz) / (dx * dx + dz * dz), 0, 1)
            best = np.minimum(best, np.hypot(X - a[0] - t * dx, Z - a[1] - t * dz))
    return best


def slope_of(X, Z):
    e = 2.0
    hx = (heights(X + e, Z)[0] - heights(X - e, Z)[0]) / (2 * e)
    hz = (heights(X, Z + e)[0] - heights(X, Z - e)[0]) / (2 * e)
    return np.hypot(hx, hz)


SHOTS = [
    ('01_плотина_над_лесопилкой', (-300, 140), (0, 450, 170), {'fov': 72}),
    ('02_плотина_над_санаторием', (355, 40), (0, 450, 160), {'fov': 70}),
    ('03_плотина_из_посёлка', (-280, -250), (0, 450, 130), {'fov': 55}),
    ('04_плотина_с_моста_у_машзала', (0, 362, 4.6), (0, 450, 120), {'fov': 80}),
    ('05_долина_и_плотина_с_водослива', (0, WEIR_Z, 7.7), (0, 450, 120), {'fov': 50}),
    ('06_плотина_с_пирса_санатория', (190, 105, 2.6), (0, 450, 150), {'fov': 62}),
    ('07_плотина_от_ОРУ', (200, 300), (0, 450, 150), {'fov': 72}),
    ('08_с_гребня_на_долину', (0, float(arc_z(0, R_ARC - 10.4)), CREST + 1.9), (0, -500, 0), {'fov': 62}),
    ('09_с_гребня_вниз_на_машзал', (0, float(arc_z(0, R_ARC - 10.4)), CREST + 1.9), (0, 360, 0), {'fov': 70}),
    ('10_с_гребня_на_водохранилище', (0, float(arc_z(0, R_ARC - 1)), CREST + 1.7), (0, 1200, 300), {'fov': 62}),
    ('11_вдоль_гребня', (-200, float(arc_z(200, R_ARC - 5)), CREST + 1.7), (200, float(arc_z(200, R_ARC - 5)), CREST), {}),
    ('12_долина_от_старой_ПВО', (AD_BROW[0], AD_BROW[1]), (0, 0, 40), {}),
    ('13_гребень_с_водоприёмной_башни', (120, 520, CREST + 2.2), (-120, 465, CREST), {}),
    ('14_посёлок_с_водонапорной_башни', (-470, -180), (-380, -270, 30), {'up': 26.5}),
    ('15_санаторий_с_пирса', (190, 105, 2.6), (420, 80, 55), {}),
    ('16_склад_за_оградой', (-420, -630), (-520, -660, 155), {}),
    ('17_долина_с_западного_хребта', (V1[0], V1[1]), (100, 300, 100), {}),
    ('18_вертолёт_над_озером_с_гребня', (-150, float(arc_z(150, R_ARC - 10.4)), CREST + 1.9), (-10, 0, 150), {'heli': [-10, 0], 'fov': 45}),
    ('19_вертолёт_над_гребнем_из_санатория', (355, 40), (0, 430, 300), {'heli': [0, 430], 'fov': 60}),
    ('20_с_края_гребня_на_лесопилку', (-225, float(arc_z(225, R_ARC - 10.4)), CREST + 1.9), (-320, 160, 12), {'fov': 66}),
    ('21_с_воздуха_с_севера', (0, -1300, 450), (0, 400, 150), {'fov': 60}),
    ('22_с_воздуха_над_водохранилищем', (0, 950, 520), (0, 0, 0), {'fov': 60}),
    ('23_пункт_сбора_и_плотина', (-330, -60), (0, 450, 150), {'fov': 60}),
    ('24_с_воздуха_у_подножия', (-260, 150, 120), (0, 440, 150), {'fov': 70}),
]
VIEWS = [
    ('гребень_на_долину', (0, CREST_MID[1], CREST + 1.7), (0, -500, 0)),
    ('гребень_на_водохранилище', (0, float(arc_z(0, R_ARC - 1)), CREST + 1.7), (0, 1200, 300)),
    ('пво_у_бровки', (AD_BROW[0], AD_BROW[1]), (0, 0, 40)),
    ('хребет_запад', (V1[0], V1[1]), (100, 300, 100)),
    ('хребет_восток', (V3[0], V3[1]), (-100, 300, 100)),
    ('санаторий_терраса', (355, 40), (0, 450, 160)),
    ('лесопилка', (-300, 140), (0, 450, 170)),
    ('посёлок', (-400, -230), (0, 450, 130)),
    ('лес_на_склоне', (-540, -420), (-400, -300, 120)),
    ('сверху', (0, -200, 1300), (0, -100, 0)),
]


# Ортографические кадры (tools/heli_study.tscn -- ortho): рамка места на плане (центр x, z; ширина, глубина, м), сколько метров
# над низом рамки самое высокое, на какой высоте смотреть, откуда (курс: 0 — с юга, 90 — с востока, 180 — с севера, 270 —
# с запада; None — стенд выбирает сам: со стороны, где склон перед местом не встаёт выше взгляда, и не против солнца),
# наклон взгляда, виды (план сверху, вид под углом); низ рамки — земля в центре или уровень воды (ORTHO_BASE).
ORTHO = [
    ('место_1_посёлок', (-395, -252), 150, 230, 12, 4, None, 38, ['top', 'oblique']),
    ('место_2_лесопилка', (-350, 172), 130, 110, 12, 4, None, 38, ['top', 'oblique']),
    ('место_3_склад_ПЗРК', (-480, -655), 190, 150, 15, 4, None, 38, ['top', 'oblique']),
    ('место_4_старая_ПВО', (440, 380), 150, 130, 12, 4, None, 38, ['top', 'oblique']),
    ('место_5_санаторий', (350, 60), 330, 360, 15, 6, None, 38, ['top', 'oblique']),
    ('место_6_плотина', (0, 440), 620, 170, 270, 130, 180, 25, ['top', 'oblique']),
    ('место_7_ГЭС_у_подножия', (27, 355), 340, 120, 30, 6, 180, 42, ['top', 'oblique']),
    ('место_10_водослив', (0, -705), 220, 150, 10, 2, 180, 38, ['top', 'oblique']),
    ('остановка_08_водоприёмная_башня', (120, 522), 40, 60, 20, 8, 70, 28, ['oblique']),
    ('остановка_09_бетонный_завод', (-230, 305), 90, 70, 30, 10, None, 35, ['oblique']),
    ('остановка_10_кабель-кран', (0, 425), 600, 120, 300, 280, 180, 20, ['oblique']),
    ('остановка_11_водонапорная_башня', (-470, -180), 40, 40, 26, 12, None, 30, ['oblique']),
    ('остановка_12_пожарная_вышка', (-570, -60), 30, 30, 26, 12, None, 30, ['oblique']),
    ('остановка_12_ретранслятор', (568, -560), 30, 30, 42, 18, None, 30, ['oblique']),
    ('остановка_13_служебный_городок', (255, 290), 100, 80, 12, 4, None, 38, ['oblique']),
    ('остановка_14_ЛЭП', (390, 312), 440, 60, 32, 14, 180, 12, ['oblique']),
    ('остановка_15_вагоны_у_лесопилки', (-283, 75), 40, 80, 6, 2, None, 38, ['oblique']),
    ('остановка_16_КПП', (-440, -515), 40, 40, 5, 2, None, 38, ['oblique']),
    ('остановка_17_казармы', (470, 375), 80, 110, 9, 3, None, 38, ['oblique']),
    ('остановка_18_терренкур', (470, -40), 100, 140, 5, 2, None, 38, ['oblique']),
    ('остановка_19_пирс_и_кафе', (240, 100), 100, 100, 7, 2, None, 38, ['oblique']),
    ('остановка_20_дебаркадер', (-80, -658), 190, 40, 6, 2, None, 38, ['oblique']),
    ('остановка_21_рыбацкие_домики', (245, -478), 60, 70, 5, 2, None, 38, ['oblique']),
    ('остановка_22_пункт_сбора', (-320, -32), 90, 60, 5, 2, None, 38, ['oblique']),
    ('остановка_23_лодочная_станция', (-232, -260), 60, 40, 6, 2, None, 38, ['oblique']),
    ('остановка_24_делянка', (-530, -380), 60, 40, 4, 2, None, 38, ['oblique']),
    ('остановка_25_вагон-городок', (-250, 398), 50, 70, 6, 2, 180, 45, ['oblique']),
    ('остановка_28_водозабор', (285, -160), 120, 230, 8, 3, None, 38, ['oblique']),
    ('остановка_29_огороды', (-212, -562), 60, 50, 4, 2, None, 38, ['oblique']),
    ('остановка_30_пост_у_перевала', (382, -678), 40, 40, 4, 2, None, 38, ['oblique']),
]
# низ рамки по уровню воды (над уровнем озера), а не по дну под местом
ORTHO_BASE = {'остановка_08_водоприёмная_башня': 255.0, 'остановка_20_дебаркадер': 0.0}


def places():
    out = [
        ('1 · Посёлок', VILLAGE[:2], (0, 450)),
        ('2 · Лесопилка', SAWMILL[:2], (0, 450)),
        ('3 · Склад ПЗРК', WAREHOUSE[:2], (-440, -520)),
        ('4 · Старая ПВО', AD_BROW, (0, 0)),
        ('5 · Санаторий', (355, 40), (0, 450)),
        ('6 · Гребень плотины', (0, CREST_MID[1], CREST + 1.7), (0, -500)),
        ('7 · Мост у машзала', (0, 362, 4.6), (0, 450)),
        ('8 · Мостик к водоприёмной башне', (120, 500, CREST + 2.6), (120, 540)),
        ('10 · Водослив', (0, WEIR_Z, 7.7), (0, 450)),
        ('Серпантин к гребню (запад)', (-345, 320), (-238, 448)),
        ('V1 · Смотровая, западный хребет', V1, (100, 300)),
        ('V3 · Смотровая, восточный хребет', V3, (-100, 300)),
        ('9 · Бетонный завод', (-200, 300), (-230, 290)),
        ('13 · Служебный городок ГЭС', (SERVICE[0] - 30, SERVICE[1] + 20), SERVICE[:2]),
        ('22 · Пункт сбора «эвакуации»', (-330, -60), (-300, -30)),
        ('24 · Делянка (K1)', (-520, -430), (-530, -380)),
        ('21 · Каменистый берег (K2)', (240, -440), (100, -440)),
        ('K3 · У подножия, восточный берег', (170, 250), (0, 420)),
        ('W · Заход', W[:2], (-300, 60)),
        ('B · Заход', B[:2], (300, -400)),
        ('N · Заход по реке', (0, -1020), (0, -745)),
        ('A · Выход у склада', A[:2], WAREHOUSE[:2]),
        ('D · Выход у санатория', D[:2], SAN[:2]),
        ('C · Тоннель у гребня', (C[0], C[1], C[2] + 1.7), (0, 480)),
    ]
    eye_named = {'4 · Старая ПВО', 'V1 · Смотровая, западный хребет', 'V3 · Смотровая, восточный хребет'}
    res = []
    for n, at, look in out:
        at = list(at)
        if n in eye_named:
            at = at[:2]
        res.append({'name': n, 'at': [float(v) for v in at], 'look': [float(v) for v in look[:2]]})
    return res


def export_data():
    xs4 = np.arange(VIS[0], VIS[1] + STEP / 2, STEP)
    zs4 = np.arange(VIS[2], VIS[3] + STEP / 2, STEP)
    X, Z = np.meshgrid(xs4, zs4)
    h, lake, res = heights(X, Z)
    terrain_dir = ROOT / 'data' / 'terrain'
    terrain_dir.mkdir(parents=True, exist_ok=True)
    h.astype('<f4').tofile(terrain_dir / 'heli_v05_heights.r32')
    road = polyline_distance(X, Z, ROADS + SERPENTINES)
    trail = polyline_distance(X, Z, TRAILS)
    mud = np.clip(1 - np.abs(h - 1.0) / 3.0, 0, 1) * (~lake) + np.clip(1 - trail / 2.5, 0, 1)
    rock = np.clip((h - 660) / 80, 0, 1) + np.clip(1 - np.abs(h - RES_LEVEL - 4) / 6, 0, 1) * (~res) * 0.6
    gravel = np.clip(1 - (road - 3.5) / 2.5, 0, 1)
    for x, z, r in ((0, 380, 90), (YARD[0], YARD[1], 40), (SWITCH[0], SWITCH[1], 60), (WAREHOUSE[0], WAREHOUSE[1], 80),
                    (AD[0], AD[1], 55), (SAWMILL[0], SAWMILL[1], 60), (SERVICE[0], SERVICE[1], 50), (-230, 300, 45),
                    (-262, 420, 18), (262, 420, 18)):
        gravel = np.maximum(gravel, np.clip(1 - (np.hypot(X - x, Z - z) - r) / 10, 0, 1) * 0.8)
    floor_ = np.clip((h - 8) / 20, 0, 1) * np.clip((700 - h) / 60, 0, 1) * (1 - gravel)
    rgba = np.stack([mud, rock, gravel, floor_], -1)
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), 'RGBA').save(terrain_dir / 'heli_v05_splat.png')
    # лес: дрожащая сетка, ядро чаще; не на воде, дорогах, площадках, у плотины и в местах съёмки
    rng = np.random.default_rng(5)
    keep_out = [(x, z, r) for x, z, _, r, _ in PADS] + [(e[3][0], e[3][1], 22.0) for e in EXTRAS]
    keep_out += [(v[0], v[1], 26.0) for v in (V1, V3, AD_BROW)]
    keep_out += [(at[0], at[1], 16.0) for _, at, _, _ in SHOTS if len(at) == 2]
    points = {}
    totals = {'core': 0, 'bg': 0}
    for spacing, part in ((6.5, 'core'), (9.0, 'bg')):
        gx = np.arange(VIS[0], VIS[1], spacing)
        gz = np.arange(VIS[2], VIS[3], spacing)
        PX, PZ = np.meshgrid(gx, gz)
        PX = PX + rng.uniform(-0.45, 0.45, PX.shape) * spacing
        PZ = PZ + rng.uniform(-0.45, 0.45, PZ.shape) * spacing
        w = WALKABLE
        core = (PX > w[0] - 40) & (PX < w[1] + 40) & (PZ > w[2] - 40) & (PZ < w[3] + 40)
        sel = core if part == 'core' else ~core
        PX, PZ = PX[sel], PZ[sel]
        ph, plake, pres = heights(PX, PZ)
        slope = slope_of(PX, PZ)
        ok = (~plake) & (~pres) & (ph > 1.5) & (ph < 720) & (slope < (1.05 if part == 'core' else 1.2))
        ok &= polyline_distance(PX, PZ, ROADS + SERPENTINES) > 7.0
        ok &= polyline_distance(PX, PZ, TRAILS) > 2.5
        ok &= polyline_distance(PX, PZ, [RAIL]) > 5.0
        for x, z, r in keep_out:
            ok &= np.hypot(PX - x, PZ - z) > r + 6
        ok &= ~((np.abs(PX) < 290) & (PZ > 330) & (PZ < 520))
        ok &= np.abs(ph - RES_LEVEL) > 4
        prob = np.full(PX.shape, 0.85)
        for x, z, _ in (VILLAGE, SAN, SAWMILL):
            prob = np.where(np.hypot(PX - x, PZ - z) < 230, 0.3, prob)
        ok &= rng.random(PX.shape) < prob
        PX, PZ, ph, slope = PX[ok], PZ[ok], ph[ok], slope[ok]
        roll = rng.random(PX.shape)
        near_people = np.zeros(PX.shape, bool)
        for x, z, _ in (VILLAGE, SAN, SAWMILL):
            near_people |= np.hypot(PX - x, PZ - z) < 420
        kind = np.where(roll < 0.35, 'spruce_a', np.where(roll < 0.7, 'spruce_b', 'spruce_young'))
        kind = np.where((ph > 330) | (slope > 0.6), np.where(roll < 0.6, 'pine', 'pine_slim'), kind)
        kind = np.where(near_people & (ph < 140) & (roll < 0.5), 'birch', kind)
        rot = rng.uniform(0, 360, PX.shape)
        scale = rng.uniform(0.8, 1.2, PX.shape)
        for k_ in SPECIES:
            m = kind == k_
            key = k_ if part == 'core' else k_ + '_bg'
            points[key] = [[round(float(a), 2), round(float(b) + Y_OFFSET - 0.1, 2), round(float(c), 2), round(float(r), 1),
                            round(float(sc), 3)] for a, b, c, r, sc in zip(PX[m], ph[m], PZ[m], rot[m], scale[m])]
            totals[part] += int(m.sum())
    (ROOT / 'data' / 'blockouts' / 'heli_v05_vegetation.json').write_text(
        json.dumps(points, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    # вода: нижнее озеро, водохранилище, реки; невидимые стенки по берегам
    lower = [[float(x), float(z)] for z, x in WEST] + [[float(x), float(z)] for z, x in EAST[::-1]]
    ang = math.asin(240 / R_ARC)
    reservoir = [[float(R_ARC * math.sin(a)), float(CZ + R_ARC * math.cos(a))] for a in np.linspace(-ang, ang, 25)]
    zr = np.arange(445, 1501, 25)
    reservoir += [[float(np.interp(z, RES_AXIS[:, 0], RES_AXIS[:, 1]) + np.interp(z, RES_HALF[:, 0], RES_HALF[:, 1])), float(z)] for z in zr]
    reservoir += [[float(np.interp(z, RES_AXIS[:, 0], RES_AXIS[:, 1]) - np.interp(z, RES_HALF[:, 0], RES_HALF[:, 1])), float(z)] for z in zr[::-1]]
    zb = np.arange(445, WALKABLE[3] + 1, 20)
    barriers = [
        {'points': [[float(x) + 1.5, float(z)] for z, x in WEST], 'bottom': -4.0, 'top': 0.25},
        {'points': [[float(x) - 1.5, float(z)] for z, x in EAST], 'bottom': -4.0, 'top': 0.25},
        {'points': [[float(WEST[-1][1]), TOE_Z - 1.5], [float(EAST[-1][1]), TOE_Z - 1.5]], 'bottom': -4.0, 'top': 0.25},
        {'points': [[float(WEST[0][1]) - 30, WEIR_Z + 8], [float(EAST[0][1]) + 30, WEIR_Z + 8]], 'bottom': -4.0, 'top': 7.5},
        {'points': [[float(np.interp(z, RES_AXIS[:, 0], RES_AXIS[:, 1]) + np.interp(z, RES_HALF[:, 0], RES_HALF[:, 1])) - 1.5, float(z)]
                    for z in zb], 'bottom': RES_LEVEL - 4, 'top': RES_LEVEL + 0.25},
        {'points': [[float(np.interp(z, RES_AXIS[:, 0], RES_AXIS[:, 1]) - np.interp(z, RES_HALF[:, 0], RES_HALF[:, 1])) + 1.5, float(z)]
                    for z in zb], 'bottom': RES_LEVEL - 4, 'top': RES_LEVEL + 0.25},
    ]
    plan = {
        'name': 'Вертолёт · v05 · плотина над долиной · серый стенд',
        'y_offset': Y_OFFSET,
        'terrain': {'heights': 'res://data/terrain/heli_v05_heights.r32', 'origin': [VIS[0], VIS[2]], 'grid': [xs4.size, zs4.size],
                    'step': STEP, 'layer_tiles': [3.0, 3.0, 2.5, 3.0, 4.0, 2.0],
                    'textures': {'albedo_array': 'res://assets/terrain/zone01_albedo.jpg',
                                 'normal_array': 'res://assets/terrain/zone01_normal.jpg',
                                 'arm_array': 'res://assets/terrain/zone01_arm.jpg',
                                 'noise': 'res://assets/terrain/zone01_noise.png'},
                    'splat_file': 'res://data/terrain/heli_v05_splat.png'},
        'walkable': list(WALKABLE),
        'water': [{'name': 'Lake', 'level': 0.0, 'poly': lower}, {'name': 'Reservoir', 'level': RES_LEVEL, 'poly': reservoir}],
        'rivers': [{'name': 'RiverNorth', 'width': 26.0, 'points': [[float(x), float(z)] for z, x in NORTH_RIVER[::-1]]},
                   {'name': 'Outflow', 'width': 40.0, 'points': [[0.0, 412.0], [0.0, 362.0]]}],
        'barriers': barriers,
        'dam': {'center': [0.0, CZ], 'dir': 1, 'radius': R_ARC, 'half_angle_deg': math.degrees(math.asin(265 / R_ARC)),
                'crest': CREST, 'foot': FOOT, 'thick_top': 10.0, 'thick_base': 60.0, 'parapet': 1.1},
        'structures': structures(),
        'places': places(),
        'views': [{'name': n, 'at': [float(v) for v in at], 'look': [float(v) for v in look]} for n, at, look in VIEWS],
        'shots': [dict({'name': n, 'at': [float(v) for v in at], 'look': [float(v) for v in look]}, **extra)
                  for n, at, look, extra in SHOTS],
        'ortho': [{'name': n, 'center': [float(c[0]), float(c[1])], 'w': float(w), 'h': float(h), 'top': float(top),
                   'focus': float(focus), 'yaw': None if yaw is None else float(yaw), 'pitch': float(pitch), 'views': views,
                   'base': ORTHO_BASE.get(n)}
                  for n, c, w, h, top, focus, yaw, pitch, views in ORTHO],
        'heli': [[float(v) for v in q] for q in HELI],
        'heli_speed': HELI_SPEED,
        'plan_image': 'res://docs/plans/mission_helicopter_v05_plan_core.png',
        'plan_image_rect': [WALKABLE[0] - 20, WALKABLE[2] - 20, WALKABLE[1] + 20, WALKABLE[3] + 30],
        'trees': totals,
    }
    (ROOT / 'data' / 'blockouts' / 'heli_v05.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8',
                                                               newline='\n')
    print(f'данные v05: рельеф {xs4.size}×{zs4.size}, деревьев: ядро {totals["core"]}, фон {totals["bg"]}, '
          f'построек {len(plan["structures"])}')


def main():
    args = set(sys.argv[1:]) or {'plans', 'data'}
    if 'plans' in args:
        travel = [route_row(n, parts, e) for n, parts, e in TRAVEL]
        escapes = [route_row(n, parts, e) for n, parts, e in ESCAPES]
        heli = heli_rows()
        for r in travel + escapes:
            print(f'{r[0]}: {r[1]:.0f} м, подъём {r[2]:.0f} м, бегом {r[3] / 60:.1f} мин, шагом {r[4] / 60:.1f} мин')
        print('вертолёт над долиной, с:', heli[0], 'V1', V1, 'V3', V3, 'бровка ПВО', AD_BROW)
        for n, lock, run in heli[1]:
            print(f'  {n}: {lock} с, подряд {run} с')
        for name, dist, deg in dam_angles():
            print(f'  гребень с {name}: {dist:.0f} м, {deg:.1f}°')
        for name, (x, z, y) in (('посёлок', VILLAGE), ('лесопилка', SAWMILL), ('склад', WAREHOUSE), ('ПВО', AD),
                                ('санаторий', SAN), ('A', A), ('B', B), ('W', W), ('D', D), ('C', C)):
            print(f'  высота {name}: по плану {y}, рельеф {h_at(x, z):.0f}')
        for name, worst in gap_check():
            print(f'  пусто дольше 150 м от мест: {name}: {worst:.0f} м')
        plan_sheet()
        sections_sheet(travel, escapes, heli)
    if 'data' in args:
        export_data()


if __name__ == '__main__':
    main()
