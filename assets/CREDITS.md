# Источники ассетов

Каждый внешний ассет — строкой: путь в `assets/`, название, автор, лицензия, ссылка.
Допустимы только CC0 / CC-BY и собственные работы. Сырьё лежит в `_asset_src/<тип>/<id>/` с `license.txt`.
Файл собирается скриптами из `tools/` — руками не править.

## Текстуры (assets/textures, материалы в assets/materials)

- `assets/textures/asphalt_02/` — Asphalt 02, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/asphalt_02 — асфальт парковки и доков
- `assets/textures/concrete_block_wall_02/` — Concrete Block Wall 02, Charlotte Baglioni, CC0 1.0, https://polyhaven.com/a/concrete_block_wall_02 — стены доков и ограждения
- `assets/textures/concrete_floor_worn_001/` — Concrete Floor Worn 001, Dimitrios Savva, Rico Cilliers, CC0 1.0, https://polyhaven.com/a/concrete_floor_worn_001 — пол склада и служебных помещений
- `assets/textures/concrete_panels/` — Concrete Panels, Amal Kumar, CC0 1.0, https://polyhaven.com/a/concrete_panels — внешняя стена здания
- `assets/textures/concrete_wall_006/` — Concrete Wall 006, Dario Barresi, Charlotte Baglioni, CC0 1.0, https://polyhaven.com/a/concrete_wall_006 — стены служебных коридоров
- `assets/textures/corrugated_iron_02/` — Corrugated Iron 02, Jenelle van Heerden, Sergej Majboroda, CC0 1.0, https://polyhaven.com/a/corrugated_iron_02 — профлист, крыши доков
- `assets/textures/green_metal_rust/` — Green Metal Rust, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/green_metal_rust — крашеный корпус гранаты
- `assets/textures/large_floor_tiles_02/` — Large Floor Tiles 02, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/large_floor_tiles_02 — пол галереи ТЦ
- `assets/textures/metal_plate/` — Metal Plate, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/metal_plate — рампы и металлические полы
- `assets/textures/natural_walnut_veneer/` — Natural Walnut Veneer, Jenelle van Heerden, CC0 1.0, https://polyhaven.com/a/natural_walnut_veneer — ореховое ложе дробовика и винтовки
- `assets/textures/painted_metal_shutter/` — Painted Metal Shutter, Dario Barresi, Rico Cilliers, Charlotte Baglioni, CC0 1.0, https://polyhaven.com/a/painted_metal_shutter — роллеты магазинов
- `assets/textures/painted_plaster_wall/` — Painted Plaster Wall, Amal Kumar, CC0 1.0, https://polyhaven.com/a/painted_plaster_wall — стены магазинов
- `assets/textures/sapele_veneer/` — Sapele Veneer, Jenelle van Heerden, CC0 1.0, https://polyhaven.com/a/sapele_veneer — дерево автомата (красноватый лак)
- `assets/textures/worn_tile_floor/` — Worn Tile Floor, Dimitrios Savva, CC0 1.0, https://polyhaven.com/a/worn_tile_floor — пол торгового зала

## Звук (assets/audio — `tools/import_audio.py`, обработка — `tools/build_audio.py` прежнего RING)

| Источник | Автор | Лицензия | Где |
|---|---|---|---|
| The Free Firearm Sound Library | Ben Jaszczak, Brian Nelson, Kevin Heras, Matthew Nanney | CC0 | guns/shotgun, guns/marksman, *_far |
| 100 CC0 SFX #2 | rubberduck (OpenGameArt) | CC0 | world/door, world/debris, hits/hard, body/hit |
| Gun reload sounds | zer0_sol, SpringySpringo | CC0 | guns/reload_* |
| Loopable Dungeon Ambience / Wind whoosh loop / Dripping water | JaggedStone, SketchMan3, qubodup | CC0 | ambient/building_wind_drips |
| Пистолет и автомат (одиночный) | Shecter8ght — сгенерировано в ElevenLabs | права автора проекта; ElevenLabs — https://elevenlabs.io | guns/pistol, guns/carbine |
| Шаги и бег по камню, грунту, снегу; попадания в стекло, металл, дерево; предсмертные хрипы | Shecter8ght — сгенерировано в ElevenLabs | права автора проекта; ElevenLabs — https://elevenlabs.io | steps/*, hits/glass|metal|wood, voice/rattle_* |

## Персонаж и анимации

- `assets/models/characters/persona_animated.glb` и связанные текстуры — экспорт из `Persona.blend`, предоставленного владельцем проекта. Исходник остаётся у владельца в `D:\ПРОГРАММЫ\Blender 5\Projects`.
- `assets/models/characters/persona_clips.res` — запечённые анимации из предоставленных владельцем файлов Mixamo. Файлы FBX остаются локальными в `assets/animations/`; перечень использованных клипов — `tools/character_clips.json`.

## Транспорт RING

- `assets/models/ring_vehicles/` — модели седана, грузовика и автобуса, созданные для RING; текстуры на основе CC0 Poly Haven.
- `assets/textures/ring_vehicles/` — Blue Metal Plate, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/blue_metal_plate
- `assets/textures/ring_vehicles/` — Rusty Metal Sheet, Amal Kumar, CC0 1.0, https://polyhaven.com/a/rusty_metal_sheet
- `assets/textures/ring_vehicles/` — Rubber Tiles, Amal Kumar, CC0 1.0, https://polyhaven.com/a/rubber_tiles
- `assets/textures/ring_vehicles/` — Denim Fabric 06, Greg Zaal (фото), Rico Cilliers (обработка), CC0 1.0, https://polyhaven.com/a/denim_fabric_06

## Небо (assets/sky)

- `assets/sky/qwantani_night_puresky.hdr` — Qwantani Night (Pure Sky), Greg Zaal, Jarod Guest, CC0 1.0, https://polyhaven.com/a/qwantani_night_puresky — ночное небо со звёздами (фон)
- `assets/sky/moon_lroc_color.jpg` — CGI Moon Kit — Lunar Surface in Color (LRO LROC), NASA's Scientific Visualization Studio, Public Domain (NASA), https://svs.gsfc.nasa.gov/4720 — диск Луны в шейдере неба
