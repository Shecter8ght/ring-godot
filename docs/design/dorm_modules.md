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

Для игры (по итогам проверки света): каждая деталь — замкнутое тело настоящей толщины, стекло и полотна дверей —
отдельные объекты (полотно — на пустышке оси петель), UV2 не нужна (запечённого света нет).
В сцену общежития модули ставятся только после слияния пробного света r6.1 в main.
