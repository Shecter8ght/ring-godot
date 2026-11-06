class_name ProcSound
extends Node
## Процедурный звук на AudioStreamGenerator — для учебной цели ПЗРК и заглушек «Осоки», пока у них нет записей
## (владелец 2026-11-06: вертолёту на стенде «добавить процедурный звук»). Записи, если их назначат в Sonora
## (события osoka_launch, osoka_motor, osoka_seeker, heli_rotor — docs/weapon_sounds.md), звучат вместо этого.
## Виды: ROTOR — хлопки лопастей несущего винта (rotor_hz × blades в секунду) по глухому шуму, жужжание рулевого
## винта и свист турбины; MOTOR — рёв ракетного двигателя (низкий шум с треском); TONE — писк головки
## самонаведения (tone_hz, прерывистый с частотой gate_hz, 0 — ровный); THUMP — хлопок вышибного заряда и шелест
## ракеты из трубы (звучит life секунд и убирается сам).

enum Kind { ROTOR, MOTOR, TONE, THUMP }

var kind: int = Kind.TONE
## Громкость 0…1 — к ней звук идёт плавно (без щелчков при включении и смене прерывистого на ровный).
var level: float = 1.0
var tone_hz: float = 1000.0
var gate_hz: float = 0.0
var rotor_hz: float = 4.3
var blades: int = 4
var tail_hz: float = 19.0
## Сколько звучать, с (THUMP); меньше нуля — пока не уберут.
var life: float = -1.0
var player: Node

var _rate: float = 22050.0
var _pb: AudioStreamGeneratorPlayback
var _t: float = 0.0
var _phase: float = 0.0
var _phase2: float = 0.0
var _lp: float = 0.0
var _lp2: float = 0.0
var _lp3: float = 0.0
var _gain: float = 0.0
var _rng := RandomNumberGenerator.new()


## Звук в мире у узла parent: unit_m — до какого расстояния громкость полная, max_m — дальше не слышно.
static func make_3d(parent: Node3D, what: int, unit_m: float, max_m: float, db: float, bus: StringName = &"World") -> ProcSound:
	var s := ProcSound.new()
	s.kind = what
	var p := AudioStreamPlayer3D.new()
	p.unit_size = unit_m
	p.max_distance = max_m
	p.volume_db = db
	p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	# эффект Доплера в проекте выключен у всех источников (docs/weapon_sounds.md, 2026-10-21)
	p.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	p.bus = bus if AudioServer.get_bus_index(bus) >= 0 else &"Master"
	s.player = p
	s.add_child(p)
	parent.add_child(s)
	s._start()
	return s


## Звук «в ушах» (писк ГСН — в наушнике у стрелка).
static func make_ui(parent: Node, what: int, db: float) -> ProcSound:
	var s := ProcSound.new()
	s.kind = what
	var p := AudioStreamPlayer.new()
	p.volume_db = db
	p.bus = &"UI" if AudioServer.get_bus_index(&"UI") >= 0 else &"Master"
	s.player = p
	s.add_child(p)
	parent.add_child(s)
	s._start()
	return s


func _start() -> void:
	_rng.randomize()
	# низкие звуки — реже отсчёты (дешевле в скрипте), писк — чаще
	_rate = 22050.0 if kind == Kind.TONE else 16000.0
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = _rate
	gen.buffer_length = 0.12
	player.set("stream", gen)
	player.call("play")
	_pb = player.call("get_stream_playback") as AudioStreamGeneratorPlayback
	_gain = level if kind == Kind.THUMP else 0.0


func _process(delta: float) -> void:
	if life >= 0.0:
		life -= delta
		if life <= 0.0:
			queue_free()
			return
	if _pb == null:
		return
	var n: int = _pb.get_frames_available()
	if n <= 0:
		return
	var dt: float = 1.0 / _rate
	var smooth: float = 1.0 - exp(-dt / 0.02)
	var frames := PackedVector2Array()
	frames.resize(n)
	for i in range(n):
		_gain += (level - _gain) * smooth
		var s: float = 0.0
		match kind:
			Kind.ROTOR:
				s = _rotor(dt)
			Kind.MOTOR:
				s = _motor(dt)
			Kind.TONE:
				s = _tone(dt)
			Kind.THUMP:
				s = _thump()
		_t += dt
		var v: float = clampf(s * _gain, -1.0, 1.0)
		frames[i] = Vector2(v, v)
	_pb.push_buffer(frames)


## Несущий винт: каждая лопасть — глухой хлопок по шуму; рулевой — жужжание; турбина — тонкий свист.
func _rotor(dt: float) -> float:
	_phase = fmod(_phase + rotor_hz * float(blades) * dt, 1.0)
	_phase2 = fmod(_phase2 + tail_hz * 3.0 * dt, 1.0)
	var slap: float = pow(maxf(0.0, sin(TAU * _phase)), 10.0)
	var noise: float = _rng.randf_range(-1.0, 1.0)
	_lp += (noise - _lp) * 0.06
	_lp2 += (_lp - _lp2) * 0.25
	var body: float = _lp2 * (0.35 + 2.6 * slap) * 2.2
	var tail: float = sin(TAU * _phase2) * 0.05 + _lp * 0.25 * pow(maxf(0.0, sin(TAU * _phase2)), 4.0)
	var whine: float = sin(TAU * 1730.0 * _t) * 0.018 + sin(TAU * 3460.0 * _t) * 0.006
	return body + tail + whine


## Ракетный двигатель: плотный низкий шум, колышется и потрескивает.
func _motor(_dt: float) -> float:
	var noise: float = _rng.randf_range(-1.0, 1.0)
	_lp += (noise - _lp) * 0.45
	_lp2 += (_lp - _lp2) * 0.14
	_lp3 += (_lp2 - _lp3) * 0.05
	var crackle: float = _rng.randf_range(-1.0, 1.0) * 0.9 if _rng.randf() < 0.004 else 0.0
	var wobble: float = 1.0 + 0.18 * sin(TAU * 6.5 * _t) + 0.1 * sin(TAU * 17.0 * _t)
	return (_lp3 * 2.4 + _lp2 * 0.9 + _lp * 0.15) * wobble + crackle


## Писк ГСН: тон с нечётными гармониками (как у зуммера), прерывистый или ровный.
func _tone(dt: float) -> float:
	_phase = fmod(_phase + tone_hz * dt, 1.0)
	var w: float = sin(TAU * _phase) + 0.3 * sin(3.0 * TAU * _phase) + 0.12 * sin(5.0 * TAU * _phase)
	var gate: float = 1.0
	if gate_hz > 0.0:
		_phase2 = fmod(_phase2 + gate_hz * dt, 1.0)
		gate = clampf((0.55 - _phase2) * 40.0, 0.0, 1.0) * clampf(_phase2 * 40.0, 0.0, 1.0)
	_lp += (gate - _lp) * 0.02
	return w * 0.35 * _lp


## Вышибной заряд: удар с низким «бумом», потом шелест.
func _thump() -> float:
	var noise: float = _rng.randf_range(-1.0, 1.0)
	_lp += (noise - _lp) * 0.3
	var hit: float = exp(-_t / 0.035) * (noise * 0.8 + sin(TAU * 62.0 * _t) * 1.2)
	var hiss: float = exp(-_t / 0.35) * _lp * 0.5
	return hit + hiss
