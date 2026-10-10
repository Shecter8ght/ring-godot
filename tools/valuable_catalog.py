"""Цены из Balance, каталог 100 ценных находок и четыре листа игровых иконок."""
import json
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
items = json.loads((ROOT/'data/items.json').read_text(encoding='utf8'))['items']
assets = json.loads((ROOT/'data/valuable_loot_assets.json').read_text(encoding='utf8'))
balance = (ROOT/'src/core/balance.gd').read_text(encoding='utf8')
values = json.loads(re.search(r'const VALUABLE_LOOT_VALUES := (\{.*?\})',balance,re.S)[1])
sell = float(re.search(r'const TRADER_SELL_MULT := ([\d.]+)',balance)[1])
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
head = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 23)
groups = {'electronics':'Электроника','parts':'Оружейные детали','medical':'Медицина','vehicle':'Автомастерская','food':'Снабжение','ammo':'Боеприпасы','signal':'Сигнал снабжения'}
doc = ['# Сто ценных находок', '',
    '100 новых предметов в дополнение к 24 гражданским находкам: 24 электронных прибора/компонента, 16 оружейных деталей/наборов, 16 медицинских предметов, 12 автозапчастей/инструментов, 12 продовольственных партий, 18 упаковок боеприпасов и расходников, сигнальный пистолет и его патрон.', '',
    'Каждый имеет цену, описание, вес, клетки рюкзака, иконку и физическую модель. 65 предметов представлены закрытыми маркированными упаковками; их содержимое отдельно не моделировалось, варианты используют общую готовую геометрию упаковки. Остальные — приборы, инструменты, продовольственная тара и детали проверенных моделей оружия. Это 100 записей предметов, а не 100 уникальных сеток.', '',
    'Дорогие находки добавляются отдельным тематическим броском в обычный лут. Редкость и стоимость — `Balance.VALUABLE_LOOT_VALUES`, `VALUABLE_LOOT`, `VALUABLE_LOOT_CHANCE`. Отдельные 3D-находки используют те же темы; выносятся, сохраняются и продаются как остальные вещи.', '',
    'Медицинское оборудование/препараты, электроника, автозапчасти, ремонтные оружейные детали и продовольствие здесь — бартер. Новые медицинские эффекты, голод, ремонт автомобилей и установка внутренних деталей оружия не введены.', '',
    '## Действия', '',
    '- Пачки патронов, комплект гранат, ракет и химсвета: «Вскрыть упаковку» в меню рюкзака или тайника. Выдают реальные игровые расходники; найденное в рейде сохраняет отметку FIR. Проверка и изменение сетки атомарные.',
    '- Сигнальный пистолет: «Вызвать самолёт снабжения» в меню рюкзака или двойной клик. Требует отдельного патрона снабжения. Обычная осветительная ракета не подходит.',
    '- Под крышей, возле препятствий, без боеприпаса, после эвакуации или при повторном вызове предмет не расходуется. Один самолёт на общий рейд. Пистолет остаётся у игрока.',
    '- Примерно через 45 с самолёт проходит над площадкой на высоте 170 м. Ящик снижается 8 с; внутри 4–6 разных предметов с оценкой от 28 000 ₽. Патронов повторного вызова в нём нет. Шум слышат NPC; груз доступен всей группе.', '',
    '## Каталог и цена продажи', '',
    'Продажа Михалычу — 55 % от оценки (`TRADER_SELL_MULT`). Значения — начальный баланс, не реальные рыночные цены.', '',
    '| № | Предмет | Группа | Оценка, ₽ | Продажа, ₽ | кг | Клетки |',
    '|---:|---|---|---:|---:|---:|---|']
for index, (id, spec) in enumerate(assets.items()):
    if index % 25 == 0:
        canvas = Image.new('RGB',(1500,1320),(25,30,33)); draw = ImageDraw.Draw(canvas)
        draw.text((28,15),f'RING — ценные находки {index+1}–{min(index+25,100)}',font=head,fill=(233,227,212))
    image = Image.open(ROOT/'assets/icons'/f'{id}.png').convert('RGBA'); image.thumbnail((245,175))
    tile = index % 25; x,y = 24 + tile%5*295, 55 + tile//5*248
    canvas.paste(image,(x+(275-image.width)//2,y+(180-image.height)//2),image)
    draw.multiline_text((x+5,y+180),'\n'.join(textwrap.wrap(items[id]['name'],30)),font=font,fill=(230,227,214))
    draw.text((x+5,y+224),f'{int(values[id]*sell):,} ₽'.replace(',',' '),font=font,fill=(209,170,85))
    it = items[id]
    doc.append(f"| {index+1} | {it['name']} | {groups[spec['group']]} | {values[id]} | {int(values[id]*sell)} | {it['weight']} | {it['size'][0]}×{it['size'][1]} |")
    if tile == 24: canvas.save(ROOT/'docs/screens'/f'valuable_loot_{index//25+1}.png')
doc += ['', '## Проверка', '',
    '`valuable_loot_test` проверяет все 100 записей/ассетов, достижимость в луте, количество при вскрытии, сохранение FIR, отказ под крышей и единственный сброс. `loot_net_test` проверяет настоящую пару ENet, подбор и вынос. Сигнал и пачки — `valuable_loot_net_test`.', '',
    'Сборка: `build_valuable_loot.py`, `valuable_labels.py`, `build_supply_aircraft.py`; иконки — `icon_bake.tscn`; источники и лицензии — `assets/CREDITS.md`. Фото-ассеты Poly Haven/телефон CC0, самолёт и ракетница CC0, звук самолёта CC BY 3.0.', '']
(ROOT/'docs/design/valuable_loot.md').write_text('\n'.join(doc),encoding='utf8')
