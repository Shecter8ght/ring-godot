# RING — правила проекта для любого агента (Claude, Codex, локальные модели)

Тактический extraction-шутер от первого лица (изометрии нет; разведдрон отменён владельцем 2026-10-29). Godot 4.7, GDScript, Forward+.
Кооп на 3 игроков (один хостит). Реализм в графике: PBR, фототекстуры (CC0 / CC BY 4.0 с указанием авторства), реальные пропорции.

**Начать с:** `docs/OWNER_NOTES.md` (решения и предпочтения владельца, как с ним работать), конец
`docs/STATUS.md` (что сделано последним), `docs/BACKLOG.md` (что ждёт; помеченное «СЛЕДУЮЩЕЕ» — первым).
Порядок работ до демоверсии — `data/roadmap.json` (в игре: Esc → «Дорожная карта»); закончил работу из списка —
поставь ей статус там же.

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
вдоль оси (axis, t, r — см. SectorBuilder). Кольцо Ø250 (`f1_ring`) и старый сектор `f1_market` (Ø180) **удалены 2026-10-24** по решению владельца (в git — до этой даты);
рейд по умолчанию — `mall_map`.
**Решение владельца 2026-10-15:** ТЦ — отдельная карта Ø200 с прилегающей территорией
(`docs/design/mall_map.md`); `f1_ring` Ø250 — прежний серый черновик (удалён 2026-10-24); ТЦ с карты
зоны 1 уходит. Кольцо на Ø250 больше не развивать.
Серый черновик 1-го этажа Ø200 — `data/sectors/mall_1f.json` (генератор `tools/gen_mall_1f.py`, план —
`docs/design/mall_1f_plan.md`) + `scenes/levels/mall_1f.tscn`; отдельно в рейды не подключён — в рейде он часть
карты территории ТЦ `scenes/levels/mall_map.tscn` (черновик `mall_study` внутри рейдового уровня, маршрут
«ТЦ «РИНГ» · территория», данные `data/sectors/mall_map.json`, места заказа «Вернуть машину» — `scenes/levels/mall/`).

**Блокаут.** Сейчас уровень — серый блокаут (`"greybox": true`): стены без текстур, толщина по
классу конструкции (фасад 0.5 / противопожарная 0.3 / несущая 0.3 / перегородка 0.15), нормы и
источники — `docs/building_standards.md`. Чертёж сверху: `python tools/plan_svg.py data/sectors/mall_1f.json`
→ `docs/plans/mall_1f.svg` (берёт кольцо из JSON, постройки и точки — из .tscn уровня).

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
SCENE_BOARD.cmd                                              # доска сцен (tools/scene_board): все сцены, стенды и уровни на одной странице http://localhost:8767/ —
                                                              # что это, откуда запускают, что сломается, если убрать; «Запустить», «Убрать» в карантин E:/RING_карантин_<дата>/Доска_сцен
                                                              # (запись и отчёт.md) и «Вернуть»; из git — только кнопкой владельца «Убрать из git»; --lan — с телефона, только смотреть;
                                                              # отчёт для агентов: python -X utf8 tools/scene_board/inventory.py --md → docs/scene_inventory.md; названия и пометки — notes.json
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
tools/godot.cmd --headless res://tools/lean_light_test.tscn  # наклон у стены и свет на свои руки (приёмы Road to Vostok): наклон в стену
                                                              # останавливается (глаз не ближе Balance.LEAN_WALL_RADIUS), в другую сторону — полный;
                                                              # своя вспышка в мир не светит на руки, им — свой короткий свет; отражённый свет фонаря
                                                              # у стены есть, в поле — почти нет (Balance.VIEWMODEL_LIGHTS); с окном — снимки lean_light_*
tools/godot.cmd --headless res://tools/tree_shadows_test.tscn # тени деревьев (Balance.TREE_SHADOWS): видимые модели без тени, у каждой клетки
                                                              # копии «только тень» — вблизи полная модель, дальше карточки, порог общий; кусты
                                                              # «Проспекта» с тенью; треугольники деревьев в тени было / стало (зона 1, «Проспект»)
tools/godot.cmd --headless res://tools/far_grass_test.tscn   # «трава издали» (Balance.GRASS.far_look): рельеф зоны 1 берёт карту густоты травы
                                                              # и отрезок, где травинки уходят в землю, по качеству графики; снимки — grass_shots GRASS_ONLY=eye
tools/godot.cmd --windowed --resolution 1600x900 res://tools/scale_probe.tscn # стенд масштаба (вопрос владельца 2026-10-24 «реальные размеры мелкие»):
                                                              # пять наборов рядом — A всё 1:1, B предметы 1:1 / проходы × 1,2, C всё × 1,3, D предметы 1:1 / проходы × 1,3,
                                                              # E как D с высотами × 1,15 (улица, комната с дверью,
                                                              # коридор, стеллажи, лестница, фигура 1,75); F1/F2/F3 — поле зрения 75/80/90°, F5…F9 — к набору;
                                                              # SCALE_PROBE_SHOTS=1 — снимки scale_probe_* и выход
tools/godot.cmd --windowed --resolution 1600x900 res://tools/parking_probe.tscn # стенд высоты паркинга −1 «Проспекта» (владелец 2026-10-29): пять залов
                                                              # с местами и проездами карты — A как сейчас 2,8 м, B 2,8 м с отделкой как в Таркове (колонны 0,9 м
                                                              # с капителями, балки, воздуховод, трубы, лампы), C/D/E — 4,5/6/9 м в свету под балками; F1/F2/F3 —
                                                              # поле зрения, F5…F9 — к залу; PARKING_PROBE_SHOTS=1 — снимки parking_probe_* и выход
tools/godot.cmd --headless res://tools/carry_test.tscn       # стойка «наискосок» (Balance.WEAPON_CARRY): по умолчанию опущено, колесо вверх — от бедра, вниз — наискосок,
                                                              # бегом всегда наискосок, огонь поднимает и стреляет (клик не теряется), ПКМ — и обратно, лёжа и перезарядка
tools/godot.cmd --windowed --resolution 1280x720 res://tools/carry_shots.tscn # снимки стойки: от бедра и наискосок у стволов песочницы → docs/screens/carry_*;
                                                              # подбор позы: CARRY_VARIANTS="yaw=35 pitch=22 back=0.15 sy=0.04;…" CARRY_ONLY=wpn_sg_02
BAKE_MAPS.cmd                                                 # после ручных правок «Пригорода» и «Проспекта»: навигация ботов, точки укрытия, карты плана рейда
tools/godot.cmd --headless res://tools/zone01_ld_test.tscn   # Пригород, левел-дизайн: в каждом зале с интерьером есть лут и до всех мест лута можно дойти,
                                                              # места заказа «Вернуть машину», путь от появлений к выходам, серверная под ключом, голые отрезки улиц
python -X utf8 tools/zone01_ld_plan.py                         # схема левел-дизайна Пригорода (маршруты, горячие точки, интерьеры, укрытия, посты) → docs/design/zone01_level_design.png
tools/godot.cmd --headless res://tools/water_wade_test.tscn # брод в болоте зоны 1: по пояс, медленнее, без бега и «лечь», шаги — плеск (WaterBody, Balance.WATER)
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/grass_shots.tscn # трава: густой ярус, ветер, след после прохода и подъём, против солнца, кадры в секунду по ярусам; снимки grass_* (GRASS_TIME=dusk, GRASS_ONLY=eye,down)
tools/godot.cmd --windowed --resolution 1600x900 res://tools/blood_shots.tscn # кровь у стены в зоне 1: капли, следы по углу удара, подтёки, лужа под убитым, высохла; игрок ранен — лужа, утащили — мазок; снимки blood_*
python tools/gen_blood_maps.py                                 # карты крови: растекание лужи (перколяция), подтёки, следы капель → assets/textures/blood; затем --import
tools/godot.cmd --headless res://tools/settings_test.tscn   # настройки: шины громкости, качество графики (и тень солнца по качеству —
                                                              # Balance.SHADOW_QUALITY: низко 100 м / 2 каскада, средне 160 м, высоко как в сцене), мышь
tools/godot.cmd --headless res://tools/downed_test.tscn    # тяжёлое ранение: лечь, добить, голова/граната, поднять, тащить, спасение мародёров
tools/godot.cmd --headless res://tools/ragdoll_test.tscn   # трупы на модели (SkinRagdoll) не рвутся нитями: «Проспект», обычная смерть, удар в голову,
                                                              # добили лежачего (руки были под полом), у стены, огромный толчок; пули по телам, разбор ящиков
tools/godot.cmd --headless res://tools/quest_test.tscn     # сюжет «Не вернулся» целиком: этапы, смерть, эвакуация, сохранение, Антон, второй квест из данных
tools/godot.cmd --headless res://tools/terminal_story_test.tscn # переписка в терминале: принять заказ, история, отчёт, оплата этапа один раз, гостю тоже, задание ждёт карту
tools/godot.cmd --headless res://tools/quest_steps_test.tscn # шаги заказа машины в убежище: снимки, ранняя находка, пропуск шагов, сдача деталей без эвакуации, «не в карман»
tools/godot.cmd --headless res://tools/tutorial_test.tscn   # обучение новой игры: пакет на ящиках → рюкзак → полка → терминал, рюкзак заранее, старые сохранения
tools/godot.cmd --headless res://tools/prologue_test.tscn   # пролог «Первый выход» на «Проспекте» (docs/design/prologue.md): режим карты, вводный экран, сумка
                                                              # и пакет, ворота → ЧВК (окрик, предупредительный, огонь) → заново от ворот, цели по порядку и ранние
                                                              # действия, контрольная точка у кофейни, бой в зале → заново от кофейни, служебный коридор, засов,
                                                              # выход без пакета, обучение в убежище после; кооп: «-- host» + «-- client» через 3 с (порт 17797) —
                                                              # сумка каждому, пакет выносит гость, упавший напарник; с окном — снимки prologue_*
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
tools/godot.cmd --headless res://tools/reload_fast_test.tscn # ВЕРАС со снаряжением: одно R — обычная перезарядка, два быстрых — быстрая (−28 %, старый магазин на землю), держать R — магазин в руке;
                                                              # магазины из подсумков на броне без надбавки, старый — в сброс пустых, пояс с подсумками весит с магазинами
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
tools/godot.cmd --windowed --resolution 1600x900 res://tools/first_look_test.tscn # фризы первого раза на настоящей карте (зона 1;
                                                              # FIRST_LOOK_SCENE — другая): первый поворот по кругу, вверх-вниз, выстрел, фонарь, химсвет, фальшфейер —
                                                              # самый длинный кадр и собранные конвейеры; провал — кадр длиннее FIRST_LOOK_LIMIT_MS (100); чистый кэш — как у first_hit_test
tools/godot.cmd res://tools/asphalt_shots.tscn              # мокрый асфальт: сухо / сыро / лужи, от первого лица и изометрия (ASPH_TIME=day|dusk|night); снимки asphalt_*
tools/godot.cmd res://tools/ssr_probe.tscn                  # SSR движка: зеркало и мокрый асфальт при разных настройках отражений; снимки ssr_probe_*
python tools/fetch_sky.py                                      # ночное небо: HDRI Poly Haven + карта Луны NASA в assets/sky, CREDITS
tools/rtv_look.cmd                                            # стенд «Как в Road to Vostok» (опыт владельца 2026-11-05): две одинаковые поляны — опушка, земля, пруд, дом —
                                                              # наша (земля зоны 1, наша трава, деревья «Проспекта», R06) и из файлов их игры (RTV.pck читается из папки Steam,
                                                              # RTV_PCK — другой путь, в проект не копируется); игрок с оружием; F1 — свет наш / их, F2 — время, F3 — погода,
                                                              # F4 — другая поляна; -- shots — 64 кадра в E:/RTV_research/rtv_look (RTV_LOOK_OUT, RTV_LOOK_ONLY=day_clear);
                                                              # --headless … -- check — сборка и свет туда-обратно; выводы — docs/research/road_to_vostok.md
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
python -X utf8 tools/build_prospekt.py                        # карта «Проспект» (docs/design/prospekt_map.md): серый блокаут 232 × 212 м по правилу масштаба E →
                                                              # data/blockouts/prospekt.json + scenes/levels/prospekt_study.tscn (StudyBuilding с интерьерами, MallFiller,
                                                              # ProspektLandscape: переход, паркинг −1, кордон); перезаписывает оба файла
python -X utf8 tools/build_dorm.py                            # общежитие, пробный свет r6.1 на принятой геометрии r4, пороги и порталы r5 сохранены →
                                                              # data/blockouts/dorm.json, scenes/levels/dorm_study.tscn, docs/plans/dorm.png; режимы и замеры — docs/design/dorm_light_test.md
                                                              # вертикальные пути (5 открытых этажей, 5-й — техэтаж, пожарные лестницы, проломы, люки) — docs/design/dorm_routes.md
tools/dorm_study.cmd                                         # старт — выбранный владельцем вечер Б (VoxelGI) со светом «как в Таркове»; F1–F4 — вечер А / Б, ночь А, пасмурно А; F5 — холодные коридоры 4400 K, F6 — ночь Б, F7 — Б без оконных источников, F8 — пробная ночная луна (при старте выключена); F9 — выключить / включить свет «как в Таркове» (зоны окружения, основной), F10 или U — скрыть весь интерфейс (для записи ролика); L — расставить свет (колесо — вид, ЛКМ / ПКМ — поставить / убрать, сразу в dorm_found_lights.json);
                                                              # Esc — мышь / FOV 60–110° / SSIL, пыль, обработка; E — дверь или ящик (открыть), M — план, 1–9/0 и N/B — места
tools/godot.cmd --headless --fixed-fps 60 res://tools/dorm_study.tscn -- verify # 178 проверок: 97 помещений пешком (4 жилых этажа и технический зал),
                                                              # лестница до крыши, обе пожарные лестницы, проломы-скаты П1 и П3, 8 проломов в стенах, провал С1;
                                                              # кучи П2 и П4 (наверх на руках) и люк Л (вертикальная лестница) — по высотам, ходок их не лезет
tools/godot.cmd --windowed --resolution 1600x900 --script res://tools/dorm_ui_check.gd # интерфейс прогулки: подсказка умещается в окно,
                                                              # F10 / U прячет всё (панель света, подсказки, план, подписи) и возвращает; снимки docs/screens/dorm/ui_check_*
tools/dorm_play.cmd                                           # общежитие с настоящим игроком и ботами при свете стенда: в полёте расставить ботов где угодно
                                                              # (ЛКМ / ПКМ, 1–5 — кого, R — патруль по зданию / обход рядом / пост, G — игрок сюда, Backspace — заново),
                                                              # Enter — в тело игрока, боты оживают; Tab — любое оружие игры и конструктор (любые обвесы без покупки),
                                                              # F — дверь или ящик (открыть), Esc — свет, поле зрения, бессмертие; --headless res://tools/dorm_play.tscn -- check — навмеш, пути ботов
                                                              # до крыши, техэтажа и пожарных лестниц, расстановка, патруль и пост, конструктор; -- shots — снимки dorm/play_*
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/dorm_study.tscn -- shots # r6.1: 42 затронутых вида + шесть ночных пар с луной; 36 новых серий FPS/GPU → light_* / light61_*; «до» — light6_*; общая матрица 149 кадров / 83 серии
tools/godot.cmd --windowed --resolution 1600x900 res://tools/dorm_study.tscn -- bake # шесть объёмов VoxelGI трёх этажей (~4 с), цвета шейдера учтены; источники динамические, LightmapGI нет
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/dorm_study.tscn -- v3shots # материалы v03 (краска, побелка, паркет, плитка;
                                                              # src/blockout/dorm_v3) при свете «вечер Б»: снимки docs/screens/dorm/v3 и время кадра на видеокарте
                                                              # (DORM_V3_VIEWS=01_corridor,04_wash — выборочно; архивы пробы света не трогает);
                                                              # с модулями Blender (dorm_modules.gd: двери, окна, батареи); свои кадры —
                                                              # DORM_V3_VIEW="имя:x:y:z:куда_x:куда_y:куда_z;…" (крупные планы v3_m_*); DORM_V3_CASE=overcast_A — другой свет; DORM_V3_FILL=1 — свет от камеры; DORM_V3_TARKOV=0 — без «как в Таркове»; DORM_V3_LOOT=open — ящики партии 3 открыты
tools/godot.cmd --headless --script res://tools/dorm_v3_check.gd # материалы v03 в движке: карты и форматы (поля EXR без сжатия), шейдеры, палитра стенда, модули и их места
python -X utf8 tools/dorm_modules/godot_textures.py           # карты v03 из комплекта модулей → assets/textures/dorm_v3 (+ .import, шум износа); затем --import
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend" --python-exit-code 1 --python tools/dorm_modules/godot_export.py
                                                              # модули общежития в стенд: коробка двери, полотно, окно, батарея, марши, ограждения и повороты
                                                              # поручня — по сетке на модуль (-- <имя …> — выборочно)
                                                              # → assets/models/dorm/*.glb (материалы — dorm_modules.gd, карт в файлах нет); затем --import
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_found_lights.py -- build|export
                                                              # свет, оставленный людьми (фонарь, налобник, химсвет, кемпинговый фонарь, свечи, мигалка): build <.blend> — форма
                                                              # на просмотр (RING_Dorm_FoundLights), export (на этом .blend) → assets/models/dorm/found_*.glb + found_lights.json;
                                                              # расстановка в стенде — data/blockouts/dorm_found_lights.json (лампы плана там же убраны)
python -X utf8 tools/dorm_modules/gen_dorm_decals.py [имя …]            # следы общежития (кровь, грязь, пыль, копоть) из масок владельца
                                                              # Маски_АЛЬФА → assets/textures/dorm_decals; расстановка — data/blockouts/dorm_decals.json; затем --import
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_clutter.py -- <файл.blend>
                                                              # мусор общежития, партия 1 (банки, бутылки, окурки с пачкой, гильзы) → RING_Dorm_Clutter;
                                                              # затем мятые банки симуляцией: blender --background <файл.blend> --python tools/dorm_modules/crush_sim.py
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_trash_bags.py -- <файл.blend> [вариант …]
                                                              # мусор общежития, партия 2: чёрные мешки 60 л с синей лентой — симуляция плёнки по куче мусора
                                                              # (полный, лежит, полупустой; ~5 мин на мешок) → RING_Dorm_Bags
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_rubble.py -- <файл.blend>
                                                              # обломки стен: глыбы кладки со штукатуркой, кирпичи, обломок плиты ПК, штукатурка, крошка → RING_Dorm_Rubble
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_furniture.py -- <файл.blend> [preview <папка>]
                                                              # мебель общежития, партия 1 (комнаты): кровати двух- и одноярусная с панцирной сеткой на пружинах,
                                                              # матрас, тумбочка, шкаф, стол, стул, табурет, полка; вещи жильцов — холодильник, диван-книжка, ковёр,
                                                              # телевизор с антенной, плитка → RING_Dorm_Furniture (preview — кадры самопроверки)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_furniture2.py -- <файл.blend> [preview <папка> [номера]]
                                                              # мебель общежития, партия 2 (кухня, умывальня, туалеты): электроплита (и с распахнутой дверцей), чугунная
                                                              # мойка на тумбе со смесителем, стол-тумба, обеденный стол, шкафчик и полка для посуды, кастрюля, чайник,
                                                              # сковорода, бидон, бак; фаянсовая раковина на кронштейнах (и отбитая), зеркало; унитаз с высоким бачком
                                                              # и цепочкой (и с сорванным бачком), кабинки (дверца прикрыта / распахнута / выбита), крайняя перегородка;
                                                              # фаянс и мойка — лофтом по сечениям-суперэллипсам → RING_Dorm_Furniture2_v01.blend
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture2_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/furniture2_uv.py
                                                              # мебель партия 2, текстуры этап 1: развёртка 15 наборов (дверцы, ящик, дверца духовки и кабинки, сиденье —
                                                              # сетки «<слот>__<метка>»; панель плиты ×5 в развёртке под шкалы; варианты формы на время текстур сдвинуты —
                                                              # OFFSETS) и FBX → _asset_src/dorm_furniture2/sp; печать — print_bake.py (furniture2_uv) и python -X utf8
                                                              # tools/dorm_modules/furniture2_prints.py (ободки посуды, шкалы плиты, марка «РУСЛО»); Painter — python -X utf8
                                                              # tools/dorm_modules/furniture2_sp.py projects|stack|variants (finish-spec-2.json, свой экземпляр,
                                                              # FINISH_SP_JOBS=_asset_src/dorm_furniture2/sp_jobs); просмотр — furniture2_review.py -- <карты> <выход.blend>
                                                              # на файле развёртки (варианты отделки — копиями с подписью)
python -X utf8 tools/dorm_modules/furniture2_wear_zones.py [набор …] # мебель партия 2, износ (этап 2): места в развёртке —
                                                              # кромки своей картой (расстояние до выпуклого ребра: генератор кривизны Painter
                                                              # на панелях давал полосу в ладонь), удары точками, жир и пригар плиты, ржавчина
                                                              # у выпуска, разбухшая ДСП, пятна / кольца / порезы на столешницах, потёки и налёт
                                                              # в чашах, трещины глазури, ржавые потёки бачка, чешуйки краски кабинок и пятна
                                                              # амальгамы шумом с порогом → _asset_src/dorm_furniture2/wear; Painter —
                                                              # furniture2_sp.py wear [набор …] (построитель sp_furniture2_wear.py, код варианта
                                                              # отделки — ему: у крашеных свой износ) → maps_worn; просмотр — furniture2_review.py
                                                              # -- <maps_worn> <…_worn_v01.blend>
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture2_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/furniture2_game.py [-- набор …]
                                                              # мебель партия 2, игровые версии (бюджет «средне»: крупное 1K, посуда, бидон, бак 512; тяжёлое
                                                              # упрощено с запеканием нормали): подвижное — узлами с осью (дверцы и ящик тумб, дверца духовки
                                                              # и кабинки, сиденье; index movers — плюс открывает), варианты формы — свои модели (отбитая
                                                              # раковина, унитаз без бачка, крайняя перегородка), у кабинок коробки по доскам (colliders) →
                                                              # assets/models/dorm/furniture (тот же furniture.json; material — набор); --import, python -X utf8
                                                              # tools/dorm_modules/furniture_imports.py, --import; расстановка — furnish_rooms.py (кухни, умывальни,
                                                              # душевые, туалеты; pose подвижного, серые умывальники и чаши снимаются по clear)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/loot_containers/build_batch1.py -- <файл.blend> [preview <папка> [ключи]] [check [detail]]
                                                              # контейнеры для лута, партия 1 (форма на просмотр): сейф напольный и настенная ячейка, оружейный шкаф, кассовое место,
                                                              # сумка-укладка (ткань симуляцией) и настенная аптечка, картотечный шкаф; у каждого закрытый и открытый корень, подвижные узлы с осью;
                                                              # check — габариты, треугольники, пересечения в открытом положении → RING_Loot_Containers_v01.blend
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_items3.py -- <файл.blend> [preview <папка> [номера]]
                                                              # вещи общежития, партия 3 (RING_Dorm_Items, интервью 2026-11-02), группа А — ящики для лута и вещи
                                                              # жильцов: дощатые ящики под патроны (с цинками) и ЗИП, стальной сундук, раскладной ящик для
                                                              # инструментов, жёсткий чемодан на колёсах, спортивная сумка (ткань симуляцией на «вещах»),
                                                              # картонная коробка; у каждого — закрытый и открытый / раскрытый / полупустой корень, крышки и
                                                              # створки — узлами с осью; группа Б — плакаты на кнопках и скотче (целый, надорван,
                                                              # угол отклеился), вырезка, календарь, учебная таблица на рейках (и сорванная), чертёж
                                                              # на кнопках (и свернулся), картины в раме (висит на тросике, разбито, упала; пластиковая)
                                                              # группа В — техника 2020+: системный блок со стеклом (нутро: плата, кулер, видеокарта,
                                                              # память, вентиляторы; вскрытый — стекло снято, видеокарты и памяти нет), монитор 24″ (и
                                                              # разбитый), клавиатура (104 колпачка), мышь, ноутбук 15,6″ (открыт, закрыт, разбит)
                                                              # группа Г — тубус телескопический (и открытый: крышка снята, торчат свёрнутые
                                                              # чертежи), тетради (школьная — закрыта, раскрыта, стопкой; общая), учебники в твёрдом
                                                              # переплёте (закрыт, раскрыт, стопкой, ряд стоя)
                                                              # → RING_Dorm_Items_v01.blend
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Items_v01.blend | …_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/items3_uv.py [-- набор …]
                                                              # вещи партии 3, текстуры этап 1: развёртка 33 наборов (подвижное и прячущееся — сетки «<слот>__<метка>»;
                                                              # бумага — слой «Печать» из формы, изнанка мельче; сумка — выкройкой; доски — волокнами вдоль U, картон — гофрой;
                                                              # верх клавиш ×3, корешки ×2,5; тонкие листы лицом наружу) и FBX → _asset_src/dorm_items3/sp; на файле развёртки —
                                                              # переделка отдельных наборов. Карты геометрии — print_bake.py (items3_uv; у листов ещё «prm»), оси книг
                                                              # и тетрадей — items3_frames.py; печать — python -X utf8 tools/dorm_modules/items3_prints.py [набор …]
                                                              # (картинки владельца RING_Dorm_Items/картинки по развёртке листа и по лицу, трафареты, коробка,
                                                              # календарь, правила, таблица Менделеева, страницы, подписи клавиш, марки); Painter — python -X utf8
                                                              # tools/dorm_modules/items3_sp.py projects|stack|variants|prints (свой экземпляр, FINISH_SP_JOBS=
                                                              # _asset_src/dorm_items3/sp_jobs); просмотр — items3_review.py -- <карты> <выход.blend> на файле
                                                              # развёртки (состояния формы — в позах формы, варианты — копиями)
python -X utf8 tools/dorm_modules/items3_wear_zones.py [набор …] # вещи партии 3, износ (этап 2): места в развёртке — пыль, кромки и углы,
                                                              # следы сапог, ржавчина фурнитуры, отсыревший низ коробки; у бумаги — пожелтение, сырость, ржавчина у
                                                              # кнопок, мухи, захватанные углы, ручка и карандаш в координатах листа (обведённые даты календаря, подписи);
                                                              # затёртые клавиши, надписи на обложках тетрадей, потёртые углы и корешки → _asset_src/dorm_items3/wear;
                                                              # Painter — items3_sp.py wear [набор …] (построитель sp_items3_wear.py; свой износ у каждого варианта отделки
                                                              # и картинки) → maps_worn; просмотр — items3_review.py -- <maps_worn> <…/RING_Dorm_Items_worn_v01.blend>
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Items_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/items3_game.py [-- набор …]
                                                              # вещи партии 3, игровые версии (бюджет «средне»: крупное и бумага 1K, мышь, тетради, учебник 512; листы плакатов
                                                              # и чертежей, ткань сумки, чемодан, тубус, мышь упрощены с запеканием нормали): каждое состояние формы — своя модель
                                                              # (it_ammo / it_ammo_open, it_frame_fallen, it_pc_opened …), у открытых ящиков и чемодана крышка и створка — узлы
                                                              # с углом открытия (movers: open) → assets/models/dorm/furniture (тот же furniture.json); --import, python -X utf8
                                                              # tools/dorm_modules/furniture_imports.py, --import; расстановка — furnish_rooms.py (комнаты по виду, коридоры, вахта,
                                                              # комната отдыха, кладовые, клетка техэтажа); ящики, сундук, ящик для инструментов, чемодан, сумка, коробка
                                                              # обыскиваются (item.loot → LootContainer, таблицы dorm_* в data/loot.json; стенд — src/blockout/dorm_loot_box.gd:
                                                              # после обыска открытая модель, крышка доводится до открытой; в стенде открыть — E в прогулке, F в dorm_play)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/furniture_uv.py
                                                              # мебель, текстуры этап 1: развёртка и FBX → _asset_src/dorm_furniture/sp; печать — print_bake.py
                                                              # (furniture_uv) и python -X utf8 tools/dorm_modules/furniture_prints.py (тик, орнамент ковра, марки);
                                                              # Painter — python -X utf8 tools/dorm_modules/furniture_sp.py projects|stack|variants (свой экземпляр,
                                                              # FINISH_SP_JOBS=_asset_src/dorm_furniture/sp_jobs); просмотр — finish_review.py … furniture_uv, затем
                                                              # furniture_review.py -- <карты> на том же файле (варианты отделки рядами)
python -X utf8 tools/dorm_modules/furniture_wear_zones.py [предмет …] # мебель, износ (этап 2): места в развёртке (пыль, грязь у пола, удары по раме, касания,
                                                              # засалено, пятна, прожоги, кольца от кружек, жар) → _asset_src/dorm_furniture/wear; Painter —
                                                              # furniture_sp.py wear [предмет …] (группа «Этап 2 — износ», построитель sp_furniture_wear.py,
                                                              # варианты тоже) → maps_worn; просмотр — finish_review.py / furniture_review.py с maps_worn
python -X utf8 tools/dorm_modules/carpet_maps.py              # ковёр общежития, карты 4K без Painter: ворс генератором (furniture_prints.py furn_carpet —
                                                              # пучки 2,4 × 2 мм, край узора вперемешку, нормаль, шероховатость) и износ по зонам →
                                                              # maps/ и maps_worn/furn_carpet; развёртка ковра — furniture_uv.py -- furn_carpet в файле развёртки
                                                              # (лицо — 75 % карты), карты геометрии 4K — print_bake.py (RES модуля развёртки)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_worn_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/carpet_render.py -- <выход.blend> [<папка кадров> [1 2 3]]
                                                              # ковёр с настоящим ворсом (carpet_pile.py: волокна Geometry Nodes на объекте-волосах, Principled
                                                              # Hair, цвет из карты по корню) в углу комнаты общежития под вечерним солнцем: три камеры, Cycles
                                                              # (CARPET_QUICK=1 — проба вдвое меньше и мало выборок)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/furniture_game.py -- [предмет …]
                                                              # мебель, игровые версии (бюджет «подробнее»): карты износа 2K (ковёр 4K) как есть, тяжёлое упрощено
                                                              # с запеканием в нормали, панцирная сетка — плоскость с плиткой ячеек (в стенде — alpha hash) →
                                                              # assets/models/dorm/furniture (+ варианты отделки, furniture.json); --import, python -X utf8
                                                              # tools/dorm_modules/furniture_imports.py, --import; расстановка — python -X utf8
                                                              # tools/dorm_modules/furnish_rooms.py → data/blockouts/dorm_furniture.json (по виду комнаты)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/dorm_modules/build_electrics.py -- <файл.blend> [preview <папка>]
                                                              # электрика общежития, партия 1 (форма): люминесцентные — открытый на две трубки ЛБ-40 и с рассеивателем
                                                              # (варианты: трубки, обломок, рассеиватель висит / сорван), плафон, патрон на витом шнуре с лампой А60,
                                                              # выключатели и розетки — накладные круглые из карболита и белые утопленные, распаечная коробка,
                                                              # провод плоский на гвоздиках и витой на роликах модулями → RING_Dorm_Electrics
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Electrics_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/electrics_uv.py
                                                              # электрика, текстуры этап 1: развёртка по наборам деталей (трубка и лампа общие, отдельные игровые узлы —
                                                              # сетки «<слот>__<метка>») и FBX → _asset_src/dorm_electrics/sp; печать — print_bake.py (electrics_uv) и
                                                              # python -X utf8 tools/dorm_modules/electrics_prints.py; Painter — python -X utf8 tools/dorm_modules/electrics_sp.py
                                                              # projects|stack|variants (драйвер мебели furniture_sp.py, свои папки); просмотр — electrics_review.py
                                                              # -- <карты> <выход.blend> на файле развёртки
python -X utf8 tools/dorm_modules/electrics_wear_zones.py [набор …]  # электрика, износ (этап 2): места в развёртке (пыль сверху, почерневшие
                                                              # концы трубок, мухи и пыль в рассеивателе и плафоне, захватано, копоть у гнёзд, налёт
                                                              # в колбе, закраска) → _asset_src/dorm_electrics/wear; Painter — electrics_sp.py wear [набор …]
                                                              # (построитель sp_electrics_wear.py; каждый вариант отделки, у настенного ещё «краска» /
                                                              # «побелка») → maps_worn; просмотр — electrics_review.py -- <maps_worn> <выход.blend>
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Electrics_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/electrics_game.py
                                                              # электрика, игровые версии (бюджет «средне»: светильники 1K, настенное и провода 512, тяжёлое
                                                              # упрощено с запеканием нормали): модели собраны из наборов как в форме (ЛСП 2/1/0 трубок, ЛПО закрыт /
                                                              # висит / сорван, плафон, патрон, выключатели с рычажком и клавишей, модули провода с портами) →
                                                              # assets/models/dorm/electrics (+ electrics.json); --import, python -X utf8 tools/dorm_modules/furniture_imports.py
                                                              # electrics, --import; расстановка — python -X utf8 tools/dorm_modules/electrify.py → data/blockouts/dorm_electrics.json
                                                              # (стенд: src/blockout/dorm_electrics.gd, мигающие — dorm_flicker_light.gd)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Containers_v01.blend" --python-exit-code 1 --python tools/loot_containers/lc_uv.py [-- набор …]
                                                              # контейнеры для лута, партия 1, текстуры этап 1: развёртка на открытом состоянии (закрытое — те же UV), листы оболочек по сторонам
                                                              # «<объект>__внутри» и т. п., шильдики и наклейки тонкими пластинками → RING_Loot_Containers_uv_v01.blend, _asset_src/loot_containers/sp/<набор>.fbx;
                                                              # затем python -X utf8 tools/loot_containers/lc_cards.py (новые карточки каталога), lc_spec.py (finish-spec.json из таблицы слотов),
                                                              # blender -b <uv.blend> --python tools/loot_containers/lc_print_bake.py (карты геометрии .npy), python -X utf8 tools/loot_containers/lc_prints.py (вымышленные
                                                              # марки, шильдики, шкала лимба, клавиши, кресты — печать слоем), Painter: FINISH_SP_JOBS=_asset_src/loot_containers/sp_jobs, python -X utf8 tools/asset_kit/finish/sp_run.py start;
                                                              # python -X utf8 tools/loot_containers/lc_sp.py projects|stack [набор …] → _asset_src/loot_containers/maps; просмотр —
                                                              # blender -b <uv.blend> --python tools/loot_containers/lc_review.py -- <папка карт> <выход.blend> [shots <папка>]; проверка развёртки — lc_check.py
python -X utf8 tools/loot_containers/lc_fetch_materials.py ; blender -b <uv_v01.blend> --python tools/loot_containers/lc2_dump_uv.py -- <json> ; python -X utf8 tools/loot_containers/lc2_struct.py
                                                              # отделка v02 на фото-основах: загрузка наборов CC0 (ambientCG) → _asset_src/textures, выгрузка развёртки, структурные карты (строчки, валик, точки сварки);
                                                              # blender -b RING_Loot_Containers_uv_v01.blend --python tools/loot_containers/lc2_review.py -- <finish_v02.blend> [shots <папка> [кадры]] — материалы-узлы и файл просмотра
tools/loot_containers/lc3_start.cmd ; python -X utf8 tools/loot_containers/lc3_sp.py stack [набор …] [k=<сила износа>] [floor=<грязь у пола>]
                                                              # контейнеры для лута, партия 1, отделка v03 (образцы владельца 2026-11-13: шкаф зелёный, сейф чёрный, касса состаренный АБС;
                                                              # заводская отделка и износ сразу, в Painter): свой мост (_asset_src/loot_containers/sp_jobs_v03), стек на проектах v01 (lc3_sp.py:
                                                              # отделки V3, замены по коду и по сетке; lc3_stacks.py: группа «Этап 2 — износ», РИСУНОК — только фото-маски библиотеки
                                                              # Маски_АЛЬФА, генераторы Painter дают лишь место) → _asset_src/loot_containers/maps_v03/<набор>, проекты sp/<набор>_v03.spp;
                                                              # просмотр: blender -b RING_Loot_Containers_uv_v01.blend --factory-startup --python tools/loot_containers/lc3_review.py --
                                                              # <textures/finish_v03> <finish_v03.blend> [shots <папка> [кадры]] [res=1600x1000] (тёмная студия, как у Sketchfab); листы сверки с образцами —
                                                              # python -X utf8 tools/loot_containers/lc3_compare.py [gun safe cash]
                                                              # перед стеком (круг 2: износ по форме): python -X utf8 -I tools/loot_containers/lc3_masks.py (маски владельца → masks_v03) и lc3_zones.py [набор …]
                                                              # (кромка, низ, верх, вокруг ручек по картам геометрии → wear_v03)
                                                              # круг 3: lc3_digits.py («0.00» на окнах кассы), lc3_measure.py [набор деталь-дверь] (медиана и разброс цвета плоскости двери, доля светлых вдоль кромки)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/loot_containers/medbag2.py -- build <RING_Loot_MedBag_v02.blend> [preview <папка>]
                                                              # медсумка v02, нейлоновая шитая (форма high-poly: кант, молнии, стропы, строчки; закрыта / раскрыта); затем blender -b <файл> --python tools/loot_containers/lc3_bag_uv.py -- pack <uv.blend>,
                                                              # … -- bake A B (карты геометрии), python -X utf8 tools/loot_containers/lc3_bag_maps.py A B copy (карты отделки по маскам владельца),
                                                              # lc3_bag_view.py -- build | shots (файл просмотра и кадры Cycles)
python -X utf8 tools/dorm_modules/brick_rects.py [--preview]   # кирпичи без швов со снимка стены (Red Bricks 04) → brick_rects.json в _asset_src: каждый кирпич обломков берёт лицо настоящего
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Clutter_v01.blend | RING_Dorm_Bags_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/clutter_uv.py
                                                              # мусор, текстуры: развёртка 12 вещей и FBX для Painter; дальше python -X utf8 tools/dorm_modules/clutter_sp.py
                                                              # projects|stack (тот же Painter, что у оставленного света); просмотр со студией —
                                                              # blender --background <…_uv_v01.blend> --python tools/dorm_modules/finish_review.py -- <карты> <выход.blend> clutter_uv|found_lights_uv
python -X utf8 tools/dorm_modules/print_designs.py             # печать мусора и маркировка оставленного света: вымышленные марки → _asset_src/dorm_clutter/prints;
                                                              # blender --background <…_uv_v01.blend> --python tools/dorm_modules/print_bake.py -- <папка geo> clutter_uv|found_lights_uv
                                                              # (положение/нормаль/деталь в развёртку) → python -X utf8 tools/dorm_modules/print_apply.py [вещь …]
python -X utf8 tools/dorm_modules/wear_zones.py [вещь …]     # общежитие, износ (этап 2): места в развёртке по картам геометрии print_bake.py
                                                              # (пыль сверху, грязь у пола, подтёк, сырость, кровь) → _asset_src/<набор>/wear; печать слоем —
                                                              # print_apply.py --layers; Painter: found_lights_sp.py|clutter_sp.py wear [вещь …] (группа «Этап 2 — износ»,
                                                              # построитель tools/dorm_modules/sp_dorm_wear.py — профили вещей, сила по возрасту)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<…_uv_v01.blend | RING_Dorm_Rubble_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/game_props.py -- props|rubble [вещь …]
                                                              # общежитие, игровые версии (бюджет «экономно»): свет и мусор — упрощение той же развёртки, нормали с high-poly,
                                                              # карты Painter уменьшены до 512 / 1K; обломки — скрытые грани прочь, новая развёртка, фотоматериалы запечены →
                                                              # assets/models/dorm/props/*.gltf (стекло «_стекло», светящееся «_свет»); затем --import; расстановка мусора —
                                                              # data/blockouts/dorm_props.json (dorm_geometry.gd: far, solid, tilt), свет — dorm_found_light.gd
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_FoundLights_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/found_lights_uv.py
                                                              # оставленный свет, текстуры: развёртка принятой формы и FBX для Painter; дальше
                                                              # python -X utf8 tools/dorm_modules/found_lights_sp.py projects|stack (стек по finish-spec.json)
python -X utf8 tools/dorm_light_archive.py --verify           # r6: хеши архива light5_* и неизменность геометрии, масштаба, базовых цветов и 14 камер
python -X utf8 tools/dorm_light_r61_archive.py --verify       # r6.1: 46 побайтных файлов «до» light6_* (42 вида, два JSON, две калибровки)
tools/godot.cmd --headless --script res://tools/dorm_light_geometry_check.gd # r6: те же треугольники / нормали / UV / коллизии при группировке по этажам и наружным граням
python -X utf8 tools/dorm_light_report.py                      # r6.1: проверка 149 кадров / 83 серий, новые 48 кадров / 36 серий, неизменные камеры и калибровка → light61_summary.json
tools/heli_study.cmd                                          # карта «Плотина» (на ней задание «Вертолёт», docs/design/mission_helicopter.md), серый стенд v05:
                                                              # прогулка (F — полёт, M — план, 1–9/0 — места); -- check | perf | shots | ortho — снимки docs/screens/heli_v05;
                                                              # HELI_PLAN=v04 — прежняя версия; схемы и данные — python -X utf8 tools/mission_helicopter_v05.py [plans] [data]
tools/dam_play.cmd                                            # «Плотина» с настоящим игроком, оружием и ботами (как dorm_play): в полёте расставить ботов (ЛКМ / ПКМ,
                                                              # 1–6 — кого, R — что делает, N / B — места, G — игрок сюда), Enter — в тело игрока; навигация ботов печётся
                                                              # кусками 128 м вокруг игрока и ботов; --headless res://tools/dam_play.tscn -- check, с окном -- shots
tools/sanatorium_study.cmd                                    # карта «Санаторий» (docs/design/sanatorium_map.md), серый блокаут по принятым планам: прогулка
                                                              # (M — схема участка v13, 1–9/0 и N/B — места, F — полёт); с 2026-11-08 правится руками в редакторе
                                                              # (scenes/levels/sanatorium_study.tscn + scenes/levels/sanatorium/*, кисть земли — docs/level_editing.md);
                                                              # генератор — только в папку: SANATORIUM_OUT=<папка> python -X utf8 tools/build_sanatorium.py (план с метками
                                                              # групп; разовый перенос в сцены сделал tools/sanatorium_to_scenes.tscn — повторно не запускать: сотрёт правки);
                                                              # --headless --fixed-fps 60 res://tools/sanatorium_study.tscn -- verify — пешком все 623 помещения, лестницы,
                                                              # каскад, тропы, дороги, ось КПП → маяк, ~45 с (SANATORIUM_ROUTES=id,… — выборочно, SANATORIUM_TRACE=1 —
                                                              # точки хода); с окном -- shots — docs/screens/sanatorium (SANATORIUM_SHOTS=имя,…; SANATORIUM_TIME, _WEATHER)
                                                              # --windowed --resolution 1920x1080 --disable-vsync … -- perf — кадры по видам и местам → perf.txt, perf.json;
                                                              # --headless … -- snapshot — снимок сцены в прежнем формате → data/blockouts/sanatorium_snapshot*.json (для обзора);
                                                              # обзор: python -X utf8 tools/sanatorium_ld_plan.py — лучи на высоте глаз, доля длиннее 90 м по зонам →
                                                              # docs/design/sanatorium_sightlines.png, docs/screens/sanatorium/sightlines.json
                                                              # (--breaks 90 — места групп елей против длинного обзора → docs/design/data/sanatorium_view_breaks.json,
                                                              # ставить их теперь руками — деревьями TreeSpot; после — снимок и замер заново)
python -X utf8 tools/fetch_sanatorium_ground.py                 # земля «Санатория»: восемь грунтов 4K (CC0 ambientCG, Poly Haven) → _asset_src/textures/<id>
python -X utf8 tools/build_sanatorium_ground.py                 # массивы слоёв земли → assets/terrain/sanatorium_{albedo,normal,arm}.jpg; затем --import
                                                              # (маски и трава — «Кисть земли» в редакторе; шейдеры src/world/sanatorium_ground, sanatorium_lake)
tools/godot.cmd --headless res://tools/blockout_edit_test.tscn # «Санаторий», правка руками: скрытое глазком в игре не существует (ни стен, ни помещений
                                                              # в проверке), валун ×2 — коллизия ×2, повёрнутая беседка, марш шире — в склейке шире
tools/sanatorium_play.cmd                                     # «Санаторий» с настоящим игроком, оружием и ботами (как dam_play): расстановка в полёте, Enter — в тело;
                                                              # --headless res://tools/sanatorium_play.tscn -- check, с окном -- shots — docs/screens/sanatorium/play_*
tools/prospekt_study.cmd                                      # прогулка по блокауту «Проспекта»: M — план, 1–9/0 — места, N/B, F — полёт;
                                                              # --headless res://tools/prospekt_study.tscn -- verify — здания, места лута, уровни, 16 мест, 7 маршрутов пешком (пролог
                                                              # до тоннеля, заходы → выходы, паркинг −1, банк до крыши, подкоп в хранилище), открытые куски ≤ 30 м, кордон
                                                              # не пройти; -- shots — снимки docs/screens/prospekt/ (PROSPEKT_VIEW=имя:x:y:z:куда_x:куда_y:куда_z — свой кадр,
                                                              # несколько — через «;», или имена готовых кадров); PROSPEKT_LIGHT=all_variants -- shots — стенд света
                                                              # (tools/prospekt_light_variants.gd): умолчания, черты освещения EFT по одной и вместе → <вариант>__<кадр>.png;
                                                              # -- snapshot — план по узлам сцены (улицы, вещи, постройки) → data/blockouts/prospekt_snapshot.json
tools/godot.cmd --headless res://tools/plan_piece_test.tscn  # улицы «Проспекта» узлами (PlanPiece): сдвиг, поворот 90° и 30° (стена → коробка), растяжение,
                                                              # глазок, копия, разворот пандуса, подъём лестницы, покрытие с вырезами — в плане и в физике
tools/paving_probe.cmd                                        # стенд покрытий «Проспекта» по фото владельца (docs/design/prospekt_paving.md): три куска
                                                              # улицы А / Б / В — газон, бордюры ГОСТ 6665, тротуар, дорога с зеброй, площадь у вокзала; детская
                                                              # и корт; F2 — время, F3 — погода, F5–F8 — куски; -- shots — снимки docs/screens/paving_probe
                                                              # (PAVING_ONLY, PAVING_PLAIN=1 — без шейдеров покрытий, замер их стоимости); шейдер — StreetPaving;
                                                              # люки и решётка ливнёвки — python -X utf8 tools/gen_street_iron_textures.py
tools/godot.cmd --headless res://tools/prospekt_surfaces_test.tscn # «Проспект»: из чего поверхности для шагов, гильз и попаданий (Surfaces) —
                                                              # 14 точек: асфальт, плитка, газоны, крошка, корт, грунт стройки, паркинг, фонтан, бордюр, люк, решётка
python -X utf8 tools/prospekt_ld_plan.py                       # «Проспект», левел-дизайн: схема (маршруты, лут, появления, выходы) и замер обзора на высоте глаз —
                                                              # лучи длиннее 90 м красным → docs/design/prospekt_level_design.png, docs/screens/prospekt/sightlines.json
                                                              # (по снимку сцены: сначала prospekt_study -- snapshot)
python -X utf8 tools/prospekt_vershina_plan.py                 # «Проспект», район высоток: чертежи предложения по переделке ЖК «Вершина»
                                                              # (генплан, первый этаж стилобата, развёртка, разрез) → docs/design/prospekt_vershina_*.png;
                                                              # расстановка — словари в скрипте, в сцену не внесена (docs/design/prospekt_map.md §21)
python -X utf8 tools/prospekt_house7_plan.py                 # «Проспект», дом 7 (пробный жилой дом): чертёж под место и фасады → docs/design/prospekt_house7_1_site.png, prospekt_house7_2_facades.png (docs/design/prospekt_bc5_yard_concepts.md; в сцену не внесено)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_houses/house7.py -- <выход.blend> [preview <папка>] [check]
                                                              # «Проспект», дом 7 — форма без текстур (набор частей фасада H_* для всех домов серии + свои узлы: портал, служебная дверь, кровля):
                                                              # tools/prospekt_houses/kit.py (модули) и house7.py (сборка из экземпляров, check — габарит / этажи / оболочки, preview — камеры и ортофасады);
                                                              # python -X utf8 tools/prospekt_houses/sheets.py <папка Просмотр/form> — листы сверки с концептом; файл и кадры — E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_houses/house7_finish.py -- <выход.blend> [preview <папка>] [only cam,cam] [res 1400x875] [samples 64]
                                                              # «Проспект», дом 7 — материалы v01 поверх принятой формы (форму-файл не трогает): плиточные фото-наборы CC0 по мировым координатам
                                                              # (tools/prospekt_houses/materials.py) + фото-маски владельца, грязь по форме, декали, вестибюль, клумба с растениями, двор, мир с HDRI, кадры Cycles;
                                                              # карты и маски готовит python -X utf8 tools/prospekt_houses/prep_textures.py → E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures;
                                                              # листы сверки с концептом и замер цвета — python -X utf8 tools/prospekt_houses/sheets_finish.py <папка Просмотр/finish>
python -X utf8 tools/prospekt_north_side_plan.py              # «Проспект», северная сторона проспекта: чертежи предложения — квартал, развёртка
                                                              # и карманы, банк «Капитал» по этажам, автомойка «Блеск» → docs/design/prospekt_north_*.png;
                                                              # в сцену не внесено (docs/design/prospekt_map.md §22)
python -X utf8 tools/prospekt_ideas_plan.py                   # «Проспект»: сводный план предложений по восьми зонам и идеям
                                                              # → docs/design/prospekt_ideas_9_master.png (docs/design/prospekt_map.md §24; в сцену не внесено)
python -X utf8 tools/prospekt_stage2_plan.py [10 … 16]         # «Проспект», вторая очередь: чертежи по решениям владельца — генплан, «Ярус» со складом,
                                                              # вокзал и площадь, Объездная на эстакаде (и она же в геймплее), малые зоны → docs/design/prospekt_s2_<N>_*.png
                                                              # (docs/design/prospekt_map.md §25; в сцену не внесено)
python -X utf8 tools/prospekt_patch.py <этап>                    # «Проспект», перенос чертежей этапами (docs/tasks/prospekt_north_vershina_build.md): патч этапа
                                                              # (1_street …) из словарей чертежей → data/blockouts/prospekt_patch_<этап>.json: remove (вещи, куски улиц, узлы) и add
                                                              # вторая очередь (docs/tasks/prospekt_stage2_build.md): s2_1a_southwest — граница по X −248, юго-запад, Вокзальная улица,
                                                              # стройка, гаражи, почтовый двор; этап заодно правит граничные данные, заходы и ящики городка (prospekt.json, sectors, prospekt.tscn)
tools/godot.cmd --headless res://tools/prospekt_apply_patch.tscn -- <этап> # применить патч к scenes/levels/prospekt_study.tscn: убрать и добавить узлы (PlanPiece, PropSpot),
                                                              # у добавленных meta patch_stage; повтор того же этапа — без дубликатов; копию сцены сделать до первого запуска
python -X utf8 tools/build_prospekt_raid.py                   # рейдовая карта «Проспект» из плана блокаута: data/sectors/prospekt.json, scenes/levels/prospekt.tscn
                                                              # (заходы, выходы, посты — кордон ЧВК, патрули, гнёзда, подход, места лута), своё освещение
tools/godot.cmd --headless res://tools/bake_prospekt_nav.tscn  # перепечь кэш навигации data/navigation/prospekt после правки блокаута
tools/godot.cmd --headless res://tools/bake_cover_points.tscn [-- prospekt mall_map zone01_mall] # точки укрытия карты (src/ai/cover_points.gd,
                                                              # Balance.AI_POINTS; приём Road to Vostok): «низкое укрытие» и «угол» с направлением по физике
                                                              # и навигации → <nav_cache>/cover_points.json (запечены «Проспект», ТЦ, «Пригород»); после навигации — заново
tools/godot.cmd --headless res://tools/cover_points_test.tscn # точки укрытия: разметка на полигоне (ящик, конец стены, поле), «Проспект» — мародёр
                                                              # берёт точку, где его не видно с угрозы, с другой стороны угрозы — нет, занятую второй не берёт
tools/godot.cmd --headless res://tools/prospekt_raid_check.tscn # рейд «Проспекта»: навигация, население слоями, кордон ЧВК, точки на навигации,
                                                              # от каждого захода до всех выходов, места лута; приёмы EFT — выходы по стороне захода
                                                              # и «не каждый рейд», ворота паркинга (КТП / брелок), труба без рюкзака, решётка
                                                              # хранилища, сейфы под ключ, схроны, главарь банка
tools/godot.cmd --headless res://tools/prospekt_nav_reach.tscn # «Проспект»: достижимость мест второй очереди по навигации ИИ от (0; −15) — таблица «место — путь есть / нет — длина»
                                                              # (второй этаж «Яруса», мостки, крыша склада, вокзал, полиция, туалет, вышки, полотно эстакады, полосы под ней…); только печать, код 0
tools/godot.cmd --headless res://tools/prospekt_nav_stairs.tscn [-- detail=N,M map=N path=x,y,z:x,y,z area=x,y,z] # «Проспект»: навигация вдоль каждой лестницы плана (63 из prospekt_snapshot.json)
                                                              # и «ковры» StairNavigation: по лестнице — сетка у оси, путь от низа к верху; по ковру — путь между привязками его концов;
                                                              # map=N — вид сверху на площадки у концов лестницы N (физика + сетка), path= — путь между двумя точками, area= — вид сверху на 16 × 16 м
tools/godot.cmd --headless res://tools/prospekt_ai_stairs.tscn # «Проспект»: живой мародёр по лестницам — эскалатор «Яруса», полиция, сход эстакады, спуск в туалет, крыло вокзала:
                                                              # внизу шум (NoiseBus) наверху, за 60 с поднялся (y тела у цели) и обратно; PASS / FAIL по каждому направлению
tools/godot.cmd --headless res://tools/nav_stair_probe.tscn   # стенд навигации на лестнице: марш разной ширины и уклона (без ограждения, с поручнями, между стенами, с ковром StairNavigation) —
                                                              # какие сочетания держит сетка Balance.URBAN_WORLD (крутизна > atan(подъём / ячейка) ≈ 26,6° и узкие с поручнями рвут её)
tools/godot.cmd --headless res://tools/prospekt_ring_view.tscn # «Проспект»: обзор с полотна эстакады — из двух окон экрана и с верхов сходов веер лучей на восток (±60°, −35…+5°):
                                                              # доли длиннее 90 / 120 / 150 м, самый длинный луч, дальность видимой земли; только замер
tools/godot.cmd --headless res://tools/prospekt_pop_stats.tscn # «Проспект»: бойцов по слоям населения при 1 / 2 / 3 игроках, среднее по POP_TRIALS (20) настоящих расстановок;
                                                              # POP_LEVEL=res://… — другая сцена (до / после правки точек)
python -X utf8 tools/prospekt_s2_5b_loot.py cands <файл.json>  # «Проспект», этап 5б: места лута второй очереди (94 ящика, таблицы из data/loot.json) → кандидаты для
                                                              # LOOT_SNAP_IN=<файл> LOOT_SNAP_OUT=<файл> tools/godot.cmd --headless res://tools/prospekt_loot_snap.tscn (пол лучом, ящик не в коллизии,
                                                              # до навигации ≤ 1,6 м, иначе ближайшее свободное) → … apply <подогнанные.json> дописывает Loot_N в сцену и loot плана (один раз)
python -X utf8 tools/prospekt_loot_kinds.py [--apply | --fit]  # «Проспект», лут по виду контейнера (docs/design/loot_matrix_v2.md §5.1): каждому Loot_N — вид и таблица того же имени
                                                              # (weapon_crate, ammo_crate, toolbox, duffel, carton, safe …) по подписи места → data/blockouts/prospekt_loot_kinds.json
                                                              # (правится руками, повторный запуск берёт его; --rules — пересчитать); --apply — kind/table/model_id в узлы сцены и container в план;
                                                              # --fit — ещё поворот, пол и «не помещается» из prospekt_loot_fit.json (model_off — остаётся бокс; model_ok плана прячет маркер блокаута)
LOOT_FIT_OUT=data/blockouts/prospekt_loot_fit.json tools/godot.cmd --headless res://tools/prospekt_loot_fit.tscn # подгонка моделей контейнеров по физике карты: пол лучом, спинка к стене, габарит закрытой и открытой модели не в коллизии
python -X utf8 tools/gen_loot_containers.py                    # каталог моделей контейнеров data/loot_containers.json (габариты — из индексов: мебель общежития и assets/models/loot_containers/loot_containers_models.json — у модели из второго источника свои dir / index / lod в записи; вид без модели — model "", подключение правкой данных)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/loot_containers/medbag_game.py -- lp|bake|export
                                                              # медицинская сумка-укладка (принята 2026-11-13), игровая версия: lp — низкие сетки по деталям (≈ 7,95 тыс. треугольников на состояние,
                                                              # закрытая — смещением раскрытой, общая развёртка в один атлас 2K), bake — карты с high-poly раскрытой (≈ 17 мин на процессоре, Cycles:
                                                              # цвет, шероховатость, металл через излучение, касательная нормаль, AO), export — lc_medbag и lc_medbag_open (корпус одной сеткой, клапан —
                                                              # узел с осью, LOD1 ≈ ¼ — узлы *_lod1) → assets/models/loot_containers + loot_containers_models.json; затем --import,
                                                              # python -X utf8 tools/loot_containers/medbag_imports.py, --import, gen_loot_containers.py, prospekt_loot_fit + prospekt_loot_kinds.py --fit;
                                                              # сверка с high-poly — blender -b <RING_Loot_MedBag_finish_v03.blend> --python tools/loot_containers/medbag_game_compare.py -- [open closed top]
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/loot_containers/lc_game.py -- <lc_safe|lc_cell|lc_gun|lc_file|lc_cash|lc_aid|all> [lp] [bake] [export]
                                                              # игровые версии шести принятых контейнеров (общий код с медсумкой — lc_game_lib.py; развёртка — укладчик tools/asset_kit/uv.py, заполнение 74–80 %):
                                                              # lp — детали раскрытого состояния схлопыванием рёбер до бюджета (шкаф 5,6 / касса 7,6 / сейф и картотека 4,3–4,7 / ячейка 2,3 / аптечка 1,7 тыс.),
                                                              # закрытое — жёстким переносом деталей; bake — цвет, шероховатость, металл, AO переносом карт v03 с high, касательная нормаль, у кассы излучение цифр
                                                              # (от 5 до 25 мин на процессоре); export — <предмет> и <предмет>_open (подвижное — узлы с осью: hinge — ось и угол, slide — ось и ход), LOD1 ≈ ¼ → assets/models/loot_containers;
                                                              # затем --import, medbag_imports.py, --import, gen_loot_containers.py, prospekt_loot_fit + prospekt_loot_kinds.py --fit (настенные модели — "wall": true в каталоге:
                                                              # подгонка ищет стену и вешает на Balance.LOOT_WALL_HEIGHT; вид register — касса, места с таблицей register); кадры из игры — prospekt_raid_shots с PROSPEKT_CLEAN=1 и PROSPEKT_FILL=4 (лампа у камеры)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/loot_containers/build_counters.py -- <файл.blend> [preview <папка>] [check]
                                                              # опоры под кассу «Проспекта» (форма без текстур, в игру не внесены): прилавок торговый ПТ_ (ЛДСП 16 мм, 1500 × 600 × 900, ящик на телескопах)
                                                              # и кассовый бокс супермаркета КБ_ (транспортёр, сканер, накопитель, стол кассира, стойка с номером); у каждого socket_register — место кассы;
                                                              # детали — counters.py; для масштаба — касса партии 1 и фигура 1,75 м; check — габариты, пересечения, нормали, касса на опоре
tools/godot.cmd --headless res://tools/loot_stats.tscn         # замер лута по настоящему ItemDb.roll: по таблице — среднее, медиана, p90, пустые %; по «Проспекту» — ожидаемая стоимость Loot_N (схроны × 4/12),
                                                              # категории и штуки ключевых вещей за рейд (LOOT_STATS_N=3000, LOOT_STATS_OUT=<json>, LOOT_STATS_MAP=<узел → таблица> — расчёт до внесения в сцену);
                                                              # числа до / после — docs/design/data/loot_stats_{before,after}.{json,txt}
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/loot_kinds_perf.tscn # «Проспект»: кадры в секунду с моделями контейнеров и без них (склад «Яруса», вокзал, гаражи, паркинг −1, разгрузка)
tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_raid_shots.tscn # свет «Проспекта» в рейде глазами игрока (привыкание глаза,
                                                              # «объектив»): день, закат, ночь, пасмурно, дождь с трёх точек → user://prospekt_raid_shots
                                                              # (PROSPEKT_OUTPUT, PROSPEKT_CASES=day,night; PROSPEKT_CLEAN=1 — своей камерой, чистый свет сцены; PROSPEKT_OPEN=Loot_1,Loot_2 — эти контейнеры лута открыты)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/urban95_export.py -- [ID …]
                                                              # библиотека RING_Urban_95 (retopology_v01, 101 модель) в игру: assets/models/urban95/<ID>.gltf,
                                                              # карты WebP ≤ 2K, индекс с габаритами data/urban95_models.json; на карте их ставит MallFiller (filler.kit_models)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_kit.py -- <класс> <папка FBX> <игровой .blend>
                                                              # транспорт «Проспекта»: игровая сетка LOD0 тем же генератором (vq.py) и FBX для Painter (sedan…suv, bus12, paz, gazel)
bash tools/prospekt_vehicles/sp_family.sh <папка> <Имя> <класс> <семья> sp/stack_car.py color=r,g,b # отделка в Substance Painter (мост sp_bridge, Painter запущен):
                                                              # проект, запекание, стек vstacks.py, карты, варианты в Blender (apply_maps.py → <папка>/game/<Имя>_textured_v01.blend
                                                              # в E:/Models Blender/VEHICLES/Город_партия1); правка стека без запекания — sp_redo.sh
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_export.py -- [класс …]
                                                              # транспорт в игру: assets/models/prospekt_vehicles/PV_*.gltf, карты WebP ≤ 2K, записи PV_* и группы вперемешку
                                                              # в data/urban95_models.json; --import, python -X utf8 tools/prospekt_vehicles/game_imports.py, --import
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_lods.py -- [класс …]
                                                              # свои дальние LOD транспорта (после game_export.py): LOD1 ≈ ¼ треугольников, атлас 1K запечён с LOD0 +
                                                              # прозрачные окна, LOD2 — одна поверхность; «lods» у PV_* (легковые 25 / 60 м); --import, game_imports.py, --import
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_bus.py -- van|ambulance|bus12 <выход.blend> intact,open|intact,over
                                                              # партия 2 (формы): фургон и скорая на кузове ГАЗели, перевёрнутый автобус 12 м (over); такси и полиция —
                                                              # build_special.py -- taxi|police <выход.blend> (принятый седан + плафон / балка маячков) → E:/Models Blender/VEHICLES/Город_партия2
bash tools/prospekt_vehicles/batch2_finish.sh [taxi police van ambulance bus12_over] # партия 2, отделка: ливреи и маска мест ссадин в развёртку
                                                              # (livery.py: надписи DejaVu Sans Bold, наклейки Shrinkwrap'ом, EMIT) → семьи в Painter (sp_family.sh, BATCH=Город_партия2);
                                                              # игровая сетка до этого — game_kit.py -- <класс> _asset_src/prospekt_vehicles/<класс>/sp <машина>/game/<Имя>_lod0_v01.blend
bash tools/prospekt_vehicles/wheels_finish.sh [stack|open]     # колёса v2 на просмотр: колпак, штамповка, литой (vwheels.py), шина с протектором и надписями
                                                              # боковины (tire_marks.py, системный Python с PIL) — запекание в Painter, стек vstacks.wheel по вариантам
                                                              # отделки wheel_looks.py (цвет, глянец, износ) → карты <набор>_<вариант>_* → E:/Models Blender/VEHICLES/Колёса/
                                                              # game/Wheels_textured_v01.blend (stack — только стеки и карты, open — сначала открыть проект); Painter с мостом запущен
bash tools/prospekt_vehicles/wheels_cars.sh [класс …]          # колёса v2 на машины обеих партий: игровая сетка (game_kit.py — стиль и вариант колеса класса —
                                                              # wheel_looks.CAR_WHEELS), у партии 2 ливреи (livery.py), семьи в Painter с прежним цветом кузова и колесом
                                                              # («wheel=стиль:вариант»); SKIP_KIT=1 — сетка уже собрана; затем game_export.py, game_lods.py, импорт
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_vehicles_perf.tscn [-- off | lod | lodcmp] # кадры в секунду у транспорта «Проспекта»
                                                              # (паркинг −1, стоянки, поворот, сверху); off — пачки машин скрыты; lod — одна машина с 4…80 м → docs/screens/prospekt_vehicles/lod_*;
                                                              # lodcmp — LOD0 / LOD1 / LOD2 варианта рядом с 8…60 м → lodcmp_*
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/fire_truck/build.py -- <выход.blend>
                                                              # пожарная автоцистерна (по мотивам АЦ на КамАЗ-43253) в sand3d (_asset_src/sand3d, v1.6.3):
                                                              # high-poly форма, коллекции «Целая» / «Отсеки открыты»; размеры — tools/fire_truck/spec.py;
                                                              # проверка — audit.py -- <отчёт.json>, виды — shots.py -- <папка> [виды] [closed|open] (blender --background <файл>)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_plants/<этап>.py -- [вид …] [preview]
                                                              # растения «Проспекта» (берёза, липа, тополь, сирень, изгородь): build_forms (форма) → python -X utf8
                                                              # tools/prospekt_plants/textures.py (листья, гладкая кора) → build_pbr (UCUPaint) → game.py -- atlas|meshes|preview
                                                              # (атлас веточек, LOD0/LOD1/дальний) → python -X utf8 tools/prospekt_plants/godot_assets.py (WebP, материалы,
                                                              # индекс P_*) → --import; исходники — E:/Models Blender/ENVIRONMENT/RING_Prospekt_Plants
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_plants_perf.tscn [-- off] # кадры в секунду у растений «Проспекта»
                                                              # (сквер, берёзы, тополя, сверху); «off» — растения скрыты, сравнение в одной сборке
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/prospekt_light_perf.tscn [-- метка] # кадры в секунду «Проспекта» в точках света интерьеров
                                                              # (зал «Яруса», склад, зал вокзала, холл полиции, блокпост, башня схода) → user://prospekt_light_perf_<метка>.txt
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/zone01_trees/<этап>.py -- [maple negundo poplar] [preview]
                                                              # клёны и тополя зоны 1 (клён остролистный и ясенелистный, тополь берлинский; поздняя осень):
                                                              # forms (форма, -- maple poplar; check_forms.py — повторное открытие) → python -X utf8
                                                              # tools/zone01_trees/leaf_textures.py (осенние листья ambientCG LeafSet028/006/007) → pbr (UCUPaint) →
                                                              # export_game (атлас веточек, LOD0/LOD1/дальний → assets/zone01/trees) → python -X utf8
                                                              # tools/zone01_trees/godot_assets.py (WebP, материалы) → --import; исходники — E:/Models Blender/ENVIRONMENT/RING_Zone01_Trees
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/zone01_trees_perf.tscn [-- off] # клёны и тополя зоны 1: кадры в секунду и снимки
                                                              # (двор, ряд тополей, центр, с высоты, опушка, сверху) → docs/screens/zone01_trees/<метка>_*; off — скрыты;
                                                              # ZONE01_TREES_TAG — метка, ZONE01_TREES_ONLY=клён_вблизи,ясенелистный_вблизи,тополь_вблизи — крупные планы;
                                                              # ZONE01_QUALITY=low|medium|high — качество графики на время замера (в настройки игрока не пишется)
tools/mall_study.cmd                                          # прогулка по черновику территории ТЦ 1:1 (docs/design/mall_study.md): M — план, 1–9/0, N/B — участки, F — полёт;
                                                              # проверка: --headless res://tools/mall_study.tscn -- verify (подходы A–E, галерея, наполнение и открытые куски ≤ 60 м, рельеф, брод, мостики, ж/д ветка и переезд, паркинг, двор, пристройка приёмки); -- shots — снимки
                                                              # (MALL_STUDY_VIEW=имя:x:y:z:куда_x:куда_y:куда_z — свой кадр, несколько — через «;», MALL_STUDY_OUTPUT — папка)
tools/godot.cmd --headless res://tools/bake_mall_nav.tscn      # рейдовая карта ТЦ (scenes/levels/mall_map.tscn = черновик территории + заходы, выходы, мародёры, места заказа):
                                                              # перепечь кэш навигации data/navigation/mall_map после правки территории (~30 с; без кэша рейд печёт сам при загрузке)
tools/godot.cmd --headless res://tools/nav_seams_test.tscn      # швы тайлов навигации ТЦ, «Проспекта», зоны 1 (UrbanNavigation: связи по краю только у полос у швов):
                                                              # переходы через каждый шов, заходы → выходы, случайные пары — как у эталона (тайл целиком, связи у всех);
                                                              # время до готовности и пересинхронизации (с окном — то же); кэши свежие (bake_*_nav) [-- mall_map prospekt zone01_mall]
tools/godot.cmd --windowed --resolution 1600x900 --disable-vsync res://tools/mall_ground_perf.tscn # покрытия и бетон территории ТЦ (MallGround, шейдеры paved_ground, cast_concrete):
                                                              # кадры в секунду и время видеокарты против прежних серых на одних кадрах (MALL_GROUND_FALLBACK=1 — вид без текстур)
tools/godot.cmd --headless res://tools/car_mall_sites_shots.tscn # места заказа «Вернуть машину» на карте ТЦ: стоянка у доков, бокс скупки у АЗС, склад техники —
                                                              # F засчитан, путь по навигации от заходов; с окном (--windowed --resolution 1600x900) — снимки car_mall_*
python -X utf8 tools/gen_car_clue_textures.py                 # улики заказа на карте ТЦ → assets/textures/car_clues: пятно антифриза и следы шин по альфа-маскам
                                                              # владельца (Маски_АЛЬФА), номера, накладная, бирка «ЮР / 8»; затем --import
tools/godot.cmd --headless res://tools/sector_stats.tscn -- res://data/sectors/mall_map.json # сводка сборки сектора (стены, двери, огни):
                                                              # снять до и после правки SectorBuilder — старые уровни не должны меняться
tools/godot.cmd res://tools/quest_shots.tscn                  # снимки сюжета: разговор, места этапов, несёшь Антона
python tools/import_model.py <id>                              # модель из _asset_src/<id> (+license.txt) в assets/models/props, CREDITS
tools/godot.cmd res://tools/ui_shots.tscn                    # снимки: карта (M), меню (Esc), управление, рюкзак и лут
tools/godot.cmd --disable-vsync res://tools/perf_test.tscn   # FPS / вызовы отрисовки в изометрии и в прицеле по точкам
tools/godot.cmd res://tools/raid_test.tscn                   # цикл рейда: рубильник, ключи, запертая дверь, эвакуация, итог
tools/godot.cmd res://tools/loadout_test.tscn                # убежище → рейд со снаряжением → эвакуация → убежище (тестовый профиль)
tools/godot.cmd --headless res://tools/arsenal_test.tscn     # арсенал, CASE 1–20 ТЗ: прицелы (FPS/изометрия), фонарь+ЛЦУ, пробитие, плиты, ИИ-патроны, снятие с трупа, сохранение
tools/godot.cmd --headless res://tools/compile_check.tscn    # все скрипты собираются (с автозагрузками) — после больших правок
tools/godot.cmd --windowed --resolution 1280x720 res://tools/raid_map_bake.tscn [-- id …] # карты маршрутов для окна «План рейда»: каждая рейдовая сцена
                                                              # (data/floors.json) сверху ортокамерой днём → assets/maps/<id>.webp, выходы (условия) и заходы с края
                                                              # → data/raid_maps.json; затем --import (после правки уровня — снять заново)
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/region_map_shots.tscn # схема района в «Плане рейда» (RegionMapView): убежище, участки, пути
                                                              # от убежища, кордон; раскладка (принята владельцем) — data/region_map.json → docs/screens/region_map_<маршрут>.png
tools/godot.cmd res://tools/hideout_shots.tscn               # снимки убежища и его окон в docs/screens/hideout_*.png
                                                              # (HIDEOUT_ONLY=exit — план рейда: схема района, клик по участку — его план)
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
                                                              # в том числе обойма из окна рюкзака: вынуть, вставить, сменить — предметы у хоста, движение рига у наблюдателя
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/asset_kit/uv_check.py -- [veras|mosin|pm] [атлас] [вариант]
                                                              # общий модуль игровой развёртки оружия (tools/asset_kit/uv.py, укладка uv_pack.py) на копиях готовых сеток:
                                                              # заполнение, плотность видимого / у глаза / вдали, отступы проверены растром; слои KitUV* —
                                                              # в _asset_src/<ствол>/uv_kit/*_UVKit.blend, игровые файлы и карты не меняются
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/asset_kit/normal_probe.py -- <папка>
                                                              # стенд нормалей: пять пар high/low запекаются как у оружия (Cycles, 8 бит), low в glTF с тангентами
                                                              # и без, снимки Eevee; затем NORMAL_PROBE_DIR=<папка> tools/godot.cmd --windowed --resolution 512x512
                                                              # res://tools/normal_probe.tscn (тангенты файла / свои, сжатие карты S3TC / RGTC / BPTC, бинормаль в пикселе)
                                                              # и python -X utf8 tools/asset_kit/normal_probe_report.py <папка> — ошибка против high; выводы — навык godot-asset-preparation
python -X utf8 tools/asset_kit/roughness_imports.py [--fix]   # фильтр шероховатости в .import карт: roughness/mode за перечнем (8 пишет редактор Godot 4.7.2 —
                                                              # фильтр молчит), фильтр без карты нормалей или mip-уровней; --fix — канал по имени карты (ORM — 3), затем --import
"D:/ПРОГРАММЫ/RizomUV 2024.1/rizomuv.exe"                      # RizomUV (владелец, 2026-10-27): развёртка и упаковка UV — для норм заполнения 80 % (кузова машин,
                                                              # новые стволы); управляется скриптами — Lua из командной строки или Python через RizomUVLink
                                                              # (папка программы); в конвейер ещё не подключён
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
                                                              # VERAS_PART=eject — «вынуть магазин» из окна рюкзака (veras_eject_*); VERAS_POS=spawn | x,y,z и VERAS_YAW=град —
                                                              # точка съёмки: точка по умолчанию (100; 0,1; −5) после переделки карты ТЦ стоит у стены, оружие там убрано
bash tools/veras54_v13/clips/build_fire_modes.sh              # переводчик огня большим пальцем правой руки (clips/fire_mode_clip.py): АВ→2, 2→ОД, ОД→АВ без рукоятки и под ВАРН V1/V2
                                                              # → «Клипы v13/VERAS54_FireMode_*_v13.blend»; затем export_veras54.py -- viewmodel grips, --import, veras_shots VERAS_PART=firemode
tools/godot.cmd --headless res://tools/veras_hand_test.tscn # ВЕРАС-54, левая рука с рукоятками (ВАРН V1 и V2, на удлинителе): стоя, на ходу, в прицел и обратно — кости не копят масштаб, кисть у рукоятки
tools/godot.cmd res://tools/veras_gloss_shots.tscn          # ВЕРАС-54 под лампами тира: блики отделки v13 и жировых следов; снимки veras_gloss_*
                                                              # (GLOSS_MAG=mag_545_45|mag_545_60 — магазин 45/60, GLOSS_CHECK=1 — магазин у глаз, держать R)
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/veras_outdoor_shots.tscn # ВЕРАС-54 днём под небом (Пригород): бедро, магазин у глаз, прицел — на солнце
                                                              # и от солнца; глянец материалов виден только тут; снимки veras_outdoor_* (VERAS_OUT_TAG=имя; VERAS_OUT_MAG=mag_545_45|mag_545_60 — с магазином 45/60)
# ВСС-М v8 в игру (blender … --background --factory-startup --python-exit-code 1 --python): tools/vss_m_v8/game_lp.py (сетка ~37 тыс. в руках,
#   магазины на 10/20/30 в стороне; подвижные детали — свои узлы по моверам исходника) → game_bake.py -- [атлас …] [--channels color,rough,metal,normal,ao] → python -X utf8 tools/vss_m_v8/game_pack.py
#   → game_export.py (assets/models/weapons/vss_m: vss_m.gltf, vss_mag10/20/30.gltf) → game_optics.py -- [pso] [s432] (ПСО и 4×32 →
#   assets/models/attachments/pso_vss, scope_4x32; их сетки окуляра — python -X utf8 tools/vss_m_v8/reticles.py) → --import →
#   python -X utf8 tools/vss_m_v8/game_imports.py → --import
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/vss_shots.tscn # ВСС-М в руках днём (Пригород): механический, ПСО, 4×32 с фонарём и рукояткой на планках муфты —
                                                              # от бедра, в прицел, на отдаче (_ads_recoil; наглазник ПСО — виден ли), с подсветкой сетки (_ads_lit), модель сбоку;
                                                              # механический — выстрел от бедра (_hip_fire: ход рамы и затвора в лог) и рама отведена (_side_r_bolt_open);
                                                              # снимки vss_* (VSS_ONLY=iron,pso,rail; VSS_POS=x,y,z)
                                                              # один кадр 4K: VSS_HERO=1 VSS_ONLY=iron VSS_RES=3840x2160 VSS_TIME=dusk VSS_OUT=<папка> (VSS_LOOK=курс,наклон;…)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<папка сдачи>/ВСС-М_v8_студия.blend" --python tools/vss_m_v8/render_hq.py -- studio <png>
                                                              # рендеры 4K для владельца: в воздухе (своя студия) и на столе (ВСС-М_v8_на_столе.blend -- table <png>)
tools/vss_m_v8/painter_open.cmd [receiver|parts]                 # ВСС-М: Painter для ручного износа (OCIO проектов + мост; путь проекта — полный)
bash tools/vss_m_v8/painter_to_game.sh [набор …] [--scenes] [--shots] # карты, выгруженные владельцем из Painter → запекание, экспорт, импорт;
                                                              # инструкция — docs/assets/vss_m_painter_manual_wear.md; наборы с «РУКАМИ» скриптом не пересобираются
                                                              # основа материалов без пересборки (сохраняет «РУКАМИ») — задание моста tools/vss_m_v8/sp_base_values.py (BASE_SETS = [...])
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/ar15/build.py -- <out.blend> [стадии]
                                                              # AR-15 «ГРАНЬ-15» (геометрия high-poly со всей механикой): части tools/ar15/part_*.py, управление —
                                                              # пустышка AR15_Controls (part_rig.py); затем blender -b <out.blend> --python tools/ar15/delivery.py -- <выдача.blend>;
                                                              # глушитель отдельным файлом (в игре покупной): --python tools/ar15/delivery_suppressor.py -- <глушитель.blend>;
                                                              # проверки: --python tools/ar15/check_overlaps.py [-- состояния] (пересечения в положениях), tools/ar15/shots.py (снимки)
                                                              # снимки как в Material Preview (Eevee, HDRI forest.exr): --python tools/ar15/render_preview.py -- <папка> [вид,…] [ширина]
python -X utf8 tools/ar15/trace_ch_wing.py <снимок> [наложение.png]   # AR-15: обводка крыла рукоятки заряжания по снимку владельца → tools/ar15/ch_wing_trace.json (его берёт part_bolt)
# AR-15, текстуры этап 1 (blender … --background --factory-startup --python-exit-code 1 --python): tools/ar15/tex_uv_blender.py -- <AR15_uv_v03.blend>
#   на AR-15_геометрия_v08.blend (развёртка 13 наборов tools/ar15/tex_sets.py: Smart UV + Minimum Stretch + укладка asset_kit/uv.py; RizomUV 2024.1 на этой
#   сетке не справился — tools/ar15/rz_unwrap.py, rizomuv.exe -cfi) → на AR15_uv_v03.blend: tex_marks.py -- preview <папка>|bake|seams (надписи, знак, швы литья →
#   маски в развёртку), sp_export.py -- <AR15_sp.fbx> → Painter: python -X utf8 tools/ar15/sp_run.py start; -c "sp_ar15.create|bake([набор])|save|build|export_variant(...)"
#   (запекать по одному набору и сохранять после каждого — общий прогон пропадает при сбое)
#   (стек tools/ar15/sp_ar15.py, варианты основы А/Б/В) → tex_apply.py -- apply <A|B|C> <карты> <out.blend> <нормали> (студия в файле) | shots <папка> [samples]
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <AR-15_…blend> --python tools/ar15/long_rail.py -- <out.blend> [задний_паз 100] [передний_паз 220]
                                                              # AR-15: длинная нижняя планка из кусков штатной короткой вместе с её развёрткой — без
                                                              # пересборки и перезапекания; коллекции «Нижняя планка — длинная / короткая (штатная)»
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/ar15/sharp_edges.py -- [--angle 35] [--json <отчёт.json>] [--show <out.blend>]
                                                              # AR-15: острые рёбра (угол граней больше 35° или скругление меньше R 0,35 мм) — число и длина
                                                              # по деталям, горячие места клетками 6 мм в JSON; --show — копия файла с коллекцией «Острые рёбра»
                                                              # (выпуклые красным, вогнутые синим)
# AR-15, этап 2 — износ: blender -b <AR15_uv_v03.blend> --python-expr "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/ar15')"
#   --python tools/ar15/wear_zones.py -- <папка> [2048] [4096] (зоны хвата, рёбрышки и углы у них в развёртку) → python -X utf8 tools/ar15/wear_masks.py (фото-маски CC0
#   из Маски_АЛЬФА/50_Скачанные_CC0_… — уровни, порог) → Painter: tools/ar15/sp_run.py -c "import sp_ar15_wear; print(sp_ar15_wear.build_grip())"
#   (группа «Этап 2 — износ», Passthrough), export_variant('B', <папка>, ['grip'])
#   Остальные детали — места попиксельно: blender -b <AR15_uv_v03.blend> --python tools/ar15/wear_maps.py -- <набор> <папка> (положение,
#   нормаль, номер детали в каждом пикселе развёртки → <набор>_maps.npz) → python -X utf8 tools/ar15/wear_lower.py (нижний ресивер и УСМ:
#   зоны <набор>_zone_*_L.png, просмотр lower_zones_preview.png) → sp_ar15_wear.build_lower(), export_variant('B', <папка>, ['lower', 'internals'])
#   Магазин: wear_maps.py -- magazine → python -X utf8 tools/ar15/wear_magazine.py (штрихи strokes() — по якобиану карты положения) →
#   sp_ar15_wear.build_magazine(), export_variant('B', <папка>, ['magazine'])
tools/ar15/mark_server.cmd                                   # AR-15, разметка мест износа владельцем: http://localhost:8766/ — кистью место, тип и сила
                                                              # из списка, «Сохранить» → «Разметка_износа/marks» в папке модели. Виды: blender -b <файл просмотра>
                                                              # --python tools/ar15/mark_views.py -- <Разметка_износа> [вид,…] [сэмплы] (рендер + карта точек);
                                                              # перенос: python -X utf8 tools/ar15/mark_apply.py → sp_ar15_wear.build_marks() (группа
                                                              # «Этап 2 — метки владельца», вид — по материалу под меткой) → export_variant('B', <папка>, [наборы])
#   Остальные детали (верхний, затвор, цевьё, ствол, приклад, трубка, прицелы, патроны): python -X utf8 tools/ar15/wear_parts.py [набор …]
#   (кромки — по выпуклости в пространстве и месту, рисунок — фото-маски CC0 трипланарно, маски по виду: слой на вид) →
#   sp_ar15_wear.build_part(<набор>) → export_variant('B', <папка>, [наборы]) — выгружать по 2–4 набора (видеопамять)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y <AR-15_износ_этап2_v1.blend> --python tools/ar15/render_table.py -- <папка кадров> <сцена.blend> <сцена_разряжание.blend> [ширина высота сэмплы] [кадры]
                                                              # AR-15, рендеры для владельца: две винтовки на полевом столе в палатке (разобранная — физикой
                                                              # жёстких тел), 26 кадров: 5 общих, 11 собранной, 4 — разряжание, 6 средних планов; окружение — tools/ar15/tent_scene.py;
                                                              # на раскладушке — tools/ar15/render_tent.py -- <out.blend> <out.png> [ширина высота сэмплы] [вид]
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/build.py
                                                              # цевьё по ролику Dolinskyi (эксперимент 2026-11-01, docs/assets/handguard_dolinskyi_plan.md): high- и low-poly
                                                              # → «Цевьё_Dolinskyi_форма_v01.blend»; затем на нём uv.py (развёртка 2K, FBX для Painter), на развёртке mesh_dump.py,
                                                              # python -X utf8 tools/handguard_dolinskyi/masks.py (маски вместо мазков кистью: надписи, места касаний, износ планок);
                                                              # Painter — python -X utf8 tools/handguard_dolinskyi/sp_run.py start, -c "sp_handguard.create()" / "…bake()" /
                                                              # "import sp_stack; sp_stack.build()" / "sp_handguard.export(<папка>)" (без неявных слоёв Vulkan: с RivaTuner падал);
                                                              # нормаль сетки — в Blender: на развёртке tools/handguard_dolinskyi/bake_normal.py, затем в Painter
                                                              # "sp_handguard.use_blender_normal()" после bake() (его карта из FBX рябит вокруг окон в Blender / Godot);
                                                              # просмотр и сравнение с кадрами — review.py; открыть проект руками — tools/handguard_dolinskyi/painter_open.cmd
# ГРАНЬ-15 (AR-15) в игру (blender … --python): tools/ar15/game_lp.py (сетка ~40 тыс. из AR-15_износ_этап2_v1.blend: подвижные детали — свои узлы
#   по моверам, рукоять — вокселями; развёртка asset_kit, планки Picatinny с пазами) → game_bake.py -- [атлас …] [--cpu] (с high-poly, каждая
#   деталь — со своих) → python -X utf8 tools/ar15/game_pack.py → game_export.py (assets/models/weapons/ar15: ar15.gltf, ar15_mag30.gltf,
#   отчёт ar15.json) → python -X utf8 tools/ar15/game_data.py (models.ar15 — сокеты планок по пазам, откидные прицельные, ход рамы и шторка;
#   wpn_ar_09, mag_556_30_gran, хват) → --import → python -X utf8 tools/ar15/game_imports.py → --import; иконки — icon_bake -- wpn_ar_09 mag_556_30_gran
#   Глушитель ГРАНЬ (обвес muzzle_supp_gran_01, крепление QD_GRAN15 — только у ГРАНЬ-15): blender … --python tools/ar15/supp_game.py -- lp
#   (сетка ~2,6 тыс. с той же high-poly, атлас 2K) → supp_game.py -- bake [--cpu] → python -X utf8 tools/ar15/supp_pack.py → supp_game.py -- export
#   → assets/models/attachments/supp_gran; --import, game_imports.py, --import; данные — game_data.py; иконка — icon_bake -- muzzle_supp_gran_01
tools/godot.cmd --headless res://tools/ar15_check.tscn         # ГРАНЬ-15 в движке: узлы и метки, треугольники, карты, габарит, ход рамы и шторка, сокет у каждого
                                                              # крепления, планки длиннее зажима, обвесы встают, с прицелом сверху целик и мушка сложены (90°);
                                                              # глушитель ГРАНЬ: встаёт только на ГРАНЬ-15, торец на тормозе, срез выстрела на переднем торце;
                                                              # на короткие боковые планки встаёт любой боковой обвес (длиннее планки — посередине)
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/ar15_shots.tscn # ГРАНЬ-15 в руках (Пригород): механический, коллиматор + фонарь + рукоятка,
                                                              # фонарь слева / справа — от бедра, в прицел, на отдаче, сбоку; выстрел (ход рамы в лог), рама отведена
                                                              # и шторка откинута; снимки ar15_* (AR15_ONLY=iron,optic; supp, supprail — с глушителем ГРАНЬ; sides — ЛЦУ и блок на боковых);
                                                              # без окна — только лог отвода ствола
tools/godot.cmd --headless res://tools/dust_cover_test.tscn    # шторка ГРАНЬ-15: у нового ствола закрыта; выстрел, перезарядка с пустым магазином, задержка —
                                                              # откинута и такой остаётся (перезарядка, убрал-достал), в руках — до упора с отскоком, хосту в запись ствола
# ИЗЛОМ-45 (wpn_smg_03) в игру: "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python
#   tools/smg03/game_export.py [-- <папка карт Painter>] (игровая сетка SMG03_Game_LP.blend + карты износа «Текстуры_этап2_v3» →
#   assets/models/weapons/smg03: smg03.gltf — подвижные детали своими узлами, заглушка резьбы MuzzleDevice, Magazine; магазины
#   smg03_mag13/30.gltf; отчёт smg03.json) → python -X utf8 tools/smg03/game_data.py (models.smg03: планки, ход затвора,
#   затворная задержка hold_open, флажки переводчика levers, спуск trigger; wpn_smg_03, магазины, хват smg03) → --import →
#   python -X utf8 tools/smg03/game_imports.py → --import; иконки — icon_bake -- wpn_smg_03 mag_45_vector13 mag_45_vector30
tools/godot.cmd --headless res://tools/smg03_check.tscn       # ИЗЛОМ-45 в движке: узлы, метки, бюджет, карты, затвор с задержкой, флажки
                                                              # и спуск, обвесы на планках, прицельные складываются, глушитель .45 прячет
                                                              # заглушку резьбы, магазин на 30 — из файла, темп и режимы огня
tools/godot.cmd --windowed --resolution 1600x900 res://tools/smg03_shots.tscn # ИЗЛОМ-45 в руках (Пригород): от бедра, очередь, магазин
                                                              # пуст — затвор на задержке, перезарядка, флажки по режимам (лог), в прицеле,
                                                              # сбоку; снимки smg03_* (SMG03_ONLY=iron,rail; SMG03_OUT — папка)
# ПЗРК «Осока» (wpn_mp_01) в игру: "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python
#   tools/osoka/game_export.py [-- <папка карт>] (игровая сетка work/osoka_game_uv_v01.blend + карты износа «Осока_износ_этап2_v1_карты»
#   → assets/models/weapons/osoka: osoka.gltf — подвижное своими узлами, крышки, нос ракеты, лампа индикатора; osoka_missile.gltf — ракета
#   с рулями и стабилизаторами на шарнирах; отчёт osoka.json; линия прицела — по +Z модели, труба выше неё на 6,6°) → --import →
#   python -X utf8 tools/osoka/game_imports.py → --import; данные — python -X utf8 tools/osoka/game_data.py (calibers.zr36, ammo.msl_zr36,
#   models.osoka, weapons.wpn_mp_01, хват osoka); у Михалыча — каталог 5 (tools/gen_trader_catalogs.py)
# Тепловизор ПН-36Т «ПОЛЫНЬ» (optic_polyn_01, по мотивам 1ПН97) в игру: "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup
#   --python-exit-code 1 --python tools/osoka/sight_export.py [-- <папка карт>] (игровая сетка Тепловизор/work/thermal_game_uv_v01.blend +
#   карты «Тепловизор_износ_этап2_v1_карты» → assets/models/attachments/polyn: polyn.gltf — Body, наглазник BodyEyecup, рычажок
#   BodyLever и крышка объектива BodyCap своими узлами с осями, Body_LOD1; отчёт polyn.json — в осях «Осоки», начало — точка
#   крепления) → --import → python -X utf8 tools/osoka/game_imports.py → --import; данные — тот же tools/osoka/game_data.py
#   (attachments.optic_polyn_01, сокет optic_primary «Осоки» — интерфейс OSOKA_PN, fold_sights); экран окуляра — CameraRig
#   (_update_display), тепловой канал — src/combat/ThermalView, знаки — OsokaHud, числа — Balance.THERMAL_SIGHT
tools/osoka_range.cmd                                         # стенд «Осоки» на карте «Плотина» (мир tools/heli_study.tscn, как у dam_play):
                                                              # по маршруту задания летает учебный вертолёт (HeliTarget, процедурный звук винтов),
                                                              # игрок во дворе лесопилки; ПКМ — головка ищет, держать цель в кольце мушки — захват
                                                              # (ровный писк, зелёная метка), ЛКМ — пуск, R — новая труба;
                                                              # --headless res://tools/osoka_range.tscn -- check — захват, пуск, попадание, падение,
                                                              # без захвата пуска нет, сбить осветительную ракету; -- shots (с окном) — снимки osoka_*
                                                              # на «Осоке» — тепловизор «ПОЛЫНЬ» (-- bare — без него): в окуляре кольцо головки,
                                                              # рамка захвата и дальность, X — канал «ДЕНЬ / ТЕПЛО»; check ещё — прицел на модели,
                                                              # прицельные сложены, тёплый вертолёт только в тепловом канале; OSOKA_TAG — приставка снимков
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/render_street.py -- <папка> [кадр,…] [ширина высота выборки] [сцена.blend]
                                                              # ИЗЛОМ-45, рендеры на улице: в статике, затвор на задержке, приклад сложен,
                                                              # очередь (вспышка, гильзы), на асфальте; позы — tools/smg03/render_poses.py
# Мосин 1891/30 ПУ (wpn_sr_03) в игру (blender … --background --factory-startup --python-exit-code 1 --python): tools/mosin_pu/game_retopo.py
#   (ретопология той же сборкой формы build_*.py: лишние петли сняты, клейма и фаски — в запекание → _asset_src/mosin_pu_game/lr)
#   → game_lp.py -- fp (лучи видимости; развёртка game_uv.py: швы до дисков, ложа и длинное — отрезками, ABF, укладка asset_kit) → game_bake.py --
#   rifle|mount|scope|ammo|ao → game_pack.py → game_export.py (винтовка с основанием кронштейна; прицел ПУ на кронштейне — съёмный
#   обвес optic_pu_01: assets/models/attachments/pu_mosin, карты — общий атлас винтовки) → --import → python -X utf8 tools/mosin_pu/game_imports.py → --import;
#   сетка ПУ — python -X utf8 tools/mosin_pu/reticle.py; данные — python -X utf8 tools/mosin_pu/game_data.py; переразвернуть
#   готовую сетку без пересборки — game_uv.py -- [атлас …]; файл просмотра для владельца — game_view.py
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/mosin_hands_shots.tscn # Мосин в руках (Пригород): от бедра, цикл затвора после выстрела
                                                              # (рукоять вверх, отвод, правая кисть на шаре), в прицел ПУ, перезарядка с открытым затвором,
                                                              # сбоку, мировая модель (LOD1), ПУ предметом, без ПУ — открытые прицельные;
                                                              # снимки mosin_hands_* (MOSIN_ONLY=hip,fire,ads,item,iron)
tools/godot.cmd --windowed --resolution 1100x760 res://tools/mosin_pu_shots.tscn  # Мосин — сама модель в студии: ракурсы, затвор открыт, LOD; снимки mosin_pu_*
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/smg03/build.py -- <out.blend>
                                                              # ПП по мотивам KRISS Vector Gen II (wpn_smg_03), high-poly, форма ждёт приёмки: контуры со снимков KRISS
                                                              # (python -X utf8 tools/smg03/trace_photos.py <снимки> <trace> → profiles.py <trace> → tools/smg03/data/profiles.json;
                                                              # приклад — trace_stock.py), детали part_*.py, подвижное — пустышка SMG03_Controls; выдача — -b <out.blend>
                                                              # --python tools/smg03/delivery.py -- <файл>; проверки -b <файл> --python tools/smg03/check_overlaps.py (16 положений)
                                                              # | measure.py (габариты против заводских) | shots.py -- <папка> [виды] (наложение на снимки KRISS, крупные планы)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/prepare_veras_attachments.py -- geometry|bake|export|imports <varn_v1|varn_v2|supp_veras> [100]
                                                              # рукоятки ВАРН и глушитель из библиотеки → assets/models/attachments/<id> (сетка + LOD, карты 100)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_mag_loader.py # ускоритель снаряжения магазинов: модель, превью mag_loader_preview.png; затем --import и icon_bake -- mag_loader
python -X utf8 tools/asten919/build.py <папка полей> [деталь …] [--k 2]   # АСТЕН-919 (по мотивам Glock 17 Gen4 MOS), high-poly неявными
                                                              # поверхностями: поля расстояний деталей (numpy, sdf.py; --k 2 — черновик), 90 с; затем
                                                              # blender --background --factory-startup --python tools/asten919/assemble.py -- <папка полей> <out.blend>
                                                              # (сетка OpenVDB, нормали из поля, пустышка ASTEN919_Controls с ползунками поз); виды — blender -b <out.blend>
                                                              # --python tools/asten919/shots.py -- <папка> [виды] [--pose slide_back,mag_out,trigger,catch,lock];
                                                              # пересечения деталей в позах — python -X utf8 tools/asten919/check_overlaps.py <папка полей>;
                                                              # контур рамки со снимка — trace_photo.py, наложение вида на снимок — compare.py; выдача и описание —
                                                              # E:/Models Blender/WEAPONS/АСТЕН-919 (asset-state.md)
# АСТЕН-919, текстуры этап 1: blender --background <АСТЕН-919_геометрия_v03.blend> --factory-startup --python-exit-code 1 --python
#   tools/asten919/tex_uv.py [-- out.blend набор,набор] (развёртка high-poly по наборам tex_sets.py: Smart UV → Minimum Stretch →
#   укладка asset_kit.uv; ~20 мин; картинка раскладки — python -X utf8 tools/asten919/tex_uv_view.py <набор>_tris.npz <png>) → на файле
#   развёртки: tex_geo_dump.py -- <папка geo> Magazine_Body Rear_Sight Front_Sight → python -X utf8 tools/asten919/tex_marks.py (маски в
#   развёртку: белая обводка целика и точка мушки, цифры окошек магазина) → sp_export.py -- <ASTEN919_sp.fbx> → Painter:
#   python -X utf8 tools/asten919/sp_run.py start; -c "print(sp_asten.create())" / "…bake()" / "…stack()" / "…export(<папка>)" (метки
#   _project_ready / _bake_done / _stack_done / _export_done.txt — sp_run.py wait <метка>; отделки — finish-spec.json в папке модели,
#   слот без выбора строится по кандидату) → tex_review.py -- apply <карты> <файл просмотра.blend> | shots <папка> [samples];
#   рендеры при уличном пасмурном свете — blender -b <файл просмотра.blend> --factory-startup --python tools/asten919/render_street.py
#   -- <папка> [кадр,кадр] [ширина высота выборки] (стороны, 3/4, затвор закрыт / открыт, рукоять, магазин, кадры «на блик»;
#   файл не сохраняется)
# АСТЕН-919, этап 2 — износ: blender -b <АСТЕН-919_развёртка_v02.blend> --factory-startup --python tools/asten919/wear_maps.py --
#   all <_asset_src/asten919/tex/wear_maps> (положение, нормаль, деталь в каждом пикселе развёртки) → python -X utf8
#   tools/asten919/wear_marks.py [набор …] (места следов в мм + штампы фото-масок владельца E:/Models Blender/Маски_АЛЬФА:
#   жир, полировка, затёртости, царапины → tex/wear/<набор>_<вид>.png) → Painter: sp_run.py -c "print(sp_asten_wear.build())"
#   (группа «Этап 2 — износ», метка _wear_done.txt; show(False) — выключить для сравнения) → sp_asten.export → tex_review.py
# АСТЕН-919 (wpn_hg_02 — встал на место прежнего Glock, 2026-11-12) в игру: ASTEN919_PLAIN=1 python -X utf8 tools/asten919/build.py
#   _asset_src/asten919/plain Frame Slide Front_Sight Serial_Plate --k 1.6 (те же детали без мелкого рельефа — исходник упрощения) →
#   blender … --background --factory-startup --python-exit-code 1 --python tools/asten919/game_lp.py (сетка ~29 тыс.: подвижное своими
#   узлами, 17 патронов, развёртка asset_kit; _asset_src/asten919/game/lp) → game_bake.py [-- атлас …] [--cpu] (с high-poly износа v02) →
#   python -X utf8 tools/asten919/game_pack.py → game_export.py (assets/models/weapons/asten919: asten919.gltf с веткой ASTEN919_LOD1,
#   asten919_mag.gltf, отчёт asten919.json) → --import → python -X utf8 tools/asten919/game_imports.py → --import; данные —
#   python -X utf8 tools/asten919/game_data.py (название, модель, ход механики; id, характеристики и хваты прежние); иконки —
#   icon_bake -- wpn_hg_02 mag_919_17
# АСТЕН-919, клипы рук от первого лица (ключевые кадры; хваты правит владелец): python -X utf8 tools/asten919/clips/hand_sdf.py
#   (поля расстояний пистолета 0,4 мм: static / slide / mag / trigger / whole → _asset_src/asten919/anim/sdf — ими меряется
#   касание перчатки) → blender -b --factory-startup --python tools/asten919/clips/rig.py (мастер рук v14 + игровая сетка на
#   костях ASTEN919_WeaponRig) → blender -b <ASTEN919_Rig_v01.blend> --python tools/asten919/clips/poses.py -- <позы.blend>
#   (черновые позы-хваты действием ASTEN919_Poses: кадры 1…61) → blender -b <позы.blend> --python
#   tools/asten919/clips/build_clips.py -- <E:/Models Blender/WEAPONS/АСТЕН-919/АСТЕН-919_руки_клипы_v01.blend> (клипы
#   действиями ASTEN919_<Клип> и подряд на дорожке NLA; движение — таблицы в скрипте, пальцы и места кистей — из поз);
#   это генератор черновиков: дальше клипы владелец правит в Blender сам — панель «АСТЕН» внутри файла (clip_tools.py:
#   открыть позы / клип, «Хваты из поз → во все клипы» — перенос поз без потери ручных ключей); rebuild.cmd на файле
#   с клипами делает то же, что эта кнопка, заново из таблиц (сотрёт ручные правки клипов) — regenerate.cmd;
#   кадры для своей проверки — stills.py (кадр клипа: «Reload_Full:25», позы: «poses:41»)
# Пулемёт «Частокол» (по мотивам ПКП «Печенег»; встаёт на место заглушки ПКМ — слот wpn_lmg_01), high-poly неявными поверхностями — форма v03 принята 2026-11-14, дальше текстуры:
#   bash tools/pkp/go.sh <k> "<модули>" "<виды>" — поля расстояний деталей (python: sdf.py, part_*.py, build.py; k = 2 —
#   черновик, 1 — рабочий шаг; PKP_JOBS — работники, PKP_ADAPT=0.4 — чистовая сетка, PKP_TAG — своя папка) → сборка сцены
#   (blender: assemble.py, OpenVDB) → кадры (shots.py; ref13 / ref14 — камерами боковых рендеров владельца, --pose — позы
#   рига) → наложение на образцы (compare.py) → E:/Models Blender/WEAPONS/Печенег — модель/work/pkp_k<k>.blend.
#   Риг — ползунки пустышки PKP_Controls (part_rig.py: крышка, её защёлка, лоток, рукоятка, рама, щитки, спуск, предохранитель,
#   плечевой упор, сошки, прицел, коробка). Проверки на собранном файле: blender -b <файл> --python
#   tools/pkp/check_overlaps.py -- [--depth 0.25] (пересечения во всех позах), tools/pkp/measure.py -- [отчёт.json]
#   (габариты против заводских, открытые рёбра). Миллиметры с рендеров-образцов — refmap.py и ref_tiles.py (--mm --y
#   <глубина>), подбор камеры образца — fit_cam.py. Памятка исполнителю отдельного модуля — tools/pkp/HELPERS.md;
#   размеры — dims.py; состояние и вопросы владельцу — asset-state.md в папке модели. Места под кронштейны (опоры
#   на крышке, втулки в корпусе газовой трубки) и съёмные кронштейны с планками Picatinny — part_mounts.py
#   (две коллекции «Кронштейн — …», выключены по умолчанию: планка на крышку под прицел, цевьё с нижней и боковыми
#   планками; их пересечения проверять с --show «имена коллекций»)
python tools/trace_flare_gun_claude.py                        # ракетница Claude: контуры с фото владельца → _asset_src/flare_gun_claude/trace (ещё аргумент overlay — сверка рендера с фото)
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_flare_gun_claude.py [-- render] # ракетница Claude и два патрона → assets/models/weapons/flare_gun_claude; render — превью в _asset_src/flare_gun_claude/Просмотр
python tools/flare_gun_claude_wear_masks.py                    # ракетница Claude: собственные маски износа → _asset_src/flare_gun_claude/textures/worn_v01
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/texture_flare_gun_claude.py -- build|render|inspect # ракетница Claude: слои UCUPaint на принятой геометрии, превью, проверка стека
python tools/import_weapon_model.py pm_highpoly_v5          # проверенный ПМ из _asset_src: дерево, PBR, размеры, бюджеты, CREDITS
tools/godot.cmd --headless res://tools/glock_test.tscn        # АСТЕН-919 (wpn_hg_02): детали без курка/флажка/глушителя, LOD, патроны 17+1, дуло с обвесом, гайка резьбы прячется под глушителем
tools/godot.cmd --windowed --resolution 1280x720 res://tools/glock_shots.tscn # АСТЕН-919 (wpn_hg_02): хват, ADS, перезарядка, третье лицо в docs/screens/glock_*.png
tools/godot.cmd --windowed --resolution 1920x1080 res://tools/icon_detail_shots.tscn # подробные значки (Balance.ICON_DETAIL — пистолет АСТЕН-919 и обойма):
                                                              # мастер 384 точки на клетку, показ пересчитан под размер на экране (ItemIcons.sized); сетка рюкзака,
                                                              # слот, карточки торговца, строка конструктора, метка «БЕЗ МАГ» → docs/screens/icon_detail*.png;
                                                              # перепечь: res://tools/icon_bake.tscn -- wpn_hg_02 mag_919_17 (с окном), затем --import
tools/godot.cmd --headless res://tools/hand_mag_test.tscn    # обойма оружия в руках из окна рюкзака (Balance.HAND_MAG; пистолеты с ригом — ПМ, АСТЕН-919):
                                                              # «Вынуть обойму» — руки вынимают, предмет в рюкзак по окончании движения; магазин на оружие — вставить
                                                              # (пустая шахта, с досылом на задержке) или перезарядка этим магазином; отмена, руки заняты, полный рюкзак
tools/godot.cmd --headless res://tools/export_weapon_refs.tscn -- "out=<папка>" # все стволы игры (и ГРАНЬ-15 с обвесами под левую руку) в GLB — образцы для хватов в Blender
tools/godot.cmd --headless res://tools/build_test.tscn       # сборка деревом (WeaponBuild): старый угловой → кронштейн, пазы 20 мм, «занято»/«закроет прицел», кронштейн снимается с прицелом, линии прицелов
tools/godot.cmd --windowed --resolution 1280x720 res://tools/build_shots.tscn # снимки сборок: кронштейн 45° справа/слева, проставка, поворотный; docs/screens/build_*.png
tools/godot.cmd --windowed --resolution 1280x720 res://tools/thumb_shots.tscn # миниатюры экземпляров в сетке рюкзака (сборка, вынутый магазин, магазин на 60); docs/screens/thumb_*.png
tools/godot.cmd --windowed --resolution 1600x900 res://tools/builder_shots.tscn # конструктор оружия: обзор, точка, кронштейн по пазам (можно/занято), прицел на нём, из глаза, торговец, применено; docs/screens/builder_*.png
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_adapters.py -- [id …] # переходники (кронштейн 45°, проставка, удлинитель, поворотный) → assets/models/attachments/adapters
tools/godot.cmd --windowed --resolution 1280x720 res://tools/scope_far_shots.tscn # сильная оптика на планке над цевьём: в прицеле картинка, линза не красная; снимки scope_far_*
tools/godot.cmd res://tools/scope_sun_shots.tscn             # оптика против солнца (блики, аберрация) и открытые прицельные из глаза
tools/build_release.cmd                                      # сборка для друзей: export\RING.zip (RING.exe = Godot 4.7.2 + RING.pck, шаблоны не нужны)
tools/build_patch.cmd                                        # обновление для друзей патчем вместо полного архива: export\patches\RING_patch_<N>_<метка>.pck —
                                                              # только изменённое с основы (последний build_release, метка — export\RING\patches\base.txt); накопительный,
                                                              # друзьям — в patches рядом с RING.exe, подключает автозагрузка ReleasePatch (первая). Изменились project.godot
                                                              # или src/core/release_patch.gd — не соберётся (tools/release_patch.py check), нужен полный выпуск
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
tools/godot.cmd --windowed --resolution 1600x900 res://tools/rig_shots.tscn # ростовая фигура со слотами и подсумки на броне (магазины, сброс пустых): тайник и окно рюкзака в рейде; снимки doll_*
tools/godot.cmd --headless res://tools/engraver_head_test.tscn # головка гравировщика в станке: вставить, нанести (размер, слева), вынуть; с окном — снимок окна станка
tools/godot.cmd --headless res://tools/trade_net_test.tscn -- host # + «-- client» через 3 с (порт 17793): обмен вещами в убежище и в рейде — отмена, обмен, рюкзак напарника виден, разошлись — отмена
tools/godot.cmd --windowed --resolution 1600x900 res://tools/workbench_repair_test.tscn # верстак, ремонт: изношенное плашками без прокрутки, починить одно и всё разом, нет денег — кнопки выключены; снимок workbench_repair
tools/godot.cmd --headless res://tools/hideout_keys_test.tscn # клавиши под окном убежища: открыт торговец или набирают текст — персонаж не ходит и не приседает
tools/godot.cmd --headless res://tools/roadmap_test.tscn    # дорожная карта до демоверсии (Esc → «Дорожная карта», то же в главном меню; RoadmapWindow,
                                                              # RoadmapData): список работ data/roadmap.json читается без ошибок, счёт «сделано / всего» по разделам и этапам,
                                                              # отметка из игры пишется в этот же файл и не затирает ручные правки, фильтр «только не сделанное», «отложено»;
                                                              # с окном (--windowed --resolution 1600x900) — снимки roadmap_*
tools/godot.cmd --windowed --resolution 1600x900 res://tools/tv_light_shots.tscn # свет от телевизора ночью без генератора: видно мебель и дальнюю стену; снимки tv_light_*
tools/godot.cmd --headless res://tools/holster_test.tscn    # оружие убирается клавишей своего слота и достаётся ею же, бег быстрее; с открытым рюкзаком в рейде персонаж стоит
tools/godot.cmd --headless res://tools/slung_test.tscn     # снаряжение и убранное оружие на теле (NpcOutfit, SlungWeapons): игрок на теле мародёра
                                                              # одет по своему снаряжению, длинные — за спиной (два накрест), пистолет и ракетница —
                                                              # в кобурах на бёдрах, от первого лица — только тень, убит — пусто; мародёр сменил ствол —
                                                              # второй на теле (active_slot гостям); с окном (--windowed --resolution 1600x900) — снимки slung_*
tools/godot.cmd --windowed --resolution 1600x900 res://tools/stickers_test.tscn # наклейки на оружии: клеить (предмет тратится), три на ствол, снять — пропала, зарубки «Счёта» за эвакуацию, страница верстака; снимок stickers_panel
tools/godot.cmd --headless res://tools/sticker_icons.tscn  # иконки наклеек из их рисунков (assets/stickers/<id>.png владельца или знак кодом) → assets/icons; затем --import
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
tools/godot.cmd --headless res://tools/climb_test.tscn     # залезть наверх (Climb: машина, ящик, край; тонкое — по-прежнему через) и вертикальная
                                                              # лестница (Ladder): схватиться, вверх, шаг на крышу, вниз, спрыгнуть; мародёр по лестнице; с окном — снимки climb_*
tools/godot.cmd res://tools/info_shots.tscn                # снимки окна описания предмета (info_*; ствол 47 % и прицел 30 % — состояние процентом) и прицела гранаты (nade_aim)
# Звукового стенда нет (удалён по решению владельца 2026-10-21). Звуки оружия: владелец прописывает список (docs/weapon_sounds.md),
# агент сверяет его с кодом (подключены ли механики) и сам следит за полнотой списка — см. docs/OWNER_NOTES.md, «Звук».
tools/godot.cmd --windowed --resolution 640x360 res://tools/weapon_sounds_test.tscn # звуки оружия от механики: гильза по полу под ней (плитка / металл / мягкое, катится на твёрдом),
                                                              # у задержки два звука (затвор назад и вперёд), без записей — тишина; без окна Godot после ошибки скрипта висит
python tools/sound_catalog_md.py                               # список всех звуков для чтения: docs/sound_catalog.md
python -X utf8 tools/prepare_firearm_layers.py [--only ключ,ключ] # выстрелы CC0-библиотеки (_asset_src/sound_libraries) слоями дистанции:
                                                              # свой, вблизи, средняя, вдали, очень далеко → кандидаты в _sound_try/Выстрелы_CC0_дистанции
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
tools/godot.cmd --headless res://tools/npc_outfit_test.tscn # внешность ботов по снаряжению (NpcOutfit): ряд типов на новом теле — броня, шлем, рюкзак по посадке,
                                                              # забрало у штурмовика «Периметра», подсумки по магазинам, LOD по дальности, чужой отряд в одном стиле;
                                                              # с окном -- shots — снимки npc_outfit_* (ряд спереди и сзади, крупно, чужой отряд)
tools/godot.cmd --headless res://tools/npc_loot_test.tscn   # лут с тела по видимому: убит — в ящике броня с подсумками и магазинами бота; забрали броню — на теле
                                                              # нет ни брони, ни подсумков; ящик унесли — тело голое
tools/godot.cmd --headless res://tools/equip_doll_test.tscn  # окно снаряжения v2 без окна: места брони половинками (пистолетный ½, автоматный — место, большой — пара),
                                                              # перевод старых подсумков, магазины по виду подсумка, снять / переставить, ПНВ и шлем без площадки, кукла, тело бота
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
src/audio/     audio_system.gd — только явные назначения data/audio_events.json; пустое действие молчит.
               Стенд — Sonora Studio 1.3, действия моделей — data/weapon_sound_slots.json; общих семейств и синтеза нет.
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
   **Карты, переведённые в правку руками** (решение владельца 2026-11-08: «перевести в формат, чтобы я мог
   редактировать их вручную из editor»; план — `docs/design/editable_levels.md`, памятка — `docs/level_editing.md`):
   **сцена — источник правды, генератор её не перезаписывает.** Сейчас это «Санаторий», «Пригород» и «Проспект».
   «Проспект»: здания — узлы `prospekt_study.tscn` (были), 4 370 вещей наполнения — узлы `PropSpot` в `Filler/Наполнение`
   (план `filler.from_nodes`: `MallLandscape._items_from_nodes` собирает их в `plan.filler.items`, у вещей «вперемешку»
   модель закреплена девятым полем); улицы — 4 348 узлов `PlanPiece` в `Landscape/Улицы` (покрытия, вырезы, плиты,
   стены, коробки, колонны, лестницы, пандусы, балки, фонари, надписи; план `lists_from_nodes`: `MallLandscape.
   _pieces_from_nodes` собирает списки по узлам в прежнем порядке, в редакторе после правки — пересборка сама); места
   лута — данными (ящики — узлы `prospekt.tscn`); щелчок по кускам, вещам, деревьям — гизмо плагина
   `addons/ring_level_tools/pick_gizmo.gd`; схеме `prospekt_ld_plan.py` — снимок `prospekt_study -- snapshot`; генераторы
   `build_prospekt.py` / `build_prospekt_raid.py` — только с `PROSPEKT_OVERWRITE=1` (или `PROSPEKT_OUT` — в свою папку).
   «Пригород»: дома,
   машины, укрытия, мусор и так далее — узлы сцен `scenes/levels/zone01*` (были и раньше), деревья — узлы `TreeSpot`
   в `World/Vegetation/Деревья` (у россыпей деревьев `from_nodes`), кусты и лесной мусор — данные (кисть
   «Растительность»); генераторы зоны 1 (`build_zone01*.py`, `author_zone01_nw.py`, `author_loose_loot`) — только
   с `ZONE01_OVERWRITE=1`; после правок — `BAKE_MAPS.cmd` (навигация, укрытия, карта плана рейда). «Санаторий»: постройки — сцены
   `scenes/levels/sanatorium/buildings`, куски участка — `…/site`, беседки, машины, валуны, стройплощадки и деревья
   участка (`TreeSpot`) — узлы сцены уровня; коробки — `CSGBox3D` (материал — файл `…/materials/<ключ>.tres`, имя
   файла = ключ палитры), марши — `BlockoutStair`, покрытия — `MeshInstance3D` с meta `blockout_mat`, проверки пешком —
   `BlockoutChecks` внутри построек (едут вместе с ними). В игре всё склеивает `BlockoutMerge` — один меш на материал
   и простые коллизии, как было у генератора. Земля — «Кисть земли» (`addons/ring_level_tools`): маски грунта, трава,
   высоты — прямо в `data/terrain/*`. Генератор такой карты пишет только в отдельную папку (`SANATORIUM_OUT`):
   заготовки новых построек. Остальные карты переводятся по одной; до перевода у них — как ниже.
   Всё, что вне кольца, — узлы сцены уровня, их двигают руками: постройки
   (`scenes/world/blockout_building.tscn`, вид/размеры/этажи в инспекторе; двери и ворота —
   дочерние `blockout_opening.tscn`, режут ближайшую стену), точки появления (`spawn_point.tscn`)
   и эвакуации (`extraction_point.tscn`), эскалаторы (`escalator.tscn`: пара, уклон 30°, наверху
   площадка 2F и опущенная противопожарная штора). Вертикальные лестницы — `ladder.tscn` (высота площадки
   в инспекторе; лезут со стороны +Z лицом к −Z, площадка — за лестницей; связку навигации мародёрам ставит сама). Перекрытия (этажи паркинга, навесы, площадка
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
6. **Ассеты.** Из интернета — **только текстуры** (CC0 / CC-BY); **все модели — свои, в Blender, в стиле реализма**
   (решение владельца 2026-10-24; прежние импортированные модели пропсов ждут его решения о замене). Исключение —
   растительность Poly Haven (CC0: трава, бурьян, цветы, кусты, деревья) — можно (владелец 2026-11-07). Текстуры — CC0 / CC-BY
   (или собственные). Материалы, генераторы, кисти и альфы для Substance Painter — ещё Substance 3D Community
   Assets (Adobe Community Assets License 1.1, решение владельца 2026-10-26): в игру — только запечённым
   результатом, источник — в `assets/CREDITS.md`, сырьё — в `_asset_src/<id>/` с license.txt; сами файлы не
   раздаются отдельно и не входят в комплекты моделей на продажу; для обучения нейросетей их не использовать.
   Звук — ещё royalty-free библиотеки (Sonniss GDC,
   Boom Library, Soundsnap и т. п.: разрешено использовать в своей игре): текст лицензии —
   `assets/audio/LICENSES/<библиотека>.txt`, библиотека и ссылка — в источнике записи (стенд не
   перенесёт без этого). Пока репозиторий закрытый; если откроется — сырые файлы таких библиотек
   из git убрать (их лицензии обычно запрещают раздавать звуки отдельно от игры).
   Сырьё в `_asset_src/<id>/` + `license.txt`,
   в `assets/` — только через `tools/`; каждый источник записан в `assets/CREDITS.md`.
   **CC BY 4.0 разрешена и для коммерческой игры** (уточнение владельца 2026-11-06): обязательно
   указывать автора, источник, ссылку https://creativecommons.org/licenses/by/4.0/ и внесённые изменения
   (если были); сохранять предоставленные уведомления об авторских правах и лицензии. Всё это фиксировать
   в `assets/CREDITS.md`; атрибуция должна быть доступна игроку в поставке игры, а не только в репозитории.
   Для внешних ассетов должен быть процедурный запасной вариант — проект обязан запускаться
   без `assets/models` и `assets/textures`.
7. **Нет `any`-стиля.** Типизированный GDScript: аннотации у всех переменных, аргументов, возвратов.
8. **Комментарии — по-русски, о смысле, не о синтаксисе.** Имена — по-английски.
9. **Масштаб (решение владельца 2026-10-24, стенд `tools/scale_probe.tscn`, набор E).** Предметы, которые человек
   берёт и трогает, — 1:1: оружие, руки, NPC, машины, мебель, ларьки, прилавки, ступени, бордюры, знаки. **Проходы и
   помещения — × 1,3 по ширине и × 1,15 по высоте** от реальных: дверные проёмы (0,9 × 2,1 → 1,17 × 2,42), ширина
   комнат, коридоров, проходов между стеллажами, тротуаров и проездов; высота потолков жилья и первых этажей
   (2,7 → 3,1). Высоты, которые и так большие (залы, паркинги, цеха), не раздувать; исключение — паркинг −1 «Проспекта»:
   6 м в свету под балками с отделкой как в Таркове (выбор владельца на стенде `tools/parking_probe.tscn`, зал D,
   2026-10-29). Расстояния между объектами
   на улице — 1:1. Поле зрения по умолчанию — **80° по горизонтали** (`Settings.FOV_H_DEFAULT`). Правило — для
   новой геометрии («Проспект» и дальше); готовые карты пересобираются по его слову. Причина: при реальных
   размерах в игре всё выглядит мелким (нет периферийного зрения и тела), а общий множитель ломает пропорции.
10. **Единое освещение всех рейдовых карт** (решение владельца 2026-11-04: «сделай как на проспекте»,
   настройки стенда должны действовать на имеющиеся и будущие карты). Прежнее правило от 2026-10-24
   о новом свете для каждой карты заменено. Общая основа Проспекта — `data/lighting/raid_environment.tres`,
   панорамы — `data/lighting/sky.json`, численные настройки — `Balance.WORLD_LIGHT`, `WORLD_FOG`,
   `LAB_RULES.atmosphere`. `RaidLighting` подключает их в `RaidAtmosphere`, `DayCycle`, `RaidWeather`
   и `CameraLook` автоматически. Не возвращать индивидуальные light/look/depth_fog/sky_hdri из JSON
   карты в расчёт света. Стенд — `LIGHT_LAB.cmd` / «Отладочные стенды → Свет и атмосфера»;
   «Варианты → Применять на всех картах после сохранения → Сохранить». Именованные варианты локальны
   для компьютера (`user://development_labs.cfg`), работают на всех рейдовых картах и сохранениях.
   Подробности — `docs/development_labs.md`. Геометрия и локальные лампы помещений остаются у карты.
   **С 2026-11-05 свет ведёт `TodLight`** (решение владельца: «свет Road to Vostok — на все карты»; `src/world/tod_light.gd`,
   `Balance.TOD_LIGHT`, таблица по часам `data/lighting/time_of_day.json` — числа из их файлов, снимает
   `tools/research/rtv/light_tables.gd`): сила и цвет солнца и луны, рассеянный свет (половина — от неба), небо по их
   схеме (`src/world/tod_sky.gdshader`, облака — наши панорамы из `sky.json`), объёмная дымка вместо тумана по
   расстоянию, AgX; их час подбирается по высоте нашего солнца. Привыкание глаза, SSAO, SDFGI и отражения — наши.
   Выбор игрока — Esc → Читы → Мир → «Свет и небо» (`Settings.sky_mode`: «tod» / прежний с расчётным небом /
   с панорамами, в рейде сразу); `TOD_LIGHT.on = false` выключает новый свет совсем. Стенд «Свет и атмосфера» при
   новом свете — свои ползунки `LAB_RULES.atmosphere_tod`, при прежнем — прежние. Сравнение со светом их игры —
   стенд `tools/rtv_look.tscn`.

## Git

- Ветка `main`, работать в ней. Перед началом работы **всегда** `git pull --rebase`.
- Коммиты маленькие и частые, сообщение по-русски: `область: что сделано`.
- После каждой законченной задачи — `git push`. Бинарники идут через LFS автоматически (`.gitattributes`).
- Конфликт в `.tscn`/`.tres` решает тот, кто пришёл вторым: перечитать сцену, применить свои
  изменения заново, не сливать текстом вслепую.
- Папки `референсы/`, `_asset_src/` и `_sound_try/` (звуки на пробу) никогда не коммитятся.
- Агент дописывает в `docs/STATUS.md`, что сделал и что осталось — это единственный общий журнал.
