# -*- coding: utf-8 -*-
"""Карта «Санаторий» — схема участка, концепция v01 (предложение агента, docs/design/sanatorium_map.md).

Карта — сама территория санатория на берегу озера под плотиной: около 300 × 500 м суши неправильной формы
(≈ 15 га) и мол «Стрелка» в воду. Плато +32…+38 м над водой, склон 30 м, набережная +2 м. Жилые корпуса —
по замыслу владельца 2026-11-07 цепочки отдельных модулей-номеров (2–3 этажа, вход с улицы) вдоль буквы S;
здесь их раскладка условная до рисунка владельца. Главный корпус, парковки, парк, коттеджи, спуски и мол —
предложение для обсуждения.

    python -X utf8 tools/sanatorium_map_plan.py   → docs/plans/sanatorium_map_v01.png (план, разрез по оси, легенда)

Координаты: x — на восток, y — на север, метры; 0 — середина плато у главного корпуса. Озеро на западе,
плотина — за озером на юго-западе (фон, на карту не входит).
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_map_v01.png'

# рамка рисунка и масштаб плана
XMIN, XMAX, YMIN, YMAX = -310.0, 170.0, -270.0, 270.0
SCALE = 2.2
PAD = 40
LEGEND_W = 640
SECTION_H = 470

# высоты (м над уровнем озера)
WATER = 0.0
QUAY = 2.0         # набережная
PLATEAU = 32.0     # бровка плато
MOLE = 1.5         # настил мола

INK = (40, 42, 46)
MUTED = (110, 112, 118)
PAPER = (247, 245, 239)
WATER_C = (150, 186, 206)
WATER_DEEP = (126, 166, 192)
QUAY_C = (214, 206, 188)
SAND_C = (232, 216, 170)
SLOPE_C = (156, 172, 128)
PLATEAU_C = (222, 228, 206)
FOREST_C = (196, 210, 178)
ROAD_C = (178, 176, 170)
PARK_C = (190, 190, 186)
BUILD_C = (236, 236, 232)
MAIN_C = (246, 226, 196)
S_C = (214, 228, 242)
POOL_C = (120, 196, 220)
STAIR_C = (196, 84, 60)
PATH_C = (150, 106, 60)
EXIT_C = (40, 150, 70)
SPAWN_C = (60, 110, 200)


def font(size, bold=False):
    name = 'arialbd.ttf' if bold else 'arial.ttf'
    return ImageFont.truetype(f'C:/Windows/Fonts/{name}', size)


W = int((XMAX - XMIN) * SCALE) + PAD * 2 + LEGEND_W
H = int((YMAX - YMIN) * SCALE) + PAD * 2 + 60 + SECTION_H
img = Image.new('RGB', (W, H), PAPER)
d = ImageDraw.Draw(img)
TOP = 60  # место под заголовок


def P(x, y):
    return (PAD + (x - XMIN) * SCALE, TOP + PAD + (YMAX - y) * SCALE)


def poly(pts, fill=None, outline=None, width=1):
    d.polygon([P(*p) for p in pts], fill=fill, outline=outline, width=width)


def rect(x0, y0, x1, y1, fill=BUILD_C, outline=INK, width=2):
    poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width)


def circle(cx, cy, r, fill=None, outline=INK, width=2):
    (ax, ay), (bx, by) = P(cx - r, cy + r), P(cx + r, cy - r)
    d.ellipse([ax, ay, bx, by], fill=fill, outline=outline, width=width)


def line(pts, color=INK, width=2, dash=None):
    q = [P(*p) for p in pts]
    if not dash:
        d.line(q, fill=color, width=width, joint='curve')
        return
    on, off = dash
    for a, b in zip(q, q[1:]):
        length = math.dist(a, b)
        t = 0.0
        while t < length:
            t1 = min(t + on, length)
            d.line([(a[0] + (b[0] - a[0]) * t / length, a[1] + (b[1] - a[1]) * t / length),
                    (a[0] + (b[0] - a[0]) * t1 / length, a[1] + (b[1] - a[1]) * t1 / length)], fill=color, width=width)
            t = t1 + off


def text(x, y, s, size=13, color=INK, bold=False, anchor='mm'):
    d.text(P(x, y), s, font=font(size, bold), fill=color, anchor=anchor)


def marker(x, y, n, color=INK):
    cx, cy = P(x, y)
    d.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], fill=(255, 255, 255), outline=color, width=2)
    d.text((cx, cy), str(n), font=font(12, True), fill=color, anchor='mm')


# ---------------------------------------------------------------- рельеф и граница карты

def shore_x(y):
    """Урез воды: берег бухтами, на юге мыс."""
    return -150.0 + 7.0 * math.sin(y / 45.0) + 5.0 * math.sin(y / 17.0 + 1.0) + (14.0 if y < -215 else 0.0) * min(1.0, (-215 - y) / 30.0)


def brow_x(y):
    """Бровка склона (верх, +32): склон 35–45 м по горизонтали, у мыса круче."""
    return shore_x(y) + 20.0 + 42.0 + 6.0 * math.sin(y / 70.0 + 0.5)


# граница карты: запад — урез воды (ходят по набережной и молу), восток — забор и опушка, север — овраг с ручьём,
# юг — скальный мыс; неправильная форма, ≈ 15 га суши
ys = [YMIN + 30 + i * 4.0 for i in range(int((YMAX - YMIN - 60) / 4.0) + 1)]
east = [(150.0 + 10.0 * math.sin(y / 55.0) - (22.0 if y > 190 else 0.0) * min(1.0, (y - 190) / 40.0)
         - (30.0 if y < -200 else 0.0) * min(1.0, (-200 - y) / 40.0), y) for y in ys]
west = [(shore_x(y), y) for y in reversed(ys)]
# север — край оврага с ручьём (кромка извилистая), юг — скальный мыс выпирает к югу у берега
north = [(x, east[-1][1] + 7.0 * math.sin(x / 23.0) + 4.0 * math.sin(x / 9.0)) for x in
         [east[-1][0] - k * 6.0 for k in range(1, int((east[-1][0] - shore_x(east[-1][1])) / 6.0))]]
south = [(x, ys[0] - 10.0 - 12.0 * math.exp(-((x + 90.0) / 60.0) ** 2) + 3.0 * math.sin(x / 13.0)) for x in
         [shore_x(ys[0]) + k * 6.0 for k in range(1, int((east[0][0] - shore_x(ys[0])) / 6.0))]]
boundary = south + east + north + west


def area(pts):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


LAND_HA = area(boundary) / 10000.0

# вода — всё, что западнее уреза
poly([(XMIN, YMIN), (XMIN, YMAX)] + [(shore_x(y), y) for y in [YMAX - i * 4.0 for i in range(int((YMAX - YMIN) / 4) + 1)]],
     fill=WATER_C)
poly([(XMIN, YMIN), (XMIN, YMAX), (-230, YMAX), (-230, YMIN)], fill=WATER_DEEP)
# лес за границей карты (фон, не ходят)
poly([(XMAX, YMIN), (XMAX, YMAX)] + [(p[0] + 0.0, p[1]) for p in reversed(east)] + [(east[0][0], YMIN)], fill=FOREST_C)
poly(boundary, fill=PLATEAU_C)
# набережная + пляж, склон
quay = [(shore_x(y), y) for y in ys] + [(shore_x(y) + 20.0, y) for y in reversed(ys)]
poly(quay, fill=QUAY_C)
slope = [(shore_x(y) + 20.0, y) for y in ys] + [(brow_x(y), y) for y in reversed(ys)]
poly(slope, fill=SLOPE_C)
# пляж — южная часть набережной шире, песок
beach_ys = [y for y in ys if -235 <= y <= -95]
poly([(shore_x(y), y) for y in beach_ys] + [(shore_x(y) + 22.0, y) for y in reversed(beach_ys)], fill=SAND_C)
poly(boundary, outline=(170, 40, 40), width=3)

# ---------------------------------------------------------------- мол «Стрелка»
MOLE_PTS = [(-148, -26), (-205, -20), (-258, -6), (-286, 4), (-292, 10), (-286, 16), (-258, 26), (-205, 40), (-148, 46)]
poly(MOLE_PTS, fill=QUAY_C, outline=INK, width=2)
# амфитеатр-ступени к воде с южной стороны
for k in range(6):
    line([(-160 - k * 2.0, -22 - k * 0.3), (-198 - k * 1.6, -17 - k * 0.6)], color=MUTED, width=1)
# фонтанная площадь, павильон речного вокзала, кафе, киоски, колоннада, ротонда, маяк, клумбы, лодки
circle(-182, 10, 9, fill=POOL_C)
rect(-246, 0, -214, 20, fill=BUILD_C)
rect(-176, 24, -160, 36, fill=BUILD_C)
for kx, ky in ((-200, -8), (-262, 18), (-232, 30)):
    rect(kx - 3, ky - 2.5, kx + 3, ky + 2.5, fill=BUILD_C, width=1)
for k in range(10):
    circle(-192 - k * 5.5, 36 - k * 0.9, 0.9, fill=INK, width=1)
circle(-270, 10, 5, fill=BUILD_C)
circle(-288, 10, 2.6, fill=(240, 200, 80))
for px_, py_ in ((-192, 2), (-206, 18), (-226, -6), (-252, 10), (-170, -8), (-240, 36)):
    rect(px_ - 3.5, py_ - 1.2, px_ + 3.5, py_ + 1.2, fill=(160, 180, 120), width=1)
for k in range(5):
    poly([(-200 - k * 14, 48 + k * 0.5), (-190 - k * 14, 48 + k * 0.5), (-192 - k * 14, 52 + k * 0.5), (-198 - k * 14, 52 + k * 0.5)],
         fill=(250, 250, 250), outline=INK)

# ---------------------------------------------------------------- набережная: лодочная станция, пляж
rect(-152, 188, -134, 206, fill=BUILD_C)                 # эллинг
poly([(-152, 192), (-170, 194), (-170, 200), (-152, 202)], fill=QUAY_C, outline=INK)   # слип
rect(-146, 214, -136, 222, fill=BUILD_C, width=1)        # склад ГСМ
line([(-150, 174), (-186, 176)], width=4)                 # причальная стенка-пальчик
for k in range(4):
    rect(-140 + 0, 160 + k * 6, -132, 163 + k * 6, fill=(250, 250, 250), width=1)  # стеллажи лодок
rect(-142, -128, -130, -116, fill=BUILD_C)               # спасательная станция
for k in range(6):
    rect(-140, -150 - k * 9, -136, -146 - k * 9, fill=BUILD_C, width=1)   # кабинки
for k in range(10):
    circle(-152 + (k % 2) * 6, -100 - k * 12, 2.0, fill=(240, 160, 90), width=1)   # грибки
rect(-136, -96, -128, -88, fill=BUILD_C, width=1)        # кафе-киоск у пляжа

# ---------------------------------------------------------------- дороги и парковки
ROAD = 9.0
line([(170, 0), (95, 0)], color=ROAD_C, width=int(ROAD * SCALE))
line([(95, 0), (10, 0)], color=ROAD_C, width=int(7 * SCALE))
circle(10, 0, 18, fill=ROAD_C, outline=None)
circle(10, 0, 8, fill=POOL_C)                            # фонтан на кругу
line([(70, 0), (70, 150), (35, 150)], color=ROAD_C, width=int(7 * SCALE))
line([(70, 0), (70, -150), (35, -150)], color=ROAD_C, width=int(7 * SCALE))
line([(70, 150), (90, 205), (128, 222)], color=ROAD_C, width=int(6 * SCALE))     # к хоздвору
line([(95, 205), (-60, 238), (-104, 232), (-90, 214), (-128, 206), (-138, 196)], color=ROAD_C, width=int(5 * SCALE))  # служебная к лодочной станции
line([(70, -150), (70, -213), (140, -213)], color=ROAD_C, width=int(6 * SCALE))  # к коттеджам
for x0, y0, x1, y1, label in ((76, -36, 128, 36, 'P1'), (20, 118, 62, 182, 'P2'), (20, -182, 62, -118, 'P3')):
    rect(x0, y0, x1, y1, fill=PARK_C, outline=MUTED, width=1)
    step = 2.6
    yy = y0 + 1
    while yy < y1 - 1:
        line([(x0 + 1, yy), (x0 + 5, yy)], color=(150, 150, 146), width=1)
        line([(x1 - 5, yy), (x1 - 1, yy)], color=(150, 150, 146), width=1)
        yy += step
    text((x0 + x1) / 2, (y0 + y1) / 2, label, 15, MUTED, True)
rect(136, -6, 144, 6, fill=BUILD_C)                      # КПП
line([(134, -8), (134, 8)], color=(200, 40, 40), width=3)

# ---------------------------------------------------------------- главный корпус (предложение)
rect(-56, -22, -10, 22, fill=MAIN_C)                     # вестибюль, приёмная, атриум; 3 этаж — администрация
rect(-52, 22, -12, 64, fill=MAIN_C)                      # столовая (двусветный зал) и кухня
rect(-12, 40, 4, 60, fill=MAIN_C, width=1)               # хозяйственный вход кухни, рампа
rect(-52, -64, -12, -22, fill=MAIN_C)                    # лечебные кабинеты, медпост, библиотека
rect(-88, -58, -56, -24, fill=(206, 232, 240))           # крытый бассейн (зал со стеклянной стеной к озеру)
rect(-84, -52, -62, -32, fill=POOL_C, width=1)
poly([(-88, -60), (-104, -60), (-108, -22), (-88, -22)], fill=(232, 228, 214), outline=INK, width=2)  # подиум над склоном
rect(-104, -50, -92, -30, fill=POOL_C, width=1)          # открытая чаша с видом на воду
rect(-86, -16, -56, 16, fill=(232, 228, 214), outline=MUTED, width=1)   # парадная терраса
circle(-72, 0, 5, fill=POOL_C, width=1)

# ---------------------------------------------------------------- жилые S-кварталы из модулей (замысел владельца 2026-11-07)
# Корпус — не сплошное здание с холлом и коридорами (v02 заменена), а цепочка отдельных модулей-номеров вдоль буквы S:
# каждый номер — куб / параллелепипед в 2–3 этажа со своим входом прямо с улицы; соседние модули стоят на одном уровне
# или со сдвигом по высоте. Здесь — условная раскладка до рисунка владельца: шаг, размеры и число модулей — предложение.
MOD_W = 8.0        # вдоль улицы
MOD_D = 11.0       # в глубину
MOD_STEP = 10.5    # шаг по осевой S: модуль + проход 2,5 м
S_R = 28.0         # радиус полуокружностей S


def s_path(ox, oy):
    """Осевая буквы S: верхняя дуга раскрыта на восток, нижняя — на запад."""
    pts = []
    for k in range(91):
        a = math.radians(90 + 180 * k / 90)          # верхняя: от севера через запад к югу
        pts.append((ox + S_R * math.cos(a), oy + S_R + S_R * math.sin(a)))
    for k in range(1, 91):
        a = math.radians(90 - 180 * k / 90)          # нижняя: от севера через восток к югу
        pts.append((ox + S_R * math.cos(a), oy - S_R + S_R * math.sin(a)))
    return pts


def modules_along(pts):
    out = []
    acc = 0.0
    next_at = MOD_STEP * 0.5
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        while acc + seg >= next_at:
            t = (next_at - acc) / seg
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            out.append((x, y, math.atan2(b[1] - a[1], b[0] - a[0])))
            next_at += MOD_STEP
        acc += seg
    return out


MODULE_COUNT = 0
S_SITES = [(-40.0, 142.0, 'С-1'), (-40.0, -142.0, 'С-2')]
for ox, oy, name in S_SITES:
    path = s_path(ox, oy)
    line(path, color=(200, 196, 186), width=int(4 * SCALE))     # внутренняя улочка вдоль модулей
    mods = modules_along(path)
    MODULE_COUNT += len(mods)
    for k, (x, y, ang) in enumerate(mods):
        tx, ty = math.cos(ang), math.sin(ang)
        nx_, ny_ = -ty, tx
        # модуль сбоку от улочки: чередуем стороны по высотам — светлее ниже, темнее выше (сдвиг уровней)
        side = 1.0
        cx_, cy_ = x + nx_ * (MOD_D * 0.5 + 2.5) * side, y + ny_ * (MOD_D * 0.5 + 2.5) * side
        corners = []
        for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append((cx_ + tx * u * MOD_W * 0.5 + nx_ * v * MOD_D * 0.5, cy_ + ty * u * MOD_W * 0.5 + ny_ * v * MOD_D * 0.5))
        shade = [(214, 228, 242), (190, 208, 228), (166, 190, 216)][k % 3]
        poly(corners, fill=shade, outline=INK, width=1)
        # вход с улицы — метка на стороне улочки
        dx, dy = x + nx_ * 2.6, y + ny_ * 2.6
        line([(dx - tx * 1.2, dy - ty * 1.2), (dx + tx * 1.2, dy + ty * 1.2)], color=(200, 60, 40), width=3)
    text(ox, oy, name, 15, INK, True)

# ---------------------------------------------------------------- хоздвор, спорт, летний театр, коттеджи
rect(104, 196, 130, 214, fill=BUILD_C)                   # котельная
circle(134, 205, 3, fill=(150, 90, 70))                  # труба
rect(104, 222, 126, 236, fill=BUILD_C)                   # прачечная
rect(132, 222, 146, 246, fill=BUILD_C)                   # гаражи
circle(96, 240, 4, fill=BUILD_C)                         # водонапорная башня
rect(110, 244, 124, 252, fill=BUILD_C, width=1)          # трансформаторная
rect(96, 62, 140, 112, fill=(204, 196, 176), outline=MUTED, width=1)   # корты и волейбол
line([(118, 62), (118, 112)], color=MUTED, width=1)
for k in range(5):                                       # летний театр — полукруг рядов
    d.arc([*P(118 - 10 - k * 5, -80 + 10 + k * 5), *P(118 + 10 + k * 5, -80 - 10 - k * 5)], 200, 340, fill=MUTED, width=2)
rect(110, -100, 126, -92, fill=BUILD_C)                  # сцена
COTTAGES = [(x, y) for y in (-199.0, -227.0) for x in (30.0, 56.0, 82.0, 108.0, 132.0)]
for cx_, cy_ in COTTAGES:
    rect(cx_ - 7, cy_ - 6, cx_ + 7, cy_ + 6, fill=(232, 214, 196))
# детская площадка во дворе С-1, сад во дворе С-2 (раскрытия дуг)
rect(-30, 158, -14, 172, fill=(214, 226, 190), outline=MUTED, width=1)
circle(-58, -126, 6, fill=(200, 222, 180), outline=MUTED, width=1)

# ---------------------------------------------------------------- спуски к воде
# 1 — парадная лестница-каскад по оси: марш вниз — площадка — вбок — ещё вбок …
GRAND = [(-88, 0), (-94, 0), (-94, 22), (-101, 22), (-101, -22), (-108, -22), (-108, 22), (-115, 22), (-115, -22),
         (-122, -22), (-122, 22), (-129, 22), (-129, 0), (-134, 0)]
line(GRAND, color=STAIR_C, width=5)
for p in GRAND[1:-1]:
    rect(p[0] - 2.4, p[1] - 2.4, p[0] + 2.4, p[1] + 2.4, fill=(240, 220, 210), outline=STAIR_C, width=1)
rect(-117, 24, -113, 30, fill=BUILD_C, width=1)          # киоск на площадке
circle(-108, -27, 3, fill=BUILD_C, width=1)              # беседка-ротонда
rect(-103, -30, -99, -24, fill=(240, 220, 210), outline=STAIR_C, width=1)   # смотровой балкон
# 2 — грунтовая тропа-серпантин южнее, с беседками, лавками, киоском и родником
TRAIL = [(-80, -72), (-92, -78), (-86, -92), (-100, -100), (-94, -114), (-110, -120), (-104, -136), (-118, -142),
         (-112, -156), (-126, -164), (-132, -176)]
line(TRAIL, color=PATH_C, width=3, dash=(9, 5))
for gx, gy in ((-86, -92), (-104, -136)):
    circle(gx, gy, 3.4, fill=BUILD_C, width=1)
rect(-99, -116, -95, -112, fill=BUILD_C, width=1)
circle(-118, -142, 1.8, fill=POOL_C, width=1)
# 3 — тропа от коттеджей к пляжу
line([(20, -213), (-40, -222), (-90, -214), (-104, -228), (-118, -218), (-130, -230)], color=PATH_C, width=3, dash=(9, 5))
# 4 — лифт к пляжу: шахта у бровки и тоннель (предложение)
rect(-100, -76, -94, -70, fill=(120, 120, 140), outline=INK, width=1)
line([(-97, -73), (-128, -86)], color=(90, 90, 110), width=3, dash=(5, 4))
# 5 — ливнёвка (скрытый лаз): от хоздвора по оврагу к набережной
line([(-60, 252), (-110, 248), (-138, 244)], color=(100, 100, 110), width=2, dash=(3, 4))

# ---------------------------------------------------------------- деревья: сосны и ели парка
rng = random.Random(7)
KEEP = [(-60, -70, 10, 70), (-110, -64, -54, 24), (-90, -20, 20, 20), (78, -40, 170, 40), (16, 114, 66, 186), (16, -186, 66, -114),
        (-75, 80, -4, 205), (-75, -205, -4, -80), (92, 58, 144, 116), (100, 190, 150, 256), (18, -236, 146, -190),
        (96, -112, 140, -70), (60, -230, 80, 160), (-40, 228, 100, 248)]


def free(x, y):
    for x0, y0, x1, y1 in KEEP:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return False
    return True


inside = [p for p in boundary]


def in_poly(x, y, pts):
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
            c = not c
        j = i
    return c


for k in range(1400):
    x = rng.uniform(-140, 165)
    y = rng.uniform(-258, 258)
    if not in_poly(x, y, boundary) or not free(x, y) or x < brow_x(y) - 34:
        continue
    r = rng.uniform(2.2, 3.6)
    circle(x, y, r, fill=(98, 128, 92) if rng.random() < 0.7 else (120, 146, 96), outline=None)
for k in range(300):    # лес по склону — реже
    y = rng.uniform(-250, 250)
    x = rng.uniform(shore_x(y) + 21, brow_x(y) - 2)
    if abs(y) < 28 or (-230 < y < -60 and abs(x + 105) < 30 and rng.random() < 0.4):
        continue
    circle(x, y, rng.uniform(2.0, 3.0), fill=(86, 116, 82), outline=None)

# ---------------------------------------------------------------- выходы, заходы, номера мест
EXITS = [(160, 0, 'В1 · КПП, дорога'), (138, 258, 'В2 · лесная тропа к горам'), (-186, 176, 'В3 · лодка у причала'),
         (-112, -262, 'В4 · берег за мысом')]
for x, y, label in EXITS:
    circle(x, y, 6, fill=EXIT_C, outline=INK)
    text(x + (-9 if x > 100 else 9), y + 9, label.split(' · ')[0], 13, EXIT_C, True, 'rm' if x > 100 else 'lm')
for x, y in ((160, 60), (160, -120), (40, 258), (100, -258)):
    poly([(x, y + 6), (x - 5, y - 4), (x + 5, y - 4)], fill=SPAWN_C, outline=INK)

PLACES = [
    (1, -33, -6, 'Главный корпус: вестибюль с атриумом, приёмная; 3 этаж — администрация, касса с сейфом'),
    (2, -32, 43, 'Столовая (двусветный зал) и кухня, склады, рампа хозяйственного въезда'),
    (3, -32, -43, 'Лечебный блок: кабинеты, процедурные, медпост и аптека, библиотека, зал отдыха'),
    (4, -72, -41, 'Спа: крытый бассейн 25 м, сауны, раздевалки; стеклянная стена к озеру'),
    (5, -98, -54, 'Открытый бассейн на подиуме над склоном — чаша с видом на воду (как в «Бухте Коприно»)'),
    (6, -72, 10, 'Парадная терраса с фонтаном — верх главной оси'),
    (7, -40, 112, 'Жилой S-квартал С-1: цепочка модулей-номеров по 2–3 этажа, вход в каждый с улицы, уровни со сдвигом'
                  ' (раскладка условная — ждём рисунок владельца)'),
    (8, -40, -172, 'Жилой S-квартал С-2: то же; в раскрытиях S — детская площадка и сад'),
    (9, 2, 112, 'Улочка вдоль модулей: входы, крыльца, лестницы между уровнями — бой на коротке'),
    (10, 112, 28, 'Въезд: КПП, аллея, главная парковка P1 и круг с фонтаном перед вестибюлем'),
    (11, 41, 196, 'Парковки P2 (С-1) и P3 (С-2) — у каждого корпуса своя'),
    (12, 118, 182, 'Хоздвор: котельная с трубой, прачечная, гаражи, склад, водонапорная башня, трансформаторная'),
    (13, 118, 50, 'Спортплощадка: корты, волейбол — за сеткой'),
    (14, 118, -60, 'Летний театр (эстрада и ряды) в сосновом парке'),
    (15, 86, -190, '10 коттеджей в два ряда у лесной дороги, своя тропа к пляжу'),
    (16, -112, 34, 'Парадная лестница-каскад: марш вниз — площадка — вбок — ещё вбок; киоск, беседка, смотровой балкон'),
    (17, -84, -120, 'Грунтовая тропа-серпантин: беседки, лавки, киоск, родник — свой маршрут к пляжу'),
    (18, -86, -66, 'Лифт к пляжу: шахта у бровки и тоннель к набережной (предложение)'),
    (19, -100, 238, 'Служебная дорога вниз к лодочной станции; рядом ливнёвка по оврагу — скрытый лаз'),
    (20, -150, 228, 'Лодочная станция: эллинг (внутри), слип, стеллажи лодок, склад ГСМ, причальная стенка'),
    (21, -152, -160, 'Пляж: песок, кабинки, грибки, спасательная станция, кафе-киоск'),
    (22, -205, 58, '«Стрелка» — мол-променад 140 м: амфитеатр к воде, фонтан, павильон речного вокзала (2 уровня),'
                   ' кафе, киоски, колоннада, ротонда, маяк, клумбы и стенки, лодки у причала'),
]
for n, x, y, _ in PLACES:
    marker(x, y, n)

# ---------------------------------------------------------------- подписи, масштаб, ориентиры
text(-262, 210, 'О З Е Р О', 22, (70, 100, 130), True)
text(-262, -150, 'к плотине ≈ 1,2 км, на юго-запад', 15, (70, 100, 130), True)
text(-262, -168, '(видна через озеро, фон)', 12, (70, 100, 130))
text(-100, 262, 'овраг с ручьём', 12, MUTED)
text(-100, -262, 'скальный мыс', 12, MUTED)
text(162, 140, 'лес (фон)', 12, MUTED)
# масштабная линейка
bx, by = -300, -255
line([(bx, by), (bx + 100, by)], width=3)
for k in range(0, 101, 25):
    line([(bx + k, by - 2), (bx + k, by + 2)], width=2)
text(bx + 50, by + 7, '100 м', 13)
# север
nx, ny = P(150, 252)
d.polygon([(nx, ny - 18), (nx - 8, ny + 6), (nx + 8, ny + 6)], fill=INK)
d.text((nx, ny + 16), 'С', font=font(14, True), fill=INK, anchor='mm')

d.text((PAD, 18), f'Карта «Санаторий» · схема участка v01 — предложение на обсуждение · суша ≈ {LAND_HA:.1f} га (рамка ~300 × 500 м) + мол',
       font=font(22, True), fill=INK)

# ---------------------------------------------------------------- легенда
LX = PAD + int((XMAX - XMIN) * SCALE) + 30
ly = TOP + PAD
for n, _, _, label in PLACES:
    words = label.split(' ')
    rows, cur = [], ''
    for w in words:
        if len(cur) + len(w) + 1 > 62:
            rows.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    rows.append(cur)
    d.ellipse([LX, ly, LX + 22, ly + 22], fill=(255, 255, 255), outline=INK, width=2)
    d.text((LX + 11, ly + 11), str(n), font=font(12, True), fill=INK, anchor='mm')
    for i, r in enumerate(rows):
        d.text((LX + 32, ly + 3 + i * 17), r, font=font(14), fill=INK)
    ly += max(28, 17 * len(rows) + 9)
ly += 8
for color, label in ((EXIT_C, 'выходы (предложение): В1 — КПП, дорога; В2 — лесная тропа к горам;'),
                     (None, 'В3 — лодка у причала (с условием); В4 — берег за мысом (не каждый рейд)'),
                     (SPAWN_C, 'заходы с края леса и дорог')):
    if color:
        d.ellipse([LX + 4, ly + 4, LX + 18, ly + 18], fill=color, outline=INK)
    d.text((LX + 32, ly + 3), label, font=font(14), fill=INK)
    ly += 26 if color else 22
for color, label in ((STAIR_C, 'парадная лестница (марши и площадки)'), (PATH_C, 'грунтовые тропы'),
                     ((170, 40, 40), 'граница карты: берег, овраг, мыс, забор и опушка')):
    d.line([(LX, ly + 11), (LX + 22, ly + 11)], fill=color, width=4)
    d.text((LX + 32, ly + 3), label, font=font(14), fill=INK)
    ly += 26
for color, label in ((PLATEAU_C, 'плато +32…+38 м (корпуса, парк)'), (SLOPE_C, 'склон: перепад 30 м'),
                     (QUAY_C, 'набережная +2 м, мол +1,5 м'), (SAND_C, 'пляж'), (WATER_C, 'озеро 0 м')):
    d.rectangle([LX, ly + 2, LX + 22, ly + 20], fill=color, outline=INK)
    d.text((LX + 32, ly + 3), label, font=font(14), fill=INK)
    ly += 26

# ---------------------------------------------------------------- разрез по главной оси (y = 0)
SY0 = TOP + PAD * 2 + int((YMAX - YMIN) * SCALE) + 30
d.text((PAD, SY0), 'Разрез по главной оси: въезд — главный корпус — терраса — лестница-каскад — набережная — «Стрелка» '
       '(по вертикали × 1,5)', font=font(17, True), fill=INK)
SX = (W - PAD * 2) / (XMAX - XMIN)
VZ = SX * 1.5
BASE = SY0 + SECTION_H - 100


def S(x, z):
    return (PAD + (x - XMIN) * SX, BASE - z * VZ)


def ground(x):
    if x <= -150:
        return -6.0 + 6.0 * max(0.0, min(1.0, (x + 175) / 25.0))
    if x <= -134:
        return QUAY
    if x <= -88:
        t = (x + 134) / 46.0
        return QUAY + (PLATEAU - QUAY) * t
    return PLATEAU + max(0.0, (x + 88)) * 0.028


xs_ = [XMIN + i * 1.0 for i in range(int(XMAX - XMIN) + 1)]
d.polygon([S(XMIN, -10)] + [S(x, ground(x)) for x in xs_] + [S(XMAX, -10)], fill=(214, 206, 186), outline=INK)
d.polygon([S(XMIN, WATER), S(-150, WATER), S(-150, -6), S(XMIN, -6)], fill=WATER_C)
d.rectangle([*S(-292, MOLE), *S(-148, -1)], fill=QUAY_C, outline=INK)
# лестница-каскад ступеньками по склону
zx = -134.0
for k in range(15):
    x0, x1 = -134 + k * 3.07, -134 + (k + 1) * 3.07
    z = QUAY + (PLATEAU - QUAY) * (k + 1) / 15.0
    d.line([S(x0, z - (PLATEAU - QUAY) / 15.0), S(x0, z), S(x1, z)], fill=STAIR_C, width=3)
for x0, x1, h, label in ((-56, -10, 12.5, 'главный корпус, 3 эт.'), (-88, -56, 8.0, 'бассейн'),
                         (128, 136, 4.0, ''), (-246, -214, 7.0, 'вокзал'), (-176, -160, 4.0, 'кафе')):
    base = ground((x0 + x1) / 2) if x0 > -148 else MOLE
    d.rectangle([*S(x0, base + h), *S(x1, base)], fill=MAIN_C if label.startswith('главный') else BUILD_C, outline=INK)
    if label:
        d.text(S((x0 + x1) / 2, base + h + 3), label, font=font(13), fill=INK, anchor='mb')
d.line([S(-288, MOLE), S(-288, MOLE + 12)], fill=INK, width=3)
d.text(S(-288, MOLE + 13), 'маяк', font=font(13), fill=INK, anchor='mb')
for x, z, label in ((-88, PLATEAU, '+32 бровка'), (-134, QUAY, '+2 набережная'), (-200, MOLE, '+1,5 мол'),
                    (60, ground(60), '+36 въезд'), (-160, WATER, '0 озеро')):
    sx, sz = S(x, z)
    d.line([(sx, sz), (sx, sz + 26)], fill=MUTED, width=1)
    d.text((sx + 3, sz + 28), label, font=font(13), fill=MUTED)
d.text(S(-111, 22), 'лестница: 30 м перепада ≈ 200 ступеней, 17 маршей', font=font(13, True), fill=STAIR_C, anchor='mm')

img.save(OUT)
print(f'санаторий: {OUT.relative_to(ROOT)} · суша {LAND_HA:.1f} га · модулей {MODULE_COUNT} · {W}×{H}')
