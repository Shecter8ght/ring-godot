# Сцены, стенды и уровни RING — инвентаризация

Собрано `tools/scene_board/inventory.py` 2026-11-02 12:13. Смотреть и убирать — «Доска сцен» (`SCENE_BOARD.cmd`).
Колонки: что это, откуда запускают, кто ссылается (живые ссылки — сцены, код, данные, запускалки; документы не считаются), сколько файлов принадлежат только ей, последняя правка.

## Карты рейда (3)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `scenes/levels/mall_map.tscn` | ТЦ «РИНГ» · территория | Запускалка tools/smoke.cmd; Маршрут рейда «ТЦ «РИНГ» · территория» (data/floors.json); Игра открывает её сама (src/core/balance.gd) | `data/floors.json`, `data/navigation/mall_map/manifest.json`, `data/quests/car_recovery.json`, `data/sectors/mall_map.json` и ещё 79 | 1, 5 КБ | 2026-10-19 | не убирать |
| `scenes/levels/prospekt.tscn` | Проспект | Маршрут рейда «Проспект» (data/floors.json); Игра открывает её сама (src/core/balance.gd) | `data/floors.json`, `data/navigation/prospekt/manifest.json`, `data/quests/prologue.json`, `data/raid_maps.json` и ещё 12 | 2, 73 КБ | 2026-10-31 | не убирать |
| `scenes/levels/zone01_mall.tscn` | Пригород (зона 1) | Маршрут рейда «Зона 1 · Пригород» (data/floors.json) | `data/floors.json`, `data/navigation/zone01/manifest.json`, `data/quest_sites/car_recovery_belt.json`, `data/quests/car_recovery.json` и ещё 27 | 1, 6 КБ | 2026-10-19 | не убирать |

## Убежище (5)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `levels/shelter/Hideout_Legacy.tscn` | Старое убежище — Можно убирать: ни игра, ни проверки его не открывают. | — | — | 1, 42 КБ | 2026-10-05 | устарело |
| `levels/shelter/Hideout_Lounge_Legacy.tscn` | Старое убежище — комната отдыха — Можно убирать вместе со старым убежищем. | — | — | 1, 1 КБ | 2026-10-05 | устарело |
| `levels/shelter/Shelter_Exterior.tscn` | Котельная — двор и выход | Входит в scenes/levels/hideout.tscn | `scenes/levels/hideout.tscn`, `tools/author_shelter_exterior.gd` | 16, 2.5 МБ | 2026-10-11 | не убирать |
| `levels/shelter/Shelter_Interior.tscn` | Котельная — внутри | Входит в scenes/levels/hideout.tscn | `scenes/levels/hideout.tscn`, `tools/author_shelter_dressing.gd`, `tools/author_shelter_grime.gd`, `tools/author_shelter_scene.gd` и ещё 4 | 423, 112.6 МБ | 2026-11-01 | не убирать |
| `scenes/levels/hideout.tscn` | Убежище — котельная (сейчас в игре) | Игра открывает её сама (src/core/balance.gd) | `data/quests/missing_anton.json`, `data/quests/tutorial_basics.json`, `src/core/balance.gd`, `tools/author_loose_loot.gd` и ещё 13 | 4, 33 КБ | 2026-10-11 | не убирать |

## Меню и экраны игры (3)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `scenes/net/lobby.tscn` | Лобби (кооп) | — | `tools/net_host_test.gd` | 3, 7 КБ | 2026-10-24 | не убирать |
| `scenes/ui/loading_screen.tscn` | Экран загрузки | — | `project.godot` | 3, 6 КБ | 2026-10-14 | не убирать |
| `scenes/ui/main_menu.tscn` | Главное меню | Стартовая сцена игры (project.godot); Игра открывает её сама (src/core/balance.gd) | `project.godot`, `src/core/balance.gd`, `tools/development_labs_test.gd` | 3, 13 КБ | 2026-10-31 | не убирать |

## Стенды владельца (24)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `scenes/debug/atmosphere_lab.tscn` | Свет и атмосфера | Запускалка LIGHT_LAB.cmd; Главное меню игры | `src/ui/main_menu.gd`, `tools/development_labs_test.gd` | 2, 493 Б | 2026-10-23 | нет в AGENTS.md |
| `scenes/debug/impact_lab.tscn` | Попадания и эффекты | Запускалка IMPACT_LAB.cmd; Главное меню игры | `src/ui/main_menu.gd`, `tools/development_labs_test.gd` | 2, 492 Б | 2026-10-23 | нет в AGENTS.md |
| `scenes/debug/perception_lab.tscn` | Зрение и слух противников | Запускалка PERCEPTION_LAB.cmd; Главное меню игры | `src/ui/main_menu.gd`, `tools/development_labs_test.gd` | 2, 510 Б | 2026-10-23 | нет в AGENTS.md |
| `scenes/debug/weapon_pose_lab.tscn` | Оружие и хват рук — HAND_GRIP_LAB.cmd и WEAPON_POSE.cmd открывают одно и то же. | Запускалка HAND_GRIP_LAB.cmd; Запускалка WEAPON_POSE.cmd; Главное меню игры | `src/ui/main_menu.gd`, `tools/development_labs_test.gd`, `tools/finger_fit_test.gd`, `tools/hand_grip_test.gd` и ещё 1 | 3, 4 КБ | 2026-10-23 | дубль, нет в AGENTS.md |
| `tools/anim_stand.tscn` | Стенд анимаций | AGENTS.md, строка 638 | — | 3, 16 КБ | 2026-10-19 |  |
| `tools/arms_gallery.tscn` | Хват крупным планом | — | — | 3, 2 КБ | 2026-09-26 | нет в AGENTS.md |
| `tools/arms_playtest.tscn` | Обход всех стволов и обвесов | — | — | 3, 8 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/character_gallery.tscn` | Персонаж в трёх позах — Сделано на Persona — её владелец решил убрать (2026-10-29), стенды на ней пока оставлены. | — | — | 3, 2 КБ | 2026-09-30 | нет в AGENTS.md |
| `tools/dorm_play.tscn` | Общежитие — игрок и боты | Запускалка tools/dorm_play.cmd; AGENTS.md, строка 199 | — | 4, 36 КБ | 2026-11-02 | не убирать, в работе |
| `tools/dorm_study.tscn` | Общежитие — прогулка и свет | Запускалка tools/dorm_study.cmd; AGENTS.md, строка 195; AGENTS.md, строка 204; AGENTS.md, строка 205; AGENTS.md, строка 206 | `tools/dorm_ui_check.gd` | 8, 52 КБ | 2026-11-02 | не убирать, в работе |
| `tools/gallery.tscn` | Витрина оружия | — | — | 3, 2 КБ | 2026-09-22 | нет в AGENTS.md |
| `tools/hideout_move_probe.tscn` | Скорость в убежище | AGENTS.md, строка 653 | — | 3, 1 КБ | 2026-11-01 |  |
| `tools/impact_gallery.tscn` | Галерея попаданий | — | — | 3, 19 КБ | 2026-10-19 | нет в AGENTS.md |
| `tools/mall_study.tscn` | ТЦ — прогулка по черновику территории | Запускалка tools/mall_study.cmd; AGENTS.md, строка 384 | `tools/mall_study.gd` | 2, 280 Б | 2026-10-17 |  |
| `tools/mods_gallery.tscn` | Витрина обвесов | AGENTS.md, строка 583 | — | 3, 5 КБ | 2026-11-01 |  |
| `tools/normal_probe.tscn` | Стенд нормалей | AGENTS.md, строка 450 | — | 3, 7 КБ | 2026-11-01 |  |
| `tools/parking_probe.tscn` | Стенд высоты паркинга — Выбор сделан — стенд нужен, только если захотите пересмотреть. | AGENTS.md, строка 101 | — | 3, 16 КБ | 2026-10-29 |  |
| `tools/persona_playtest.tscn` | Persona — 30 секунд игры — Persona владелец решил убрать (2026-10-29); стенды на ней пока оставлены. | — | — | 3, 3 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/prospekt_study.tscn` | Проспект — прогулка по черновику | Запускалка tools/prospekt_study.cmd; AGENTS.md, строка 320 | `tools/prospekt_study.gd` | 2, 292 Б | 2026-10-24 |  |
| `tools/scale_probe.tscn` | Стенд масштаба — Выбор сделан — стенд нужен, только если захотите пересмотреть. | AGENTS.md, строка 96 | — | 3, 15 КБ | 2026-10-24 |  |
| `tools/shelter_bench.tscn` | Сравнение старого и нового убежища — Нужен был при переезде в котельную; без старого убежища смысла не имеет. | — | — | 3, 1 КБ | 2026-10-05 | устарело, нет в AGENTS.md |
| `tools/sight_inventory.tscn` | Перечень прицелов | — | — | 4, 61 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/ssr_probe.tscn` | SSR движка | AGENTS.md, строка 166 | — | 3, 2 КБ | 2026-09-24 |  |
| `tools/urban_belt_study.tscn` | «Городской пояс» — прогулка (старый черновик) — По решению 2026-10-17 черновик только для прогулки, дальше не развивается; Пригород строится в рейдовой карте. | Запускалка tools/urban_belt_study.cmd | — | 2, 299 Б | 2026-10-16 | устарело, нет в AGENTS.md |

## Прогулки по черновикам карт (5)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `scenes/levels/dorm_study.tscn` | Общежитие — сама карта | — | `tools/dorm_light_probe.gd`, `tools/dorm_play.gd`, `tools/dorm_study.gd` | 8, 39 КБ | 2026-11-02 | не убирать, в работе, есть несохранённые правки, нет в AGENTS.md |
| `scenes/levels/mall_1f.tscn` | ТЦ — 1-й этаж (серый черновик) | — | `data/sectors/mall_1f.json`, `tools/author_loose_loot.gd`, `tools/mall_1f_check.gd` | 1, 13 КБ | 2026-10-15 | нет в AGENTS.md |
| `scenes/levels/mall_study.tscn` | ТЦ — черновик территории | Входит в scenes/levels/mall_map.tscn | `data/navigation/mall_map/manifest.json`, `data/sectors/mall_map.json`, `scenes/levels/mall_map.tscn`, `src/world/urban_navigation.gd` и ещё 2 | 3, 34 КБ | 2026-10-17 | не убирать, нет в AGENTS.md |
| `scenes/levels/prospekt_study.tscn` | Проспект — черновик карты | Входит в scenes/levels/prospekt.tscn | `data/navigation/prospekt/manifest.json`, `data/sectors/prospekt.json`, `scenes/levels/prospekt.tscn`, `src/world/urban_navigation.gd` и ещё 4 | 3, 23 КБ | 2026-10-31 | не убирать, нет в AGENTS.md |
| `scenes/levels/urban_belt_study.tscn` | «Городской пояс» — старый черновик карты — Убирать вместе с прогулкой и её проверкой. | — | `tools/urban_belt_launch_test.gd`, `tools/urban_belt_study.gd` | 3, 18 КБ | 2026-10-16 | устарело, нет в AGENTS.md |

## Автоматические проверки (142)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `tools/ads_optics_test.tscn` | ADS: мир без увеличения, кратность только в линзе, колесо и… | — | — | 3, 12 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/ai_population_test.tscn` | Население слоями на «Пешем маршруте» | AGENTS.md, строка 88 | — | 3, 16 КБ | 2026-10-18 |  |
| `tools/ai_reaction_test.tscn` | Настоящие зрение, оружейный таймер и бой Marauder. Статистика | — | — | 3, 11 КБ | 2026-10-30 | нет в AGENTS.md |
| `tools/ai_squad_test.tscn` | Тактика отряда | AGENTS.md, строка 85 | — | 3, 13 КБ | 2026-10-24 |  |
| `tools/ai_test.tscn` | Прогон мародёра | AGENTS.md, строка 84 | — | 3, 5 КБ | 2026-10-24 |  |
| `tools/ai_work_test.tscn` | Повторные цели не сбрасывают путь | — | — | 3, 9 КБ | 2026-10-14 | нет в AGENTS.md |
| `tools/aim_feel_test.tscn` | Пристрелка (сбитый ноль, щелчки), дыхание и его задержка, отдача в… | AGENTS.md, строка 156 | — | 3, 11 КБ | 2026-11-01 |  |
| `tools/ambush_test.tscn` | Засада (AI_AMBUSH) | AGENTS.md, строка 86 | — | 3, 9 КБ | 2026-10-24 |  |
| `tools/ammo_mix_test.tscn` | Патроны в магазине вперемешку | AGENTS.md, строка 153 | — | 3, 9 КБ | 2026-10-24 |  |
| `tools/anim_test.tscn` | Анимации Persona при 144 к/с — Проверяет анимации на Persona — её владелец решил убрать (2026-10-29), но клипы общие и пока нужны. | AGENTS.md, строка 635 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/ar15_check.tscn` | ГРАНЬ-15 в движке | AGENTS.md, строка 561 | — | 3, 12 КБ | 2026-11-01 |  |
| `tools/arsenal_test.tscn` | Арсенал, CASE 1–20 ТЗ | AGENTS.md, строка 406 | — | 3, 25 КБ | 2026-11-01 |  |
| `tools/audio_dry_test.tscn` | Измеряет реальный выход Audio | — | — | 3, 8 КБ | 2026-10-21 | нет в AGENTS.md |
| `tools/backpack_test.tscn` | Рюкзак | — | — | 3, 4 КБ | 2026-10-19 | нет в AGENTS.md |
| `tools/breaker_test.tscn` | Главный рубильник света ТЦ | AGENTS.md, строка 648 | — | 3, 4 КБ | 2026-09-26 |  |
| `tools/build_test.tscn` | Сборка деревом (WeaponBuild) | AGENTS.md, строка 584 | — | 3, 25 КБ | 2026-11-01 |  |
| `tools/camera_motion_test.tscn` | Движение камеры (CameraMotion, Balance.CAMERA_MOTION) при 144 к/с | AGENTS.md, строка 93 | — | 3, 17 КБ | 2026-10-24 | есть несохранённые правки |
| `tools/car_recovery_test.tscn` | Заказ «Вернуть машину» по данным | AGENTS.md, строка 129 | — | 3, 8 КБ | 2026-10-19 |  |
| `tools/carry_test.tscn` | Стойка «наискосок» (Balance.WEAPON_CARRY) | AGENTS.md, строка 105 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/cart_net_test.tscn` | Настоящий ENet | — | — | 3, 8 КБ | 2026-10-02 | нет в AGENTS.md |
| `tools/cart_test.tscn` | Стенд настоящих столкновений | — | — | 3, 10 КБ | 2026-10-02 | нет в AGENTS.md |
| `tools/cheats_settings_test.tscn` | Сохранение настройки, единственное меню читов, выполнение команд и… | — | — | 3, 6 КБ | 2026-10-14 | нет в AGENTS.md |
| `tools/climb_test.tscn` | Залезть наверх (Climb | AGENTS.md, строка 650 | — | 3, 14 КБ | 2026-10-24 |  |
| `tools/compile_check.tscn` | Все скрипты собираются (с автозагрузками) | AGENTS.md, строка 407 | — | 3, 1 КБ | 2026-09-26 | не убирать |
| `tools/conditions_test.tscn` | Условия рейда | AGENTS.md, строка 144 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/contracts_net_test.tscn` | Контракты в группе (хост + гость, в убежище) | — | — | 3, 4 КБ | 2026-10-07 | нет в AGENTS.md |
| `tools/contracts_test.tscn` | Контракты терминала (Contracts) | — | — | 3, 7 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/coop_hideout_client.tscn` | Кооп-убежище, клиент (в паре с coop_hideout_host) | AGENTS.md, строка 598 | — | 3, 3 КБ | 2026-09-25 |  |
| `tools/coop_hideout_host.tscn` | Кооп-убежище, хост (в паре с coop_hideout_client) | AGENTS.md, строка 598 | — | 3, 4 КБ | 2026-09-25 |  |
| `tools/coop_items_test.tscn` | Кооп, вещи гостя в рейде (два реальных ENet peer, порт 17791) | AGENTS.md, строка 609 | — | 3, 12 КБ | 2026-10-24 |  |
| `tools/coop_loading_test.tscn` | Долгая загрузка зоны 1 не должна выкидывать друга в убежище | AGENTS.md, строка 600 | — | 3, 6 КБ | 2026-10-14 |  |
| `tools/coop_population_test.tscn` | Кооп, население рейда слоями на «Пешем маршруте» (реальные ENet… | AGENTS.md, строка 89 | — | 3, 15 КБ | 2026-10-18 |  |
| `tools/coop_quest_client.tscn` | Общий сюжет группы, клиент (в паре с coop_quest_host) | AGENTS.md, строка 641 | — | 3, 4 КБ | 2026-10-02 |  |
| `tools/coop_quest_host.tscn` | Общий сюжет группы, хост (в паре с coop_quest_client) | AGENTS.md, строка 641 | — | 3, 3 КБ | 2026-10-02 |  |
| `tools/coop_raid_test.tscn` | Кооп на троих | AGENTS.md, строка 603 | — | 3, 17 КБ | 2026-10-09 |  |
| `tools/detection_indicator_test.tscn` | Общий стенд Player/Health/CameraRig | — | — | 3, 9 КБ | 2026-10-30 | нет в AGENTS.md |
| `tools/development_labs_test.tscn` | Реальные сцены, UI, свет, частицы, лучи и состояния мародёра | — | — | 3, 10 КБ | 2026-10-23 | нет в AGENTS.md |
| `tools/downed_test.tscn` | Тяжёлое ранение | AGENTS.md, строка 117 | — | 3, 17 КБ | 2026-10-31 |  |
| `tools/dust_cover_test.tscn` | Шторка ГРАНЬ-15 | AGENTS.md, строка 569 | — | 3, 7 КБ | 2026-10-30 |  |
| `tools/economy_audit.tscn` | Снимок экономики для обсуждения баланса | — | — | 4, 340 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/economy_prices_test.tscn` | Цены v0 | — | — | 5, 404 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/engraver_head_test.tscn` | Головка гравировщика в станке | AGENTS.md, строка 615 | — | 3, 5 КБ | 2026-11-01 |  |
| `tools/engraving_net_test.tscn` | Реальный ENet на отдельном порту | — | — | 3, 7 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/engraving_raid_test.tscn` | Настоящие сцены рейда и сохранения | — | — | 3, 6 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/engraving_test.tscn` | Полный ресурс головки, миграция, запись с отказом диска, груз и… | — | — | 3, 8 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/equip_doll_test.tscn` | Окно снаряжения v2 без окна | AGENTS.md, строка 679 | — | 3, 11 КБ | 2026-11-01 |  |
| `tools/evac_test.tscn` | Эвакуация группой | AGENTS.md, строка 633 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/events_test.tscn` | События и фракции | AGENTS.md, строка 146 | — | 3, 9 КБ | 2026-10-24 |  |
| `tools/finger_fit_test.tscn` | Геометрия контакта, неизменность костей, оба рига и настоящий ввод… | — | — | 3, 13 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/fire_mode_test.tscn` | Режимы огня (X, ВЕРАС-54 | AGENTS.md, строка 149 | — | 3, 8 КБ | 2026-11-01 |  |
| `tools/first_hit_test.tscn` | Фриз первых попаданий | AGENTS.md, строка 163 | — | 3, 5 КБ | 2026-10-19 |  |
| `tools/flare_pistol_net_test.tscn` | Два настоящих ENet-процесса | — | — | 3, 9 КБ | 2026-10-11 | нет в AGENTS.md |
| `tools/flare_pistol_test.tscn` | Реальные игровые ресурсы и операции | — | — | 3, 14 КБ | 2026-10-19 | нет в AGENTS.md |
| `tools/fx_test.tscn` | Проверка эффектов попаданий | — | — | 3, 3 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/glass_test.tscn` | Витрины | AGENTS.md, строка 162 | — | 3, 6 КБ | 2026-10-24 |  |
| `tools/glock_test.tscn` | Glock | AGENTS.md, строка 580 | — | 3, 8 КБ | 2026-10-04 |  |
| `tools/god_test.tscn` | Чит «бессмертие» | AGENTS.md, строка 645 | — | 3, 2 КБ | 2026-09-25 |  |
| `tools/grenade_hand_test.tscn` | Проверяет реальные Player/CameraRig, расход и физику | — | — | 5, 17 КБ | 2026-10-15 | нет в AGENTS.md |
| `tools/grenade_net_test.tscn` | Два настоящих ENet-процесса | — | — | 3, 7 КБ | 2026-10-19 | нет в AGENTS.md |
| `tools/grenade_window_test.tscn` | Открытое окно выше головы | — | — | 3, 10 КБ | 2026-10-15 | нет в AGENTS.md |
| `tools/hand_grip_test.tscn` | Настоящие игровые руки обоих типов | — | — | 3, 25 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/hideout_keys_test.tscn` | Клавиши под окном убежища | AGENTS.md, строка 618 | — | 3, 3 КБ | 2026-10-11 |  |
| `tools/holster_test.tscn` | Оружие убирается клавишей своего слота и достаётся ею же, бег быстрее | AGENTS.md, строка 621 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/hurt_direction_test.tscn` | Направление входящего урона через настоящий Player/Health/CameraRig | — | `tools/hurt_direction_test.gd` | 1, 185 Б | 2026-10-30 | нет в AGENTS.md |
| `tools/impact_net_test.tscn` | Два процесса | — | — | 3, 2 КБ | 2026-09-29 | нет в AGENTS.md |
| `tools/impact_test.tscn` | Проверяет реальный луч, слои выброса по поверхностям, пол под… | — | — | 3, 9 КБ | 2026-10-18 | нет в AGENTS.md |
| `tools/inventory_drag_test.tscn` | Регрессия | — | — | 3, 7 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/jump_test.tscn` | Настоящий ввод пробела и физика в убежище и рейде | — | — | 3, 4 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/light_keys_test.tscn` | Свет в руку | AGENTS.md, строка 151 | — | 3, 8 КБ | 2026-10-24 |  |
| `tools/loading_test.tscn` | Настоящие переходы меню → убежище → рейд → эвакуация, только с… | — | — | 3, 8 КБ | 2026-10-14 | нет в AGENTS.md |
| `tools/loadout_test.tscn` | Убежище → рейд со снаряжением → эвакуация → убежище (тестовый профиль) | AGENTS.md, строка 405 | — | 3, 16 КБ | 2026-10-26 | есть несохранённые правки |
| `tools/loot_net_test.tscn` | Два реальных ENet peer | — | — | 3, 7 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/loot_test.tscn` | Каталог, тематические броски, настоящая модель, отказ полного… | — | — | 3, 5 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/lumar_mounts_test.tscn` | Угловой ЛУМАР, запасное крепление на цевье и переключение реальным… | — | — | 3, 13 КБ | 2026-10-22 | нет в AGENTS.md |
| `tools/mags_test.tscn` | Магазины | AGENTS.md, строка 630 | — | 3, 17 КБ | 2026-11-01 |  |
| `tools/mall_1f_check.tscn` | Серый черновик ТЦ Ø200 | AGENTS.md, строка 175 | — | 3, 19 КБ | 2026-10-15 |  |
| `tools/metka4_test.tscn` | МЕТКА-4 через реальные операции сборки, сохранения, лута и… | — | — | 4, 16 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/nav_seams_test.tscn` | Швы тайлов навигации ТЦ, «Проспекта», зоны 1 (UrbanNavigation | AGENTS.md, строка 389 | — | 3, 17 КБ | 2026-10-31 |  |
| `tools/net_client_test.tscn` | Клиент для сетевого прогона | — | — | 3, 6 КБ | 2026-09-25 | нет в AGENTS.md |
| `tools/net_host_test.tscn` | Хост + tools/net_client_test.tscn в двух процессах | AGENTS.md, строка 596 | — | 3, 5 КБ | 2026-09-26 |  |
| `tools/npc_loot_test.tscn` | Лут с тела по видимому | AGENTS.md, строка 677 | — | 3, 5 КБ | 2026-10-24 |  |
| `tools/npc_outfit_test.tscn` | Внешность ботов по снаряжению (NpcOutfit) | AGENTS.md, строка 674 | — | 3, 8 КБ | 2026-10-24 |  |
| `tools/npc_rig_test.tscn` | Мародёр v03 на скелете Persona | AGENTS.md, строка 671 | — | 3, 16 КБ | 2026-10-24 |  |
| `tools/nvg_stress_test.tscn` | ПНВ в бою | AGENTS.md, строка 154 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/pm_net_test.tscn` | Сквозной ПМ по настоящему ENet | AGENTS.md, строка 445 | — | 3, 19 КБ | 2026-10-09 |  |
| `tools/pm_state_maps_test.tscn` | Вид оружия один (2026-10-19) | AGENTS.md, строка 432 | — | 3, 5 КБ | 2026-10-23 |  |
| `tools/pm_test.tscn` | ПМ: детали, LOD, патронник 8+1/8, прерывания и атомарный глушитель | AGENTS.md, строка 431 | — | 3, 28 КБ | 2026-10-24 |  |
| `tools/pm_worn_check.tscn` | ПМ «пошарпанный» в движке | AGENTS.md, строка 441 | — | 3, 14 КБ | 2026-10-23 |  |
| `tools/printer_quest_test.tscn` | Задание «Фирменный знак» | AGENTS.md, строка 629 | — | 3, 7 КБ | 2026-10-11 |  |
| `tools/prologue_test.tscn` | Пролог «Первый выход» на «Проспекте» (docs/design/prologue.md) | AGENTS.md, строка 124 | — | 3, 39 КБ | 2026-10-31 |  |
| `tools/prospekt_raid_check.tscn` | Рейд «Проспекта» | AGENTS.md, строка 331 | — | 3, 14 КБ | 2026-10-29 |  |
| `tools/quest_steps_test.tscn` | Шаги заказа машины в убежище | AGENTS.md, строка 122 | — | 3, 8 КБ | 2026-10-17 |  |
| `tools/quest_test.tscn` | Сюжет «Не вернулся» целиком | AGENTS.md, строка 120 | — | 3, 14 КБ | 2026-10-24 |  |
| `tools/ragdoll_test.tscn` | Трупы на модели (SkinRagdoll) не рвутся нитями | AGENTS.md, строка 118 | — | 3, 8 КБ | 2026-10-29 |  |
| `tools/raid_test.tscn` | Цикл рейда | AGENTS.md, строка 404 | — | 3, 6 КБ | 2026-10-24 |  |
| `tools/rain_test.tscn` | Дождь шейдерами | AGENTS.md, строка 159 | — | 3, 4 КБ | 2026-10-24 |  |
| `tools/reload_fast_test.tscn` | ВЕРАС со снаряжением | AGENTS.md, строка 147 | — | 3, 17 КБ | 2026-10-24 |  |
| `tools/rivals_fight_test.tscn` | Бой между группами | AGENTS.md, строка 158 | — | 3, 11 КБ | 2026-10-24 |  |
| `tools/rivals_test.tscn` | Чужие отряды («другие игроки») | AGENTS.md, строка 157 | — | 3, 13 КБ | 2026-10-24 |  |
| `tools/settings_test.tscn` | Настройки | AGENTS.md, строка 116 | — | 3, 8 КБ | 2026-10-24 |  |
| `tools/shared_fps_arms_test.tscn` | Один внешний вид рук у процедурных хватов, клипов ВЕРАСа,… | — | — | 3, 7 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/shelter_dressing_test.tscn` | Проверка загруженного художественного слоя, анимаций и общего… | — | — | 4, 10 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/shelter_exit_test.tscn` | Выход в рейд пешком | AGENTS.md, строка 628 | — | 3, 5 КБ | 2026-10-11 |  |
| `tools/shelter_net_end.tscn` | shelter net end | — | `tools/shelter_net_test.gd` | 1, 61 Б | 2026-10-05 | нет в AGENTS.md |
| `tools/shelter_net_test.tscn` | Три настоящих ENet процесса | — | — | 4, 8 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/shelter_test.tscn` | Acceptance-проверка migrated gameplay, профиль до ремейка,… | — | — | 3, 11 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/shooting_range_test.tscn` | Тир котельной | AGENTS.md, строка 415 | — | 3, 5 КБ | 2026-10-07 |  |
| `tools/shot_layers_test.tscn` | Слои дистанции выстрела | AGENTS.md, строка 661 | — | 3, 375 Б | 2026-10-21 |  |
| `tools/slung_test.tscn` | Снаряжение и убранное оружие на теле (NpcOutfit, SlungWeapons) | AGENTS.md, строка 622 | — | 3, 12 КБ | 2026-10-29 |  |
| `tools/sonora_weapon_contract_test.tscn` | Договор назначений | — | — | 1, 196 Б | 2026-10-21 | нет в AGENTS.md |
| `tools/step_up_test.tscn` | Ступеньки | — | — | 3, 2 КБ | 2026-10-10 | нет в AGENTS.md |
| `tools/steps_test.tscn` | Шаги | AGENTS.md, строка 92 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/stickers_test.tscn` | Наклейки на оружии | AGENTS.md, строка 626 | — | 3, 5 КБ | 2026-11-01 |  |
| `tools/story_test.tscn` | Хроника рейда | AGENTS.md, строка 634 | — | 3, 14 КБ | 2026-11-01 |  |
| `tools/stress_test.tscn` | Стресс | AGENTS.md, строка 647 | — | 3, 4 КБ | 2026-09-25 |  |
| `tools/templates_test.tscn` | Шаблоны снаряжения | AGENTS.md, строка 642 | — | 3, 3 КБ | 2026-10-26 |  |
| `tools/terminal_story_test.tscn` | Переписка в терминале | AGENTS.md, строка 121 | — | 3, 7 КБ | 2026-10-19 |  |
| `tools/trade_net_test.tscn` | Обмен вещами, два реальных ENet peer (порт 17793). Убежище | AGENTS.md, строка 616 | — | 3, 12 КБ | 2026-10-24 |  |
| `tools/trader_purchase_test.tscn` | Покупки | — | — | 3, 9 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/trader_ui_test.tscn` | Михалыч «Купить» | AGENTS.md, строка 643 | — | 3, 12 КБ | 2026-11-01 |  |
| `tools/tutorial_test.tscn` | Обучение новой игры | AGENTS.md, строка 123 | — | 3, 5 КБ | 2026-10-17 |  |
| `tools/unlock_test.tscn` | Чит «открыть всё» (Настройки / консоль unlock) | AGENTS.md, строка 646 | — | 3, 5 КБ | 2026-10-14 |  |
| `tools/urban_belt_launch_test.tscn` | «Городской пояс» — проверка запуска — Нужна только старому черновику. | — | — | 3, 1 КБ | 2026-10-16 | устарело, нет в AGENTS.md |
| `tools/valuable_loot_net_test.tscn` | valuable loot net test | — | — | 3, 7 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/valuable_loot_test.tscn` | Проверка каталога, вскрытия пачек, отказов сигнала и единственного… | — | — | 3, 8 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/vault_test.tscn` | Перелезание (игрок и мародёр по связке навигации), бросок на землю | AGENTS.md, строка 649 | — | 3, 6 КБ | 2026-09-26 |  |
| `tools/vehicle_test.tscn` | Транспорт | AGENTS.md, строка 644 | — | 3, 4 КБ | 2026-10-02 |  |
| `tools/veras54_mags_check.tscn` | Магазины 45/60 в движке | AGENTS.md, строка 468 | — | 3, 10 КБ | 2026-10-19 |  |
| `tools/veras_hand_test.tscn` | ВЕРАС-54, левая рука с рукоятками (ВАРН V1 и V2, на удлинителе) | AGENTS.md, строка 482 | — | 3, 4 КБ | 2026-11-01 |  |
| `tools/veras_load_test.tscn` | ВЕРАС с полной навеской | — | — | 3, 6 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/water_wade_test.tscn` | Брод в болоте зоны 1 | AGENTS.md, строка 112 | — | 3, 4 КБ | 2026-10-18 |  |
| `tools/weapon_condition_test.tscn` | Состояние не теряется в предметных операциях, хост считает износ,… | — | — | 3, 8 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/weapon_ik_net_test.tscn` | Три процесса ENet | — | — | 3, 7 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/weapon_ik_test.tscn` | Реальные Persona, оружие и камеры — Проверка на Persona — её владелец решил убрать (2026-10-29). | — | — | 1, 175 Б | 2026-10-05 | нет в AGENTS.md |
| `tools/weapon_pose_test.tscn` | Проверяет настоящие поля интерфейса, позу CameraRig, изоляцию… | — | — | 3, 7 КБ | 2026-11-02 | нет в AGENTS.md |
| `tools/weapon_sounds_test.tscn` | Звуки оружия от механики — Не в git, но записан в AGENTS.md — чья-то текущая работа. | AGENTS.md, строка 656 | — | 3, 378 Б | 2026-10-21 | не в git |
| `tools/weapon_switch_test.tscn` | ВЕРАС ↔ Glock | — | — | 3, 6 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/weather_test.tscn` | Погода | AGENTS.md, строка 145 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/wet_steps_test.tscn` | Записи владельца | — | — | 3, 6 КБ | 2026-10-11 | нет в AGENTS.md |
| `tools/workbench_repair_test.tscn` | Верстак, ремонт | AGENTS.md, строка 617 | — | 3, 4 КБ | 2026-11-01 |  |
| `tools/zone01_ld_test.tscn` | Пригород, левел-дизайн | AGENTS.md, строка 109 | — | 3, 8 КБ | 2026-10-19 |  |
| `tools/zone01_nw_test.tscn` | Реальные коллизии, доступ к добыче и связность первого игрового… | — | — | 3, 12 КБ | 2026-10-19 | нет в AGENTS.md |

## Снимки для просмотра (57)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `tools/ar15_shots.tscn` | ГРАНЬ-15 в руках (Пригород) | AGENTS.md, строка 565 | — | 3, 15 КБ | 2026-11-01 |  |
| `tools/asphalt_shots.tscn` | Мокрый асфальт | AGENTS.md, строка 165 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/blood_shots.tscn` | Кровь у стены в зоне 1 | AGENTS.md, строка 114 | — | 3, 13 КБ | 2026-10-15 |  |
| `tools/boiler_hall_shots.tscn` | Снимки котельной и тира в docs/screens/boiler_*.png… | AGENTS.md, строка 416 | — | 3, 3 КБ | 2026-10-07 |  |
| `tools/build_shots.tscn` | Снимки сборок | AGENTS.md, строка 585 | — | 3, 3 КБ | 2026-11-01 |  |
| `tools/builder_shots.tscn` | Конструктор оружия | AGENTS.md, строка 587 | — | 3, 3 КБ | 2026-10-26 |  |
| `tools/car_mall_sites_shots.tscn` | Места заказа «Вернуть машину» на карте ТЦ | AGENTS.md, строка 394 | — | 3, 10 КБ | 2026-10-19 |  |
| `tools/car_parts_shots.tscn` | «Пригород», автобаза | AGENTS.md, строка 137 | — | 3, 3 КБ | 2026-10-19 |  |
| `tools/car_radiator_shots.tscn` | Радиатор как предмет игры | AGENTS.md, строка 134 | — | 3, 3 КБ | 2026-10-19 |  |
| `tools/carry_shots.tscn` | Снимки стойки | AGENTS.md, строка 107 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/ceiling_shots.tscn` | Потолки и купол атриума | AGENTS.md, строка 173 | — | 3, 1 КБ | 2026-10-24 |  |
| `tools/coupe_ilya_shots.tscn` | Купе в движке | AGENTS.md, строка 142 | — | 3, 12 КБ | 2026-10-19 |  |
| `tools/engraving_shots.tscn` | Снимки станка и надписей на реальных моделях | — | — | 3, 4 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/flare_claude_shots.tscn` | Ракетница Claude в настоящей игровой камере — Не в git: чья-то незаконченная работа (ракетница Claude, 2026-10-11). | — | — | 8, 17.0 МБ | 2026-10-11 | не в git, нет в AGENTS.md |
| `tools/flare_pistol_shots.tscn` | Кадры настоящей игровой камеры и клипов рук ВЕРАС-54, не имитация UI. | — | — | 3, 4 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/flashlight_shots.tscn` | Фонари в паркинге «Проспекта» | — | — | 3, 7 КБ | 2026-10-29 | нет в AGENTS.md |
| `tools/glock_shots.tscn` | Glock | AGENTS.md, строка 581 | — | 3, 14 КБ | 2026-10-19 |  |
| `tools/grass_shots.tscn` | Трава | AGENTS.md, строка 113 | — | 3, 6 КБ | 2026-10-18 |  |
| `tools/hand_scale_shots.tscn` | Проба размера кистей от первого лица (вопрос владельца 2026-10-24… | — | — | 3, 5 КБ | 2026-10-26 | нет в AGENTS.md |
| `tools/hideout_shots.tscn` | Снимки убежища и его окон в docs/screens/hideout_*.png… | AGENTS.md, строка 413 | — | 3, 8 КБ | 2026-11-01 |  |
| `tools/info_shots.tscn` | Снимки окна описания предмета (info_*; ствол 47 % и прицел 30 % | AGENTS.md, строка 652 | — | 3, 3 КБ | 2026-10-26 |  |
| `tools/jump_shots.tscn` | Реальный прыжок в убежище | — | — | 3, 1 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/light_shots.tscn` | Заградительные огни (ночь/туман горят, ясный день | AGENTS.md, строка 160 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/light_tour.tscn` | Свет | AGENTS.md, строка 161 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/look_shots.tscn` | Вид «как с камеры» | AGENTS.md, строка 426 | — | 3, 7 КБ | 2026-10-24 |  |
| `tools/loot_shots.tscn` | Реальные точки лута двора зоны 1 | — | — | 3, 2 КБ | 2026-10-10 | нет в AGENTS.md |
| `tools/lumar_reticle_shots.tscn` | ЛУМАР | AGENTS.md, строка 631 | — | 3, 5 КБ | 2026-10-24 |  |
| `tools/lumar_shots.tscn` | Проверка игровых карт (вид один при прочности 100/60/20 | — | — | 3, 4 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/metka4_shots.tscn` | Проверочные кадры принятой модели в Forward+ | — | — | 3, 3 КБ | 2026-10-22 | нет в AGENTS.md |
| `tools/mosin_pu_shots.tscn` | Мосин 1891/30 ПУ в движке | — | — | 6, 95.2 МБ | 2026-10-19 | нет в AGENTS.md |
| `tools/pistol_shots.tscn` | Пистолет крупно | — | — | 3, 2 КБ | 2026-11-01 | нет в AGENTS.md |
| `tools/pm_shots.tscn` | ПМ: хват, ADS, фазы перезарядки/глушителя, третье лицо в… | AGENTS.md, строка 444 | — | 3, 14 КБ | 2026-10-19 |  |
| `tools/prospekt_raid_shots.tscn` | Свет «Проспекта» в рейде глазами игрока (привыкание глаза, «объектив») | AGENTS.md, строка 335 | — | 3, 5 КБ | 2026-10-29 |  |
| `tools/quest_shots.tscn` | Снимки сюжета | AGENTS.md, строка 400 | — | 3, 2 КБ | 2026-10-24 |  |
| `tools/region_map_shots.tscn` | Схема района в «Плане рейда» (RegionMapView) | AGENTS.md, строка 411 | — | 3, 1 КБ | 2026-10-31 |  |
| `tools/rig_shots.tscn` | Ростовая фигура со слотами и подсумки на броне (магазины, сброс… | AGENTS.md, строка 614 | — | 3, 5 КБ | 2026-11-01 |  |
| `tools/scope_far_shots.tscn` | Сильная оптика на планке над цевьём | AGENTS.md, строка 589 | — | 3, 2 КБ | 2026-10-24 |  |
| `tools/scope_sun_shots.tscn` | Оптика против солнца (блики, аберрация) и открытые прицельные из глаза | AGENTS.md, строка 590 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/shelter_dressing_shots.tscn` | Крупные планы готовых предметов и последовательность запечённого пара. | — | — | 3, 2 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/shelter_shots.tscn` | Фиксированные ракурсы finished interior | — | — | 3, 3 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/sight_nvg_shots.tscn` | Коллиматор в ПНВ, ЛЦУ | AGENTS.md, строка 632 | — | 3, 4 КБ | 2026-10-24 |  |
| `tools/sky_compare_shots.tscn` | Небо из панорам и расчётное с облаками (Esc → Читы → Мир → «Небо») | AGENTS.md, строка 170 | — | 3, 10 КБ | 2026-10-18 |  |
| `tools/sky_flare_shots.tscn` | Осветительная ракета из сигнального пистолета во дворе зоны 1 ночью | AGENTS.md, строка 155 | — | 3, 5 КБ | 2026-10-18 |  |
| `tools/terminal_shots.tscn` | Терминал связи | — | — | 3, 1 КБ | 2026-10-07 | нет в AGENTS.md |
| `tools/thumb_shots.tscn` | Миниатюры экземпляров в сетке рюкзака (сборка, вынутый магазин,… | AGENTS.md, строка 586 | — | 3, 2 КБ | 2026-10-26 |  |
| `tools/trailer_capture.tscn` | Запись трейлера | — | — | 3, 6 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/tv_light_shots.tscn` | Свет от телевизора ночью без генератора | AGENTS.md, строка 619 | — | 3, 4 КБ | 2026-10-11 |  |
| `tools/ui_shots.tscn` | Снимки | AGENTS.md, строка 402 | — | 3, 4 КБ | 2026-11-01 |  |
| `tools/valuable_loot_shots.tscn` | valuable loot shots | — | — | 3, 4 КБ | 2026-10-10 | нет в AGENTS.md |
| `tools/veras54_mags_vm_shots.tscn` | Магазины 45/60 в руках | AGENTS.md, строка 474 | — | 3, 8 КБ | 2026-10-24 |  |
| `tools/veras_gloss_shots.tscn` | ВЕРАС-54 под лампами тира | AGENTS.md, строка 483 | — | 3, 4 КБ | 2026-10-19 |  |
| `tools/veras_outdoor_shots.tscn` | ВЕРАС-54 днём под небом (Пригород) | AGENTS.md, строка 485 | — | 3, 3 КБ | 2026-10-19 |  |
| `tools/veras_shots.tscn` | ВЕРАС-54 от первого лица | AGENTS.md, строка 478 | — | 3, 26 КБ | 2026-11-01 |  |
| `tools/vss_shots.tscn` | ВСС-М в руках днём (Пригород) | AGENTS.md, строка 492 | — | 3, 13 КБ | 2026-10-27 |  |
| `tools/weapon_ik_hideout_shots.tscn` | Снимки и короткий проход к настоящей стене убежища, отдельный профиль. | — | — | 3, 2 КБ | 2026-10-05 | нет в AGENTS.md |
| `tools/zone01_nw_shots.tscn` | Снимки согласованного фрагмента из реального Forward+, без… | — | — | 3, 4 КБ | 2026-10-18 | нет в AGENTS.md |
| `tools/zone01_shots.tscn` | Снимки зоны 1 «Пригород» в docs/screens/zone01_*.png | — | — | 3, 11 КБ | 2026-10-19 | нет в AGENTS.md |

## Замеры скорости (10)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `tools/ai_work_benchmark.tscn` | Живые 24 NPC на готовой карте, одинаковое зерно, без событий и… | — | — | 3, 4 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/cpu_probe.tscn` | Во что упирается процессор на уровне | AGENTS.md, строка 611 | — | 3, 4 КБ | 2026-10-24 |  |
| `tools/mall_ground_perf.tscn` | Покрытия и бетон территории ТЦ (MallGround, шейдеры paved_ground,… | AGENTS.md, строка 392 | — | 3, 5 КБ | 2026-10-19 |  |
| `tools/mesh_census.tscn` | Какие модели дают треугольники на уровне | AGENTS.md, строка 613 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/perf_test.tscn` | FPS / вызовы отрисовки в изометрии и в прицеле по точкам | AGENTS.md, строка 403 | — | 3, 3 КБ | 2026-10-24 |  |
| `tools/performance_audit.tscn` | Штатная загрузка и кадры в фиксированных точках всех готовых карт | — | — | 3, 10 КБ | 2026-10-24 | нет в AGENTS.md |
| `tools/prospekt_city_perf.tscn` | Замер кадров в секунду на «Проспекте» там, где стоят ограждения и… | — | — | 3, 4 КБ | 2026-10-29 | нет в AGENTS.md |
| `tools/prospekt_plants_perf.tscn` | Кадры в секунду у растений «Проспекта» (сквер, берёзы, тополя, сверху) | AGENTS.md, строка 373 | — | 3, 3 КБ | 2026-10-26 |  |
| `tools/prospekt_vehicles_perf.tscn` | Кадры в секунду у транспорта «Проспекта» (паркинг −1, стоянки,… | AGENTS.md, строка 365 | — | 3, 8 КБ | 2026-10-31 |  |
| `tools/zone01_trees_perf.tscn` | Клёны и тополя зоны 1 | AGENTS.md, строка 381 | — | 3, 7 КБ | 2026-10-29 |  |

## Сборка и служебное (15)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `tools/author_loose_loot.tscn` | Авторские точки находок городских карт | — | — | 3, 3 КБ | 2026-10-18 | нет в AGENTS.md |
| `tools/author_shelter_dressing.tscn` | Добавляет законченный художественный слой к существующей сцене,… | AGENTS.md, строка 417 | — | 4, 89 КБ | 2026-10-11 |  |
| `tools/author_shelter_exterior.tscn` | Офлайн-авторинг двора котельной (убежище снаружи) | AGENTS.md, строка 417 | — | 3, 23 КБ | 2026-10-11 |  |
| `tools/author_shelter_grime.tscn` | Офлайн-авторинг | AGENTS.md, строка 417 | — | 3, 13 КБ | 2026-10-07 |  |
| `tools/author_shelter_scene.tscn` | Офлайн-авторинг | AGENTS.md, строка 417 | — | 1, 165 Б | 2026-10-05 |  |
| `tools/bake_mall_nav.tscn` | Рейдовая карта ТЦ (scenes/levels/mall_map.tscn = черновик… | AGENTS.md, строка 387 | `data/sectors/mall_map.json` | 3, 1 КБ | 2026-10-19 |  |
| `tools/bake_prospekt_nav.tscn` | Перепечь кэш навигации data/navigation/prospekt после правки блокаута | AGENTS.md, строка 330 | `data/sectors/prospekt.json` | 3, 1 КБ | 2026-10-25 |  |
| `tools/bake_zone01_nav.tscn` | Перепечь навигацию после ручного изменения городской планировки,… | — | — | 3, 976 Б | 2026-10-07 | нет в AGENTS.md |
| `tools/export_weapon_refs.tscn` | Все стволы игры (и ГРАНЬ-15 с обвесами под левую руку) в GLB | AGENTS.md, строка 582 | — | 3, 5 КБ | 2026-11-01 |  |
| `tools/hand_fit_dump.tscn` | Выгрузка рук для подгонки хвата | — | — | 5, 47.5 МБ | 2026-11-01 | нет в AGENTS.md |
| `tools/icon_bake.tscn` | Иконки предметов (ItemModels) в assets/icons/<id>.png, затем --import | AGENTS.md, строка 427 | — | 3, 4 КБ | 2026-10-31 |  |
| `tools/raid_map_bake.tscn` | Карты маршрутов для окна «План рейда» | AGENTS.md, строка 408 | `data/raid_maps.json` | 3, 6 КБ | 2026-10-31 |  |
| `tools/sector_stats.tscn` | Сводка сборки сектора (стены, двери, огни) | AGENTS.md, строка 398 | — | 3, 1 КБ | 2026-10-24 |  |
| `tools/smoke.tscn` | Быстрый снимок любой сцены | Запускалка tools/smoke.cmd | `tools/smoke.cmd` | 3, 3 КБ | 2026-09-23 | не убирать, нет в AGENTS.md |
| `tools/sticker_icons.tscn` | Иконки наклеек из их рисунков (assets/stickers/<id>.png владельца… | AGENTS.md, строка 627 | — | 3, 1 КБ | 2026-10-11 |  |

## Детали карт, предметов и персонажа (50)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `assets/models/attachments/lumar_h1/lumar_h1.tscn` | lumar h1 | — | `data/weapons.json` | 3, 12.8 МБ | 2026-10-19 |  |
| `scenes/ai/marauder.tscn` | marauder | — | `src/debug/perception_lab.gd`, `src/world/sector_level.gd`, `tools/ai_reaction_test.gd`, `tools/ai_squad_test.gd` и ещё 15 | 1, 2 КБ | 2026-10-29 |  |
| `scenes/combat/impact_burst.tscn` | Одно попадание слоями | — | `src/combat/impact_fx.gd` | 1, 682 Б | 2026-10-18 |  |
| `scenes/debug/development_lab_base.tscn` | Основа отладочных стендов | Входит в scenes/debug/atmosphere_lab.tscn, scenes/debug/impact_lab.tscn, scenes/debug/perception_lab.tscn | `scenes/debug/atmosphere_lab.tscn`, `scenes/debug/impact_lab.tscn`, `scenes/debug/perception_lab.tscn` | 1, 3 КБ | 2026-10-23 | не убирать |
| `scenes/hideout/laser_engraver.tscn` | laser engraver | Входит в scenes/levels/hideout.tscn | `scenes/levels/hideout.tscn` | 3, 2 КБ | 2026-10-11 |  |
| `scenes/items/metka4_loot.tscn` | Точка одной физической находки. Корень стоит на поверхности, модель | — | `tools/metka4_test.gd` | 1, 217 Б | 2026-10-22 |  |
| `scenes/levels/mall/car_recovery_sites.tscn` | car recovery sites | Входит в scenes/levels/mall_map.tscn | `data/quests/car_recovery.json`, `data/sectors/mall_map.json`, `scenes/levels/mall_map.tscn` | 12, 24.6 МБ | 2026-10-19 |  |
| `scenes/levels/zone01/zone01_ai.tscn` | zone01 ai | — | `data/navigation/zone01/manifest.json`, `data/sectors/zone01_mall.json` | 1, 8 КБ | 2026-10-19 |  |
| `scenes/levels/zone01/zone01_blockout.tscn` | zone01 blockout | Входит в scenes/levels/zone01_mall.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01_mall.tscn` | 1, 4 КБ | 2026-10-18 |  |
| `scenes/levels/zone01/zone01_car_recovery_sites.tscn` | zone01 car recovery sites | Входит в scenes/levels/zone01_mall.tscn | `data/navigation/zone01/manifest.json`, `data/quest_sites/car_recovery_belt.json`, `data/quests/car_recovery.json`, `scenes/levels/zone01_mall.tscn` | 3, 5 КБ | 2026-10-19 |  |
| `scenes/levels/zone01/zone01_houses12.tscn` | zone01 houses12 | Входит в scenes/levels/zone01/zone01_blockout.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_blockout.tscn` | 14, 9.3 МБ | 2026-10-18 |  |
| `scenes/levels/zone01/zone01_layout.tscn` | zone01 layout | Входит в scenes/levels/zone01_mall.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01_mall.tscn` | 1, 403 КБ | 2026-10-19 |  |
| `scenes/levels/zone01/zone01_loose_loot.tscn` | zone01 loose loot | — | `data/navigation/zone01/manifest.json`, `data/sectors/zone01_mall.json` | 1, 1 КБ | 2026-10-18 |  |
| `scenes/levels/zone01/zone01_market06.tscn` | zone01 market06 | Входит в scenes/levels/zone01/zone01_blockout.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_blockout.tscn` | 28, 1.5 МБ | 2026-10-18 |  |
| `scenes/levels/zone01/zone01_world.tscn` | zone01 world | Входит в scenes/levels/zone01_mall.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01_mall.tscn` | 24, 26.0 МБ | 2026-10-29 |  |
| `scenes/levels/zone01/zone01_yard05.tscn` | zone01 yard05 | Входит в scenes/levels/zone01_mall.tscn | `data/navigation/zone01/manifest.json`, `data/sectors/zone01_mall.json`, `scenes/levels/zone01_mall.tscn`, `tools/author_loose_loot.gd` | 31, 22.3 МБ | 2026-10-29 |  |
| `scenes/levels/zone01/zone01_yard05_gameplay.tscn` | zone01 yard05 gameplay | Входит в scenes/levels/zone01/zone01_yard05.tscn | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_yard05.tscn`, `tools/author_loose_loot.gd` | 9, 582 КБ | 2026-10-15 |  |
| `scenes/player/camera_rig.tscn` | camera rig | Входит в levels/shelter/Hideout_Legacy.tscn, levels/shelter/Shelter_Interior.tscn, scenes/debug/development_lab_base.tscn и ещё 5 | `levels/shelter/Hideout_Legacy.tscn`, `levels/shelter/Shelter_Interior.tscn`, `scenes/debug/development_lab_base.tscn`, `scenes/debug/weapon_pose_lab.tscn` и ещё 15 | 1, 513 Б | 2026-09-26 |  |
| `scenes/player/first_person_arms.tscn` | Кисти и рукава ВЕРАС-54 для оружия без собственных клипов рук | — | `src/player/camera_rig.gd`, `tools/arms_gallery.gd`, `tools/glock_shots.gd`, `tools/hand_fit_dump.gd` и ещё 2 | 1, 237 Б | 2026-10-07 |  |
| `scenes/player/player.tscn` | player | Входит в scenes/debug/development_lab_base.tscn, scenes/debug/weapon_pose_lab.tscn | `scenes/debug/development_lab_base.tscn`, `scenes/debug/weapon_pose_lab.tscn`, `src/hideout/hideout_level.gd`, `src/world/sector_level.gd` и ещё 27 | 1, 2 КБ | 2026-10-29 |  |
| `scenes/props/coupe_ilya.tscn` | Машина Ильи (заказ «Вернуть машину») | Входит в scenes/levels/zone01/zone01_car_recovery_sites.tscn | `scenes/levels/zone01/zone01_car_recovery_sites.tscn`, `tools/coupe_ilya_shots.gd`, `tools/scale_probe.gd` | 3, 56.3 МБ | 2026-10-19 |  |
| `scenes/props/coupe_ilya_trim_fragment.tscn` | coupe ilya trim fragment | Входит в scenes/levels/mall/car_recovery_sites.tscn | `scenes/levels/mall/car_recovery_sites.tscn` | 9, 24.0 МБ | 2026-10-19 |  |
| `scenes/props/door.tscn` | Дверь-створка | Входит в scenes/levels/prospekt.tscn | `scenes/levels/prospekt.tscn`, `src/blockout/study_building.gd`, `src/world/blockout_building.gd`, `src/world/sector_builder.gd` | 1, 441 Б | 2026-09-21 |  |
| `scenes/props/roll_gate.tscn` | Ворота-роллета в проёме (рампа склада «Яруса»,… | Входит в scenes/levels/prospekt.tscn | `scenes/levels/prospekt.tscn` | 1, 157 Б | 2026-10-31 |  |
| `scenes/props/shopping_cart.tscn` | shopping cart | — | `src/world/props.gd`, `tools/cart_net_test.gd`, `tools/cart_test.gd` | 1, 2 КБ | 2026-10-02 |  |
| `scenes/ui/detection_indicator.tscn` | Подтверждённое обнаружение своим врагом | — | `src/player/camera_rig.gd` | 1, 594 Б | 2026-10-30 |  |
| `scenes/world/ai_arrival.tscn` | Точка подхода (docs/design/enemy_population.md) | Входит в scenes/levels/mall_1f.tscn, scenes/levels/prospekt.tscn, scenes/levels/zone01/zone01_ai.tscn | `scenes/levels/mall_1f.tscn`, `scenes/levels/prospekt.tscn`, `scenes/levels/zone01/zone01_ai.tscn` | 1, 162 Б | 2026-10-14 |  |
| `scenes/world/ai_nest.tscn` | Гнездо снайпера (слой «движение», docs/design/enemy_population.md) | Входит в scenes/levels/prospekt.tscn, scenes/levels/zone01/zone01_ai.tscn | `scenes/levels/prospekt.tscn`, `scenes/levels/zone01/zone01_ai.tscn` | 1, 156 Б | 2026-10-14 |  |
| `scenes/world/ai_post.tscn` | Пост гарнизона (слой «гарнизоны мест»,… | Входит в scenes/levels/mall_1f.tscn, scenes/levels/prospekt.tscn, scenes/levels/zone01/zone01_ai.tscn | `scenes/levels/mall_1f.tscn`, `scenes/levels/prospekt.tscn`, `scenes/levels/zone01/zone01_ai.tscn` | 1, 156 Б | 2026-10-14 |  |
| `scenes/world/ai_route.tscn` | Маршрут патруля (слой «движение», docs/design/enemy_population.md) | Входит в scenes/levels/mall_1f.tscn, scenes/levels/prospekt.tscn, scenes/levels/zone01/zone01_ai.tscn | `scenes/levels/mall_1f.tscn`, `scenes/levels/prospekt.tscn`, `scenes/levels/zone01/zone01_ai.tscn` | 1, 156 Б | 2026-10-14 |  |
| `scenes/world/blockout_building.tscn` | Постройка-блокаут вне кольца | — | `data/navigation/mall_map/manifest.json`, `data/navigation/prospekt/manifest.json`, `data/navigation/zone01/manifest.json`, `src/world/urban_navigation.gd` | 1, 177 Б | 2026-09-23 |  |
| `scenes/world/blockout_opening.tscn` | Дверь или ворота в стене постройки-блокаута | — | `data/navigation/mall_map/manifest.json`, `data/navigation/prospekt/manifest.json`, `data/navigation/zone01/manifest.json`, `src/world/urban_navigation.gd` | 1, 175 Б | 2026-09-23 |  |
| `scenes/world/escalator.tscn` | Эскалаторы блокаута | Входит в scenes/levels/mall_1f.tscn, scenes/levels/mall_study.tscn | `scenes/levels/mall_1f.tscn`, `scenes/levels/mall_study.tscn` | 1, 162 Б | 2026-09-23 |  |
| `scenes/world/extraction_point.tscn` | Точка эвакуации | Входит в scenes/levels/mall_1f.tscn, scenes/levels/mall_map.tscn, scenes/levels/prospekt.tscn и ещё 1 | `scenes/levels/mall_1f.tscn`, `scenes/levels/mall_map.tscn`, `scenes/levels/prospekt.tscn`, `scenes/levels/zone01_mall.tscn` | 1, 177 Б | 2026-09-23 |  |
| `scenes/world/f1_mall_power.tscn` | f1 mall power | — | — | 1, 594 Б | 2026-09-26 |  |
| `scenes/world/gate_warden.tscn` | Ворота кордона (docs/design/prologue.md §8 | Входит в scenes/levels/prospekt.tscn | `scenes/levels/prospekt.tscn` | 1, 163 Б | 2026-10-31 |  |
| `scenes/world/hideout_activity.tscn` | Досуг в убежище (F рядом) | Входит в levels/shelter/Hideout_Lounge_Legacy.tscn, scenes/world/hideout_lounge.tscn | `levels/shelter/Hideout_Lounge_Legacy.tscn`, `scenes/world/hideout_lounge.tscn` | 1, 190 Б | 2026-09-25 |  |
| `scenes/world/hideout_lounge.tscn` | Занятия в убежище — Код убежища ещё ссылается на неё — убирать только через агента. | — | `src/hideout/hideout_level.gd` | 1, 1 КБ | 2026-09-25 |  |
| `scenes/world/hideout_station.tscn` | Станция старого убежища — Убирать после «Старого убежища». | Входит в levels/shelter/Hideout_Legacy.tscn | `levels/shelter/Hideout_Legacy.tscn` | 1, 175 Б | 2026-09-23 | устарело |
| `scenes/world/key_pickup.tscn` | Ключ / карта-ключ на полу. Подобрал | — | `data/audio_actions.json`, `data/audio_events.json`, `src/blockout/study_building.gd`, `src/world/urban_navigation.gd` | 1, 163 Б | 2026-09-23 |  |
| `scenes/world/ladder.tscn` | Вертикальная лестница | — | `data/blockouts/dorm.json`, `src/world/urban_navigation.gd`, `tools/climb_test.gd` | 1, 156 Б | 2026-10-24 |  |
| `scenes/world/loose_loot.tscn` | Точка одной физической находки. Корень стоит на поверхности, модель | Входит в scenes/levels/zone01/zone01_houses12.tscn, scenes/levels/zone01/zone01_loose_loot.tscn, scenes/levels/zone01/zone01_market06.tscn и ещё 1 | `scenes/levels/zone01/zone01_houses12.tscn`, `scenes/levels/zone01/zone01_loose_loot.tscn`, `scenes/levels/zone01/zone01_market06.tscn`, `scenes/levels/zone01/zone01_yard05_gameplay.tscn` и ещё 4 | 1, 172 Б | 2026-10-10 |  |
| `scenes/world/loot_container.tscn` | То, что обыскивают | Входит в scenes/levels/prospekt.tscn, scenes/levels/zone01/zone01_houses12.tscn, scenes/levels/zone01/zone01_market06.tscn и ещё 1 | `scenes/levels/prospekt.tscn`, `scenes/levels/zone01/zone01_houses12.tscn`, `scenes/levels/zone01/zone01_market06.tscn`, `scenes/levels/zone01/zone01_yard05_gameplay.tscn` и ещё 3 | 1, 171 Б | 2026-09-23 |  |
| `scenes/world/power_switch.tscn` | Рубильник | Входит в scenes/levels/prospekt.tscn | `data/audio_actions.json`, `data/audio_events.json`, `scenes/levels/prospekt.tscn`, `src/world/urban_navigation.gd` | 1, 167 Б | 2026-09-23 |  |
| `scenes/world/rubble_pile.tscn` | Завал блокаута | Входит в scenes/levels/mall_1f.tscn, scenes/levels/mall_study.tscn | `data/blockouts/dorm.json`, `scenes/levels/mall_1f.tscn`, `scenes/levels/mall_study.tscn`, `src/world/urban_navigation.gd` | 1, 165 Б | 2026-10-15 |  |
| `scenes/world/spawn_point.tscn` | Точка появления группы. Уровень выбирает одну случайную на рейд | Входит в scenes/levels/mall_1f.tscn, scenes/levels/mall_map.tscn, scenes/levels/prospekt.tscn и ещё 1 | `scenes/levels/mall_1f.tscn`, `scenes/levels/mall_map.tscn`, `scenes/levels/prospekt.tscn`, `scenes/levels/zone01_mall.tscn` | 1, 167 Б | 2026-09-23 |  |
| `scenes/world/street_lamp.tscn` | Уличный фонарь | — | — | 1, 178 Б | 2026-09-24 |  |
| `scenes/world/supply_flight.tscn` | Только изображение общего сигнала | — | `src/world/raid.gd` | 1, 178 Б | 2026-10-10 |  |
| `scenes/world/urban_props.tscn` | Редактируемый блок статических примитивов | Входит в scenes/levels/zone01/zone01_layout.tscn, scenes/levels/zone01/zone01_world.tscn | `data/navigation/mall_map/manifest.json`, `data/navigation/prospekt/manifest.json`, `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_layout.tscn` и ещё 2 | 1, 174 Б | 2026-10-05 |  |
| `scenes/world/urban_road.tscn` | Полилиния реальной улицы | Входит в scenes/levels/zone01/zone01_world.tscn | `data/navigation/mall_map/manifest.json`, `data/navigation/prospekt/manifest.json`, `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_world.tscn` и ещё 1 | 1, 172 Б | 2026-10-05 |  |

## Детали убежища (204)

Вставляются в сцены убежища. Всего 204, никем не используются — 18:

- `levels/shelter/props/Bench.tscn` — 38 КБ
- `levels/shelter/props/Binoculars.tscn` — 84 КБ
- `levels/shelter/props/Boots.tscn` — 58 КБ
- `levels/shelter/props/CardboardBox.tscn` — 49 КБ
- `levels/shelter/props/Case.tscn` — 50 КБ
- `levels/shelter/props/Chair.tscn` — 50 КБ
- `levels/shelter/props/CoffeeTable.tscn` — 38 КБ
- `levels/shelter/props/Couch.tscn` — 138 КБ
- `levels/shelter/props/DeskLamp.tscn` — 38 КБ
- `levels/shelter/props/Display_wpn_ar_03.tscn` — 178 КБ
- `levels/shelter/props/Display_wpn_hg_01.tscn` — 244 КБ
- `levels/shelter/props/FoodCan.tscn` — 33 КБ
- `levels/shelter/props/JerryCan.tscn` — 24 КБ
- `levels/shelter/props/MedicalCase.tscn` — 9 КБ
- `levels/shelter/props/PH_DrillPress.tscn` — 1.5 МБ
- `levels/shelter/props/PH_Sledgehammer.tscn` — 100 КБ
- `levels/shelter/props/PH_Thermos.tscn` — 348 КБ
- `levels/shelter/props/Radio.tscn` — 73 КБ

## Запускалки без своей сцены (10)

| Сцена | Что это | Откуда запускают | Живые ссылки | Своих файлов | Правка | Пометки |
|---|---|---|---|---|---|---|
| `EDITOR.cmd` | Редактор Godot | — | — | 1, 1 КБ | 2026-10-18 | не убирать |
| `RING.cmd` | Игра | — | — | 1, 1 КБ | 2026-10-18 | не убирать |
| `SCENE_BOARD.cmd` | Доска сцен | — | — | 1, 578 Б | — | не убирать |
| `tools/build_patch.cmd` | Обновление для друзей | — | `tools/build_release.cmd` | 1, 1 КБ | 2026-10-24 | не убирать |
| `tools/build_release.cmd` | Сборка для друзей | — | `tools/build_patch.cmd` | 1, 1 КБ | 2026-10-24 | не убирать |
| `tools/finish_grenade_cast_v08.cmd` | Граната — доводка отливки v08 | — | — | 1, 86 Б | 2026-10-13 |  |
| `tools/godot.cmd` | Godot (служебная) | — | `HAND_GRIP_LAB.cmd`, `IMPACT_LAB.cmd`, `LIGHT_LAB.cmd`, `PERCEPTION_LAB.cmd` и ещё 1 | 1, 1 КБ | 2026-10-18 | не убирать |
| `tools/pm_grip_rebuild.cmd` | ПМ — пересборка хвата | — | — | 1, 2 КБ | 2026-10-20 |  |
| `tools/release_fast_start.cmd` | Быстрый старт сборки | — | — | 1, 367 Б | 2026-09-24 | не убирать |
| `tools/smoke.cmd` | Снимок сцены (служебная) | Открывает scenes/levels/mall_map.tscn; Открывает tools/smoke.tscn | — | 1, 439 Б | 2026-10-24 | не убирать |

## Удалены в рабочей копии, но не из git

- `tools/sound_bench.tscn`
- `tools/sound_bench_test.tscn`

## Данные карт (data/blockouts, data/sectors)

| Файл | Чей | Кто читает | Размер | Правка |
|---|---|---|---|---|
| `data/blockouts/dorm.json` | общий | `src/blockout/dorm_geometry.gd`, `src/blockout/dorm_lighting.gd`, `tools/build_dorm.py`, `tools/dorm_light_archive.py` | 2.8 МБ | 2026-11-02 |
| `data/blockouts/dorm_decals.json` | общий | `src/blockout/dorm_geometry.gd`, `tools/dorm_modules/gen_dorm_decals.py` | 4 КБ | 2026-10-30 |
| `data/blockouts/dorm_electrics.json` | общий | `src/blockout/dorm_electrics.gd`, `tools/dorm_modules/electrify.py` | 401 КБ | 2026-11-02 |
| `data/blockouts/dorm_found_lights.json` | общий | `src/blockout/dorm_geometry.gd`, `tools/dorm_light_placer.gd` | 2 КБ | 2026-10-31 |
| `data/blockouts/dorm_furniture.json` | общий | `src/blockout/dorm_geometry.gd`, `tools/dorm_modules/furnish_rooms.py` | 58 КБ | 2026-11-02 |
| `data/blockouts/dorm_props.json` | общий | `src/blockout/dorm_geometry.gd` | 6 КБ | 2026-10-31 |
| `data/blockouts/dorm_voxel/.gitattributes` | общий | — | 42 Б | 2026-10-28 |
| `data/blockouts/dorm_voxel/annex_1.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 618 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/annex_2.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 537 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/annex_3.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 537 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/annex_4.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 537 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/bake.json` | `scenes/levels/dorm_study.tscn` | `src/blockout/dorm_lighting.gd` | 2 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/floor_1.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 878 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/floor_2.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 803 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/floor_3.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 793 КБ | 2026-11-02 |
| `data/blockouts/dorm_voxel/floor_4.res` | общий | `data/blockouts/dorm.json`, `data/blockouts/dorm_voxel/bake.json` | 818 КБ | 2026-11-02 |
| `data/blockouts/mall_study.json` | общий | `data/navigation/mall_map/manifest.json`, `src/blockout/mall_landscape.gd`, `src/world/urban_navigation.gd`, `tools/build_mall_study.py` | 725 КБ | 2026-10-17 |
| `data/blockouts/prospekt.json` | общий | `data/navigation/prospekt/manifest.json`, `src/blockout/prospekt_landscape.gd`, `src/world/urban_navigation.gd`, `tools/build_prospekt.py` | 687 КБ | 2026-10-31 |
| `data/blockouts/urban_belt_study.json` | общий | `src/blockout/study_landscape.gd` | 33 КБ | 2026-10-16 |
| `data/sectors/README.md` | общий | — | 92 Б | 2026-09-21 |
| `data/sectors/mall_1f.json` | общий | `data/blockouts/mall_study.json`, `data/navigation/mall_map/manifest.json`, `scenes/levels/mall_1f.tscn`, `src/blockout/mall_ring.gd` | 59 КБ | 2026-10-15 |
| `data/sectors/mall_map.json` | общий | `data/navigation/mall_map/manifest.json`, `scenes/levels/mall_map.tscn`, `src/world/sector_level.gd`, `src/world/urban_navigation.gd` | 2 КБ | 2026-10-19 |
| `data/sectors/prospekt.json` | общий | `data/navigation/prospekt/manifest.json`, `scenes/levels/prospekt.tscn`, `src/world/urban_navigation.gd`, `tools/bake_prospekt_nav.gd` | 1 КБ | 2026-10-29 |
| `data/sectors/zone01_mall.json` | общий | `data/navigation/zone01/manifest.json`, `scenes/levels/zone01/zone01_world.tscn`, `scenes/levels/zone01_mall.tscn`, `src/debug/development_lab.gd` | 22 КБ | 2026-10-29 |
