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
## Вырез стен у камеры: доли дистанции камеры, ближе near — стена невидима, дальше far — целая.
## Пол на дистанции ~0.85 (высота камеры), стена под камерой ~0.6 — попадает в вырез, игрок (1.0) — нет.
const CAMERA_CUTAWAY_NEAR := 0.62
const CAMERA_CUTAWAY_FAR := 0.96

# --- Свет и атмосфера ---
const SUN_ENERGY := 1.6
const SUN_ELEVATION_DEG := 34.0
const SUN_AZIMUTH_DEG := -140.0
const AMBIENT_ENERGY := 0.35
const FOG_DENSITY := 0.005

# --- Двери ---
## Скорость распахивания створки (чем больше, тем резче), 1/с.
const DOOR_SWING_SPEED := 7.0

# --- Здоровье ---
const PLAYER_HP := 100.0
const MARAUDER_HP := 60.0

# --- Пистолет игрока ---
const PISTOL := {"damage": 22.0, "interval": 0.22, "mag": 8, "reload": 1.8, "spread_deg": 1.4, "range_m": 60.0, "noise_m": 60.0}

# --- Шум игрока: радиус слышимости шагов по стойке, м ---
const NOISE_STEP := {"stand": 7.0, "sprint": 14.0, "crouch": 3.0, "prone": 1.5}
const NOISE_STEP_INTERVAL := 0.45

# --- Мародёр ---
const MARAUDER_COUNT := 4
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
## Бой: дистанция открытия огня, интервал выстрелов, разброс, урон.
const AI_ENGAGE_RANGE := 32.0
const AI_FIRE_INTERVAL := 0.75
const AI_SPREAD_DEG := 7.0
const AI_DAMAGE := 9.0
## Патруль: пауза на точке, с.
const AI_PATROL_PAUSE := [1.5, 4.0]
## Расследование: сколько стоять на месте шума, прежде чем вернуться к патрулю, с.
const AI_INVESTIGATE_LINGER := 5.0
