# RING — Shelter asset credits

Дата интеграции: 2026-10-05. CC0: https://polyhaven.com/license и https://creativecommons.org/publicdomain/zero/1.0/.

## Фототекстуры Poly Haven

| Набор | Автор | Источник | Лицензия | Изменения и финальные файлы |
|---|---|---|---|---|
| Brown Leather | Rob Tuytel | https://polyhaven.com/a/brown_leather | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Dirty Carpet | Rohit Seervi | https://polyhaven.com/a/dirty_carpet | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Denim Fabric 06 | Greg Zaal, Rico Cilliers | https://polyhaven.com/a/denim_fabric_06 | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Rusty Metal Sheet | Amal Kumar | https://polyhaven.com/a/rusty_metal_sheet | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Oak Wood Planks | Dimitrios Savva | https://polyhaven.com/a/oak_wood_planks | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Rubber Tiles | Amal Kumar | https://polyhaven.com/a/rubber_tiles | CC0 1.0 | Tint, roughness/metallic, упаковка ORM; assets/shelter/textures/; 1K |
| Concrete Wall 006 | Dario Barresi, Charlotte Baglioni | https://polyhaven.com/a/concrete_wall_006 | CC0 1.0 | Повторное использование существующего разрешённого источника; assets/shelter/textures/ |
| Painted Plaster Wall | Amal Kumar | https://polyhaven.com/a/painted_plaster_wall | CC0 1.0 | Повторное использование существующего разрешённого источника; assets/shelter/textures/ |
| Concrete Floor Worn 001 | Dimitrios Savva, Rico Cilliers | https://polyhaven.com/a/concrete_floor_worn_001 | CC0 1.0 | Повторное использование существующего разрешённого источника; assets/shelter/textures/ |
| Green Metal Rust | Rob Tuytel | https://polyhaven.com/a/green_metal_rust | CC0 1.0 | Повторное использование существующего разрешённого источника; assets/shelter/textures/ |
| Metal Plate | Rob Tuytel | https://polyhaven.com/a/metal_plate | CC0 1.0 | Повторное использование существующего разрешённого источника; assets/shelter/textures/ |

## Модели Poly Haven

| Ассет | Автор | Источник | Лицензия | Интеграция |
|---|---|---|---|---|
| PH_Sofa (sofa_02) | Kirill Sannikov | https://polyhaven.com/a/sofa_02 | CC0 1.0 | Метры, ground pivot, applied transforms, выбран вариант, simplified collision, исходный PBR 2k; assets/shelter/models/PH_Sofa.glb и levels/shelter/props/ |
| PH_Armchair (ArmChair_01) | Kirill Sannikov | https://polyhaven.com/a/ArmChair_01 | CC0 1.0 | Метры, ground pivot, applied transforms, выбран вариант, simplified collision, исходный PBR 2k; assets/shelter/models/PH_Armchair.glb и levels/shelter/props/ |
| PH_Crate (old_military_crate) | Jack Mava | https://polyhaven.com/a/old_military_crate | CC0 1.0 | Метры, ground pivot, applied transforms, выбран вариант, simplified collision, исходный PBR 1k; assets/shelter/models/PH_Crate.glb и levels/shelter/props/ |
| PH_Barrel (Barrel_01) | Jorge Camacho | https://polyhaven.com/a/Barrel_01 | CC0 1.0 | Метры, ground pivot, applied transforms, выбран вариант, simplified collision, исходный PBR 1k; assets/shelter/models/PH_Barrel.glb и levels/shelter/props/ |
| PH_AmmoBox (ammo_box) | DanKit | https://polyhaven.com/a/ammo_box | CC0 1.0 | Метры, ground pivot, applied transforms, выбран вариант, simplified collision, исходный PBR 1k; assets/shelter/models/PH_AmmoBox.glb и levels/shelter/props/ |

## Собственные и существующие проектные ассеты

- 99 authored моделей архитектуры, мебели, генератора, инженерии, личных предметов и 13 металлических табличек: собственная работа для владельца RING. `tools/build_shelter_assets.py`; редактируемый master `_asset_src/shelter/shelter.blend`. Финальные GLB — `assets/shelter/models/`, ArrayMesh и сцены — `levels/shelter/`.
- PlanningMap, Labels, IndustrialTrim, RoomSigns (атлас эмалированной печати 2048²) и маски декалей — собственная графика; схема кольца взята из существующего дизайна RING. Фотографии пользовательского референса не копировались в текстуры.
- Декоративное оружие — прежние WeaponModels (`wpn_ar_03`, `wpn_hg_01`), запечённые в static ArrayMesh. Происхождение ПМ/PBR — существующий `assets/CREDITS.md`; новые чужие модели оружия не скачивались.
- Персонаж торговца — существующая Persona `assets/models/characters/persona_animated.glb`; его происхождение и анимации указаны в `assets/CREDITS.md`. Старые исходники и лицензии не заменены.
- Аудио — прежние `Audio.hum_loop`, записи шагов и PCM-станции HideoutActivity. Новых сторонних записей нет; наследуем их существующие лицензии.

Сырые скачанные glTF/.bin/фотокарты и `license.txt` каждой модели хранятся в `_asset_src/shelter/external/<id>/`; текстуры — `_asset_src/shelter/textures/<id>/`. `integrated.blend` каждой внешней модели сохраняется отдельно. `_asset_src/` намеренно исключён из Git по правилам проекта.

Ни Sketchfab, ни платные/Editorial/NC/ND ассеты в финальном убежище не используются.

## Художественное наполнение и атмосфера — 2026-10-05

- 34 дополнительных Blender-ассета: посуда и чайный уголок, книги, часы, ткань и одежда, чистка оружия, боеприпасы, инструменты, расходники, упаковки, ручная тележка, приборы и соединения генератора. Собственные модели для владельца RING; исходник `_asset_src/shelter/dressing/shelter_dressing.blend`, экспорт `assets/shelter/dressing/`, сцены `levels/shelter/dressing/`.
- Атлас Dressing: собственные четыре image layers Ucupaint (цвет поверхности, контактный износ, шероховатость, открытый металл), запечённые в три карты 1024². В цвете повторно использованы уже перечисленные выше CC0 фотографии: Green Metal Rust, Metal Plate, Denim Fabric 06, Oak Wood Planks, Painted Plaster Wall. Поверхности Paper/Cardboard наследуют прежние карты Painted Plaster Wall/Oak Wood Planks с художественной обработкой. Новых сторонних источников нет.
- DustMotes и KettleVapor: собственные нарисованные маски и заранее записанные Blender shape-key анимации. Исходник `_asset_src/shelter/atmosphere/shelter_atmosphere.blend`; GLB, маски и собственный шейдер `soft_density.gdshader` — `assets/shelter/atmosphere/`. Лицензия — собственная работа для RING.
- Локальные `license.txt` лежат рядом с обоими исходниками. Сохранённые исходники повторно открыты и проверены; результаты с SHA256 — `docs/shelter/validation/dressing_source_audit.json` и `atmosphere_source_audit.json`. Сырьё по правилам проекта не публикуется в Git.

## Котельная зоны 5 и тир (2026-10-07)

Фототекстуры Poly Haven (CC0 1.0), 1K, tint/ORM — `tools/shelter_boiler_materials.py`:

| Набор | Автор | Источник | Материал |
|---|---|---|---|
| Factory Brick | Rob Tuytel | https://polyhaven.com/a/factory_brick | Brick |
| Whitewashed Brick | Charlotte Baglioni | https://polyhaven.com/a/whitewashed_brick | Whitewash |
| Peeling Painted Wall | Dimitrios Savva | https://polyhaven.com/a/peeling_painted_wall | PeelingPaint |
| Blue Metal Plate | Rob Tuytel | https://polyhaven.com/a/blue_metal_plate | BoilerSteel |
| Rusty Metal 02 | Rob Tuytel | https://polyhaven.com/a/rusty_metal_02 | FlueRust |

Модели Poly Haven (CC0 1.0), реальный масштаб, опора на пол, лишние варианты отброшены, мелочь с картами 512 px — `tools/shelter_boiler_external.py`, `tools/integrate_shelter_boiler_external.py`:

| Ассет | Модель | Автор | Источник |
|---|---|---|---|
| PH_Chair | Painted Wooden Chair 02 | Kirill Sannikov | https://polyhaven.com/a/painted_wooden_chair_02 |
| PH_Boots | Rubber Boots | L | https://polyhaven.com/a/rubber_boots |
| PH_Cans | Russian Food Cans 01 | Kosan Aziz | https://polyhaven.com/a/russian_food_cans_01 |
| PH_JerryCan | Metal Jerrycan Green | Ulan Cabanilla | https://polyhaven.com/a/metal_jerrycan_green |
| PH_MedicalBox | Medical Box | Ulan Cabanilla | https://polyhaven.com/a/medical_box |
| PH_Radio | Vintage Radio Transceiver | Mateusz Sadek | https://polyhaven.com/a/vintage_radio_transceiver |
| PH_DeskLamp | Desk Lamp Arm 01 | Yann Kervran, Kuutti Siitonen | https://polyhaven.com/a/desk_lamp_arm_01 |
| PH_MilitaryCrate | Wooden Military Crate | Prabhjinder Singh | https://polyhaven.com/a/wooden_military_crate |
| PH_Carton | Cardboard Box 01 | Rahul Chaudhary | https://polyhaven.com/a/cardboard_box_01 |
| PH_Bench | Painted Wooden Bench | Kirill Sannikov | https://polyhaven.com/a/painted_wooden_bench |
| PH_CoffeeTable | Industrial Coffee Table | Ulan Cabanilla | https://polyhaven.com/a/industrial_coffee_table |
| PH_Binoculars | Binoculars | Derek Wight | https://polyhaven.com/a/binoculars |
| PH_GasMask | Old Gas Mask | Michał Wiśniewski | https://polyhaven.com/a/old_gas_mask |
| PH_Gloves | Garden Gloves 01 | Satyaki Mandal | https://polyhaven.com/a/garden_gloves_01 |
| PH_Kettle | Vintage Electric Kettle | SV Garip | https://polyhaven.com/a/vintage_electric_kettle |
| PH_Clipboard | Clipboard | ProgrammerOnCoffee | https://polyhaven.com/a/clipboard |
| PH_Toolbox | Metal Toolbox | Mateusz Sadek | https://polyhaven.com/a/metal_toolbox |
| PH_ToolChest | Metal Tool Chest | Yann Kervran, John Hutcheson | https://polyhaven.com/a/metal_tool_chest |
| PH_ToolCart | Tool Cart | Savva Zakharov | https://polyhaven.com/a/tool_cart |
| PH_Vice | Bench Vice 01 | Yann Kervran, Antanas Kep | https://polyhaven.com/a/bench_vice_01 |
| PH_DrillPress | Drill Press 01 | Viktor | https://polyhaven.com/a/drill_press_01 |
| PH_Compressor | Old Military Compressor | Brian Speight | https://polyhaven.com/a/old_military_compressor |
| PH_PropaneTank | Propane Tank | Slinc | https://polyhaven.com/a/propane_tank |
| PH_PowerBox | Power Box 01 | Rico Cilliers, Yann Kervran | https://polyhaven.com/a/power_box_01 |
| PH_UtilityBox | Utility Box 01 | James Ray Cock | https://polyhaven.com/a/utility_box_01 |
| PH_HangingLamp | Hanging Industrial Lamp | Kuutti Siitonen | https://polyhaven.com/a/hanging_industrial_lamp |
| PH_Thermos | Modified Thermos | Alex Weber | https://polyhaven.com/a/modified_thermos |
| PH_TrashCan | Metal Trash Can | GurJas Studios | https://polyhaven.com/a/metal_trash_can |
| PH_FoldingStool | Folding Wooden Stool | Ulan Cabanilla | https://polyhaven.com/a/folding_wooden_stool |
| PH_PlasticCrate | Plastic Crate 01 | PierreB3D | https://polyhaven.com/a/plastic_crate_01 |
| PH_Multimeter | Retro Multimeter | elli moeller | https://polyhaven.com/a/retro_multimeter |
| PH_OilTin | Oil Tin | Niklas | https://polyhaven.com/a/oil_tin |
| PH_Crane | Overhead Crane | Timothy3D | https://polyhaven.com/a/overhead_crane |
| PH_MetalDesk | Metal Office Desk | Ulan Cabanilla | https://polyhaven.com/a/metal_office_desk |
| PH_WallClock | Wall Clock | PierreB3D | https://polyhaven.com/a/wall_clock |
| PH_Stool | Metal Stool 02 | Ulan Cabanilla | https://polyhaven.com/a/metal_stool_02 |
| PH_LpgTank | Small Lpg Tank | Ulan Cabanilla | https://polyhaven.com/a/small_lpg_tank |
| PH_PipeWrench | Pipe Wrench | Will Evarts | https://polyhaven.com/a/pipe_wrench |
| PH_Sledgehammer | Sledgehammer 01 | Dylan Guzman | https://polyhaven.com/a/sledgehammer_01 |

Собственные (для владельца RING): стены котельной с окнами из армированного стекла, котельный зал, котлы, насосы, щит КИП, магистрали, тир (рубеж, кабины, направляющие, улавливатель, пульты, тележки, шкаф стойки) — `tools/build_shelter_boiler.py`; шлем, бронежилет, рюкзак — `tools/build_shelter_gear.py` (временно, до замены готовыми моделями). Лист «мишень № 4», армированное стекло, пробоина, кнопки — собственная графика. Модели оружия в шкафу и на столе — существующие ВСС, ПМ, Glock игры (см. `assets/CREDITS.md`). Манекены тира — Persona игры в матовом пластике.

### Старение убежища (2026-10-07) — `assets/shelter/textures/grime/`

| Файл | Источник | Автор | Лицензия |
|---|---|---|---|
| leak_0…4, salt_0…4 (+ ORM, нормали) | ambientCG Leaking001, 003, 004, 005, 008 — https://ambientcg.com | Lennart Demes (ambientCG) | CC0 |
| note_0…8, notes.png (надписи маркером и мелом) | шрифт Neucha — https://fonts.google.com/specimen/Neucha | Jovanny Lemonad | SIL OFL 1.1 (рисованный текст, шрифт в игру не входит) |

Собственные (процедурный шум): macro.png, streaks.png (маски шейдера `aged_surface.gdshader`), soot.png, dust_strip.png, floor_grime_0…2.
