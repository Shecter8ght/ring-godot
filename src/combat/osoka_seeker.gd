class_name OsokaSeeker
extends RefCounted
## Головка самонаведения «Осоки» у своего игрока (Balance.OSOKA). Включается, когда комплекс вскинут к прицелу:
## рычаг «НАКОЛ» (powered — вид), через power_sec — поиск. Тепловая цель (узел группы "heat_targets": heat_point(),
## heat_alive()) на виду, ближе lock_range_m и в конусе cone_deg от линии взгляда — сопровождение: прерывистый писк
## учащается, доля захвата progress растёт за lock_sec; дошла до 1 — захват: ровный высокий писк (у стрелка в
## наушнике), лампа на целике, метка на экране зелёная. Захват держится, пока цель в track_deg от линии и на виду.
## Цель ушла из конуса до захвата — доля тает вдвое быстрее, чем набиралась. Опустил комплекс — головка выключена.

enum State { OFF, WARMUP, SEARCH, TRACK, LOCK }

var state: int = State.OFF
var target: Node3D
var progress: float = 0.0
var powered: bool = false
## Угол от линии взгляда до цели, град (для метки на экране).
var angle_deg: float = 999.0
var _power_t: float = 0.0
var _tone: ProcSound
var _recorded_tone: AudioStreamPlayer
var _recorded_hook: String = ""


func locked() -> bool:
	return state == State.LOCK and target != null and is_instance_valid(target)


## Головка выключена (опустил, убрал, пуск): писк стихает, захват сброшен; powered — остаётся ли рычаг на «НАКОЛ».
func reset(keep_power: bool = false) -> void:
	_stop_recorded_tone()
	state = State.OFF
	target = null
	progress = 0.0
	angle_deg = 999.0
	powered = keep_power
	_power_t = 0.0
	if is_instance_valid(_tone):
		_tone.level = 0.0


## Каждый кадр у своего игрока: active — комплекс в руках, вскинут к прицелу, в трубе ракета.
func tick(pl: Player, delta: float, active: bool) -> void:
	var cfg: Dictionary = Balance.OSOKA
	if not active:
		if state != State.OFF:
			reset(powered)
		return
	powered = true
	if state == State.OFF:
		state = State.WARMUP
		_power_t = 0.0
	if state == State.WARMUP:
		_power_t += delta
		if _power_t < float(cfg.power_sec):
			_set_tone(pl, 0.0, 0.0, 0.0)
			return
		state = State.SEARCH
	var eye: Vector3 = pl.eye_position()
	var look: Vector3 = pl.look_dir()
	if state == State.LOCK:
		var a: float = _angle(pl, target, eye, look)
		if a <= float(cfg.track_deg):
			angle_deg = a
			_set_tone(pl, 1.0, float((cfg.tone_hz as Array)[1]), 0.0)
			return
		target = null
		progress = 0.0
		state = State.SEARCH
	var best: Node3D = null
	var best_a: float = float(cfg.cone_deg)
	for raw: Node in pl.get_tree().get_nodes_in_group("heat_targets"):
		var a2: float = _angle(pl, raw as Node3D, eye, look)
		if a2 < best_a:
			best = raw as Node3D
			best_a = a2
	if best == null:
		progress = maxf(0.0, progress - delta * 2.0 / float(cfg.lock_sec))
		if progress <= 0.0:
			target = null
			angle_deg = 999.0
			state = State.SEARCH
			_set_tone(pl, 0.0, 0.0, 0.0)
		else:
			angle_deg = _angle(pl, target, eye, look)
			_set_tone(pl, 0.6, float((cfg.tone_hz as Array)[0]), float(cfg.beep_hz))
		return
	if best != target:
		target = best
		progress = 0.0
	angle_deg = best_a
	state = State.TRACK
	progress = minf(1.0, progress + delta / float(cfg.lock_sec))
	if progress >= 1.0:
		state = State.LOCK
		_set_tone(pl, 1.0, float((cfg.tone_hz as Array)[1]), 0.0)
	else:
		_set_tone(pl, 0.85, float((cfg.tone_hz as Array)[0]), lerpf(float(cfg.beep_hz), float(cfg.beep_fast_hz), progress))


## Угол от линии взгляда до тепловой точки цели, град; цель погасла, далеко или закрыта — 999.
func _angle(pl: Player, n: Node3D, eye: Vector3, look: Vector3) -> float:
	if n == null or not is_instance_valid(n):
		return 999.0
	if n.has_method("heat_alive") and not bool(n.call("heat_alive")):
		return 999.0
	var p: Vector3 = n.call("heat_point") if n.has_method("heat_point") else n.global_position
	var d: Vector3 = p - eye
	var dist: float = d.length()
	if dist < 1.0 or dist > float(Balance.OSOKA.lock_range_m):
		return 999.0
	var a: float = rad_to_deg(look.angle_to(d))
	if a > float(Balance.OSOKA.track_deg) + 2.0:
		return a
	# ИК-головка не видит сквозь стены, крыши и стекло
	var mask: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS | Hitscan.LAYER_ROOF
	var q := PhysicsRayQueryParameters3D.create(eye, p, mask, [pl.get_rid()])
	var hit: Dictionary = pl.get_world_3d().direct_space_state.intersect_ray(q)
	if not hit.is_empty() and eye.distance_to(hit.position as Vector3) < dist - 4.0:
		return 999.0
	return a


func _set_tone(pl: Player, level: float, hz: float, gate: float) -> void:
	var hook: String = "osoka_seeker_lock" if state == State.LOCK else "osoka_seeker_track"
	if level <= 0.0:
		_stop_recorded_tone()
	elif Audio.has_sound(hook):
		if is_instance_valid(_tone):
			_tone.level = 0.0
		if _recorded_hook != hook or not is_instance_valid(_recorded_tone):
			_stop_recorded_tone()
			_recorded_tone = Audio.start_ui_loop(hook, pl, float(Balance.OSOKA.tone_db))
			_recorded_hook = hook
		return
	else:
		_stop_recorded_tone()
	if level > 0.0 and not is_instance_valid(_tone):
		_tone = ProcSound.make_ui(pl, ProcSound.Kind.TONE, float(Balance.OSOKA.tone_db))
	if not is_instance_valid(_tone):
		return
	_tone.level = level
	if hz > 0.0:
		_tone.tone_hz = hz
	_tone.gate_hz = gate


func _stop_recorded_tone() -> void:
	if is_instance_valid(_recorded_tone):
		_recorded_tone.stop()
		_recorded_tone.queue_free()
	_recorded_hook = ""
