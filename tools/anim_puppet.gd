class_name AnimPuppet
extends CharacterBody3D
## Фигура для стенда анимаций (tools/anim_stand): Persona с автоматом, без ИИ и физики — ходит по
## своей программе (PROGRAMS) по кругу и отдаёт аниматору состояние через anim_state(), как игрок
## или мародёр. legacy — аниматор «как было» (для сравнения рядом).

## Программы: отрезки {t — длительность, с; v — скорость, м/с; dir — куда идёт (в осях фигуры, если
## face задан, иначе по кругу); face — куда смотрит (град от начального, «move» — по ходу); crouch,
## prone, aim; pitch / lean — взгляд и выглядывание (от / до за отрезок); fire — выстрел раз в столько с;
## event — событие в начале отрезка; circle — радиус круга (идёт по кругу, смотрит по ходу)}.
const PROGRAMS := {
	"circle": [
		{"t": 9.0, "v": 1.5, "circle": 4.0},
		{"t": 6.0, "v": 3.4, "circle": 4.0},
		{"t": 5.0, "v": 5.2, "circle": 4.0},
		{"t": 2.5, "v": 0.0, "circle": 4.0},
	],
	"lines": [
		{"t": 3.0, "v": 1.82, "dir": 0.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 3.0, "v": 1.82, "dir": 180.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 3.0, "v": 1.82, "dir": 90.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 3.0, "v": 1.82, "dir": -90.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 3.0, "v": 1.82, "dir": 30.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 3.0, "v": 1.82, "dir": -150.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
	],
	"strafe": [
		{"t": 1.6, "v": 1.82, "dir": 0.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": 180.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": 90.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": -90.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": 45.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": -135.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": -45.0, "face": 0.0},
		{"t": 1.6, "v": 1.82, "dir": 135.0, "face": 0.0},
		{"t": 1.0, "v": 0.0, "face": 0.0},
		{"t": 1.6, "v": 1.4, "dir": 30.0, "face": 0.0, "crouch": true},
		{"t": 1.6, "v": 1.4, "dir": -150.0, "face": 0.0, "crouch": true},
		{"t": 1.6, "v": 1.4, "dir": 120.0, "face": 0.0, "crouch": true},
		{"t": 1.6, "v": 1.4, "dir": -60.0, "face": 0.0, "crouch": true},
		{"t": 1.0, "v": 0.0, "face": 0.0},
	],
	"turns": [
		{"t": 1.5, "v": 0.0, "face": 0.0, "aim": true},
		{"t": 1.5, "v": 0.0, "face": 100.0, "aim": true},
		{"t": 1.5, "v": 0.0, "face": -60.0, "aim": true},
		{"t": 1.2, "v": 0.0, "face": 30.0, "aim": true},
		{"t": 1.8, "v": 1.82, "dir": 0.0, "face": "move"},
		{"t": 0.8, "v": 0.0, "face": 0.0},
		{"t": 1.2, "v": 1.82, "dir": 180.0, "face": "move"},
		{"t": 1.0, "v": 0.0, "face": 0.0, "crouch": true},
		{"t": 1.5, "v": 5.2, "dir": 90.0, "face": "move"},
		{"t": 1.5, "v": 5.2, "dir": -90.0, "face": "move"},
		{"t": 1.0, "v": 0.0, "face": 0.0},
	],
	"shooter": [
		{"t": 1.2, "v": 0.0, "face": 0.0, "aim": true},
		{"t": 3.0, "v": 0.0, "face": 0.0, "aim": true, "pitch": [0.0, 0.6]},
		{"t": 3.0, "v": 0.0, "face": 0.0, "aim": true, "pitch": [0.6, -0.6]},
		{"t": 1.5, "v": 0.0, "face": 0.0, "aim": true, "pitch": [-0.6, 0.0]},
		{"t": 1.5, "v": 0.0, "face": 0.0, "aim": true, "lean": [0.0, 1.0]},
		{"t": 1.5, "v": 0.0, "face": 0.0, "aim": true, "lean": [1.0, -1.0]},
		{"t": 1.0, "v": 0.0, "face": 0.0, "aim": true, "lean": [-1.0, 0.0]},
		{"t": 1.2, "v": 0.0, "face": 0.0, "aim": true, "fire": 0.1},
		{"t": 3.0, "v": 0.0, "face": 0.0, "event": "rifle_reload"},
		{"t": 3.0, "v": 1.0, "dir": 0.0, "face": 0.0, "event": "rifle_reload"},
		{"t": 1.2, "v": 0.0, "face": 0.0, "aim": true, "event": "hit"},
		{"t": 1.5, "v": 0.0, "face": 0.0, "aim": true, "crouch": true, "fire": 0.12},
		{"t": 2.5, "v": 0.0, "face": 0.0, "prone": true},
		{"t": 1.0, "v": 0.0, "face": 0.0},
	],
}

const PERSONA_MODEL := "res://assets/models/characters/persona_animated.glb"

var program: String = "circle"
var legacy: bool = false
## Модель фигуры: Persona или другое тело на том же скелете mixamorig_* (мародёр v03 —
## res://assets/models/characters/npc_marauder/npc_marauder.gltf); ставится до добавления в дерево.
var model: String = PERSONA_MODEL
## Время программы с запуска, с (по шагам физики: при тормозах первых кадров идёт медленнее часов).
var clock: float = 0.0
var weapon_id: String = "wpn_ar_01"

var _segment: int = 0
var _t: float = 0.0
var _anchor: Vector3
var _face0: float = 0.0
var _yaw: float = 0.0
var _angle: float = 0.0
var _state: Dictionary = {}
var _event_seq: int = 0
var _fire_t: float = 0.0
var _body: Node3D
var _animator: CharacterAnimator
## Скорость по земле: разгон и торможение как у игрока (Balance.PLAYER_ACCEL / PLAYER_DECEL) — живое
## тело не разворачивается с бега на бег мгновенно.
var _move_v: Vector3 = Vector3.ZERO


func _init() -> void:
	_body = Node3D.new()
	_body.name = "Body"
	add_child(_body)
	_animator = CharacterAnimator.new()
	_animator.name = "CharacterAnimator"
	add_child(_animator)
	collision_layer = 0
	collision_mask = 0


func _enter_tree() -> void:
	# модель — до _ready аниматора (он ищет Body/Persona), а сама фигура может быть создана до выбора модели
	if _body.get_node_or_null("Persona") == null:
		var persona: Node3D = (load(model) as PackedScene).instantiate() as Node3D
		persona.name = "Persona"
		_body.add_child(persona)


func _ready() -> void:
	_anchor = global_position
	_face0 = rotation.y
	rotation.y = 0.0
	_yaw = _face0
	_animator.legacy = legacy
	var grip: Node3D = _animator.weapon_grip(String(WeaponDb.weapon(weapon_id).get("model", "rifle")), weapon_id)
	if grip:
		grip.add_child(WeaponModels.build(weapon_id, {}, 1))
	_enter(0)


func anim_state() -> Dictionary:
	return _state


func animator() -> CharacterAnimator:
	return _animator


func _enter(i: int) -> void:
	var steps: Array = PROGRAMS[program]
	_segment = i % steps.size()
	_t = 0.0
	_fire_t = 0.0
	var seg: Dictionary = steps[_segment]
	if seg.has("event"):
		_event(String(seg.event))
	if _segment == 0 and _move_v.length() < 0.05:
		# программа замкнута, но погрешность шагов копится — каждый круг с начальной точки
		global_position = _anchor
		_angle = 0.0


func _event(name: String) -> void:
	_event_seq += 1
	_state.event = name
	_state.event_seq = _event_seq


func _physics_process(delta: float) -> void:
	var steps: Array = PROGRAMS[program]
	var seg: Dictionary = steps[_segment]
	_t += delta
	clock += delta
	var k: float = clampf(_t / float(seg.t), 0.0, 1.0)
	var v: float = float(seg.get("v", 0.0))
	var move := Vector3.ZERO
	if seg.has("circle"):
		# по кругу против часовой, лицом по ходу
		var r: float = float(seg.circle)
		var along: float = move_toward(_move_v.length(), v, (Balance.PLAYER_ACCEL if v > _move_v.length() else Balance.PLAYER_DECEL) * delta)
		_angle += along / r * delta
		var center: Vector3 = _anchor + Vector3(r, 0.0, 0.0)
		var pos: Vector3 = center + Vector3(-cos(_angle), 0.0, sin(_angle)) * r
		move = pos - global_position
		global_position = pos
		_move_v = move / delta
		if move.length() > 0.0001:
			_yaw = atan2(move.x, move.z)
	else:
		var face: Variant = seg.get("face", null)
		if face is float or face is int:
			# поворот мгновенный, как у мародёра (_face): модель догоняет сама
			_yaw = _face0 + deg_to_rad(float(face))
		var want := Vector3.ZERO
		if v > 0.0:
			var a: float = _face0 + deg_to_rad(float(seg.get("dir", 0.0)))
			want = Vector3(sin(a), 0.0, cos(a)) * v
			if face is String and face == "move":
				_yaw = a
		var rate: float = Balance.PLAYER_DECEL if want.length() < _move_v.length() or want.dot(_move_v) < 0.0 else Balance.PLAYER_ACCEL
		_move_v = _move_v.move_toward(want, rate * delta)
		move = _move_v * delta
		global_position += move
	_body.rotation.y = _yaw
	_state.family = "rifle"
	_state.crouched = bool(seg.get("crouch", false))
	_state.prone = bool(seg.get("prone", false))
	_state.aiming = bool(seg.get("aim", false))
	var pitch: Array = seg.get("pitch", [0.0, 0.0])
	_state.look_pitch = lerpf(float(pitch[0]), float(pitch[1]), k)
	var lean: Array = seg.get("lean", [0.0, 0.0])
	_state.lean = lerpf(float(lean[0]), float(lean[1]), k)
	if seg.has("fire"):
		_fire_t -= delta
		if _fire_t <= 0.0:
			_fire_t = float(seg.fire)
			_event("rifle_fire")
	if _t >= float(seg.t):
		_enter(_segment + 1)
