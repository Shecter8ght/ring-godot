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
