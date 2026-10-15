class_name GrassTrample
extends Node
## Карта примятой травы вокруг камеры: квадрат GRASS.trample_extent м, res×res клеток, по кругу
## (клетка = мир по модулю окна — при движении камеры ничего не сдвигается). В клетке: RG — куда
## отогнута трава (мир xz), B — насколько (1 — легла). Кто примял — игроки (стоя, присев, лёжа),
## мародёры и чужие отряды, тела убитых, взрывы гранат (blast). Трава поднимается сама за
## trample_recover_sec; процессор обходит только примятые клетки, видеокарте отдаётся маленькая
## текстура (глобальная grass_trample, её читают шейдеры травы) не чаще trample_hz раз в секунду.
## Всё видно только этому peer: каждый считает по тем, кого у него видно, — по сети ничего не идёт.

static var current: GrassTrample

var _res: int = 128
var _extent: float = 48.0
var _cell: float = 0.375
var _data: PackedByteArray
var _img: Image
var _tex: ImageTexture
## клетка → Vector3(мир x, мир z, сила): где примяли — чтобы снять клетку, когда она ушла из окна
var _active: Dictionary = {}
var _center: Vector2 = Vector2.ZERO
var _tick: float = 0.0
var _dirty: bool = false
## кто последний раз примял и где — стоящего на месте не перештамповываем каждый кадр
var _last: Dictionary = {}
var _wind: float = 1.0


func _ready() -> void:
	current = self
	var cfg: Dictionary = Balance.GRASS
	_res = int(cfg.trample_res)
	_extent = float(cfg.trample_extent)
	_cell = _extent / float(_res)
	_data = PackedByteArray()
	_data.resize(_res * _res * 4)
	for i in range(_res * _res):
		_data[i * 4] = 128
		_data[i * 4 + 1] = 128
		_data[i * 4 + 2] = 0
		_data[i * 4 + 3] = 255
	_img = Image.create_from_data(_res, _res, false, Image.FORMAT_RGBA8, _data)
	_tex = ImageTexture.create_from_image(_img)
	RenderingServer.global_shader_parameter_set("grass_trample", _tex)
	_push_area()
	_wind = float((cfg.wind as Vector4).z)
	_push_wind()


func _exit_tree() -> void:
	if current == self:
		current = null
		RenderingServer.global_shader_parameter_set("grass_trample_area", Vector4.ZERO)


## Взрыв: трава вокруг легла от центра (радиус, м). Можно звать без травы на уровне.
static func blast(pos: Vector3, radius: float) -> void:
	if current == null:
		return
	current._stamp(Vector2(pos.x, pos.z), radius * float(Balance.GRASS.trample_radius.blast_k), Vector2.ZERO, 1.0)


func _process(delta: float) -> void:
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return
	_tick_wind(delta)
	_tick += delta
	var period := 1.0 / float(Balance.GRASS.trample_hz)
	if _tick < period:
		return
	var dt := _tick
	_tick = 0.0
	_center = Vector2(cam.global_position.x, cam.global_position.z)
	_push_area()
	_stamp_pushers()
	_decay(dt)
	if _dirty:
		_dirty = false
		_img.set_data(_res, _res, false, Image.FORMAT_RGBA8, _data)
		_tex.update(_img)


## Сила ветра: в дождь сильнее; меняется плавно.
func _tick_wind(delta: float) -> void:
	var cfg: Dictionary = Balance.GRASS
	var want := float((cfg.wind as Vector4).z)
	if RaidWeather.current != null and RaidWeather.current.is_raining():
		want *= float(cfg.wind_rain_k)
	if absf(want - _wind) > 0.001:
		_wind = move_toward(_wind, want, delta * 0.2)
		_push_wind()


func _push_wind() -> void:
	var w: Vector4 = Balance.GRASS.wind
	RenderingServer.global_shader_parameter_set("grass_wind", Vector4(w.x, w.y, _wind, w.w))


func _push_area() -> void:
	RenderingServer.global_shader_parameter_set("grass_trample_area", Vector4(_center.x, _center.y, _extent, 1.0))


func _stamp_pushers() -> void:
	var rad: Dictionary = Balance.GRASS.trample_radius
	var seen: Dictionary = {}
	for n in get_tree().get_nodes_in_group("all_players"):
		var p := n as Player
		if p == null or not p.is_inside_tree():
			continue
		var r := float(rad.stand)
		var down := p.health != null and (p.health.downed or not p.health.alive)
		if p.stance == Player.Stance.PRONE or down:
			r = float(rad.prone)
		elif p.stance == Player.Stance.CROUCH:
			r = float(rad.crouch)
		_push_body(p, p.global_position, r, down, seen)
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == null or not m.is_inside_tree():
			continue
		var h := m.get_node_or_null("Health") as Health
		# убитый лежит регдоллом — его мнёт группа ragdolls ниже
		if h != null and not h.alive:
			continue
		var down := h != null and h.downed
		_push_body(m, m.global_position, float(rad.prone) if down else float(rad.stand), down, seen)
	for n in get_tree().get_nodes_in_group("ragdolls"):
		if n is Node3D and (n as Node3D).is_inside_tree():
			for part in (n as Node).get_children():
				if part is Node3D:
					_push_point(part, (part as Node3D).global_position, float(rad.body), seen)
	# ушедшие из дерева — забыть
	for k in _last.keys():
		if not is_instance_valid(k) or not seen.has(k):
			_last.erase(k)


## Лежащий (раненый, убитый) мнёт траву всем телом: по костям модели, если она есть.
func _push_body(node: Node3D, pos: Vector3, r: float, lying: bool, seen: Dictionary) -> void:
	if lying:
		var anim := node.get_node_or_null("CharacterAnimator") as CharacterAnimator
		if anim and anim.has_model():
			for bone: String in Balance.GRASS.body_bones:
				var b := anim.bone_node(bone)
				if b:
					_push_point(b, b.global_position, float(Balance.GRASS.trample_radius.body), seen)
			return
	_push_point(node, pos, r, seen)


func _push_point(key: Object, pos: Vector3, r: float, seen: Dictionary) -> void:
	seen[key] = true
	var at := Vector2(pos.x, pos.z)
	if absf(at.x - _center.x) > _extent * 0.42 or absf(at.y - _center.y) > _extent * 0.42:
		return
	var last: Variant = _last.get(key)
	var move := Vector2.ZERO
	if last != null:
		var lp: Vector3 = last
		move = at - Vector2(lp.x, lp.y)
		# стоит на месте — освежаем раз в треть времени подъёма, не каждый кадр
		if move.length() < 0.06 and Time.get_ticks_msec() * 0.001 - lp.z < float(Balance.GRASS.trample_recover_sec) * 0.3:
			return
	_last[key] = Vector3(at.x, at.y, Time.get_ticks_msec() * 0.001)
	var dir := move.normalized() if move.length() > 0.01 else Vector2.ZERO
	_stamp(at, r, dir, 1.0)


## Круг радиуса r вокруг at: трава отогнута от центра (и по ходу движения dir), сила — к краю меньше.
func _stamp(at: Vector2, r: float, dir: Vector2, strength: float) -> void:
	var c0 := Vector2i(floori((at.x - r) / _cell), floori((at.y - r) / _cell))
	var c1 := Vector2i(floori((at.x + r) / _cell), floori((at.y + r) / _cell))
	for cz in range(c0.y, c1.y + 1):
		for cx in range(c0.x, c1.x + 1):
			var wp := Vector2((float(cx) + 0.5) * _cell, (float(cz) + 0.5) * _cell)
			var off := wp - at
			var d := off.length()
			if d > r + _cell * 0.5:
				continue
			var s := strength * (1.0 - smoothstep(r * 0.45, r + _cell * 0.5, d))
			if s <= 0.02:
				continue
			var radial := off / d if d > 0.001 else dir
			var bend := (radial * 0.75 + dir * 0.6)
			bend = bend.normalized() if bend.length() > 0.001 else Vector2(1.0, 0.0)
			var tx := posmod(cx, _res)
			var tz := posmod(cz, _res)
			var idx := tz * _res + tx
			var prev: Vector3 = _active.get(idx, Vector3(wp.x, wp.y, 0.0))
			# в клетке уже чужое место (окно ушло по кругу) — заменить
			if absf(prev.x - wp.x) > 0.01 or absf(prev.y - wp.y) > 0.01:
				prev = Vector3(wp.x, wp.y, 0.0)
			if s < prev.z:
				continue
			_active[idx] = Vector3(wp.x, wp.y, s)
			_write(idx, bend, s)


func _write(idx: int, bend: Vector2, s: float) -> void:
	var o := idx * 4
	_data[o] = clampi(int(round((bend.x * 0.5 + 0.5) * 255.0)), 0, 255)
	_data[o + 1] = clampi(int(round((bend.y * 0.5 + 0.5) * 255.0)), 0, 255)
	_data[o + 2] = clampi(int(round(s * 255.0)), 0, 255)
	_dirty = true


## Трава поднимается; клетки, ушедшие из окна, снимаются сразу (иначе всплыли бы с другой стороны).
func _decay(dt: float) -> void:
	if _active.is_empty():
		return
	var step := dt / float(Balance.GRASS.trample_recover_sec)
	var lim := _extent * 0.45
	for idx: int in _active.keys():
		var v: Vector3 = _active[idx]
		var s := v.z - step
		if s <= 0.0 or absf(v.x - _center.x) > lim or absf(v.y - _center.y) > lim:
			_active.erase(idx)
			var o := idx * 4
			_data[o] = 128
			_data[o + 1] = 128
			_data[o + 2] = 0
			_dirty = true
			continue
		_active[idx] = Vector3(v.x, v.y, s)
		_data[idx * 4 + 2] = clampi(int(round(s * 255.0)), 0, 255)
		_dirty = true


## Для проверок: сколько клеток примято и сила в точке мира.
func pressed_at(pos: Vector3) -> float:
	var cx := floori(pos.x / _cell)
	var cz := floori(pos.z / _cell)
	var idx := posmod(cz, _res) * _res + posmod(cx, _res)
	var v: Variant = _active.get(idx)
	return (v as Vector3).z if v != null else 0.0


func active_cells() -> int:
	return _active.size()
