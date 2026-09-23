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
## Щелчок рубильника слышно далеко — мародёры идут проверить, м.
const NOISE_SWITCH := 35.0
## Рюкзак: вместимость в ячейках (размеры предметов — data/items.json).
const BACKPACK_CELLS := 30
## Сетка рюкзака, ш × в (ячеек — BACKPACK_CELLS).
const BACKPACK_GRID := Vector2i(6, 5)
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
const START_STASH := [["w_pistol", 1], ["w_rifle", 1], ["ammo_9x19", 100], ["ammo_545", 120],
	["bandage", 4], ["painkillers", 2], ["vest_light", 1], ["helmet", 1], ["grenade", 2]]
## Торговец продаёт дороже цены предмета и покупает дешевле (с учётом износа брони).
const TRADER_BUY_MULT := 1.25
const TRADER_SELL_MULT := 0.55
## Доверие торговца: за каждую эвакуацию и сверху — если вынес на сумму не меньше порога, ₽.
## Пороги доверия и цены маршрутов на этажи — в data/floors.json.
const TRUST_PER_EXTRACTION := 1
## Уровни доверия: очки доверия, с которых начинается уровень 1, 2, 3, 4 (товары, задания, модули).
const TRUST_LEVELS := [0, 3, 6, 10]
## Модули убежища (data/hideout.json): с какого уровня верстака ставится обвес в слот;
## сетка защищённого кармана по уровню (0 — кармана нет); строк тайника по уровню;
## сколько заданий одновременно — без рации / с рацией.
const WORKBENCH_SLOT_LEVEL := {"muzzle": 1, "grip": 1, "stock": 1, "mag": 1, "optic": 2, "tac": 2, "bipod": 2}
const POCKET_GRIDS := [Vector2i(0, 0), Vector2i(2, 2), Vector2i(3, 3)]
const STASH_ROWS := [30, 40, 50]
const MISSION_SLOTS := [1, 3]
const TRUST_BONUS := 1
const TRUST_BONUS_VALUE := 60000
## Сцены: убежище (старт игры, между рейдами) и рейд.
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
const MARAUDER_HP := 120.0

# --- Пистолет игрока ---
const PISTOL := {"damage": 22.0, "interval": 0.22, "mag": 8, "reload": 1.8, "spread_deg": 1.4, "range_m": 60.0, "noise_m": 60.0}

# --- Оружие игрока ---
## auto — зажим ЛКМ стреляет очередью; interval — с между выстрелами (у болтовки/помпы — с
## передёргиванием); pellets — сколько лучей за выстрел (дробь); shake — тряска камеры;
## sound/reload_sound/cycle_sound — виды звука в Audio.
## Отдача (натуральная): kick — подброс ствола за выстрел, рад; kick_h — увод вбок (случайно ±,
## со сдвигом kick_bias: плюс — вправо, у АК ствол уходит вправо-вверх); recover — какую долю
## подброса руки возвращают сами (остальное остаётся — очередь «ползёт», её тянут мышью вниз).
const WEAPONS := {
	"pistol": {"name": "Пистолет", "damage": 22.0, "interval": 0.16, "mag": 12, "reload": 1.6, "spread_deg": 1.4,
		"pellets": 1, "auto": false, "range_m": 60.0, "noise_m": 60.0, "kick": 0.05, "kick_h": 0.014, "kick_bias": 0.2, "recover": 0.8, "shake": 0.12,
		"sound": "shot_pistol", "reload_sound": "reload_pistol", "cycle_sound": "", "ergo": 72},
	"rifle": {"name": "Автомат", "damage": 19.0, "interval": 0.1, "mag": 30, "reload": 2.4, "spread_deg": 2.0,
		"pellets": 1, "auto": true, "range_m": 90.0, "noise_m": 80.0, "kick": 0.026, "kick_h": 0.014, "kick_bias": 0.35, "recover": 0.3, "shake": 0.09,
		"sound": "shot_rifle", "reload_sound": "reload_rifle", "cycle_sound": "", "ergo": 44},
	"shotgun": {"name": "Дробовик", "damage": 12.0, "interval": 0.8, "mag": 6, "reload": 3.0, "spread_deg": 5.5,
		"pellets": 8, "auto": false, "range_m": 35.0, "noise_m": 75.0, "kick": 0.09, "kick_h": 0.022, "kick_bias": 0.1, "recover": 0.6, "shake": 0.32,
		"sound": "shot_shotgun", "reload_sound": "reload_shotgun", "cycle_sound": "reload_shotgun", "ergo": 40},
	"bolt": {"name": "Винтовка", "damage": 95.0, "interval": 1.3, "mag": 5, "reload": 3.2, "spread_deg": 1.6,
		"pellets": 1, "auto": false, "range_m": 160.0, "noise_m": 120.0, "kick": 0.08, "kick_h": 0.012, "kick_bias": 0.0, "recover": 0.75, "shake": 0.35,
		"sound": "shot_bolt", "reload_sound": "reload_rifle", "cycle_sound": "bolt", "ergo": 30, "zoom": 6.0},
}
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
## Порядок на клавишах 1–4.
const WEAPON_ORDER := ["pistol", "rifle", "shotgun", "bolt"]

# --- Прицел от первого лица (ПКМ) ---
## Разброс в прицеле — доля от стрельбы с бедра; у болтовки через оптику почти ноль.
const ADS_SPREAD := {"pistol": 0.5, "rifle": 0.35, "shotgun": 0.85, "bolt": 0.03}
## Поле зрения в прицеле, град; у болтовки — оптика (вид через прицельную сетку, без модели).
const ADS_FOV := {"pistol": 62.0, "rifle": 56.0, "shotgun": 62.0, "bolt": 16.0}
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

# --- Мародёр ---
## Кольцо Ø400 (3 сектора) — в разы больше старого сектора, мародёров больше.
const MARAUDER_COUNT := 12
const MARAUDER_WALK := 1.5
const MARAUDER_RUN := 3.4
## Ближе этого до точки спавна игрока мародёры не появляются, м.
const MARAUDER_SPAWN_MIN_DIST := 28.0
## Зрение: дальность, полуугол конуса, и во сколько раз дальность меньше для сидящего/лежащего.
const AI_VIEW_DISTANCE := 30.0
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
## дальность боя (м), шум выстрела (м), звук, модель.
const AI_WEAPONS := {
	"pistol": {"weight": 0.45, "mag": 12, "reload": 2.0, "interval": 0.42, "burst": 1, "burst_pause": 0.0,
		"damage": 9.0, "pellets": 1, "spread": 5.5, "range": 28.0, "noise_m": 45.0, "sound": "shot_ai", "model": "pistol"},
	"rifle": {"weight": 0.4, "mag": 30, "reload": 2.6, "interval": 0.11, "burst": 3, "burst_pause": 0.75,
		"damage": 11.0, "pellets": 1, "spread": 4.5, "range": 45.0, "noise_m": 80.0, "sound": "shot_rifle", "model": "rifle"},
	"shotgun": {"weight": 0.15, "mag": 6, "reload": 3.2, "interval": 0.95, "burst": 1, "burst_pause": 0.0,
		"damage": 7.0, "pellets": 8, "spread": 4.0, "range": 18.0, "noise_m": 90.0, "sound": "shot_shotgun", "model": "shotgun"},
}
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
## Поиск после потери цели: сколько точек осмотреть вокруг последней известной, в радиусе, м.
const AI_SEARCH_POINTS := 3
const AI_SEARCH_RADIUS := 9.0
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
