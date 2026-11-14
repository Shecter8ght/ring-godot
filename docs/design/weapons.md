# Оружие, патроны, обвес, броня — архитектура

Задача «расширить вооружение»: что было в проекте, что переиспользовали, как устроено теперь.
Если код расходится с этим файлом — правим файл.

## 1. Что было

| Система | Где | Как устроено |
|---|---|---|
| Справочник предметов | `data/items.json`, `ItemDb` | Предмет — словарь `{id, n}` + состояние (`dur` у брони, `mods` у оружия), позиция в сетке `x, y, r`. Категории `cat`, размер `size`, цена `value`, стопка `stack`. |
| Оружие | `Balance.WEAPONS` (4 ключа: pistol / rifle / shotgun / bolt), предметы `w_*` с `equip.weapon` | Урон, темп, магазин, разброс, отдача — в балансе по ключу. Один патрон на калибр (`ammo_9x19`, `ammo_545`, `ammo_12`, `ammo_762r`). |
| Обвес | `items.json → mod`, `WeaponMods`, `WeaponStats` | Слоты optic / muzzle / grip / stock / mag / tac / bipod, совместимость — список оружия (`fits`). Позиции крепления — в коде (`WeaponMods.MOUNTS`). Эффект — множители `fx`. Один tac-слот. |
| Модели | `WeaponModels` | Процедурные: пистолет, АК, помпа, болтовка. Meta: `muzzle`, `sight_h`, `ads_z`, `ocular`. Внешних моделей оружия нет. |
| Стрельба | `Player._fire` → `Hitscan.fire` | Луч, разброс; урон `Health.apply_or_request_damage(amount, from, zone, attacker)`, считает хост. Зоны: head / body / blast. |
| Броня | `Inventory.absorb` | «Доля снятого урона» + прочность (≈ доп. HP). Шлем защищает голову от ваншота. |
| Патроны у игрока | `Player.ammo`, `ammo_by`; `Raid.request_consume` | Магазин — число; перезарядка берёт патроны из рюкзака (хост вычитает). При эвакуации патроны из магазинов возвращаются. |
| ИИ | `Balance.AI_WEAPONS`, `Marauder` | Свой упрощённый ствол, бесконечные перезарядки; при смерти — ствол + случайный запас патронов + таблица лута. Броня — множитель урона. |
| Лут, торговец | `data/loot.json`, `data/trader.json` | Таблицы `[id, вес, [мин, макс]]`, бросков `rolls`; торговец — список id + уровень доверия. |
| Сохранение | `Profile` (json) | stash / equipment / backpack / pocket — списки тех же словарей-экземпляров. |
| UI | `InventoryUI` (рейд), `HideoutUI` (верстак), `GridView` | Сетка, контекстное меню, верстак: список слотов обвеса. |
| Ввод | `project.godot` actions | fire, aim, reload, flashlight (T) и т.д. |

## 2. Что переиспользуем

- **Экземпляр предмета = словарь в инвентаре.** Definition — в данных, Instance — сама запись
  (`dur`, `mods`, `mag`, `sight`…). Сетка, перенос, сохранение, репликация уже работают со словарями.
- **ItemDb** остаётся единым реестром предметов; оружие/патроны/магазины/обвес/броня — в своих
  файлах данных, ItemDb подмешивает их в общий справочник (имя, размер, цена, вес, теги).
- **WeaponStats** — единственное место расчёта характеристик (теперь от экземпляра + патрона).
- **WeaponModels / WeaponMods** — процедурные модели и детали обвеса остаются запасным вариантом;
  точки крепления переезжают в данные.
- **Hitscan → Health (хост)** — та же цепочка, к урону добавляются параметры пули.
- **Raid RPC** (хост меняет инвентарь, у всех реплицируется) — для перезарядки, снятия обвеса, плит.
- **Консоль разработчика** (`QuestHud`, `) — туда же команды оружия.

## 3. Данные

- `data/weapons.json` — калибры, модели-основы (точки крепления), оружие, патроны, магазины,
  обвес, пресеты, алиасы старых id.
- `data/armor.json` — жилеты/плитоносцы, плиты, шлемы.
- `data/loadouts.json` — снаряжение ИИ по типам (мирные, мародёры, «Периметр»).
- `WeaponDb` (`src/combat/weapon_db.gd`) — типизированный доступ: `weapon(id)`, `ammo(id)`,
  `magazine(id)`, `attachment(id)`, `vest / plate / helmet(id)`, `preset(id)`,
  `loadout(id)`, `mounts_of`, `mounts_for`, `attach_block`, `mag_fits`, `make_weapon`, `pick`.
- `Gear` (`src/items/gear.gd`) — операции над экземплярами: снять/поставить часть (`strip`,
  `fit`), перезарядка, снарядить магазины. `Armor` — пробитие. `WeaponStats` — характеристики.

Инвентаризация прицелов, ЛЦУ и креплений (2026-10-26): [перечень и найденные пробелы](sight_inventory.md),
машинная совместимость — `sight_inventory.json`, повторный сбор — `tools/sight_inventory.tscn`.

### ID
Основные 23 позиции оружейной линейки взяты из `docs/RING_weapon_design_doc_v9_final_cut.html`; их
встроенные PNG извлекает `node tools/import_weapon_catalog.mjs`. По отдельному решению владельца к ним
добавлена винтовка «Шорох-9» (прототип VSS Vintorez) из полного дизайн-документа; её собственная иконка хранится
в проекте. Игровое название утверждено владельцем 2026-10-26; ID `wpn_sp_02`, пресет `VSS_BASE` и пути моделей
сохранены для совместимости. Коды и ID:

| Класс | Оружие |
|---|---|
| Пистолеты | `wpn_hg_01` ПМ; `wpn_hg_02` Glock 17 Gen5; `wpn_hg_03` HK USP .45 |
| SMG / PDW | `wpn_smg_01` HK UMP45; `wpn_smg_02` FN P90; `wpn_smg_03` KRISS Vector; `wpn_smg_04` PP-19-01 Vityaz; `wpn_smg_05` SR-2M Veresk |
| Автоматы | `wpn_ar_01` AK-12; `wpn_ar_02` M4A1; `wpn_ar_03` SIG MCX Virtus; `wpn_ar_04` FN SCAR-L; `wpn_ar_05` SIG MCX Spear; `wpn_sp_01` AS VAL |
| Точные | `wpn_sp_02` Шорох-9; `wpn_dmr_01` HK MR762; `wpn_dmr_02` BCM MK12; `wpn_sr_01` Accuracy International AWM; `wpn_sr_02` Barrett M82A1 |
| Дробовики | `wpn_sg_01` Benelli M4; `wpn_sg_02` Saiga-12K; `wpn_sg_03` Mossberg 590A1 |
| Пулемёты | `wpn_lmg_01` PKM; `wpn_lmg_02` M249 SAW |

У предмета есть короткий `code` (`AK12`, `G17`, `M249`…). Старые id (`w_rifle`, `wpn_ar_06`,
`ammo_76239_std`, `mod_red_dot`…) сохранены в `aliases`: профиль при загрузке переводит их в
ближайшие новые аналоги. Это мягкая совместимость, а не обещание сохранить прежнюю платформу и калибр.

Кнопка `i` на карточке разделяет текст на назначение, **технические характеристики** и выделенную
фразу **«В деле»**. ТТХ не переписаны вручную: окно берёт актуальные калибр, темп, дальность,
перезарядку, надёжность, ёмкости, баллистику и числовые эффекты обвеса прямо из данных. Поле `flavor`
есть у всех 138 элементов оружейного каталога: 24 стволов, 37 боеприпасов, 32 магазинов и 45 обвесов.
Генератор прекращает работу, если у нового элемента нет такой фразы; `arsenal_test` проверяет покрытие.

### Ёмкости и платформы: источники

Игровые характеристики не пытаются быть баллистическим симулятором, но штатные магазины,
калибры, темп и ограничения платформ сверены прежде всего с первичными источниками:

- Glock G17 Gen5 — 17 штатно, варианты 19/24/31/33: https://us.glock.com/en/products/law-enforcement/pistols/g17-gen5
- HK USP .45 — 12: https://www.heckler-koch.com/Downloads/Bedienungsanleitungen%20Jagd%20und%20Sport/Pistolen/DE/USP%20%20OM%20%28DE-EN-ES-FR%29%20986451%20001.0320.pdf
- FN P90 — 50: https://fnherstal.com/en/defence/portable-weapons/fn-p90/
- KRISS Vector .45 — Glock 21 на 13 и увеличенные MagEx: https://store.kriss-usa.com/images/dealer-resources/kriss/KRISS-MANUAL/Gen-Two/KRISS-MANUAL_2017_VECTOR-Gen-2_CRB-SBR-SDP-12.pdf
- Vityaz — 30: https://rostec.ru/media/news/zaversheny-gosispytaniya-pistoleta-pulemeta-kalashnikova/
- SR-2M — 20/30 и темп 900: https://rosguard.gov.ru/page/index/pistoletpulemt-sr2m-veresk
- VSS Vintorez — принадлежность к специальному оружию ЦНИИТОЧМАШ и актуальная модернизированная
  версия подтверждены Ростехом: https://rostec.ru/media/news/andrey-belousov-posetil-tsentralnyy-nii-tochnogo-mashinostroeniya/
- AK-12 — 30 и основные ТТХ: https://www.rostec.ru/en/directions/weapons/products-projects/ak-12-ak-15-ak-19-assault-rifles/
- M4 — 30 и диапазон темпа: https://www.colt.com/wp-content/uploads/2023/02/m16a2carbinecommando9mmsmgm4carbine.pdf
- MCX Virtus — 5.56/.300 BLK и интерфейсы: https://www.sigsauer.com/pub/media/sigsauer/resources/OPERATORS-MANUAL-SIGMCX-VIRTUS-ENGLISH-2402117-01-REV-00-LR.pdf
- FN SCAR-L — 30 и 550–650 выстр./мин: https://fnherstal.com/app/uploads/sites/2/technical-data-fn-scar-l-mk2-2.pdf
- MCX Spear — два магазина на 20 и 6.8×51: https://www.sigsauer.com/blog/now-shipping-the-incredible-new-mcx-spear-rifle
- Barrett M82A1 — 10; глушитель не допускается производителем: https://barrett.net/support/faq/
- Benelli M4 — 5+1: https://www.benelliusa.com/resources/ballistic-magazine-names-benelli-m4-h2o-tactical-as-2019-best-semi-auto-shotgun
- Mossberg 590A1 — конфигурация 7-shot и патронник 3″ (12/76): https://resources.mossberg.com/hubfs/press_releases/Mossberg-Introduces-7-Shot-Versions-of-590A1-and-590-PR-1-4-2016-FINAL.pdf
- PKM — короба 100/200 и темп 600–800: https://roe.ru/pdfs/pdf_7081.pdf
- M249 / FN MINIMI — ленточное питание, короб/мягкий короб и около 800 выстр./мин: https://fnherstal.com/app/uploads/sites/2/technical-data-fn-minimi-556-mk3.pdf

Для редких ёмкостей без однозначного актуального первичного листа (ПМ, UMP45, AS VAL, VSS Vintorez,
Saiga-12, AWM) зафиксированы распространённые штатные значения как осознанные игровые допущения.

## 4. Экземпляр оружия

```
{"id": "wpn_ar_01", "n": 1, "dur": 91.0, "rev": 3,
 "mods": {"optic_primary": {"id": "optic_lpvo_01"},
          "optic_offset":  {"id": "optic_offset_rd_01"},
          "side_left":     {"id": "tac_flashlight_01", "light": false},
          "side_right":    {"id": "tac_laser_01", "laser": true},
          "muzzle":        {"id": "muzzle_supp_545_01"}},
 "mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 17},
 "sight": "offset"}
```
Магазин в рюкзаке: `{"id": "mag_545_30", "n": 1, "ammo": "ammo_545_ap", "rounds": 30}` (с
состоянием — не складывается). У ружей и болтовок магазин встроенный: `mag.id == ""`, патроны —
`mag.ammo / rounds`. Плитоносец: `{"id": "carrier_perimeter_std", "dur": … (мягкая часть),
"plates": {"front": {"id": "plate_perimeter", "dur": 17}, "back": {…}}}`. Шлем, плита — `dur`.
`rev` — счётчик правок хозяином (`Gear._bump`): владелец видит, что оружие поменяли (вставили
магазин, сняли обвес), и перечитывает своё состояние.

Состояние «в руках» (патроны, износ, фонарь/ЛЦУ, выбранный прицел, задержка) ведёт владелец
(`Player._ws`) и шлёт хосту `Raid.request_weapon_state`; перезарядку делает хост
(`Raid.request_reload` → `Inventory.reload_slot` → `Gear.reload_weapon`): полный магазин из
рюкзака меняется на текущий (тот — обратно с остатком), нет магазинов — досыпка россыпью
(дольше, `RELOAD_TOPUP_K`).

## 5. Крепления и совместимость

- У оружия — `mounts`: имя точки → интерфейс. Имена точек общие (`WeaponDb.MOUNTS`):
  `optic_primary, optic_offset, muzzle, underbarrel, side_left, side_right, stock`.
  Магазин — отдельно: `mag_if` (интерфейс горловины), у магазина `mag.if`; `internal_mag` — встроенный.
- У обвеса — `fits`: список интерфейсов (`RAIL_TOP`, `RAIL_SIDE`, `RAIL_BOTTOM`, `SLIDE_RMR`,
  `PISTOL_RAIL`, `DOVETAIL`, `OFFSET_45`, калиберные `THREAD_*`, платформенные `STOCK_*`,
  `BIPOD_CLAMP`). Интерфейсы магазинов разделены по платформе и калибру: физически похожие STANAG
  5.56 и .300 BLK намеренно разные, чтобы игра не позволяла зарядить неподходящий патрон.
  Новое оружие с тем же интерфейсом сразу принимает весь подходящий обвес (arsenal_test CASE 12:
  прицел и ствол добавлены только данными).
- Конфликты: `blocks` у обвеса (оптика 8× и 12× закрывает `optic_offset`) — `WeaponDb.attach_block`.
- **Угловой прицел.** Точка `optic_offset` с интерфейсом `OFFSET_45` — встроенный кронштейн 45° на
  верхней планке (упрощение из п.19 ТЗ). Формат `mods` допускает позже вложенный
  `{"id": кронштейн, "mods": {...}}` — физический адаптер.
- ЛУМАР H1 ставится также на угловой кронштейн (удлинённое плечо, чтобы корпус не пересекал
  основную оптику). Запасной вариант по решению владельца от 2026-10-09 — левая или правая
  планка цевья (`side_left` / `side_right`, `RAIL_SIDE`); корпус на боку, при наведении крен
  компенсируется поворотом оружия на 90°. Фонарь или ЛЦУ в этих слотах прицелом не считается.
- Позиции точек — `weapons.json → models → sockets` (по процедурной основе: pistol, rifle,
  shotgun, bolt; у углового — `roll`). Нет точки у модели — обвес не рисуется, но работает.
- Где ставить: верстак в убежище (уровень верстака по точке — `Balance.WORKBENCH_SLOT_LEVEL`),
  в рейде — перетащить из рюкзака на оружие; снять — ПКМ по оружию (слот, рюкзак, ящик/труп).

## 6. Прицелы

- `sight` на экземпляре: `primary` / `offset` / `side_left` / `side_right`.
  СКМ от первого лица или клавиша O (`toggle_sight`) перебирает установленные прицелы.
  Один прицел — ничего.
  Снят основной — остаётся угловой (или открытый).
- От первого лица: у каждого прицела своя линия (`sight_h`, `ads_z`; у углового `sight_offset
  {x, h, roll}`). Угловой — модель в руках заваливается на 45° по крену, его линия — на оси
  взгляда; основной оптический — вид в окуляр (`scope_active`). arsenal_test CASE 2.
- В изометрии: основной оптический — приближение камеры (`iso_zoom`), от бедра хуже
  (`ISO_AIM.scope_hip`); угловой — без приближения, от бедра точнее (`ISO_AIM.offset_hip`),
  быстрее довод (`aim_k`). CASE 3.

## 7. Тактические устройства

- `side_left` / `side_right` (и `underbarrel` у комбо). Фонарь и ЛЦУ одновременно, каждый в своей
  точке; модели — узлы `Flashlight_<точка>` / `LaserBeam_<точка>` с meta `mount`.
- Состояние — в записи оружия: `mods[точка].light` / `.laser`. T — все фонари на стволе, L — все
  ЛЦУ; у комбо (`tac_combo_01`, есть и `light`, и `laser`) T и L включают свою часть независимо.
- Фонари из данных: `light: {range, angle, energy, indirect, specular, fog, view}` — обычный
  (`tac_flashlight_01`) и мощный светодиодный (`tac_flashlight_hp_01`: вдвое дальше и ярче, уже
  пучок, сильнее отражения; `view` — ИИ видят светящего дальше).
- Проба по двум кадрам владельца из Tarkov (2026-10-29): у обычного фонаря, мощного и комбо
  мягкий профиль рефлектора `assets/textures/lights/flashlight_beam.tres`: светлее в середине,
  плавный спад к слабой широкой периферии. Один прожектор с проекцией и тенями; цвет слегка
  холодный белый. `angle` задаёт внешнюю границу периферии (полуугол), яркость и отражённый свет
  уменьшены, чтобы сохранялась фактура близкой стены. Дальность 30/60 м и `view` прежние.
  Профиль и тени задаёт `WeaponMods._light_node`, общее `Settings.soften` их не перекалибровывает.
  Проверка в движке: `tools/godot.cmd --windowed --resolution 1920x1080 res://tools/flashlight_shots.tscn`
  → `docs/screens/flashlight_eft_20261029/`: прежние/новые параметры с одной точки, в прицеле,
  стена в темноте, при стационарном свете вкл/выкл, мощный фонарь, комбо. Художественная оценка — владельцу.
  Уточнение по его замечанию о размере пятна: обычный/комбо — полуугол 28° вместо 32°, мощный —
  20° вместо 23° (диаметр пятна на той же дистанции примерно на 15% меньше). Профиль и яркость прежние.
  `FLASHLIGHT_COMPARE=soft` сравнивает с первой мягкой версией; `FLASHLIGHT_OUTPUT` задаёт папку кадров.
  Сравнение ширины — `docs/screens/flashlight_eft_20261029_narrow/`.
- ЛЦУ: от бедра точнее (`laser.hip_spread`), в темноте выдаёт (`Balance.AI_VIEW_LASER`).
- Фонари ИИ: налобный или, если есть, на оружии; дальше `AI_LIGHT_FADE.begin` от камеры гаснут,
  тень — только вблизи. Фонарь в лицо слепит (LightGlare у игрока, мародёр целится хуже).

## 8. Урон и броня

- Брони три (`armor_poor` — мягкая без плит, `armor_mid` — плитоносец, `armor_top` — тяжёлая) и пояс `belt_pouches`
  без защиты; шлемов три (`helmet_simple`, `helmet_mid`, `helmet_top`). Старые id (`vest_*`, `carrier_*`, `helmet_*`)
  — псевдонимы (`aliases`), сохранения переводятся при загрузке (2026-10-24, `docs/design/npc_gear_by_type.md`).
- Пуля несёт `damage, pen, armor_dmg` (патрон) — `Hitscan.fire(..., bullet)` →
  `Health.take_damage(amount, from, zone, at, bullet)` → фильтр брони `Armor.hit` (один путь для
  игрока и ИИ). Зоны: `head`, `thorax` (спереди/сзади — по направлению выстрела относительно
  корпуса), `arms`, `legs` (`ZONE_DAMAGE`).
- Плита защищает `thorax` своей стороны (с вероятностью `coverage`), под ней — мягкая часть
  жилета; шлем — `head` (тоже `coverage`). Защита слоя = `ARMOR_CLASS_PROT[класс]` × состояние
  (не ниже `ARMOR.dur_floor`). Шанс пробития — плавная ступень `pen` против защиты
  (± `ARMOR.window`). Не пробила — травма `blunt × урон`, износ `armor_dmg`. Пробила — проходит
  от `through_min` до всего урона, износ × `wear_pen` × материал.
- Голова без шлема (или мимо него, или шлем пробит) — смерть, как было. Жилет без плит почти не
  защищает от винтовки. CASE 13–16.

## 9. ИИ

- Снаряжение — `loadouts.json` (тип ИИ → `Balance.AI_ARCHETYPES.loadout`, у штурмовиков шанс
  главаря): пресет оружия, запасные магазины с тем же патроном, броня с плитами, шлем,
  аптечки, износ. «Периметр» по ролям отряда: командир, стрелок, штурмовик, марксман
  (`pmc_squad`). Марксман — LPVO + угловой коллиматор, стрелок — фонарь + ЛЦУ.
- Стреляет своими магазинами (урон — патрон × `AI_DAMAGE_K`, поведение — `AI_CLASS` по классу
  оружия); кончились — пистолет, нет и его — «Пустой!» и отход. Раненым лёжа — пистолет, если есть.
- При смерти выпадает то, что на нём: оружие с обвесом, износом и остатком в магазине, запасные
  магазины, броня с износом плит, шлем, аптечки + таблица лута выкладки. CASE 17.

## 10. Прочность и вес

- Прочность оружия 0–100: разброс (`WEAPON_WEAR.spread`), шанс задержки (R — устранить), цена.
  Износ за выстрел (`wear` оружия × патрон).
- Вес у каждого предмета (с обвесом, магазином, плитами); выше `CARRY.free_kg` — медленнее и
  быстрее устаёшь.

## 11. Лут и торговец

- Таблицы лута (`data/loot.json`): предмет, `preset:<сборка>`, `table:<таблица>` и
  `pick:kind=…;tags=…;tier=…;min_tier=…` — случайный предмет арсенала по виду, тегам и тиру
  (вес — по редкости, `Balance.LOOT_RARITY_W`). Опции: износ, доля патронов.
- Торговец: T1 — сразу, T2 — доверие 2, T3 и редкое (глушители, бронебойные) — доверие 3, T4
  не продаёт — только с тел и из сбросов. Список разбит на разделы. На панели Esc → «Админ» чит
  «Любое оружие у Михалыча» добавляет все 23 ствола и снимает только их проверку доверия; цена и
  свободное место по-прежнему проверяются.

## 12. Отладка

Консоль разработчика (` в сборке из редактора), `ArsenalDev`: `give weapon AK12`,
`give ammo 545_AP 120`, `give optic LPVO_01`, `equip primaryOptic LPVO_01`,
`equip offsetOptic OFFSET_RED_DOT_01`, `equip sideLeft FLASHLIGHT_01`, `toggle sight|flashlight|laser`,
`spawn loadout perimeter_marksman`, `damage plate front 50`, `set weapon durability 25`, а также
`give preset:AK12_BASE`, `unmount <точка>`, `stats`, `list …`. Проверки: `tools/arsenal_test`
(CASE 1–20 ТЗ), `tools/compile_check` (все скрипты собираются).

## 13. Что дальше (не сделано)

- Модели оружия — 4 процедурные основы, масштабируются; своих 3D-моделей у 23 стволов пока нет.
- Физический адаптер углового прицела, подствольники, сменные цевья, магнифер, тепловизор, ИК-ЛЦУ.
- Боковые плиты, разгрузки, рюкзаки с ёмкостью.
