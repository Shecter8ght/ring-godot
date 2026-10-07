# Ремейк убежища — аудит и карта зависимостей

Дата: 2026-10-05. Godot CLI 4.5.1, Forward+, RTX 5070 Ti. В project.godot уже было незакоммиченное указание 4.7; оно не изменено. Старт: scenes/ui/main_menu.tscn. 1 единица = 1 м.

Запрошенная ветка: feature/shelter-remake. Pull с rebase отказал из-за существующих пользовательских изменений. Fetch выполнен: HEAD и origin/main совпадали (0/0). Пользовательские изменения не включаются в коммиты ремейка.

## Dependency map

| Feature | Node / scene | Script / resource | Group / signal | Save ID | Network | Migration |
|---|---|---|---|---|---|---|
| TV | Activities/Tv; hideout_lounge.tscn | HideoutActivity; TV_SHADER; 4 канала | interactables; Net.scenes_changed | Ранее не сохранялся | reliable any_peer _set_state, late join _share_state | Сохранить путь и shader, заменить корпус, перенести в Living |
| Radio | Activities/Radio | HideoutActivity; 4 станции; PCM synthesis | interactables; Net.scenes_changed | Ранее не сохранялось | как TV | Сохранить playback и RPC, заменить mesh |
| Couch | Activities/SeatL, SeatM, SeatR | HideoutActivity.SEAT; Player.sit | interactables | Нет | поза Player — существующий sync | Три места на новом диване |
| Beer | Activities/Beer | HideoutActivity.BEER; hideout_level.drink | interactables | Нет; эффект временный | _said; пьёт локальный игрок | Оставить поведение, authored bottles |
| Trader | Stations/TraderStation; старый Geometry/Trader/TraderNpc = декоративная капсула, НЕ отдельный NPC | HideoutStation.TRADER; HideoutUI; TraderStock; Profile; Missions; Quests | interactables; Quests.changed | money/stash/trust/quests/unlocked_stock | Персональный профиль; сюжет хоста | Тот же station и UI, согласованная человеческая модель из Persona |
| Generator | Stations/UpgradeStation; Geometry/Generator | Upgrades; data/hideout.json | interactables | modules.generator | Локальная прогрессия, ранее нет ON/OFF/fuel | Сохранить окно модулей; отдельный общий рубильник отвечает только за питание нового интерьера по ТЗ, без топлива |
| Workbench | Stations/WorkbenchStation | HideoutStation.WORKBENCH; HideoutUI; Profile.install_mod; WeaponStats | interactables | modules.workbench; equipment | Персональный профиль | Новый стол и инструменты; старый код сборки оружия |
| WeaponStorage | старые декоративные стойки; Stations/StashStation | Profile; ItemDb; HideoutUI.STASH | interactables | stash/equipment | Персональный профиль | Armory station в том же тайнике; прежней динамической выкладки нет |
| ItemStorage | Stations/StashStation | Profile; ItemDb; GridView; SlotView; MagOps | interactables | stash/backpack/pocket | Персональный профиль | Тот же узел в Storage, единый inventory |
| Raid selection | Stations/ExitStation | HideoutUI.EXIT; Floors; RaidConditions; Net.start_level | interactables | floor/floors_open/next_conditions | Хост начинает общий рейд | Планировочный стол + прежний путь ExitStation |
| Saved game | Profile; Saves | src/items/profile.gd; saves.gd | Settings last profile | user://saves/*.json и legacy profile.json | У каждого свой файл | Схема предметов и старый путь hideout.tscn сохраняются |
| Quest hooks | QuestWorld; anton_hideout | data/quests/missing_anton.json | quest_anchors; Quests.changed | quests/flags/campaign | Кампания хоста | Якорь переносится в сцене; текст и этапы не меняются |
| Players/FPS | Player_<peer>; CameraRig | player.tscn; camera_rig.tscn | players/all_players/camera_rig | Нет позиции убежища | owner movement, host Health; Net.scope_sync | Три явных спавна, прежние имена peers и scene scope |
| Lighting/materials | WorldEnvironment; Lights | SectorMaterials; existing CC0 Poly Haven | CEILING_LAYER для изометрии | Нет | Статический environment | SDFGI остаётся; локальные probes, законченные меши и PBR |

## Baseline

Одинаковый инструмент tools/shelter_bench.tscn, отдельный shelter_bench_test.json, VSync off. Godot сообщает render viewport 1920×1080 (окно 1280×720, project stretch). Legacy scene: iso 375.64 FPS / 2.662 ms / 347 draw / 1,226,158 triangles; FPS 374.17 / 2.673 ms / 336 draw / 1,194,187 triangles. Это конкретный прогон на данном ПК, не целевая гарантия.

Резервная версия: levels/shelter/Hideout_Legacy.tscn и Hideout_Lounge_Legacy.tscn. Финальный interior: levels/shelter/Shelter_Interior.tscn; старый путь scenes/levels/hideout.tscn является совместимым экземпляром новой сцены.

## Authoring contract

Фиксированные координаты и меши в GLB/.tscn; Blender/Python нужны только при авторинге. На запуске игры нет генерации окружения. RandomNumberGenerator в прежнем HideoutActivity используется только для PCM-звука; hash в TV_SHADER — картинка помех, не расстановка объектов.
