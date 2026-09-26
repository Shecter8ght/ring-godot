extends Node
## Весь баланс игры — только здесь. Autoload `Balance`.
## Другие скрипты читают значения отсюда и не держат своих чисел.

# --- Игрок: движение по стойкам, м/с ---
const PLAYER_WALK_SPEED := 2.6
const PLAYER_SPRINT_SPEED := 5.2
const PLAYER_CROUCH_SPEED := 1.4
const PLAYER_PRONE_SPEED := 0.6
const PLAYER_ADS_SPEED_SCALE := 0.55
## Ускорение/торможение — чтобы разгон и остановка читались, но не «плыли».
const PLAYER_ACCEL := 18.0
const PLAYER_DECEL := 24.0
## Поворот корпуса к курсору, рад/с.
const PLAYER_TURN_SPEED := 12.0

## Визуальный выбор клипа по реальному перемещению; физику персонажа не меняет. Скорость для
## выбора сглажена за speed_smooth_sec, с (иначе на мониторе 144+ клип скачет каждый кадр);
## с автоматом от sprint_from, м/с, — спринт (бег игрока 5.2, сглаженная скорость к ней снизу).
## Модель опущена под стойку, м: присед на месте, ходьба вприсядку (у клипа таз выше), лёжа.
const CHARACTER_ANIM := {"move_min": 0.12, "run_from": 3.1, "sprint_from": 4.8, "blend_sec": 0.16, "prone_hold_sec": 1.0, "crouch_drop": 0.57, "crouch_walk_drop": 0.29, "prone_drop": 0.63, "speed_smooth_sec": 0.1}

# --- Капсула по стойкам: высота, м ---
const STANCE_HEIGHT := {"stand": 1.8, "crouch": 1.2, "prone": 0.5}
const CAPSULE_RADIUS := 0.35

# --- Камера ---
## Наклон изометрии от горизонта (Duckov ≈ 55–60°: видно планировку, а не стены).
const CAMERA_PITCH_DEG := 58.0
const CAMERA_YAW_DEG := 45.0
const CAMERA_DISTANCE := 28.0
const CAMERA_FOV := 32.0
const CAMERA_ZOOM_MIN := 12.0
const CAMERA_ZOOM_MAX := 50.0
const CAMERA_ZOOM_STEP := 2.0
## Камера смещается к курсору: доля расстояния до курсора и предел, м.
const CAMERA_CURSOR_LEAD := 0.28
const CAMERA_CURSOR_LEAD_MAX := 5.0
const CAMERA_FOLLOW_SMOOTH := 8.0
## Скорость вращения камеры по Q/E, град/с.
const CAMERA_TURN_DEG_PER_SEC := 90.0
## Вырез стен у камеры: доли дистанции камеры, ближе near — стена невидима, дальше far — целая.
## Пол на дистанции ~0.85 (высота камеры), стена под камерой ~0.6 — попадает в вырез, игрок (1.0) — нет.
const CAMERA_CUTAWAY_NEAR := 0.62
const CAMERA_CUTAWAY_FAR := 0.96
## Перекрытие (этаж паркинга, крыша навеса) выше ног игрока больше чем на это — прячется, м.
const DECK_HIDE_ABOVE := 1.9
## Взаимодействие (F): ключ, рубильник — ближе этого к предмету, м.
const INTERACT_RADIUS := 1.8
## Зона эвакуации по высоте от точки (паркинг многоуровневый — не засчитывать этаж выше), м.
const EXTRACT_ZONE_HEIGHT := 2.5
## Эвакуация группой: кто-то встал в открытую зону — общий отсчёт, с. Кончился — кто в зоне, уходит
## со всем; живые не в зоне — в убежище без добычи. Все живые уже в зонах — короткий отсчёт точки.
const EXTRACT_GROUP_SEC := 180.0
## Щелчок рубильника слышно далеко — мародёры идут проверить, м.
const NOISE_SWITCH := 35.0
## Рюкзак: вместимость в ячейках (размеры предметов — data/items.json).
const BACKPACK_CELLS := 30
## Сетка рюкзака, ш × в (ячеек — BACKPACK_CELLS).
const BACKPACK_GRID := Vector2i(6, 5)
## Стопки мелочи (предметы 1×1 без состояния и не надеваемые): сколько штук в одной ячейке —
## не меньше этого (в данных может быть больше, как у патронов). Расходники и ценная мелочь
## (категории STACK_BIG_CATS: бинты, еда, гранаты, ювелирка, часы…) — по STACK_BIG, остальное — по STACK_SMALL.
const STACK_SMALL := 5
const STACK_BIG := 10
const STACK_BIG_CATS := ["med", "food", "value", "barter", "throw"]
## Обыск тела / выброшенного, с (у контейнеров на пропсах — data/loot.json).
const SEARCH_BODY_SEC := 2.0
## Контейнер на пропе — на этой высоте над полом (к ней меряется дальность «F»), м.
const LOOT_POINT_HEIGHT := 0.6

# --- Убежище и торговец ---
## Тайник: вместимость в ячейках.
const STASH_CELLS := 300
## Сетка тайника, ш × в (ячеек — STASH_CELLS).
const STASH_GRID := Vector2i(10, 30)
## Новый профиль: деньги и что лежит в тайнике ([id, штук]).
const START_MONEY := 60000
const START_STASH := [["wpn_hg_03", 1], ["wpn_ar_03", 1], ["ammo_919_fmj", 100], ["ammo_545_std", 120],
	["mag_545_30", 1], ["mag_919_17", 1], ["bandage", 4], ["painkillers", 2], ["vest_police", 1], ["helmet_military_old", 1], ["grenade", 2]]
## Выручка Михалыча: остался без огнестрела и без денег на самый дешёвый ствол — бесплатный
## набор, чтобы было с чем идти в рейд (сколько угодно раз, пока снова не встанешь на ноги).
const RESCUE_KIT := [["wpn_hg_01", 1], ["ammo_918_pst", 48], ["bandage", 2]]
## Торговец продаёт дороже цены предмета и покупает дешевле (с учётом износа брони).
const TRADER_BUY_MULT := 1.25
## Обвесы — редкость: у Михалыча вдвое дороже обычной наценки (продать — по обычной цене).
const TRADER_MOD_BUY_MULT := 2.0
const TRADER_SELL_MULT := 0.55
## Доверие торговца: за каждую эвакуацию и сверху — если вынес на сумму не меньше порога, ₽.
## Пороги доверия и цены маршрутов на этажи — в data/floors.json.
const TRUST_PER_EXTRACTION := 1
## Уровни доверия: очки доверия, с которых начинается уровень 1, 2, 3, 4 (товары, задания, модули).
const TRUST_LEVELS := [0, 3, 6, 10]
## Модули убежища (data/hideout.json): с какого уровня верстака ставится обвес в слот;
## сетка защищённого кармана по уровню (0 — кармана нет); строк тайника по уровню;
## сколько заданий одновременно — без рации / с рацией.
const WORKBENCH_SLOT_LEVEL := {"muzzle": 1, "underbarrel": 1, "stock": 1, "optic_primary": 2, "optic_offset": 2, "side_left": 2, "side_right": 2}
const POCKET_GRIDS := [Vector2i(0, 0), Vector2i(2, 2), Vector2i(3, 3)]
const STASH_ROWS := [30, 40, 50]
const MISSION_SLOTS := [1, 3]
const TRUST_BONUS := 1
const TRUST_BONUS_VALUE := 60000
## Сцены: убежище (старт игры, между рейдами) и рейд.
const MAIN_MENU_SCENE := "res://scenes/ui/main_menu.tscn"
const HIDEOUT_SCENE := "res://scenes/levels/hideout.tscn"
const RAID_SCENE := "res://scenes/levels/f1_ring.tscn"
## Камера в убежище ближе — комната тесная.
const HIDEOUT_CAMERA_DISTANCE := 20.0
## Компас вверху экрана: ширина полосы, px, и сколько градусов видно в обе стороны.
const COMPASS_WIDTH := 560.0
const COMPASS_SPAN_DEG := 75.0

# --- Свет и атмосфера ---
const SUN_ENERGY := 1.6
const SUN_ELEVATION_DEG := 34.0
const SUN_AZIMUTH_DEG := -140.0
const AMBIENT_ENERGY := 0.35
const FOG_DENSITY := 0.005

# --- Ощущение выстрела ---
## Тряска камеры от своего выстрела и от попадания по тебе (м смещения), затухание 1/с.
const SHOT_SHAKE := 0.12
const HURT_SHAKE := 0.35
const SHAKE_DECAY := 9.0
## Отдача: подброс ствола (корпуса) вверх, рад, и возврат, 1/с.
const RECOIL_KICK := 0.12
const RECOIL_RETURN := 6.0
## Вид от первого лица (режим, V): поле зрения без прицела, град; оружие у бедра — смещение модели
## от глаза (вправо, вниз, вперёд), м.
const FPS_FOV := 74.0
const FPS_HIP_POSE := Vector3(0.13, -0.19, -0.42)
## Наклон из-за угла (Q/E, от первого лица и в прицеле): сдвиг глаза вбок, м; крен, град;
## скорость наклона (доля в секунду); на ходу в наклоне — медленнее.
const LEAN_OFFSET := 0.4
const LEAN_ROLL_DEG := 12.0
const LEAN_SPEED := 5.0
const LEAN_MOVE_SCALE := 0.6
## Раскачка разброса очередью: за выстрел прибавка = подброс × RECOIL_BLOOM, потолок, спад в секунду;
## в прицеле раскачка — эта доля.
const RECOIL_BLOOM := 10.0
const RECOIL_BLOOM_MAX := 1.5
const RECOIL_BLOOM_DECAY := 2.5
const RECOIL_BLOOM_ADS := 0.4
## Хитмаркер у курсора, с.
const HITMARKER_SEC := 0.14

# --- Мишени-попперы ---
const TARGET_HEAD_MULT := 2.5
const TARGET_KNOCK := 6.0
const TARGET_SPRING := 90.0
const TARGET_DAMP := 9.0
const TARGET_DOWN_SEC := 1.6

# --- Двери ---
## Скорость распахивания створки (чем больше, тем резче), 1/с.
const DOOR_SWING_SPEED := 7.0

# --- Здоровье ---
const PLAYER_HP := 100.0

# --- Условия рейда (RaidConditions, выбираются у лестницы в убежище) ---
## Время: риск (очки), солнце/луна (высота°, сила, цвет), небо и окружение (×), выдержка,
## дальность зрения мародёров на улице, м.
const RAID_TIME := {
	"day": {"name": "День", "risk": 0, "sun_elev": 48.0, "sun_energy": 2.2, "sun_color": Color(1.0, 0.95, 0.88), "sky": 1.0, "ambient": 1.0, "exposure": 0.9, "view": 60.0},
	"dusk": {"name": "Закат", "risk": 1, "sun_elev": 12.0, "sun_energy": 2.6, "sun_color": Color(1.0, 0.74, 0.5), "sky": 1.0, "ambient": 1.0, "exposure": 1.0, "view": 45.0},
	"night": {"name": "Ночь", "risk": 2, "sun_elev": 35.0, "sun_energy": 0.2, "sun_color": Color(0.70, 0.78, 1.0), "sky": 0.03, "ambient": 0.12, "exposure": 1.25, "view": 25.0},
}
## Погода: риск, во сколько раз хуже видно на улице (view), слышно (hear — радиус шума).
const RAID_WEATHER := {
	"clear": {"name": "Ясно", "risk": 0, "view": 1.0, "hear": 1.0},
	"rain": {"name": "Дождь", "risk": 1, "view": 0.75, "hear": 0.6},
	"fog": {"name": "Туман", "risk": 1, "view": 0.45, "hear": 1.0},
	"heat": {"name": "Жара", "risk": 1, "view": 1.0, "hear": 1.0},
}
const RAID_POWER := {
	"on": {"name": "Свет есть", "risk": 0},
	"emergency": {"name": "Аварийное освещение", "risk": 1},
	"off": {"name": "Электричества нет", "risk": 2},
}
## Погода меняется в рейде: ясно → дождь (шанс, через сколько секунд, гром за столько до него),
## туман → рассеется (шанс, через сколько).
const WEATHER_CHANGE := {"rain_chance": 0.3, "rain_after": [180.0, 600.0], "thunder_lead": 50.0,
	"fog_lift_chance": 0.4, "fog_lift_after": [300.0, 720.0]}
## Мокрая земля (асфальт, шейдер wet_asphalt): за сколько секунд дождя намокает плёнкой и
## наливаются лужи, за сколько после дождя сохнет плёнка и уходят лужи; лужи наливаются не
## выше puddle_max; рейд начался в дождь — уже мокро (start: [плёнка, лужи]).
const WET_GROUND := {"film_up_sec": 45.0, "puddle_up_sec": 200.0, "film_dry_sec": 300.0, "puddle_dry_sec": 900.0,
	"puddle_max": 0.85, "start": [1.0, 0.7]}
## Выносливость: запас, расход на бег в секунду, восстановление в секунду (после паузы, с);
## выдохся — бег снова с порога. В жару на улице расход × STAMINA_HEAT.
const STAMINA_MAX := 100.0
const STAMINA_DRAIN := 11.0
const STAMINA_REGEN := 16.0
const STAMINA_REGEN_DELAY := 1.0
const STAMINA_RESUME := 25.0
const STAMINA_HEAT := 1.7
## За очко риска: шанс лишнего броска в контейнере, доплата Михалыча (доля вынесенного).
const RISK_LOOT_BONUS := 0.12
## Вес редкости в выборке лута по тегам ("pick:" в data/loot.json).
const LOOT_RARITY_W := {"common": 6.0, "uncommon": 2.5, "rare": 0.7}
const RISK_PAY_BONUS := 0.05

# --- Тяжёлое ранение («лежит») ---
## Здоровье кончилось от попадания в корпус (или по касательной) — не смерть, а тяжёлое ранение:
## лежит, стреляет из пистолета, кидает гранаты, истекает кровью. Сразу смерть: в голову без
## шлема, граната ближе GRENADE_LETHAL_M, добили лежащего (кончился запас DOWN_HP — 1–3
## попадания), истёк кровью, третье ранение за рейд (больше DOWN_MAX).
const DOWN_HP := 30.0
## До смерти от кровотечения, с: первое ранение, второе.
const DOWN_BLEED_SEC := [60.0, 35.0]
const DOWN_MAX := 2
## Игрок не умирает сразу: смертельное попадание (голова без шлема, граната в упор) — тоже
## тяжёлое ранение, но кровь уходит быстрее (время × DOWN_LETHAL_BLEED_K).
const DOWN_LETHAL_BLEED_K := 0.5
const DOWN_CRAWL_SPEED := 0.3
## Раскачка прицела лёжа раненым ×, разброс ×.
const DOWN_SWAY := 3.0
const DOWN_SPREAD := 2.0
## Бинт лёжа: + секунд к кровотечению (подняться — только аптечкой).
const DOWN_BANDAGE_SEC := 20.0
## Поднять: напарник (держит F, аптечка из его рюкзака), сам себя (аптечка, дольше), с;
## встаёт с долей здоровья REVIVE_HP.
const REVIVE_SEC := 5.0
const REVIVE_SELF_SEC := 10.0
const REVIVE_HP := 0.3
const REVIVE_RADIUS := 1.8
## Тащить раненого (X): скорость того, кто тащит, м/с; на каком расстоянии тело за ним, м.
const DRAG_SPEED := 1.2
## Несёт раненого NPC на плече (сюжет): скорость, м/с (бег невозможен).
const CARRY_SPEED := 1.7
const DRAG_DIST := 0.95
## Лежит — держать X столько секунд: сдаться (умереть сразу).
const GIVE_UP_SEC := 3.0
## Голова: попадание выше стольких метров над ногами (по стойке). Лёжа — голову не выделяем.
const HEAD_ZONE := {"stand": 1.47, "crouch": 0.97}
## Граната ближе — насмерть (подорвался на ней).
const GRENADE_LETHAL_M := 1.6
const MARAUDER_HP := 100.0

# --- Оружие игрока ---
## Сами стволы, патроны, магазины, обвес — data/weapons.json (характеристики — WeaponStats).
## Отдача (натуральная): kick — подброс ствола за выстрел, рад; kick_h — увод вбок (случайно ±,
## со сдвигом kick_bias: плюс — вправо, у АК ствол уходит вправо-вверх); recover — какую долю
## подброса руки возвращают сами (остальное остаётся — очередь «ползёт», её тянут мышью вниз).
## Эргономика (0–100, WeaponStats): время «довода» в прицел и раскачка прицела, от худшей к лучшей.
const AIM_TIME_SLOW := 0.5
const AIM_TIME_FAST := 0.12
## Раскачка в прицеле: амплитуда, рад (стоя; сидя ×0.6, лёжа ×0.3, на сошках ещё ×0.4).
const SWAY_MAX := 0.012
const SWAY_MIN := 0.0015
const SWAY_STANCE := {"stand": 1.0, "crouch": 0.6, "prone": 0.3}
## Оптика отдельным рендером: разрешение картинки в окуляре, px; поле зрения основной камеры в
## прицеле с оптикой, град (сама оптика показывает своё, по кратности).
const SCOPE_RT_SIZE := 768
const SCOPE_MAIN_FOV := 52.0

# --- Прицел от первого лица (ПКМ) ---
## Чувствительность мыши в прицеле, рад на пиксель; у оптики — медленнее пропорционально FOV.
const ADS_SENS := 0.0024
## Высота глаз по стойке, м.
const ADS_EYE := {"stand": 1.62, "crouch": 1.05, "prone": 0.4}
## Предел наклона взгляда вверх/вниз, рад.
const ADS_PITCH_LIMIT := 1.35
## Вращение изометрической камеры средней кнопкой мыши, рад на пиксель.
const CAMERA_MMB_SENS := 0.006

# --- Гранаты ---
const GRENADES_START := 3
## fuse — запал, с; radius — радиус поражения, м; damage — урон в центре (падает к краю);
## throw_speed — скорость броска, м/с; max_range — дальше не докинуть; push — толчок телам.
const GRENADE := {"fuse": 2.6, "radius": 7.0, "damage": 140.0, "throw_speed": 13.0, "max_range": 18.0,
	"noise_m": 130.0, "push": 28.0, "shake_radius": 28.0}
## Огонёк на гранате: мигает всё чаще к взрыву (период от slow до fast, с), свет вокруг и ореол.
const GRENADE_LED := {"slow": 0.6, "fast": 0.07, "light_range": 2.5, "light_energy": 2.2, "halo_m": 0.5}
## Прицел гранаты (G зажата — траектория и радиус, отпустил — бросок): шаг расчёта дуги, с;
## сколько секунд полёта считать; толщина линии, м.
const GRENADE_AIM := {"step": 0.03, "max_t": 3.0, "width": 0.05}

# --- Регдолл ---
## Через сколько секунд покоя тела замирают (экономия физики).
const RAGDOLL_FREEZE_SEC := 8.0
## Толчок тела пулей: импульс = урон × коэффициент, Н·с (пуля не сдвигает тело — только вздрагивает).
const BULLET_PUSH := 0.12
## Толчок при смерти: база + за единицу последнего урона, Н·с — без подброса: подстреленный
## оседает и валится от стрелявшего, а не отлетает.
const RAGDOLL_DEATH_PUSH := {"base": 4.0, "per_damage": 0.1}
## Ящик с лутом, что вываливается из трупа мародёра: на сколько откатывается к стрелявшему, м,
## и за сколько падает, с.
const CRATE_TOSS_DIST := 0.8
const CRATE_TOSS_SEC := 0.5
## Какая доля скорости бега переходит в падение и демпфирование тел (вязкость «тяжёлого» тела).
const RAGDOLL_CARRY := 0.45
const RAGDOLL_DAMP := {"linear": 1.4, "angular": 6.0}

# --- Шум игрока: радиус слышимости шагов по стойке, м ---
const NOISE_STEP := {"stand": 7.0, "sprint": 14.0, "crouch": 3.0, "prone": 1.5}
const NOISE_STEP_INTERVAL := 0.45
## Звук шагов (Footsteps): между шагами — STEP_STRIDE / скорость, но в пределах STEP_INTERVAL, с;
## быстрее STEP_RUN_SPEED, м/с — бег (свои записи). Стена между ушами и шагами — глуше на
## AUDIO_OCCLUDED_DB и без верхов (срез AUDIO_OCCLUDED_CUTOFF, Гц): за стеной слышно, но не ясно.
const STEP_STRIDE := 1.2
const STEP_INTERVAL := [0.26, 0.75]
const STEP_RUN_SPEED := 3.8
const STEP_STANCE_DB := {"stand": 0.0, "crouch": -8.0, "prone": -14.0}
const AUDIO_OCCLUDED_DB := 8.0
const AUDIO_OCCLUDED_CUTOFF := 700.0

# --- Мародёр ---
## Кольцо (3 сектора): 24 мародёра отрядами по 1–3 — встречи часто, но не на каждом углу.
const MARAUDER_COUNT := 24
const MARAUDER_WALK := 1.5
const MARAUDER_RUN := 3.4
## Ближе этого до точки спавна игрока мародёры не появляются, м.
const MARAUDER_SPAWN_MIN_DIST := 45.0
## Безопасный старт: мародёр не появляется в прямой видимости точки появления ближе los_m;
## первые sec секунд рейда маршруты патруля обходят круг radius вокруг неё.
const SPAWN_SAFE := {"radius": 40.0, "sec": 150.0, "los_m": 90.0}

# --- Перелезание и бросок на землю ---
## Перелезание (Пробел у преграды; мародёры — по связкам навигации): высота преграды от min_h до
## max_h, м; дотянуться — reach от ног; толщина до max_thick; время, с (с перегрузом — дольше на
## weight_k); шум, м; выносливость.
const VAULT := {"min_h": 0.35, "max_h": 1.3, "reach": 1.0, "max_thick": 1.6, "sec": 0.75, "weight_k": 0.6,
	"noise_m": 16.0, "stamina": 12.0}
## Связки навигации «перелезть» для ИИ: образцы вдоль края навмеша через step м; не ставить, если
## обойти не дольше detour_m; связки не ближе spacing_m друг к другу; цена пути по связке.
const VAULT_LINKS := {"step": 1.5, "detour_m": 7.0, "spacing_m": 2.5, "travel_cost": 2.0}
## Бросок на землю (Alt + направление, в любую сторону): скорость рывка, м/с; подскок, м/с; сколько
## летит, с; сколько приходит в себя (не стреляет), с; шум, м; выносливость; повтор не чаще, с.
const DIVE := {"speed": 5.0, "hop": 1.6, "sec": 0.42, "recover": 0.55, "noise_m": 20.0, "stamina": 15.0, "cooldown": 1.0}

# --- Стресс ---
## Стресс 0–100 (свой у каждого игрока). Растёт от того, что пугает: пули рядом (near_miss за пулю,
## не чаще раза в near_gap с, ближе near_m), попадание (hit + hit_per_dmg за единицу урона), взрыв
## рядом (blast у самой гранаты, к краю тряски — ноль), тяжёлое ранение (сразу не ниже downed),
## напарник упал рядом (ally_down, в ally_down_m). Не ниже: low_hp — мало здоровья (< 35%),
## winded — выдохся. Спадает через calm_delay с тишины на calm в секунду; сидя/лёжа на месте —
## ×calm_cover_k, напарник в ally_m — ×calm_ally_k. Обезболивающее — минус painkillers.
## Последствия — только выше effects_from и плавно до 100: перезарядка дольше (×1+reload_k),
## прицел гуляет сильнее (×1+sway_k); редко, с перерывом — запнулся на перелезании (от
## stumble_from, шанс до stumble_chance, не чаще stumble_cd), выронил отстёгнутый магазин при
## смене (от fumble_from, шанс до fumble_chance, не чаще fumble_cd, +fumble_sec к перезарядке).
## Сердце слышно от heart_from. Адреналин (та же шкала stress_k): бег быстрее на ×1+adr_speed,
## выносливость тратится медленнее (×1−adr_stamina), попадание трясёт слабее (×1−adr_shake).
const STRESS := {"adr_speed": 0.1, "adr_stamina": 0.35, "adr_shake": 0.5, "near_miss": 6.0, "near_gap": 0.25, "near_m": 2.0, "hit": 10.0, "hit_per_dmg": 0.35, "blast": 25.0,
	"downed": 85.0, "ally_down": 22.0, "ally_down_m": 25.0, "low_hp": 35.0, "winded": 20.0,
	"calm_delay": 3.0, "calm": 5.0, "calm_cover_k": 2.0, "calm_ally_k": 1.5, "ally_m": 8.0, "painkillers": 35.0,
	"effects_from": 50.0, "reload_k": 0.4, "sway_k": 1.2,
	"stumble_from": 65.0, "stumble_chance": 0.3, "stumble_cd": 40.0,
	"fumble_from": 70.0, "fumble_chance": 0.25, "fumble_cd": 45.0, "fumble_sec": 0.8, "heart_from": 70.0}

# --- Общение в коопе ---
## Чат (Enter): сколько строк видно и сколько секунд строка висит после последнего сообщения;
## реплика над головой, с.
const CHAT_LINES := 8
const CHAT_FADE_SEC := 12.0
const CHAT_BUBBLE_SEC := 6.0
## Голос (зажать K): частота передачи, Гц; пакет, с; буфер у слушателя, с; слышно до, м (в
## убежище и рейде — объёмно, как голос рядом; по рации — нет); громкость, дБ.
const VOICE := {"rate": 16000, "packet_sec": 0.04, "buffer_sec": 0.5, "max_m": 40.0, "db": 4.0}
## Зрение: дальность (без уровня — запасная; в рейде — RaidAtmosphere по условиям), полуугол
## конуса, и во сколько раз дальность меньше для сидящего/лежащего.
const AI_VIEW_DISTANCE := 45.0
## В помещении видно на столько, м: свет есть, аварийный, темно днём (свет с улицы), темно ночью.
const AI_VIEW_INDOOR := {"lit": 50.0, "emergency": 25.0, "dark_day": 28.0, "dark_night": 12.0}
## С включённым фонарём тебя видно минимум на столько, м (× view фонаря: мощный — дальше).
const AI_VIEW_FLASHLIGHT := 70.0
## Включённый ЛЦУ в темноте (луч в дыму и пыли, точка на стене) — видно минимум на столько, м.
const AI_VIEW_LASER := 35.0
## В ПНВ точка коллиматора и голографа в руках — во столько раз крупнее (тонкая теряется в трубке).
const NVG_RETICLE_SCALE := 2.5
## Хроника рейда (src/story): когда событие считается событием. Здоровье ниже доли low_hp —
## критический момент; комплект дороже expensive_kit ₽ — дорогой, дешевле cheap_kit — дешёвый;
## убийств от high_kills — «много»; streak_n убийств за streak_sec с — серия; weak_kills убийств
## пистолетом — «слабым оружием»; точность — от accuracy_min_shots выстрелов (accurate / inaccurate);
## без урона — если рейд дольше no_damage_min_sec; находка от big_find ₽; вынес от valuable_loot ₽
## (меньше empty_handed — пустой); долгий рейд — от long_raid_sec; у выхода дольше camped_exit_sec;
## смерть быстрая — до fast_death_sec, у выхода — ближе near_exit_m; серия рейдов — от streak_raids.
## В рассказе events_min…events_max событий; история — history_n рейдов, recent_lines фраз не
## повторять. Ранг класса оружия — «лучше / хуже» (нашёл получше, убил слабым). Отбор: к интересности
## события — случайная прибавка до pick_jitter (похожие рейды звучат по-разному); событий в рассказе —
## сколько интереснее interesting, +0…1, в пределах events_min…events_max; связка между абзацами —
## с шансом transition_chance.
const RAID_STORY := {
	"low_hp": 0.25, "cheap_kit": 25000, "expensive_kit": 150000, "high_kills": 8, "streak_sec": 30.0, "streak_n": 3,
	"weak_kills": 2, "many_switches": 4, "accuracy_min_shots": 20, "accurate": 0.55, "inaccurate": 0.2,
	"trigger_happy": 250, "many_heals": 3, "no_damage_min_sec": 240.0, "big_find": 30000, "valuable_loot": 80000,
	"empty_handed": 5000, "long_raid_sec": 1500.0, "camped_exit_sec": 90.0, "fast_death_sec": 90.0, "near_exit_m": 25.0,
	"streak_raids": 3, "events_min": 3, "events_max": 6, "history_n": 10, "recent_lines": 80,
	"pick_jitter": 0.25, "interesting": 0.6, "transition_chance": 0.6,
	"class_rank": {"PISTOL": 1, "SMG": 2, "SHOTGUN": 2, "CARBINE": 3, "ASSAULT_RIFLE": 3, "DMR": 4, "SNIPER": 4, "SPECIAL": 4},
}
## Буфер посередине окна лута (рейд), клеток: ширина × высота.
const BUFFER_GRID := Vector2i(3, 3)
## Проверка патронов (держать R): сколько держать, с; сколько виден ответ, с; «на глаз» — от какой
## доли магазина какое слово (пустой и полный — отдельно). Точно — у пистолетов и болтовок.
const AMMO_CHECK := {"hold_sec": 0.4, "show_sec": 3.0,
	"words": [[0.85, "почти полный"], [0.6, "больше половины"], [0.4, "половина"], [0.15, "меньше половины"], [0.0, "почти пустой"]],
	# метка на магазине в сетке: полный / пустой видно всегда, остальное — после проверки
	"short": {"полный": "ПОЛН", "почти полный": "~ПОЛН", "больше половины": ">½", "половина": "½",
		"меньше половины": "<½", "почти пустой": "~ПУСТ", "пустой": "ПУСТ"}}
## Поштучно (MagOps): снарядить магазин — с на патрон, разрядить — с на патрон, вынуть плиту из
## жилета — с на плиту. Игровой темп, не армейский норматив: 30 патронов — около 8 с.
const MAG_OPS := {"load_sec": 0.26, "unload_sec": 0.14, "plate_sec": 1.2}
## Ящики и тела — сетка: ширина и сколько рядов минимум по виду (LootContainer.Look; бросок не
## влез — рядов больше, чтобы ничего не терялось).
const LOOT_GRID_W := 6
const LOOT_ROWS := {"NONE": 3, "SAFE": 3, "RACK": 4, "BODY": 4, "BAG": 3, "CRATE": 3}
## ЛЦУ (LaserSight): докуда видна точка, м; её радиус вблизи и прирост на метр дистанции (чтобы
## разглядеть сверху), отсвет точки — сила и радиус, м.
const LASER := {"range_m": 150.0, "dot_radius": 0.012, "dot_grow": 0.0012, "light_energy": 1.2, "light_range": 0.5}
## Брошенный свет: осветительная ракета и химсвет — цвет, сила, радиус, сколько горит, с.
const THROWN_LIGHTS := {
	"flare": {"color": Color(1.0, 0.32, 0.22), "energy": 9.0, "range": 20.0, "sec": 60.0, "shadow": true},
	"chemlight": {"color": Color(0.35, 1.0, 0.45), "energy": 1.0, "range": 9.0, "sec": 600.0, "shadow": true,
		"indirect": 2.6, "blur": 2.5},
}
## Брошенный свет после приземления: медленнее settle_speed м/с дольше settle_sec — замирает
## (не катается, свет не скачет); не позже max_roll_sec после первого касания.
## Наружный свет — одна система (RaidWeather): темно (не день) — горят уличные фонари и заградительные
## огни; днём заградительные зажигаются, когда видимость по туману ниже fog_on_m, и гаснут, только когда
## она поднимется выше fog_off_m (гистерезис — у порога не мигают). fade_sec — плавное включение и
## выключение; fog_change_sec — за сколько туман сгущается / рассеивается; beacon_light_m — дальше
## этого у заградительного огня остаётся только свечение (лампа и ореол), без источника света.
const OUTDOOR_LIGHTS := {"fade_sec": 3.0, "fog_on_m": 300.0, "fog_off_m": 450.0, "fog_change_sec": 30.0,
	"beacon_light_m": 70.0, "beacon_fade_m": 20.0}

## Уличный фонарь (StreetLamp): цвет, сила, дальность и угол конуса, отражённый свет, свечение
## в тумане, яркость рассеивателя; дальше fade_begin м от камеры гаснет, тень — ближе shadow_m.
const STREET_LAMP := {"color": Color(1.0, 0.84, 0.62), "energy": 7.0, "range": 26.0, "angle": 62.0, "indirect": 1.6,
	"fog": 1.2, "lens": 9.0, "fade_begin": 110.0, "shadow_m": 45.0}
## Отражённый от мокрой земли луч фонаря (WetBounce): вклад плёнки и луж в отражение, доля
## отражения в упор (к касательной — до 1), общий множитель яркости, во сколько раз шире конус;
## считается раз в tick с, если фонарь ближе max_cam_m к камере.
const WET_BOUNCE := {"film": 0.35, "puddle": 0.65, "base": 0.08, "energy": 0.9, "spread": 1.35, "tick": 0.05, "max_cam_m": 45.0}
## Ночное окружение (небо — шейдер night_sky, Луна — свет «Sun»): рассеянный свет ровным
## тёмно-холодным цветом (звёзды не светят), свечение — только от очень яркого (диск Луны, маяки),
## объёмный туман слабее (× fog_k).
const NIGHT_ENV := {"ambient_color": Color(0.09, 0.11, 0.16), "glow_threshold": 1.3, "glow_intensity": 0.4, "glow_bloom": 0.0,
	"fog_k": 0.55, "fog_sky": 0.08, "moon_fog": 0.12}
const THROWN_SETTLE := {"settle_speed": 0.35, "settle_sec": 0.25, "max_roll_sec": 2.0, "roll_damp": 9.0}
## Ракета: кто в радиусе горит — виден минимум на столько, м; мародёр ближе FLARE_BLIND_M,
## глядя на неё, целится как только что заметивший (слепит).
const FLARE_LIT_VIEW := 45.0
const FLARE_BLIND_M := 12.0
## Фонарь на оружии в лицо ближе стольких метров — слепит мародёра (целится как только что
## заметивший), как ракета.
const FLASHLIGHT_BLIND_M := 15.0

# --- Арсенал (data/weapons.json, data/armor.json; docs/design/weapons.md) ---
## Износ оружия: разброс × (1 + износ² × spread); задержка за выстрел = (1 − надёжность) ×
## jam_base × (1 + износ² × jam_worn) (износ = (100 − прочность)/100); устранить — clear_sec.
const WEAPON_WEAR := {"spread": 0.8, "jam_base": 0.012, "jam_worn": 25.0, "clear_sec": 0.9}
## Досыпать россыпь в отстёгиваемый магазин (снаряжённых нет) — дольше смены магазина во столько.
## Переключение основной ↔ угловой прицел от первого лица, с (без опускания оружия).
const SIGHT_SWITCH_SEC := 0.22
const RELOAD_TOPUP_K := 1.6
## Изометрия (ПКМ переводит в прицел от первого лица — там выбранный прицел и работает), от бедра:
## угловой коллиматор выбран — разброс × offset_hip (навскидку), крупная оптика — × scope_hip;
## zoom_per_x — на будущее: приближение камеры за кратность.
const ISO_AIM := {"offset_hip": 0.88, "scope_hip": 1.1, "zoom_per_x": 0.035}
## Защита класса брони (0–5): против пробития патрона (pen).
const ARMOR_CLASS_PROT := [0.0, 12.0, 22.0, 34.0, 46.0, 56.0]
## Пробитие: защита = класс × (dur_floor + (1 − dur_floor) × доля прочности); шанс пробить —
## плавная ступень pen в окне ±window вокруг защиты. Пробила — проходит урон × от through_min
## до 1 (на full_over сверх защиты — весь); не пробила — тупая травма (blunt слоя), износ слоя —
## armor_dmg × wear_stopped (пробила — × wear_pen) × износ материала.
const ARMOR := {"dur_floor": 0.55, "window": 10.0, "through_min": 0.6, "full_over": 20.0, "wear_stopped": 1.0, "wear_pen": 0.6}
## Зоны попадания: множитель урона. Голова без шлема или сквозь шлем — насмерть (Health).
const ZONE_DAMAGE := {"thorax": 1.0, "arms": 0.6, "legs": 0.7}
## Высоты зон (доля роста): ниже legs — ноги; руки — дальше arms_w от оси корпуса.
const ZONE_SHAPE := {"legs": 0.5, "arms_w": 0.2}
## Вес: до free_kg — без штрафа; к max_kg — скорость × speed_min, расход выносливости × stamina_max.
const CARRY := {"free_kg": 22.0, "max_kg": 50.0, "speed_min": 0.72, "stamina_max": 1.8}
## Витринное стекло: урон пули по нему = урон × bullet_k (прочность панели 100); треснувшее
## ниже collapse_below — осыпается само через collapse_sec; пуля за стеклом — урон × pass_k;
## звон осколков слышно на noise_m.
const GLASS := {"bullet_k": 1.4, "collapse_below": 0.45, "collapse_sec": [1.2, 3.5], "pass_k": 0.85, "noise_m": 35.0}
## ПНВ: заряда на столько секунд работы за рейд.
const NVG_BATTERY_SEC := 1200.0
## Фонарь мародёра в темноте: сила и дальность луча.
const AI_TORCH_ENERGY := 4.0
const AI_TORCH_RANGE := 24.0
## Фонари ИИ (налобный и на оружии) дальше begin м от камеры плавно гаснут (за length м), тень —
## только ближе shadow м: много мародёров с фонарями ночью не роняют кадр.
const AI_LIGHT_FADE := {"begin": 70.0, "length": 20.0, "shadow": 28.0}
const AI_VIEW_HALF_ANGLE_DEG := 60.0
const AI_VIEW_STANCE_SCALE := {"stand": 1.0, "crouch": 0.7, "prone": 0.4}
## Сколько секунд непрерывной видимости нужно, чтобы заметить (ближе — быстрее).
const AI_NOTICE_SEC := 0.35
## Память о цели после потери из виду, с.
const AI_MEMORY_SEC := 12.0
## Бой: дистанция открытия огня, интервал выстрелов, разброс, урон (старые — для ai_test/сектора).
const AI_ENGAGE_RANGE := 32.0
const AI_FIRE_INTERVAL := 0.75
const AI_SPREAD_DEG := 7.0
const AI_DAMAGE := 9.0
## Оружие мародёров: доля в отряде (weight), магазин, перезарядка (с), интервал выстрелов (с),
## очередь (выстрелов) и пауза между очередями (с), урон за пулю/дробину, дробин, разброс (град),
## дальность боя (м), шум выстрела (м), звук, модель; item/ammo — что выпадает с трупа (ствол и патроны).
## Как ИИ стреляет по классу оружия (само оружие, магазины и патроны — из снаряжения ИИ,
## data/loadouts.json): очередь, пауза между очередями, не чаще interval_min, разброс, дальность
## боя. Урон — от патрона × AI_DAMAGE_K (пробитие брони — как у патрона).
const AI_CLASS := {
	"PISTOL": {"burst": 1, "burst_pause": 0.0, "interval_min": 0.42, "spread": 5.5, "range": 28.0},
	"SMG": {"burst": 4, "burst_pause": 0.6, "interval_min": 0.08, "spread": 5.0, "range": 32.0},
	"SHOTGUN": {"burst": 1, "burst_pause": 0.0, "interval_min": 0.6, "spread": 4.0, "range": 18.0},
	"ASSAULT_RIFLE": {"burst": 3, "burst_pause": 0.75, "interval_min": 0.11, "spread": 4.5, "range": 45.0},
	"CARBINE": {"burst": 3, "burst_pause": 0.7, "interval_min": 0.1, "spread": 4.2, "range": 45.0},
	"DMR": {"burst": 1, "burst_pause": 0.5, "interval_min": 0.9, "spread": 1.4, "range": 70.0},
	"SNIPER": {"burst": 1, "burst_pause": 0.0, "interval_min": 1.7, "spread": 0.9, "range": 80.0},
	"SPECIAL": {"burst": 3, "burst_pause": 0.7, "interval_min": 0.11, "spread": 4.5, "range": 40.0},
}
## Урон пуль ИИ по игроку — доля урона патрона (ИИ стреляет часто и много).
const AI_DAMAGE_K := 0.36
## Сколько ИИ перезаряжается, с: время оружия × это.
const AI_RELOAD_K := 1.1
## Типы мародёров: доля среди всех (weight), снаряжение (loadout — data/loadouts.json: оружие,
## магазины, броня, шлем, гарнитура, аптечки; leader — с этим шансом главарь), скорость ×,
## здоровье ×, память ×, дальность зрения ×, цвет куртки, фигура (масштаб), holds — держит
## позицию: не сближается, патруль у своего поста, ищет глазами, а не ногами (снайпер ходит один).
const AI_ARCHETYPES := {
	"scout": {"name": "Разведчик", "weight": 0.3, "loadout": "scav_poor", "speed": 1.3, "hp": 0.85,
		"memory": 0.5, "view": 1.1, "color": Color(0.46, 0.4, 0.28), "scale": Vector3(0.9, 1.0, 0.9), "holds": false},
	"gunner": {"name": "Штурмовик", "weight": 0.45, "loadout": "scav_standard", "leader": {"chance": 0.1, "loadout": "scav_leader"}, "speed": 1.0, "hp": 1.0,
		"memory": 1.0, "view": 1.0, "color": Color(0.36, 0.2, 0.16), "scale": Vector3(1.0, 1.0, 1.0), "holds": false},
	"heavy": {"name": "Бывалый", "weight": 0.15, "loadout": "scav_veteran", "speed": 0.85, "hp": 1.2,
		"memory": 1.3, "view": 0.95, "color": Color(0.18, 0.22, 0.2), "scale": Vector3(1.18, 1.03, 1.18), "holds": false},
	"sniper": {"name": "Снайпер", "weight": 0.1, "loadout": "scav_sniper", "speed": 0.9, "hp": 0.9,
		"memory": 1.5, "view": 2.2, "color": Color(0.3, 0.33, 0.24), "scale": Vector3(0.95, 1.0, 0.95), "holds": true},
	# третья сторона — не выпадают случайно (weight 0): ставят события и уровень
	# «Периметр» — не толще людей: опасны снаряжением (броня, патроны), меткостью и слаженностью
	"pmc": {"name": "ЧВК «Периметр»", "weight": 0.0, "loadout": "perimeter_rifleman", "speed": 1.05, "hp": 1.0,
		"memory": 1.4, "view": 1.2, "color": Color(0.1, 0.12, 0.15), "scale": Vector3(1.08, 1.02, 1.08), "holds": false,
		"faction": "pmc", "loots": false},
	"resident": {"name": "Жилец", "weight": 0.0, "loadout": "civilian", "speed": 0.95, "hp": 1.0,
		"memory": 1.0, "view": 0.9, "color": Color(0.55, 0.48, 0.38), "scale": Vector3(0.96, 0.98, 0.96), "holds": false,
		"faction": "resident", "loots": false},
}
## Кто кому враг (фракции ИИ). Игрок — враг мародёрам и ЧВК; жильцам — только если к ним полез
## (зашёл к ним, стрелял рядом, попал) или группа враждебная с самого начала.
const AI_HOSTILE := {"marauder": ["pmc", "resident"], "pmc": ["marauder", "resident"], "resident": ["marauder", "pmc"]}
## Жильцы: сколько групп, по сколько, доля враждебных сразу; ближе стольких метров к их
## магазину — «полез к ним»; враждебные стреляют с такого расстояния.
const RESIDENTS := {"groups": [1, 2], "size": [2, 3], "hostile_share": 0.3, "trespass_m": 7.0, "hostile_m": 22.0}
## События рейда (RaidEvents): шансы и когда (от и до, с). Отключение / авария генератора — только
## если свет был; сирена: сколько воет, докуда слышно, сколько отключать у пульта, с; задание по рации: какие вещи, во сколько
## раз дороже цены платит Михалыч; починка генератора, с.
const RAID_EVENTS := {
	"outage_chance": 0.25, "outage_at": [180.0, 720.0],
	"generator_chance": 0.25, "generator_at": [180.0, 720.0], "repair_sec": 8.0,
	"drop_chance": 0.35, "drop_at": [240.0, 780.0], "drop_noise_m": 160.0, "drop_smoke_sec": 90.0,
	"pmc_chance": 0.35, "pmc_at": [300.0, 900.0],
	"alarm_shops": 2, "alarm_sec": 120.0, "alarm_noise_m": 70.0, "alarm_off_sec": 3.0,
	"radio_items": ["laptop", "gpu", "server_drive", "camera", "documents", "diamond_ring"], "radio_at": [120.0, 360.0], "radio_mult": 3,
}
## Генератор ТЦ (MallGenerator): гул работающего (громкость, дБ; 1:1 до, слышно до, м), лязг
## ремонта раз в clank_sec — мародёры слышат на clank_noise_m; мигание лампы сломанного, Гц;
## проход вокруг корпуса без пропсов, м.
const MALL_GENERATOR := {"hum_db": -6.0, "hum_unit_m": 5.0, "hum_max_m": 40.0, "clank_sec": 1.2, "clank_noise_m": 45.0, "blink_hz": 1.5, "keepout_m": 1.2}
## ЧВК: сколько в группе.
const PMC_SQUAD := 4
## Раненый мародёр кричит — товарищи в радиусе, м, идут спасать: тащат за укрытие (до
## AI_DRAG_COVER_M), поднимают за AI_REVIVE_SEC. Лёжа стреляет из пистолета.
const AI_RESCUE_RADIUS := 28.0
const AI_DRAG_COVER_M := 12.0
const AI_DRAG_SPEED := 1.4
const AI_REVIVE_SEC := 6.0
## Добивают лежащего игрока, только если другие не стреляют столько секунд (лежащий сам
## стреляет — его и добивают).
const AI_FINISH_QUIET_SEC := 4.0
## Мародёры тоже ищут припасы: ведущий отряда идёт к ближайшему неразграбленному контейнеру
## (не дальше AI_LOOT_RANGE, не занятому другим отрядом — метка на AI_LOOT_CLAIM_SEC), роется
## (обыск контейнера × AI_LOOT_SEARCH_MULT, не меньше AI_LOOT_SEARCH_MIN, слышно), забирает самое
## ценное (до AI_LOOT_TAKE записей, всего в сумке до AI_LOOT_PACK_MAX) и идёт дальше. Сумка
## выпадает с трупа.
const AI_LOOT_RANGE := 60.0
const AI_LOOT_CLAIM_SEC := 90.0
const AI_LOOT_SEARCH_MULT := 4.0
const AI_LOOT_SEARCH_MIN := 3.0
const AI_LOOT_TAKE := 2
const AI_LOOT_PACK_MAX := 6
## Роли отрядов в бою (по порядку вступления в бой у одной цели, в радиусе AI_ROLE_RADIUS):
## штурм (давит, гранаты), обход (широко, на AI_ROLE_FLANK_OFFSET в сторону), прикрытие
## (позиция с обзором цели в AI_OVERWATCH_DIST, держит место огнём). Роль гаснет, когда отряд
## AI_ROLE_FORGET_SEC не в бою.
const AI_ROLE_RADIUS := 60.0
const AI_ROLE_FLANK_OFFSET := 20.0
const AI_OVERWATCH_DIST := [15.0, 35.0]
const AI_ROLE_FORGET_SEC := 25.0
## Гранаты мародёров: дальность броска (от и до, м), перезарядка, с, сколько у каждого, цель не
## видна хотя бы столько, с; своих ближе AI_GRENADE_SAFE_M к точке — не кидает.
const AI_GRENADE := {"range": [8.0, 22.0], "cooldown": 18.0, "count": 1, "min_unseen": 1.5, "safe_m": 7.0}
## Держит позицию: патрульные точки — не дальше стольких метров от поста, м.
const AI_HOLD_PATROL_R := 12.0
## Реакция на попадание: сколько секунд «ведёт» (скорость ×, разброс ×), задержка следующего выстрела, с.
const AI_HIT_STAGGER_SEC := 0.45
const AI_HIT_STAGGER_SPEED := 0.3
const AI_HIT_STAGGER_SPREAD := 1.8
const AI_HIT_FLINCH_DELAY := 0.3
## Точность: только что замеченная цель — разброс × AI_AIM_COLD, за AI_AIM_SETTLE_SEC сходится к 1.
## Цель бежит — × AI_TARGET_MOVING; сам на ходу — × AI_SELF_MOVING.
const AI_AIM_COLD := 2.4
const AI_AIM_SETTLE_SEC := 1.4
const AI_TARGET_MOVING := 1.5
const AI_SELF_MOVING := 1.7
## Окрик «контакт»: докуда слышно, м, и как часто повторять, пока видит цель, с.
const AI_CALLOUT_RADIUS := 32.0
const AI_CALLOUT_EVERY := 3.0
## Укрытие: поиск в радиусе, м; сколько сидеть, прежде чем выглянуть, и сколько стрелять, выглянув, с.
const AI_COVER_RADIUS := 10.0
const AI_COVER_HIDE := [0.8, 1.8]
const AI_COVER_PEEK := [1.2, 2.4]
## В укрытие — после попадания или если рядом свистят пули (слышал выстрел цели ближе, м).
const AI_SUPPRESS_RADIUS := 12.0
## Раненый (меньше этой доли HP) без товарищей рядом — отходит в дальнее укрытие.
const AI_RETREAT_HP := 0.35
const AI_RETREAT_HOLD := [6.0, 10.0]
## Обход: на сколько метров в сторону от цели заходит второй в отряде.
const AI_FLANK_OFFSET := 11.0
## Поиск после потери цели: сколько точек осмотреть вокруг последней известной, до какого радиуса, м
## (прочёсывание: от ближних к дальним, дугой; точки, которые уже смотрит другой, — пропускаются
## ближе AI_SEARCH_CLAIM_M). После проверки шума — AI_INVESTIGATE_SEARCH точек.
const AI_SEARCH_POINTS := 6
const AI_SEARCH_RADIUS := 18.0
const AI_SEARCH_CLAIM_M := 5.0
const AI_INVESTIGATE_SEARCH := 2
## Попадание от невидимого стрелка: направление угадывается с ошибкой (град), дальность — ± доля.
const AI_HIT_DIR_ERR_DEG := 15.0
const AI_HIT_DIST_ERR := 0.3
## Продвижение перебежками к цели, которую не видно: шаг от и до, м; ближе AI_ADVANCE_MIN_DIST — идёт прямо.
const AI_ADVANCE_STEP := [5.0, 12.0]
const AI_ADVANCE_MIN_DIST := 10.0
## Не толпиться: куда идёт другой мародёр ближе стольких метров — туда не идём, точка сдвигается
## на AI_SPREAD_RADIUS в сторону. Шум, который уже проверяет другой отряд (AI_INVESTIGATE_SHARE_M
## от него), не проверяем — если только он не ближе AI_INVESTIGATE_NEAR.
const AI_SPREAD_CLAIM_M := 2.5
const AI_SPREAD_RADIUS := [2.5, 6.0]
const AI_INVESTIGATE_SHARE_M := 12.0
const AI_INVESTIGATE_NEAR := 15.0
## Слух: падение тела товарища слышно в радиусе, м.
const AI_DEATH_NOISE := 22.0
## Строй патруля: ведомые держатся на таком расстоянии за ведущим, м.
const AI_FOLLOW_DIST := 2.6
## Отряды: сколько в отряде (от и до).
const AI_SQUAD_SIZE := [1, 3]
## Патруль: пауза на точке, с.
const AI_PATROL_PAUSE := [1.5, 4.0]
## Расследование: сколько стоять на месте шума, прежде чем вернуться к патрулю, с.
const AI_INVESTIGATE_LINGER := 5.0
