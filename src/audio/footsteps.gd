class_name Footsteps
extends Node
## Шаги — звук у каждого peer: по перемещению родителя (своего игрока, чужого — по синхронизации,
## мародёра — тоже), поэтому в коопе слышно и напарника, и мародёров, которых считает хост.
## Темп — от скорости (Balance.STEP_*), бег — отдельными записями, поверхность — под ногами
## (Audio.step: плитка/бетон, асфальт, металл, снег), левая/правая — источник у соответствующей стопы.
## Шум для слуха AI сюда не относится — его шлёт Player._footsteps (только свой игрок).
## У своего игрока по этой же фазе качается камера и оружие в руках (CameraMotion: stride_phase,
## steps_taken) — шаг слышен ровно тогда, когда камера проседает.

## () -> float: насколько тише/громче шаг сейчас (присел, лёг), дБ. Пусто — 0.
var loud_db: Callable
## () -> String: особое движение игрока (ползком / вприсядку); пусто — обычный шаг по поверхности.
var movement_kind: Callable
## Игрок сообщает состояние пола, в том числе по сети: в воздухе шагов нет.
var grounded: Callable
## На лестнице, при ползании раненого и после смерти шаги не проигрываются.
var can_step: Callable
var _was_airborne: bool = false
## Мародёр: тяжёлые ботинки — ниже и чуть громче.
var ai: bool = false
## Корпус поворачивается отдельно от корневого узла персонажа. Его +Z направлена вперёд.
var body: Node3D

## () -> float: скорость по земле, м/с, если её знает сам персонаж (свой игрок — по физике, без
## ступенек кадра); пусто или меньше нуля — по перемещению родителя.
var speed_source: Callable
## Сколько шагов сделано: камера (CameraMotion) по нему узнаёт удар стопы в тот же кадр, что и звук.
var steps_taken: int = 0
## На полу ли сейчас (в воздухе и при перелезании шагов нет).
var on_ground: bool = true

var _last: Vector3
## Доля пути до следующего шага: 1 — шаг сейчас. Идёт непрерывно — от неё же фаза камеры.
var _phase: float = 1.0
var _interval: float = 0.75
var _walking: bool = false
var _speed: float = 0.0
## Какой ногой был последний шаг.
var _left: bool = false
var _local_steps: bool = false
var _timing_revision: int = -1
var _walk_scale: float = 1.0
var _run_scale: float = 1.0
var _custom_start: bool = false
var _start_sec: float = Balance.STEP_START_SEC
var _start_left: float = 0.0


func _ready() -> void:
	var actor: Node3D = get_parent() as Node3D
	_last = actor.global_position
	_local_steps = actor.is_in_group("players") and bool(actor.call("is_local"))


## Фаза пары шагов для камеры и оружия в руках: 0 — удар левой, 0.5 — удар правой, 1 — снова левой.
func stride_phase() -> float:
	return (minf(_phase, 1.0) + (0.0 if _left else 1.0)) * 0.5


## Сколько секунд сейчас между шагами (темп от скорости).
func interval() -> float:
	return _interval


## Идёт ли (фаза шагов движется); стоит, в воздухе — нет.
func walking() -> bool:
	return _walking


func _process(delta: float) -> void:
	if delta <= 0.0:
		return
	var pos := (get_parent() as Node3D).global_position
	var travel := Vector3(pos.x - _last.x, 0.0, pos.z - _last.z)
	var v := travel.length() / delta
	_last = pos
	if can_step.is_valid() and not bool(can_step.call()):
		_was_airborne = false
		_walking = false
		_speed = 0.0
		_phase = 1.0
		return
	var landed: bool = false
	if grounded.is_valid():
		on_ground = bool(grounded.call())
		if not on_ground:
			_was_airborne = true
			_walking = false
			_start_left = 0.0
			# приземлился — сразу шаг
			_phase = 1.0
			return
		if _was_airborne:
			_was_airborne = false
			landed = true
			Audio.play("land", pos, float(Balance.JUMP.land_db))
	# телепорт (спавн, тест) — не шаги
	if v > 20.0:
		return
	if speed_source.is_valid():
		var own := float(speed_source.call())
		if own >= 0.0:
			v = own
	# у чужих позиция приходит рывками — скорость сглаживаем
	_speed = lerpf(_speed, v, minf(1.0, delta * 8.0))
	_interval = clampf(Balance.STEP_STRIDE / maxf(_speed, 0.01), float(Balance.STEP_INTERVAL[0]), float(Balance.STEP_INTERVAL[1]))
	if _local_steps:
		_read_timing()
		var running: float = smoothstep(Balance.PLAYER_WALK_SPEED, Balance.PLAYER_SPRINT_SPEED, _speed)
		_interval *= lerpf(_walk_scale, _run_scale, running)
	if _speed < 0.35:
		# встал — следующий шаг сразу, как тронется (фаза подходит к этому плавно, без скачка)
		_walking = false
		_start_left = 0.0
		var ready := 1.0 - Balance.STEP_START_SEC / float(Balance.STEP_INTERVAL[1])
		if _phase < ready:
			_phase = minf(ready, _phase + delta * Balance.STEP_READY_RATE)
		return
	if not _walking and _custom_start and not landed:
		_start_left = _start_sec
		_phase = 1.0
	_walking = true
	if _start_left > 0.0:
		var waited: float = minf(_start_left, delta)
		_start_left -= waited
		delta -= waited
		_phase = maxf(0.0, 1.0 - _start_left / _interval)
		if _start_left > 0.0:
			return
	# темп следует за скоростью сразу, а не со следующего шага
	_phase += delta / _interval
	if _phase < 1.0:
		return
	_phase = minf(_phase - 1.0, 0.99)
	steps_taken += 1
	_left = not _left
	var extra := float(loud_db.call()) if loud_db.is_valid() else 0.0
	# вброд — брызги и круг на воде у ноги (видно у всех peer, как и шаг)
	if WaterBody.depth_at(pos) > float(Balance.WATER.ankle):
		WaterBody.splash(get_tree(), pos, clampf(_speed / 5.0, 0.2, 1.0))
	var special := String(movement_kind.call()) if movement_kind.is_valid() else ""
	if special != "" and special != "step_crouch":
		Audio.play(special, pos, extra)
		return
	var run_speed := Balance.AI_STEP_RUN_SPEED if ai else Balance.STEP_RUN_SPEED
	var right: Vector3 = -body.global_basis.x if is_instance_valid(body) else (get_parent() as Node3D).global_basis.x
	var ahead: Vector3 = travel.normalized() * minf(_speed * _interval * 0.32, 0.32)
	Audio.step(pos, _speed > run_speed, ai, extra, _left, right, _local_steps, ahead)


func _read_timing() -> void:
	if _timing_revision == LabTuning.revision:
		return
	_timing_revision = LabTuning.revision
	_walk_scale = Balance.lab_number("step_timing", "walk_sec") / Balance.STEP_WALK_SEC
	_run_scale = Balance.lab_number("step_timing", "run_sec") / Balance.STEP_RUN_SEC
	_custom_start = Balance.lab_number("step_timing", "start_custom") >= 0.5
	_start_sec = Balance.lab_number("step_timing", "start_sec")
	if not _custom_start:
		_start_left = 0.0
