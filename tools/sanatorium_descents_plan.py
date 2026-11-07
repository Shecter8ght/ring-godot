# -*- coding: utf-8 -*-
"""Санаторий — спуски к воде v01: лестница-каскад (16) и тропа-серпантин (17): план, марши, профили, точки.

Решения владельца (docs/design/sanatorium_map.md, §1): вода ниже санатория, к ней спускаются не по прямой, а по
лестницам — вниз, потом в сторону, потом ещё в сторону; параллельно — грунтовая тропа другим маршрутом; по пути
лавочки, небольшие беседки, киоски. Лифта и ливнёвки нет. Деревья — только ели и сосны. Вид — картинки 16 и 17
(docs/design/sanatorium_visual.md), планировку с картинок не брать. Остальное — предложение агента
(docs/design/sanatorium_descents.md).

Каскад — постройка на подпорных стенках: уровни площадок задаёт лестница, склон под ней террасирован. Ступени 1:1 —
подъём 0,15, проступь 0,30 (уличные); ширина марша 4 × 1,3 = 5,2 м (правило E). Координаты — схемы участка.

    python -X utf8 tools/sanatorium_descents_plan.py
        → docs/plans/sanatorium_descents_v01.png, docs/design/data/sanatorium_descents_v01.json
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_descents_v01.png'
DATA = ROOT / 'docs/design/data/sanatorium_descents_v01.json'

RISE, RUN, WIDTH = 0.15, 0.30, 5.2
TERRACE_Z, QUAY_Z = 32.0, 2.0
STONE = (226, 222, 212)
STEP_C = (206, 200, 186)
WALL_C = (120, 116, 108)

# ----------------------------------------------------------------------------- каскад: путь и марши
# Спуски «вниз» — марши по 15 подъёмов поперёк склона (на запад); «в сторону» — галереи вдоль склона (по y)
# с короткими маршами по 10–11 подъёмов и площадками. Итого 17 маршей, 200 подъёмов, 30 м.
LINK_RISERS = 15
TRAV = [  # (x оси галереи, y начала, y конца, марши подъёмов)
    (-92.8, 0.0, 22.0, (10, 11)),
    (-102.2, 22.0, -22.0, (10, 11, 10, 11)),
    (-111.6, -22.0, 22.0, (10, 11, 10, 11)),
    (-121.0, 22.0, 0.0, (10, 10)),
]
LINKS = [(-86.0, -90.2, 0.0), (-95.4, -99.6, 22.0), (-104.8, -109.0, -22.0), (-114.2, -118.4, 22.0), (-123.6, -127.8, 0.0)]

elements = []      # (вид, многоугольник/данные, z верх, z низ, подъёмов)
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
    elements.append(('flight', (min(x0, x1), y - WIDTH / 2, max(x0, x1), y + WIDTH / 2), zs, z, LINK_RISERS, 'x'))
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
        elements.append(('landing', (xt - WIDTH / 2, ya - WIDTH / 2, xt + WIDTH / 2, ya + WIDTH / 2), z, z, 0, ''))
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
            elements.append(('flight', (xt - WIDTH / 2, y_lo, xt + WIDTH / 2, y_hi), zs, z, n, 'y'))
            flights += 1
            risers_total += n
            yy += sgn * r
            dist += r
            profile.append((dist, z))
        dist += gap + corner
        profile.append((dist, z))
        elements.append(('landing', (xt - WIDTH / 2, yb - WIDTH / 2, xt + WIDTH / 2, yb + WIDTH / 2), z, z, 0, ''))
        elements.append(('walk', (xt - WIDTH / 2, min(ya, yb), xt + WIDTH / 2, max(ya, yb)), None, None, 0, ''))
CASCADE_LEN = dist
assert abs(z - QUAY_Z) < 0.2, f'низ каскада {z:.2f} вместо +{QUAY_Z}'

CASCADE_POINTS = [  # (название, x, y, что)
    ('Верх: парадная терраса', -86.0, 0.0, 'балюстрада, фонтан, вид на озеро и плотину'),
    ('Площадка с киоском', -92.8, 22.0, 'киоск: вода, мороженое; скамьи'),
    ('Беседка-ротонда', -102.2, -29.5, 'белые колонны на выступе, к ней ответвление с угловой площадки'),
    ('Смотровой балкон', -111.6, 27.0, 'выступ над склоном, перила, подзорная труба'),
    ('Площадка со скамьями', -121.0, 22.0, 'скамьи, фонарь, урны'),
    ('Низ: набережная', -127.8, 0.0, 'к «Стрелке» и пляжу'),
]

# ----------------------------------------------------------------------------- тропа-серпантин
TRAIL = [(-97, -106), (-101, -146), (-106, -148), (-108, -112), (-113, -110), (-117, -150), (-121, -152), (-123, -118),
         (-127, -120), (-131, -160), (-135, -168)]
TRAIL_Z0, TRAIL_Z1 = 31.0, QUAY_Z
seg = [math.dist(a, b) for a, b in zip(TRAIL, TRAIL[1:])]
TRAIL_LEN = sum(seg)
trail_profile = [(0.0, TRAIL_Z0)]
acc = 0.0
for s_ in seg:
    acc += s_
    trail_profile.append((acc, TRAIL_Z0 + (TRAIL_Z1 - TRAIL_Z0) * acc / TRAIL_LEN))
TRAIL_POINTS = [
    ('Начало: киоск у бровки', -95.0, -103.0, 'ларёк, лавка; к южной стороне спа и детской площадке'),
    ('Выход из-под сцены амфитеатра', -96.0, -160.0, 'короткая тропка к первому колену'),
    ('Родник в каменной кладке', -104.0, -150.5, 'трубка, чаша; под кладкой — укрытие'),
    ('Беседка восьмигранная', -116.5, -107.5, 'деревянная, на выступе с видом на озеро'),
    ('Лавка у поворота', -122.0, -155.0, 'старая деревянная лавка'),
    ('Беседка у воды', -130.0, -116.5, 'деревянная, на последнем колене'),
    ('Низ: пляж', -135.0, -168.0, 'к пляжу и спасательной станции'),
]

# ----------------------------------------------------------------------------- лист
W, H = 1960, 1250
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
d.text((30, 18), f'Санаторий · спуски к воде v01 — лестница-каскад ({flights} маршей, {risers_total} ступеней) и тропа-серпантин '
       f'({TRAIL_LEN:.0f} м)', font=font(21, True), fill=INK)
d.text((30, 50), 'вниз — в сторону — ещё в сторону (решение владельца) · ступень 15 × 30 см, марш 5,2 м · каскад на подпорных '
       'стенках · координаты схемы участка, метры игры', font=font(14), fill=MUTED)

# --- план каскада
A = kit.Plan(d, 30, 100, -136.0, 34.0, 9.0)
A.rect(-136, -38, -80, 34, fill=(176, 190, 150), outline=None)                 # склон
A.rect(-136, -38, -126, 34, fill=(214, 206, 188), outline=None)                # набережная
A.text(-131, 31, 'набережная +2', 11, MUTED)
A.rect(-86, -16, -80, 16, fill=(232, 228, 214), outline=MUTED)                 # край парадной террасы
A.text(-83, 13, 'терраса +32', 10, MUTED)
for kind, rect, zt, zb, n, axis in elements:
    if kind == 'walk':
        A.rect(*rect, fill=STONE, outline=None)
for kind, rect, zt, zb, n, axis in elements:
    if kind == 'landing':
        A.rect(*rect, fill=(236, 232, 222), outline=MUTED)
    if kind == 'flight':
        A.rect(*rect, fill=STEP_C, outline=INK)
        x0, y0, x1, y1 = rect
        if axis == 'x':
            k = 0
            while x0 + k * RUN <= x1:
                A.line([(x0 + k * RUN, y0), (x0 + k * RUN, y1)], fill=MUTED)
                k += 1
        else:
            k = 0
            while y0 + k * RUN <= y1:
                A.line([(x0, y0 + k * RUN), (x1, y0 + k * RUN)], fill=MUTED)
                k += 1
for xt, ya, yb, runs in TRAV:                                                    # подпорная стенка — с нагорной стороны
    A.line([(xt + WIDTH / 2 + 0.3, min(ya, yb) - 2.6), (xt + WIDTH / 2 + 0.3, max(ya, yb) + 2.6)], fill=WALL_C, width=4)
    A.line([(xt - WIDTH / 2 - 0.2, min(ya, yb) - 2.6), (xt - WIDTH / 2 - 0.2, max(ya, yb) + 2.6)], fill=INK, width=1)
    for yy_ in range(int(min(ya, yb)), int(max(ya, yb)) + 1, 7):                 # фонари
        A.circle(xt + WIDTH / 2 - 0.5, yy_, 0.35, fill=(240, 190, 80), outline=None)
A.rect(-95, 25.6, -91, 29.6, fill=(236, 236, 232), outline=INK)                # киоск
A.text(-93, 27.6, 'киоск', 9, INK)
A.rect(-104, -26.6, -100.4, -24.6, fill=(236, 232, 222), outline=MUTED)        # ответвление к ротонде
A.circle(-102.2, -29.5, 3.0, fill=(245, 245, 245), outline=INK, width=2)       # ротонда
for k in range(8):
    a = math.radians(k * 45)
    A.circle(-102.2 + 2.6 * math.cos(a), -29.5 + 2.6 * math.sin(a), 0.3, fill=INK, outline=None)
A.rect(-114, 24.6, -109.2, 29.4, fill=(236, 232, 222), outline=INK, width=2)   # смотровой балкон
A.text(-111.6, 27, 'балкон', 9, INK)
for x, y in ((-90.5, 20), (-104.5, 20), (-109.3, -20), (-123.3, 20), (-104.5, -1), (-109.3, 1)):   # скамьи
    A.rect(x - 0.3, y - 0.9, x + 0.3, y + 0.9, fill=(150, 110, 80), outline=None)
# уровни площадок
zmark = {}
for kind, rect, zt, zb, n, axis in elements:
    if kind == 'landing':
        cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        zmark[(round(cx, 1), round(cy, 1))] = zt
for (cx, cy), zz in zmark.items():
    A.text(cx, cy, f'+{zz:.1f}'.replace('.', ','), 10, INK, True)
for k, (name, x, y, what) in enumerate(CASCADE_POINTS, 1):
    px, py = A.p(x, y)
    d.ellipse([px - 9, py - 9 - 24, px + 9, py + 9 - 24], fill=(255, 255, 255), outline=INK, width=2)
    d.text((px, py - 24), str(k), font=font(11, True), fill=INK, anchor='mm')
bx, by = A.p(-134, -36)
d.line([(bx, by), (bx + 10 * 9, by)], fill=INK, width=3)
d.text((bx + 45, by - 10), '10 м', font=font(12), fill=INK, anchor='mm')
d.text((30, 100 + 72 * 9 + 6), 'Лестница-каскад (16) — план', font=font(16, True), fill=INK)

# --- план тропы
B = kit.Plan(d, 590, 100, -140.0, -98.0, 6.6)
B.rect(-140, -172, -86, -98, fill=(176, 190, 150), outline=None)
B.poly([(-86, -172), (-95.4, -172), (-95.4, -98), (-86, -98)], fill=(226, 230, 214), outline=None)   # плато
B.rect(-140, -172, -133, -98, fill=(232, 216, 170), outline=None)            # пляж
B.text(-136.5, -100, 'пляж', 10, MUTED)
B.text(-90.5, -100, 'плато', 10, MUTED)
B.rect(-95, -176 + 4, -80, -144, fill=(236, 236, 232), outline=MUTED)         # сцена амфитеатра
B.text(-88, -150, 'сцена', 9, MUTED)
B.rect(-124, -102, -96, -98, fill=(232, 228, 214), outline=MUTED)             # край подиума бассейна
B.text(-110, -100, 'подиум бассейна', 9, MUTED)
B.line(TRAIL, fill=(150, 106, 60), width=6)
B.line([(-96, -160), (-101, -150), (-101, -146)], fill=(150, 106, 60), width=3)
for i, (x, y) in enumerate(TRAIL):
    if 0 < i < len(TRAIL) - 1:
        B.circle(x, y, 1.0, fill=(150, 106, 60), outline=None)
for k, (name, x, y, what) in enumerate(TRAIL_POINTS, 1):
    px, py = B.p(x, y)
    d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=(255, 255, 255), outline=INK, width=2)
    d.text((px, py), str(k), font=font(11, True), fill=INK, anchor='mm')
for (x, y), zz in zip(TRAIL, [p_[1] for p_ in trail_profile]):
    B.text(x - 2.6, y + 2.2, f'+{zz:.0f}', 9, MUTED)
d.text((590, 100 + 74 * 6.6 + 6), 'Тропа-серпантин (17) — план', font=font(16, True), fill=INK)

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


profile_draw(70, PY + 300, profile, CASCADE_LEN, 4.2, (196, 84, 60),
             f'каскад: {CASCADE_LEN:.0f} м по ходу, {flights} маршей, {risers_total} ступеней, площадки ровные')
profile_draw(700, PY + 300, trail_profile, TRAIL_LEN, 3.0, (150, 106, 60),
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
for s_ in ['Каскад: марш «вниз» — 15 ступеней поперёк склона, галерея «в сторону» вдоль',
           'склона с короткими маршами по 10–11 ступеней и площадками. С нагорной стороны —',
           'подпорная стенка с подсветкой ступеней (укрытие), с низовой — перила.',
           'Тропа: грунт, корни, камни; шесть колен вдоль склона, ступени из брёвен,',
           'верёвочные перила на поворотах; под соснами и елями, видно на 20–40 м.']:
    d.text((sx, yy), s_, font=font(12), fill=(60, 62, 66))
    yy += 17
img.save(OUT)

DATA.parent.mkdir(parents=True, exist_ok=True)
DATA.write_text(json.dumps({
    'version': 'v01', 'rise': RISE, 'run': RUN, 'width': WIDTH,
    'cascade': {'flights': flights, 'risers': risers_total, 'length': round(CASCADE_LEN, 1),
                'elements': [{'kind': k, 'rect': [round(v, 2) for v in r], 'z_top': zt, 'z_bottom': zb, 'risers': n,
                              'axis': ax} for k, r, zt, zb, n, ax in elements],
                'points': [{'name': n, 'xy': [x, y], 'what': w} for n, x, y, w in CASCADE_POINTS]},
    'trail': {'polyline': TRAIL, 'length': round(TRAIL_LEN, 1),
              'profile': [[round(a, 1), round(b, 2)] for a, b in trail_profile],
              'points': [{'name': n, 'xy': [x, y], 'what': w} for n, x, y, w in TRAIL_POINTS]},
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
print(f'спуски: каскад {flights} маршей, {risers_total} ступеней, {CASCADE_LEN:.0f} м по ходу; тропа {TRAIL_LEN:.0f} м')
