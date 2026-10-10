"""Каталог новых находок и контактный лист игровых иконок: python tools/loot_catalog.py."""
import json
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
items = json.loads((ROOT / 'data/items.json').read_text(encoding='utf-8'))['items']
sources = json.loads((ROOT / 'assets/items/models/loot/manifest.json').read_text(encoding='utf-8'))
balance = (ROOT / 'src/core/balance.gd').read_text(encoding='utf-8')
values = json.loads(re.search(r'const CIVILIAN_LOOT_VALUES := (\{.*?\})', balance, re.S)[1])
sell = float(re.search(r'const TRADER_SELL_MULT := ([\d.]+)', balance)[1])
canvas = Image.new('RGB', (1500, 1100), (25, 30, 33))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 17)
draw.text((28, 14), 'RING — переносимые находки: 24 предмета', font=font, fill=(233, 227, 212))
doc = ['# Переносимый гражданский лут', '',
       '24 новых предмета. Все имеют отдельную PBR-модель CC0, иконку, описание, вес и размер в рюкзаке.', '',
       'Ещё 100 ценных предметов и вызов самолёта — [расширенный каталог](valuable_loot.md).', '',
       'Цены и 15 тематических матриц — `Balance.CIVILIAN_LOOT_VALUES` / `Balance.CIVILIAN_LOOT`.',
       'Михалыч покупает по общей доле `TRADER_SELL_MULT` (сейчас 55 % от оценки).', '',
       '| Предмет | Оценка, ₽ | Продажа, ₽ | Вес, кг | Клетки | Источник CC0 |',
       '|---|---:|---:|---:|---|---|']
for index, (id, source) in enumerate(sources.items()):
    image = Image.open(ROOT / 'assets/icons' / (id + '.png')).convert('RGBA')
    image.thumbnail((220, 175))
    x, y = 24 + index % 6 * 245, 52 + index // 6 * 255
    canvas.paste(image, (x + (230 - image.width) // 2, y + 15 + (175 - image.height) // 2), image)
    draw.multiline_text((x + 5, y + 199), '\n'.join(textwrap.wrap(items[id]['name'], 24)), font=font, fill=(225, 222, 208))
    it = items[id]
    doc.append(f"| {it['name']} | {values[id]} | {int(values[id] * sell)} | {it['weight']} | {it['size'][0]}×{it['size'][1]} | [Poly Haven]({source['source']}) |")
doc += ['', '## Где искать', '',
        '- Инструменты и тара: хозяйственные магазины, склады, мастерские и гаражи.',
        '- Электроника и компоненты: электроника, сервисные помещения и серверные стойки.',
        '- Бытовые вещи: жилые места, общие стеллажи, продуктовые магазины и киоски.',
        '- Канцелярия и свет: офисы, банк, аптечные помещения. Оптика: фототехника и спорт.', '',
        'Физические находки — `scenes/world/loose_loot.tscn`: нажатие F кладёт одну вещь в рюкзак.',
        'При полном рюкзаке она остаётся на месте. Хост проверяет расстояние и состояние игрока;',
        'успешный подбор удаляет модель у всех участников. Пустая точка не возрождается в том же рейде.', '',
        'В ТЦ точки создаются на свободных частях столов, касс, киосков и на полу у части стеллажей.',
        'В зоне 1 — 16 авторских точек в уже построенном дворе и у гаражей; в зоне 2 — 18 возле существующих мест обыска.',
        'Редактируемые слои подключены через `extras` данных сектора. Шанс вещи на точке — 42 %;',
        'выбор зависит от темы, дорогие вещи имеют меньший вес. Видимость модели ограничена 65 м.', '',
        'Канистра и медицинский футляр пустые, ящик не содержит инструментов. Это бартерные находки:',
        'новых расходников, функций оптики и электрических приборов здесь не вводится.', '',
        'Лазерные головки, рама и контроллер сохраняют отдельные редкие броски в исходных темах.', '',
        '## Проверка и сборка', '',
        '- `tools/godot.cmd --headless res://tools/loot_test.tscn` — каталог, темы, полный рюкзак, подбор, вынос, сохранение и продажа.',
        '- `tools/godot.cmd --headless res://tools/loot_net_test.tscn -- host` и затем `-- client` — ENet на отдельном порту 17788.',
        '- `tools/godot.cmd res://tools/loot_shots.tscn` — игровые снимки на реальной карте.',
        '- Blender: `tools/build_loot_assets.py`; исходники и редактируемые `.blend` в `_asset_src`, готовые GLB в `assets/items/models/loot`.',
        '- `tools/icon_bake.tscn -- <id ...>` — иконки, `python tools/loot_catalog.py` — этот каталог и контактный лист.', '']
(ROOT / 'docs/design/loot.md').write_text('\n'.join(doc), encoding='utf-8')
canvas.save(ROOT / 'docs/screens/loot_catalog.png')
