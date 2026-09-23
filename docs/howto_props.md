# Как добавить проп (убежище или уровень)

## Быстро — из примитивов (как всё убежище сейчас)

1. `EDITOR.cmd` → открыть `scenes/levels/hideout.tscn`.
2. В дереве выделить `Geometry` (или его подпапку, например `Lounge`) → «+» → `CSGBox3D`
   (или `CSGCylinder3D`, `CSGSphere3D`).
3. В инспекторе: `Size`, положение/поворот гизмо. Галочка **Use Collision** — чтобы об него
   не проходили насквозь.
4. Материал — через **Metadata** (внизу инспектора, «Add Metadata»):
   - `mat` (String) — текстура проекта, например `concrete_floor_worn_001`, `painted_plaster_wall`,
     `corrugated_iron_02`, `metal_plate`, `sapele_veneer`, `natural_walnut_veneer`,
     `green_metal_rust` (папки в `assets/textures`);
   - или `color` (Color) + по желанию `rough`, `metal` (float) — однотонный;
   - или `emit` (Color) — светится (лампа, экран).
5. Ctrl+S. Запустить `RING.cmd` — проп в убежище.

Сложный предмет — несколько CSG-узлов под одним `Node3D` (как `Workbench`, `Lounge`).

## Готовая модель (.glb / .gltf)

1. Скачать модель **только CC0 / CC-BY** (Poly Haven, Kenney, Quaternius, Sketchfab с фильтром
   лицензии). Положить в `_asset_src/<id>/` (например `_asset_src/old_sofa/`) вместе с
   `license.txt`:
   ```
   Название: Old sofa
   Автор: Someone
   Лицензия: CC0
   Источник: https://...
   ```
2. `python tools/import_model.py old_sofa` — копирует в `assets/models/props/old_sofa/` и
   дописывает строку в `assets/CREDITS.md`.
3. `tools/godot.cmd --headless --import` (или просто открыть редактор — он импортирует сам).
4. В сцене: «+» → **ModelProp** → в инспекторе `Model` — выбрать файл модели. Поставить на место,
   повернуть, при нужде `Scale`. Нажать галочку **Fit Box To Model** — коллизия по габариту.
5. Из чего предмет (звук шагов по нему и попаданий): Metadata `surface` = `metal`, `wood`,
   `concrete`, `fabric`, `glass`…
6. Ctrl+S, проверить в игре, закоммитить (или сказать Claude — закоммитит сам).

`ModelProp` сам подставит серую коробку того же размера, если модели нет, — правило проекта:
игра запускается и без `assets/models`.

## Станция (интерактивный проп)

Диван, верстак, торговец — это `HideoutStation` (`src/hideout/hideout_station.gd`): узел с полем
`Kind` (тайник, торговец, выход, верстак, модули) — к нему подходят и жмут F. Станцию можно
перетащить мышкой в другое место или скопировать (Ctrl+D) — окно у неё то же. Новый
вид станции — это уже код (окно в `hideout_ui.gd`): попросить Claude.
