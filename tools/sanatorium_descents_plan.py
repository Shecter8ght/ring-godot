# -*- coding: utf-8 -*-
"""Санаторий — спуски к воде v03: лестница-каскад (16) и общая сеть троп (17, 3): план, марши, профили, точки.

Решения владельца (docs/design/sanatorium_map.md, §1): вода ниже санатория, к ней спускаются не по прямой, а по
лестницам — вниз, потом в сторону, потом ещё в сторону; параллельно — грунтовая тропа другим маршрутом; по пути
лавочки, небольшие беседки, киоски. Лифта и ливнёвки нет. Деревья — только ели и сосны. Вид — картинки 16 и 17
(docs/design/sanatorium_visual.md), планировку с картинок не брать. Остальное — предложение агента
(docs/design/sanatorium_descents.md).

v02 — владелец после прогулки по серому блокауту: каскад и тропа «слишком сжатые и тесные — удлинить, сделать
просторнее и масштабнее», береговая линия дальше. Склон стал длиннее (схема участка v11: урез на 45 м западнее,
бровка на месте) — каскад 74 м по горизонтали вместо 42: марш 7,8 м вместо 5,2, марш «вниз» с площадками по 2,25 м
сверху и снизу, галереи вдвое дальше друг от друга, на север до +34 м; тропа — колена через 10 м вместо 4–5 м.

v03 — владелец: тропы «сделать общими — пересекаться, меньше сегментов, естественнее». Трассы проложены по рельефу
блокаута с ровным уклоном ≈ 13 % (разовая трассировка по склону, координаты ниже): серпантин — три колена
с плавными поворотами вместо десяти отрезков; тропа от коттеджей спускается от бровки у мыса и сходится с ним
на развилке у родника, ниже — общая; тропка из-под сцены — к первому колену. Высоты — по рельефу блокаута.

Каскад — постройка на подпорных стенках: уровни площадок задаёт лестница, склон под ней террасирован. Ступени 1:1 —
подъём 0,15, проступь 0,30 (уличные); ширина марша 6 × 1,3 = 7,8 м (правило E). Координаты — схемы участка.

    python -X utf8 tools/sanatorium_descents_plan.py
        → docs/plans/sanatorium_descents_v03.png, docs/design/data/sanatorium_descents_v03.json
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_descents_v03.png'
DATA = ROOT / 'docs/design/data/sanatorium_descents_v03.json'

RISE, RUN, WIDTH = 0.15, 0.30, 7.8
TERRACE_Z, QUAY_Z = 32.0, 2.0
TOP_X = -86.0                 # край парадной террасы (+32)
STONE = (226, 222, 212)
STEP_C = (206, 200, 186)
WALL_C = (120, 116, 108)

# ----------------------------------------------------------------------------- каскад: путь и марши
# Спуски «вниз» — марши по 15 подъёмов поперёк склона (на запад) с площадками сверху и снизу; «в сторону» — галереи
# вдоль склона (по y) с короткими маршами по 10–11 подъёмов и площадками. Итого 17 маршей, 200 подъёмов, 30 м.
LINK_RISERS = 15
LINK_LEN = 8.7                # марш 4,2 м и две площадки по 2,25 м
N_END, S_END = 34.0, -20.0    # галереи — от оси на север до +34, на юг до −20 (южнее — терраса ресторана)
GALLERY_RUNS = [(0.0, N_END, (10, 11)), (N_END, S_END, (10, 11, 10, 11)), (S_END, N_END, (10, 11, 10, 11)), (N_END, 0.0, (10, 10))]
TRAV = []                     # (x оси галереи, y начала, y конца, марши подъёмов)
LINKS = []                    # (x верх, x низ, y)
x_ = TOP_X
for k in range(5):
    y_link = 0.0 if k in (0, 4) else (N_END if k in (1, 3) else S_END)
    LINKS.append((x_, x_ - LINK_LEN, y_link))
    x_ -= LINK_LEN
    if k < 4:
        ya, yb, runs = GALLERY_RUNS[k]
        TRAV.append((x_ - WIDTH / 2, ya, yb, runs))
        x_ -= WIDTH
BOTTOM_X = x_

elements = []      # (вид, прямоугольник, z верх, z низ, подъёмов, ось, номер марша «вниз» / галереи)
z = TERRACE_Z
profile = [(0.0, z)]
dist = 0.0
flights = 0
risers_total = 0


def flight_run(n):
    return (n - 1) * RUN


for i, (x0, x1, y) in enumerate(LINKS):
    run = flight_run(LINK_RISERS)
    pad = (abs(x1 - x0) - run) / 2
    zs = z
    z -= LINK_RISERS * RISE
    fx0, fx1 = x1 + pad, x0 - pad                       # марш посередине, площадки по краям
    elements.append(('pad', (fx1, y - WIDTH / 2, x0, y + WIDTH / 2), zs, zs, 0, 'x', i))
    elements.append(('flight', (fx0, y - WIDTH / 2, fx1, y + WIDTH / 2), zs, z, LINK_RISERS, 'x', i))
    elements.append(('pad', (x1, y - WIDTH / 2, fx0, y + WIDTH / 2), z, z, 0, 'x', i))
    flights += 1
    risers_total += LINK_RISERS
    dist += pad
    profile.append((dist, zs))
    dist += run
    profile.append((dist, z))
    dist += pad
    profile.append((dist, z))
    if i < len(TRAV):
        xt, ya, yb, runs = TRAV[i]
        sgn = 1.0 if yb > ya else -1.0
        L = abs(yb - ya)
        corner = WIDTH / 2
        elements.append(('landing', (xt - WIDTH / 2, ya - WIDTH / 2, xt + WIDTH / 2, ya + WIDTH / 2), z, z, 0, '', i))
        total_run = sum(flight_run(n) for n in runs)
        gap = (L - corner * 2 - total_run) / (len(runs) + 1)
        yy = ya + sgn * corner
        dist += corner
        profile.append((dist, z))
        for n in runs:
            yy += sgn * gap
            dist += gap
            profile.append((dist, z))
            r = flight_run(n)
            zs = z
            z -= n * RISE
            y_lo, y_hi = sorted((yy, yy + sgn * r))
            elements.append(('flight', (xt - WIDTH / 2, y_lo, xt + WIDTH / 2, y_hi), zs, z, n, 'y', i))
            flights += 1
            risers_total += n
            yy += sgn * r
            dist += r
            profile.append((dist, z))
        dist += gap + corner
        profile.append((dist, z))
        elements.append(('landing', (xt - WIDTH / 2, yb - WIDTH / 2, xt + WIDTH / 2, yb + WIDTH / 2), z, z, 0, '', i))
        elements.append(('walk', (xt - WIDTH / 2, min(ya, yb), xt + WIDTH / 2, max(ya, yb)), None, None, 0, '', i))
CASCADE_LEN = dist
assert abs(z - QUAY_Z) < 0.2, f'низ каскада {z:.2f} вместо +{QUAY_Z}'

# выступы и киоск — от галерей: киоск на северной площадке первой, ротонда к югу от южной площадки второй (западнее
# террасы ресторана), смотровой балкон к северу от северной площадки третьей
G = [t[0] for t in TRAV]
KIOSK = (G[0] + WIDTH / 2 - 0.2 - 2.4, N_END + WIDTH / 2 - 0.1 - 1.6, G[0] + WIDTH / 2 - 0.2, N_END + WIDTH / 2 - 0.1)
ROT_DECK = (G[1] - WIDTH / 2, S_END - WIDTH / 2 - 6.4, G[1] - WIDTH / 2 + 6.4, S_END - WIDTH / 2)
ROT_C = ((ROT_DECK[0] + ROT_DECK[2]) / 2, (ROT_DECK[1] + ROT_DECK[3]) / 2)
BALCONY = (G[2] - 3.4, N_END + WIDTH / 2, G[2] + 3.4, N_END + WIDTH / 2 + 5.2)
EXT_GAPS = [{'gallery': 1, 'end': 'end', 'x': [round(ROT_C[0] - 1.5, 2), round(ROT_C[0] + 1.5, 2)]},
            {'gallery': 2, 'end': 'end', 'x': [round(G[2] - 1.5, 2), round(G[2] + 1.5, 2)]}]
z_g1_end = [e for e in elements if e[0] == 'landing' and e[6] == 0][1][2]

CASCADE_POINTS = [  # (название, x, y, что)
    ('Верх: парадная терраса', TOP_X, 0.0, 'балюстрада, фонтан, вид на озеро и плотину'),
    ('Площадка с киоском', G[0], N_END, 'киоск: вода, мороженое; скамьи'),
    ('Беседка-ротонда', ROT_C[0], ROT_C[1], 'белые колонны на выступе к югу от площадки'),
    ('Смотровой балкон', G[2], N_END + WIDTH / 2 + 2.6, 'выступ над склоном, перила, подзорная труба'),
    ('Площадка со скамьями', G[3], N_END, 'скамьи, фонарь, урны'),
    ('Низ: набережная', BOTTOM_X, 0.0, 'к «Стрелке» и пляжу'),
]

# ----------------------------------------------------------------------------- тропы: общая сеть (v03)
# Серпантин (17): от ларька у бровки три колена — на юг, на север, на юг — до пляжа; повороты плавные. Тропа от
# коттеджей (3): с улицы коттеджей по плато к бровке у мыса, по склону на север — к развилке у родника на конце
# первого колена; дальше — по серпантину. Точки — (x, y, z), z — рельеф блокаута (до врезки троп).
N1 = [(-94.0, -108.0, 32.0), (-101.0, -113.0, 29.4), (-108.8, -129.2, 27.0), (-113.3, -142.5, 25.2), (-114.7, -158.4, 23.1),
      (-110.8, -184.0, 19.7)]
N2 = [(-129.7, -153.5, 15.2), (-133.9, -140.1, 13.4), (-135.7, -124.3, 11.5)]
N3 = [(-141.1, -139.3, 9.4), (-143.3, -151.1, 7.8), (-141.8, -194.9, 2.1), (-149.0, -199.0, 2.0)]
TRAIL3 = N1 + N2 + N3
TRAIL = [p[:2] for p in TRAIL3]
JUNCTION_I = len(N1) - 1                       # развилка у родника — конец первого колена
JUNCTION = TRAIL[JUNCTION_I]
COTTAGE3 = [(-2.0, -216.0, 33.6), (-40.0, -232.0, 33.0), (-70.0, -244.0, 32.1), (-76.7, -242.2, 31.2), (-83.4, -234.7, 29.5),
            (-94.6, -215.9, 25.8), (-101.0, -199.1, 22.7), TRAIL3[JUNCTION_I]]
COTTAGE = [p[:2] for p in COTTAGE3]
COT_BROW_I = 3                                 # от этой точки — по склону (до неё — по плато)
seg = [math.dist(a, b) for a, b in zip(TRAIL, TRAIL[1:])]
TRAIL_LEN = sum(seg)
trail_profile = [(0.0, TRAIL3[0][2])]
acc = 0.0
for s_, p_ in zip(seg, TRAIL3[1:]):
    acc += s_
    trail_profile.append((acc, p_[2]))
cot_seg = [math.dist(a, b) for a, b in zip(COTTAGE, COTTAGE[1:])]
COT_SLOPE_LEN = sum(cot_seg[COT_BROW_I:])
cot_profile = [(0.0, COTTAGE3[COT_BROW_I][2])]
acc = 0.0
for s_, p_ in zip(cot_seg[COT_BROW_I:], COTTAGE3[COT_BROW_I + 1:]):
    acc += s_
    cot_profile.append((acc, p_[2]))
STAGE_PATH = [(-101.0, -160.0), (-103.0, -158.2), (-106.7, -151.1), (-111.0, -137.8)]    # к первому колену
GAZEBOS = [(-120.0, -150.0), (-137.5, -119.0)]   # над склоном у первого колена; над пляжем на втором повороте
SPRING = (-105.5, -183.0)                         # развилка: родник в каменной кладке и лавка (как на картинке владельца)
BENCH = (-107.0, -178.5)
TRAIL_POINTS = [
    ('Начало: ларёк у бровки', -95.0, -103.0, 'ларёк, лавка; к южной стороне спа и детской площадке'),
    ('Выход из-под сцены амфитеатра', -96.0, -160.0, 'короткая тропка к первому колену'),
    ('Развилка у родника', JUNCTION[0], JUNCTION[1], 'родник в каменной кладке, лавка; сюда сходится тропа от коттеджей'),
    ('Беседка над склоном', GAZEBOS[0][0], GAZEBOS[0][1], 'деревянная, у первого колена, вид на озеро'),
    ('Беседка над пляжем', GAZEBOS[1][0], GAZEBOS[1][1], 'деревянная, на повороте второго колена'),
    ('Низ: пляж', TRAIL[-1][0], TRAIL[-1][1], 'к пляжу и спасательной станции'),
    ('Тропа от коттеджей у бровки', COTTAGE[COT_BROW_I][0], COTTAGE[COT_BROW_I][1], 'с улицы коттеджей по плато, дальше по склону'),
]

# ----------------------------------------------------------------------------- лист
W, H = 1960, 1290
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
d.text((30, 18), f'Санаторий · спуски к воде v03 — лестница-каскад ({flights} маршей, {risers_total} ступеней) и общая сеть '
       f'троп (серпантин {TRAIL_LEN:.0f} м, от коттеджей {COT_SLOPE_LEN:.0f} м по склону)', font=font(21, True), fill=INK)
d.text((30, 50), 'вниз — в сторону — ещё в сторону (решение владельца) · каскад: марш 7,8 м, марши «вниз» с площадками, '
       'склон 74 м · v03: тропы общие, по рельефу, ≈ 13 % · координаты схемы участка, метры игры', font=font(14), fill=MUTED)

# --- план каскада
CX0, CX1, CY0, CY1 = -168.0, -78.0, -36.0, 48.0
CS = 6.6
A = kit.Plan(d, 30, 100, CX0, CY1, CS)
A.rect(CX0, CY0, CX1, CY1, fill=(176, 190, 150), outline=None)                 # склон
A.rect(CX0, CY0, BOTTOM_X - 1.0, CY1, fill=(214, 206, 188), outline=None)      # набережная
A.text(CX0 + 4, CY1 - 3, 'набережная +2', 11, MUTED, False, 'lm')
A.rect(TOP_X, -16, CX1, 16, fill=(232, 228, 214), outline=MUTED)              # край парадной террасы
A.text(TOP_X + 4, 13, 'терраса +32', 10, MUTED)
A.rect(-112.0, CY0, -96.0, -30.0, fill=(222, 206, 176), outline=MUTED)         # терраса ресторана (над склоном)
A.text(-104.0, -33.0, 'терраса ресторана', 9, MUTED)
for kind, rect, zt, zb, n, axis, idx in elements:
    if kind == 'walk':
        A.rect(*rect, fill=STONE, outline=None)
for kind, rect, zt, zb, n, axis, idx in elements:
    if kind in ('landing', 'pad'):
        A.rect(*rect, fill=(236, 232, 222), outline=MUTED)
    if kind == 'flight':
        A.rect(*rect, fill=STEP_C, outline=INK)
        x0, y0, x1, y1 = rect
        if axis == 'x':
            k = 0
            while x0 + k * RUN <= x1 + 1e-6:
                A.line([(x0 + k * RUN, y0), (x0 + k * RUN, y1)], fill=MUTED)
                k += 1
        else:
            k = 0
            while y0 + k * RUN <= y1 + 1e-6:
                A.line([(x0, y0 + k * RUN), (x1, y0 + k * RUN)], fill=MUTED)
                k += 1
for xt, ya, yb, runs in TRAV:                                                    # подпорная стенка — с нагорной стороны
    A.line([(xt + WIDTH / 2 + 0.3, min(ya, yb) - WIDTH / 2), (xt + WIDTH / 2 + 0.3, max(ya, yb) + WIDTH / 2)], fill=WALL_C, width=4)
    A.line([(xt - WIDTH / 2 - 0.2, min(ya, yb) - WIDTH / 2), (xt - WIDTH / 2 - 0.2, max(ya, yb) + WIDTH / 2)], fill=INK, width=1)
    for yy_ in range(int(min(ya, yb)), int(max(ya, yb)) + 1, 7):                 # фонари
        A.circle(xt + WIDTH / 2 - 0.5, yy_, 0.35, fill=(240, 190, 80), outline=None)
A.rect(*KIOSK, fill=(236, 236, 232), outline=INK)                                # киоск
A.text((KIOSK[0] + KIOSK[2]) / 2, KIOSK[1] - 1.6, 'киоск', 9, INK)
A.rect(*ROT_DECK, fill=(236, 232, 222), outline=INK)                             # выступ ротонды
A.circle(ROT_C[0], ROT_C[1], 3.0, fill=(245, 245, 245), outline=INK, width=2)    # ротонда
for k in range(8):
    a = math.radians(k * 45)
    A.circle(ROT_C[0] + 2.6 * math.cos(a), ROT_C[1] + 2.6 * math.sin(a), 0.3, fill=INK, outline=None)
A.rect(*BALCONY, fill=(236, 232, 222), outline=INK, width=2)                     # смотровой балкон
A.text(G[2], (BALCONY[1] + BALCONY[3]) / 2, 'балкон', 9, INK)
for x, y in ((G[0] + 3.2, 20), (G[1] + 3.2, 20), (G[1] + 3.2, -10), (G[2] + 3.2, 20), (G[3] + 3.2, 20), (G[3] + 3.2, 8)):   # скамьи
    A.rect(x - 0.3, y - 0.9, x + 0.3, y + 0.9, fill=(150, 110, 80), outline=None)
# уровни площадок
zmark = {}
for kind, rect, zt, zb, n, axis, idx in elements:
    if kind == 'landing':
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        zmark[(round(cx, 1), round(cy, 1))] = zt
for (cx, cy), zz in zmark.items():
    A.text(cx, cy, f'+{zz:.1f}'.replace('.', ','), 10, INK, True)
for k, (name, x, y, what) in enumerate(CASCADE_POINTS, 1):
    px, py = A.p(x, y)
    d.ellipse([px - 9, py - 9 - 24, px + 9, py + 9 - 24], fill=(255, 255, 255), outline=INK, width=2)
    d.text((px, py - 24), str(k), font=font(11, True), fill=INK, anchor='mm')
bx, by = A.p(CX0 + 2, CY0 + 2)
d.line([(bx, by), (bx + 10 * CS, by)], fill=INK, width=3)
d.text((bx + 5 * CS, by - 10), '10 м', font=font(12), fill=INK, anchor='mm')
d.text((30, 100 + int((CY1 - CY0) * CS) + 6), 'Лестница-каскад (16) — план', font=font(16, True), fill=INK)

# --- план троп
TX0, TX1, TY0, TY1 = -158.0, -66.0, -250.0, -100.0
TS = 4.0
B = kit.Plan(d, 650, 100, TX0, TY1, TS)
B.rect(TX0, TY0, TX1, TY1, fill=(176, 190, 150), outline=None)
B.poly([(TX1, TY0), (-80.0, TY0), (-96.0, -150.0), (-95.4, TY1), (TX1, TY1)], fill=(226, 230, 214), outline=None)   # плато
B.rect(TX0, TY0, -146.0, TY1, fill=(232, 216, 170), outline=None)            # пляж
B.text(TX0 + 2, TY1 - 3, 'пляж', 10, MUTED, False, 'lm')
B.text(-76.0, TY1 - 3, 'плато', 10, MUTED)
B.rect(-95, -172, -80, -144, fill=(236, 236, 232), outline=MUTED)             # сцена амфитеатра
B.text(-88, -150, 'сцена', 9, MUTED)
B.rect(-131.5, -102, -103.5, TY1, fill=(232, 228, 214), outline=MUTED)         # край подиума бассейна
B.text(-117.5, -101, 'подиум', 9, MUTED)
B.line(TRAIL, fill=(150, 106, 60), width=6)
B.line(COTTAGE[2:], fill=(150, 106, 60), width=5)              # по плато дальше — к улице коттеджей
B.line(STAGE_PATH, fill=(150, 106, 60), width=3)
for (gx, gy) in GAZEBOS:
    B.circle(gx, gy, 2.4, fill=(236, 236, 232), outline=INK)
B.circle(SPRING[0], SPRING[1], 1.2, fill=(120, 196, 220), outline=INK)
B.rect(BENCH[0] - 0.9, BENCH[1] - 0.3, BENCH[0] + 0.9, BENCH[1] + 0.3, fill=(150, 110, 80), outline=None)
for k, (name, x, y, what) in enumerate(TRAIL_POINTS, 1):
    px, py = B.p(x, y)
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 255, 255), outline=INK, width=2)
    d.text((px, py), str(k), font=font(11, True), fill=INK, anchor='mm')
for x, y, zz in TRAIL3[::2] + COTTAGE3[COT_BROW_I:-1:2]:
    B.text(x - 3.0, y + 2.6, f'+{zz:.0f}', 9, MUTED)
bx, by = B.p(TX0 + 2, TY0 + 3)
d.line([(bx, by), (bx + 20 * TS, by)], fill=INK, width=3)
d.text((bx + 10 * TS, by - 10), '20 м', font=font(12), fill=INK, anchor='mm')
d.text((650, 100 + int((TY1 - TY0) * TS) + 6), 'Тропы (17 и 3) — план: общая нижняя часть', font=font(16, True), fill=INK)

# --- профили
PY = 820
d.text((30, PY), 'Профили, развёрнуто по ходу (по вертикали × 2)', font=font(16, True), fill=INK)


def profile_draw(x0, y0, pts, length, scale_x, color, label):
    d.line([(x0, y0), (x0 + length * scale_x, y0)], fill=MUTED)
    d.line([(x0, y0), (x0, y0 - 32 * 2 * 4)], fill=MUTED)
    for zz in (0, 10, 20, 30):
        yy_ = y0 - zz * 2 * 4
        d.line([(x0 - 4, yy_), (x0, yy_)], fill=MUTED)
        d.text((x0 - 8, yy_), f'+{zz}', font=font(10), fill=MUTED, anchor='rm')
    d.line([(x0 + a * scale_x, y0 - b * 2 * 4) for a, b in pts], fill=color, width=3)
    d.text((x0 + 6, y0 + 14), label, font=font(12), fill=INK)


profile_draw(70, PY + 300, profile, CASCADE_LEN, 2.6, (196, 84, 60),
             f'каскад: {CASCADE_LEN:.0f} м по ходу, {flights} маршей, {risers_total} ступеней, площадки ровные')
profile_draw(700, PY + 300, trail_profile, TRAIL_LEN, 2.1, (150, 106, 60),
             f'серпантин: {TRAIL_LEN:.0f} м, средний уклон {30 / TRAIL_LEN * 100:.0f} %; от коттеджей по склону — {COT_SLOPE_LEN:.0f} м')
d.line([(700 + a * 2.1, PY + 300 - b * 2 * 4) for a, b in cot_profile], fill=(196, 150, 90), width=2)

# --- списки и замечания
sx = 1260
yy = 100
d.text((sx, yy), 'Каскад — точки', font=font(16, True), fill=INK)
yy += 26
for k, (name, x, y, what) in enumerate(CASCADE_POINTS, 1):
    d.text((sx, yy), f'{k}', font=font(13, True), fill=INK)
    d.text((sx + 24, yy), name, font=font(13, True), fill=INK)
    d.text((sx + 24, yy + 17), what, font=font(12), fill=(60, 62, 66))
    yy += 38
yy += 6
d.text((sx, yy), 'Тропы — точки', font=font(16, True), fill=INK)
yy += 26
for k, (name, x, y, what) in enumerate(TRAIL_POINTS, 1):
    d.text((sx, yy), f'{k}', font=font(13, True), fill=INK)
    d.text((sx + 24, yy), name, font=font(13, True), fill=INK)
    d.text((sx + 24, yy + 17), what, font=font(12), fill=(60, 62, 66))
    yy += 38
yy += 6
for s_ in ['Каскад: марш «вниз» — 15 ступеней поперёк склона с площадками сверху и снизу,',
           'галерея «в сторону» вдоль склона с короткими маршами по 10–11 ступеней. С нагорной',
           'стороны — подпорная стенка с подсветкой ступеней (укрытие), с низовой — перила.',
           'Между галереями — цветники террасами. Марш 7,8 м (в v01 — 5,2).',
           'Тропы: грунт, корни, камни; серпантин — три колена с плавными поворотами, уклон',
           '≈ 13 %; тропа от коттеджей сходится с ним у родника, ниже — общая. Под соснами',
           'и елями, видно на 20–40 м; где круче — ступени из брёвен.']:
    d.text((sx, yy), s_, font=font(12), fill=(60, 62, 66))
    yy += 17
img.save(OUT)

DATA.parent.mkdir(parents=True, exist_ok=True)
DATA.write_text(json.dumps({
    'version': 'v02', 'rise': RISE, 'run': RUN, 'width': WIDTH, 'top_x': TOP_X, 'bottom_x': round(BOTTOM_X, 2),
    'n_end': N_END, 's_end': S_END,
    'cascade': {'flights': flights, 'risers': risers_total, 'length': round(CASCADE_LEN, 1),
                'elements': [{'kind': k, 'rect': [round(v, 2) for v in r], 'z_top': zt, 'z_bottom': zb, 'risers': n,
                              'axis': ax, 'index': idx} for k, r, zt, zb, n, ax, idx in elements],
                'kiosk': [round(v, 2) for v in KIOSK], 'kiosk_z': z_g1_end,
                'rotunda_deck': [round(v, 2) for v in ROT_DECK], 'rotunda': [round(v, 2) for v in ROT_C],
                'balcony': [round(v, 2) for v in BALCONY], 'ext_gaps': EXT_GAPS,
                'points': [{'name': n, 'xy': [round(x, 2), round(y, 2)], 'what': w} for n, x, y, w in CASCADE_POINTS]},
    'trail': {'polyline': TRAIL, 'z': [p[2] for p in TRAIL3], 'length': round(TRAIL_LEN, 1), 'junction': JUNCTION_I,
              'profile': [[round(a, 1), round(b, 2)] for a, b in trail_profile],
              'stage_path': [list(p) for p in STAGE_PATH],
              'gazebos': [{'xy': list(p)} for p in GAZEBOS], 'spring': list(SPRING), 'bench': list(BENCH),
              'points': [{'name': n, 'xy': [x, y], 'what': w} for n, x, y, w in TRAIL_POINTS]},
    'cottage': {'polyline': COTTAGE, 'z': [p[2] for p in COTTAGE3], 'brow_index': COT_BROW_I, 'slope_length': round(COT_SLOPE_LEN, 1)},
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
print(f'спуски v03: каскад {flights} маршей, {risers_total} ступеней, {CASCADE_LEN:.0f} м по ходу, низ x {BOTTOM_X:.1f}; '
      f'серпантин {TRAIL_LEN:.0f} м, от коттеджей {COT_SLOPE_LEN:.0f} м; галереи x {[round(g, 1) for g in G]}; ротонда {ROT_DECK}')
