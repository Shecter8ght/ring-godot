# Общежитие — модули Blender, этап 2

2026-10-28, Claude. Поручение — этап 2 `docs/tasks/dorm_vertical_slice.md`. Форма v01 на просмотре у владельца;
текстуры и игровая версия — после принятия формы.

Файл для просмотра: `E:\Models Blender\ENVIRONMENT\RING_Dorm_Modules\models\RING_Dorm_Modules_v01.blend`
(состав, размеры, решения и открытые вопросы — `asset-state.md` в той же папке).

```bat
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_modules.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v01.blend"
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v01.blend" --python-exit-code 1 --python tools/dorm_modules/check_modules.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/checks" [вид …]
```

Модули M01–M18: дверь комнаты со стеной 0,38, окно с раздельными переплётами со стеной 0,64, батарея МС-140,
плинтус, двустворчатая остеклённая дверь с перегородкой, марши 12 и 10 ступеней, площадка, ограждение марша и
поворот на площадке, плиты перекрытия со швом, балка, пилястра, глухие стены. Размеры — из принятого плана r4:
чистый проход двери 1,17 × 2,415, окно 2,096 × 1,65, коридорный портал 0,40 / 0,45 × 0,18.

## Текстуры v02 (на просмотре)

Файл: `E:\Models Blender\ENVIRONMENT\RING_Dorm_Modules\models\RING_Dorm_Modules_v02_textures.blend`
(форма v01 принята 2026-10-28). Стены — облупленная масляная краска до 2,0 м, выше побелка → штукатурка → кирпич;
пол — паркет «ёлочкой» с выбитыми и треснувшими планками; душевые — плитка 20 × 20 с выбитыми, сколотыми и
треснувшими плитками. Доли повреждений — ползунки материала, износ стен — атрибут цвета вершин «Износ».

```bat
tools\sd_bridge\designer_open.cmd
python -X utf8 tools/dorm_modules/sd_run.py tools/dorm_modules/sd_paint.py
python -X utf8 tools/dorm_modules/sd_run.py tools/dorm_modules/sd_plaster.py
python -X utf8 tools/dorm_modules/sd_cook.py "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/designer/dorm_paint.sbs" "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/paint"
python -X utf8 tools/dorm_modules/sd_cook.py "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/designer/dorm_plaster.sbs" "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/plaster"
python -X utf8 tools/dorm_modules/post_cells.py "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/paint" paint
python -X utf8 tools/dorm_modules/post_cells.py "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/plaster" plaster
python -X utf8 tools/dorm_modules/gen_floor_maps.py "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures"
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_modules.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v02_textures.blend"
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v02_textures.blend" --python-exit-code 1 --python tools/dorm_modules/texture_modules.py
```

Предпросмотр карт без Blender: `preview_paint.py`, `preview_plaster.py`. Кадры Eevee: `check_modules.py -- <папка> --eevee [вид …]`.

## Краска v03 (на просмотре, 2026-10-29)

Владелец о v02: «похоже на графику уровня GTA Vice City» — плоские многоугольники Вороного, чистые цвета, швы на
стыках модулей. Краска переделана с нуля (побелка, штукатурка до кирпича, пол и плитка — пока v02).

- Карты считает `tools/dorm_modules/gen_paint_v3.py` (numpy, тайл 2 × 2 м, 4096², бесшовно, ~1,5 мин) →
  `textures/paint_v3`: сетка трещин — ячейки Вороного ~1,6 см с искажёнными координатами (кромки кривые, стыки на три
  стороны), где краска старше — шире и гуще, волосяная сетка ~0,7 см тоном; порядок отслоения E (износ = доля снятой
  краски) с рваным краем, куски у кромки отпадают целиком, островки остаются; крутизна E и её направление — по ним
  материал считает расстояние до кромки в мм при любом износе. Под краской — фотоскан Poly Haven
  `painted_plaster_wall` 4K (CC0, `_asset_src/dorm_textures/ph_painted_plaster_wall_4k`).
- Узлы — `tools/dorm_modules/paint_v3.py`: слои снимаются ступеньками (зелёный → местами старый слой → шпаклёвка →
  штукатурка), каждая ступенька рвётся по своей мелкой сетке; у кромки края кусков приподняты, трещины шире, грязь у
  ступеньки; загиб валиком — только на кромке большого поля краски. Нормали — из карт и направления крутизны, без
  производных экрана (тот же расчёт пойдёт в шейдер Godot). Ползунки: «Цвет краски», «Шероховатость краски» (0,24 —
  полуглянец по просьбе владельца), «Рельеф краски, сила», «Старый слой, доля», «Загиб кромки, доля», «Износ краски, база».
- Стены берут координаты от мира (`paint_v3.wall_coords`): рисунок идёт через стыки модулей без шва.
- Студия краски: `RING_Dorm_Paint_v03_studio.blend` (стена 2,4 × 2 м, износ растёт слева направо, свет скользящий, камеры
  «вблизи», «кромка», «средний», «общий»). Модули с новой краской: `RING_Dorm_Modules_v03.blend`. Кадры — `checks/v03`.
- Открыто: валиков загнутой краски заметно меньше, чем на образце «Cracked Paint»; цвет краски — ползунок.

```bat
python -X utf8 tools/dorm_modules/gen_paint_v3.py [папка] [--size 4096] [--preview]
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/paint_v3_review.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Paint_v03_studio.blend" "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/checks/v03"
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_modules.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend"
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend" --python-exit-code 1 --python tools/dorm_modules/texture_modules.py
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend" --python-exit-code 1 --python tools/dorm_modules/check_modules.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/checks/v03" --eevee corridor_bay wall_close
```

Проверка масок без света: `PAINT_V3_DEBUG=layers` (R — загиб, G — шпаклёвка, B — старый слой) или имя маски
(`curl`, `putty`, `old`, `peeled`, `lift`, `crack`) перед запуском студии.

Файл v02 с 2026-10-28 без карты `textures/paint/peel_field.png` (её стёрла оборвавшаяся сессия доводки) — краска в нём
не отображается; v03 его заменяет.

Для игры (по итогам проверки света): каждая деталь — замкнутое тело настоящей толщины, стекло и полотна дверей —
отдельные объекты (полотно — на пустышке оси петель), UV2 не нужна (запечённого света нет).
В сцену общежития модули ставятся только после слияния пробного света r6.1 в main.
