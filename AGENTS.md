# RING — правила проекта для любого агента (Claude, Codex, локальные модели)

Тактический extraction-шутер от первого лица (изометрии нет — обзор сверху только у разведдрона, docs/design/drone.md). Godot 4.7, GDScript, Forward+.
Кооп на 3 игроков (один хостит). Реализм в графике: PBR, фототекстуры (CC0), реальные пропорции.

**Начать с:** `docs/OWNER_NOTES.md` (решения и предпочтения владельца, как с ним работать), конец
`docs/STATUS.md` (что сделано последним), `docs/BACKLOG.md` (что ждёт; помеченное «СЛЕДУЮЩЕЕ» — первым).

## Производственные ограничения сюжета (владелец, 2026-10-16)

- **Запрещён не транспорт, а вождение** (уточнение владельца 2026-10-17: «мы не транспорт
  запрещаем, а механику вождения автомобиля игроком и NPC, которые с ним взаимодействуют»).
  Игрок машин не водит; NPC, которые садятся в машину, водят, грузят или чинят её, не делаются.
  Машины в заданиях — неподвижное окружение или объект задания, перевозки — за кадром между
  рейдами. Сам транспорт в мире этим правилом не отменён (выходы «грузовик» / «вертолёт»
  из плана ТЦ остаются в силе; как они работают — решается при их проработке).
- Сюжет строить без видимых второстепенных NPC, требующих новых моделей / анимаций:
  заказчик, механик, посредник и внешняя команда работают через терминал / удалённую
  связь. Не заказывать видимых механиков и союзных охранников. Это не команда удалить
  уже готовых основных персонажей или существующие боевые NPC.
- Сначала короткое элементарное обучение. Новая редакция заказа машины и ограничения:
  `docs/design/mission_car_recovery.md`, `docs/tasks/car_recovery_maps.md`.
  Старые сценарии с движением машин и видимыми спутниками не являются актуальным ТЗ.

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
**Решение владельца 2026-10-15:** ТЦ — отдельная карта Ø200 с прилегающей территорией
(`docs/design/mall_map.md`); `f1_ring` Ø250 — прежний серый черновик, будет пересобран; ТЦ с карты
зоны 1 уходит. Кольцо на Ø250 больше не развивать.
Серый черновик 1-го этажа Ø200 — `data/sectors/mall_1f.json` (генератор `tools/gen_mall_1f.py`, план —
`docs/design/mall_1f_plan.md`) + `scenes/levels/mall_1f.tscn`; отдельно в рейды не подключён — в рейде он часть
карты территории ТЦ `scenes/levels/mall_map.tscn` (черновик `mall_study` внутри рейдового уровня, маршрут
«ТЦ «РИНГ» · территория», данные `data/sectors/mall_map.json`, места заказа «Вернуть машину» — `scenes/levels/mall/`).

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
tools/godot.cmd --headless res://tools/ambush_test.tscn     # засада (AI_AMBUSH): цель ушла за угол — присел, смотрит на точку, ждёт; вышла там же — прицел сидит;
                                                              # склонность 0 — идёт вперёд; в отряде ждёт один; никто не вышел — встал и пошёл
tools/godot.cmd --headless res://tools/ai_population_test.tscn # население слоями на «Пешем маршруте»: точки, 1/2/3 игрока, рынок, подход, отклик на шум, стычки
tools/godot.cmd --headless res://tools/coop_population_test.tscn -- host # + «-- client» через 3 с (порт 17795; COOP_POP_PEERS=3 и второй «-- client» —
                                                              # двое гостей): население по числу игроков, у гостей те же бойцы и ходят, подход вдали от всех,
                                                              # чужие отряды и ЧВК по составу, стычка с гостем засчитана
tools/godot.cmd --headless res://tools/steps_test.tscn      # шаги: поверхность под ногами, темп от скорости, глушение стеной
tools/godot.cmd --headless res://tools/camera_motion_test.tscn # движение камеры (CameraMotion, Balance.CAMERA_MOTION) при 144 к/с: покачивание в фазе шагов, бег сильнее,
                                                              # остановка досаживается и не копится, вбок крен, прицел почти стоит, присед плавно, приземление,
                                                              # ползунок 0, вид сверху и обратно, без ступенек между тиками физики
tools/godot.cmd --windowed --resolution 1600x900 res://tools/scale_probe.tscn # стенд масштаба (вопрос владельца 2026-10-24 «реальные размеры мелкие»):
                                                              # пять наборов рядом — A всё 1:1, B предметы 1:1 / проходы × 1,2, C всё × 1,3, D предметы 1:1 / проходы × 1,3,
                                                              # E как D с высотами × 1,15 (улица, комната с дверью,
                                                              # коридор, стеллажи, лестница, фигура 1,75); F1/F2/F3 — поле зрения 75/80/90°, F5…F9 — к набору;
                                                              # SCALE_PROBE_SHOTS=1 — снимки scale_probe_* и выход
tools/godot.cmd --headless res://tools/carry_test.tscn       # стойка «наискосок» (Balance.WEAPON_CARRY): по умолчанию опущено, колесо вверх — от бедра, вниз — наискосок,
                                                              # бегом всегда наискосок, огонь поднимает и стреляет (клик не теряется), ПКМ — и обратно, лёжа и перезарядка
tools/godot.cmd --windowed --resolution 1280x720 res://tools/carry_shots.tscn # снимки стойки: от бедра и наискосок у стволов песочницы → docs/screens/carry_*;
                                                              # подбор позы: CARRY_VARIANTS="yaw=35 pitch=22 back=0.15 sy=0.04;…" CARRY_ONLY=wpn_sg_02
tools/godot.cmd --headless res://tools/zone01_ld_test.tscn   # Пригород, левел-дизайн: в каждом зале с интерьером есть лут и до всех мест лута можно дойти,
                                                              # места заказа «Вернуть машину», путь от появлений к выходам, серверная под ключом, голые отрезки улиц
python -X utf8 tools/zone01_ld_plan.py                         # схема левел-дизайна Пригорода (маршруты, горячие точки, интерьеры, укрытия, посты) → docs/design/zone01_level_design.png
tools/godot.cmd --headless res://tools/water_wade_test.tscn # брод в болоте зоны 1: по пояс, медленнее, без бега и «лечь», шаги — плеск (WaterBody, Balance.WATER)
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/grass_shots.tscn # трава: густой ярус, ветер, след после прохода и подъём, против солнца, кадры в секунду по ярусам; снимки grass_* (GRASS_TIME=dusk, GRASS_ONLY=eye,down)
tools/godot.cmd --windowed --resolution 1600x900 res://tools/blood_shots.tscn # кровь у стены в зоне 1: капли, следы по углу удара, подтёки, лужа под убитым, высохла; игрок ранен — лужа, утащили — мазок; снимки blood_*
python tools/gen_blood_maps.py                                 # карты крови: растекание лужи (перколяция), подтёки, следы капель → assets/textures/blood; затем --import
tools/godot.cmd --headless res://tools/settings_test.tscn   # настройки: шины громкости, качество графики, мышь
tools/godot.cmd --headless res://tools/downed_test.tscn    # тяжёлое ранение: лечь, добить, голова/граната, поднять, тащить, спасение мародёров
tools/godot.cmd --headless res://tools/quest_test.tscn     # сюжет «Не вернулся» целиком: этапы, смерть, эвакуация, сохранение, Антон, второй квест из данных
tools/godot.cmd --headless res://tools/terminal_story_test.tscn # переписка в терминале: принять заказ, история, отчёт, оплата этапа один раз, гостю тоже, задание ждёт карту
tools/godot.cmd --headless res://tools/quest_steps_test.tscn # шаги заказа машины в убежище: снимки, ранняя находка, пропуск шагов, сдача деталей без эвакуации, «не в карман»
tools/godot.cmd --headless res://tools/tutorial_test.tscn   # обучение новой игры: пакет на ящиках → рюкзак → полка → терминал, рюкзак заранее, старые сохранения
tools/godot.cmd --headless res://tools/car_recovery_test.tscn # заказ «Вернуть машину» по данным: обычный путь, ранняя находка, общий отчёт, оплаты, тестовые инструкции
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/radiator_game.py -- lp|bake|pack|export|imports
                                                              # радиатор (предмет car_radiator) в игру: сетка ~16,5 тыс. треугольников тем же генератором,
                                                              # запекание с принятых текстур UCUPaint, два атласа 2K → assets/items/models/car/car_radiator.glb
                                                              # (imports — после первого --import: сжатие карт как у ПМ; затем --import ещё раз)
tools/godot.cmd --windowed --resolution 1600x900 res://tools/car_radiator_shots.tscn # радиатор как предмет игры: стоит и лежит, бирка, патрубок, горловина вблизи, издали; снимки car_radiator_*
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/wheel_item.py -- export|imports
                                                              # колесо (предмет car_wheel) = игровое колесо машины LOD0 и его атлас → assets/items/models/car/car_wheel.glb
tools/godot.cmd --windowed --resolution 1600x900 res://tools/car_parts_shots.tscn # «Пригород», автобаза: колесо и радиатор в кладовой на этапе «комплект»,
                                                              # после сдачи — кладовая пуста, радиатор в комплекте; снимки car_parts_*
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/game_lp.py -- <отделка.blend>
                                                              # купе Ильи в игру: сетка LOD 150/50/12 тыс. и развёртки, затем тем же Blender game_bake.py → game_pack.py →
                                                              # game_export.py → assets/models/props/coupe_ilya; --import, python tools/coupe_ilya/game_imports.py, --import
tools/godot.cmd --headless res://tools/coupe_ilya_shots.tscn -- check # купе в движке: узлы состояний и LOD, габарит, коллизия, бюджет;
                                                              # с окном (--windowed --resolution 1280x800) — снимки coupe_ilya_* (-- only=front34,bay,lod)
tools/godot.cmd res://tools/conditions_test.tscn            # условия рейда: зрение мародёров днём/ночью, свет ТЦ по питанию; с окном — снимки cond_*
tools/godot.cmd res://tools/weather_test.tscn               # погода: дождь (в т.ч. начинается в рейде), пасмурно (сыро без капель, потом дождь), туман и снайпер, жара и очки, выносливость
tools/godot.cmd --headless res://tools/events_test.tscn     # события и фракции: жильцы, сигнализация, свет погас, генератор, сброс, ЧВК против мародёров, рация
tools/godot.cmd --headless res://tools/reload_fast_test.tscn # ВЕРАС со снаряжением: одно R — обычная перезарядка, два быстрых — быстрая (−28 %, старый магазин на землю), держать R — магазин в руке
tools/godot.cmd --headless res://tools/fire_mode_test.tscn  # режимы огня (X, ВЕРАС-54: АВ → 2 → ОД → АВ): очередь по 2 на нажатие, ОД — один, пока переводчик щёлкает — не стреляет,
                                                              # режим на экземпляре ствола (хосту, после перезарядки и смены ствола), у пистолета X ничего не делает
tools/godot.cmd --headless res://tools/light_keys_test.tscn # свет в руку: Y — химсвет, бросок как граната (ЛКМ/ПКМ); G — ракетница из слота (в руках — тип патрона),
                                                              # дважды G — фальшфейер в руку; расход у хоста, свет на земле; без ракетницы G ничего не достаёт
tools/godot.cmd --headless res://tools/ammo_mix_test.tscn  # патроны в магазине вперемешку: слои, снаряжение и разрядка сверху, стрельба по слоям, смена и досыпка
tools/godot.cmd --windowed --resolution 1280x720 res://tools/nvg_stress_test.tscn # ПНВ в бою: зелёная картинка не пропадает под эффектами стресса и ранения; снимки nvg_stress_*
tools/godot.cmd --windowed --resolution 1280x720 res://tools/sky_flare_shots.tscn # осветительная ракета из сигнального пистолета во дворе зоны 1 ночью: 15 с в воздухе, высота, кадры в секунду; снимки sky_flare_*
tools/godot.cmd --windowed --resolution 1280x720 res://tools/aim_feel_test.tscn  # пристрелка (сбитый ноль, щелчки), дыхание и его задержка, отдача в руках пружинами, своя инерция метки коллиматора
tools/godot.cmd --headless res://tools/rivals_test.tscn    # чужие отряды («другие игроки»): входят, обыскивают, уходят через выход с добычей, воюют между собой и с мародёрами, память состава
tools/godot.cmd --headless res://tools/rivals_fight_test.tscn # бой между группами: потеряли бойца — отход к выходу, «крысы» с добычей уходят сразу, предел погони, обыск тел под прикрытием
tools/godot.cmd res://tools/rain_test.tscn                  # дождь шейдерами: карта «что над головой» = лучи физики; снимки rain_* (RAIN_TIME=night RAIN_SUFFIX=_night — ночью)
tools/godot.cmd res://tools/light_shots.tscn                # заградительные огни (ночь/туман горят, ясный день — нет), мягкий свет ТЦ; снимки light_*
tools/godot.cmd res://tools/light_tour.tscn                 # свет: помещения ночью, аварийный (панели = огни), ракета/химсвет за стеной, засвет от фонаря, фонарь на оружии за взглядом, ПНВ; снимки tour_* (TOUR_ONLY=glare — только засвет/ПНВ)
tools/godot.cmd res://tools/glass_test.tscn                 # витрины: пуля пробивает, трещины, осыпается сама, дробь выбивает, проём — путь ИИ и проход; снимки glass_*
tools/godot.cmd --windowed --resolution 1280x720 res://tools/first_hit_test.tscn # фриз первых попаданий: каждый вид, стекло, граната — самый длинный кадр
                                                              # (FIRST_HIT_WARM=1 — после разогрева ImpactFx.warm_up; чистый кэш — APPDATA и LOCALAPPDATA на пустую папку)
tools/godot.cmd res://tools/asphalt_shots.tscn              # мокрый асфальт: сухо / сыро / лужи, от первого лица и изометрия (ASPH_TIME=day|dusk|night); снимки asphalt_*
tools/godot.cmd res://tools/ssr_probe.tscn                  # SSR движка: зеркало и мокрый асфальт при разных настройках отражений; снимки ssr_probe_*
python tools/fetch_sky.py                                      # ночное небо: HDRI Poly Haven + карта Луны NASA в assets/sky, CREDITS
python -X utf8 tools/gen_sky_atmosphere.py                    # расчётное небо: таблицы рассеяния и подгонка яркости к небу из панорам → data/sky_atmosphere.json
                                                              # (--preview <папка> — панорамы обоих режимов по высотам солнца)
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/sky_compare_shots.tscn # небо из панорам и расчётное с облаками (Esc → Читы → Мир → «Небо»):
                                                              # 05:00, 13:00, 18:30, 21:00, дождь → docs/screens/sky_cmp_*.png; свет на земле (расчётное / панорамы), кадры в секунду
                                                              # (SKY_CMP_ONLY=0500,2100; SKY_CMP_HOURS=5,13 SKY_CMP_WEATHER=fog — свои часы; SKY_CMP_NOCLOUDS=1 — без облаков)
tools/godot.cmd res://tools/ceiling_shots.tscn             # потолки и купол атриума: от первого лица вверх и изометрия
python -X utf8 tools/gen_mall_1f.py                          # ТЦ Ø200, 1-й этаж: раскладка плана docs/design/mall_1f_plan.md → data/sectors/mall_1f.json
tools/godot.cmd --headless res://tools/mall_1f_check.tscn   # серый черновик ТЦ Ø200: ИИ доходит во все открытые места, выходы по плану;
                                                              # с окном (--windowed --resolution 1920x1080) — снимки mall_1f_* (MALL_ONLY=top|eye);
                                                              # MALL_ONLY=perf — кадры с мародёрами и без, atrium — засвет под куполом (MALL_TIME, MALL_WEATHER)
python -X utf8 tools/build_mall_study.py                     # черновик территории ТЦ по принятой схеме → data/blockouts/mall_study.json, scenes/levels/mall_study.tscn
                                                              # (наполнение пустых мест — tools/mall_study_filler.py → узел Filler, src/blockout/mall_filler.gd;
                                                              #  рельеф: речка, горки, утёсы, рощи — tools/mall_study_relief.py → MallLandscape.ground();
                                                              #  улицы: перекрёстки, разметка, отбойники, знаки, галерея — tools/mall_study_streets.py → узел Streets;
                                                              #  земля: площадки, пятна, тропы — tools/mall_study_ground.py; уплотнение по «карте пустоты» —
                                                              #  tools/mall_study_density.py; поля, грунтовки, машины на дорогах, вертолёт —
                                                              #  tools/mall_study_scenery.py; ж/д ветка — tools/mall_study_railway.py;
                                                              #  сквер-парк — tools/mall_study_park.py → узел Park, src/blockout/mall_park.gd;
                                                              #  разбор игр — docs/design/mall_density_research.md)
tools/mall_study.cmd                                          # прогулка по черновику территории ТЦ 1:1 (docs/design/mall_study.md): M — план, 1–9/0, N/B — участки, F — полёт;
                                                              # проверка: --headless res://tools/mall_study.tscn -- verify (подходы A–E, галерея, наполнение и открытые куски ≤ 60 м, рельеф, брод, мостики, ж/д ветка и переезд, паркинг, двор, пристройка приёмки); -- shots — снимки
                                                              # (MALL_STUDY_VIEW=имя:x:y:z:куда_x:куда_y:куда_z — свой кадр, несколько — через «;», MALL_STUDY_OUTPUT — папка)
tools/godot.cmd --headless res://tools/bake_mall_nav.tscn      # рейдовая карта ТЦ (scenes/levels/mall_map.tscn = черновик территории + заходы, выходы, мародёры, места заказа):
                                                              # перепечь кэш навигации data/navigation/mall_map после правки территории (~30 с; без кэша рейд печёт сам при загрузке)
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/mall_ground_perf.tscn # покрытия и бетон территории ТЦ (MallGround, шейдеры paved_ground, cast_concrete):
                                                              # кадры в секунду и время видеокарты против прежних серых на одних кадрах (MALL_GROUND_FALLBACK=1 — вид без текстур)
tools/godot.cmd --headless res://tools/car_mall_sites_shots.tscn # места заказа «Вернуть машину» на карте ТЦ: стоянка у доков, бокс скупки у АЗС, склад техники —
                                                              # F засчитан, путь по навигации от заходов; с окном (--windowed --resolution 1600x900) — снимки car_mall_*
python -X utf8 tools/gen_car_clue_textures.py                 # улики заказа на карте ТЦ → assets/textures/car_clues: пятно антифриза и следы шин по альфа-маскам
                                                              # владельца (Маски_АЛЬФА), номера, накладная, бирка «ЮР / 8»; затем --import
tools/godot.cmd --headless res://tools/sector_stats.tscn -- res://data/sectors/f1_ring.json # сводка сборки сектора (стены, двери, огни):
                                                              # снять до и после правки SectorBuilder — старые уровни не должны меняться
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
#   --headless --import; res://tools/author_shelter_scene.tscn; res://tools/author_shelter_dressing.tscn;
#   python tools/shelter_grime_textures.py → res://tools/author_shelter_grime.tscn (декали старения).
#   Запечённого света нет (решение владельца 2026-10-11): свет уличный, рассеянный — SDFGI.
#   Двор и выход (после author_shelter_scene его запускать заново — он же возвращает проём в стене тамбура):
#   blender … --python tools/build_shelter_exterior.py; --headless --import; res://tools/author_shelter_exterior.tscn
#   → levels/shelter/Shelter_Exterior.tscn (земля, лес, забор, ворота, дверь, зона сбора); дальше сцену правят руками.
#   Только материалы (шейдер старения стен): SHELTER_MATERIALS_ONLY=1 … res://tools/author_shelter_scene.tscn
tools/godot.cmd res://tools/look_shots.tscn                 # вид «как с камеры»: те же кадры с эффектами и без (убежище, рейд день/ночь, поворот головы)
tools/godot.cmd res://tools/icon_bake.tscn [-- id …]      # иконки предметов (ItemModels) в assets/icons/<id>.png, затем --import
tools/pm_grip_rebuild.cmd [shots]                             # ПМ, руки от первого лица, после правки владельцем хвата (_asset_src/pm_game/anim/PM_FPS_Grip_v03.blend)
                                                              # или поз перезарядки (PM_FPS_ReloadPoses_v01.blend): проверка хвата, правая → в файл поз, клипы PM_FPS_Clips_v02.blend
                                                              # (режимы по отдельности — tools/pm_grip_lock.py: build|check|reload|poses_sync_right|poses_stills|stills)
tools/godot.cmd --headless res://tools/pm_test.tscn           # ПМ: детали, LOD, патронник 8+1/8, прерывания и атомарный глушитель
tools/godot.cmd --headless res://tools/pm_state_maps_test.tscn # вид оружия один (2026-10-19): ПМ при любой прочности — карты «пошарпанный» v01 (pm_<Атлас>_100_*)
                                                              # с маской плёнки _coat, ВЕРАС-54 — то же; файлов прежнего износа (_wear, 60/20, wear_detail) нет
# ПМ «пошарпанный» v01 в игру (blender … --background --factory-startup --python-exit-code 1 --python): tools/pm_worn/build_lp.py (сетка ~26 тыс. +
#   обойма с патронами ~5 тыс., глушитель 2 тыс.; хвостовик ствола) → tools/pm_worn/bake.py -- pm|mag|ammo|supp|ao (карты и плёнка со стеков
#   принятого файла 21_…; глушитель — из сборки) → tools/pm_worn/pack.py (→ assets/models/weapons/pm/pm_<Атлас>_100_*, карты глушителя-обвеса) →
#   tools/pm_worn/export.py (pm.gltf + LOD1, pm_mag.gltf — обойма, attachments/supp_pm) → tools/pm_worn/sight.py -- geometry|bake|export [zorin_k1|mount_pm_k1]
#   (ЗОРИН К-1 — прицел на любую планку → attachments/zorin_k1; крепление к затвору ПМ — переходник → attachments/mount_pm_k1) → --import →
#   python -X utf8 tools/pm_worn/imports.py → --import; сверка со сборкой в студии владельца — tools/pm_worn/compare.py (docs/screens/pm_worn_compare*.png);
#   описание docs/assets/pm_game_worn_v01.md
tools/godot.cmd --headless res://tools/pm_worn_check.tscn   # ПМ «пошарпанный» в движке: риг и метки pm.gltf, плёнка, бюджеты (≤ 40 тыс. в руках с К-1 и глушителем),
                                                              # обойма, К-1, крепление и глушитель как предметы и на полу, К-1 на планке автомата, набор PM_TAC
                                                              # (метка, линия прицеливания); с окном (--windowed --resolution 1600x900) — снимки pm_worn_*
tools/godot.cmd --windowed --resolution 1280x720 res://tools/pm_shots.tscn # ПМ: хват, ADS, фазы перезарядки/глушителя, третье лицо в docs/screens/pm_*.png
tools/godot.cmd --headless res://tools/pm_net_test.tscn -- host # + та же сцена -- client через 3 с: реальные действия ПМ по ENet (порт 7777; отдельно от coop_raid_test)
# ВЕРАС-54 v13 в игру (blender … --background --factory-startup --python-exit-code 1 --python): tools/veras54_v13/game_lp.py (сетка ~33 тыс. + патроны ~5 тыс.)
#   → game_bake.py -- gun|ammo|ao → game_pack.py (карты; маски жировой плёнки _coat в assets) → game_finish.py (матовый корпус: ORM)
#   → game_rig.py (риг рук v13 в библиотеке)
#   → bash tools/veras54_v13/clips/build_all.sh (18 клипов, «Клипы v13») → export_veras54.py → --import → python -X utf8 tools/veras54_v13/game_imports.py → --import;
#   сверка запекания с исходником в его студии — tools/veras54_v13/bake_compare.py, гильза задержки — clips/jam_check.py
# Магазины ВЕРАС-54 на 45 и барабан на 60 в игру: sh tools/veras54_mags/chain.sh [m45] [d60] (mags_game_lp → bake → pack → export:
#   атлас 4096, .gltf «в руках» и _world, маски _coat — assets/models/weapons/veras54_mags; файл для Blender — «Игровая версия»
#   в библиотеке) → --import → python -X utf8 tools/veras54_mags/mags_game_imports.py → --import
tools/godot.cmd --headless res://tools/veras54_mags_check.tscn # магазины 45/60 в движке: узлы, патроны Round_NN, габарит, карты, шейдер плёнки;
                                                              # с окном (--windowed --resolution 1600x900) — снимки veras54_mags_*
# Хваты и клипы рук под магазины 45/60: blender … «Риг v13/VERAS54_Rig_v13.blend» --python tools/veras54_mags/mags_grip_file.py -- m45|d60 [--force] (файл хвата —
#   «Игровая версия/Хваты магазинов 45 и 60», пальцы правит владелец) → bash tools/veras54_mags/mags_clips.sh [m45] [d60] (30 клипов
#   «Клипы v13/*_{mag45,drum60}_v13»: перезарядки построителем автомата, проверка поворотом — mags_check_clip.py) → export_veras54.py -- viewmodel grips
#   (наборы подхватывает tools/veras54_mags/mags_vm.py) → --import
tools/godot.cmd --windowed --resolution 1600x900 res://tools/veras54_mags_vm_shots.tscn # магазины 45/60 в руках: модель на метке вместо штатного, свой набор клипов,
                                                              # патроны и подаватель по счёту, тактическая/полная/быстрая (старый вылетает), проверка удержанием R —
                                                              # поворот окнами остатка к глазам; снимки veras54_mags_vm_* (MAGS_ONLY=mag_545_45)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/export_veras54.py -- [viewmodel] [world] [detail] [grips] # ВЕРАС-54: руки+клипы (перезарядки, проверка, задержка, переводчик огня), мировая и подробная (конструктор) — .gltf с общими картами в assets/models/weapons/veras54; grips — наборы клипов под рукоятки ВАРН
tools/godot.cmd res://tools/veras_shots.tscn                # ВЕРАС-54 от первого лица: бедро, прицел, перезарядки, проверка магазина, мировая модель; рукоятки ВАРН V1/V2 и глушитель
                                                              # задержка «гильза в окне» и её устранение, вид при прочности 100/60/20 (один), прицеливание «с завалом» (СКМ, 45°), кисти крупно, быстрая перезарядка, проверка магазина с удержанием и поворотом кисти; снимки veras_* (VERAS_PART=grips|jam|states|cant|hand|fast|check|firemode)
bash tools/veras54_v13/clips/build_fire_modes.sh              # переводчик огня большим пальцем правой руки (clips/fire_mode_clip.py): АВ→2, 2→ОД, ОД→АВ без рукоятки и под ВАРН V1/V2
                                                              # → «Клипы v13/VERAS54_FireMode_*_v13.blend»; затем export_veras54.py -- viewmodel grips, --import, veras_shots VERAS_PART=firemode
tools/godot.cmd --headless res://tools/veras_hand_test.tscn # ВЕРАС-54, левая рука с рукоятками (ВАРН, угловая, на удлинителе): стоя, на ходу, в прицел и обратно — кости не копят масштаб, кисть у рукоятки
tools/godot.cmd res://tools/veras_gloss_shots.tscn          # ВЕРАС-54 под лампами тира: блики отделки v13 и жировых следов; снимки veras_gloss_*
                                                              # (GLOSS_MAG=mag_545_45|mag_545_60 — магазин 45/60, GLOSS_CHECK=1 — магазин у глаз, держать R)
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/veras_outdoor_shots.tscn # ВЕРАС-54 днём под небом (Пригород): бедро, магазин у глаз, прицел — на солнце
                                                              # и от солнца; глянец материалов виден только тут; снимки veras_outdoor_* (VERAS_OUT_TAG=имя; VERAS_OUT_MAG=mag_545_45|mag_545_60 — с магазином 45/60)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/prepare_veras_attachments.py -- geometry|bake|export|imports <varn_v1|varn_v2|supp_veras> [100]
                                                              # рукоятки ВАРН и глушитель из библиотеки → assets/models/attachments/<id> (сетка + LOD, карты 100)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_mag_loader.py # ускоритель снаряжения магазинов: модель, превью mag_loader_preview.png; затем --import и icon_bake -- mag_loader
python tools/trace_flare_gun_claude.py                        # ракетница Claude: контуры с фото владельца → _asset_src/flare_gun_claude/trace (ещё аргумент overlay — сверка рендера с фото)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_flare_gun_claude.py [-- render] # ракетница Claude и два патрона → assets/models/weapons/flare_gun_claude; render — превью в _asset_src/flare_gun_claude/Просмотр
python tools/flare_gun_claude_wear_masks.py                    # ракетница Claude: собственные маски износа → _asset_src/flare_gun_claude/textures/worn_v01
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/texture_flare_gun_claude.py -- build|render|inspect # ракетница Claude: слои UCUPaint на принятой геометрии, превью, проверка стека
python tools/import_weapon_model.py pm_highpoly_v5          # проверенный ПМ из _asset_src: дерево, PBR, размеры, бюджеты, CREDITS
python tools/import_weapon_model.py glock17_gen5            # Glock 17 Gen5 из _asset_src (--check — только проверка): дерево, PBR, размеры, бюджеты, CREDITS
tools/godot.cmd --headless res://tools/glock_test.tscn        # Glock: детали без курка/флажка/глушителя, LOD, патроны 17+1, дуло с обвесом
tools/godot.cmd --windowed --resolution 1280x720 res://tools/glock_shots.tscn # Glock: хват, ADS, перезарядка, третье лицо в docs/screens/glock_*.png
tools/godot.cmd --headless res://tools/export_weapon_refs.tscn -- "out=<папка>" # все стволы игры (и M4A1 с обвесами под левую руку) в GLB — образцы для хватов в Blender
tools/godot.cmd res://tools/mods_gallery.tscn                # витрина обвесов: сбоку, 3/4, крупные планы, вид из глаза
tools/godot.cmd --headless res://tools/build_test.tscn       # сборка деревом (WeaponBuild): старый угловой → кронштейн, пазы 20 мм, «занято»/«закроет прицел», кронштейн снимается с прицелом, линии прицелов
tools/godot.cmd --windowed --resolution 1280x720 res://tools/build_shots.tscn # снимки сборок: кронштейн 45° справа/слева, проставка, поворотный; docs/screens/build_*.png
tools/godot.cmd --windowed --resolution 1280x720 res://tools/thumb_shots.tscn # миниатюры экземпляров в сетке рюкзака (сборка, вынутый магазин, магазин на 60); docs/screens/thumb_*.png
tools/godot.cmd --windowed --resolution 1600x900 res://tools/builder_shots.tscn # конструктор оружия: обзор, точка, кронштейн по пазам (можно/занято), прицел на нём, из глаза, торговец, применено; docs/screens/builder_*.png
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_adapters.py -- [id …] # переходники (кронштейн 45°, проставка, удлинитель, поворотный) → assets/models/attachments/adapters
tools/godot.cmd --windowed --resolution 1280x720 res://tools/scope_far_shots.tscn # сильная оптика на планке над цевьём: в прицеле картинка, линза не красная; снимки scope_far_*
tools/godot.cmd res://tools/scope_sun_shots.tscn             # оптика против солнца (блики, аберрация) и открытые прицельные из глаза
tools/build_release.cmd                                      # сборка для друзей: export\RING.zip (RING.exe = Godot 4.7.2 + RING.pck, шаблоны не нужны)
tools/godot.cmd res://tools/net_host_test.tscn               # хост + tools/net_client_test.tscn в двух процессах —
                                                              # реальный ENet по 127.0.0.1, проверка репликации
tools/godot.cmd --headless res://tools/coop_hideout_host.tscn # + coop_hideout_client.tscn через 3 с: собрание в убежище —
                                                              # видят друг друга, телевизор общий, «Рейд всем» — оба в рейде
tools/godot.cmd --headless res://tools/coop_loading_test.tscn -- host client 17780 # + «-- client client 17780» через 3 с:
                                                              # зона 1, загрузка клиента остановлена на 35 с, связь и движение сохранены;
                                                              # второй аргумент host — медленный хост; порт отдельный от живой игры
tools/godot.cmd --headless res://tools/coop_raid_test.tscn -- host   # кооп на троих: + «-- c1» через 3 с, + «-- c2» ещё
                                                              # через 3 с (c1 — из главного меню, c2 — из своего убежища):
                                                              # в убежище и рейде все видят всех и как ходят, выстрелы
                                                              # напарников видно, дверь ТЦ, открытая клиентом, открыта у всех,
                                                              # генератор встал у хоста — c2 чинит, у всех снова весь свет,
                                                              # хост и c1 в зоне эвакуации, c2 нет — общий отсчёт, c2 не успел
tools/godot.cmd --headless res://tools/coop_items_test.tscn -- host [сцена] [two] # + «-- client …» через 3 с (порт 17791): гость в рейде снаряжает
                                                              # магазин, сортирует, меняет ствол, клавиши 1/2; гость вышел — рейд не ждёт (COOP_ITEMS_PEERS=3 — двое гостей)
tools/godot.cmd --disable-vsync res://tools/cpu_probe.tscn  # во что упирается процессор на уровне: выключает системы по очереди
python -X utf8 tools/hang_stacks.py [pid] [--all]            # игра зависла: стеки потоков живого процесса Godot — чего ждёт главный поток (без отладчика; не закрывать игру до снятия)
tools/godot.cmd --headless res://tools/mesh_census.tscn     # какие модели дают треугольники на уровне
tools/godot.cmd --windowed --resolution 1600x900 res://tools/rig_shots.tscn # ростовая фигура со слотами и разгрузка (подсумки, сумка сброса): тайник и окно рюкзака в рейде; снимки doll_*
tools/godot.cmd --headless res://tools/engraver_head_test.tscn # головка гравировщика в станке: вставить, нанести (размер, слева), вынуть; с окном — снимок окна станка
tools/godot.cmd --headless res://tools/trade_net_test.tscn -- host # + «-- client» через 3 с (порт 17793): обмен вещами в убежище и в рейде — отмена, обмен, рюкзак напарника виден, разошлись — отмена
tools/godot.cmd --windowed --resolution 1600x900 res://tools/workbench_repair_test.tscn # верстак, ремонт: изношенное плашками без прокрутки, починить одно и всё разом, нет денег — кнопки выключены; снимок workbench_repair
tools/godot.cmd --headless res://tools/hideout_keys_test.tscn # клавиши под окном убежища: открыт торговец или набирают текст — персонаж не ходит и не приседает
tools/godot.cmd --windowed --resolution 1600x900 res://tools/tv_light_shots.tscn # свет от телевизора ночью без генератора: видно мебель и дальнюю стену; снимки tv_light_*
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_rigs.py # разгрузки rig_*: модели (-- --preview <папка> — превью); затем --import и icon_bake -- rig_belt rig_chest rig_assault rig_heavy
tools/godot.cmd --headless res://tools/holster_test.tscn    # оружие убирается клавишей своего слота и достаётся ею же, бег быстрее; с открытым рюкзаком в рейде персонаж стоит
tools/godot.cmd --windowed --resolution 1600x900 res://tools/stickers_test.tscn # наклейки на оружии: клеить (предмет тратится), три на ствол, снять — пропала, зарубки «Счёта» за эвакуацию, страница верстака; снимок stickers_panel
tools/godot.cmd --headless res://tools/sticker_icons.tscn  # иконки наклеек из их рисунков (assets/stickers/<id>.png владельца или знак кодом) → assets/icons; затем --import
tools/godot.cmd --headless res://tools/birds_test.tscn     # птицы зоны 1: стаи сидят и кружат, взлетают от выстрела и от пробежавшего рядом, садятся, ночью нет, в дождь меньше; с окном — снимки birds_*
tools/godot.cmd --headless res://tools/shelter_exit_test.tscn # выход в рейд пешком: запечённого света нет, дверь тамбура, коридор и лестница во двор, план у стола, зона сбора — отсчёт и рейд
tools/godot.cmd --headless res://tools/printer_quest_test.tscn # задание «Фирменный знак»: этапы, сдача расходников разговором, печать наклеек, плёнка у Михалыча; с окном — снимок stickers_printer
tools/godot.cmd --headless res://tools/mags_test.tscn      # магазины: ПОЛН/ПУСТ и оценка после проверки, снарядить/разрядить поштучно (MagOps), нет патронов — текст, разрядка в клетки ящика и буфер 3×3, плиты по одной, вопрос о буфере, держать R
tools/godot.cmd --windowed --resolution 1280x720 res://tools/lumar_reticle_shots.tscn # ЛУМАР: метка шейдером (формы, цвета, толщина), окно под ПНВ на голове, ночной режим окна, окно настройки (P); снимки lumar_ret_*
tools/godot.cmd res://tools/sight_nvg_shots.tscn             # коллиматор в ПНВ, ЛЦУ: точка без ПНВ, луч в ПНВ; снимки sight_nvg_* (SHOTS_LOW=1 — качество «низко»)
tools/godot.cmd --headless res://tools/evac_test.tscn      # эвакуация группой: общий отсчёт 3 мин, ждём напарника, сброс, все в зоне — короткий, раненого выносят, не успел — без добычи
tools/godot.cmd --headless res://tools/story_test.tscn     # хроника рейда: вердикт по обстоятельствам и истории, стили не повторяются, 400 случайных рейдов без дыр в тексте, факты от хоста в уровне (с окном — снимок story_summary)
tools/godot.cmd --headless res://tools/anim_test.tscn      # анимации Persona при 144 к/с: клип ходьбы не скачет, спринт, присед и ходьба вприсядку — ступни на полу, лёжа, оружие в правой руке в любой стойке, левая кисть на цевье (SupportHandIK)
tools/godot.cmd --headless -s res://tools/bake_character_clips.gd  # клипы Mixamo (tools/character_clips.json) → persona_clips.res; что есть и чего нет — docs/animations.md
tools/godot.cmd --headless -s res://tools/bake_weapon_sockets.gd  # как оружие лежит в правой руке Persona (по позе прицеливания) → data/weapon_sockets.json
tools/godot.cmd res://tools/anim_stand.tscn                # стенд анимаций: новая и «как было» рядом, пол в клетку (ЛКМ, колесо, 1–5, Z — замедление);
                                                              # --headless … -- verify — скольжение опорной ступни и левая кисть на цевье; -- shots — снимки anim_stand_*
tools/godot.cmd --headless -s res://tools/measure_gait.gd   # шаг клипов передвижения (скорость, число шагов, постановка левой ноги, развёрнутые) → data/character_gait.json; после запекания клипов
tools/godot.cmd --headless res://tools/coop_quest_host.tscn  # + coop_quest_client.tscn через 3 с: общий сюжет группы (взял задание, осмотр, зачёт обоим)
tools/godot.cmd --headless res://tools/templates_test.tscn  # шаблоны снаряжения: сохранить, собрать из тайника, докупить, причины «нет»
tools/godot.cmd --windowed --resolution 1600x900 res://tools/trader_ui_test.tscn # Михалыч «Купить»: закреплённая шапка, поиск, группы, количество руками, чит «лут в продаже», готовые комплекты; снимки trader_*
tools/godot.cmd --headless res://tools/vehicle_test.tscn   # транспорт: одна коллизия на модель, навмеш под машинами вырезан (и под автобусом, и повёрнутым)
tools/godot.cmd --headless res://tools/god_test.tscn       # чит «бессмертие»: голова, граната, очередь — жив; лёжа — встал; выключил — урон проходит
tools/godot.cmd --headless res://tools/unlock_test.tscn    # чит «открыть всё» (Настройки / консоль unlock): каталоги, модули, верстак, станок гравировки; выключил — прогресс прежний
tools/godot.cmd --headless res://tools/stress_test.tscn    # стресс: пули рядом, спад в тишине, пороги, адреналин, обезболивающее
tools/godot.cmd res://tools/breaker_test.tscn              # главный рубильник света ТЦ: щитовая, свет погас → поднять, генератор; снимок breaker.png
tools/godot.cmd res://tools/vault_test.tscn                # перелезание (игрок и мародёр по связке навигации), бросок на землю; снимки vault_*
tools/godot.cmd res://tools/info_shots.tscn                # снимки окна описания предмета (info_*; ствол 47 % и прицел 30 % — состояние процентом) и прицела гранаты (nade_aim)
tools/godot.cmd res://tools/hideout_move_probe.tscn          # скорость в убежище: шаг / бег (с оружием, от первого лица)
tools/godot.cmd res://tools/sound_bench.tscn               # стенд звуков: одна страница — сворачиваемые разделы (оружие → классы → стволы, общие наборы;
                                                              # разделы каталога → подгруппы → карточки событий); справа событие: слушать в разных местах /
                                                              # вдали / за стеной / очередью, назначить запись проекта нескольким событиям, снять запасной
                                                              # набор или синтез (data/sound_active.json); «Входящие» — файлы из _sound_try/ → assets/audio.
                                                              # Снимок: -- capture:res://_sound_try/b.png select:<id> open:all
tools/godot.cmd --headless res://tools/sound_bench_test.tscn # стенд звуков: каталог покрывает всё, что зовёт игра; страница и карточки; назначения и снятие
                                                              # (и в Audio); новые файлы, отбор, перенос, CREDITS, воспроизведение
python tools/sound_catalog_md.py                               # список всех звуков для чтения: docs/sound_catalog.md
python -X utf8 tools/prepare_firearm_layers.py [--only ключ,ключ] # выстрелы CC0-библиотеки (_asset_src/sound_libraries) слоями дистанции:
                                                              # свой, вблизи, средняя, вдали, очень далеко → кандидаты стенда _sound_try/Выстрелы_CC0_дистанции
tools/godot.cmd --headless res://tools/shot_layers_test.tscn  # слои дистанции выстрела: какой слой на каком расстоянии, переход без провала громкости,
                                                              # свой выстрел — своего набора, очередь внахлёст с пределом, шина «Выстрелы» с потолком
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/npc_kit/<этап>.py [-- render]
                                                              # NPC «мародёр» одеждой симуляцией ткани (docs/assets/npc_marauder_v01.md): body → boots → pants →
                                                              # jacket → balaclava → assemble → details → deliver -- <папка>; схема сменной экипировки — docs/design/npc_modular_kit.md
# Игровая версия NPC и снаряжения (blender … --python): tools/npc_kit/game_lp.py -- lp uv bake lods (мародёр: ретопология, карты, LOD),
#   game_gear.py -- <вещь> (шлемы, брони, пояс, рюкзаки), game_pouches.py; затем скелет mixamorig_* как у Persona и экспорт в Godot:
#   game_rig.py -- character export [deliver=<папка>] → assets/models/characters/npc_marauder; game_rig.py -- helmets armor_poor armor_mid
#   armor_top belt daypack tourist raid pouches export → assets/models/characters/npc_gear (места подсумков — places.json);
#   --import, python -X utf8 tools/npc_kit/game_imports.py, --import. Справка — навык npc-character-gear («Скелет и Godot»).
tools/godot.cmd --headless res://tools/npc_rig_test.tscn    # мародёр v03 на скелете Persona: кости и rest как у Persona, те же клипы — та же поза, таз под рост (HipsHeight),
                                                              # ступни на полу, лёжа у земли; -- gear — снаряжение и подсумки надеваются (NpcGear);
                                                              # с окном (--windowed --resolution 1600x900) -- shots — снимки npc_rig_* (Persona слева, мародёр справа), -- gear shots — npc_gear_*
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
src/audio/     audio_system.gd — явные назначения data/audio_events.json; пустое действие молчит.
               Стенд Sonora 1.3, действия моделей — data/weapon_sound_slots.json; семейств и синтеза нет.
               Постэффекты Godot запрещены решением владельца 2026-10-21: обработка в готовой записи; в игре — выбор и 3D-громкость.
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
   Убежище — старая полуподвальная котельная в зоне 5, отдельная от ТЦ карта (люков из ТЦ нет): `scenes/levels/hideout.tscn`
   → `levels/shelter/Shelter_Interior.tscn` + двор `levels/shelter/Shelter_Exterior.tscn` (узел `Exterior`): здание стоит на
   открытой местности, окна настоящие, свет уличный (`ShelterWeather`), запечённого нет. В рейд выходят пешком: план
   принимают у стола планирования, дальше дверь тамбура (`ShelterExitDoor`), коридор, лестница, двор — и зона сбора у
   ворот (`RaidStartZone`): все, кто в убежище, в зоне — отсчёт и рейд (`HideoutLevel._tick_raid_start`).
   Собирается инструментами (см. «Пересборка убежища»); в котельном
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
9. **Масштаб (решение владельца 2026-10-24, стенд `tools/scale_probe.tscn`, набор E).** Предметы, которые человек
   берёт и трогает, — 1:1: оружие, руки, NPC, машины, мебель, ларьки, прилавки, ступени, бордюры, знаки. **Проходы и
   помещения — × 1,3 по ширине и × 1,15 по высоте** от реальных: дверные проёмы (0,9 × 2,1 → 1,17 × 2,42), ширина
   комнат, коридоров, проходов между стеллажами, тротуаров и проездов; высота потолков жилья и первых этажей
   (2,7 → 3,1). Высоты, которые и так большие (залы, паркинги, цеха), не раздувать. Расстояния между объектами
   на улице — 1:1. Поле зрения по умолчанию — **80° по горизонтали** (`Settings.FOV_H_DEFAULT`). Правило — для
   новой геометрии («Проспект» и дальше); готовые карты пересобираются по его слову. Причина: при реальных
   размерах в игре всё выглядит мелким (нет периферийного зрения и тела), а общий множитель ломает пропорции.
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
