# Переносимый гражданский лут

24 новых предмета. Все имеют отдельную PBR-модель CC0, иконку, описание, вес и размер в рюкзаке.

Ещё 100 ценных предметов и вызов самолёта — [расширенный каталог](valuable_loot.md).

Цены и 15 тематических матриц — `Balance.CIVILIAN_LOOT_VALUES` / `Balance.CIVILIAN_LOOT`.
Михалыч покупает по общей доле `TRADER_SELL_MULT` (сейчас 55 % от оценки).

| Предмет | Оценка, ₽ | Продажа, ₽ | Вес, кг | Клетки | Источник CC0 |
|---|---:|---:|---:|---|---|
| Материнская плата | 10500 | 5775 | 0.55 | 3×2 | [Poly Haven](https://polyhaven.com/a/circuit_board) |
| Пассатижи | 1200 | 660 | 0.28 | 1×2 | [Poly Haven](https://polyhaven.com/a/pliers) |
| Отвёртка | 700 | 385 | 0.12 | 1×2 | [Poly Haven](https://polyhaven.com/a/screwdriver) |
| Слесарный молоток | 1100 | 605 | 0.65 | 1×2 | [Poly Haven](https://polyhaven.com/a/cross_pein_hammer) |
| Трубный ключ | 1900 | 1045 | 1.1 | 1×3 | [Poly Haven](https://polyhaven.com/a/pipe_wrench) |
| Стрелочный мультиметр | 7800 | 4290 | 0.9 | 2×2 | [Poly Haven](https://polyhaven.com/a/retro_multimeter) |
| Банка технического масла | 1400 | 770 | 0.75 | 1×2 | [Poly Haven](https://polyhaven.com/a/oil_tin) |
| Металлический термос | 1700 | 935 | 0.7 | 1×2 | [Poly Haven](https://polyhaven.com/a/modified_thermos) |
| Электрический чайник | 2400 | 1320 | 1.3 | 2×2 | [Poly Haven](https://polyhaven.com/a/vintage_electric_kettle) |
| Настольная радиостанция | 14000 | 7700 | 2.4 | 3×2 | [Poly Haven](https://polyhaven.com/a/vintage_radio_transceiver) |
| Кассетный плеер | 3200 | 1760 | 0.32 | 1×2 | [Poly Haven](https://polyhaven.com/a/cassette_player) |
| Плёночная кинокамера | 11500 | 6325 | 0.85 | 2×2 | [Poly Haven](https://polyhaven.com/a/vintage_video_camera) |
| Полевой бинокль | 8500 | 4675 | 0.8 | 2×2 | [Poly Haven](https://polyhaven.com/a/binoculars) |
| Пустая металлическая канистра | 2200 | 1210 | 3.2 | 3×3 | [Poly Haven](https://polyhaven.com/a/metal_jerrycan_green) |
| Пустой медицинский футляр | 1600 | 880 | 1.2 | 3×2 | [Poly Haven](https://polyhaven.com/a/medical_box) |
| Металлический ящик для инструмента | 2800 | 1540 | 2.4 | 3×2 | [Poly Haven](https://polyhaven.com/a/metal_toolbox) |
| Слесарные тиски | 3600 | 1980 | 5.4 | 2×3 | [Poly Haven](https://polyhaven.com/a/bench_vice_01) |
| Настольная лампа | 2600 | 1430 | 2.0 | 3×3 | [Poly Haven](https://polyhaven.com/a/desk_lamp_arm_01) |
| Распределительная коробка | 2800 | 1540 | 0.9 | 2×2 | [Poly Haven](https://polyhaven.com/a/utility_box_01) |
| Силовой электрический блок | 6400 | 3520 | 3.5 | 3×3 | [Poly Haven](https://polyhaven.com/a/power_box_01) |

## Где искать

- Инструменты и тара: хозяйственные магазины, склады, мастерские и гаражи.
- Электроника и компоненты: электроника, сервисные помещения и серверные стойки.
- Бытовые вещи: жилые места, общие стеллажи, продуктовые магазины и киоски.
- Канцелярия и свет: офисы, банк, аптечные помещения. Оптика: фототехника и спорт.

Физические находки — `scenes/world/loose_loot.tscn`: нажатие F кладёт одну вещь в рюкзак.
При полном рюкзаке она остаётся на месте. Хост проверяет расстояние и состояние игрока;
успешный подбор удаляет модель у всех участников. Пустая точка не возрождается в том же рейде.

В ТЦ точки создаются на свободных частях столов, касс, киосков и на полу у части стеллажей.
В зоне 1 — 16 авторских точек в уже построенном дворе и у гаражей; в зоне 2 — 18 возле существующих мест обыска.
Редактируемые слои подключены через `extras` данных сектора. Шанс вещи на точке — 42 %;
выбор зависит от темы, дорогие вещи имеют меньший вес. Видимость модели ограничена 65 м.

Канистра и медицинский футляр пустые, ящик не содержит инструментов. Это бартерные находки:
новых расходников, функций оптики и электрических приборов здесь не вводится.

Лазерные головки, рама и контроллер сохраняют отдельные редкие броски в исходных темах.

## Проверка и сборка

- `tools/godot.cmd --headless res://tools/loot_test.tscn` — каталог, темы, полный рюкзак, подбор, вынос, сохранение и продажа.
- `tools/godot.cmd --headless res://tools/loot_net_test.tscn -- host` и затем `-- client` — ENet на отдельном порту 17788.
- `tools/godot.cmd res://tools/loot_shots.tscn` — игровые снимки на реальной карте.
- Blender: `tools/build_loot_assets.py`; исходники и редактируемые `.blend` в `_asset_src`, готовые GLB в `assets/items/models/loot`.
- `tools/icon_bake.tscn -- <id ...>` — иконки, `python tools/loot_catalog.py` — этот каталог и контактный лист.
