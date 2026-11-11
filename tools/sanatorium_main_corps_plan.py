# -*- coding: utf-8 -*-
"""Санаторий — главный корпус v03: два этажа, лобби в два света; план, адресные данные, проверка связей.

v03 (владелец после прогулки по серому блокауту): корпус тот же, на участке сдвинут к S-корпусам — в середину между
ними и «Рестораном и спа» (схема участка v11): на +4 м по x и +30 м по y. Лист рисуется в координатах v02 (подписи
окружения — по новому месту), в данных — координаты участка со сдвигом SITE_SHIFT.

Решения владельца 2026-11-07 (docs/design/sanatorium_main_corps.md, §1): главный корпус — отдельное строение в два
этажа. Входящего встречает общее пространство в два света — большие панорамные окна, очень высокий потолок; там
длинный ресепшен, общее лобби, бар, зона отдыха с диванами. Дальше — помещения, куда обычным посетителям доступа нет.
На 2 этаже — администрация, сейф и прочее; лестница на 2 этаж — с краю, без доступа для посетителей. Остальное —
предложение агента. Прежние планы v01 (три этажа в трёх крыльях со столовой и спа) устарели — генератор v01 в истории git.

Координаты — схемы участка (tools/sanatorium_map_plan.py), метры игры (правило E: помещения и проходы × 1,3).

    python -X utf8 tools/sanatorium_main_corps_plan.py
        → docs/plans/sanatorium_main_corps_v03.png, docs/design/data/sanatorium_main_corps_v03.json
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import DOOR, DOOR2, INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_main_corps_v03.png'
DATA = ROOT / 'docs/design/data/sanatorium_main_corps_v03.json'
SITE_SHIFT = (4.0, 30.0)       # v03: место корпуса на участке — сдвиг от координат листа

FLOOR_TO_FLOOR = {1: 4.5, 2: 4.0}      # лобби в два света — 8,5 м до потолка
STA = ('STA', 'Служебная лестница (только персонал)', -54, -20, -46, -10, 'stair', '')

ROOMS = {
    1: [
        ('LOB', 'Лобби в два света: длинный ресепшен, бар, диваны', -54, -4, -10, 16, 'pub', ''),
        STA,
        ('SEN', 'Служебный вход', -54, -10, -46, -4, 'corr', ''),
        ('TMB', 'Служебный тамбур — только персонал', -46, -10, -40, -4, 'corr', ''),
        ('LUG', 'Камера хранения багажа', -40, -10, -32, -4, 'store', 'loot'),
        ('BOF', 'Бэк-офис ресепшена', -32, -10, -22, -4, 'admin', 'loot'),
        ('GWC', 'Санузлы гостей', -22, -10, -10, -4, 'wc', ''),
        ('SCR', 'Служебный коридор', -46, -13.1, -10, -10, 'corr', ''),
        ('SEC', 'Пост охраны, видеонаблюдение', -46, -20, -38, -13.1, 'serv', 'loot'),
        ('STF', 'Комната персонала', -38, -20, -30, -13.1, 'serv', 'loot'),
        ('STO', 'Кладовая', -30, -20, -24, -13.1, 'store', 'loot'),
        ('SRV', 'Серверная', -24, -20, -18, -13.1, 'tech', 'loot'),
        ('UTL', 'Хозяйственная, выход к хоздвору', -18, -20, -10, -13.1, 'store', ''),
    ],
    2: [
        STA,
        ('HL2', 'Холл служебной лестницы', -54, -10, -46, -4, 'corr', ''),
        ('GLR', 'Галерея над лобби (стеклянное ограждение)', -54, -4, -10, 0, 'admin', ''),
        ('VOID', 'Второй свет лобби', -54, 0, -10, 16, 'void', ''),
        ('ACR', 'Коридор администрации', -46, -13.1, -10, -10, 'corr', ''),
        ('ACC', 'Бухгалтерия', -46, -10, -34, -4, 'admin', 'loot'),
        ('REC', 'Приёмная директора', -34, -10, -22, -4, 'admin', ''),
        ('DIR', 'Кабинет директора', -22, -10, -10, -4, 'admin', 'loot lock'),
        ('CSH', 'Касса с сейфом', -46, -20, -38, -13.1, 'admin', 'loot lock'),
        ('ARC', 'Архив', -38, -20, -30, -13.1, 'store', 'loot lock'),
        ('HRD', 'Отдел кадров', -30, -20, -24, -13.1, 'admin', 'loot'),
        ('KEY', 'Хозчасть, ключница', -24, -20, -18, -13.1, 'admin', 'loot'),
        ('MET', 'Переговорная', -18, -20, -10, -13.1, 'admin', ''),
    ],
}
DOORS = {
    1: [
        ('LOB', 'out', ('E', 0.5), 3.0), ('LOB', 'out', ('W', 0.5), 3.0), ('LOB', 'out', ('N', 0.5), DOOR2),
        ('LOB', 'TMB', 0.5, DOOR), ('LOB', 'LUG', 0.5, DOOR), ('LOB', 'BOF', 0.5, DOOR), ('LOB', 'GWC', 0.5, DOOR2),
        ('SEN', 'out', ('W', 0.5), DOOR), ('SEN', 'STA', 0.5, DOOR2), ('SEN', 'TMB', 0.5, DOOR),
        ('TMB', 'SCR', 0.5, DOOR), ('STA', 'SCR', 0.5, DOOR),       # багажная и бэк-офис — только из-за стойки
        ('SCR', 'SEC', 0.5, DOOR), ('SCR', 'STF', 0.5, DOOR), ('SCR', 'STO', 0.5, DOOR), ('SCR', 'SRV', 0.5, DOOR),
        ('SCR', 'UTL', 0.5, DOOR), ('UTL', 'out', ('S', 0.5), DOOR2),
    ],
    2: [
        ('STA', 'HL2', 0.5, DOOR2), ('STA', 'ACR', 0.5, DOOR), ('HL2', 'GLR', 0.5, DOOR2),
        ('ACR', 'ACC', 0.5, DOOR), ('ACR', 'REC', 0.5, DOOR), ('REC', 'DIR', 0.5, DOOR), ('REC', 'GLR', 0.5, DOOR2),
        ('ACC', 'GLR', 0.5, DOOR),
        ('ACR', 'CSH', 0.5, DOOR), ('ACR', 'ARC', 0.5, DOOR), ('ACR', 'HRD', 0.5, DOOR), ('ACR', 'KEY', 0.5, DOOR),
        ('ACR', 'MET', 0.5, DOOR),
    ],
}
LOCKED = {('REC', 'DIR'), ('ACR', 'CSH'), ('ACR', 'ARC')}
STAFF_DOOR = ('LOB', 'TMB')            # единственный проход из лобби в служебную часть

PROBLEMS, BY = [], {}
for f in ROOMS:
    probs, by = kit.check_floor(ROOMS[f], DOORS[f], LOCKED, reach_check=False)
    PROBLEMS += [f'{f} эт.: {x}' for x in probs]
    BY[f] = by
unreach, unreach_nokey = kit.reach_multi({f: (ROOMS[f], DOORS[f]) for f in ROOMS}, ['STA'], LOCKED)
PROBLEMS += [f'не дойти: {f} эт. {r}' for f, r in unreach] + [f'без ключей не дойти: {f} эт. {r}' for f, r in unreach_nokey]
NUM = {}
for f in ROOMS:
    k = 0
    for r in ROOMS[f]:
        if r[6] != 'void':
            k += 1
            NUM.setdefault(f, {})[r[0]] = f'{f}.{k:02d}'

# ----------------------------------------------------------------------------- рисунок
XMIN, XMAX, YMIN, YMAX = -64.0, 0.0, -28.0, 24.0
SC = 9.4
PW = int((XMAX - XMIN) * SC)
PH = int((YMAX - YMIN) * SC)
W = PW * 2 + 90 + 40
H = 100 + PH + 30 + 600
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
d.text((30, 18), 'Санаторий · главный корпус v03 — два этажа, лобби в два света; на участке — в середине между S-корпусами и рестораном', font=font(21, True), fill=INK)
d.text((30, 50), 'входящего встречают длинный ресепшен, бар и диваны; дальше — служебные помещения; 2 этаж — администрация и сейф,'
       ' лестница с краю — только персонал', font=font(14), fill=MUTED)
d.text((30, 70), 'этаж 4,5 / 4,0 м, лобби ≈ 8,5 м до потолка · координаты листа = участок v10; на участке v11 корпус '
       'сдвинут на (+4, +30) м · метры игры', font=font(13), fill=MUTED)

for i, f in enumerate((1, 2)):
    P = kit.Plan(d, 30 + i * (PW + 60), 100, XMIN, YMAX, SC)
    P.rect(XMIN, YMIN, XMAX, YMAX, fill=(226, 230, 214), outline=None)
    P.rect(-64, 3, -54, 9, fill=(218, 210, 196), outline=None)                    # v03: дорожка к парадной террасе (юго-запад)
    P.text(-59, 11, 'к террасе', 10, MUTED)
    P.rect(-10, 3, 0, 9, fill=(218, 210, 196), outline=None)                      # дорожка к кругу с фонтаном
    P.text(-5, 11, 'к фонтану', 10, MUTED)
    P.rect(-34, 16, -30, 24, fill=(218, 210, 196), outline=None)                  # дорожка к S-корпусам
    P.rect(-16, -26, -12, -20, fill=(218, 210, 196), outline=None)                # служебный выход в парк
    P.text(-14, -24, 'к ресторану', 10, MUTED)
    P.rooms(ROOMS[f], BY[f], DOORS[f], NUM[f], LOCKED)
    if f == 2:
        for k in range(0, 64, 3):
            P.line([(-54 + max(0, k - 16), min(16, k)), (-54 + min(44, k), max(0, k - 44))], fill=(205, 205, 205))
        P.text(-32, 8, 'второй свет лобби', 13, MUTED)
        P.line([(-54, 0), (-10, 0)], fill=kit.GLASS, width=3)                     # стеклянное ограждение галереи
    else:
        P.rect(-40, -3.2, -16, -2.2, fill=(196, 170, 130), outline=None)          # длинный ресепшен
        P.text(-28, -0.8, 'длинный ресепшен', 11, INK)
        P.rect(-20, 9, -12, 10, fill=(150, 110, 80), outline=None)                # бар
        P.rect(-13, 10, -12, 15, fill=(150, 110, 80), outline=None)
        P.text(-17, 12.5, 'бар', 11, INK)
        for cx, cy in ((-48, 11), (-48, 3), (-40, 12)):                           # диваны
            P.rect(cx - 2.5, cy - 0.6, cx + 2.5, cy + 0.6, fill=(230, 220, 205), outline=MUTED)
            P.rect(cx - 2.5, cy - 3.2, cx + 2.5, cy - 2.0, fill=(230, 220, 205), outline=MUTED)
            P.rect(cx - 1.0, cy - 1.8, cx + 1.0, cy - 0.9, fill=(255, 255, 255), outline=MUTED)
        P.text(-44, 6.8, 'зона отдыха', 11, INK)
        P.rect(-46, -4.35, -40, -3.65, fill=(200, 40, 40), outline=None)          # метка служебной двери
    for k in range(1, 15):                                                         # марши служебной лестницы
        yy = -20 + k * 0.66
        P.line([(-53.6, yy), (-50.2, yy)], fill=MUTED)
        P.line([(-49.8, yy), (-46.4, yy)], fill=MUTED)
    P.labels(ROOMS[f], NUM[f], at={'LOB': (-32, 4)} if f == 1 else {'GLR': (-32, -2)})
    d.text((30 + i * (PW + 60), 100 + PH + 6), f'{f} этаж', font=font(16, True), fill=INK)

# разрез с юга на север по x = −32
SY = 100 + PH + 40
d.text((30, SY), 'Разрез с юга на север по оси лобби', font=font(14, True), fill=INK)
SS = 10.5
base = SY + 250


def S(y, z):
    return (40 + (y + 28) * SS, base - z * SS)


d.rectangle([S(-28, 0), S(24, -1.5)], fill=(214, 206, 186))
d.line([S(-28, 0), S(24, 0)], fill=INK, width=2)
z1, z2 = 4.5, 8.5
d.rectangle([S(-20, z1), S(0, z1 - 0.3)], fill=(170, 170, 168))                # перекрытие: служебные и галерея
d.rectangle([S(-20, z2 + 0.4), S(16, z2)], fill=(70, 72, 78))                  # кровля
d.rectangle([S(-20.3, z2), S(-19.7, 0)], fill=(120, 120, 124))
d.rectangle([S(15.8, z2), S(16.2, 0)], fill=(150, 196, 230))                   # панорамное остекление
d.rectangle([S(-4.2, z2), S(-3.8, 0)], fill=(120, 120, 124))
d.line([S(0, z1), S(0, z1 + 1.1)], fill=kit.GLASS, width=3)
d.text(S(-12, 2.2), 'служебные', font=font(12), fill=INK, anchor='mm')
d.text(S(-12, 6.4), 'администрация', font=font(12), fill=INK, anchor='mm')
d.text(S(-2, 6.0), 'галерея', font=font(11), fill=INK, anchor='mm')
d.text(S(7, 4.2), 'лобби в два света, 8,5 м', font=font(13, True), fill=INK, anchor='mm')
d.text(S(18.5, 6.8), 'панорама', font=font(11), fill=MUTED, anchor='lm')
d.text(S(-24, 1.2), 'парк', font=font(11), fill=MUTED, anchor='mm')
for z, lab in ((0, '±0'), (4.5, '+4,5'), (8.9, '+8,9 кровля')):
    d.line([S(17, z), S(18, z)], fill=MUTED)
    d.text(S(18.3, z + 0.6), lab, font=font(11), fill=MUTED, anchor='lm')

sx = 30 + PW + 60
yy = SY
for f in (1, 2):
    yy, _ = kit.schedule(d, ROOMS[f], NUM[f], sx, yy, f'Помещения {f} этажа', name_w=440)
    yy += 2
info = ['Из лобби в служебную часть — только служебная дверь тамбура (красная метка); лестница на 2 этаж —',
        'в служебной части с краю. На ключ: кабинет директора, касса с сейфом, архив.',
        'Проверка: ' + ('помещения не пересекаются, двери по общим стенам, всё достижимо' if not PROBLEMS
                        else f'{len(PROBLEMS)} замечаний')]
for s in info:
    d.text((sx, yy), s, font=font(12), fill=INK)
    yy += 17
if yy + 20 > H:
    big = Image.new('RGB', (W, yy + 20), kit.PAPER)
    big.paste(img, (0, 0))
    img = big
img.save(OUT)

DATA.parent.mkdir(parents=True, exist_ok=True)


def shift_wall(w):
    o, c, a, b = w
    if o == 'v':
        return [o, round(c + SITE_SHIFT[0], 3), round(a + SITE_SHIFT[1], 3), round(b + SITE_SHIFT[1], 3)]
    return [o, round(c + SITE_SHIFT[1], 3), round(a + SITE_SHIFT[0], 3), round(b + SITE_SHIFT[0], 3)]


DATA.write_text(json.dumps({
    'version': 'v03', 'note': 'по решениям владельца; координаты схемы участка v11 (корпус сдвинут на (+4, +30) от листа v02), '
            'метры игры (правило E)', 'site_shift': list(SITE_SHIFT),
    'floor_to_floor': FLOOR_TO_FLOOR, 'vertical': ['STA'], 'staff_door': STAFF_DOOR,
    'floors': {str(f): {
        'rooms': [{'id': r[0], 'no': NUM[f].get(r[0]), 'name': r[1],
                   'rect': [r[2] + SITE_SHIFT[0], r[3] + SITE_SHIFT[1], r[4] + SITE_SHIFT[0], r[5] + SITE_SHIFT[1]], 'kind': r[6],
                   'flags': r[7].split(), 'area': round((r[4] - r[2]) * (r[5] - r[3]), 1)} for r in ROOMS[f]],
        'doors': [{'a': x[0], 'b': x[1], 'width': x[3], 'locked': (x[0], x[1]) in LOCKED,
                   'wall': shift_wall(kit.door_geom(BY[f], x))} for x in DOORS[f]]} for f in ROOMS},
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')

for p in PROBLEMS:
    print('ЗАМЕЧАНИЕ:', p)
print(f'главный корпус v03: помещений {sum(1 for f in ROOMS for r in ROOMS[f] if r[6] != "void")}, '
      f'дверей {sum(len(DOORS[f]) for f in ROOMS)}, замечаний {len(PROBLEMS)}')
