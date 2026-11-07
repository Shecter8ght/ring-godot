# -*- coding: utf-8 -*-
"""Санаторий — здание «Ресторан и спа» v01: план, адресные данные помещений и дверей, проверка связей.

Решение владельца 2026-11-07: главный корпус — отдельное строение; другое отдельное строение — ресторан, спа-центр
и центр физнагрузок и процедур, всё в одном. Спа одноэтажный: вестибюль с ресепшеном → раздевалки мужская и
женская → душевые → общий холл к крытому бассейну; у бассейна разные небольшие сауны и хамамы на 6–7 человек,
лежаки, сам бассейн; из него переход в открытый бассейн на улице, вокруг него тоже лежаки; кроме бассейна —
спортзал и лечебные физпроцедуры, как принято. Остальное — предложение агента (docs/design/sanatorium_spa_restaurant.md).

Координаты — схемы участка (tools/sanatorium_map_plan.py), метры игры: помещения и проходы × 1,3 (правило E),
мебель, лежаки, чаши бассейнов 25 × 12,5 и 20 × 12,5 м — 1:1. Здание к югу от главного корпуса, у бровки склона.

    python -X utf8 tools/sanatorium_spa_plan.py
        → docs/plans/sanatorium_spa_restaurant_v01.png, docs/design/data/sanatorium_spa_restaurant_v01.json
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

import sanatorium_plan_kit as kit
from sanatorium_plan_kit import DOOR, DOOR2, OPEN, INK, MUTED, font

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_spa_restaurant_v01.png'
DATA = ROOT / 'docs/design/data/sanatorium_spa_restaurant_v01.json'

POOL_IN = (-79.0, -77.5, -54.0, -65.0)          # крытая чаша 25 × 12,5
POOL_OUT = (-108.0, -77.5, -88.0, -65.0)        # открытая чаша 20 × 12,5, переливной край — на запад, к озеру
CHANNEL = (-88.0, -72.75, -79.0, -69.75)        # проплыв из крытой чаши в открытую под завесой в стеклянной стене
PODIUM = (-112.0, -92.0, -84.0, -52.0)          # подиум открытого бассейна над склоном
TERRACE = (-104.0, -50.0, -84.0, -32.0)         # терраса ресторана

ROOMS = [
    # ресторан и кухня (север)
    ('REST', 'Ресторан, зал на ≈ 120 мест', -84, -56, -56, -32, 'pub', ''),
    ('RWC', 'Санузлы ресторана', -56, -40, -50, -32, 'wc', ''),
    ('SRV', 'Раздача и бар', -56, -56, -50, -40, 'serv', 'loot'),
    ('HOT', 'Горячий цех', -50, -44, -34, -32, 'serv', ''),
    ('PRP', 'Заготовочная', -50, -56, -34, -44, 'serv', ''),
    ('WSH', 'Моечная', -34, -44, -24, -32, 'serv', ''),
    ('KST', 'Бытовые кухни', -34, -56, -24, -44, 'serv', 'loot'),
    ('DRY', 'Сухой склад', -24, -44, -16, -32, 'store', 'loot'),
    ('CLD', 'Холодильная камера', -24, -56, -16, -44, 'store', 'loot'),
    ('DCK', 'Приёмка (рампа)', -16, -46, 0, -32, 'serv', ''),
    ('GRD', 'Пост охраны, служебный вход', -16, -56, 0, -46, 'serv', 'loot'),
    # спа: по порядку владельца — вестибюль → раздевалки → душевые → общий холл → бассейн
    ('VST', 'Вестибюль и ресепшен спа', -16, -80, 0, -56, 'pub', 'loot'),
    ('CHM', 'Раздевалка мужская', -28, -68, -16, -56, 'wc', ''),
    ('CHF', 'Раздевалка женская', -28, -80, -16, -68, 'wc', ''),
    ('SHM', 'Душевые мужские', -36, -68, -28, -56, 'wet', ''),
    ('SHF', 'Душевые женские', -36, -80, -28, -68, 'wet', ''),
    ('HAL', 'Общий холл бассейна', -44, -80, -36, -56, 'wet', ''),
    ('POOL', 'Крытый бассейн 25 м, лежаки', -84, -86, -44, -56, 'wet', ''),
    ('B1', 'Финская сауна, 6–7 чел.', -84, -92, -79, -86, 'bath', ''),
    ('B2', 'Русская парная, 6–7 чел.', -79, -92, -74, -86, 'bath', ''),
    ('B3', 'Био-сауна с травами, 6–7 чел.', -74, -92, -69, -86, 'bath', ''),
    ('B4', 'Инфракрасная сауна, 6–7 чел.', -69, -92, -64, -86, 'bath', ''),
    ('KUP', 'Купель и ледяной фонтан', -64, -92, -58, -86, 'wet', ''),
    ('B5', 'Турецкий хамам, 6–7 чел.', -58, -92, -51, -86, 'bath', ''),
    ('B6', 'Хамам с паром трав, 6–7 чел.', -51, -92, -44, -86, 'bath', ''),
    ('TCH', 'Техника бассейнов: насосы, фильтры, хлор', -84, -100, -44, -92, 'tech', 'loot'),
    # центр физнагрузок и процедур (юго-восток)
    ('PEN', 'Вход в лечебный центр, ожидание', -16, -86.9, 0, -80, 'pub', ''),
    ('PDC', 'Врач-физиотерапевт', -44, -86.9, -37, -80, 'med', 'loot'),
    ('PPH', 'Физиокабинеты: магнит, электро, свет', -37, -86.9, -30, -80, 'med', 'loot'),
    ('PM1', 'Массажный кабинет', -30, -86.9, -23, -80, 'med', ''),
    ('PM2', 'Массажный кабинет', -23, -86.9, -16, -80, 'med', ''),
    ('PCR', 'Коридор процедур', -44, -90, 0, -86.9, 'corr', ''),
    ('PHY', 'Водолечебница: душ Шарко, циркулярный, ванны', -44, -110, -32, -90, 'wet', ''),
    ('PIN', 'Ингаляторий', -32, -100, -24, -90, 'med', 'loot'),
    ('PSL', 'Соляная пещера', -32, -110, -24, -100, 'med', ''),
    ('STU', 'Зал ЛФК и групповых занятий', -24, -110, -14, -90, 'sport', ''),
    ('GYM', 'Тренажёрный зал', -14, -110, 0, -90, 'sport', ''),
]

DOORS = [
    ('REST', 'out', ('N', 0.3), DOOR2), ('REST', 'out', ('N', 0.75), DOOR2), ('REST', 'out', ('W', 0.6), DOOR2),
    ('REST', 'RWC', 0.5, DOOR), ('REST', 'SRV', 0.5, DOOR2), ('REST', 'POOL', 0.5, DOOR2),
    ('SRV', 'HOT', 0.5, DOOR), ('SRV', 'PRP', 0.5, DOOR), ('HOT', 'PRP', 0.5, DOOR2), ('HOT', 'WSH', 0.5, DOOR),
    ('PRP', 'KST', 0.5, DOOR), ('WSH', 'KST', 0.5, DOOR), ('WSH', 'DRY', 0.5, DOOR), ('KST', 'CLD', 0.5, DOOR),
    ('DRY', 'CLD', 0.5, DOOR), ('DRY', 'DCK', 0.5, DOOR2), ('CLD', 'DCK', 0.5, DOOR), ('GRD', 'DCK', 0.5, DOOR),
    ('GRD', 'out', ('E', 0.5), DOOR), ('DCK', 'out', ('E', 0.5), 3.5), ('GRD', 'VST', 0.5, DOOR),
    ('VST', 'out', ('E', 0.5), 3.0), ('VST', 'CHM', 0.5, DOOR), ('VST', 'CHF', 0.5, DOOR), ('VST', 'PEN', 0.5, DOOR2),
    ('CHM', 'SHM', 0.5, DOOR), ('CHF', 'SHF', 0.5, DOOR), ('SHM', 'HAL', 0.5, DOOR2), ('SHF', 'HAL', 0.5, DOOR2),
    ('HAL', 'POOL', 0.5, 10.0),
    ('POOL', 'B1', 0.5, DOOR), ('POOL', 'B2', 0.5, DOOR), ('POOL', 'B3', 0.5, DOOR), ('POOL', 'B4', 0.5, DOOR),
    ('POOL', 'KUP', 0.5, 3.0), ('POOL', 'B5', 0.5, DOOR), ('POOL', 'B6', 0.5, DOOR),
    ('POOL', 'out', ('W', 0.25), DOOR2), ('POOL', 'out', ('W', 0.85), DOOR2),
    ('KUP', 'TCH', 0.5, DOOR), ('TCH', 'out', ('S', 0.5), DOOR2),
    ('PEN', 'PCR', 0.5, DOOR2), ('PCR', 'PDC', 0.5, DOOR), ('PCR', 'PPH', 0.5, DOOR), ('PCR', 'PM1', 0.5, DOOR),
    ('PCR', 'PM2', 0.5, DOOR), ('PCR', 'PHY', 0.5, DOOR2), ('PCR', 'PIN', 0.5, DOOR), ('PIN', 'PSL', 0.5, DOOR),
    ('PCR', 'STU', 0.5, DOOR2), ('PCR', 'GYM', 0.5, DOOR2), ('GYM', 'out', ('E', 0.5), DOOR2),
]
LOCKED = set()

PROBLEMS, BY_ID = kit.check_floor(ROOMS, DOORS, LOCKED)
NUM = {r[0]: f'{k + 1:02d}' for k, r in enumerate(ROOMS)}

# ----------------------------------------------------------------------------- рисунок
XMIN, XMAX, YMIN, YMAX = -118.0, 6.0, -116.0, -26.0
SC = 8.0
W = int((XMAX - XMIN) * SC) + 60 + 600
H = max(int((YMAX - YMIN) * SC) + 170, 1080)
img = Image.new('RGB', (W, H), kit.PAPER)
d = ImageDraw.Draw(img)
P = kit.Plan(d, 30, 100, XMIN, YMAX, SC)

d.text((30, 18), 'Санаторий · здание «Ресторан и спа» v01 — одноэтажное: ресторан, спа с бассейнами, центр физнагрузок и процедур',
       font=font(21, True), fill=INK)
d.text((30, 52), 'спа — по схеме владельца: вестибюль с ресепшеном → раздевалки → душевые → общий холл → крытый бассейн с саунами и хамамами'
       ' → открытый бассейн', font=font(14), fill=MUTED)
d.text((30, 72), 'потолок: ресторан 4,5 м, зал бассейна 7 м, остальное 3,6 м · координаты схемы участка, метры игры · остальное — предложение',
       font=font(13), fill=MUTED)

# окружение: плато, бровка, подиум, терраса, проезд к рампе, дорожка к входу
P.rect(XMIN, YMIN, XMAX, YMAX, fill=(226, 230, 214), outline=None)
P.poly([(XMIN, YMIN), (-112, YMIN), (-112, YMAX), (XMIN, YMAX)], fill=(176, 190, 150), outline=None)
P.text(-115, -30, 'склон', 12, MUTED, False, 'lm')
P.rect(*PODIUM, fill=(232, 226, 210), outline=MUTED)
P.rect(*POOL_OUT, fill=(110, 192, 220), outline=INK, width=2)
P.line([(POOL_OUT[0], POOL_OUT[1]), (POOL_OUT[0], POOL_OUT[3])], fill=(40, 90, 140), width=5)    # переливной край
P.text(-110.5, -71, 'перелив', 10, MUTED, False, 'mm')
P.rect(*CHANNEL, fill=(110, 192, 220), outline=None)
for k in range(8):                                                  # лежаки у открытого бассейна
    P.rect(-110 + k * 3.0, -61.5, -109.3 + k * 3.0, -59.5, fill=(255, 255, 255), outline=MUTED)
    P.rect(-110 + k * 3.0, -84, -109.3 + k * 3.0, -82, fill=(255, 255, 255), outline=MUTED)
for k in range(3):
    P.circle(-104 + k * 8, -56.5, 1.4, fill=(240, 200, 120), outline=MUTED)                      # зонты
    P.circle(-104 + k * 8, -88, 1.4, fill=(240, 200, 120), outline=MUTED)
P.rect(*TERRACE, fill=(222, 206, 176), outline=MUTED)
for ix in range(3):
    for iy in range(3):
        P.circle(-99 + ix * 6, -46 + iy * 5.5, 0.9, fill=(255, 255, 255), outline=MUTED)
P.text(-94, -34, 'терраса ресторана', 11, MUTED)
P.rect(0, -46, 6, -32, fill=(190, 190, 186), outline=None)         # подъезд к рампе
P.text(3, -29, 'к площади', 10, MUTED)
P.rect(0, -70, 6, -66, fill=(218, 210, 196), outline=None)         # дорожка к главному входу
P.text(-70, -29, 'к главному корпусу ↑', 11, MUTED)

P.rooms(ROOMS, BY_ID, DOORS, NUM, LOCKED)

# оборудование и мебель
P.rect(*POOL_IN, fill=(110, 192, 220), outline=INK, width=2)
for k in range(1, 5):
    P.line([(POOL_IN[0], POOL_IN[1] + k * 2.5), (POOL_IN[2], POOL_IN[1] + k * 2.5)], fill=(70, 150, 190))
P.line([(-84, CHANNEL[1] - 0.3), (-84, CHANNEL[3] + 0.3)], fill=(240, 240, 240), width=3)       # завеса проплыва
for k in range(9):                                                  # лежаки у крытого бассейна
    P.rect(-79 + k * 2.8, -63.5, -78.3 + k * 2.8, -61.5, fill=(255, 255, 255), outline=MUTED)
    P.rect(-79 + k * 2.8, -84, -78.3 + k * 2.8, -82, fill=(255, 255, 255), outline=MUTED)
for k in range(3):
    P.rect(-51 + k * 2.3, -77, -50.3 + k * 2.3, -75, fill=(255, 255, 255), outline=MUTED)
for x0 in (-84, -79, -74, -69):                                     # полки саун
    P.rect(x0 + 0.6, -91.4, x0 + 4.4, -90.6, fill=(196, 150, 110), outline=None)
    P.rect(x0 + 0.6, -91.4, x0 + 1.4, -87.5, fill=(196, 150, 110), outline=None)
for x0, x1 in ((-58, -51), (-51, -44)):                             # хамам: лежанка-камень посередине
    P.circle((x0 + x1) / 2, -89, 1.6, fill=(230, 230, 230), outline=MUTED)
P.circle(-61, -89.5, 1.4, fill=(150, 210, 230), outline=INK)       # купель
P.rect(-25, -55.2, -17, -54.5, fill=(200, 200, 205), outline=None)
for ix in range(4):                                                 # столы ресторана
    for iy in range(4):
        P.rect(-81 + ix * 6.5, -52.5 + iy * 5.2, -78.8 + ix * 6.5, -50.9 + iy * 5.2, fill=(255, 255, 255), outline=MUTED)
P.rect(-55.5, -55, -54.5, -41, fill=(210, 200, 180), outline=None)  # стойка раздачи
P.rect(-49.5, -42, -46.5, -34, fill=(200, 200, 205), outline=None)  # плиты
for k in range(4):                                                  # тренажёры
    P.rect(-12.5 + k * 3.2, -107, -10.8 + k * 3.2, -103.5, fill=(150, 150, 156), outline=None)
    P.rect(-12.5 + k * 3.2, -99, -10.8 + k * 3.2, -95.5, fill=(150, 150, 156), outline=None)
for k in range(3):                                                  # маты ЛФК
    P.rect(-23 + k * 3.0, -106, -21 + k * 3.0, -94, fill=(170, 200, 150), outline=None)
for k in range(3):                                                  # ванны водолечебницы и душ Шарко
    P.rect(-43 + k * 3.6, -107.5, -41.4 + k * 3.6, -104.5, fill=(150, 210, 230), outline=MUTED)
P.circle(-37, -95, 1.5, fill=(150, 210, 230), outline=MUTED)
for k in range(5):                                                  # кресла ингалятория
    P.rect(-31 + k * 1.4, -98.5, -30.2 + k * 1.4, -97.5, fill=(255, 255, 255), outline=MUTED)
P.rect(-15, -79, -10, -77.8, fill=(210, 200, 180), outline=None)    # стойка ресепшена

P.labels(ROOMS, NUM, at={'POOL': (-49, -60), 'REST': (-70, -34.5)})
# масштаб, север
bx, by = P.p(-116, -113)
d.line([(bx, by), (bx + 20 * SC, by)], fill=INK, width=3)
d.text((bx + 10 * SC, by - 10), '20 м', font=font(12), fill=INK, anchor='mm')
P.text(2, -113, 'С ↑', 14, INK, True)

sx = 30 + int((XMAX - XMIN) * SC) + 30
yy, total = kit.schedule(d, ROOMS, NUM, sx, 100, 'Помещения', name_w=470)
yy = kit.legend(d, sx, yy + 4, ['pub', 'wet', 'bath', 'wc', 'sport', 'med', 'serv', 'store', 'tech', 'corr'])
for s in ([f'Проверка: помещения не пересекаются, двери по общим стенам, всё достижимо от входов ({len(DOORS)} дверей, '
           f'{sum(1 for x in DOORS if x[1] == "out")} наружных)'] if not PROBLEMS else [f'Проверка: {len(PROBLEMS)} замечаний']):
    d.text((sx, yy + 4), s, font=font(12), fill=INK)

img.save(OUT)

DATA.parent.mkdir(parents=True, exist_ok=True)
DATA.write_text(json.dumps({
    'version': 'v01', 'note': 'предложение агента по схеме владельца; координаты схемы участка, метры игры (правило E)',
    'pool_indoor': POOL_IN, 'pool_outdoor': POOL_OUT, 'swim_channel': CHANNEL, 'podium': PODIUM, 'terrace': TERRACE,
    'rooms': [{'id': r[0], 'no': NUM[r[0]], 'name': r[1], 'rect': [r[2], r[3], r[4], r[5]], 'kind': r[6],
               'flags': r[7].split(), 'area': round((r[4] - r[2]) * (r[5] - r[3]), 1)} for r in ROOMS],
    'doors': [{'a': x[0], 'b': x[1], 'width': x[3], 'wall': list(kit.door_geom(BY_ID, x))} for x in DOORS],
}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')

for p in PROBLEMS:
    print('ЗАМЕЧАНИЕ:', p)
print(f'ресторан и спа: помещений {len(ROOMS)}, дверей {len(DOORS)}, площадь ≈ {total:.0f} м², замечаний {len(PROBLEMS)}')
