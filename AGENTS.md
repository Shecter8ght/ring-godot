# RING — правила проекта для любого агента (Claude, Codex, локальные модели)

Тактический extraction-шутер от первого лица (изометрии нет — обзор сверху только у разведдрона, docs/design/drone.md). Godot 4.7, GDScript, Forward+.
Кооп на 3 игроков (один хостит). Реализм в графике: PBR, фототекстуры (CC0), реальные пропорции.

## Мир

Торговый центр в форме **идеального кольца**, 4 этажа = 4 карты (1F якоря/маркет/логистика,
2F фуд-корт/сервисы/медицина, 3F одежда/офисы, 4F премиум/кино/крыша с вертолётной площадкой).
Этажи внутри отрезаны (опущены противопожарные шторы, лестницы заварены) — у каждого свой путь
снаружи; этаж выбирается в убежище как маршрут, верхние открывает торговец за доверие и деньги
(`docs/design/floors.md`, `data/floors.json`, `Floors`).
Кольцо поделено на **6 секторов по 60°**; в текущей версии открыты **3 сектора**, остальные заперты
(роллеты/двери непроходимы, но видны). Эвакуация — только из открытых секторов.

Геометрия кольца (одна на все этажи, менять дорого; решение владельца 2026-09-23):
внешний диаметр **250 м**, крытый атриум Ø60 под куполом (r 0–30), галерея атриума r 30–40,
внутренние магазины r 40–65, кольцевая улица r 65–79, внешние магазины r 79–109, подсобки
r 109–121, служебный коридор r 121–125, снаружи — проезд, площадь, дворы, постройки до забора
участка r 210. **Один вход для посетителей — с севера:** прямая главная аллея 24 м от фасада
до галереи атриума (вестибюль, аллея с парой эскалаторов, перекрёсток с кольцевой улицей,
аллея до атриума); вдоль неё — торговые модули с витринами на аллею. Остальные выходы —
пожарные и грузовые. На границах отсеков — поперечные проходы с техядрами, в боковых отсеках —
радиальный проход к выходу (к паркингу / грузовому шлюзу). Открыты 3 сектора a ∈ [-180°, 0°]
(север = a -90°, вверху плана). Высота 1F — 6 м, здание 4 этажа (22.5 м). Координаты полярные:
угол a (град, от +X к +Z), радиус r (м); помещение = кольцевой сектор [a0,a1]×[r0,r1] или полоса
вдоль оси (axis, t, r — см. SectorBuilder). Уровень: `data/sectors/f1_ring.json` (генератор —
`python tools/gen_f1_ring.py`) + `scenes/levels/f1_ring.tscn`.
Старый маленький сектор `f1_market` (Ø180) оставлен для тестов (ai_test, fx_test).

**Блокаут.** Сейчас уровень — серый блокаут (`"greybox": true`): стены без текстур, толщина по
классу конструкции (фасад 0.5 / противопожарная 0.3 / несущая 0.3 / перегородка 0.15), нормы и
источники — `docs/building_standards.md`. Чертёж сверху: `python tools/plan_svg.py data/sectors/f1_ring.json`
→ `docs/plans/f1_ring.svg` (берёт кольцо из JSON, постройки и точки — из .tscn уровня).

Атмосфера базовая: лето, ~20:00, закат, сухо. Низкое тёплое солнце, длинные тени, холодный ambient,
тёплые лампы внутри, мокрые полы (референсы у владельца). Погода и сезон — модификаторы поверх
сектора (свет, материалы, звук шагов, дальность зрения AI), а не отдельные карты.

## Сюжет и согласование

По указанию владельца от 2026-10-02 новые сюжетные сцены, предыстория и цепочки заданий
сначала разрабатываются текстом и предъявляются владельцу на согласование. Внедрять их
в игру до явного согласования нельзя. Файл в `docs/` или коммит черновика сам по себе
не означает утверждения сюжета. Явное поручение реализовать представленную версию считается
её согласованием; повторно спрашивать разрешение на уже одобренную работу не нужно.

## Запуск и проверка

```
tools/godot.cmd                       # редактор
tools/godot.cmd --headless --import   # переимпорт: после новых ассетов И после нового файла с class_name
tools/smoke.cmd <сцена> [кадров] [overview[:x:z:высота]|at:угол:радиус[:высота[:курс]]]
                                      # скриншот в docs/screens/, выход (cmd режет «=» и «,» — только «:»)
tools/godot.cmd res://tools/ai_test.tscn                     # прогон мародёра: шум → бой → выстрелы, печатает состояния
tools/godot.cmd res://tools/ai_squad_test.tscn               # тактика отряда: окрик, укрытие, перезарядка, поиск
tools/godot.cmd --headless res://tools/steps_test.tscn      # шаги: поверхность под ногами, темп от скорости, глушение стеной
tools/godot.cmd --headless res://tools/settings_test.tscn   # настройки: шины громкости, качество графики, мышь
tools/godot.cmd --headless res://tools/downed_test.tscn    # тяжёлое ранение: лечь, добить, голова/граната, поднять, тащить, спасение мародёров
tools/godot.cmd --headless res://tools/quest_test.tscn     # сюжет «Не вернулся» целиком: этапы, смерть, эвакуация, сохранение, Антон, второй квест из данных
tools/godot.cmd res://tools/conditions_test.tscn            # условия рейда: зрение мародёров днём/ночью, свет ТЦ по питанию; с окном — снимки cond_*
tools/godot.cmd res://tools/weather_test.tscn               # погода: дождь (в т.ч. начинается в рейде), туман и снайпер, жара и очки, выносливость
tools/godot.cmd --headless res://tools/events_test.tscn     # события и фракции: жильцы, сигнализация, свет погас, генератор, сброс, ЧВК против мародёров, рация
tools/godot.cmd res://tools/rain_test.tscn                  # дождь шейдерами: карта «что над головой» = лучи физики; снимки rain_* (RAIN_TIME=night RAIN_SUFFIX=_night — ночью)
tools/godot.cmd res://tools/light_shots.tscn                # заградительные огни (ночь/туман горят, ясный день — нет), мягкий свет ТЦ; снимки light_*
tools/godot.cmd res://tools/light_tour.tscn                 # свет: помещения ночью, аварийный (панели = огни), ракета/химсвет за стеной, засвет от фонаря, фонарь на оружии за взглядом, ПНВ; снимки tour_* (TOUR_ONLY=glare — только засвет/ПНВ)
tools/godot.cmd res://tools/glass_test.tscn                 # витрины: пуля пробивает, трещины, осыпается сама, дробь выбивает, проём — путь ИИ и проход; снимки glass_*
tools/godot.cmd res://tools/asphalt_shots.tscn              # мокрый асфальт: сухо / сыро / лужи, от первого лица и изометрия (ASPH_TIME=day|dusk|night); снимки asphalt_*
tools/godot.cmd res://tools/ssr_probe.tscn                  # SSR движка: зеркало и мокрый асфальт при разных настройках отражений; снимки ssr_probe_*
python tools/fetch_sky.py                                      # ночное небо: HDRI Poly Haven + карта Луны NASA в assets/sky, CREDITS
tools/godot.cmd res://tools/ceiling_shots.tscn             # потолки и купол атриума: от первого лица вверх и изометрия
tools/godot.cmd res://tools/quest_shots.tscn                  # снимки сюжета: разговор, места этапов, несёшь Антона
python tools/import_model.py <id>                              # модель из _asset_src/<id> (+license.txt) в assets/models/props, CREDITS
tools/godot.cmd res://tools/ui_shots.tscn                    # снимки: карта (M), меню (Esc), управление, рюкзак и лут
tools/godot.cmd --disable-vsync res://tools/perf_test.tscn   # FPS / вызовы отрисовки в изометрии и в прицеле по точкам
tools/godot.cmd res://tools/raid_test.tscn                   # цикл рейда: рубильник, ключи, запертая дверь, эвакуация, итог
tools/godot.cmd res://tools/loadout_test.tscn                # убежище → рейд со снаряжением → эвакуация → убежище (тестовый профиль)
tools/godot.cmd --headless res://tools/arsenal_test.tscn     # арсенал, CASE 1–20 ТЗ: прицелы (FPS/изометрия), фонарь+ЛЦУ, пробитие, плиты, ИИ-патроны, снятие с трупа, сохранение
tools/godot.cmd --headless res://tools/compile_check.tscn    # все скрипты собираются (с автозагрузками) — после больших правок
tools/godot.cmd res://tools/hideout_shots.tscn               # снимки убежища и его окон в docs/screens/hideout_*.png
tools/godot.cmd --headless res://tools/shooting_range_test.tscn # тир котельной: ствол стойки без расхода вещей, пробоина, кнопки ближе/дальше/лист, выход из зала
tools/godot.cmd res://tools/boiler_hall_shots.tscn         # снимки котельной и тира в docs/screens/boiler_*.png (BOILER_ONLY=имя,имя — выборочно)
# Пересборка убежища: python tools/shelter_boiler_materials.py [--fetch]; blender --background --factory-startup --python
#   tools/build_shelter_boiler.py (стены, зал, котлы, тир), tools/build_shelter_gear.py, tools/integrate_shelter_boiler_external.py;
#   --headless --import; res://tools/author_shelter_scene.tscn; res://tools/author_shelter_dressing.tscn
tools/godot.cmd res://tools/icon_bake.tscn [-- id …]      # иконки предметов (ItemModels) в assets/icons/<id>.png, затем --import
tools/godot.cmd --headless res://tools/pm_test.tscn           # ПМ: детали, LOD, патронник 8+1/8, прерывания и атомарный глушитель
tools/godot.cmd --windowed --resolution 1280x720 res://tools/pm_shots.tscn # ПМ: хват, ADS, фазы перезарядки/глушителя, третье лицо в docs/screens/pm_*.png
tools/godot.cmd --headless res://tools/pm_net_test.tscn -- host # + та же сцена -- client через 3 с: реальные действия ПМ по ENet (порт 7777; отдельно от coop_raid_test)
python tools/import_weapon_model.py pm_highpoly_v5          # проверенный ПМ из _asset_src: дерево, PBR, размеры, бюджеты, CREDITS
python tools/import_weapon_model.py glock17_gen5            # Glock 17 Gen5 из _asset_src (--check — только проверка): дерево, PBR, размеры, бюджеты, CREDITS
tools/godot.cmd --headless res://tools/glock_test.tscn        # Glock: детали без курка/флажка/глушителя, LOD, патроны 17+1, дуло с обвесом
tools/godot.cmd --windowed --resolution 1280x720 res://tools/glock_shots.tscn # Glock: хват, ADS, перезарядка, третье лицо в docs/screens/glock_*.png
tools/godot.cmd --headless res://tools/export_weapon_refs.tscn -- "out=<папка>" # все стволы игры (и M4A1 с обвесами под левую руку) в GLB — образцы для хватов в Blender
tools/godot.cmd res://tools/mods_gallery.tscn                # витрина обвесов: сбоку, 3/4, крупные планы, вид из глаза
tools/godot.cmd res://tools/scope_sun_shots.tscn             # оптика против солнца (блики, аберрация) и открытые прицельные из глаза
tools/build_release.cmd                                      # сборка для друзей: export\RING.zip (RING.exe = Godot 4.7.2 + RING.pck, шаблоны не нужны)
tools/godot.cmd res://tools/net_host_test.tscn               # хост + tools/net_client_test.tscn в двух процессах —
                                                              # реальный ENet по 127.0.0.1, проверка репликации
tools/godot.cmd --headless res://tools/coop_hideout_host.tscn # + coop_hideout_client.tscn через 3 с: собрание в убежище —
                                                              # видят друг друга, телевизор общий, «Рейд всем» — оба в рейде
tools/godot.cmd --headless res://tools/coop_raid_test.tscn -- host   # кооп на троих: + «-- c1» через 3 с, + «-- c2» ещё
                                                              # через 3 с (c1 — из главного меню, c2 — из своего убежища):
                                                              # в убежище и рейде все видят всех и как ходят, выстрелы
                                                              # напарников видно, дверь ТЦ, открытая клиентом, открыта у всех,
                                                              # генератор встал у хоста — c2 чинит, у всех снова весь свет,
                                                              # хост и c1 в зоне эвакуации, c2 нет — общий отсчёт, c2 не успел
tools/godot.cmd --headless res://tools/mags_test.tscn      # магазины: ПОЛН/ПУСТ и оценка после проверки, снарядить/разрядить поштучно (MagOps), нет патронов — текст, разрядка в клетки ящика и буфер 3×3, плиты по одной, вопрос о буфере, держать R
tools/godot.cmd res://tools/sight_nvg_shots.tscn             # коллиматор в ПНВ, ЛЦУ: точка без ПНВ, луч в ПНВ; снимки sight_nvg_* (SHOTS_LOW=1 — качество «низко»)
tools/godot.cmd --headless res://tools/evac_test.tscn      # эвакуация группой: общий отсчёт 3 мин, ждём напарника, сброс, все в зоне — короткий, раненого выносят, не успел — без добычи
tools/godot.cmd --headless res://tools/story_test.tscn     # хроника рейда: вердикт по обстоятельствам и истории, стили не повторяются, 400 случайных рейдов без дыр в тексте, факты от хоста в уровне (с окном — снимок story_summary)
tools/godot.cmd --headless res://tools/anim_test.tscn      # анимации Persona при 144 к/с: клип ходьбы не скачет, спринт, присед и ходьба вприсядку — ступни на полу, лёжа, оружие в правой руке в любой стойке, левая кисть на цевье (SupportHandIK)
tools/godot.cmd --headless -s res://tools/bake_character_clips.gd  # клипы Mixamo (tools/character_clips.json) → persona_clips.res; что есть и чего нет — docs/animations.md
tools/godot.cmd --headless -s res://tools/bake_weapon_sockets.gd  # как оружие лежит в правой руке Persona (по позе прицеливания) → data/weapon_sockets.json
tools/godot.cmd --headless res://tools/coop_quest_host.tscn  # + coop_quest_client.tscn через 3 с: общий сюжет группы (взял задание, осмотр, зачёт обоим)
tools/godot.cmd --headless res://tools/templates_test.tscn  # шаблоны снаряжения: сохранить, собрать из тайника, докупить, причины «нет»
tools/godot.cmd --headless res://tools/vehicle_test.tscn   # транспорт: одна коллизия на модель, навмеш под машинами вырезан (и под автобусом, и повёрнутым)
tools/godot.cmd --headless res://tools/god_test.tscn       # чит «бессмертие»: голова, граната, очередь — жив; лёжа — встал; выключил — урон проходит
tools/godot.cmd --headless res://tools/stress_test.tscn    # стресс: пули рядом, спад в тишине, пороги, адреналин, обезболивающее
tools/godot.cmd res://tools/breaker_test.tscn              # главный рубильник света ТЦ: щитовая, свет погас → поднять, генератор; снимок breaker.png
tools/godot.cmd res://tools/vault_test.tscn                # перелезание (игрок и мародёр по связке навигации), бросок на землю; снимки vault_*
tools/godot.cmd res://tools/info_shots.tscn                # снимки окна описания предмета (info_*) и прицела гранаты (nade_aim)
tools/godot.cmd res://tools/hideout_move_probe.tscn          # скорость в убежище: шаг / бег (с оружием, от первого лица)
tools/godot.cmd res://tools/sound_bench.tscn               # стенд звуков: одна страница — сворачиваемые разделы (оружие → классы → стволы, общие наборы;
                                                              # разделы каталога → подгруппы → карточки событий); справа событие: слушать в разных местах /
                                                              # вдали / за стеной / очередью, назначить запись проекта нескольким событиям, снять запасной
                                                              # набор или синтез (data/sound_active.json); «Входящие» — файлы из _sound_try/ → assets/audio.
                                                              # Снимок: -- capture:res://_sound_try/b.png select:<id> open:all
tools/godot.cmd --headless res://tools/sound_bench_test.tscn # стенд звуков: каталог покрывает всё, что зовёт игра; страница и карточки; назначения и снятие
                                                              # (и в Audio); новые файлы, отбор, перенос, CREDITS, воспроизведение
python tools/sound_catalog_md.py                               # список всех звуков для чтения: docs/sound_catalog.md
```

Перед сетевыми тестами — убить висящие процессы Godot: старый хост держит порт 7777, и клиент
подключается к нему. Сетевые пары не запускать одновременно.

Стартовая сцена — `scenes/ui/main_menu.tscn` (Продолжить / Новая игра / Загрузить / Собрание /
Настройки). Сохранения — `Saves` (`user://saves/*.json`, последнее — `[profile] last` в настройках);
тесты по-прежнему берут свои профили через `Profile.use_file(...)`.

Godot 4.7.2 (Steam): `D:\Steam\steamapps\common\Godot Engine\godot.windows.opt.tools.64.exe`
(путь — в `tools/godot.cmd`, править только там). Тестов нет: проверка — запустить и посмотреть.

## Структура

```
src/core/      balance.gd (ВЕСЬ баланс — только здесь, autoload `Balance`), события, утилиты
src/player/    персонаж игрока (стойки, прицел, движение), камера
src/ai/        мародёры: marauder.gd (патруль/расследование/бой), perception.gd (зрение — единственный
               способ AI узнать позицию игрока)
src/story/     хроника рейда (экран итога): RaidAnalytics (факты своего игрока) → RaidSummary (теги) →
               RaidStoryEventSelector → RaidStoryGenerator → RaidVerdictGenerator → RaidHistory; всё
               локально, фразы — data/raid_story.json (писать только о том, что тег гарантирует)
src/quests/    сюжетные квесты (autoload Quests, docs/design/quests.md): данные data/quests, состояние в Profile,
               QuestWorld/QuestSite — места в мире, QuestAnchor — место руками в сцене
src/combat/    weapon_models.gd (процедурное оружие; в руках модель развёрнута на 180°, поэтому
               **-X модели — правая сторона стрелка**), weapon_mods.gd (обвесы: точки крепления MOUNTS
               сняты с геометрии моделей — новый обвес ставить от них и проверять mods_gallery),
               weapon_stats.gd (характеристики с обвесами — одно место расчёта), grenade.gd, ragdoll.gd, target.gd (мишени),
               health.gd, hitscan.gd (выстрел лучом + разброс), tracer.gd, surfaces.gd (из чего
               поверхность в точке попадания), impact_fx.gd (частицы, декали, звук удара)
src/audio/     audio_system.gd — записи assets/audio по префиксам (SAMPLES/FAR/OWN/LOOPS), иначе синтез;
               каталог всех звуков — data/sound_catalog.json (стенд tools/sound_bench)
src/world/     сборка сектора из данных, коллизии, навигация, шум/зрение
src/net/       network.gd (autoload `Net` — host/join, `Net.is_networked()`), lobby.gd
src/ui/        HUD, инвентарь, убежище
scenes/        .tscn: один узел мира = одна сцена (player.tscn, marauder.tscn, props/*.tscn)
data/          секторы как данные (.tres / .json), предметы, таблицы лута
assets/        готовые модели/текстуры/звук (через Git LFS) + CREDITS.md с лицензиями
_asset_src/    сырьё (не в git): папка на ассет с исходником и license.txt
tools/         скрипты сборки ассетов, запуска, скриншотов
docs/          STATUS.md (что сделано / что дальше), решения по дизайну
```

## Ключевые правила

1. **Баланс — только в `src/core/balance.gd`.** Никаких магических чисел в других скриптах.
2. **Карта — данные + сцена.** Кольцо (помещения, проёмы) — `data/sectors/*.json`, собирается
   `SectorBuilder`; в редакторе видно превью (скрипты @tool), в .tscn оно не сохраняется.
   Всё, что вне кольца, — узлы сцены уровня, их двигают руками: постройки
   (`scenes/world/blockout_building.tscn`, вид/размеры/этажи в инспекторе; двери и ворота —
   дочерние `blockout_opening.tscn`, режут ближайшую стену), точки появления (`spawn_point.tscn`)
   и эвакуации (`extraction_point.tscn`), эскалаторы (`escalator.tscn`: пара, уклон 30°, наверху
   площадка 2F и опущенная противопожарная штора). Перекрытия (этажи паркинга, навесы, площадка
   эскалатора) — группа "decks": уровень прячет их над игроком в изометрии. Узел в группе
   "prop_keepout" с методом `keepout_rect()` не даёт кольцу ставить под ним пропсы.
   Рейд — узел `Raid` (src/world/raid.gd, создаёт SectorLevel; хост считает, остальным синхронизируется):
   рубильники, эвакуация группой (кто-то в открытой зоне — общий отсчёт `EXTRACT_GROUP_SEC`, все живые
   в зонах — короткий отсчёт точки; кончился — кто в зоне, ушёл, живой не в зоне — `stranded`, без
   добычи; ушёл любым способом — `has_left`), лут (просьбы игроков к хосту), тела/выброшенное
   (спавнер Drops), итог и хроника рейда (`src/story`).
   Предметы и лут — данные: `data/items.json` (у предмета `size` [ш, в] — ячеистый инвентарь),
   `data/loot.json` (какие пропсы обыскиваются, таблицы, темы магазинов); код — `src/items/` (ItemDb:
   сетки — запись = стопка с `x`,`y`,`r`; Inventory у каждого Player — авторитет хоста), окна —
   `src/ui/inventory_ui.gd` и `GridView`/`SlotView` (тащить мышью, R — повернуть).
   Прогрессия: `docs/design/progression.md` — доверие Михалыча, задания (`data/missions.json`,
   `Missions`), модули убежища (`data/hideout.json`, `Upgrades`: верстак, генератор, защищённый
   карман, тайник, рация). Контейнеры на пропсах строит SectorBuilder (Loot/Loot_N),
   особые (сейф, стойка) — `loot_container.tscn` руками в сцене. Ключи — предметы в рюкзаке.
   Убежище — старая котельная в зоне 5, отдельная от ТЦ карта (люков из ТЦ нет): `scenes/levels/hideout.tscn`
   → `levels/shelter/Shelter_Interior.tscn`, собирается инструментами (см. «Пересборка убежища»); в котельном
   зале тир (`ShootingRange`, `RangeLane`, `RangeTarget`, стойка `RangeWeaponRack` — любой ствол игры на зал).
   Прежнее описание: CSG-узлы (двигать руками; материал —
   meta "mat"/"color"/"emit", см. hideout_level.gd), станции `hideout_station.tscn` (тайник, торговец,
   выход). Профиль игрока — `Profile` (src/items/profile.gd, user://profile.json): деньги, тайник,
   снаряжение, рюкзак; уходя в рейд — всё на кону (take_loadout), эвакуация возвращает. Рейд со
   снаряжением только если `Profile.pending_raid` (убежище/лобби из убежища); запуск уровня напрямую
   и тесты — «песочница» (все стволы, патроны без счёта, профиль не трогается). Тесты профиля —
   только через `Profile.use_file("user://…_test.json", true)`. В сцене уровня: `key_pickup.tscn` (key_id),
   `power_switch.tscn` (switch_id), у `ExtractionPoint` — required_key / required_switch;
   помещение с "key" в JSON запирает свои двери (Door.required_key). Синхронизаторам давать имя
   (`sync.name = "Sync"`): автоимя у каждого peer своё, и пакеты хоста не находят узел. То же —
   любому узлу, у которого есть синхронизатор или RPC, если его создаёт код (двери кольца —
   `Door_N`, стёкла — `GlassPanes`): с автоименем `@Node3D@N` просьба клиента не находила дверь.
   Производительность: меши пропсов склеиваются (`PropBatcher`, клетка 24 м, дальше 110 м не
   рисуются) — не добавлять в сцену тысячи мелких MeshInstance; глухие стены — окклюдеры,
   отсечение за стенами включено только в прицеле (в изометрии стены у камеры растворены).
3. **AI не читает позицию игрока напрямую** — только через `Perception.can_see` (конус + луч),
   `NoiseBus.noise` (шаги, выстрелы, двери, падение тела) и `NoiseBus.callout` (окрик товарища,
   который сам видел цель, — слышен в радиусе). Никакой телепатии. Мародёры ходят отрядами
   (`Squad`: кто за кем идёт и кто заходит в обход — не общая память).
   Слои физики: 1 world, 2 player, 4 marauder, 8 door, 16 debris — регдоллы/гранаты (константы в `Hitscan`).
4. **Сеть: авторитет у хоста.** Всё, что влияет на исход (урон, лут, AI), считается на хосте;
   Player — исключение, его двигает владеющий peer (иначе движение дёргается), но его же дочерний
   `Health` — снова хост. Marauder/Door целиком хост (умалчиваемый multiplayer authority узла = 1,
   его не трогаем). Каждый узел сам ставит себе `MultiplayerSynchronizer` в своём `_ready()`
   (см. `player.gd`/`marauder.gd`/`door.gd`/`health.gd`) — авторитет синхронизатора нужно выставлять
   ДО `add_child`, иначе спавнер путает pending-спавн (реальная ошибка, на неё легко попасть).
   Там же, ДО `add_child`, — `Net.scope_sync(self, sync)`: синхронизатор шлёт только тем, кто в той же
   сцене (убежище / рейд — meta `Net.SCENE_META` уровня). Без этого он на первый кадр виден всем, путь
   к нему уходит тому, кто ещё грузится, не находится — и этому peer узел не шлётся больше никогда
   (так хост «стоял» у клиентов в рейде). Эффекты, которые считаются у одного peer (выстрел: трассер,
   вспышка, звук), остальным — отдельным RPC (`Player/Marauder._rpc_shot_fx`).
   **Ловушка Godot 4.5:** `multiplayer.has_multiplayer_peer()` и `multiplayer.is_server()` истинны
   даже без единого реального игрока в сети (умалчиваемая «оффлайн» сессия сама себе хост,
   unique_id=1) — проверять «есть ли реальная сеть» только через `Net.is_networked()`
   (свой флаг в `src/net/network.gd`, взводится в `host()`/`join()`). `is_multiplayer_authority()`
   и `is_server()` при этом остаются корректными и в оффлайне — их не заменять.
5. **Сцены-ноды.** Каждая сущность — своя сцена с понятным деревом узлов, чтобы её можно было
   открыть в редакторе и поправить руками. Не прятать всё в один скрипт-монолит.
6. **Ассеты.** Только CC0 / CC-BY (или собственные). Звук — ещё royalty-free библиотеки (Sonniss GDC,
   Boom Library, Soundsnap и т. п.: разрешено использовать в своей игре): текст лицензии —
   `assets/audio/LICENSES/<библиотека>.txt`, библиотека и ссылка — в источнике записи (стенд не
   перенесёт без этого). Пока репозиторий закрытый; если откроется — сырые файлы таких библиотек
   из git убрать (их лицензии обычно запрещают раздавать звуки отдельно от игры).
   Сырьё в `_asset_src/<id>/` + `license.txt`,
   в `assets/` — только через `tools/`; каждый источник записан в `assets/CREDITS.md`.
   Для внешних ассетов должен быть процедурный запасной вариант — проект обязан запускаться
   без `assets/models` и `assets/textures`.
7. **Нет `any`-стиля.** Типизированный GDScript: аннотации у всех переменных, аргументов, возвратов.
8. **Комментарии — по-русски, о смысле, не о синтаксисе.** Имена — по-английски.

## Git

- Ветка `main`, работать в ней. Перед началом работы **всегда** `git pull --rebase`.
- Коммиты маленькие и частые, сообщение по-русски: `область: что сделано`.
- После каждой законченной задачи — `git push`. Бинарники идут через LFS автоматически (`.gitattributes`).
- Конфликт в `.tscn`/`.tres` решает тот, кто пришёл вторым: перечитать сцену, применить свои
  изменения заново, не сливать текстом вслепую.
- Папки `референсы/`, `_asset_src/` и `_sound_try/` (звуки на пробу для стенда) никогда не коммитятся.
- Агент дописывает в `docs/STATUS.md`, что сделал и что осталось — это единственный общий журнал.
