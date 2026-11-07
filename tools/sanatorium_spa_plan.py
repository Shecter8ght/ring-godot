# -*- coding: utf-8 -*-
"""Санаторий — здание «Ресторан и спа» v02: план, адресные данные помещений и дверей, проверка связей.

Решения владельца 2026-11-07 (docs/design/sanatorium_spa_restaurant.md, §1):
- одно отдельное одноэтажное строение — ресторан, спа и центр физнагрузок и процедур;
- один общий вход с вестибюлем и ресепшеном, от него коридор, из которого три места: бассейн, тренажёрный зал
  с помещениями процедур, ресторан; эти три зоны не касаются друг друга общими стенами;
- в спа: раздевалки мужская и женская → душевые → общий холл к крытому бассейну; у бассейна небольшие сауны
  и хамамы на 6–7 человек, лежаки; из бассейна переход в открытый на улице, вокруг него тоже лежаки;
- из ресторана можно выйти на улицу, но войти там нельзя; есть и отдельный гостевой вход с улицы — не сразу к столам,
  а через коридор с гардеробом; служебный вход кухни — сверх того (предложение агента).
Остальное — предложение агента; приёмы «Бухты Коприно» — зона тишины с баром у бассейна, римская баня в наборе.

Координаты — схемы участка (tools/sanatorium_map_plan.py), метры игры: помещения и проходы × 1,3 (правило E),
мебель, лежаки и чаши 25 × 12,5 и 20 × 12,5 м — 1:1.

    python -X utf8 tools/sanatorium_spa_plan.py
        → docs/plans/sanatorium_spa_restaurant_v02.png, docs/design/data/sanatorium_spa_restaurant_v02.json
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import DOOR, DOOR2, INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_spa_restaurant_v02.png'
DATA = ROOT / 'docs/design/data/sanatorium_spa_restaurant_v02.json'

POOL_IN = (-90.0, -88.0, -65.0, -75.5)          # крытая чаша 25 × 12,5
POOL_OUT = (-120.0, -88.0, -100.0, -75.5)       # открытая чаша 20 × 12,5, перелив на запад, к озеру
CHANNEL = (-100.0, -83.25, -90.0, -80.25)       # проплыв из крытой чаши в открытую под завесой в стеклянной стене
PODIUM = (-124.0, -102.0, -96.0, -66.0)         # подиум открытого бассейна над склоном
TERRACE = (-112.0, -48.0, -96.0, -30.0)         # терраса ресторана над склоном — только выход
YARD = (-24.0, -48.0, -8.0, -30.0)              # хозяйственный двор кухни

ZONES = {  # три зоны, которые не должны касаться друг друга (решение владельца)
    'ресторан': ['RCOR', 'RCLK', 'REST', 'LNG', 'RWC', 'SRV', 'HOT', 'PRP', 'WSH', 'KST', 'DRY', 'CLD', 'SEN'],
    'бассейн': ['SEN2', 'CHM', 'CHF', 'SHM', 'SHF', 'HAL', 'POOL', 'RLX', 'B1', 'B2', 'B3', 'B4', 'KUP', 'B5', 'B6', 'TCH'],
    'фитнес и процедуры': ['PEN', 'PCR', 'PDC', 'PPH', 'PM1', 'PM2', 'PIN', 'PSL', 'GYM', 'STU', 'PHY'],
}

ROOMS = [
    # общий вход и коридор к трём зонам
    ('VST', 'Вестибюль, длинный ресепшен', -6, -60, 12, -42, 'pub', 'loot'),
    ('GAL', 'Коридор к трём зонам (стекло во дворики)', -70, -56, -6, -52, 'corr', ''),
    ('LR', 'Переход в ресторан', -70, -52, -66, -48, 'corr', ''),
    ('LP', 'Переход в бассейн', -58, -60, -54, -56, 'corr', ''),
    ('LG', 'Переход в фитнес и процедуры', -24, -60, -20, -56, 'corr', ''),
    # ресторан (север, вид на озеро); гостевой вход с улицы — через коридор с гардеробом (владелец)
    ('RCOR', 'Входной коридор ресторана', -88, -30, -84, -20, 'corr', ''),
    ('RCLK', 'Гардероб ресторана', -84, -30, -76, -20, 'pub', 'loot'),
    ('REST', 'Ресторан, зал на ≈ 100 мест', -88, -48, -62, -30, 'pub', ''),
    ('LNG', 'Лаунж с панорамой на озеро', -96, -40, -88, -30, 'pub', ''),
    ('RWC', 'Санузлы ресторана', -96, -48, -88, -40, 'wc', ''),
    ('SRV', 'Раздача и бар', -62, -48, -58, -30, 'serv', 'loot'),
    ('HOT', 'Горячий цех', -58, -39, -44, -30, 'serv', ''),
    ('PRP', 'Заготовочная', -58, -48, -44, -39, 'serv', ''),
    ('WSH', 'Моечная', -44, -39, -36, -30, 'serv', ''),
    ('KST', 'Бытовые кухни', -44, -48, -36, -39, 'serv', 'loot'),
    ('DRY', 'Сухой склад', -36, -39, -30, -30, 'store', 'loot'),
    ('CLD', 'Холодильная камера', -36, -48, -30, -39, 'store', 'loot'),
    ('SEN', 'Служебный вход кухни, пост', -30, -48, -24, -30, 'serv', 'loot'),
    # бассейн (юго-запад)
    ('SEN2', 'Вход в бассейн: турникет, ключи, полотенца', -60, -66, -44, -60, 'pub', ''),
    ('CHM', 'Раздевалка мужская', -60, -78, -52, -66, 'wc', ''),
    ('CHF', 'Раздевалка женская', -52, -78, -44, -66, 'wc', ''),
    ('SHM', 'Душевые мужские', -60, -86, -52, -78, 'wet', ''),
    ('SHF', 'Душевые женские', -52, -86, -44, -78, 'wet', ''),
    ('HAL', 'Общий холл бассейна', -60, -102, -44, -86, 'wet', ''),
    ('POOL', 'Крытый бассейн 25 м, лежаки', -96, -96, -60, -66, 'wet', ''),
    ('RLX', 'Зона тишины и спа-бар', -96, -102, -60, -96, 'wet', 'loot'),
    ('B1', 'Финская сауна, 6–7 чел.', -96, -66, -91, -60, 'bath', ''),
    ('B2', 'Русская парная, 6–7 чел.', -91, -66, -86, -60, 'bath', ''),
    ('B3', 'Римская баня, 6–7 чел.', -86, -66, -81, -60, 'bath', ''),
    ('B4', 'Био-сауна с травами, 6–7 чел.', -81, -66, -76, -60, 'bath', ''),
    ('KUP', 'Купель и ледяной фонтан', -76, -66, -71, -60, 'wet', ''),
    ('B5', 'Турецкий хамам, 6–7 чел.', -71, -66, -65.5, -60, 'bath', ''),
    ('B6', 'Хамам с паром трав, 6–7 чел.', -65.5, -66, -60, -60, 'bath', ''),
    ('TCH', 'Техника бассейнов: насосы, фильтры, хлор', -60, -108, -44, -102, 'tech', 'loot'),
    # фитнес и процедуры (юго-восток)
    ('PEN', 'Ресепшен фитнеса и процедур', -38, -68, -6, -60, 'pub', ''),
    ('PCR', 'Коридор процедур', -23.55, -102, -20.45, -68, 'corr', ''),
    ('PDC', 'Врач-физиотерапевт', -38, -73, -23.55, -68, 'med', 'loot'),
    ('PPH', 'Физиокабинеты: магнит, электро, свет', -38, -79, -23.55, -73, 'med', 'loot'),
    ('PM1', 'Массажный кабинет', -38, -84, -23.55, -79, 'med', ''),
    ('PM2', 'Массажный кабинет', -38, -89, -23.55, -84, 'med', ''),
    ('PIN', 'Ингаляторий', -38, -95, -23.55, -89, 'med', 'loot'),
    ('PSL', 'Соляная пещера', -38, -102, -23.55, -95, 'med', ''),
    ('GYM', 'Тренажёрный зал', -20.45, -86, -6, -68, 'sport', ''),
    ('STU', 'Зал ЛФК и йоги', -20.45, -94, -6, -86, 'sport', ''),
    ('PHY', 'Водолечебница: душ Шарко, ванны', -20.45, -102, -6, -94, 'wet', ''),
]

DOORS = [
    ('VST', 'out', ('N', 0.5), 3.0), ('VST', 'GAL', 0.5, 3.0),
    ('GAL', 'LR', 0.5, 3.0), ('GAL', 'LP', 0.5, 3.0), ('GAL', 'LG', 0.5, 3.0),
    ('LR', 'REST', 0.5, DOOR2), ('LP', 'SEN2', 0.5, DOOR2), ('LG', 'PEN', 0.5, DOOR2),
    # ресторан: гостевой вход с улицы через коридор с гардеробом; выход на террасу — только наружу; служебный — на кухню
    ('RCOR', 'out', ('N', 0.5), DOOR2), ('RCOR', 'RCLK', 0.5, 4.0), ('RCOR', 'REST', 0.5, 3.0),
    ('REST', 'LNG', 0.5, 6.0), ('REST', 'RWC', 0.5, DOOR), ('LNG', 'exit', ('W', 0.5), DOOR2),
    ('REST', 'SRV', 0.5, DOOR2), ('SRV', 'HOT', 0.5, DOOR), ('SRV', 'PRP', 0.5, DOOR), ('HOT', 'PRP', 0.5, DOOR2),
    ('HOT', 'WSH', 0.5, DOOR), ('PRP', 'KST', 0.5, DOOR), ('WSH', 'KST', 0.5, DOOR), ('WSH', 'DRY', 0.5, DOOR),
    ('KST', 'CLD', 0.5, DOOR), ('DRY', 'CLD', 0.5, DOOR), ('DRY', 'SEN', 0.5, DOOR2), ('CLD', 'SEN', 0.5, DOOR),
    ('SEN', 'out', ('E', 0.5), DOOR2),
    # бассейн — по порядку владельца
    ('SEN2', 'CHM', 0.5, DOOR), ('SEN2', 'CHF', 0.5, DOOR), ('CHM', 'SHM', 0.5, DOOR), ('CHF', 'SHF', 0.5, DOOR),
    ('SHM', 'HAL', 0.5, DOOR2), ('SHF', 'HAL', 0.5, DOOR2), ('HAL', 'POOL', 0.5, 8.0), ('HAL', 'RLX', 0.5, 4.0),
    ('POOL', 'RLX', 0.5, 20.0),
    ('POOL', 'B1', 0.5, DOOR), ('POOL', 'B2', 0.5, DOOR), ('POOL', 'B3', 0.5, DOOR), ('POOL', 'B4', 0.5, DOOR),
    ('POOL', 'KUP', 0.5, 3.0), ('POOL', 'B5', 0.5, DOOR), ('POOL', 'B6', 0.5, DOOR),
    ('POOL', 'out', ('W', 0.25), DOOR2), ('POOL', 'out', ('W', 0.8), DOOR2),
    ('HAL', 'TCH', 0.5, DOOR), ('TCH', 'out', ('S', 0.5), DOOR2),
    # фитнес и процедуры
    ('PEN', 'PCR', 0.5, 3.1), ('PEN', 'GYM', 0.5, DOOR2),
    ('PCR', 'PDC', 0.5, DOOR), ('PCR', 'PPH', 0.5, DOOR), ('PCR', 'PM1', 0.5, DOOR), ('PCR', 'PM2', 0.5, DOOR),
    ('PCR', 'PIN', 0.5, DOOR), ('PCR', 'PSL', 0.5, DOOR), ('PCR', 'GYM', 0.5, DOOR2), ('PCR', 'STU', 0.5, DOOR2),
    ('PCR', 'PHY', 0.5, DOOR2), ('GYM', 'exit', ('E', 0.5), DOOR2),
]
LOCKED = set()

PROBLEMS, BY_ID = kit.check_floor(ROOMS, DOORS, LOCKED)
# три зоны не касаются друг друга ни стеной, ни углом-стеной
zone_of = {rid: z for z, ids in ZONES.items() for rid in ids}
for i, a in enumerate(ROOMS):
    for b in ROOMS[i + 1:]:
        za, zb = zone_of.get(a[0]), zone_of.get(b[0])
        if za and zb and za != zb and kit.shared_edge(kit.rect_of(a), kit.rect_of(b)):
            PROBLEMS.append(f'общая стена между зонами «{za}» и «{zb}»: {a[0]} — {b[0]}')
NUM = {r[0]: f'{k + 1:02d}' for k, r in enumerate(ROOMS)}

# ----------------------------------------------------------------------------- рисунок
XMIN, XMAX, YMIN, YMAX = -128.0, 16.0, -112.0, -14.0
SC = 7.6
W = int((XMAX - XMIN) * SC) + 60 + 600
H = max(int((YMAX - YMIN) * SC) + 170, 1190)
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
P = kit.Plan(d, 30, 100, XMIN, YMAX, SC)

d.text((30, 18), 'Санаторий · здание «Ресторан и спа» v02 — один общий вход, коридор, три отдельных крыла',
       font=font(21, True), fill=INK)
d.text((30, 52), 'вестибюль с ресепшеном → коридор → ресторан / бассейн / фитнес и процедуры; крылья разделены двориками — общих стен нет',
       font=font(14), fill=MUTED)
d.text((30, 72), 'одноэтажное · потолок: ресторан 4,5 м, зал бассейна 7 м, остальное 3,6 м · координаты схемы участка, метры игры',
       font=font(13), fill=MUTED)

P.rect(XMIN, YMIN, XMAX, YMAX, fill=(226, 230, 214), outline=None)
P.poly([(XMIN, YMIN), (-124, YMIN), (-124, YMAX), (XMIN, YMAX)], fill=(176, 190, 150), outline=None)
P.text(-127, -28, 'склон', 12, MUTED, False, 'lm')
for x0, y0, x1, y1 in ((-66, -60, -6, -56), (-70, -52, -24, -48), (-44, -108, -38, -60)):    # дворики между крыльями
    P.rect(x0, y0, x1, y1, fill=(200, 220, 184), outline=None)
P.text(-40, -50, 'дворик', 10, MUTED)
P.text(-41, -84, 'сад', 10, MUTED)
P.rect(*PODIUM, fill=(232, 226, 210), outline=MUTED)
P.rect(*POOL_OUT, fill=(110, 192, 220), outline=INK, width=2)
P.line([(POOL_OUT[0], POOL_OUT[1]), (POOL_OUT[0], POOL_OUT[3])], fill=(40, 90, 140), width=5)
P.text(-122, -70, 'перелив', 10, MUTED, False, 'mm')
P.rect(*CHANNEL, fill=(110, 192, 220), outline=None)
for k in range(8):
    P.rect(-121 + k * 2.8, -72, -120.3 + k * 2.8, -70, fill=(255, 255, 255), outline=MUTED)
    P.rect(-121 + k * 2.8, -98, -120.3 + k * 2.8, -96, fill=(255, 255, 255), outline=MUTED)
for k in range(3):
    P.circle(-116 + k * 7, -68.5, 1.3, fill=(240, 200, 120), outline=MUTED)
    P.circle(-116 + k * 7, -100, 1.3, fill=(240, 200, 120), outline=MUTED)
P.rect(*TERRACE, fill=(222, 206, 176), outline=MUTED)
for ix in range(2):
    for iy in range(3):
        P.circle(-108 + ix * 7, -44 + iy * 5.5, 0.9, fill=(255, 255, 255), outline=MUTED)
P.text(-104, -32, 'терраса', 10, MUTED)
P.rect(-90, -20, -82, -16, fill=(218, 210, 196), outline=None)       # дорожка к гостевому входу
P.text(-74, -18, 'гостевой вход с улицы', 10, MUTED, False, 'lm')
P.rect(*YARD, fill=(206, 204, 198), outline=MUTED)
P.text(-16, -39, 'хоздвор кухни', 10, MUTED)
P.rect(-24, -30, -12, -26, fill=(190, 190, 186), outline=None)
P.rect(1, -42, 5, -26, fill=(218, 210, 196), outline=None)
P.text(3, -28, 'от площади', 10, MUTED)

P.rooms(ROOMS, BY_ID, DOORS, NUM, LOCKED)

P.rect(*POOL_IN, fill=(110, 192, 220), outline=INK, width=2)
for k in range(1, 5):
    P.line([(POOL_IN[0], POOL_IN[1] + k * 2.5), (POOL_IN[2], POOL_IN[1] + k * 2.5)], fill=(70, 150, 190))
P.line([(-96, CHANNEL[1] - 0.3), (-96, CHANNEL[3] + 0.3)], fill=(240, 240, 240), width=3)
for k in range(9):
    P.rect(-90 + k * 2.8, -73.5, -89.3 + k * 2.8, -71.5, fill=(255, 255, 255), outline=MUTED)
    P.rect(-90 + k * 2.8, -94, -89.3 + k * 2.8, -92, fill=(255, 255, 255), outline=MUTED)
for k in range(8):                                                  # лежаки зоны тишины
    P.rect(-94 + k * 3.4, -101.5, -93.3 + k * 3.4, -99.5, fill=(255, 255, 255), outline=MUTED)
P.rect(-67, -101.5, -61.5, -100.5, fill=(210, 200, 180), outline=None)   # стойка спа-бара
for x0 in (-96, -91, -86, -81):
    P.rect(x0 + 0.6, -61.4, x0 + 4.4, -60.6, fill=(196, 150, 110), outline=None)
    P.rect(x0 + 0.6, -64.5, x0 + 1.4, -61.4, fill=(196, 150, 110), outline=None)
for x0, x1 in ((-71, -65.5), (-65.5, -60)):
    P.circle((x0 + x1) / 2, -63, 1.4, fill=(230, 230, 230), outline=MUTED)
P.circle(-73.5, -63, 1.3, fill=(150, 210, 230), outline=INK)
P.rect(0, -58.5, 10.5, -57.5, fill=(210, 200, 180), outline=None)  # длинный ресепшен
for ix in range(4):
    for iy in range(3):
        P.rect(-86 + ix * 6, -45 + iy * 5, -83.8 + ix * 6, -43.4 + iy * 5, fill=(255, 255, 255), outline=MUTED)
P.rect(-61.5, -47, -60.5, -31, fill=(210, 200, 180), outline=None)
P.rect(-57.5, -37, -54.5, -31, fill=(200, 200, 205), outline=None)
for k in range(4):
    P.rect(-19 + k * 3.2, -83, -17.3 + k * 3.2, -79.5, fill=(150, 150, 156), outline=None)
    P.rect(-19 + k * 3.2, -75, -17.3 + k * 3.2, -71.5, fill=(150, 150, 156), outline=None)
for k in range(3):
    P.rect(-19 + k * 4, -93, -16 + k * 4, -87, fill=(170, 200, 150), outline=None)
for k in range(3):
    P.rect(-19 + k * 3.8, -101, -17.4 + k * 3.8, -98, fill=(150, 210, 230), outline=MUTED)

P.labels(ROOMS, NUM, at={'POOL': (-62.5, -69), 'GAL': (-30, -54), 'REST': (-75, -32.5)})
P.rect(-83.5, -29, -82.8, -21, fill=(196, 170, 130), outline=None)   # стойка гардероба
for k in range(6):
    P.line([(-81.5, -28.5 + k * 1.4), (-77, -28.5 + k * 1.4)], fill=MUTED)   # вешалки
bx, by = P.p(-126, -110)
d.line([(bx, by), (bx + 20 * SC, by)], fill=INK, width=3)
d.text((bx + 10 * SC, by - 10), '20 м', font=font(12), fill=INK, anchor='mm')
P.text(12, -110, 'С ↑', 14, INK, True)

sx = 30 + int((XMAX - XMIN) * SC) + 30
yy, total = kit.schedule(d, ROOMS, NUM, sx, 100, 'Помещения', name_w=470)
yy = kit.legend(d, sx, yy + 4, ['pub', 'corr', 'wet', 'bath', 'wc', 'sport', 'med', 'serv', 'store', 'tech'])
msg = ('Проверка: помещения не пересекаются, двери по общим стенам, всё достижимо от входов,' if not PROBLEMS
       else f'Проверка: {len(PROBLEMS)} замечаний — см. вывод генератора')
d.text((sx, yy + 4), msg, font=font(12), fill=INK)
if not PROBLEMS:
    d.text((sx, yy + 22), 'у ресторана, бассейна и фитнеса нет общих стен', font=font(12), fill=INK)

img.save(OUT)

DATA.parent.mkdir(parents=True, exist_ok=True)
DATA.write_text(json.dumps({
    'version': 'v02', 'note': 'по схеме владельца; координаты схемы участка, метры игры (правило E)',
    'zones': ZONES, 'pool_indoor': POOL_IN, 'pool_outdoor': POOL_OUT, 'swim_channel': CHANNEL, 'podium': PODIUM,
    'terrace': TERRACE, 'yard': YARD,
    'rooms': [{'id': r[0], 'no': NUM[r[0]], 'name': r[1], 'rect': [r[2], r[3], r[4], r[5]], 'kind': r[6],
               'flags': r[7].split(), 'area': round((r[4] - r[2]) * (r[5] - r[3]), 1)} for r in ROOMS],
    'doors': [{'a': x[0], 'b': x[1], 'width': x[3], 'wall': list(kit.door_geom(BY_ID, x))} for x in DOORS],
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')

for p in PROBLEMS:
    print('ЗАМЕЧАНИЕ:', p)
print(f'ресторан и спа v02: помещений {len(ROOMS)}, дверей {len(DOORS)}, площадь ≈ {total:.0f} м², замечаний {len(PROBLEMS)}')
