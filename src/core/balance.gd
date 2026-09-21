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
const CAMERA_DISTANCE := 22.0
const CAMERA_FOV := 32.0
const CAMERA_ZOOM_MIN := 12.0
const CAMERA_ZOOM_MAX := 34.0
const CAMERA_ZOOM_STEP := 2.0
## Камера смещается к курсору: доля расстояния до курсора и предел, м.
const CAMERA_CURSOR_LEAD := 0.28
const CAMERA_CURSOR_LEAD_MAX := 5.0
const CAMERA_FOLLOW_SMOOTH := 8.0

# --- Свет и атмосфера ---
const SUN_ENERGY := 1.6
const SUN_ELEVATION_DEG := 34.0
const SUN_AZIMUTH_DEG := -140.0
const AMBIENT_ENERGY := 0.35
const FOG_DENSITY := 0.005

# --- Зрение AI ---
const AI_VIEW_DISTANCE := 28.0
const AI_VIEW_HALF_ANGLE_DEG := 60.0
const AI_HEAR_GUNSHOT_M := 60.0
const AI_HEAR_STEP_M := 8.0
