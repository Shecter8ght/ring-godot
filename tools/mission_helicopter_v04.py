# -*- coding: utf-8 -*-
"""Карта «Вертолёт» — предложение v04 «карта вокруг плотины» (Claude, 2026-11-06), на обсуждение.

Схемы и расчёты (пути, уход к выходам, окна видимости вертолёта, пустые отрезки) → docs/plans/mission_helicopter_v04_*.png.
Тот же рельеф и места выгружает в серый стенд tools/mission_helicopter_v04_data.py (tools/heli_study.tscn).
Рельеф — аналитический набросок для замеров, не готовая форма; сюжет и места — предложения (docs/design/mission_helicopter.md).
  python -X utf8 tools/mission_helicopter_v04.py [папка вывода]
"""
import math
import sys
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if __name__ == '__main__' and len(sys.argv) > 1 else ROOT / 'docs' / 'plans'
FONT = 'C:/Windows/Fonts/arial.ttf'
BOLD = 'C:/Windows/Fonts/arialbd.ttf'
INK = '#24372e'
MUTED = '#52685b'
PAPER = '#f4f1e7'
ORANGE = '#bd642f'
RED = '#a8322a'
ROAD = '#6f7468'
TRAIL = '#f1e2b8'
PHASE2 = '#8a7a5a'

SPRINT_MIX = 4.4      # бег с передышками без груза: 5,2 м/с, спринт ~36 с, затем шаг до порога 25 %
WALK = 1.82
HELI_SPEED = 42.0     # ~150 км/ч
MANPADS_RANGE = 1000.0
STATIC_RANGE = 2500.0
LIFT_SEC = 60.0

VIS = (-1000.0, 1000.0, -1500.0, 1500.0)      # видимый мир — рамка v02 2 × 3 км
WALKABLE = (-600.0, 600.0, -400.0, 1200.0)    # ядро у плотины: 1,2 × 1,6 км
PHASE2_BOX = (-750.0, 750.0, -1100.0, -400.0)  # вторая очередь: северные берега и мост у хвоста
CELL = 2.0

WEST = np.array([(-820, -30), (-700, -110), (-520, -170), (-300, -215), (-120, -205), (40, -235),
                 (160, -200), (250, -285), (330, -300), (400, -235), (445, -222)], float)
EAST = np.array([(-820, 30), (-690, 115), (-520, 195), (-330, 230), (-150, 210), (0, 185),
                 (110, 235), (260, 250), (380, 232), (445, 222)], float)
APEX = 395.0
CHORD_HALF = 222.0
SAG = 50.0
R_ARC = (CHORD_HALF ** 2 + SAG ** 2) / (2 * SAG)
GORGE = np.array([(445, 0), (600, -20), (700, -50), (800, -40), (900, -20), (1000, -60),
                  (1100, -100), (1300, -130), (1500, -150)], float)
NORTH_RIVER = np.array([(-1500, 40), (-1300, -20), (-1100, 10), (-950, -10), (-820, 0)], float)

# Места (x, z, высота)
VILLAGE = (-380, 120, 30)
SAWMILL = (-330, 300, 12)
WAREHOUSE = (-480, -250, 150)
AD = (450, 520, 230)
SAN = (390, 60, 60)
A = (-580, -380, 200)
B = (580, -380, 200)
W = (-600, 580, 180)
D = (600, 780, 200)
C = (-100, 1180, -263)

PADS = [
    (VILLAGE[0], VILLAGE[1], VILLAGE[2], 80, 160),
    (SAWMILL[0], SAWMILL[1], SAWMILL[2], 60, 120),
    (WAREHOUSE[0], WAREHOUSE[1], WAREHOUSE[2], 70, 140),
    (AD[0], AD[1], AD[2], 55, 120),
    (SAN[0], SAN[1], SAN[2], 110, 200),
    (-95, 620, -247, 40, 70),     # служебный двор ГЭС
    (-238, 452, 10, 22, 60),      # примыкания плотины: гребень выходит на скалу
    (238, 452, 10, 22, 60),
    (115, 700, -232, 50, 80),     # ОРУ на полке
]
VALLEYS = [
    ([(-210, -150, 3), (-420, -260, 120), (A[0], A[1], A[2]), (-800, -700, 330)], 30, 0.9),
    ([(210, -200, 3), (420, -300, 120), (B[0], B[1], B[2]), (800, -700, 330)], 30, 0.9),
    ([(-225, 120, 0), (-380, 120, 30), (-560, 60, 180), (-800, 0, 400)], 22, 1.0),
    ([(-300, 330, 10), (-460, 440, 90), (W[0], W[1], W[2]), (-800, 800, 330)], 25, 1.0),
    ([(AD[0], AD[1], AD[2] - 15), (520, 650, 212), (D[0], D[1], D[2]), (800, 950, 330)], 25, 1.0),
]


def clip(a, lo=0.0, hi=1.0):
    return np.clip(a, lo, hi)


def smooth(e0, e1, x):
    t = clip((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def arc_z(x):
    x = np.asarray(x, float)
    return APEX + R_ARC - np.sqrt(np.maximum(R_ARC ** 2 - x ** 2, 0.0))


def heights(X, Z):
    ax = np.abs(X)
    wig = 55 * np.sin(Z / 260 + 0.7 + np.sign(X) * 1.3) + 30 * np.sin(Z / 110 + np.sign(X))
    axm = np.maximum(ax + wig, 0)
    mount = 350 * clip((axm - 260) / 440) ** 1.35 + 650 * clip((axm - 700) / 300) ** 1.6
    mount = mount + (22 * np.sin(X / 83 + Z / 61) + 14 * np.sin(X / 41 - Z / 57)) * clip(mount / 250)
    vf = clip((-820 - Z) / 680) * 200
    xw = np.interp(Z, WEST[:, 0], WEST[:, 1])
    xe = np.interp(Z, EAST[:, 0], EAST[:, 1])
    d = np.where(X < xw, xw - X, np.where(X > xe, X - xe, 0.0))
    north = Z < -820
    xrn = np.interp(Z, NORTH_RIVER[:, 0], NORTH_RIVER[:, 1])
    d = np.where(north, np.maximum(np.abs(X - xrn) - 12, 0), d)
    noise = 6 * np.sin(X / 37 + Z / 53) + 4 * np.sin(X / 19 - Z / 27) + 10 * np.sin(X / 151 + Z / 97)
    near = 6 * clip(d / 30) + 0.06 * d
    hn = np.maximum(near, mount) + vf + noise * clip(d / 80)
    boundary = np.where(ax < CHORD_HALF, arc_z(np.minimum(ax, CHORD_HALF)), 445.0)
    south = Z > boundary
    rr = np.abs(X - np.interp(Z, GORGE[:, 0], GORGE[:, 1]))
    plateau = np.maximum(mount, 10 + 140 * clip((Z - 445) / 600)) + noise * clip((rr - 260) / 80)
    floor = -250 - 0.012 * (Z - 470)
    # у плотины ущелье уже (край на уровне гребня там, где кончается арка), ниже по течению — шире
    wall = 150 + 40 * clip((Z - 445) / 150)
    t = clip((rr - 70) / wall)
    hs = np.where(rr < 70, floor, floor + (plateau - floor) * t ** 0.55)
    hs = np.where(rr >= 70 + wall, plateau, hs)
    h = np.where(south, hs, hn)
    for pts, w0, slope in VALLEYS:
        for a, b in zip(pts, pts[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            t = clip(((X - a[0]) * dx + (Z - a[1]) * dz) / (dx * dx + dz * dz))
            dist = np.hypot(X - a[0] - t * dx, Z - a[1] - t * dz)
            carve = a[2] + t * (b[2] - a[2]) + slope * np.maximum(dist - w0, 0)
            h = np.minimum(h, carve)
    for px, pz, py, r0, r1 in PADS:
        w = 1 - smooth(r0, r1, np.hypot(X - px, Z - pz))
        h = h * (1 - w) + py * w
    lake = (~south) & (X > xw) & (X < xe) & (Z > -820)
    return np.where(lake, 0.0, h), lake


xs = np.arange(VIS[0], VIS[1], CELL) + CELL / 2
zs = np.arange(VIS[2], VIS[3], CELL) + CELL / 2
GX, GZ = np.meshgrid(xs, zs)
H, LAKE = heights(GX, GZ)


def h_at(x, z):
    fx = (x - VIS[0]) / CELL - 0.5
    fz = (z - VIS[2]) / CELL - 0.5
    i0 = int(np.clip(math.floor(fx), 0, H.shape[1] - 2))
    j0 = int(np.clip(math.floor(fz), 0, H.shape[0] - 2))
    tx = min(max(fx - i0, 0.0), 1.0)
    tz = min(max(fz - j0, 0.0), 1.0)
    a = H[j0, i0] * (1 - tx) + H[j0, i0 + 1] * tx
    b = H[j0 + 1, i0] * (1 - tx) + H[j0 + 1, i0 + 1] * tx
    return a * (1 - tz) + b * tz


def crest(x_from, x_to, n=12, y=10.0, dz=0.0):
    return [(x, float(arc_z(abs(x))) + dz, y) for x in np.linspace(x_from, x_to, n)]


# ---------- маршруты ----------
TO_W_ABUT = [VILLAGE, (-360, 260, 20), SAWMILL, (-300, 380, 10), (-225, 448, 10)]
E_ABUT_TO_SAN = [(225, 448, 10), (300, 350, 25), (330, 220, 40), SAN]
STAIRS = [(-250, 480, 10), (-200, 520, -40), (-250, 560, -90), (-190, 600, -140), (-230, 640, -190),
          (-150, 650, -245)]
ROUTE_CREST = TO_W_ABUT + crest(-222, 222) + E_ABUT_TO_SAN
ROUTE_GALLERY = (TO_W_ABUT + [(-260, 500, -20), (-215, 478, -60)] + crest(-215, 215, 12, -60.0, 20.0)
                 + [(215, 500, -35), (205, 468, 10)] + E_ABUT_TO_SAN)
ROUTE_LOW_A = TO_W_ABUT + STAIRS + [(-95, 620, -247), (-40, 560, -250), (40, 560, -250), (200, 470, -250)]
ROUTE_LOW_B = [(200, 470, 10)] + E_ABUT_TO_SAN
R_A_WAREHOUSE = [A, (-520, -320, 175), WAREHOUSE]
R_B_SAN = [B, (420, -300, 120), (260, -200, 15), (300, -60, 35), SAN]
R_D_AD = [D, (520, 650, 212), AD]
R_W_WAREHOUSE = [W, (-460, 440, 90), (-360, 260, 20), VILLAGE, (-400, 40, 40), (-470, -50, 75), (-430, -150, 110),
                 WAREHOUSE]
R_B_AD = [B, (560, -250, 215), (540, 100, 190), (560, 350, 215), AD]
R_C_HALL = [C, (-20, 900, -256), (-40, 700, -252), (0, 560, -250), (0, 500, -250)]
R_WH_VILLAGE = [WAREHOUSE, (-430, -150, 110), (-470, -50, 75), (-400, 40, 40), VILLAGE]

TRAVEL = [
    ('Посёлок → санаторий по гребню (открыто)', [ROUTE_CREST], 0.0),
    ('Посёлок → санаторий галереей −60 (внутри плотины)', [ROUTE_GALLERY], 0.0),
    ('Посёлок → санаторий низом: лестница, мост у ГЭС, лифт', [ROUTE_LOW_A, ROUTE_LOW_B], LIFT_SEC),
    ('Заход W → склад ПЗРК (мимо посёлка)', [R_W_WAREHOUSE], 0.0),
    ('Заход B → старая ПВО (тропой по хребту)', [R_B_AD], 0.0),
    ('Заход B → санаторий', [R_B_SAN], 0.0),
    ('Заход C → машзал ГЭС', [R_C_HALL], 0.0),
]
ESCAPES = [
    ('Старая ПВО → D', [list(reversed(R_D_AD))], 0.0),
    ('Санаторий → B', [list(reversed(R_B_SAN))], 0.0),
    ('Посёлок → W', [[VILLAGE, (-360, 260, 20), (-460, 440, 90), W]], 0.0),
    ('Посёлок → A через склад', [list(reversed(R_WH_VILLAGE)) + [(-520, -320, 175), A]], 0.0),
    ('Середина гребня → W', [crest(0, -222, 6) + [(-300, 380, 10), (-460, 440, 90), W]], 0.0),
    ('Середина гребня → C лифтом', [crest(0, 200, 6) + [(200, 470, 10)],
                                   [(200, 470, -250), (100, 520, -250), (0, 560, -250), (-40, 700, -252),
                                    (-20, 900, -256), C]], LIFT_SEC),
    ('Западный берег у бонов → A', [[(-210, -330, 3), (-420, -260, 120), A]], 0.0),
    ('Восточный берег у бонов (K2) → B', [[(225, -250, 3), (420, -300, 120), B]], 0.0),
]


def length3(path):
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))


def climb(path):
    return sum(max(0.0, b[2] - a[2]) for a, b in zip(path, path[1:]))


def route_row(name, parts, extra):
    m = sum(length3(p) for p in parts)
    up = sum(climb(p) for p in parts)
    return name, m, up, m / SPRINT_MIX + extra, m / WALK + extra


# ---------- вертолёт ----------
HELI = [(0, -1700, 320), (0, -1100, 230), (-20, -880, 170), (10, -600, 150), (-10, -300, 145), (10, 0, 140),
        (0, 250, 125), (0, 390, 80), (-20, 600, 30), (-50, 800, 0), (-40, 1000, -20), (-100, 1300, -40),
        (-150, 1700, -40)]


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


V1 = best_spot(-520, -60, 100, 1.7)
V3 = best_spot(520, -120, 80, 1.7)
AD_BROW = best_spot(AD[0], AD[1], 60, 1.7)
SHOOTERS = [
    ('Старая ПВО у бровки, комплекс 2,5 км', AD_BROW[0], AD_BROW[1], 4.0, STATIC_RANGE),
    ('Старая ПВО у бровки, ПЗРК с плеча', AD_BROW[0], AD_BROW[1], 1.7, MANPADS_RANGE),
    ('Старая ПВО в середине площадки, комплекс', AD[0], AD[1], 4.0, STATIC_RANGE),
    ('Крыша жилого корпуса санатория', 330, -40, 12.0, MANPADS_RANGE),
    ('Посёлок, берег', -250, 140, 1.7, MANPADS_RANGE),
    ('Середина гребня плотины', 0, 395, 1.7, MANPADS_RANGE),
    ('Западный берег у бонов', -205, -340, 1.7, MANPADS_RANGE),
    ('Смотровая V1, западный хребет', V1[0], V1[1], 1.7, MANPADS_RANGE),
    ('Смотровая V3, восточный хребет', V3[0], V3[1], 1.7, MANPADS_RANGE),
    ('Служебный двор ГЭС (дно ущелья)', -95, 620, 1.7, MANPADS_RANGE),
]


def heli_rows():
    inside = sum(1 for p in HELI_PTS if WALKABLE[0] <= p[0] <= WALKABLE[1] and WALKABLE[2] <= p[1] <= WALKABLE[3])
    rows = []
    for name, ex, ez, up, rng in SHOOTERS:
        lock, best = window((ex, ez, h_at(ex, ez) + up), rng)
        rows.append((name, lock, best))
    return inside, rows


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


def in_box(box):
    return (GX >= box[0]) & (GX <= box[1]) & (GZ >= box[2]) & (GZ <= box[3])


def colorize(h, lake):
    stops_h = [-270, -120, 0, 60, 150, 260, 360, 520, 900]
    stops_c = [(196, 186, 160), (190, 186, 160), (214, 224, 196), (196, 214, 174), (172, 196, 150),
               (160, 182, 142), (170, 172, 150), (178, 176, 166), (214, 212, 206)]
    rgb = np.stack([np.interp(h, stops_h, [c[k] for c in stops_c]) for k in range(3)], -1)
    gz, gx = np.gradient(h, CELL)
    n = np.stack([-gx, np.ones_like(h), -gz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    light = np.array([-0.55, 0.65, -0.52])
    light /= np.linalg.norm(light)
    shade = np.clip((n * light).sum(-1), 0, 1)
    rgb *= (0.55 + 0.6 * shade)[..., None]
    for step, dark in ((50, 0.88), (250, 0.7)):
        c = np.floor(h / step)
        edge = np.zeros_like(h, bool)
        edge[:, 1:] |= c[:, 1:] != c[:, :-1]
        edge[1:, :] |= c[1:, :] != c[:-1, :]
        rgb[edge & ~lake] *= dark
    rgb[lake] = (143, 184, 189)
    paper = np.array([228, 225, 214], float)
    core = in_box(WALKABLE)
    later = in_box(PHASE2_BOX) & ~core
    rest = ~core & ~later
    rgb[later] = rgb[later] * 0.7 + paper * 0.3
    rgb[rest] = rgb[rest] * 0.42 + paper * 0.58
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB')



EXTRA = (150, 95, 55)
# Остановки между местами: номер, подпись в списке, цена, точка для проверки пустых отрезков, где номер на плане.
EXTRAS = [
    (8, 'Водоприёмная башня в озере: шахта в тоннель к машзалу, ПЗРК над водой', 'L', (150, 360), (120, 320)),
    (9, 'Бетонный завод стройки: силосы над гребнем, держат переход', 'L', (-300, 480), (-360, 470)),
    (10, 'Кабель-кран стройки: башни на краях ущелья, трос с бадьёй', 'M', (0, 540), (250, 595)),
    (11, 'Водонапорная башня посёлка, вид на озеро', 'S', (-470, 170), (-515, 170)),
    (12, 'Пожарная вышка (запад) и ретранслятор (восток, запасной блок)', 'S', (-570, 330), (-570, 375)),
    (13, 'Служебный городок ГЭС: пульт — блок для ПВО, автобаза — топливо', 'M–L', (360, 320), (420, 320)),
    (14, 'ЛЭП от ОРУ вверх по склону к подстанции у выхода D', 'S', (360, 712), (360, 670)),
    (15, 'Ж/д ветка к тоннелю C: вагоны, трансформатор на платформе', 'M', (40, 815), (95, 790)),
    (16, 'КПП части ПВО на въезде к складу, его держат мародёры', 'S', (-440, -170), (-395, -185)),
    (17, 'Казармы части у старой ПВО: 2–3 здания, столовая, гараж', 'M', (530, 595), (575, 560)),
    (18, 'Терренкур санатория: лечебная тропа с беседками к хребту', 'S', (465, -80), (510, -80)),
    (19, 'Пирс, лодочная станция и пляжное кафе санатория', 'S', (225, 90), (195, 130)),
    (20, 'Дебаркадер у бонов: весь вид на озеро, укрыться негде', 'S', (-120, -365), (-120, -325)),
    (21, 'Рыбацкие домики и гидропост на каменистом берегу (K2)', 'S', (250, -295), (300, -320)),
    (22, 'Пункт сбора «эвакуации»: автобусы, палатки, сумки — сюжет', 'S–M', (-430, 240), (-480, 270)),
    (23, 'Лодочная станция посёлка у запани: запасное топливо', 'S', (-262, 200), (-215, 205)),
    (24, 'Делянка лесорубов на склоне: вырубка, штабеля (K1)', 'S', (-515, -85), (-470, -95)),
    (25, 'Вагон-городок строителей ниже ОРУ (K3)', 'S', (-80, 990), (-130, 1000)),
    (26, 'Штольни в стенах ущелья: тайники, одна — в галерею', 'S', (-150, 760), (-195, 760)),
    (27, 'Колокольня затопленного села — только с решения владельца', '—', (-70, -150), (-135, -185)),
]


def draw_extras(s, p, k):
    d = s.d
    ink = INK
    stone = (200, 196, 186)

    def rect(x, z, w, l, fill=(236, 228, 205), outline=(130, 110, 82)):
        d.rectangle([p(x - w / 2, z - l / 2), p(x + w / 2, z + l / 2)], fill=fill, outline=outline)

    def dot(x, z, r, fill, outline=ink):
        c = p(x, z)
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=fill, outline=outline)

    # 8 башня, мостик, тоннель под плотиной
    s.dashed([p(150, 360), p(110, 440), p(60, 505)], ink, 2, (6, 6))
    d.line([p(150, 360), p(236, 350)], fill=ink, width=3)
    dot(150, 360, 8, stone)
    # 9 бетонный завод: силосы, цех, транспортёр к плотине
    d.line([p(-290, 480), p(-228, 452)], fill=(120, 110, 95), width=3)
    rect(-300, 505, 44, 20, stone, ink)
    for x in (-322, -306, -290):
        dot(x, 478, 5, (215, 212, 205))
    # 10 кабель-кран: башни, трос, бадья
    d.line([p(-290, 540), p(290, 540)], fill=(60, 60, 60), width=1)
    for x in (-290, 290):
        c = p(x, 540)
        d.rectangle([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=(90, 90, 90), outline=ink)
    c = p(0, 540)
    d.rectangle([c[0] - 3, c[1] - 2, c[0] + 3, c[1] + 4], fill=(160, 70, 40))
    # 11 водонапорная башня
    dot(-470, 170, 5, stone)
    # 12 пожарная вышка и ретранслятор
    for x, z in ((-570, 330), (540, -120)):
        c = p(x, z)
        d.polygon([(c[0], c[1] - 8), (c[0] - 6, c[1] + 5), (c[0] + 6, c[1] + 5)], outline=ink, fill=(200, 190, 170))
    # 13 служебный городок ГЭС
    rect(360, 315, 40, 18, stone, ink)
    rect(398, 300, 26, 14)
    rect(340, 352, 16, 8, (210, 120, 70), ink)
    # 14 ЛЭП и подстанция
    towers = [(115, 700), (210, 706), (310, 712), (410, 716), (510, 712), (570, 705)]
    d.line([p(*t) for t in towers], fill=(80, 80, 80), width=1)
    for t in towers[1:-1]:
        c = p(*t)
        d.line([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=ink, width=2)
        d.line([c[0] - 4, c[1] + 4, c[0] + 4, c[1] - 4], fill=ink, width=2)
    rect(575, 705, 30, 24, (210, 210, 205), ink)
    # 15 ж/д ветка с вагонами
    rail = [(48, 530), (38, 700), (48, 900), (-20, 1100), (-100, 1180)]
    d.line([p(*q) for q in rail], fill=(70, 60, 50), width=2)
    for a, b in zip(rail, rail[1:]):
        n = int(math.dist(a, b) / 25)
        for i in range(n):
            t = i / n
            x, z = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            c = p(x, z)
            d.line([c[0] - 3, c[1], c[0] + 3, c[1]], fill=(70, 60, 50), width=1)
    for z in (775, 800, 825):
        rect(40, z, 7, 20, (120, 90, 70), ink)
    # 16 КПП
    rect(-440, -170, 10, 8, stone, ink)
    d.line([p(-455, -160), p(-425, -160)], fill=(200, 40, 40), width=3)
    # 17 казармы
    for x, z, w, l in ((520, 582, 34, 12), (548, 605, 30, 12), (515, 620, 20, 10)):
        rect(x, z, w, l)
    # 18 терренкур с беседками
    path = [(400, 20), (450, -20), (470, -80), (455, -140), (440, -200)]
    s.dashed([p(*q) for q in path], (120, 150, 80), 3, (4, 5))
    for q in path[1:]:
        dot(q[0], q[1], 4, (240, 235, 220))
    # 19 пирс, лодочная станция, кафе
    d.line([p(238, 92), p(180, 92)], fill=(120, 95, 70), width=4)
    rect(244, 60, 14, 10)
    rect(262, 125, 12, 10)
    # 20 дебаркадер и понтоны
    s.dashed([p(-205, -360), p(-140, -365)], (120, 95, 70), 3, (6, 4))
    rect(-120, -365, 40, 12, (220, 215, 205), ink)
    # 21 рыбацкие домики и гидропост
    rect(255, -300, 8, 6)
    rect(262, -278, 8, 6)
    dot(235, -330, 4, (240, 240, 240))
    # 22 пункт сбора: автобусы и палатки
    for x in (-410, -390):
        rect(x, 252, 4, 12, (210, 180, 60), ink)
    for x, z in ((-450, 228), (-438, 238), (-455, 248), (-443, 220)):
        c = p(x, z)
        d.polygon([(c[0], c[1] - 4), (c[0] - 4, c[1] + 3), (c[0] + 4, c[1] + 3)], fill=(110, 140, 110))
    # 23 лодочная станция посёлка
    rect(-262, 200, 14, 10)
    d.line([p(-252, 200), p(-225, 200)], fill=(120, 95, 70), width=3)
    # 24 делянка: вырубка и штабеля
    d.polygon([p(-570, -115), p(-480, -125), p(-468, -55), p(-560, -45)], fill=(205, 196, 160), outline=(150, 130, 90))
    for x in (-540, -520, -500):
        rect(x, -90, 10, 4, (170, 130, 80), None)
    # 25 вагон-городок
    for z in (975, 995, 1015):
        rect(-82, z, 22, 9)
    # 26 штольни
    for x, z in ((-150, 760), (105, 830)):
        c = p(x, z)
        d.pieslice([c[0] - 6, c[1] - 6, c[0] + 6, c[1] + 6], 180, 360, fill=(60, 55, 50))
    # 27 колокольня — по решению владельца
    c = p(-70, -150)
    s.dashed([(c[0] - 8, c[1] - 8), (c[0] + 8, c[1] - 8), (c[0] + 8, c[1] + 8), (c[0] - 8, c[1] + 8),
              (c[0] - 8, c[1] - 8)], (150, 95, 55), 2, (3, 3))
    # номера
    for n, _, _, _, (lx, lz) in EXTRAS + [(12, '', '', None, (585, -150))]:
        c = p(lx, lz)
        d.ellipse([c[0] - 12, c[1] - 12, c[0] + 12, c[1] + 12], fill=EXTRA, outline=PAPER, width=2)
        s.text(c, str(n), 15, PAPER, True, 'mm')


def extras_list(s, top):
    s.text((60, top), 'ОСТАНОВКИ МЕЖДУ МЕСТАМИ · 8–27 · цена: S — домик или площадка, M — несколько построек, '
           'L — крупное, с проходом внутрь', 21, INK, True)
    top += 40
    for i, (n, label, cost, _, _) in enumerate(EXTRAS):
        col, row = divmod(i, 10)
        x = 60 + col * 790
        y = top + row * 34
        d = s.d
        d.ellipse([x, y, x + 24, y + 24], fill=EXTRA)
        s.text((x + 12, y + 12), str(n), 14, PAPER, True, 'mm')
        s.text((x + 34, y + 1), f'{label} · {cost}', 18)
    return top + 10 * 34


def gap_check():
    """Самый длинный кусок основных путей, где до ближайшего места или остановки дальше 150 м."""
    marks = [VILLAGE, SAWMILL, WAREHOUSE, AD, SAN, (0, 485, 0), (-95, 620, 0), (115, 700, 0), (205, 465, 0),
             (330, -40, 0), (490, 190, 0), A, B, C, D, W]
    marks = [(m[0], m[1]) for m in marks] + [e[3] for e in EXTRAS if e[0] != 27]
    marks += [(x, float(arc_z(abs(x)))) for x in np.linspace(-222, 222, 12)]
    routes = {name: parts for name, parts, _ in TRAVEL + ESCAPES}
    result = []
    for name, parts in routes.items():
        worst = run = 0.0
        for part in parts:
            pts = sample_route(part, 10)
            for a, b in zip(pts, pts[1:]):
                near = min(math.hypot(b[0] - m[0], b[1] - m[1]) for m in marks)
                step = math.hypot(b[0] - a[0], b[1] - a[1])
                run = run + step if near > 150 else 0.0
                worst = max(worst, run)
        result.append((name, worst))
    return result


def plan_sheet():
    s = Sheet((1660, 2340))
    s.text((60, 32), 'ВЕРТОЛЁТ · ПРЕДЛОЖЕНИЕ v04 · КАРТА ВОКРУГ ПЛОТИНЫ', 40, bold=True)
    s.text((60, 94), 'Claude · 06.11.2026 · на обсуждение, ничего не принято · все места v02 на месте', 23, ORANGE)
    s.text((60, 132), 'Видимый мир 2 × 3 км как в v02. Ходят по ядру 1,2 × 1,6 км (жирный пунктир), плотина — в центре.',
           22)
    x0, y0, k = 60, 200, 0.5

    def p(x, z):
        return (x0 + (x - VIS[0]) * k, y0 + (z - VIS[2]) * k)

    s.im.paste(colorize(H, LAKE), (x0, y0))
    d = s.d
    d.line([p(x, z) for z, x in NORTH_RIVER], fill=(120, 168, 176), width=7, joint='curve')
    d.line([p(x, z) for z, x in GORGE], fill=(120, 168, 176), width=9, joint='curve')
    d.ellipse([p(-310, 262), p(-262, 318)], fill=(143, 184, 189))
    # рамки
    s.dashed([p(PHASE2_BOX[0], PHASE2_BOX[2]), p(PHASE2_BOX[1], PHASE2_BOX[2]), p(PHASE2_BOX[1], PHASE2_BOX[3]),
              p(PHASE2_BOX[0], PHASE2_BOX[3]), p(PHASE2_BOX[0], PHASE2_BOX[2])], PHASE2, 2, (8, 8))
    s.dashed([p(WALKABLE[0], WALKABLE[2]), p(WALKABLE[1], WALKABLE[2]), p(WALKABLE[1], WALKABLE[3]),
              p(WALKABLE[0], WALKABLE[3]), p(WALKABLE[0], WALKABLE[2])], INK, 4, (18, 10))
    d.rectangle([p(VIS[0], VIS[2]), p(VIS[1], VIS[3])], outline=MUTED, width=2)
    # боны поперёк озера — граница ядра на воде
    xw = float(np.interp(-400, WEST[:, 0], WEST[:, 1]))
    xe = float(np.interp(-400, EAST[:, 0], EAST[:, 1]))
    bx = np.linspace(xw, xe, 18)
    d.line([p(x, -400 + 10 * math.sin(i * 1.3)) for i, x in enumerate(bx)], fill=(200, 110, 40), width=4)
    for i, x in enumerate(bx[::2]):
        c = p(x, -400 + 10 * math.sin(i * 2.6))
        d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=(230, 140, 60))
    # вторая очередь — дороги к мосту у хвоста
    for r in ([(-260, -150), (-280, -420), (-200, -650), (-90, -820), (-60, -880)],
              [(60, -880), (130, -780), (260, -560), (290, -330)]):
        s.dashed([p(*q) for q in r], PHASE2, 4, (12, 8))
    d.line([p(-70, -880), p(70, -880)], fill=PHASE2, width=7)
    # дороги ядра
    roads = [
        [A, (-520, -320), WAREHOUSE, (-430, -150), (-470, -50), (-400, 40), VILLAGE, (-360, 260), SAWMILL,
         (-300, 380), (-225, 448)],
        [(-360, 260), (-460, 440), W],
        [(225, 448), (300, 350), (330, 220), SAN, (300, -60), (260, -200), (420, -300), B],
        [D, (520, 650), AD],
        [(-400, 40), (-260, -150)],
        [(30, 520), (0, 560), (-40, 700), (-20, 900), C],
    ]
    for r in roads:
        d.line([p(q[0], q[1]) for q in r], fill=ROAD, width=5, joint='curve')
    arc = [p(x, float(arc_z(abs(x)))) for x in np.linspace(-222, 222, 30)]
    d.line(arc, fill=(232, 230, 222), width=9)
    d.line(arc, fill=INK, width=2)
    # тропы
    trails = [
        [A, (-560, -200), V1, (-560, 60), (-560, 300), W],
        [W, (-470, 560), (-330, 600), (-250, 480)],
        [VILLAGE, (-470, 80), (-540, 0), V1],
        [B, (560, -250), V3, (540, 100), (560, 350), AD],
        [AD, (400, 600), (340, 700)],
        [(225, 448), (290, 480), (330, 440), (380, 500), AD],
        [(340, 0), (280, 30), (300, 70), (245, 80)],
        [(420, 150), (330, 140), (290, 110), (245, 100)],
    ]
    for t in trails:
        s.dashed([p(q[0], q[1]) for q in t], TRAIL, 4, (10, 7))
    d.line([p(q[0], q[1]) for q in STAIRS], fill=(236, 214, 150), width=5)
    for q in STAIRS[1:-1]:
        c = p(q[0], q[1])
        d.ellipse([c[0] - 3, c[1] - 3, c[0] + 3, c[1] + 3], fill=INK)
    # постройки
    bld = (236, 228, 205)
    edge = (130, 110, 82)

    def rect(x, z, w, l, fill=bld, outline=edge):
        d.rectangle([p(x - w / 2, z - l / 2), p(x + w / 2, z + l / 2)], fill=fill, outline=outline)

    for i in range(12):
        col, row = i % 2, i // 2
        x = -440 + col * 70 + (row % 2) * 12
        z = 20 + row * 38
        d.rectangle([p(x - 16, z - 13), p(x + 16, z + 13)], outline=edge)
        rect(x - 4, z - 2, 12, 9)
    rect(-340, 312, 60, 20)
    rect(-395, 340, 28, 14)
    for i in range(4):
        rect(-400 + i * 16, 272, 9, 24, (200, 168, 120))
    d.rectangle([p(-560, -310), p(-400, -200)], outline=(110, 90, 70), width=2)
    for i in range(3):
        rect(-510 + i * 50, -260, 40, 14)
    c = p(AD[0], AD[1])
    d.ellipse([c[0] - 9, c[1] - 9, c[0] + 9, c[1] + 9], outline=INK, width=3)
    for ang in range(0, 360, 90):
        q = p(AD[0] + 40 * math.cos(math.radians(ang + 45)), AD[1] + 40 * math.sin(math.radians(ang + 45)))
        d.rectangle([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(150, 150, 140), outline=INK)
    rect(430, 70, 26, 100)

    def shell(cx, cz, finished=True):
        r = 30 * k
        color = (160, 130, 95) if finished else (175, 170, 160)
        for (oz, start, end) in ((-30, 40, 320), (30, 220, 500)):
            q = p(cx, cz + oz)
            d.arc([q[0] - r, q[1] - r, q[0] + r, q[1] + r], start, end, fill=color, width=6)
        rect(cx, cz, 24, 20, bld if finished else (215, 212, 205))

    shell(330, -40)
    shell(490, 190, False)
    for q in ((280, -90), (520, 60), (560, 260)):
        rect(q[0], q[1], 34, 22, (205, 205, 200), (120, 120, 120))
    d.rectangle([p(222, 60), p(245, 110)], fill=(232, 222, 190))
    rect(0, 485, 130, 26, (210, 206, 196), INK)
    rect(-95, 620, 70, 60, (220, 214, 200), edge)
    d.rectangle([p(55, 650), p(175, 750)], outline=INK, width=2)
    for i in range(4):
        d.line([p(70 + i * 30, 660), p(70 + i * 30, 740)], fill=MUTED, width=1)
    q = p(205, 465)
    d.rectangle([q[0] - 7, q[1] - 7, q[0] + 7, q[1] + 7], fill=(80, 110, 130), outline=INK)
    s.text((q[0] + 10, q[1] - 10), 'лифт', 17, INK, True)
    draw_extras(s, p, k)
    # вертолёт
    hp = [p(q[0], q[1]) for q in sample_route(HELI, 10) if VIS[2] + 5 <= q[1] <= VIS[3] - 5]
    s.dashed(hp, ORANGE, 5, (22, 12))
    hk = [p(q[0], q[1]) for q in HELI]
    for a, b in ((hk[2], hk[3]), (hk[5], hk[6]), (hk[8], hk[9])):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        tip = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d.polygon([tip, (tip[0] - 18 * math.cos(ang - 0.45), tip[1] - 18 * math.sin(ang - 0.45)),
                   (tip[0] - 18 * math.cos(ang + 0.45), tip[1] - 18 * math.sin(ang + 0.45))], fill=ORANGE)
    for name, (x, z) in (('K1', (-545, -140)), ('K2', (225, -250)), ('K3', (60, 900))):
        c = p(x, z)
        d.line([c[0] - 10, c[1] - 10, c[0] + 10, c[1] + 10], fill=RED, width=5)
        d.line([c[0] - 10, c[1] + 10, c[0] + 10, c[1] - 10], fill=RED, width=5)
        s.text((c[0] + 12, c[1] - 12), name, 20, RED, True)
    for name, (x, z) in (('V1', V1), ('V2', (-330, 600)), ('V3', V3), ('V4', (340, 700))):
        c = p(x, z)
        d.polygon([(c[0], c[1] - 9), (c[0] - 8, c[1] + 6), (c[0] + 8, c[1] + 6)], fill=INK)
        s.text((c[0] + 10, c[1] - 6), name, 16, INK, True)
    for name, (x, z, _) in (('A', A), ('B', B), ('C', C), ('D', D), ('W', W)):
        c = p(x, z)
        entry = name in 'BCW'
        d.rectangle([c[0] - 10, c[1] - 10, c[0] + 10, c[1] + 10], fill=ORANGE if entry else PAPER, outline=ORANGE,
                    width=3)
        s.text((c[0] + 14, c[1] - 13), name, 22, ORANGE, True)
    for n, (x, z) in ((1, (-260, 60)), (2, (-250, 330)), (3, (-470, -340)), (4, (540, 520)), (5, (470, -20)),
                      (6, (0, 360)), (7, (130, 560))):
        c = p(x, z)
        d.ellipse([c[0] - 17, c[1] - 17, c[0] + 17, c[1] + 17], fill=INK, outline=PAPER, width=2)
        s.text(c, str(n), 22, PAPER, True, 'mm')
    s.text(p(-120, -120), 'ОЗЕРО · 0 м', 24, (40, 90, 100), True)
    s.text(p(-190, -470), 'боны — граница ядра на воде', 17, (160, 80, 30), True)
    s.text(p(-700, -1080), 'вторая очередь: северные берега, мост у хвоста', 18, PHASE2, True)
    s.text(p(-60, 1080), 'ущелье −250…−265', 18, INK)
    s.text(p(-960, -1460), 'дальше — озеро и горы видом, не ходим', 18, MUTED)
    nx, ny = p(930, -1440)
    d.line([nx, ny + 50, nx, ny], fill=INK, width=4)
    d.polygon([(nx, ny - 14), (nx - 9, ny + 4), (nx + 9, ny + 4)], fill=INK)
    s.text((nx - 8, ny - 42), 'С', 22, INK, True)
    sx, sy = 80, y0 + 1500 + 34
    d.line([sx, sy, sx + 250, sy], fill=INK, width=4)
    for i, lab in ((0, '0'), (125, '250'), (250, '500 м')):
        d.line([sx + i, sy - 8, sx + i, sy + 8], fill=INK, width=3)
        s.text((sx + i - 8, sy + 14), lab, 20)
    # легенда: почему место здесь
    lx, ly = 1110, 200
    s.text((lx, ly), 'ВСЁ ЗДЕСЬ ИЗ-ЗА ПЛОТИНЫ', 24, INK, True)
    ly += 40
    items = [
        ('1 · Посёлок', 'Посёлок эксплуатационников: ходили на ГЭС пешком. 12 участков, +30.'),
        ('2 · Лесопилка', 'Со стройки, потом для посёлка. У залива с запанью, +12.'),
        ('3 · Склад ПЗРК', 'Склад части ПВО в висячей долине над посёлком, +150.'),
        ('4 · Старая ПВО', 'Прикрывала ГЭС: высота над плотиной, +230. Видно озеро и ущелье.'),
        ('5 · Санаторий', 'Санаторий энергосистемы, недавно перестроен — отсюда современные корпуса. '
                          'Окна на плотину. S-корпус 1 открыт, 2 — на ремонте.'),
        ('6 · Плотина', 'Центр карты. Гребень 455 м, высота 260; галереи −60, −130, −200; лифт.'),
        ('7 · Нижняя ГЭС', 'Главный центр добычи: машзал, двор, ОРУ, тоннель к выходу C.'),
    ]
    for head, body in items:
        s.text((lx, ly), head, 22, INK, True)
        ly += 28
        ly += s.wrapped((lx, ly), body, 42, 19, MUTED) + 10
    ly += 4
    s.text((lx, ly), 'ТРИ ПЕРЕХОДА — ЧЕРЕЗ ПЛОТИНУ', 22, INK, True)
    ly += 32
    for body in ('Гребень +10 — коротко и открыто.', 'Галерея −60 — внутри бетона, темно, тесно.',
                 'Низ −250 — лестница по стене, мост у ГЭС, лифт.'):
        ly += s.wrapped((lx, ly), '· ' + body, 44, 19, MUTED) + 4
    ly += 12
    legend = [
        ('line', ORANGE, 'Пролёт вертолёта: с севера над озером,'),
        ('none', None, 'над плотиной в ущелье; следующий — обратно'),
        ('x', RED, 'K1–K3: лесистый склон, берег, ГЭС'),
        ('sqf', ORANGE, 'B, C, W: заходы и выходы'),
        ('sq', ORANGE, 'A, D: только выходы (у склада и ПВО)'),
        ('tri', INK, 'V1–V4: смотровые у бровки'),
        ('line', ROAD, 'дороги'),
        ('dash', (205, 180, 120), 'тропы'),
        ('dash', PHASE2, 'вторая очередь'),
        ('ext', EXTRA, '8–27: остановки между местами'),
    ]
    for kind, col, label in legend:
        if kind == 'line':
            d.line([lx, ly + 10, lx + 46, ly + 10], fill=col, width=5)
        elif kind == 'dash':
            s.dashed([(lx, ly + 10), (lx + 46, ly + 10)], col, 4, (10, 7))
        elif kind == 'x':
            d.line([lx + 12, ly + 1, lx + 30, ly + 19], fill=col, width=4)
            d.line([lx + 12, ly + 19, lx + 30, ly + 1], fill=col, width=4)
        elif kind == 'sqf':
            d.rectangle([lx + 12, ly + 1, lx + 30, ly + 19], outline=col, width=3, fill=col)
        elif kind == 'sq':
            d.rectangle([lx + 12, ly + 1, lx + 30, ly + 19], outline=col, width=3, fill=PAPER)
        elif kind == 'ext':
            d.ellipse([lx + 9, ly - 1, lx + 33, ly + 21], fill=col)
        elif kind == 'tri':
            d.polygon([(lx + 21, ly), (lx + 12, ly + 18), (lx + 30, ly + 18)], fill=col)
        s.text((lx + 58, ly - 2), label, 19)
        ly += 30
    s.text((540, y0 + 1500 + 26), 'Рельеф — схема для замеров, не готовая форма. Деревья не нарисованы.', 19, MUTED)
    extras_list(s, y0 + 1500 + 90)
    s.im.save(OUT / 'mission_helicopter_v04_plan.png')
    # крупно ядро — читать на телефоне
    a, b = p(WALKABLE[0] - 20, WALKABLE[2] - 30), p(WALKABLE[1] + 20, WALKABLE[3] + 20)
    core = s.im.crop((int(a[0]), int(a[1]), int(b[0]), int(b[1])))
    core = core.resize((core.width * 2, core.height * 2), Image.LANCZOS)
    core.save(OUT / 'mission_helicopter_v04_plan_core.png')


def sections_sheet(travel, escapes, heli):
    s = Sheet((1800, 2330))
    d = s.d
    s.text((60, 32), 'ВЕРТОЛЁТ · v04 · РАЗРЕЗЫ В НАСТОЯЩЕМ МАСШТАБЕ И РАСЧЁТЫ', 38, bold=True)
    s.text((60, 92), 'Горизонталь и вертикаль одинаковые. Ядро 1,2 × 1,6 км = 1,9 км² (v03 — 3,3 км², v02 — 6 км²).',
           23, ORANGE)

    def section(top, left, xs_, zs_, k, ymin, ymax, title, extra=None):
        s.text((left, top), title, 24, INK, True)
        top += 40
        hgt = (ymax - ymin) * k
        pts = [(left + i * CELL * k, top + (ymax - min(h_at(x, z), ymax)) * k) for i, (x, z) in enumerate(zip(xs_, zs_))]
        base = top + hgt
        d.polygon(pts + [(pts[-1][0], base), (pts[0][0], base)], fill=(184, 196, 166))
        d.line(pts, fill=(90, 110, 90), width=2)
        for yv in range(int(math.ceil(ymin / 100) * 100), int(ymax) + 1, 100):
            yy = top + (ymax - yv) * k
            d.line([left - 8, yy, left, yy], fill=MUTED, width=2)
            s.text((left - 60, yy - 10), f'{yv:+d}' if yv else '0', 16, MUTED)
        if extra:
            extra(left, top, k, ymax)
        return base

    zs_a = np.arange(-1500, 1500, CELL)
    xs_a = []
    for z in zs_a:
        if z < -820:
            xs_a.append(float(np.interp(z, NORTH_RIVER[:, 0], NORTH_RIVER[:, 1])))
        elif z < 395:
            xs_a.append(float((np.interp(z, WEST[:, 0], WEST[:, 1]) + np.interp(z, EAST[:, 0], EAST[:, 1])) / 2))
        else:
            xs_a.append(float(np.interp(z, GORGE[:, 0], GORGE[:, 1])))

    def extra_a(left, top, k, ymax):
        def P(z, y):
            return (left + (z + 1500) * k, top + (ymax - y) * k)
        bed = [P(z, -250 * smooth(-820, 380, z) - 4) for z in range(-820, 396, 10)]
        d.polygon([P(-820, 0)] + bed + [P(395, 0)], fill=(150, 188, 192))
        d.line([P(-820, 0), P(395, 0)], fill=(70, 120, 130), width=3)
        d.polygon([P(395, 10), P(407, 10), P(458, -252), P(395, -252)], fill=(205, 205, 198), outline=INK)
        for gy in (-60, -130, -200):
            d.rectangle([P(400, gy + 3), P(410 + (10 - gy) * 0.18, gy - 3)], fill=INK)
        d.rectangle([P(458, -222), P(498, -252)], fill=(220, 214, 200), outline=INK)
        for z in (WALKABLE[2], WALKABLE[3]):
            s.dashed([P(z, 380), P(z, -290)], INK, 2, (8, 8))
        hp = [P(q[1], q[2]) for q in sample_route(HELI, 10) if -1500 <= q[1] <= 1500]
        s.dashed(hp, ORANGE, 4, (18, 10))
        s.text(P(-1100, 45), 'озеро — вид', 19, (40, 90, 100), True)
        s.text(P(-360, 45), 'ядро · у плотины глубина ~250 м', 19, (40, 90, 100), True)
        s.text(P(430, 40), 'гребень +10', 18, INK, True)
        s.text(P(650, -60), 'галереи −60 · −130 · −200', 18, INK)
        s.text(P(505, -228), 'машзал −250', 18, INK)
        s.text(P(-1450, 300), 'пролёт вертолёта: над озером +230…+140, в ущелье ниже краёв', 19, ORANGE)
        s.text(P(545, -120), '260 м', 26, ORANGE, True)
        d.line([P(530, 10), P(530, -250)], fill=ORANGE, width=3)
        s.text(P(-390, 360), 'граница ядра', 16, MUTED)

    bottom = section(140, 120, xs_a, zs_a, 0.55, -300, 420,
                     'А · Вдоль долины: озеро → плотина → ущелье (север слева)', extra_a)
    kb = 0.42
    xs_b = np.arange(-1000, 1000, CELL)

    def extra_b(left, top, k, ymax):
        def P(x, y):
            return (left + (x + 1000) * k, top + (ymax - y) * k)
        for x in (WALKABLE[0], WALKABLE[1]):
            s.dashed([P(x, 900), P(x, -40)], INK, 2, (8, 8))
        d.polygon([P(-210, 0), P(-150, -80), P(150, -90), P(200, 0)], fill=(150, 188, 192))
        d.line([P(-210, 0), P(210, 0)], fill=(70, 120, 130), width=3)
        for x, w, hh in ((330, 60, 12), (430, 26, 13)):
            y = h_at(x, 60)
            d.rectangle([P(x - w / 2, y + hh), P(x + w / 2, y)], fill=(236, 228, 205), outline=INK)
        y = h_at(-380, 100)
        d.rectangle([P(-440, y + 7), P(-330, y)], fill=(236, 228, 205), outline=INK)
        c = P(10, 140)
        d.ellipse([c[0] - 6, c[1] - 6, c[0] + 6, c[1] + 6], fill=ORANGE)
        s.text((c[0] + 10, c[1] - 26), 'вертолёт +140', 17, ORANGE, True)
        s.text(P(-560, 120), 'посёлок +30', 17, INK, True)
        s.text(P(260, 150), 'санаторий +60', 17, INK, True)
        s.text(P(-990, 860), 'вид', 17, MUTED)
        s.text(P(-590, 860), 'ходят', 17, MUTED)

    def extra_c(left, top, k, ymax):
        def P(x, y):
            return (left + (x + 1000) * k, top + (ymax - y) * k)
        d.line([P(q[0], q[2]) for q in STAIRS], fill=(200, 160, 70), width=4)
        d.rectangle([P(-130, -237), P(-60, -247)], fill=(220, 214, 200), outline=INK)
        d.rectangle([P(55, -222), P(175, -232)], fill=(205, 205, 200), outline=INK)
        for x in (WALKABLE[0], WALKABLE[1]):
            s.dashed([P(x, 700), P(x, -260)], INK, 2, (8, 8))
        s.text(P(-560, -60), 'лестница по стене', 17, INK, True)
        s.text(P(-180, -200), 'двор', 16, INK)
        s.text(P(120, -200), 'ОРУ', 16, INK)
        s.text(P(-980, 640), 'лифт и галереи — в 150 м выше по ущелью', 16, MUTED)

    top2 = bottom + 40
    end_b = section(top2, 120, xs_b, np.full_like(xs_b, 100.0), kb, -100, 950,
                    'Б · Поперёк: посёлок — озеро — санаторий (z +100)', extra_b)
    end_c = section(top2, 120 + 2000 * kb + 110, xs_b, np.full_like(xs_b, 620.0), kb, -280, 770,
                    'В · Поперёк ущелья у ГЭС (z +620)', extra_c)
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

    rows = [(n, f'{m / 1000:.2f} км', f'{up:.0f} м', f'{tr / 60:.1f} мин', f'{tw / 60:.1f} мин')
            for n, m, up, tr, tw in travel]
    y = table(y, 'Пути пешком (бег с передышками 4,4 м/с · шаг 1,82 м/с; лифт — 60 с)',
              ('Путь', 'длина', 'подъём', 'бегом', 'шагом'), rows, (760, 180, 160, 170, 170))
    s.text((60, y - 8), 'v03: посёлок → санаторий по гребню 1,36 км, обходом 2,18 км. v02 на глаз: 2,2 и 3,8 км.', 19, MUTED)
    y += 30
    rows = [(n, f'{m:.0f} м', f'{up:.0f} м', f'{tr / 60:.1f} мин', f'{tw / 60:.1f} мин') for n, m, up, tr, tw in escapes]
    y = table(y, 'Уход после выстрела к ближайшему выходу', ('Откуда → куда', 'длина', 'подъём', 'бегом', 'шагом'),
              rows, (760, 180, 160, 170, 170))
    inside, hrows = heli
    rows = [(n, f'{lock} с', f'{run} с') for n, lock, run in hrows]
    y = table(y, f'Вертолёт 42 м/с: над ядром {inside} с за пролёт; над озером виден и раньше (без деревьев):',
              ('Позиция пуска', 'всего за пролёт', 'дольше всего подряд'), rows, (760, 300, 300))
    s.text((60, y - 6), 'ПЗРК — 1 км, стационарный комплекс — 2,5 км (предложение). Лес сократит окна у берега.', 19, MUTED)
    s.im.save(OUT / 'mission_helicopter_v04_sections.png')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    travel = [route_row(n, parts, e) for n, parts, e in TRAVEL]
    escapes = [route_row(n, parts, e) for n, parts, e in ESCAPES]
    heli = heli_rows()
    for r in travel + escapes:
        print(f'{r[0]}: {r[1]:.0f} м, подъём {r[2]:.0f} м, бегом {r[3] / 60:.1f} мин, шагом {r[4] / 60:.1f} мин')
    print('вертолёт над ядром, с:', heli[0], 'V1', V1, 'V3', V3, 'бровка ПВО', AD_BROW)
    for n, lock, run in heli[1]:
        print(f'  {n}: {lock} с, подряд {run} с')
    for name, (x, z, y) in (('посёлок', VILLAGE), ('склад', WAREHOUSE), ('ПВО', AD), ('санаторий', SAN),
                            ('A', A), ('B', B), ('W', W), ('D', D), ('C', C)):
        print(f'  высота {name}: по плану {y}, рельеф {h_at(x, z):.0f}')
    for name, worst in gap_check():
        print(f'  пусто дольше 150 м от мест: {name}: {worst:.0f} м')
    plan_sheet()
    sections_sheet(travel, escapes, heli)


if __name__ == '__main__':
    main()
