# -*- coding: utf-8 -*-
"""Санаторий — спуски к воде v02: лестница-каскад (16) и тропа-серпантин (17): план, марши, профили, точки.

Решения владельца (docs/design/sanatorium_map.md, §1): вода ниже санатория, к ней спускаются не по прямой, а по
лестницам — вниз, потом в сторону, потом ещё в сторону; параллельно — грунтовая тропа другим маршрутом; по пути
лавочки, небольшие беседки, киоски. Лифта и ливнёвки нет. Деревья — только ели и сосны. Вид — картинки 16 и 17
(docs/design/sanatorium_visual.md), планировку с картинок не брать. Остальное — предложение агента
(docs/design/sanatorium_descents.md).

v02 — владелец после прогулки по серому блокауту: каскад и тропа «слишком сжатые и тесные — удлинить, сделать
просторнее и масштабнее», береговая линия дальше. Склон стал длиннее (схема участка v11: урез на 45 м западнее,
бровка на месте) — каскад 74 м по горизонтали вместо 42: марш 7,8 м вместо 5,2, марш «вниз» с площадками по 2,25 м
сверху и снизу, галереи вдвое дальше друг от друга, на север до +34 м; тропа — колена через 10 м вместо 4–5 м.

Каскад — постройка на подпорных стенках: уровни площадок задаёт лестница, склон под ней террасирован. Ступени 1:1 —
подъём 0,15, проступь 0,30 (уличные); ширина марша 6 × 1,3 = 7,8 м (правило E). Координаты — схемы участка.

    python -X utf8 tools/sanatorium_descents_plan.py
        → docs/plans/sanatorium_descents_v02.png, docs/design/data/sanatorium_descents_v02.json
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_descents_v02.png'
DATA = ROOT / 'docs/design/data/sanatorium_descents_v02.json'

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

# ----------------------------------------------------------------------------- тропа-серпантин
# пять колен вдоль склона по 40–47 м и короткие повороты; колена — через 10 м по склону (в v01 — через 4–5 м)
TRAIL = [(-97, -108), (-103, -152), (-108, -154), (-112, -114), (-117, -112), (-123, -154), (-128, -156), (-132, -116),
         (-137, -114), (-145, -160), (-158, -168)]
TRAIL_Z0, TRAIL_Z1 = 31.0, QUAY_Z
seg = [math.dist(a, b) for a, b in zip(TRAIL, TRAIL[1:])]
TRAIL_LEN = sum(seg)
trail_profile = [(0.0, TRAIL_Z0)]
acc = 0.0
for s_ in seg:
    acc += s_
    trail_profile.append((acc, TRAIL_Z0 + (TRAIL_Z1 - TRAIL_Z0) * acc / TRAIL_LEN))


def trail_at_y(i, y):
    """Точка колена i (отрезок TRAIL[i] → TRAIL[i + 1]) на широте y и высота тропы в ней."""
    (ax, ay), (bx, by) = TRAIL[i], TRAIL[i + 1]
    t = (y - ay) / (by - ay)
    s = trail_profile[i][0] + seg[i] * t
    return ax + (bx - ax) * t, y, TRAIL_Z0 + (TRAIL_Z1 - TRAIL_Z0) * s / TRAIL_LEN


UNDER_Z = 28.0                                     # уровень под сценой амфитеатра
_join = trail_at_y(0, -148.5)
STAGE_PATH = [(-101.0, -160.0, UNDER_Z), (-99.5, -153.5, round(UNDER_Z - 0.9, 2)), tuple(round(v, 2) for v in _join)]
GAZEBOS = [((-120.5, -109.5), 4), ((-140.5, -111.5), 8)]      # беседки у северных поворотов (номер точки тропы)
SPRING = (-111.0, -157.5)
BENCH = (-127.0, -159.5)
TRAIL_POINTS = [
    ('Начало: киоск у бровки', -95.0, -103.0, 'ларёк, лавка; к южной стороне спа и детской площадке'),
    ('Выход из-под сцены амфитеатра', -96.0, -160.0, 'короткая тропка к первому колену'),
    ('Родник в каменной кладке', SPRING[0], SPRING[1], 'трубка, чаша; под кладкой — укрытие'),
    ('Беседка восьмигранная', GAZEBOS[0][0][0], GAZEBOS[0][0][1], 'деревянная, на выступе с видом на озеро'),
    ('Лавка у поворота', BENCH[0], BENCH[1], 'старая деревянная лавка'),
    ('Беседка над пляжем', GAZEBOS[1][0][0], GAZEBOS[1][0][1], 'деревянная, на последнем северном повороте'),
    ('Низ: пляж', TRAIL[-1][0], TRAIL[-1][1], 'к пляжу и спасательной станции'),
]

# ----------------------------------------------------------------------------- лист
W, H = 1960, 1290
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
d.text((30, 18), f'Санаторий · спуски к воде v02 — лестница-каскад ({flights} маршей, {risers_total} ступеней) и тропа-серпантин '
       f'({TRAIL_LEN:.0f} м)', font=font(21, True), fill=INK)
d.text((30, 50), 'вниз — в сторону — ещё в сторону (решение владельца) · v02 просторнее: марш 7,8 м, марши «вниз» с площадками, '
       'склон 74 м · ступень 15 × 30 см · координаты схемы участка, метры игры', font=font(14), fill=MUTED)

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

# --- план тропы
TX0, TX1, TY0, TY1 = -166.0, -86.0, -174.0, -100.0
TS = 6.6
B = kit.Plan(d, 650, 100, TX0, TY1, TS)
B.rect(TX0, TY0, TX1, TY1, fill=(176, 190, 150), outline=None)
B.poly([(TX1, TY0), (-95.4, TY0), (-95.4, TY1), (TX1, TY1)], fill=(226, 230, 214), outline=None)   # плато
B.rect(TX0, TY0, -154.0, TY1, fill=(232, 216, 170), outline=None)            # пляж
B.text(TX0 + 4, TY1 - 2, 'пляж', 10, MUTED, False, 'lm')
B.text(-90.5, TY1 - 2, 'плато', 10, MUTED)
B.rect(-95, -172, -80, -144, fill=(236, 236, 232), outline=MUTED)             # сцена амфитеатра
B.text(-88, -150, 'сцена', 9, MUTED)
B.rect(-131.5, -102, -103.5, TY1, fill=(232, 228, 214), outline=MUTED)         # край подиума бассейна
B.text(-117.5, -101, 'подиум бассейна (над скалой)', 9, MUTED)
B.line(TRAIL, fill=(150, 106, 60), width=6)
B.line([p[:2] for p in STAGE_PATH], fill=(150, 106, 60), width=3)
for i, (x, y) in enumerate(TRAIL):
    if 0 < i < len(TRAIL) - 1:
        B.circle(x, y, 1.0, fill=(150, 106, 60), outline=None)
for (gx, gy), _ in GAZEBOS:
    B.circle(gx, gy, 2.4, fill=(236, 236, 232), outline=INK)
B.circle(SPRING[0], SPRING[1], 1.2, fill=(120, 196, 220), outline=INK)
for k, (name, x, y, what) in enumerate(TRAIL_POINTS, 1):
    px, py = B.p(x, y)
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 255, 255), outline=INK, width=2)
    d.text((px, py), str(k), font=font(11, True), fill=INK, anchor='mm')
for (x, y), zz in zip(TRAIL, [p_[1] for p_ in trail_profile]):
    B.text(x - 2.6, y + 2.2, f'+{zz:.0f}', 9, MUTED)
d.text((650, 100 + int((TY1 - TY0) * TS) + 6), 'Тропа-серпантин (17) — план', font=font(16, True), fill=INK)

# --- профили
PY = 800
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
             f'тропа: {TRAIL_LEN:.0f} м, средний уклон {30 / TRAIL_LEN * 100:.0f} %, на крутых местах — ступени из брёвен')

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
d.text((sx, yy), 'Тропа — точки', font=font(16, True), fill=INK)
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
           'Тропа: грунт, корни, камни; пять колен вдоль склона через 10 м, ступени из брёвен,',
           'верёвочные перила на поворотах; под соснами и елями, видно на 20–40 м.']:
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
    'trail': {'polyline': TRAIL, 'length': round(TRAIL_LEN, 1),
              'profile': [[round(a, 1), round(b, 2)] for a, b in trail_profile],
              'stage_path': [list(p) for p in STAGE_PATH],
              'gazebos': [{'xy': list(p), 'knee': k} for p, k in GAZEBOS], 'spring': list(SPRING), 'bench': list(BENCH),
              'points': [{'name': n, 'xy': [x, y], 'what': w} for n, x, y, w in TRAIL_POINTS]},
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
print(f'спуски v02: каскад {flights} маршей, {risers_total} ступеней, {CASCADE_LEN:.0f} м по ходу, низ x {BOTTOM_X:.1f}; '
      f'тропа {TRAIL_LEN:.0f} м; галереи x {[round(g, 1) for g in G]}; ротонда {ROT_DECK}')
