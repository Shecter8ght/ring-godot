# -*- coding: utf-8 -*-
"""Санаторий — планы малых построек v01: коттедж, «Стрелка» (павильон и маяк), амфитеатр, хоздвор, детская площадка.

Просьба владельца 2026-11-07: «планировку коттеджа, маяка, строения на стрелке, амфитеатра, хозяйственных корпусов
в правом верхнем углу и состав детской площадки». Принятое раньше: «Стрелка» — стрелка, а не причал (павильон
со смотровой площадкой, киоски, ротонда, маяк, без кафе); амфитеатр ≈ 600 мест со сценой у бровки, задник — озеро;
у каждого коттеджа своё парковочное место; детская площадка — горки, качели, прыгательные сетки, городки «самолёт»,
«грузовик», «корабль». Визуальные референсы — docs/design/sanatorium_visual.md (планировку с них не брать).
Ответы владельца 2026-11-07: коттедж — одна планировка на все дома; маяк — только с ключом; павильон на «Стрелке» —
без экспонатов, кофейня; на бак водонапорной башни не подняться. Остальное — предложение агента
(docs/design/sanatorium_small_buildings.md).

Координаты — схемы участка (tools/sanatorium_map_plan.py), метры игры: помещения и проходы × 1,3 (правило E),
мебель, оборудование площадки, ступени — 1:1.

    python -X utf8 tools/sanatorium_small_plans.py
        → docs/plans/sanatorium_{cottage,amphitheatre,hozdvor,playground}_v01.png, sanatorium_strelka_v02.png,
          docs/design/data/sanatorium_small_v01.json
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import DOOR, DOOR2, INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
PLANS = ROOT / 'docs/plans'
DATA = ROOT / 'docs/design/data/sanatorium_small_v01.json'
REPORT = {}


def numbered(floors):
    num = {}
    for f, rooms in floors.items():
        k = 0
        for r in rooms:
            if r[6] != 'void':
                k += 1
                num.setdefault(f, {})[r[0]] = f'{k:02d}' if len(floors) == 1 else f'{f}.{k:02d}'
    return num


def check(name, floors, doors, vertical=(), locked=()):
    probs, by = [], {}
    for f in floors:
        p, b = kit.check_floor(floors[f], doors[f], locked, reach_check=False)
        probs += [f'{name} {f}: {x}' for x in p]
        by[f] = b
    un, unk = kit.reach_multi({f: (floors[f], doors[f]) for f in floors}, list(vertical), locked)
    probs += [f'{name}: не дойти {f} {r}' for f, r in un] + [f'{name}: без ключей не дойти {f} {r}' for f, r in unk]
    REPORT[name] = {str(f): {
        'rooms': [{'id': r[0], 'name': r[1], 'rect': [r[2], r[3], r[4], r[5]], 'kind': r[6], 'flags': r[7].split(),
                   'area': round((r[4] - r[2]) * (r[5] - r[3]), 1)} for r in floors[f]],
        'doors': [{'a': x[0], 'b': x[1], 'width': x[3], 'locked': (x[0], x[1]) in locked,
                   'wall': list(kit.door_geom(by[f], x))} for x in doors[f]]} for f in floors}
    return probs, by


def sheet(w, h, title, sub):
    img = Image.new('RGB', (w, h), kit.PAPER)
    d = ImageDraw.Draw(img)
    d.text((30, 18), title, font=font(21, True), fill=INK)
    d.text((30, 50), sub, font=font(14), fill=MUTED)
    return img, d


def notes(d, x, y, lines, width_px=None):
    for s in lines:
        bold = s.startswith('**')
        d.text((x, y), s.strip('*'), font=font(14 if bold else 13, bold), fill=INK if bold else (60, 62, 66))
        y += 22 if bold else 18
    return y


PROBLEMS = []

# ============================================================================ 1. КОТТЕДЖ
# Северный ряд, дом в (14, −199): улица на юге; южный ряд — зеркально (улица на севере). Пятно 14 × 12 м, 2 этажа.
CT = {
    1: [
        ('HAL', 'Прихожая', 7, -205, 11, -199, 'pub', ''),
        ('KIT', 'Кухня', 11, -205, 16, -199, 'serv', 'loot'),
        ('UTL', 'Котельная, кладовая', 16, -205, 21, -202, 'tech', 'loot'),
        ('WC', 'Санузел', 16, -202, 21, -199, 'wc', ''),
        ('STR', 'Лестница', 7, -199, 11, -193, 'stair', ''),
        ('LIV', 'Гостиная-столовая с камином', 11, -199, 21, -193, 'pub', 'loot'),
    ],
    2: [
        ('STR', 'Лестница', 7, -199, 11, -193, 'stair', ''),
        ('HL2', 'Холл', 11, -201, 14, -193, 'corr', ''),
        ('BTH', 'Ванная', 11, -205, 14, -201, 'wc', ''),
        ('BD3', 'Детская', 7, -205, 11, -199, 'pub', 'loot'),
        ('BD2', 'Спальня', 14, -205, 21, -199, 'pub', 'loot'),
        ('BD1', 'Спальня с балконом', 14, -199, 21, -193, 'pub', 'loot'),
    ],
}
CT_D = {
    1: [('HAL', 'out', ('S', 0.5), DOOR), ('HAL', 'KIT', 0.5, DOOR), ('HAL', 'STR', 0.5, 3.0), ('KIT', 'LIV', 0.5, DOOR2),
        ('STR', 'LIV', 0.5, 3.0), ('KIT', 'UTL', 0.5, DOOR), ('UTL', 'out', ('E', 0.5), DOOR), ('LIV', 'WC', 0.5, DOOR),
        ('LIV', 'out', ('N', 0.6), DOOR2)],
    2: [('STR', 'HL2', 0.5, 3.0), ('HL2', 'BTH', 0.5, DOOR), ('HL2', 'BD3', 0.5, DOOR), ('HL2', 'BD2', 0.5, DOOR),
        ('HL2', 'BD1', 0.5, DOOR)],
}
p, CT_BY = check('коттедж', CT, CT_D, ['STR'])
PROBLEMS += p
num = numbered(CT)
img, d = sheet(1500, 900, 'Санаторий · коттедж v01 — два этажа, 14 × 12 м, одна планировка на все дома',
               'дом северного ряда (улица на юге); южный ряд — зеркально · этаж 3,4 м (потолок 3,1) · двускатная кровля · '
               'координаты схемы участка, метры игры')
for i, f in enumerate((1, 2)):
    P = kit.Plan(d, 30 + i * 470, 110, 2.0, -184.0, 19.0)
    P.rect(2, -214, 26.5, -184, fill=(226, 230, 214), outline=None)
    P.rect(2, -214, 26.5, -210.5, fill=(190, 190, 186), outline=None)              # улица коттеджей
    P.text(14, -212.3, 'улица', 11, MUTED)
    P.rect(22, -210, 25.5, -204, fill=(200, 206, 196), outline=MUTED)            # своё место — газонная решётка
    P.rect(22.4, -209.6, 25.1, -205, fill=(96, 100, 112), outline=None)
    P.text(23.75, -203, 'место', 10, MUTED)
    P.rect(7, -207, 12, -205, fill=(222, 206, 176), outline=MUTED)               # крыльцо под навесом
    P.rect(11, -193, 21, -190, fill=(222, 206, 176), outline=MUTED)              # терраса к лесу
    P.text(16, -191.5, 'терраса', 10, MUTED)
    if f == 2:
        P.rect(14, -193, 21, -191.5, fill=(236, 236, 236), outline=kit.GLASS, width=2)   # балкон
    P.rooms(CT[f], CT_BY[f], CT_D[f], num[f])
    for k in range(1, 10):                                                       # марш лестницы
        P.line([(7.3, -199 + k * 0.6), (10.7, -199 + k * 0.6)], fill=MUTED)
    if f == 1:
        P.rect(17.5, -194, 20.5, -193.4, fill=(120, 90, 70), outline=None)       # камин
        P.text(19, -194.6, 'камин', 9, MUTED)
        P.rect(11.3, -204.6, 15.6, -204, fill=(200, 200, 205), outline=None)     # кухонный ряд
    else:
        for x0, y0 in ((15.5, -197.5), (15.5, -203.5)):
            P.rect(x0, y0, x0 + 2.0, y0 + 2.2, fill=(236, 236, 230), outline=MUTED)   # кровати 1:1
        P.rect(8, -204, 9.2, -202, fill=(236, 236, 230), outline=MUTED)
    P.labels(CT[f], num[f])
    d.text((30 + i * 470, 110 + 30 * 19 + 8), f'{f} этаж', font=font(16, True), fill=INK)
sx = 30 + 2 * 470 + 10
yy = sx and 110
for f in (1, 2):
    yy, _ = kit.schedule(d, CT[f], num[f], sx, yy, f'Помещения {f} этажа', name_w=330)
notes(d, sx, yy + 6, ['**Предложение**',
                      'Вход с улицы через крыльцо, боковой — из котельной',
                      'к своему месту; к лесу — терраса из гостиной,',
                      'над ней балкон спальни. Лестница прямая, у стены.',
                      'Вид снаружи — по картинке 15: тёмная доска,',
                      'двускатная кровля, крыльцо с навесом и бра.',
                      '**Для боя**',
                      'Три входа; окна во все стороны; лестница — узкое',
                      'место; с балкона видно улицу и лес за домами.'])
img.save(PLANS / 'sanatorium_cottage_v01.png')

# ============================================================================ 2. «СТРЕЛКА»: павильон и маяк
MOLE_PTS = [(-148, -26), (-205, -20), (-258, -6), (-286, 4), (-292, 10), (-286, 16), (-258, 26), (-205, 40), (-148, 46)]
PV = {
    1: [
        ('PH', 'Кофейня: зал на ≈ 40 мест, стойка бариста', -240, 0, -214, 20, 'pub', 'loot'),
        ('PWC', 'Санузлы', -246, 0, -240, 6, 'wc', ''),
        ('PST', 'Подсобка кофейни: склад, мойка, ключ от маяка', -246, 6, -240, 12, 'serv', 'loot'),
        ('PSR', 'Лестница на крышу', -246, 12, -240, 20, 'stair', ''),
    ],
    2: [
        ('PSR', 'Лестница на крышу', -246, 12, -240, 20, 'stair', ''),
        ('DECK', 'Смотровая площадка на крыше', -240, 0, -214, 20, 'pub', ''),
    ],
}
PV_D = {
    1: [('PH', 'out', ('E', 0.5), 3.0), ('PH', 'out', ('N', 0.35), DOOR2), ('PH', 'out', ('S', 0.35), DOOR2),
        ('PH', 'PWC', 0.5, DOOR), ('PH', 'PST', 0.5, DOOR), ('PH', 'PSR', 0.5, DOOR2)],
    2: [('PSR', 'DECK', 0.5, DOOR2), ('DECK', 'out', ('N', 0.8), DOOR2)],          # наружная лестница на мол
}
LH = {   # маяк: башня Ø 6 м, внутри винтовая лестница; наверху фонарь и обходная галерея
    1: [('LH0', 'Маяк, нижний ярус, винтовая лестница', -291, 7, -285, 13, 'stair', 'loot')],
    2: [('LH0', 'Маяк, нижний ярус, винтовая лестница', -291, 7, -285, 13, 'stair', ''),
        ('LHG', 'Фонарный ярус и обходная галерея', -293.5, 4.5, -291, 15.5, 'pub', '')],
}
LH_D = {1: [('LH0', 'out', ('E', 0.5), DOOR)], 2: [('LH0', 'LHG', 0.5, DOOR)]}
LH_LOCK = {('LH0', 'out')}
p, PV_BY = check('павильон', PV, PV_D, ['PSR'])
PROBLEMS += p
p, LH_BY = check('маяк', LH, LH_D, ['LH0'])
PROBLEMS += p
pn = numbered(PV)
img, d = sheet(1900, 1060, 'Санаторий · «Стрелка» v02 — мол-променад, павильон-кофейня со смотровой площадкой, маяк',
               'стрелка, а не причал, катеров нет · павильон 32 × 20 м — кофейня, без экспонатов (решение владельца) · '
               'маяк 16 м, галерея только с ключом · координаты схемы участка, метры игры')
S = kit.Plan(d, 30, 100, -300.0, 52.0, 6.0)
S.rect(-300, -32, -140, 52, fill=(150, 186, 206), outline=None)
S.poly(MOLE_PTS, fill=(214, 206, 188), outline=INK, width=2)
S.rect(-148, -32, -140, 52, fill=(214, 206, 188), outline=None)
S.text(-144, 49, 'набережная', 10, MUTED)
S.circle(-182, 10, 9, fill=(150, 196, 220), outline=INK, width=2)               # фонтан
S.text(-182, 10, 'фонтан', 11, INK)
for kx, ky in ((-200, -8), (-262, 18), (-232, 30)):                              # киоски
    S.rect(kx - 3, ky - 2.5, kx + 3, ky + 2.5, fill=(236, 236, 232), outline=INK)
    S.text(kx, ky, 'киоск', 9, INK)
for k in range(10):                                                              # колоннада с навесом
    S.circle(-192 - k * 5.5, 36 - k * 0.9, 0.7, fill=INK, outline=None)
S.line([(-192, 37.5), (-241.5, 29.4)], fill=MUTED, width=1)
S.text(-216, 36, 'колоннада под навесом', 10, MUTED)
S.circle(-270, 10, 5, fill=(236, 236, 232), outline=INK, width=2)               # ротонда
for k in range(8):
    a = math.radians(k * 45)
    S.circle(-270 + 4.4 * math.cos(a), 10 + 4.4 * math.sin(a), 0.5, fill=INK, outline=None)
S.text(-270, 10, 'ротонда', 10, INK)
for px_, py_ in ((-192, 2), (-206, 18), (-226, -6), (-252, 10), (-170, -8), (-240, 36),
                 (-166, 30), (-172, 22), (-176, -16), (-212, -12), (-196, -13)):  # вазоны, стенки, скамьи — укрытия
    S.rect(px_ - 3.5, py_ - 1.2, px_ + 3.5, py_ + 1.2, fill=(160, 180, 120), outline=MUTED)
S.rooms(PV[1], PV_BY[1], PV_D[1], pn[1])
S.rect(-234, 20, -222, 23, fill=(200, 200, 196), outline=INK)                   # наружная лестница на крышу
S.text(-228, 21.5, 'лестница на крышу', 9, INK)
S.rect(-239, 8, -238, 18, fill=(150, 110, 80), outline=None)                  # стойка бариста вдоль подсобки
S.rect(-239, 18, -232, 19, fill=(150, 110, 80), outline=None)
for ix in range(4):                                                              # столики у панорамы
    for iy in range(3):
        S.circle(-233 + ix * 5, 3.5 + iy * 4.5, 0.7, fill=(255, 255, 255), outline=MUTED)
S.rooms(LH[1], LH_BY[1], LH_D[1], {'LH0': 'М'}, LH_LOCK)
S.circle(-288, 10, 3, fill=(240, 240, 240), outline=(200, 40, 40), width=3)
S.text(-288, 10, 'маяк', 9, INK)
S.labels(PV[1], pn[1], at={'PH': (-227, 16.5)})
bx, by = S.p(-298, -30)
d.line([(bx, by), (bx + 20 * 6, by)], fill=INK, width=3)
d.text((bx + 60, by - 10), '20 м', font=font(12), fill=INK, anchor='mm')
# крыша павильона и маяк в разрезе
R = kit.Plan(d, 1020, 100, -250.0, 24.0, 10.0)
R.rect(-250, -4, -210, 24, fill=(214, 206, 188), outline=None)
R.rooms(PV[2], PV_BY[2], PV_D[2], pn[2])
for k in range(4):
    R.circle(-236 + k * 6, 18, 0.5, fill=INK, outline=None)                       # подзорные трубы
R.text(-227, 15.5, 'подзорные трубы, скамьи', 10, INK)
R.rect(-234, 20, -222, 23, fill=(200, 200, 196), outline=INK)
R.labels(PV[2], pn[2])
d.text((1020, 100 + 28 * 10 + 6), 'Крыша павильона: смотровая площадка, лестницы внутренняя и наружная', font=font(14, True), fill=INK)
# разрез маяка
mx, mz0 = 1110, 640


def M(x, z):
    return (mx + x * 9, mz0 - z * 9)


d.text((1020, 440), 'Маяк — разрез', font=font(14, True), fill=INK)
d.polygon([M(-3, 0), M(3, 0), M(2.3, 12), M(-2.3, 12)], fill=(240, 240, 240), outline=INK)
for z in (2, 4.5, 7, 9.5):
    d.rectangle([M(-2.6, z + 1), M(2.6, z)], fill=(200, 40, 40))
d.rectangle([M(-3.7, 12.3), M(3.7, 12)], fill=(90, 90, 96))                     # галерея
d.line([M(-3.7, 12.3), M(-3.7, 13.4)], fill=INK, width=2)
d.line([M(3.7, 12.3), M(3.7, 13.4)], fill=INK, width=2)
d.rectangle([M(-1.6, 15), M(1.6, 12.3)], fill=(250, 230, 150), outline=INK)    # фонарь
d.polygon([M(-1.9, 15), M(1.9, 15), M(0, 16.5)], fill=(200, 40, 40))
for k in range(12):                                                              # винтовая лестница
    z = k
    d.line([M(-1.4 if k % 2 else 1.4, z), M(1.4 if k % 2 else -1.4, z + 1)], fill=MUTED)
d.rectangle([M(-0.6, 2.1), M(0.6, 0)], fill=(60, 60, 64))
for z, lab in ((0, '±0 мол +1,5'), (12, '+12 галерея'), (16.5, '+16,5')):
    d.text(M(4.5, z), lab, font=font(11), fill=MUTED, anchor='lm')
d.text(M(-3.2, -1.6), 'дверь (на ключ)', font=font(11), fill=(200, 40, 40), anchor='lm')
sx = 1360
yy = 440
yy, _ = kit.schedule(d, PV[1] + PV[2][1:], {**pn[1], **pn[2]}, sx, yy, 'Павильон', name_w=440)
notes(d, sx, yy + 4, ['**Решения владельца**',
                      'Павильон — кофейня, экспонатов нет. Маяк — только с ключом.',
                      '**Предложение**',
                      'Кофейня: стойка бариста вдоль подсобки, столики у стекла',
                      'в пол на озеро; подсобка — склад, мойка, ключ от маяка.',
                      'На крыше — смотровая площадка с подзорными трубами;',
                      'подъём изнутри и по наружной лестнице с мола.',
                      'Маяк: внутри винтовая лестница, наверху галерея',
                      'вокруг фонаря; галерея видит весь мол и пляж.',
                      '**Для боя**',
                      'Укрытия на молу — через 15–25 м: вазоны, стенки,',
                      'киоски, колоннада, ротонда, фонтан. Крыша павильона',
                      'и галерея маяка — позиции сверху на открытый мол.'])
img.save(PLANS / 'sanatorium_strelka_v02.png')

# ============================================================================ 3. АМФИТЕАТР
AC = (-84.0, -160.0)            # центр рядов — у переднего края сцены
ROW_R0, ROW_STEP, ROWS = 16.0, 1.2, 10          # ряд 1,2 м (0,9 × 1,3), подъём 0,4 м на ряд
SPAN = 62.0                                      # ± градусов
AISLES = (-40.0, 0.0, 40.0)
SEAT = 0.65                                      # место на скамье с запасом (люди 1:1)
seats = 0
for k in range(ROWS):
    r = ROW_R0 + (k + 0.5) * ROW_STEP
    seats += int((math.radians(2 * SPAN) * r - len(AISLES) * 1.5) / SEAT)
AM = {
    -1: [
        ('BCR', 'Коридор за сценой, выход к тропе', -96, -176, -92, -144, 'corr', ''),
        ('BTC', 'Щитовая, свет и звук', -92, -170, -86, -166, 'tech', 'loot'),
        ('BG1', 'Гримёрка', -92, -166, -86, -160, 'pub', 'loot'),
        ('BG2', 'Гримёрка', -92, -160, -86, -154, 'pub', 'loot'),
        ('BWC', 'Санузел', -92, -154, -86, -150, 'wc', ''),
        ('BST', 'Склад декораций и аппаратуры', -86, -170, -80, -150, 'store', 'loot'),
        ('KUL1', 'Кулисы север, лестница на сцену', -92, -150, -84, -144, 'stair', ''),
        ('KUL2', 'Кулисы юг, лестница на сцену', -92, -176, -84, -170, 'stair', ''),
    ],
    0: [
        ('STG', 'Сцена, +1,0 над оркестрой', -92, -170, -80, -150, 'pub', ''),
        ('KUL1', 'Кулисы север, лестница на сцену', -92, -150, -84, -144, 'stair', ''),
        ('KUL2', 'Кулисы юг, лестница на сцену', -92, -176, -84, -170, 'stair', ''),
        ('APP', 'Аппаратная на верхнем променаде', -57, -162, -53, -158, 'tech', 'loot'),
    ],
}
AM_D = {
    -1: [('BCR', 'out', ('W', 0.5), DOOR2), ('BCR', 'BTC', 0.5, DOOR), ('BCR', 'BG1', 0.5, DOOR), ('BCR', 'BG2', 0.5, DOOR),
         ('BCR', 'BWC', 0.5, DOOR), ('BCR', 'KUL1', 0.5, DOOR2), ('BCR', 'KUL2', 0.5, DOOR2), ('KUL1', 'BST', 0.5, DOOR),
         ('KUL2', 'BST', 0.5, DOOR)],
    0: [('STG', 'out', ('E', 0.5), 12.0), ('STG', 'KUL1', 0.5, 4.0), ('STG', 'KUL2', 0.5, 4.0),
        ('KUL1', 'out', ('N', 0.5), DOOR), ('KUL2', 'out', ('S', 0.5), DOOR), ('APP', 'out', ('E', 0.5), DOOR)],
}
p, AM_BY = check('амфитеатр', AM, AM_D, ['KUL1', 'KUL2'])
PROBLEMS += p
an = numbered(AM)
img, d = sheet(1900, 1000, f'Санаторий · амфитеатр v01 — {ROWS} рядов, ≈ {seats} мест, сцена у бровки, задник — озеро и плотина',
               'ряд 1,2 м, подъём 0,4 м, места 0,65 м · под сценой (−4 м, в склоне) — гримёрки, склад, щитовая, выход к тропе · '
               'координаты схемы участка, метры игры')
A = kit.Plan(d, 30, 100, -112.0, -124.0, 11.0)
A.rect(-112, -196, -40, -124, fill=(226, 230, 214), outline=None)
A.poly([(-112, -196), (-95.4, -196), (-95.4, -124), (-112, -124)], fill=(176, 190, 150), outline=None)
A.text(-110, -126, 'склон', 11, MUTED, False, 'lm')
for k in range(ROWS + 1):                                                        # ряды
    r = ROW_R0 + k * ROW_STEP
    pts = [(AC[0] + r * math.cos(math.radians(a)), AC[1] + r * math.sin(math.radians(a))) for a in range(-62, 63, 2)]
    A.line(pts, fill=(150, 150, 150), width=2)
for a in AISLES:
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    A.line([(AC[0] + ROW_R0 * ca, AC[1] + ROW_R0 * sa), (AC[0] + (ROW_R0 + ROWS * ROW_STEP) * ca,
                                                         AC[1] + (ROW_R0 + ROWS * ROW_STEP) * sa)], fill=(226, 230, 214), width=12)
RP = ROW_R0 + ROWS * ROW_STEP
pts_o = [(AC[0] + (RP + 4) * math.cos(math.radians(a)), AC[1] + (RP + 4) * math.sin(math.radians(a))) for a in range(-70, 71, 2)]
pts_i = [(AC[0] + RP * math.cos(math.radians(a)), AC[1] + RP * math.sin(math.radians(a))) for a in range(70, -71, -2)]
A.poly(pts_o + pts_i, fill=(232, 228, 214), outline=MUTED)                       # верхний променад
for k in range(17):
    a = math.radians(-64 + k * 8)
    A.circle(AC[0] + (RP + 4) * math.cos(a), AC[1] + (RP + 4) * math.sin(a), 0.5, fill=INK, outline=None)
A.text(AC[0] + RP + 2, AC[1] - 14, 'променад и колоннада', 10, MUTED)
A.poly([(AC[0], AC[1] - 16)] + [(AC[0] + 16 * math.cos(math.radians(a)), AC[1] + 16 * math.sin(math.radians(a)))
                                for a in range(-62, 63, 4)], fill=(236, 232, 220), outline=None)
A.text(AC[0] + 9, AC[1], 'оркестра', 11, MUTED)
A.rooms(AM[0], AM_BY[0], AM_D[0], an[0])
for x0, x1 in ((-91.5, -89.5), (-82.5, -80.5)):
    A.rect(x0, -169, x1, -168, fill=(90, 90, 96), outline=None)                 # фермы света
    A.rect(x0, -152, x1, -151, fill=(90, 90, 96), outline=None)
A.labels(AM[0], an[0])
d.text((30, 100 + 72 * 11 + 6), 'Уровень сцены и рядов', font=font(15, True), fill=INK)
B = kit.Plan(d, 860, 100, -100.0, -140.0, 13.0)
B.rect(-100, -180, -76, -140, fill=(176, 190, 150), outline=None)
B.rooms(AM[-1], AM_BY[-1], AM_D[-1], an[-1])
B.labels(AM[-1], an[-1])
d.text((860, 100 + 40 * 13 + 6), 'Под сценой, −4 м (в склоне)', font=font(15, True), fill=INK)
sx = 1230
yy = 100
for f in (0, -1):
    yy, _ = kit.schedule(d, AM[f], an[f], sx, yy, 'Сцена и ряды' if f == 0 else 'Под сценой', name_w=400)
notes(d, sx, yy + 6, ['**Предложение**',
                      f'{ROWS} рядов полукругом ±62° на радиусах {ROW_R0:.0f}–{RP:.0f} м, три прохода,',
                      f'≈ {seats} мест (решение владельца — ≈ 600). Верх рядов +4 м,',
                      'по нему променад с колоннадой, по оси — аппаратная.',
                      'Сцена 12 × 20 м на +1 м, по бокам кулисы с лестницами',
                      'вниз; под сценой в склоне — коридор с выходом к тропе,',
                      'гримёрки, склад, щитовая, санузел.',
                      '**Для боя**',
                      'Ряды — ступенчатые укрытия; с верха видно сцену',
                      'и озеро; под сценой — ближний бой и скрытый ход',
                      'между тропой и сценой.'])
img.save(PLANS / 'sanatorium_amphitheatre_v01.png')

# ============================================================================ 4. ХОЗДВОР
HZ = [
    ('KB', 'Котельный зал: 2 котла, насосы', 96, 178, 112, 194, 'tech', 'loot'),
    ('KP', 'Пульт оператора', 112, 186, 118, 194, 'tech', 'loot'),
    ('KM', 'Мастерская', 112, 178, 118, 186, 'tech', 'loot'),
    ('LR', 'Приём грязного белья', 96, 200, 102, 212, 'serv', ''),
    ('LW', 'Стиральный цех', 102, 200, 110, 212, 'serv', ''),
    ('LC', 'Гладильная, чистое бельё', 110, 200, 114, 212, 'serv', 'loot'),
    ('G1', 'Гараж, бокс 1', 126, 158, 140, 165, 'store', 'loot'),
    ('G2', 'Гараж, бокс 2', 126, 165, 140, 172, 'store', 'loot'),
    ('G3', 'Гараж, бокс 3', 126, 172, 140, 179, 'store', 'loot'),
    ('GS', 'Кладовая запчастей', 126, 179, 140, 182, 'store', 'loot'),
    ('SK', 'Склад хозинвентаря', 110, 160, 122, 169, 'store', 'loot'),
    ('SKK', 'Кладовщик', 110, 169, 122, 172, 'serv', 'loot'),
    ('TR', 'Трансформаторы', 98, 162, 104, 170, 'tech', ''),
    ('TRU', 'Щиты РУ-0,4 кВ', 104, 162, 108, 170, 'tech', 'loot'),
    ('WT', 'Водонапорная башня: насосная', 119, 201, 125, 207, 'tech', ''),
]
HZ_D = [
    ('KB', 'out', ('W', 0.5), 3.0), ('KB', 'KP', 0.5, DOOR), ('KB', 'KM', 0.5, DOOR), ('KM', 'out', ('S', 0.5), DOOR),
    ('LR', 'out', ('W', 0.5), DOOR2), ('LR', 'LW', 0.5, DOOR2), ('LW', 'LC', 0.5, DOOR2), ('LC', 'out', ('E', 0.5), DOOR),
    ('G1', 'out', ('W', 0.5), 3.5), ('G2', 'out', ('W', 0.5), 3.5), ('G3', 'out', ('W', 0.5), 3.5), ('GS', 'out', ('W', 0.5), DOOR),
    ('G3', 'GS', 0.5, DOOR),
    ('SK', 'out', ('W', 0.5), 3.0), ('SK', 'SKK', 0.5, DOOR), ('SKK', 'out', ('N', 0.5), DOOR),
    ('TR', 'out', ('W', 0.5), DOOR2), ('TR', 'TRU', 0.5, DOOR), ('TRU', 'out', ('E', 0.5), DOOR),
    ('WT', 'out', ('S', 0.5), DOOR),
]
HZ_LOCK = {('TR', 'out'), ('TRU', 'out')}
p, HZ_BY = check('хоздвор', {1: HZ}, {1: HZ_D})
PROBLEMS += p
hn = numbered({1: HZ})[1]
img, d = sheet(1800, 980, 'Санаторий · хоздвор v01 — котельная, прачечная, гаражи, склад, трансформаторная, водонапорная башня',
               'северо-восточный угол за забором, въезд с северной ветки · одноэтажные, кроме башни · старая советская постройка '
               '(картинка 12) · координаты схемы участка, метры игры')
H = kit.Plan(d, 30, 100, 86.0, 222.0, 11.0)
H.rect(86, 150, 150, 222, fill=(226, 230, 214), outline=None)
H.poly([(92, 156), (144, 156), (144, 216), (92, 216)], fill=(200, 198, 192), outline=None)   # асфальт двора
H.line([(92, 156), (144, 156), (144, 216), (92, 216), (92, 199)], fill=(60, 110, 70), width=3)
H.line([(92, 193), (92, 156)], fill=(60, 110, 70), width=3)
H.text(89, 196, 'ворота', 10, MUTED)
H.rect(86, 194, 92, 198, fill=(190, 190, 186), outline=None)
H.poly([(97, 160), (109, 160), (109, 172), (97, 172)], outline=(60, 110, 70), width=2)    # сетка вокруг трансформаторной
H.rooms(HZ, HZ_BY[1], HZ_D, hn, HZ_LOCK)
H.circle(123, 186, 1.6, fill=(150, 90, 70), outline=INK, width=2)              # труба
H.text(127, 189, 'труба 30 м', 10, INK, False, 'lm')
H.circle(122, 204, 4, outline=INK, width=2)                                      # ствол башни
H.text(122, 209.5, 'бак на +18 м — подняться нельзя', 10, INK)
for k in range(2):
    H.rect(98 + k * 4, 180, 101 + k * 4, 188, fill=(150, 150, 160), outline=INK)   # котлы
for k in range(3):
    H.rect(103 + k * 2.5, 202, 105 + k * 2.5, 204, fill=(210, 210, 215), outline=MUTED)   # машины
for x, y in ((100, 196), (103, 196), (130, 194), (133, 194)):                    # еврокубы, поддоны
    H.rect(x, y, x + 1.2, y + 1.2, fill=(230, 230, 230), outline=MUTED)
H.labels(HZ, hn)
bx, by = H.p(88, 152)
d.line([(bx, by), (bx + 10 * 11, by)], fill=INK, width=3)
d.text((bx + 55, by - 10), '10 м', font=font(12), fill=INK, anchor='mm')
sx = 780
yy, _ = kit.schedule(d, HZ, hn, sx, 100, 'Помещения', name_w=440)
yy = kit.legend(d, sx, yy + 4, ['tech', 'serv', 'store'])
notes(d, sx, yy + 6, ['**Предложение**',
                      'Двор за забором, ворота с северной ветки. Котельная с трубой — ориентир; прачечная — поток',
                      'грязное → стирка → чистое; гаражи — три бокса с подъёмными воротами и кладовая запчастей;',
                      'склад с кладовщиком; трансформаторная за сеткой (на ключ); водонапорная башня — насосная',
                      'внизу, бак на +18 м; подняться на бак нельзя (решение владельца), лестница снизу перекрыта.',
                      '**Для боя**',
                      'Двор — средняя дистанция: еврокубы, поддоны, машины; постройки — ближний бой; лут — инструмент,',
                      'запчасти, топливо, ключи у кладовщика.'])
img.save(PLANS / 'sanatorium_hozdvor_v01.png')

# ============================================================================ 5. ДЕТСКАЯ ПЛОЩАДКА
PG = (0.0, -150.0, 60.0, -96.0)
ITEMS = [  # (название, форма, геометрия, высота м, цвет, укрытие)
    ('Корабль: палуба, мачта, рубка, горка, сетка', 'ship', (9, -136.5, 23, -131.5), 1.5, (196, 160, 110), 'стены борта 1,2 м'),
    ('Самолёт на опорах, горка', 'plane', (10, -117, 22, -107), 2.5, (200, 200, 205), 'опоры, фюзеляж'),
    ('Грузовик: кабина, кузов-лазалка, горка', 'truck', (42, -113.5, 53, -110.5), 2.2, (200, 196, 120), 'кабина'),
    ('Верёвочная пирамида Ø 8, высота 6', 'pyramid', (46, -136, 4.0), 6.0, (200, 80, 70), 'сквозная'),
    ('Качели на А-стойках, 2 × 2 места', 'swing', (26, -102, 42, -100), 2.4, (150, 110, 80), 'стойки'),
    ('Качели-гнездо', 'swing', (44, -102, 50, -100), 2.4, (150, 110, 80), 'стойки'),
    ('Батуты в уровень с покрытием, 2 шт.', 'tramp', ((30, -142), (35, -142)), 0.0, (60, 60, 64), 'нет'),
    ('Качалки на пружине: лошадка, рыбка, 4 шт.', 'spring', ((29, -124), (32, -124), (35, -124), (38, -124)), 0.9, (240, 200, 120), 'нет'),
    ('Карусель Ø 3', 'carousel', (31, -131, 1.5), 1.0, (240, 200, 80), 'низкая'),
    ('Песочница с навесом', 'sand', (51, -147, 58, -141), 0.4, (232, 216, 170), 'бортик'),
]
img, d = sheet(1600, 900, 'Санаторий · детская площадка v01 — состав и расстановка',
               '60 × 54 м за низкой оградой, резиновое покрытие пятнами; городки «корабль», «самолёт», «грузовик» (решение '
               'владельца) · вид — по картинке 23 · оборудование 1:1')
G = kit.Plan(d, 30, 100, -4.0, -92.0, 12.0)
G.rect(-4, -154, 64, -92, fill=(226, 230, 214), outline=None)
G.rect(*PG, fill=(236, 214, 196), outline=None)
G.rect(2, -138, 26, -98, fill=(214, 120, 110), outline=None)                     # красное — у городков
G.rect(24, -110, 52, -97, fill=(150, 196, 140), outline=None)                    # зелёное — качели
G.rect(46, -150, 60, -124, fill=(140, 170, 214), outline=None)                   # синее — малыши
G.line([(PG[0], PG[1]), (PG[2], PG[1]), (PG[2], PG[3]), (PG[0], PG[3]), (PG[0], PG[1])], fill=(60, 110, 70), width=3)
for gx, gy, ax in ((30, -96, 'h'), (60, -120, 'v')):                            # калитки
    if ax == 'h':
        G.rect(gx - 1.5, gy - 0.4, gx + 1.5, gy + 0.4, fill=(250, 250, 250), outline=None)
    else:
        G.rect(gx - 0.4, gy - 1.5, gx + 0.4, gy + 1.5, fill=(250, 250, 250), outline=None)
G.text(30, -94, 'калитка', 10, MUTED)
G.text(62, -120, 'калитка', 10, MUTED, False, 'lm')
for k, (name, kind, geo, h, col, cov) in enumerate(ITEMS, 1):
    if kind == 'ship':
        x0, y0, x1, y1 = geo
        G.poly([(x0, y0), (x1 - 2, y0), (x1, (y0 + y1) / 2), (x1 - 2, y1), (x0, y1)], fill=col, outline=INK, width=2)
        G.circle(17, -134, 0.4, fill=INK, outline=None)
        G.rect(10, -135.5, 13, -132.5, fill=(240, 240, 240), outline=INK)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    elif kind == 'plane':
        G.rect(10, -113, 22, -111, fill=col, outline=INK)
        G.rect(15, -117, 17, -107, fill=col, outline=INK)
        G.rect(10, -114.5, 11.5, -109.5, fill=col, outline=INK)
        cx, cy = 19, -115
    elif kind == 'truck':
        G.rect(42, -113.5, 50, -110.5, fill=col, outline=INK)
        G.rect(50, -113.5, 53, -110.5, fill=(170, 190, 130), outline=INK)
        cx, cy = 47.5, -115
    elif kind == 'pyramid':
        x, y, r = geo
        G.circle(x, y, r, outline=col, width=3)
        G.line([(x - r, y), (x + r, y)], fill=col)
        G.line([(x, y - r), (x, y + r)], fill=col)
        cx, cy = x, y
    elif kind == 'swing':
        x0, y0, x1, y1 = geo
        G.rect(x0, y0, x1, y1, outline=col, width=2)
        cx, cy = (x0 + x1) / 2, y1 + 1.5
    elif kind == 'tramp':
        for x, y in geo:
            G.circle(x, y, 1.5, fill=col, outline=INK)
        cx, cy = 32.5, -144.5
    elif kind == 'spring':
        for x, y in geo:
            G.circle(x, y, 0.5, fill=col, outline=INK)
        cx, cy = 33.5, -126
    elif kind == 'carousel':
        x, y, r = geo
        G.circle(x, y, r, fill=col, outline=INK)
        cx, cy = x, y - 2.5
    else:
        G.rect(*geo, fill=col, outline=INK)
        cx, cy = (geo[0] + geo[2]) / 2, (geo[1] + geo[3]) / 2
    G.circle(cx, cy, 1.1, fill=(255, 255, 255), outline=INK)
    G.text(cx, cy, str(k), 10, INK, True)
for x, y in ((4, -100), (4, -120), (4, -140), (20, -148), (40, -148), (56, -100), (56, -110)):   # скамьи
    G.rect(x - 1, y - 0.3, x + 1, y + 0.3, fill=(150, 110, 80), outline=None)
for x, y in ((1, -97), (59, -97), (1, -149), (59, -149), (30, -149), (1, -123)):              # фонари
    G.circle(x, y, 0.4, fill=(240, 190, 80), outline=None)
bx, by = G.p(-2, -153)
d.line([(bx, by), (bx + 10 * 12, by)], fill=INK, width=3)
d.text((bx + 60, by - 10), '10 м', font=font(12), fill=INK, anchor='mm')
yy = 100
d.text((880, yy), 'Состав', font=font(16, True), fill=INK)
yy += 28
for k, (name, kind, geo, h, col, cov) in enumerate(ITEMS, 1):
    d.text((880, yy), f'{k}', font=font(13, True), fill=INK)
    d.text((910, yy), name, font=font(13), fill=INK)
    d.text((1330, yy), (f'{h:.1f} м'.replace('.', ',') if h else 'в уровень'), font=font(12), fill=MUTED)
    d.text((1410, yy), cov, font=font(12), fill=MUTED)
    yy += 20
notes(d, 880, yy + 10, ['**Вокруг**',
                        'Скамьи 7, урны, фонари-столбики 6, низкая зелёная ограда 1,2 м, две калитки —',
                        'с севера к амфитеатру и с востока к южной ветке. Покрытие пятнами: красное у',
                        'городков, зелёное у качелей, синее — уголок малышей с песочницей.',
                        '**Для боя**',
                        'Средняя дистанция: борт корабля и кабина грузовика — укрытия по пояс и грудь;',
                        'самолёт на опорах и пирамида — сквозные; ограда низкая, обзор почти свободный.'])
img.save(PLANS / 'sanatorium_playground_v01.png')

# ============================================================================ данные и итог
REPORT['playground'] = {'rect': PG, 'items': [{'name': n, 'kind': k, 'geo': g, 'height': h, 'cover': c}
                                              for n, k, g, h, col, c in ITEMS]}
REPORT['amphitheatre_rows'] = {'center': AC, 'r0': ROW_R0, 'step': ROW_STEP, 'rows': ROWS, 'span_deg': SPAN,
                               'aisles_deg': AISLES, 'seats': seats}
DATA.write_text(json.dumps(REPORT, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
for p in PROBLEMS:
    print('ЗАМЕЧАНИЕ:', p)
print(f'малые постройки: амфитеатр ≈ {seats} мест, замечаний {len(PROBLEMS)}')
