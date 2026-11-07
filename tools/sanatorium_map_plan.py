# -*- coding: utf-8 -*-
"""Карта «Санаторий» — схема участка, концепция v03 (docs/design/sanatorium_map.md).

Карта — сама территория санатория на берегу озера под плотиной: около 300 × 500 м суши неправильной формы
(≈ 15 га) и мол «Стрелка» в воду. Плато +32…+38 м над водой, склон 30 м, набережная +2 м.

v03 — жилые корпуса по картинке владельца 2026-11-07: две полудуги, соединённые краями, сплошной двухэтажной лентой
номеров 10 × 6 м (геометрия — tools/sanatorium_s_geom.py), С-1 «S» и С-2 «Ƨ», парковка на 40 мест между ними;
деревья только ели и сосны.

v04 — лифта к пляжу и ливнёвки нет; «Стрелка» — променад, не причал: катеров в озере нет, павильон —
со смотровой площадкой; плотина на юго-западе — мегаструктура (вид с террасы — tools/sanatorium_dam_view.py).

v05 — главный корпус отдельным строением (этажность решает владелец), рядом отдельное одноэтажное здание
«Ресторан и спа» (tools/sanatorium_spa_plan.py) с открытым бассейном на подиуме; амфитеатр южнее на 8 м.

v06 — главный корпус в 2 этажа с лобби в два света (tools/sanatorium_main_corps_plan.py); «Ресторан и спа» — один
общий вход, коридор и три крыла без общих стен; амфитеатр ещё на 10 м южнее.

v07 — амфитеатр и детская площадка по листам малых построек (tools/sanatorium_small_plans.py): 10 рядов
на радиусах 16–28 м (≈ 660 мест) вместо прежних условных 9 «рядов» до 47 м; городки площадки в реальных размерах.

v08 — лестница-каскад и тропа-серпантин по листу спусков (tools/sanatorium_descents_plan.py).

v09 — номер S-корпуса × 1,3 (владелец после прогулки по серому блокауту: «очень тесные номера»): 13 × 7,8 м, радиус оси
ленты 29,6 м. Корпуса стали больше на треть: оба сдвинуты на север (центры на y 147), С-1 — у бровки не ближе 6 м,
С-2 — на восток; парковка между ними сдвинута за корпусами; северная ветка между S-корпусами и хоздвором отодвинута
на восток к x 89,5 (мимо ворот хоздвора).

v02 — правки владельца 2026-11-07: оба S-квартала рядом на севере, у них парковка на 40 мест; на месте нижнего
S — амфитеатр (14); парковка у главного корпуса на 50 мест, у каждого коттеджа своё место; все асфальтовые дороги
сходятся к одному выезду (КПП); большая детская площадка (23); прокат лодок на лодочной станции; на пляже вместо
кафе-киоска — мороженое под зонтиком; на «Стрелке» нет амфитеатра и кафе;
шесть выходов. Остальное — предложение агента.

    python -X utf8 tools/sanatorium_map_plan.py   → docs/plans/sanatorium_map_v09.png (план, разрез по оси, легенда)

Координаты: x — на восток, y — на север, метры; 0 — середина плато у главного корпуса. Озеро на западе,
плотина — за озером на юго-западе (фон, на карту не входит).
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import sanatorium_s_geom as sg

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_map_v09.png'

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
CAR_C = (96, 100, 112)
PLAY_C = (238, 222, 196)
PLAY_INK = (196, 96, 60)

# парковки: место 2,5 × 5 м (машины 1:1), проезд 6 м × 1,3 = 7,8 м (правило масштаба E)
BAY_W, BAY_L, AISLE = 2.5, 5.0, 7.8
CAR_RNG = random.Random(11)


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


def car(x0, y0, x1, y1):
    """Брошенная машина на месте — укрытие средней дистанции."""
    m = 0.35
    rect(x0 + m, y0 + m, x1 - m, y1 - m, fill=CAR_C, outline=None, width=1)


def bay_row(x0, y0, n, along_x, depth_sign):
    """Ряд из n мест: от (x0, y0) вдоль оси, глубина 5 м в сторону depth_sign; возвращает число мест."""
    for k in range(n):
        if along_x:
            a0, a1 = x0 + k * BAY_W, x0 + (k + 1) * BAY_W
            b0, b1 = sorted((y0, y0 + depth_sign * BAY_L))
            line([(a0, b0), (a0, b1)], color=(150, 150, 146), width=1)
            if CAR_RNG.random() < 0.35:
                car(a0, b0, a1, b1)
        else:
            a0, a1 = y0 + k * BAY_W, y0 + (k + 1) * BAY_W
            b0, b1 = sorted((x0, x0 + depth_sign * BAY_L))
            line([(b0, a0), (b1, a0)], color=(150, 150, 146), width=1)
            if CAR_RNG.random() < 0.35:
                car(b0, a0, b1, a1)
    return n


def lot_block(x0, y0, n_near, n_far):
    """Блок парковки вдоль x: два ряда мест по сторонам проезда 7,8 м; ближний к y0 ряд — n_near мест."""
    length = max(n_near, n_far) * BAY_W
    y1 = y0 + BAY_L * 2 + AISLE
    rect(x0, y0, x0 + length + 7.0, y1, fill=PARK_C, outline=MUTED, width=1)
    return bay_row(x0, y0, n_near, True, 1) + bay_row(x0, y1, n_far, True, -1)


def lot_block_y(x0, y0, n_near, n_far):
    """Блок парковки вдоль y: ряд n_near мест у x0 и ряд n_far у дальнего края, проезд 7,8 м посередине, въезд с севера."""
    length = max(n_near, n_far) * BAY_W
    x1 = x0 + BAY_L * 2 + AISLE
    rect(x0, y0, x1, y0 + length + 7.0, fill=PARK_C, outline=MUTED, width=1)
    return bay_row(x0, y0, n_near, False, 1) + bay_row(x1, y0, n_far, False, -1)


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
# Владелец: амфитеатра и кафе нет; «Стрелка» остаётся стрелкой, а не причалом — катеров нет. Фонтанная площадь,
# павильон со смотровой площадкой, киоски, колоннада, ротонда, маяк, клумбы и низкие стенки — укрытия
circle(-182, 10, 9, fill=POOL_C)
rect(-246, 0, -214, 20, fill=BUILD_C)                     # павильон (2 уровня, смотровая площадка на крыше)
for kx, ky in ((-200, -8), (-262, 18), (-232, 30)):       # киоски (владелец: оставить)
    rect(kx - 3, ky - 2.5, kx + 3, ky + 2.5, fill=BUILD_C, width=1)
for k in range(10):
    circle(-192 - k * 5.5, 36 - k * 0.9, 0.9, fill=INK, width=1)
circle(-270, 10, 5, fill=BUILD_C)
circle(-288, 10, 2.6, fill=(240, 200, 80))
for px_, py_ in ((-192, 2), (-206, 18), (-226, -6), (-252, 10), (-170, -8), (-240, 36),
                 (-166, 30), (-172, 22), (-176, -16), (-212, -12), (-196, -13)):   # клумбы, стенки, лавки
    rect(px_ - 3.5, py_ - 1.2, px_ + 3.5, py_ + 1.2, fill=(160, 180, 120), width=1)

# ---------------------------------------------------------------- набережная: лодочная станция, пляж
rect(-152, 188, -134, 206, fill=BUILD_C)                 # эллинг
poly([(-152, 192), (-170, 194), (-170, 200), (-152, 202)], fill=QUAY_C, outline=INK)   # слип
rect(-146, 214, -136, 222, fill=BUILD_C, width=1)        # склад ГСМ
line([(-150, 174), (-186, 176)], width=4)                 # причальная стенка-пальчик
for k in range(4):
    rect(-140 + 0, 160 + k * 6, -132, 163 + k * 6, fill=(250, 250, 250), width=1)  # стеллажи лодок
# прокат (владелец, v02): домик выдачи, стойки сапов и каяков, плавучий понтон — катамараны и лодки с вёслами
rect(-146, 134, -136, 144, fill=BUILD_C)
for k in range(5):
    line([(-133, 133 + k * 3.2), (-129, 133 + k * 3.2)], color=(210, 120, 50), width=3)
poly([(-149, 138), (-184, 140), (-184, 143), (-149, 141)], fill=(200, 186, 160), outline=INK)
for k in range(4):                                         # катамараны — к югу от понтона
    for dy in (0.0, 2.6):
        rect(-178 + k * 8, 132.4 + dy, -173 + k * 8, 133.6 + dy, fill=(240, 240, 250), width=1)
for k in range(4):                                         # лодки с вёслами — к северу
    poly([(-178 + k * 8, 145), (-172 + k * 8, 145), (-173 + k * 8, 147.5), (-177 + k * 8, 147.5)], fill=(250, 250, 250), outline=INK)
rect(-142, -128, -130, -116, fill=BUILD_C)               # спасательная станция
for k in range(6):
    rect(-140, -150 - k * 9, -136, -146 - k * 9, fill=BUILD_C, width=1)   # кабинки
for k in range(10):
    circle(-152 + (k % 2) * 6, -100 - k * 12, 2.0, fill=(240, 160, 90), width=1)   # грибки
# вместо кафе-киоска (владелец, v02) — станция мороженого под зонтиком
circle(-134, -102, 3.2, fill=(240, 120, 150), width=1)
rect(-135.2, -103, -132.8, -101, fill=(250, 250, 250), width=1)

# ---------------------------------------------------------------- дороги и парковки
# Все асфальтовые дороги сходятся к одному выезду — КПП на востоке (владелец, v02): ось к главному корпусу,
# северная ветка к парковке S-кварталов и хоздвору (от неё служебная вниз к лодочной станции), южная — к коттеджам.
# Ветки идут через сосновый парк с изгибами: прямой асфальт на 400 м дал бы сквозной прострел через всю карту.
ROAD = 9.0
ROAD_X = 82.0      # развилка на оси
# v09: номер × 1,3 — корпуса больше; центры корпусов и парковка между ними — от их размера
S_OY, S1_OX, S2_OX = 147.0, -52.3, 45.6                 # С-1 — не ближе 6 м к бровке, С-2 — до северной ветки
S_LOT_X0 = S1_OX + sg.R + sg.HALF_T + sg.PATH_W + 3.05  # парковка между корпусами С-1 и С-2
S_LOT_Y0 = S_OY - 28.5
S_AISLE_X = S_LOT_X0 + BAY_L + AISLE / 2
S_LOT_Y1 = S_LOT_Y0 + 20 * BAY_W + 7.0
ROADS = [  # (линия, ширина, м)
    ([(170, 0), (ROAD_X, 0)], ROAD),
    ([(ROAD_X, 0), (10, 0)], 7.0),
    ([(ROAD_X, 0), (76, 36), (74, 70), (86, 108), (88, 140), (89.5, 168), (89.5, 196), (82, 222)], 7.0),   # северная ветка (v09 — восточнее)
    ([(S_AISLE_X, S_LOT_Y1), (S_AISLE_X, 224.6)], 6.0),                                                # к парковке S-корпусов
    ([(89.5, 196), (96, 196)], 6.0),                                                                    # в хоздвор
    ([(82, 222), (-60, 226), (-100, 232), (-90, 214), (-128, 206), (-138, 196)], 5.0),                  # служебная к лодочной станции
    ([(ROAD_X, 0), (88, -40), (90, -80), (76, -128), (72, -170), (ROAD_X, -213)], 7.0),                # южная ветка
    ([(4, -213), (136, -213)], 6.0),                                                                    # улица коттеджей
    ([(6, -11), (2, -24), (-16, -24), (-16, -30)], 5.0),                                                 # хозпроезд к кухне
]
for pts, w in ROADS:
    line(pts, color=ROAD_C, width=int(w * SCALE))
circle(10, 0, 12, fill=ROAD_C, outline=None)
circle(10, 0, 5.5, fill=POOL_C)                          # фонтан на кругу у входа
for ex in (4, 136):
    circle(ex, -213, 6, fill=ROAD_C, outline=None)                               # разворот
# парковка у главного корпуса — 50 мест: два блока по сторонам оси
BAYS_MAIN = lot_block(26, 6, 12, 13) + lot_block(26, -6 - BAY_L * 2 - AISLE, 13, 12)
text(46, 30, f'P · {BAYS_MAIN}', 14, MUTED, True)
# парковка S-корпусов — 40 мест между корпусами (владелец): ряды мест смотрят на оба корпуса, заезд с севера
BAYS_S = lot_block_y(S_LOT_X0, S_LOT_Y0, 20, 20)
text(S_AISLE_X, S_LOT_Y0 - 4, f'P · {BAYS_S}', 14, MUTED, True)
rect(136, -6, 144, 6, fill=BUILD_C)                      # КПП — единственный выезд
line([(134, -8), (134, 8)], color=(200, 40, 40), width=3)

# ---------------------------------------------------------------- главный корпус — отдельное строение (владелец, v05)
# v06: 2 этажа (владелец) — лобби в два света с панорамными окнами, служебные; на 2 этаже администрация и сейф
rect(-54, -20, -10, 16, fill=MAIN_C)
rect(-54, -4, -10, 16, fill=(250, 238, 214), width=1)    # лобби в два света
# ---------------------------------------------------------------- здание «Ресторан и спа» (владелец, v05; план — tools/sanatorium_spa_plan.py)
# v02 (владелец): один общий вход с ресепшеном, коридор, из него три крыла — ресторан, бассейн, фитнес и процедуры;
# крылья не касаются друг друга (между ними дворики)
rect(-24, -48, -8, -30, fill=(206, 204, 198), outline=MUTED, width=1)   # хоздвор кухни
rect(-6, -60, 12, -42, fill=MAIN_C)                      # вестибюль, длинный ресепшен
rect(-70, -56, -6, -52, fill=BUILD_C, width=1)           # коридор к трём крыльям
for x0_, y0_, x1_, y1_ in ((-70, -52, -66, -48), (-58, -60, -54, -56), (-24, -60, -20, -56)):
    rect(x0_, y0_, x1_, y1_, fill=BUILD_C, width=1)      # переходы в крылья
rect(-96, -48, -24, -30, fill=MAIN_C)                    # крыло ресторана: зал, лаунж, кухня, служебный вход
rect(-88, -30, -76, -20, fill=MAIN_C)                    # гостевой вход ресторана: коридор с гардеробом
line([(-80, -16), (-86, -20)], color=(218, 210, 196), width=int(3 * SCALE))  # дорожка от террасы
rect(-96, -102, -44, -60, fill=(206, 232, 240))          # крыло бассейна: раздевалки, душевые, холл, бассейн, бани
rect(-60, -108, -44, -102, fill=BUILD_C, width=1)        # техника бассейнов
rect(-38, -102, -6, -60, fill=MAIN_C)                    # крыло фитнеса и процедур
rect(-90, -88, -65, -75.5, fill=POOL_C, width=1)
rect(-124, -102, -96, -66, fill=(232, 228, 214), outline=INK, width=2)  # подиум открытого бассейна над склоном
rect(-120, -88, -100, -75.5, fill=POOL_C, width=1)       # открытая чаша, перелив к озеру
rect(-100, -83.25, -90, -80.25, fill=POOL_C, outline=None)  # проплыв из крытой чаши
rect(-112, -48, -96, -30, fill=(222, 206, 176), outline=MUTED, width=1)  # терраса ресторана (выход только наружу)
line([(8, -12), (3, -42)], color=(218, 210, 196), width=int(3 * SCALE))  # дорожка от площади к общему входу
rect(-86, -16, -56, 16, fill=(232, 228, 214), outline=MUTED, width=1)   # парадная терраса
circle(-72, 0, 5, fill=POOL_C, width=1)

# ---------------------------------------------------------------- жилые S-корпуса (картинка владельца 2026-11-07)
# Корпус — две полудуги, соединённые краями, сплошной двухэтажной лентой номеров 10 × 6 м (tools/sanatorium_s_geom.py,
# лист корпуса — tools/sanatorium_s_corps_plan.py). С-1 — «S», С-2 — зеркальный «Ƨ», парковка между ними (решение
# владельца): фасад входов обоих корпусов смотрит на парковку, фасад террас — от неё.
S_SITES = [(S1_OX, S_OY, False, 'С-1'), (S2_OX, S_OY, True, 'С-2')]
PAVE_C = (218, 210, 196)
TERRACE_C = (214, 190, 150)
WOOD_C = (150, 110, 70)
UNIT_COUNT = 0
WARN = []
NO_TREE = []      # оси лент корпусов: деревья — не на корпусе, террасах и дорожках
for ox, oy, mirror, name in S_SITES:
    for cx, cy, a0, a1, ent_inner in sg.halves(ox, oy, mirror):
        r_ent = sg.face_r(ent_inner, True)
        r_ter = sg.face_r(ent_inner, False)
        sgn_ent = 1.0 if r_ent > sg.R else -1.0
        poly(sg.ring_seg(cx, cy, r_ent, r_ent + sgn_ent * sg.PATH_W, a0, a1), fill=PAVE_C, outline=None)
        poly(sg.ring_seg(cx, cy, r_ter, r_ter - sgn_ent * sg.TERRACE, a0, a1), fill=TERRACE_C, outline=None)
        NO_TREE.append((sg.arc(cx, cy, sg.R, a0, a1, 6.0), sg.HALF_T * 2 + sg.TERRACE * 2 + 4.0))
    for u in sg.units(ox, oy, mirror):
        UNIT_COUNT += 1
        poly(sg.ring_seg(u['cx'], u['cy'], sg.R - sg.HALF_T, sg.R + sg.HALF_T, u['a0'], u['a1']),
             fill=(214, 228, 242) if u['n'] % 2 else (190, 208, 228), outline=INK, width=1)
        sa = sg.stair_angle(u)          # лестница у стены — глухой фасад в доске
        poly(sg.ring_seg(u['cx'], u['cy'], sg.R - sg.HALF_T, sg.R + sg.HALF_T, u['a0'], u['a0'] + sa), fill=WOOD_C, outline=None)
        r_ent = sg.face_r(u['entrance_inner'], True)
        am = math.radians(u['a0'] + sa * 1.5)
        dx, dy = u['cx'] + r_ent * math.cos(am), u['cy'] + r_ent * math.sin(am)
        circle(dx, dy, 0.9, fill=(200, 60, 40), outline=None)            # входная дверь
        for x, y in sg.ring_seg(u['cx'], u['cy'], sg.R - sg.HALF_T - sg.TERRACE, sg.R + sg.HALF_T + sg.TERRACE,
                                u['a0'], u['a1'], 30.0):
            if x < brow_x(y) + 6.0:
                WARN.append(f'{name}: номер {u["n"]} у бровки ({x:.0f}, {y:.0f})')
    text(ox, oy + (-sg.R if not mirror else sg.R), name, 15, INK, True)

# дорожки от парковки: во двор верхней полудуги каждого корпуса и к выпуклому фасаду нижней; тротуары вдоль рядов
S_LOT_X1 = S_LOT_X0 + BAY_L * 2 + AISLE
for xa, xb, y in ((S_LOT_X0, S1_OX + sg.R - sg.HALF_T - sg.PATH_W, S_OY + sg.R),
                  (S_LOT_X1, S2_OX - sg.R + sg.HALF_T + sg.PATH_W, S_OY + sg.R),
                  (S_LOT_X0, S1_OX + sg.R + sg.HALF_T + sg.PATH_W, S_OY - sg.R),
                  (S_LOT_X1, S2_OX - sg.R - sg.HALF_T - sg.PATH_W, S_OY - sg.R)):
    line([(xa, y), (xb, y)], color=PAVE_C, width=int(sg.PATH_W * SCALE))
for xs in (S_LOT_X0 - 1.5, S_LOT_X1 + 1.5):
    line([(xs, S_LOT_Y0 - 6), (xs, S_LOT_Y1 + 3)], color=PAVE_C, width=int(sg.PATH_W * SCALE))

# ---------------------------------------------------------------- хоздвор, спорт, летний театр, коттеджи
# хоздвор — в северо-восточном углу внутри забора (в v01 часть построек вылезала за границу)
rect(96, 178, 118, 194, fill=BUILD_C)                    # котельная
circle(123, 186, 3, fill=(150, 90, 70))                  # труба — ориентир
rect(96, 200, 114, 212, fill=BUILD_C)                    # прачечная
rect(126, 158, 140, 182, fill=BUILD_C)                   # гаражи
circle(122, 204, 4, fill=BUILD_C)                        # водонапорная башня
rect(98, 162, 108, 170, fill=BUILD_C, width=1)           # трансформаторная
rect(110, 160, 122, 172, fill=BUILD_C, width=1)          # склад
rect(96, 52, 140, 100, fill=(204, 196, 176), outline=MUTED, width=1)   # корты и волейбол
line([(118, 52), (118, 100)], color=MUTED, width=1)

# 14 — амфитеатр на месте нижнего S-квартала (владелец, v02): сцена у бровки, задник — озеро и закат,
# ряды поднимаются к востоку, поверху колоннада-галерея; под сценой — служебные помещения
AMPH = (-84.0, -160.0)                        # v07: как на листе амфитеатра (tools/sanatorium_small_plans.py)
for k in range(11):                                       # 10 рядов по 1,2 м на радиусах 16–28 м, ≈ 660 мест
    r = 16.0 + k * 1.2
    d.arc([*P(AMPH[0] - r, AMPH[1] + r), *P(AMPH[0] + r, AMPH[1] - r)], -62, 62, fill=MUTED, width=1)
for a in (-40, 0, 40):                                    # радиальные проходы
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    line([(AMPH[0] + 16 * ca, AMPH[1] + 16 * sa), (AMPH[0] + 28 * ca, AMPH[1] + 28 * sa)], color=PLATEAU_C, width=3)
for k in range(17):                                       # верхний променад с колоннадой
    a = math.radians(-64 + k * 8)
    circle(AMPH[0] + 32 * math.cos(a), AMPH[1] + 32 * math.sin(a), 0.7, fill=INK, width=1)
rect(-92, -170, -80, -150, fill=BUILD_C)                  # сцена
rect(-92, -150, -84, -144, fill=BUILD_C, width=1)         # кулисы с лестницами вниз
rect(-92, -176, -84, -170, fill=BUILD_C, width=1)
rect(-57, -162, -53, -158, fill=BUILD_C, width=1)         # аппаратная

# 15 — коттеджи: 10 шт. по сторонам своей улицы, у каждого своё парковочное место (владелец, v02)
COTTAGES = [(x, y) for y in (-199.0, -227.0) for x in (14.0, 38.0, 62.0, 94.0, 118.0)]
for cx_, cy_ in COTTAGES:
    rect(cx_ - 7, cy_ - 6, cx_ + 7, cy_ + 6, fill=(232, 214, 196))
    px0 = cx_ + 8.0                                        # место — сбоку от дома, выезд на улицу
    py0, py1 = (-210.0, -204.0) if cy_ > -213 else (-222.0, -216.0)
    rect(px0, py0, px0 + 3.5, py1, fill=PARK_C, outline=MUTED, width=1)
    if CAR_RNG.random() < 0.5:
        car(px0 + 0.4, py0, px0 + 3.1, py1)

# 23 — детская площадка (владелец; состав — tools/sanatorium_small_plans.py): городки в реальных размерах
PG = (0.0, -150.0, 60.0, -96.0)
rect(*PG, fill=PLAY_C, outline=MUTED, width=1)
rect(2, -138, 26, -98, fill=(226, 170, 160), outline=None)                                                          # красное покрытие
rect(24, -110, 52, -97, fill=(186, 214, 176), outline=None)                                                         # зелёное — качели
rect(46, -150, 60, -124, fill=(180, 198, 226), outline=None)                                                        # синее — малыши
line([(PG[0], PG[1]), (PG[2], PG[1]), (PG[2], PG[3]), (PG[0], PG[3]), (PG[0], PG[1])], color=(60, 110, 70), width=2)
poly([(9, -136.5), (21, -136.5), (23, -134), (21, -131.5), (9, -131.5)], fill=(250, 250, 250), outline=PLAY_INK)   # корабль
rect(10, -113, 22, -111, fill=(250, 250, 250), outline=PLAY_INK)                                                   # самолёт
rect(15, -117, 17, -107, fill=(250, 250, 250), outline=PLAY_INK)
rect(42, -113.5, 53, -110.5, fill=(250, 250, 250), outline=PLAY_INK)                                               # грузовик
circle(46, -136, 4.0, fill=None, outline=PLAY_INK, width=2)                                                        # верёвочная пирамида
rect(26, -102, 42, -100, fill=None, outline=PLAY_INK, width=2)                                                     # качели
rect(44, -102, 50, -100, fill=None, outline=PLAY_INK, width=2)
for x_ in (30, 35):
    circle(x_, -142, 1.5, fill=(60, 60, 64), outline=None)                                                         # батуты
circle(31, -131, 1.5, fill=(240, 200, 80), outline=PLAY_INK, width=1)                                              # карусель
rect(51, -147, 58, -141, fill=(232, 216, 170), outline=PLAY_INK, width=1)                                          # песочница

# ---------------------------------------------------------------- спуски к воде
# 1 — парадная лестница-каскад по оси (лист — tools/sanatorium_descents_plan.py): марш вниз (15 ступеней) — галерея
# вбок с короткими маршами — марш вниз — галерея в другую сторону …; 17 маршей, 200 ступеней, на подпорных стенках
GRAND = [(-86, 0), (-92.8, 0), (-92.8, 22), (-102.2, 22), (-102.2, -22), (-111.6, -22), (-111.6, 22), (-121, 22),
         (-121, 0), (-127.8, 0)]
line(GRAND, color=STAIR_C, width=int(5.2 * SCALE * 0.6))
for p in GRAND[1:-1]:
    rect(p[0] - 2.6, p[1] - 2.6, p[0] + 2.6, p[1] + 2.6, fill=(240, 220, 210), outline=STAIR_C, width=1)
rect(-95, 25.6, -91, 29.6, fill=BUILD_C, width=1)        # киоск на площадке
circle(-102.2, -29.5, 3, fill=BUILD_C, width=1)          # беседка-ротонда
rect(-114, 24.6, -109.2, 29.4, fill=(240, 220, 210), outline=STAIR_C, width=1)   # смотровой балкон
# 2 — грунтовая тропа-серпантин южнее: шесть колен вдоль склона, беседки, лавка, ларёк, родник
TRAIL = [(-97, -106), (-101, -146), (-106, -148), (-108, -112), (-113, -110), (-117, -150), (-121, -152), (-123, -118),
         (-127, -120), (-131, -160), (-135, -168)]
line(TRAIL, color=PATH_C, width=3, dash=(9, 5))
for gx, gy in ((-116.5, -107.5), (-130, -116.5)):        # беседки
    circle(gx, gy, 2.4, fill=BUILD_C, width=1)
rect(-97, -105, -93, -101, fill=BUILD_C, width=1)        # ларёк у начала
circle(-104, -150.5, 1.4, fill=POOL_C, width=1)          # родник
line([(-96, -160), (-101, -150), (-101, -146)], color=PATH_C, width=2, dash=(5, 4))   # выход из-под сцены к тропе
# 3 — тропа от коттеджей к пляжу
line([(-2, -216), (-40, -222), (-90, -214), (-104, -228), (-118, -218), (-130, -230)], color=PATH_C, width=3, dash=(9, 5))
# лифта к пляжу и ливнёвки нет (владелец, v04): спусков три — лестница, тропа, служебная дорога

# ---------------------------------------------------------------- деревья: только ели и сосны (владелец 2026-11-07)
rng = random.Random(7)
KEEP = [(-60, -26, 24, 26), (-110, -20, -54, 24), (22, -28, 70, 28), (-128, -112, 16, -26),
        (S_LOT_X0 - 5.5, S_LOT_Y0 - 8, S_LOT_X1 + 3, S_LOT_Y1 + 4), (92, 48, 144, 104), (92, 156, 146, 216), (-98, -196, -50, -124),
        (-4, -154, 64, -92), (-4, -238, 146, -188)]


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - ax - dx * t, py - ay - dy * t)


def free(x, y):
    for x0, y0, x1, y1 in KEEP:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return False
    for pts, w in ROADS:     # деревья — вдоль дорог, но не на асфальте
        if min(seg_dist(x, y, a, b) for a, b in zip(pts, pts[1:])) < w * 0.5 + 3.0:
            return False
    for pts, w in NO_TREE:
        if min(seg_dist(x, y, a, b) for a, b in zip(pts, pts[1:])) < w * 0.5:
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
# шесть выходов (владелец, v02); места и условия — предложение агента
EXITS = [(160, 0, 'В1', -9, 9, 'rm'), (130, 238, 'В2', -9, 6, 'rm'), (-20, 240, 'В3', 9, 6, 'lm'),
         (-188, 141, 'В4', -9, 0, 'rm'), (-300, 10, 'В5', 0, -12, 'mm'), (-112, -262, 'В6', -9, 0, 'rm')]
for x, y, label, ox_, oy_, anc in EXITS:
    circle(x, y, 6, fill=EXIT_C, outline=INK)
    text(x + ox_, y + oy_, label, 13, EXIT_C, True, anc)
for x, y in ((160, 60), (160, -120), (40, 258), (100, -258)):
    poly([(x, y + 6), (x - 5, y - 4), (x + 5, y - 4)], fill=SPAWN_C, outline=INK)

PLACES = [
    (1, -32, -2, 'Главный корпус, 2 этажа: лобби в два света — длинный ресепшен, бар, диваны; за служебной дверью —'
                 ' помещения персонала и лестница с краю; на 2 этаже администрация и сейф'),
    (2, -75, -39, 'Здание «Ресторан и спа»: один общий вход с ресепшеном, коридор к трём крыльям; ресторан'
                  ' с выходом на террасу только наружу, кухня со служебным входом'),
    (3, -22, -82, 'Крыло фитнеса и процедур: тренажёрный зал, ЛФК, водолечебница, физиокабинеты, массаж,'
                  ' ингаляторий, соляная пещера'),
    (4, -70, -80, 'Крыло бассейна: раздевалки → душевые → холл → бассейн 25 м, бани на 6–7 человек,'
                  ' зона тишины со спа-баром'),
    (5, -110, -95, 'Открытый бассейн на подиуме над склоном, проплыв из крытого, лежаки'),
    (6, -72, 10, 'Парадная терраса с фонтаном — верх главной оси'),
    (7, S1_OX, S_OY + sg.R, 'Жилой корпус С-1 («S»): две полудуги, соединённые краями, — лента из 14 номеров по 2 этажа,'
                  ' номер 13 × 7,8 м по внутренним стенам (v09 — × 1,3), вход с улицы со стороны парковки, терраса и балкон —'
                  ' с другой'),
    (8, S2_OX, S_OY - sg.R, 'Жилой корпус С-2 («Ƨ», зеркальный): то же, 14 номеров'),
    (9, S_AISLE_X, S_LOT_Y0 - 21, 'Дворы полудуг и дорожки от машин к дверям: ближний бой у стекла, деревянных пилонов и экранов террас'),
    (10, 110, 18, 'Въезд: КПП — единственный выезд, сосновая аллея, парковка у главного корпуса на 50 мест, круг с фонтаном'),
    (11, S_AISLE_X, S_OY, 'Парковка S-корпусов на 40 мест между ними: до любой двери ≤ 60 м пешком; асфальт от служебной дороги'),
    (12, 110, 220, 'Хоздвор: котельная с трубой, прачечная, гаражи, склад, водонапорная башня, трансформаторная'),
    (13, 118, 44, 'Спортплощадка: корты, волейбол — за сеткой'),
    (14, -66, -160, 'Амфитеатр ≈ 660 мест, 10 рядов: сцена у бровки, задник — озеро и плотина; под сценой —'
                    ' гримёрки, склад, щитовая, выход к тропе'),
    (15, 78, -232, '10 коттеджей на своей улице, у каждого своё парковочное место; своя тропа к пляжу'),
    (16, -107, 34, 'Лестница-каскад: 17 маршей, 200 ступеней — вниз, вбок, вниз, вбок; киоск, ротонда, смотровой балкон'),
    (17, -140, -138, 'Тропа-серпантин 220 м: шесть колен, две беседки, лавка, ларёк, родник; от неё — выход под сцену амфитеатра'),
    (19, -100, 240, 'Служебная дорога серпантином вниз к лодочной станции'),
    (20, -150, 228, 'Лодочная станция: эллинг (внутри), слип, стеллажи лодок, склад ГСМ, причальная стенка;'
                    ' прокат — домик выдачи, сапы, каяки, лодки с вёслами, катамараны у понтона'),
    (21, -152, -160, 'Пляж: песок, кабинки, грибки, спасательная станция, мороженое под зонтиком'),
    (22, -205, 58, '«Стрелка» — мол-променад 140 м, не причал: фонтан, павильон в 2 уровня со смотровой площадкой,'
                   ' киоски, колоннада, ротонда, маяк, клумбы и стенки'),
    (23, 30, -88, 'Детская площадка: городки «корабль», «самолёт», «грузовик», верёвочная пирамида, качели,'
                  ' батуты, качалки, карусель, песочница'),
]
for n, x, y, _ in PLACES:
    marker(x, y, n)

# ---------------------------------------------------------------- подписи, масштаб, ориентиры
text(-262, 210, 'О З Е Р О', 22, (70, 100, 130), True)
text(-262, -150, 'плотина ≈ 1,2 км на юго-запад:', 15, (70, 100, 130), True)
text(-262, -168, 'стена 260 м целиком — озеро нижнее', 13, (70, 100, 130), True)
text(-262, -184, '(вид с террасы — отдельный лист)', 12, (70, 100, 130))
text(-100, 262, 'овраг с ручьём', 12, MUTED)
text(-58, -267, 'скальный мыс', 12, MUTED)
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

d.text((PAD, 18), f'Карта «Санаторий» · схема участка v09 (номер S-корпуса × 1,3) — правки владельца 2026-11-07 · суша ≈ {LAND_HA:.1f} га (рамка ~300 × 500 м) + мол',
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
for color, label in ((EXIT_C, 'шесть выходов: В1 — КПП, единственный выезд; В2 — лесная тропа к горам;'),
                     (None, 'В3 — труба под служебной дорогой в овраг; В4 — прокат: каяк или лодка;'),
                     (None, 'В5 — моторка у маяка «Стрелки»; В6 — берег за мысом (условия — в описании)'),
                     (SPAWN_C, 'заходы с края леса и дорог'),
                     (CAR_C, f'парковки: у главного корпуса {BAYS_MAIN}, у S-корпусов {BAYS_S}, у коттеджей по одному месту')):
    if color:
        d.ellipse([LX + 4, ly + 4, LX + 18, ly + 18], fill=color, outline=INK)
    d.text((LX + 32, ly + 3), label, font=font(14), fill=INK)
    ly += 26 if color else 22
for color, label in ((STAIR_C, 'парадная лестница (марши и площадки)'), (PATH_C, 'грунтовые тропы'),
                     (WOOD_C, 'S-корпус: номер, глухая часть фасада над лестницей (доска), красная точка — дверь'),
                     ((98, 128, 92), 'деревья — только ели и сосны'),
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
    if x <= -127.8:
        return QUAY
    if x <= -86:
        t = (x + 127.8) / 41.8
        return QUAY + (PLATEAU - QUAY) * t
    return PLATEAU + max(0.0, (x + 86)) * 0.028


xs_ = [XMIN + i * 1.0 for i in range(int(XMAX - XMIN) + 1)]
d.polygon([S(XMIN, -10)] + [S(x, ground(x)) for x in xs_] + [S(XMAX, -10)], fill=(214, 206, 186), outline=INK)
d.polygon([S(XMIN, WATER), S(-150, WATER), S(-150, -6), S(XMIN, -6)], fill=WATER_C)
d.rectangle([*S(-292, MOLE), *S(-148, -1)], fill=QUAY_C, outline=INK)
# лестница-каскад ступеньками по склону
for k in range(17):                                       # 17 маршей каскада в разрезе — условно, по оси
    x0, x1 = -127.8 + k * 2.46, -127.8 + (k + 1) * 2.46
    z = QUAY + (PLATEAU - QUAY) * (k + 1) / 17.0
    d.line([S(x0, z - (PLATEAU - QUAY) / 17.0), S(x0, z), S(x1, z)], fill=STAIR_C, width=3)
for x0, x1, h, label in ((-54, -10, 8.9, 'главный корпус, 2 эт.'),
                         (136, 144, 4.0, ''), (-246, -214, 7.0, 'павильон')):
    base = ground((x0 + x1) / 2) if x0 > -148 else MOLE
    d.rectangle([*S(x0, base + h), *S(x1, base)], fill=MAIN_C if label.startswith('главный') else BUILD_C, outline=INK)
    if label:
        d.text(S((x0 + x1) / 2, base + h + 3), label, font=font(13), fill=INK, anchor='mb')
d.line([S(-288, MOLE), S(-288, MOLE + 12)], fill=INK, width=3)
d.text(S(-288, MOLE + 13), 'маяк', font=font(13), fill=INK, anchor='mb')
for x, z, label in ((-86, PLATEAU, '+32 терраса'), (-127.8, QUAY, '+2 набережная'), (-200, MOLE, '+1,5 мол'),
                    (60, ground(60), '+36 въезд'), (-160, WATER, '0 озеро')):
    sx, sz = S(x, z)
    d.line([(sx, sz), (sx, sz + 26)], fill=MUTED, width=1)
    d.text((sx + 3, sz + 28), label, font=font(13), fill=MUTED)
d.text(S(-111, 22), 'лестница: 30 м перепада ≈ 200 ступеней, 17 маршей', font=font(13, True), fill=STAIR_C, anchor='mm')

img.save(OUT)
for w in WARN:
    print('ВНИМАНИЕ:', w)
print(f'санаторий: {OUT.relative_to(ROOT)} · суша {LAND_HA:.1f} га · мест: главный корпус {BAYS_MAIN},'
      f' S-корпуса {BAYS_S}, коттеджи {len(COTTAGES)} · номеров {UNIT_COUNT} · {W}×{H}')
