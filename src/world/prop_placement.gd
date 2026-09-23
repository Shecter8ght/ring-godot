class_name PropPlacement
extends RefCounted
## Расстановка пропсов по смыслу помещения — в полярных координатах кольца.
## Ряды идут дугами вдоль помещения (стеллажи торгового зала, машины на парковке), а не россыпью:
## так читаются проходы и линии укрытий. Проёмы и точка спавна остаются свободными.
## Полосы (прямая аллея, см. SectorBuilder) — свои правила в осях полосы; кольцевые помещения
## под полосой пропсов не получают (проверка владельца точки по углам пропа). Узлы сцены уровня
## в группе "prop_keepout" (эскалаторы) отдают прямоугольник, где пропсов быть не должно.

## Зазор между случайно поставленными пропами — не меньше ширины тела с запасом, м.
const SCATTER_GAP := 1.0
## Полоса у проёма, которую пропы не занимают, м.
const DOOR_PAD := 2.6

var _props: Props
var _rng := RandomNumberGenerator.new()
## Занятые полярные прямоугольники {a0,a1,r0,r1} — пропы и запретные зоны.
var _taken: Array[Dictionary] = []
var _zones: Array[Dictionary] = []
var _root: Node3D
var _openings: Array = []
var count: int = 0
## Пропсы, которые обыскиваются (data/loot.json → containers): {kind, pos, room}. Сами
## LootContainer ставит SectorBuilder — порядок и выбор детерминированы сидом, как и пропсы.
var lootables: Array[Dictionary] = []
var _room_id: String = ""
var _rooms: Array = []
## Запретные прямоугольники в мировых XZ: проёмы в стенах полос и keepout-узлы сцены.
var _world_zones: Array[Rect2] = []
## Занятые пропсами полос прямоугольники (мировые XZ).
var _taken_world: Array[Rect2] = []


func place(root: Node3D, rooms: Array, openings: Array, spawn: Vector3, seed_value: int, keepouts: Array[Rect2] = []) -> void:
	_root = root
	_openings = openings
	_rooms = rooms
	_rng.seed = seed_value
	_props = Props.new(seed_value + 1)
	_world_zones.append_array(keepouts)
	for op in openings:
		if String(op.wall) == "along":
			var a := SectorBuilder.strip_point(float(op.axis), float(op.s[0]) - 1.0, float(op.t))
			var b := SectorBuilder.strip_point(float(op.axis), float(op.s[1]) + 1.0, float(op.t))
			var zr := Rect2(Vector2(a.x, a.z), Vector2.ZERO).expand(Vector2(b.x, b.z))
			_world_zones.append(zr.grow(DOOR_PAD))
		elif String(op.wall) == "arc":
			_zones.append({"a0": float(op.a[0]) - 1.0, "a1": float(op.a[1]) + 1.0, "r0": float(op.r) - DOOR_PAD, "r1": float(op.r) + DOOR_PAD})
		else:
			var rm := (float(op.r[0]) + float(op.r[1])) * 0.5
			var da := _deg(DOOR_PAD, rm)
			_zones.append({"a0": float(op.a) - da, "a1": float(op.a) + da, "r0": float(op.r[0]) - 1.0, "r1": float(op.r[1]) + 1.0})
	var sa := rad_to_deg(atan2(spawn.z, spawn.x))
	var sr := spawn.length()
	_zones.append({"a0": sa - _deg(3.0, sr), "a1": sa + _deg(3.0, sr), "r0": sr - 3.0, "r1": sr + 3.0})

	for room in rooms:
		if bool(room.get("locked", false)):
			continue
		_room_id = String(room.get("id", ""))
		if SectorBuilder.is_strip(room):
			if String(room.get("type", "")) == "gallery":
				_strip_gallery(room)
			continue
		match String(room.get("type", "")):
			"retail":
				_retail(room)
			"storage":
				_storage(room)
			"corridor":
				_corridor(room)
			"office", "security":
				_office(room)
			"utility":
				_utility(room)
			"gallery":
				_gallery(room)
			"atrium":
				_atrium(room)
			"yard":
				_yard(room)
			"parking":
				_parking(room)


# ---------------------------------------------------------------- правила по типам

func _retail(room: Dictionary) -> void:
	var a0 := float(room.a[0])
	var a1 := float(room.a[1])
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	# кассы у входов
	for op in _openings:
		if String(op.wall) != "arc" or absf(float(op.r) - r0) > 0.01 or String(op.kind) != "storefront":
			continue
		var ae := (float(op.a[0]) + float(op.a[1])) * 0.5
		if ae < a0 or ae > a1:
			continue
		var rr := r0 + 4.2
		for k in [-1.2, 0.0, 1.2]:
			_put("checkout", ae + _deg(k * 3.2, rr), rr, "tangent")
	# ряды стеллажей дугами: между кассами и задним проходом
	var rr := r0 + 8.0
	while rr < r1 - 4.5:
		_row(room, rr, "shelf_retail", 0.1, 5, 0.92, 2.0)
		rr += 3.4
	# пристенные стеллажи у задней стены
	_row(room, r1 - 0.5, "shelf_retail", 0.15, 100, 0.8, 1.0)
	# тележки и коробки — россыпью у входа
	for i in range(_rng.randi_range(4, 8)):
		_scatter(room, "cart", r0 + 1.5, r0 + 6.5, 3)
	for i in range(3):
		_scatter(room, "box_stack", r0 + 2.0, r1 - 2.0, 3)


func _storage(room: Dictionary) -> void:
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	_row(room, r0 + 0.6, "shelf_warehouse", 0.15, 100, 0.8, 1.0)
	if r1 - r0 >= 7.0:
		_row(room, r1 - 0.6, "shelf_warehouse", 0.15, 100, 0.8, 1.0)
	var rr := r0 + 3.2
	while rr < r1 - 3.0:
		_row(room, rr, "pallet_boxes", 0.9, 2, 0.45, 1.8, ["pallet_boxes", "box_stack", "barrel"])
		rr += 2.6


func _corridor(room: Dictionary) -> void:
	var r1 := float(room.r[1])
	_row(room, r1 - 0.75, "cart", 3.0, 100, 0.45, 1.5, ["cart", "barrel", "box_stack", "pallet_boxes"])


func _office(room: Dictionary) -> void:
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	_row(room, r0 + 0.4, "cabinet", 0.3, 100, 0.6, 1.2)
	var rr := r0 + 3.0
	while rr < r1 - 2.0:
		_row(room, rr, "desk", 1.4, 100, 0.75, 1.5)
		rr += 2.8


func _utility(room: Dictionary) -> void:
	var r1 := float(room.r[1])
	_row(room, r1 - 0.4, "cabinet", 0.3, 100, 0.7, 1.0)
	for i in range(3):
		_scatter(room, "barrel", float(room.r[0]) + 1.5, r1 - 1.5, 3)


func _gallery(room: Dictionary) -> void:
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	_row(room, r0 + DOOR_PAD + 0.8, "bench", 5.0, 100, 0.8, 2.0, ["bench", "planter", "bin", "planter"])
	_row(room, (r0 + r1) * 0.5, "kiosk", 15.0, 100, 0.5, 4.0)
	for i in range(3):
		_scatter(room, "cart", r0 + 2.0, r1 - 1.5, 3)


func _atrium(room: Dictionary) -> void:
	var a0 := float(room.a[0])
	var a1 := float(room.a[1])
	_put("planter", (a0 + a1) * 0.5, 2.2, "tangent")
	for rr in [13.0, 19.0]:
		var step := _deg(7.0 if rr < 15.0 else 6.0, rr)
		var a := a0 + step * 0.5
		var i := 0
		while a < a1 - step * 0.3:
			_put("planter" if (i % 2 == 0) == (rr < 15.0) else "bench", a, rr, "tangent")
			a += step
			i += 1


func _yard(room: Dictionary) -> void:
	var a0 := float(room.a[0])
	var a1 := float(room.a[1])
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	# фуры задом к воротам склада
	for op in _openings:
		if String(op.wall) != "arc" or absf(float(op.r) - r0) > 0.01 or String(op.kind) != "gate":
			continue
		var ae := (float(op.a[0]) + float(op.a[1])) * 0.5
		if ae < a0 or ae > a1:
			continue
		# по обе стороны ворот, сами ворота свободны
		_put("truck", ae - _deg(4.2, r0 + 5.0), r0 + 0.9 + 4.5, "tangent_out", "", true)
		_put("truck", ae + _deg(4.2, r0 + 5.0), r0 + 0.9 + 4.5, "tangent_out", "", true)
	# ещё одна брошенная фура и паллеты вдоль фасада
	_scatter(room, "truck", r0 + 9.0, r1 - 6.0, 4)
	_row(room, r0 + 1.4, "pallet_boxes", 1.6, 100, 0.5, 1.0, ["pallet_boxes", "box_stack", "barrel", "barrel"])
	for i in range(3):
		_scatter(room, "cart", r0 + 3.0, r1 - 3.0, 3)


func _parking(room: Dictionary) -> void:
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	var rr := r0 + 7.0
	while rr < r1 - 3.5:
		_row(room, rr, "car", 1.2, 100, 0.45, 2.0, [], true)
		rr += 10.0
	for i in range(4):
		_scatter(room, "cart", r0 + 2.0, r1 - 2.0, 3)


## Аллея: по оси — клумбы, скамейки и урны с шагом, киоски реже; эскалаторы и проёмы обходятся
## (keepout). Россыпью — брошенные тележки.
func _strip_gallery(room: Dictionary) -> void:
	var ax := float(room.axis)
	var s0 := SectorBuilder._strip_s(float(room.r[0]), 0.0) + 3.0
	var s1 := SectorBuilder._strip_s(float(room.r[1]), 0.0) - 3.0
	var alt := ["planter", "bench", "bin", "bench", "kiosk"]
	var s := s0
	var k := 0
	while s < s1:
		_put_strip(String(alt[k % alt.size()]), ax, s, 0.0, 0.0)
		s += 6.0
		k += 1
	for i in range(4):
		var t := _rng.randf_range(float(room.t[0]) + 2.0, float(room.t[1]) - 2.0)
		_put_strip("cart", ax, _rng.randf_range(s0, s1), t, _rng.randf_range(-PI, PI))


## Проп в осях полосы: ширина (X пропа) — вдоль оси. Возвращает false, если место занято.
func _put_strip(id: String, ax: float, s: float, t: float, yaw_extra: float) -> bool:
	var sz := Props.size(id)
	var pos := SectorBuilder.strip_point(ax, s, t)
	var ext := maxf(sz.x, sz.z) * 0.5 if yaw_extra != 0.0 else 0.0
	var d := SectorBuilder.polar(ax, 1.0)
	var n := SectorBuilder.polar(ax + 90.0, 1.0)
	var hx := d * (sz.x * 0.5) if ext == 0.0 else d * ext
	var hz := n * (sz.z * 0.5) if ext == 0.0 else n * ext
	var foot := Rect2(Vector2(pos.x, pos.z), Vector2.ZERO)
	for c in [hx + hz, hx - hz, -hx + hz, -hx - hz]:
		var q: Vector3 = pos + c
		foot = foot.expand(Vector2(q.x, q.z))
		if String(SectorBuilder.owner_of(_rooms, q).get("id", "")) != _room_id:
			return false
	for z in _world_zones:
		if z.intersects(foot):
			return false
	for tk in _taken_world:
		if tk.grow(0.5).intersects(foot):
			return false
	var node := _props.build(id, "")
	node.position = pos
	node.rotation.y = -deg_to_rad(ax) + yaw_extra
	_root.add_child(node)
	_taken_world.append(foot)
	count += 1
	var loot := ItemDb.container(id)
	if not loot.is_empty() and _rng.randf() < float(loot.chance):
		lootables.append({"kind": id, "pos": node.position, "room": _room_id})
	return true


# ---------------------------------------------------------------- размещение

## Ряд дугой на радиусе rr: единицы длиной w+gap вдоль угла; каждая breach_every-я — прореха.
## alt — из чего выбирать случайно вместо id; flip — случайный разворот на 180° (машины носом туда-сюда).
func _row(room: Dictionary, rr: float, id: String, gap: float, breach_every: int, fill: float, end_inset: float, alt: Array = [], flip: bool = false) -> void:
	var a0 := float(room.a[0]) + _deg(end_inset, rr)
	var a1 := float(room.a[1]) - _deg(end_inset, rr)
	if a1 <= a0:
		return
	var unit := Props.size(id).x + gap
	var len := deg_to_rad(a1 - a0) * rr
	var n := int(floor(len / unit))
	if n <= 0:
		return
	var start := a0 + _deg((len - n * unit) * 0.5, rr)
	for i in range(n):
		if breach_every < 100 and i % breach_every == breach_every - 1:
			continue
		if _rng.randf() > fill:
			continue
		var pick := id if alt.is_empty() else String(alt[_rng.randi_range(0, alt.size() - 1)])
		var a := start + _deg(unit * (i + 0.5), rr)
		var orient := "tangent"
		if flip and _rng.randf() < 0.5:
			orient = "tangent_out"
		var variant := "wrecked" if (pick == "car" and _rng.randf() < 0.2) else ""
		_put(pick, a, rr, orient, variant, false, 0.0)


## Случайная точка в поясе радиусов помещения, несколько попыток.
func _scatter(room: Dictionary, id: String, rmin: float, rmax: float, tries: int) -> void:
	for t in range(tries):
		var rr := _rng.randf_range(rmin, rmax)
		var a := _rng.randf_range(float(room.a[0]) + _deg(1.5, rr), float(room.a[1]) - _deg(1.5, rr))
		if _put(id, a, rr, "tangent", "", false, SCATTER_GAP, _rng.randf_range(-PI, PI)):
			return


## Ставит проп в полярную точку. orient: tangent (ширина вдоль дуги), tangent_out (то же, развёрнут
## на 180°: нос наружу), radial (ширина вдоль радиуса). Возвращает false, если место занято.
func _put(id: String, a: float, r: float, orient: String, variant: String = "", force: bool = false, gap: float = 0.5, yaw_extra: float = 0.0) -> bool:
	var sz := Props.size(id)
	var along := sz.x if orient != "radial" else sz.z
	var radial := sz.z if orient != "radial" else sz.x
	if yaw_extra != 0.0:
		along = maxf(sz.x, sz.z)
		radial = along
	var rect := {"a0": a - _deg(along * 0.5, r), "a1": a + _deg(along * 0.5, r), "r0": r - radial * 0.5, "r1": r + radial * 0.5}
	if not force and not _free(rect, gap):
		return false
	if not force and not _inside_own_room(rect):
		return false
	var node := _props.build(id, variant)
	node.position = SectorBuilder.polar(a, r)
	var yaw := -deg_to_rad(a)
	match orient:
		"tangent":
			yaw -= PI * 0.5
		"tangent_out":
			yaw += PI * 0.5
	node.rotation.y = yaw + yaw_extra
	_root.add_child(node)
	_taken.append(rect)
	count += 1
	var loot := ItemDb.container(id)
	if not loot.is_empty() and _rng.randf() < float(loot.chance):
		lootables.append({"kind": id, "pos": node.position, "room": _room_id})
	return true


## Углы пропа — в своём помещении (его не перекрыла полоса) и вне запретных прямоугольников.
func _inside_own_room(rect: Dictionary) -> bool:
	var foot := Rect2()
	var first := true
	for a in [float(rect.a0), float(rect.a1)]:
		for r in [float(rect.r0), float(rect.r1)]:
			var q := SectorBuilder.polar(a, r)
			if first:
				foot = Rect2(Vector2(q.x, q.z), Vector2.ZERO)
				first = false
			else:
				foot = foot.expand(Vector2(q.x, q.z))
			if String(SectorBuilder.owner_of(_rooms, q).get("id", "")) != _room_id:
				return false
	for z in _world_zones:
		if z.intersects(foot):
			return false
	return true


func _free(rect: Dictionary, gap: float) -> bool:
	var rm := (float(rect.r0) + float(rect.r1)) * 0.5
	var da := _deg(gap, maxf(rm, 1.0))
	for z in _zones:
		if _overlap(rect, z, 0.0, 0.0):
			return false
	for t in _taken:
		if _overlap(rect, t, da, gap):
			return false
	return true


func _overlap(a: Dictionary, b: Dictionary, da: float, dr: float) -> bool:
	return float(a.a0) - da < float(b.a1) and float(a.a1) + da > float(b.a0) and float(a.r0) - dr < float(b.r1) and float(a.r1) + dr > float(b.r0)


## Метры вдоль дуги радиуса r → градусы.
static func _deg(m: float, r: float) -> float:
	return rad_to_deg(m / maxf(r, 0.5))
