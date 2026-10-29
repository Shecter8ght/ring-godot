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

## Побелка, паркет, плитка v03 (на просмотре, 2026-10-29)

Краску владелец принял («Краска ок, дальше»); остальные поверхности переделаны тем же способом.

- **Побелка → старый слой с синькой → штукатурка → кирпич / бетон** — `gen_plaster_v3.py` → `textures/plaster_v3`,
  узлы `plaster_v3.py`: побелка облетает чешуйками ~1 см (порядок облетания с крутизной, как у краски), толстая —
  в сетке трещин; длинные трещины штукатурки, разводы протечек с каймой, колонии плесени; штукатурка отваливается
  компактными кусками с осыпающимся краем; кирпич — Poly Haven red_bricks_04 4K (CC0), остатки раствора у края.
  Потолок («Побелка_потолок») — то же по бетону плиты.
- **Паркет «ёлочкой»** — `gen_floor_v3.py` → `textures/floor_v3`, узлы `floor_v3.py`: шпон дуба Poly Haven
  oak_veneer_01 4K (CC0) по планкам, волокна прямые и частые, у каждой планки своя щель, высота и выпуклость;
  старый лак — царапины в основном по блеску, вмятины, разводы, грязь, по проходу лак вытерт. Повреждения
  (владелец: «какие-то разломаны вдоль, какие-то поперёк, какие-то отломаны»): выбита целиком; обломана — конец
  поперёк волокон с зубьями-занозами, полоса вдоль волокон, угол, конец и полоса вместе; трещина вдоль волокон;
  сорван лак с верхним слоем (выбоина). Ползунки: «Выбито», «Обломано», «Треснуло», «Сорван лак» (доли), «Лак
  вытерт», «Грязь» (сила), «Тон старого лака».
- **Плитка 200 × 200** — `gen_tiles_v3.py` → `textures/tiles_v3`, узлы `tiles_v3.py`: каждая плитка чуть косо
  (блики ломаются по плиткам), скруглённая глазурь, утопленный грязный шов, цек, трещины с изломом, сколы до
  черепка, потёки ржавчины от источников вниз по стене, известь, мыльная плёнка, у пола грязь и плесень в швах.
  На стене выше 2,0 м — побелка v03; пол — тёмная метлахская (скол того же цвета). Ползунки: «Выбито», «Скол»,
  «Треснуло», «Ржавые потёки», «Известковый налёт», «Цвет глазури».
- **Глубина ям** (владелец: «дощечка имеет толщину, там, где её нет, должен считываться перепад высот») —
  `parallax.py`: луч от глаза идёт вглубь ямы шагами (паркет 15 мм, плитка 8 мм, штукатурка 20 мм); упёрся в
  соседа — видна его боковая грань (торец планки, кромка плитки с черепком, срез штукатурки), иначе — дно, сдвинутое
  вдаль по взгляду. Решение «выбита / обломана» — одно на элемент: у паркета «плохое место» запечено на планку
  (`floor_break.png`, A), у плитки — шум в центре плитки по сетке 0,2 м мира.
- Координаты от мира у всех поверхностей (`tiles_v3.surface_coords`): пол — x, y, стена — вдоль стены и z.

Студии: `RING_Dorm_Wash_v03_studio.blend`, `RING_Dorm_Floor_v03_studio.blend`, `RING_Dorm_Tiles_v03_studio.blend`
(папка `models`), кадры — `checks/v03` (`wash_v3_*`, `floor_v3_*`, `tiles_v3_*`, `tex_*` — модули).

```bat
python -X utf8 tools/dorm_modules/gen_plaster_v3.py
python -X utf8 tools/dorm_modules/gen_floor_v3.py
python -X utf8 tools/dorm_modules/gen_tiles_v3.py
set REVIEW_KIND=wash|floor|tiles && "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/paint_v3_review.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_<Wash|Floor|Tiles>_v03_studio.blend" "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/checks/v03"
```

Модули v03 пересобираются теми же тремя командами, что выше (build_modules → texture_modules → check_modules
`corridor_bay wall_upper floor_close shower shower_floor`). Отладка паркета без света: `FLOOR_V3_DEBUG=mask`
(R — стенка ямы, G — яма, B — свежее дерево) или `side` (цвет стенки).

## Материалы v03 в стенде Godot (2026-10-29)

Владелец: «Ок, в стенд». Шейдеры `src/blockout/dorm_v3`: `common.gdshaderinc` (оси карты из нормали грани — развёртка
боксов стенда не нужна, шум износа по миру, луч вглубь ямы), `paint` / `wash` / `parquet` / `tiles.gdshaderinc` — те же
числа, что в узлах Blender; верхние `dorm_wall_v3` (стена / откос / потолок), `dorm_parquet_v3`, `dorm_tiles_v3`
(стена / пол). Палитра — `src/blockout/dorm_geometry.gd` (`_apply_v3`): карты раздаются по имени параметра (`_n` — та
же карта без сглаживания: номер планки и плитки), без карт — прежние черновые. Износ по месту вместо атрибута
«Износ» — `wear_attr` в `floors.gdshaderinc` (у пола больше, пятнами). VoxelGI — подмена средними цветами
(`dorm_voxel_bake.gd`, `V3_COLORS`).

```bat
python -X utf8 tools/dorm_modules/godot_textures.py
tools\godot.cmd --headless --import
tools\godot.cmd --headless --script res://tools/dorm_v3_check.gd
tools\godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/dorm_study.tscn -- v3shots
```

Проверка масок без света: `PAINT_V3_DEBUG=layers` (R — загиб, G — шпаклёвка, B — старый слой) или имя маски
(`curl`, `putty`, `old`, `peeled`, `lift`, `crack`) перед запуском студии.

Файл v02 с 2026-10-28 без карты `textures/paint/peel_field.png` (её стёрла оборвавшаяся сессия доводки) — краска в нём
не отображается; v03 его заменяет.

Для игры (по итогам проверки света): каждая деталь — замкнутое тело настоящей толщины, стекло и полотна дверей —
отдельные объекты (полотно — на пустышке оси петель), UV2 не нужна (запечённого света нет).
В сцену общежития модули ставятся только после слияния пробного света r6.1 в main (слит — модули в стенде, ниже).

## Модули в стенде Godot (2026-10-29)

`tools/dorm_modules/godot_export.py` (запуск — в начале файла) сливает части модуля в одну сетку от его корня
(поверхность на материал, фаски применены, карт нет) → `assets/models/dorm`:

| файл | что | корень | треугольников |
|---|---|---|---|
| `door_frame.glb` | коробка с добором и наличниками, номерок (M01 без полотна) | середина проёма на полу, ось стены | 3 152 |
| `door_leaf.glb` | полотно, ручки, петли, скважина | ось петель | 5 876 |
| `window.glb` | коробка, створки, стёкла, фурнитура, подоконник, отлив (M03) | середина окна на полу, ось фасада | 7 396 |
| `radiator.glb` | МС-140 и подводка (M05) | внутренняя грань фасада на полу | 19 332 |

Оси Blender: X вдоль стены, +Y — коридор у двери / комната у окна; в Godot +Y Blender → −Z. Уровни детализации
строит импорт; в стенде один узел на место, сетка общая.

Расстановка — `src/blockout/dorm_modules.gd` (стенд спрашивает `skip` и `trim` у каждого бруска плана):
- двери комнат — проём 1,17 × 2,415 в стене 0,38: коробка наличниками в коридор (по `inward`), полотно — на узле
  двери с петлёй (`dorm_study_door.gd`: позы, коллизия 40 мм и решётка прежние, полотно смещено на 26 мм от оси);
- проём плана — чистый, по четверти коробки; добор стоит за ним (0,597 от оси), коробка — в черновом проёме
  1,244 × 2,452: стены у таких дверей подрезаются до него, срезанное остаётся коллизией;
- окна 2,096 × 1,65 — створками в комнату (сторона — к середине корпуса), батарея под каждым, где в плане была;
  коллизии стекла, подоконника и батареи — прежними брусками без вида.

Краска модулей — `src/blockout/dorm_v3/dorm_module_paint.gdshader` по их развёртке: дерево (коробки, полотна, окна) —
фактура ambientCG PaintedWood008A перекрашена по яркости, тёмные щели краски остаются; металл (батареи) —
green_metal_rust перекрашена, ржавчина точками внизу. Алюминий, тёмная сталь, оцинковка отлива — металл без карт,
стекло — прозрачное. Материалы ставятся по именам слотов Blender (`_material`). VoxelGI — цветом краски × 0,85.

Черновыми остались: двойные двери M07, проёмы 1,8 и двери в перегородках 0,15, лестницы с перилами, плинтусы, фасад.

```bat
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend" --python-exit-code 1 --python tools/dorm_modules/godot_export.py
tools\godot.cmd --headless --import
tools\godot.cmd --headless --script res://tools/dorm_v3_check.gd
set DORM_V3_VIEW=m_door203:5.15:6.0:0.5:5.15:5.5:-1.89
tools\godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/dorm_study.tscn -- v3shots
```
