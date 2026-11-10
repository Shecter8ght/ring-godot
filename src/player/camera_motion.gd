class_name CameraMotion
extends RefCounted
## Движение камеры от первого лица — вес тела поверх взгляда мышью: покачивание в темп шагов, удар
## стопы, инерция головы на разгоне и остановке, едва заметный крен на шаге вбок, проседание при
## приземлении. Только вид своего игрока. CameraRig прибавляет pitch / yaw / roll к взгляду (пуля
## в прицеле идёт по той же оси, что видна) и offset — к глазу; мышь, отдача, раскачка и люфт
## оружия считаются отдельно и сюда не входят. Каждый кадр всё собирается заново около нуля:
## смещения не копятся, стоишь — камера ровно в глазах. Числа — Balance.CAMERA_MOTION.
##
## Фаза покачивания — фаза шагов (Footsteps.stride_phase): своя частота у камеры не заводится, иначе
## шаги и покачивание разъезжаются. Камера подстраивается к фазе шагов плавно (lock_rate): скачок фазы
## у шагов (встал, прыгнул) не даёт скачка камеры.

## Поворот камеры от движения, рад: кивок (плюс — вверх), поворот (плюс — влево), крен (плюс — влево).
var pitch: float = 0.0
var yaw: float = 0.0
var roll: float = 0.0
## Сдвиг глаза в осях камеры, м (x — вправо, y — вверх, z — назад).
var offset: Vector3 = Vector3.ZERO
## Покачивание оружия в руках относительно глаз, м (оси камеры), в той же фазе шагов (Balance.WEAPON_BOB).
var weapon_bob: Vector3 = Vector3.ZERO
## То же для оружия в прицеле (Balance.WEAPON_BOB_ADS): сдвиг, м, и завал, рад. Умножить на долю вскидки и ползунок.
var weapon_bob_ads: Vector3 = Vector3.ZERO
var weapon_roll_ads: float = 0.0

## Фаза пары шагов: 0 — удар левой, 0.5 — правой.
var _phase: float = 0.0
## Доля размаха шага (0 — стоит, 1 — полный шаг) и доля бега — плавно за скоростью.
var _amp: float = 0.0
var _sprint: float = 0.0
var _stance_k: float = 1.0
var _seen_steps: int = -1
## Удар стопы: x — проседание, м; y — кивок, рад (затухающая пружина) и их скорости.
var _impact: Vector2 = Vector2.ZERO
var _impact_v: Vector2 = Vector2.ZERO
## Инерция головы: x — вперёд, y — вправо, м, и скорости.
var _lag: Vector2 = Vector2.ZERO
var _lag_v: Vector2 = Vector2.ZERO
var _prev_vel: Vector2 = Vector2.ZERO
var _has_prev: bool = false
## Крен на шаге вбок, рад.
var _strafe: float = 0.0
var _was_ground: bool = true
## Самая большая скорость падения за прыжок, м/с.
var _fall: float = 0.0
var _idle_t: float = 0.0
var _land: Vector2 = Vector2.ZERO
var _land_v: Vector2 = Vector2.ZERO
var _air: Vector2 = Vector2.ZERO
var _weapon_phase_shift: float = 0.0
var _settings_revision: int = -1
var _head_scale: float = 1.0
var _jump_scale: float = 1.0
var _idle_scale: float = 1.0
var _walk_angle: float = 0.0
var _run_angle: float = 0.0
var weapon_rate: float = 1.0


## Новый вид из глаз (вошёл в первое лицо, сменилась цель) — без остатков прошлых пружин.
func reset() -> void:
	pitch = 0.0
	yaw = 0.0
	roll = 0.0
	offset = Vector3.ZERO
	weapon_bob = Vector3.ZERO
	weapon_bob_ads = Vector3.ZERO
	weapon_roll_ads = 0.0
	_amp = 0.0
	_sprint = 0.0
	_seen_steps = -1
	_impact = Vector2.ZERO
	_impact_v = Vector2.ZERO
	_lag = Vector2.ZERO
	_lag_v = Vector2.ZERO
	_has_prev = false
	_strafe = 0.0
	_was_ground = true
	_fall = 0.0
	_land = Vector2.ZERO
	_land_v = Vector2.ZERO
	_air = Vector2.ZERO
	_weapon_phase_shift = 0.0


## aim_t — доля вскидки к глазам (0 — у бедра, 1 — в прицеле); look_yaw — курс взгляда мышью, рад.
func update(pl: Player, delta: float, aim_t: float, look_yaw: float) -> void:
	var cfg: Dictionary = Balance.CAMERA_MOTION
	_read_tuning()
	var fs: Footsteps = pl.get_node_or_null("Footsteps") as Footsteps
	var vel := Vector2(pl.velocity.x, pl.velocity.z)
	# оси взгляда по земле: вперёд и вправо (камера смотрит по −Z, курс от +Z)
	var fwd := Vector2(sin(look_yaw), cos(look_yaw))
	var right := Vector2(-cos(look_yaw), sin(look_yaw))
	var ground: bool = fs.on_ground if fs else not pl.airborne
	var speed: float = vel.length() if ground else 0.0
	var walk_k := clampf(speed / Balance.PLAYER_WALK_SPEED, 0.0, 1.0)
	var sprint_k := clampf((speed - Balance.PLAYER_WALK_SPEED) / (Balance.PLAYER_SPRINT_SPEED - Balance.PLAYER_WALK_SPEED), 0.0, 1.0)
	var follow := 1.0 - exp(-float(cfg.amp_rate) * delta)
	_amp = lerpf(_amp, walk_k, follow)
	_sprint = lerpf(_sprint, sprint_k, follow)
	_stance_k = lerpf(_stance_k, float((cfg.stance as Dictionary).get(pl.stance_key(), 1.0)), follow)
	var size := _amp * _stance_k
	var step_rate: float = 0.0
	if fs:
		# своя скорость фазы — от темпа шагов; ошибку к фазе шагов догоняем плавно
		step_rate = 0.5 / fs.interval() if fs.walking() else 0.0
		var miss := wrapf(fs.stride_phase() - _phase, -0.5, 0.5)
		_phase = fposmod(_phase + delta * step_rate + miss * (1.0 - exp(-float(cfg.lock_rate) * delta)), 1.0)
		if _seen_steps >= 0 and fs.steps_taken != _seen_steps:
			# удар стопы — в тот же кадр, что и звук шага
			var dip := lerpf(float(cfg.impact_walk_m), float(cfg.impact_sprint_m), _sprint) * size
			var nod := deg_to_rad(lerpf(float(cfg.impact_walk_deg), float(cfg.impact_sprint_deg), _sprint)) * size
			_impact_v -= Vector2(dip, nod) * _kick(float(cfg.impact_hz), float(cfg.impact_damp))
		_seen_steps = fs.steps_taken
	# приземление: тем глубже, чем быстрее падал
	if not ground:
		_fall = maxf(_fall, -pl.velocity.y)
	elif not _was_ground:
		var land := minf(_fall * float(cfg.land_m), float(cfg.land_max_m)) * _stance_k
		var nod := land * deg_to_rad(float(cfg.land_nod_deg_cm)) * 100.0
		_land_v -= Vector2(land, nod) * _kick(float(cfg.impact_hz), float(cfg.impact_damp))
		_fall = 0.0
	_was_ground = ground
	var jump_speed: float = clampf(pl.velocity.y, -float(Balance.JUMP.speed), float(Balance.JUMP.speed)) if pl.airborne and not pl.on_ladder else 0.0
	var air_target: Vector2 = -Vector2(float(cfg.air_m), deg_to_rad(float(cfg.air_deg))) * jump_speed
	_air = _air.lerp(air_target, 1.0 - exp(-float(cfg.air_follow) * delta))
	# инерция: резкая смена скорости тела — голова отстаёт на разгоне и уходит вперёд на остановке
	if _has_prev:
		var dv := vel - _prev_vel
		var push := float(cfg.inertia_m) * _kick(float(cfg.inertia_hz), float(cfg.inertia_damp)) * _stance_k
		_lag_v -= Vector2(dv.dot(fwd), dv.dot(right)) * push
	_prev_vel = vel
	_has_prev = true
	# шаг вбок — лёгкий крен в сторону движения
	var side_speed: float = vel.dot(right) if ground else 0.0
	_strafe = lerpf(_strafe, -side_speed * deg_to_rad(float(cfg.strafe_roll_deg)) * _stance_k,
		1.0 - exp(-float(cfg.strafe_rate) * delta))
	_springs(cfg, delta)
	# покачивание: ниже всего — сразу после удара стопы, выше всего — посреди шага; вбок — к опорной ноге
	var walk: Dictionary = cfg.walk
	var run: Dictionary = cfg.sprint
	var step_phase := fposmod(_phase * 2.0, 1.0)
	var c := cos(TAU * (step_phase - float(cfg.low)))
	var s := sin(TAU * _phase)
	var up := lerpf(float(walk.up_m), float(run.up_m), _sprint) * size
	var side := lerpf(float(walk.side_m), float(run.side_m), _sprint) * size
	var bob_roll := deg_to_rad(lerpf(float(walk.roll_deg), float(run.roll_deg), _sprint)) * size
	var bob_pitch := deg_to_rad(lerpf(float(walk.pitch_deg), float(run.pitch_deg), _sprint)) * size
	var bob_yaw := deg_to_rad(lerpf(float(walk.yaw_deg), float(run.yaw_deg), _sprint)) * size
	var pitch_per_m := deg_to_rad(float(cfg.inertia_pitch_deg_cm)) * 100.0
	var roll_per_m := deg_to_rad(float(cfg.inertia_roll_deg_cm)) * 100.0
	# общий множитель и ползунок игрока; в прицеле — почти ничего (точка прицеливания стоит)
	var k := float(Balance.CAMERA_MOTION_INTENSITY) * Settings.camera_motion
	var kp := k * lerpf(1.0, float(cfg.ads_pos_k), aim_t)
	var kr := k * lerpf(1.0, float(cfg.ads_rot_k), aim_t)
	var jump: Vector2 = (_land + _air) * _jump_scale
	offset = (Vector3(-side * s + _lag.y, -up * c + _impact.x, -_lag.x) * _head_scale + Vector3.UP * jump.x) * kp
	pitch = ((-bob_pitch * c + _impact.y - _lag.x * pitch_per_m) * _head_scale + jump.y) * kr
	yaw = bob_yaw * s * kr * _head_scale
	roll = (bob_roll * s + _strafe - _lag.y * roll_per_m) * kr * _head_scale
	_weapon_phase_shift = wrapf(_weapon_phase_shift + delta * step_rate * (weapon_rate - 1.0), -0.5, 0.5)
	if is_equal_approx(weapon_rate, 1.0):
		_weapon_phase_shift = lerpf(_weapon_phase_shift, 0.0, follow)
	_weapon(cfg, delta, size, _phase + _weapon_phase_shift)


func _read_tuning() -> void:
	if _settings_revision == LabTuning.revision:
		return
	_settings_revision = LabTuning.revision
	_head_scale = Balance.lab_number("motion", "head")
	_jump_scale = Balance.lab_number("motion", "jump")
	_idle_scale = Balance.lab_number("motion", "idle_amp")
	_walk_angle = deg_to_rad(Balance.lab_number("motion", "walk_angle"))
	_run_angle = deg_to_rad(Balance.lab_number("motion", "run_angle"))
	weapon_rate = Balance.lab_number("motion", "weapon_speed")


func idle_sway_scale() -> float:
	return lerpf(_idle_scale, 1.0, _amp)


## Оружие у бедра: в покое — медленно (как раньше), на ходу — в темп шагов, руки чуть позже головы.
func _weapon(cfg: Dictionary, delta: float, size: float, weapon_phase: float) -> void:
	var wb: Dictionary = Balance.WEAPON_BOB
	_idle_t += delta * float(wb.idle_rate) * weapon_rate
	var idle := Vector3(sin(_idle_t * 0.5) * float(wb.horizontal), absf(sin(_idle_t)) * float(wb.idle_vertical), 0.0)
	var direction: float = lerpf(_walk_angle, _run_angle, _sprint)
	var low: float = float(cfg.low)
	weapon_bob = idle * (1.0 - _amp) * _idle_scale + _stride_bob(wb, weapon_phase, low).rotated(Vector3.BACK, direction) * size
	var ab: Dictionary = Balance.WEAPON_BOB_ADS
	weapon_bob_ads = _stride_bob(ab, weapon_phase, low).rotated(Vector3.BACK, direction) * size
	weapon_roll_ads = deg_to_rad(float(ab.roll_deg)) * size * sin(TAU * (weapon_phase - float(ab.lag) * 0.5))


func _stride_bob(spec: Dictionary, phase: float, low: float) -> Vector3:
	var lag: float = float(spec.lag)
	var side: float = lerpf(float(spec.walk_side), float(spec.sprint_side), _sprint)
	var vertical: float = lerpf(float(spec.walk_vertical), float(spec.sprint_vertical), _sprint)
	return Vector3(side * sin(TAU * (phase - lag * 0.5)), -vertical * 0.5 * cos(TAU * (phase * 2.0 - low - lag)), 0.0)


## Пружины удара стопы и инерции — мелкими шагами (одинаково при любой частоте кадров).
func _springs(cfg: Dictionary, delta: float) -> void:
	var wi := TAU * float(cfg.impact_hz)
	var zi := float(cfg.impact_damp)
	var wl := TAU * float(cfg.inertia_hz)
	var zl := float(cfg.inertia_damp)
	var steps: int = clampi(ceili(delta / 0.004), 1, 16)
	var h: float = delta / float(steps)
	for i in steps:
		_impact_v += (-wi * wi * _impact - 2.0 * zi * wi * _impact_v) * h
		_impact += _impact_v * h
		_land_v += (-wi * wi * _land - 2.0 * zi * wi * _land_v) * h
		_land += _land_v * h
		_lag_v += (-wl * wl * _lag - 2.0 * zl * wl * _lag_v) * h
		_lag += _lag_v * h
	var limit := float(cfg.inertia_max_m)
	if _lag.length() > limit:
		_lag = _lag.normalized() * limit
		_lag_v *= 0.5


## Какую скорость дать пружине (частота hz, демпфирование damp < 1), чтобы она отошла на 1 м:
## толчок v0 даёт наибольший отход v0 / ω · e^(−ζ/√(1−ζ²) · atan(√(1−ζ²)/ζ)).
static func _kick(hz: float, damp: float) -> float:
	var w := TAU * hz
	var z := clampf(damp, 0.05, 0.95)
	var r := sqrt(1.0 - z * z)
	return w / exp(-z / r * atan(r / z))
