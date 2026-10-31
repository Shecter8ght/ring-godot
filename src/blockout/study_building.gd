@tool
extends Node3D
## Временная архитектура в метрах. Пять и девять этажей имеют реальную высоту.
## Отдельные узлы зданий сохраняются в сцене и заменяются готовыми ассетами.
## Интерьер (левел-дизайн зоны 1 «Пригород», 2026-10-19): у залов — мебель блоками (стеллажи, прилавки,
## верстаки — они же укрытия), перегородки с проёмами, свои ворота и двери; у квартир, офисов и домов —
## комнаты. Места лута, запертая дверь и ключ появляются только в игре (узел Gameplay, имена постоянные —
## одинаковые у всех игроков, по ним сеть находит контейнеры и двери).

const Geometry = preload("res://src/blockout/study_geometry.gd")
const LOOT_SCENE: PackedScene = preload("res://scenes/world/loot_container.tscn")
const DOOR_SCENE: PackedScene = preload("res://scenes/props/door.tscn")
const KEY_SCENE: PackedScene = preload("res://scenes/world/key_pickup.tscn")

@export_enum("mass", "apartments", "skeleton", "hall", "canopy", "bus", "crane", "house") var kind: String = "mass":
	set(value):
		kind = value
		_request_rebuild()
@export var footprint: Vector2 = Vector2(48.0, 12.0):
	set(value):
		footprint = Vector2(maxf(value.x,12.0),maxf(value.y,10.0)) if kind in ["skeleton","apartments"] else value
		_request_rebuild()
@export var floors: int = 5:
	set(value):
		floors = maxi(value,1)
		_request_rebuild()
@export var story_height: float = 3.0:
	set(value):
		story_height = maxf(value,1.0)
		_request_rebuild()
@export var label: String = ""
## Интерьер зала (kind = hall): shop, pharmacy, supermarket, cinema, terminal, depot, workshop, warehouse,
## server, gym, lockers, hangar, storeroom; пусто — пустой зал с проёмами посередине длинных стен, как раньше.
@export var interior: String = "":
	set(value):
		interior = value
		_request_rebuild()
## Таблица лута «по теме» (data/loot.json → tables) для стеллажей и комнат; пусто — по виду мебели.
@export var loot_theme: String = ""
## Доля комнат квартир, офисов и домов с местом лута (0 — без лута).
@export var loot_density: float = 0.0
## Машина внутри цеха или бокса: "" — нет, "bus" — автобус на смотровой, "car" — легковая на разборке.
@export var vehicle: String = ""
## Ключ запертой двери серверной (data/items.json); пусто — дверь не ставится.
@export var locked_key: String = ""
## Ключ, который лежит в дальнем кабинете верхнего этажа (офис); пусто — нет.
@export var key_item: String = ""
## Сейф в том же кабинете — таблица лута; пусто — нет.
@export var safe_table: String = ""
## Универсам: служебный коридор «Только для персонала» вдоль стены −X от входа до склада — дверь в зал у
## фасада, проём в склад (пролог, «Ярус»: обход мимо мародёров в зале, docs/design/prologue.md §4.5).
@export var staff_corridor: bool = false:
	set(value):
		staff_corridor = value
		_request_rebuild()
## Магазин: дверь в проёме входа, ширина, м (пролог: кофейня «Зерно» — закрыта, не заперта); 0 — открытый проём.
@export var entry_door: float = 0.0:
	set(value):
		entry_door = value
		_request_rebuild()

var generated: Node3D
var stair_origin: Vector2
var queued: bool = false
## Места лута: {at, kind, table, title, look, chance} — в координатах здания.
var _spots: Array[Dictionary] = []
var _doors: Array[Dictionary] = []
var _keys: Array[Dictionary] = []
## Лампы: точки в координатах здания (в игре — OmniLight в группе mall_lights, Balance.BLOCKOUT_LIGHTS).
var _lamps: PackedVector3Array = PackedVector3Array()

func _request_rebuild() -> void:
	if not is_inside_tree() or queued:
		return
	queued = true
	rebuild.call_deferred()

func _ready() -> void:
	rebuild()

func rebuild() -> void:
	queued = false
	if is_instance_valid(generated):
		generated.free()
	_spots.clear()
	_doors.clear()
	_keys.clear()
	_lamps.clear()
	generated = Node3D.new()
	generated.name = "_Geometry"
	add_child(generated)
	var g: RefCounted = Geometry.new(generated, Geometry.materials())
	match kind:
		"skeleton", "apartments":
			_multistory(g)
		"hall":
			_hall(g)
		"canopy":
			_canopy(g)
		"bus":
			_bus(g)
		"crane":
			_crane(g)
		"house":
			_house(g)
		_:
			_mass(g)
	g.finish()
	set_meta("height_m", float(floors) * story_height)
	set_meta("enterable", kind in ["skeleton", "apartments", "hall", "house"])
	_place_gameplay()

func _mass(g: RefCounted) -> void:
	var height: float = float(floors) * story_height
	g.box(Vector3(0, height * 0.5 - 0.1, 0), Vector3(footprint.x, height + 0.2, footprint.y), "wall")
	g.box(Vector3(0, height + 0.15, 0), Vector3(footprint.x + 0.5, 0.3, footprint.y + 0.5), "slab")
	var bays: int = maxi(2, int(footprint.x / 3.2))
	for level: int in range(floors):
		for bay: int in range(bays):
			var x: float = -footprint.x * 0.5 + (float(bay) + 0.5) * footprint.x / float(bays)
			for sign_z: float in [-1.0, 1.0]:
				g.box(Vector3(x, float(level) * story_height + 1.65, sign_z * (footprint.y * 0.5 + 0.015)), Vector3(1.4, 1.45, 0.035), "dark", false)

func _slab(g: RefCounted, y: float) -> void:
	# Лестничный проём 4.6 × 8.2 м остаётся открытым на всех этажах.
	var hx: float = stair_origin.x
	var hz: float = stair_origin.y
	var left: float = hx - 2.3
	var right: float = hx + 2.3
	var front: float = hz - 4.1
	var back: float = hz + 4.1
	var xmin: float = -footprint.x * 0.5
	var xmax: float = footprint.x * 0.5
	var zmin: float = -footprint.y * 0.5
	var zmax: float = footprint.y * 0.5
	for rect: Rect2 in [Rect2(xmin, zmin, left - xmin, footprint.y), Rect2(right, zmin, xmax - right, footprint.y), Rect2(left, zmin, right - left, front - zmin), Rect2(left, back, right - left, zmax - back)]:
		if rect.size.x > 0.01 and rect.size.y > 0.01:
			g.box(Vector3(rect.get_center().x, y - 0.14, rect.get_center().y), Vector3(rect.size.x, 0.28, rect.size.y), "slab")

func _multistory(g: RefCounted) -> void:
	stair_origin = Vector2(-footprint.x * 0.5 + 5.0, 0.0)
	var hx: float = stair_origin.x
	var base_y: float = 0.1
	g.box(Vector3(0, -0.18, 0), Vector3(footprint.x + 1.2, 0.56, footprint.y + 1.2), "concrete")
	for level: int in range(floors + 1):
		var y: float = base_y + float(level) * story_height
		if level > 0:
			_slab(g, y)
		# Южная площадка соединяет лестницу с перекрытием у проёма.
		g.box(Vector3(hx, y - 0.12, 3.45), Vector3(4.6, 0.24, 1.3), "concrete")
		if level == floors:
			continue
		var half_rise: float = story_height * 0.5
		g.stairs(Vector3(hx - 1.05, y, 2.8), Vector3(hx - 1.05, y + half_rise, -2.8), 1.8, 10, "concrete")
		g.box(Vector3(hx, y + half_rise - 0.12, -3.45), Vector3(4.6, 0.24, 1.3), "concrete")
		g.stairs(Vector3(hx + 1.05, y + half_rise, -2.8), Vector3(hx + 1.05, y + story_height, 2.8), 1.8, 10, "concrete")
		if kind == "skeleton":
			_skeleton_floor(g, y)
		else:
			_apartment_floor(g, y, level)
			_lamps.append(Vector3(hx + 3.2, y + story_height - 0.4, 0.0))
	if kind == "skeleton":
		var roof_y: float = base_y + float(floors) * story_height
		g.box(Vector3(0, roof_y + 0.5, -footprint.y * 0.5), Vector3(footprint.x, 1.0, 0.18), "concrete")
		g.box(Vector3(0, roof_y + 0.5, footprint.y * 0.5), Vector3(footprint.x, 1.0, 0.18), "concrete")
		for x: float in [-footprint.x * 0.5, footprint.x * 0.5]:
			g.box(Vector3(x, roof_y + 0.5, 0), Vector3(0.18, 1.0, footprint.y), "concrete")

func _skeleton_floor(g: RefCounted, y: float) -> void:
	var nx: int = maxi(2, int(footprint.x / 6.0))
	var nz: int = maxi(2, int(footprint.y / 6.0))
	for ix: int in range(nx + 1):
		for iz: int in range(nz + 1):
			var x: float = lerpf(-footprint.x * 0.5 + 0.3, footprint.x * 0.5 - 0.3, float(ix) / float(nx))
			var z: float = lerpf(-footprint.y * 0.5 + 0.3, footprint.y * 0.5 - 0.3, float(iz) / float(nz))
			if absf(x - stair_origin.x) < 3.0 and absf(z) < 4.2:
				continue
			g.box(Vector3(x, y + story_height * 0.5, z), Vector3(0.5, story_height, 0.5), "concrete")
	# Короткие непрозрачные ядра ограничивают обзор верхних этажей.
	g.box(Vector3(3.0, y + story_height * 0.5, 0), Vector3(0.25, story_height, footprint.y * 0.32), "concrete")
	for side: float in [-1.0, 1.0]:
		g.box(Vector3(0, y + 1.05, side * footprint.y * 0.5), Vector3(footprint.x, 0.09, 0.09), "steel", false)

func _apartment_floor(g: RefCounted, y: float, level: int) -> void:
	var bay_count: int = maxi(4, int(footprint.x / 3.0))
	var pitch: float = footprint.x / float(bay_count)
	for side: float in [-1.0, 1.0]:
		var z: float = side * footprint.y * 0.5
		for i: int in range(bay_count):
			var x: float = -footprint.x * 0.5 + (float(i) + 0.5) * pitch
			var entrance: bool = level == 0 and absf(x) < pitch * 0.65
			if not entrance:
				g.box(Vector3(x, y + 0.45, z), Vector3(pitch, 0.9, 0.3), "wall")
			g.box(Vector3(x, y + story_height - 0.3, z), Vector3(pitch, 0.6, 0.3), "wall")
			g.box(Vector3(x - pitch * 0.5, y + story_height * 0.5, z), Vector3(0.5, story_height, 0.3), "wall")
	for x: float in [-footprint.x * 0.5, footprint.x * 0.5]:
		g.box(Vector3(x, y + story_height * 0.5, 0), Vector3(0.3, story_height, footprint.y), "wall")
	# Сквозной коридор и простые комнаты; западная часть отдана лестнице и площадке перед коридором
	# (1,9 м от проёма — с лестницы на этаж проходят и мародёры).
	var x0: float = stair_origin.x + 4.2
	var room_count: int = maxi(1, int((footprint.x * 0.5 - x0) / 6.0))
	var room_w: float = (footprint.x * 0.5 - x0) / float(room_count)
	for i: int in range(room_count):
		var x: float = x0 + float(i) * room_w
		for side: float in [-1.0, 1.0]:
			g.box(Vector3(x, y + story_height * 0.5, side * (footprint.y * 0.25 + 0.6)), Vector3(0.16, story_height, footprint.y * 0.5 - 1.2), "wall")
			var door_x: float = x + room_w * 0.5
			# дверь 1,3 м: и под углом к сетке навигации проход для мародёров не схлопывается
			for edge: float in [-1.0, 1.0]:
				g.box(Vector3(door_x + edge * (room_w + 1.3) * 0.25, y + story_height * 0.5, side * 1.2), Vector3((room_w - 1.3) * 0.5, story_height, 0.16), "wall")
			g.box(Vector3(door_x, y + 2.6, side * 1.2), Vector3(1.3, 0.8, 0.16), "wall")
			# шкаф у наружной стены комнаты; в дальнем кабинете верхнего этажа — ключ и сейф
			var far: bool = level == floors - 1 and i == room_count - 1
			var wall_z: float = side * (footprint.y * 0.5 - 0.55)
			if loot_density > 0.0:
				# у входа в подъезд (первый этаж, середина фасада) шкаф — к другой стене комнаты, проём свободен
				var cab_x: float = NAN
				for k: float in [0.25, -0.25, 0.4, -0.4]:
					var cx: float = door_x + room_w * k
					if (level > 0 or absf(cx) >= pitch + 0.8) and cx > x + 0.6 and cx < x + room_w - 0.6:
						cab_x = cx
						break
				if not is_nan(cab_x):
					g.box(Vector3(cab_x, y + 1.0, wall_z), Vector3(1.0, 2.0, 0.5), "accent")
					_spot(Vector3(cab_x, y + _lp(), wall_z - side * 0.6), "cabinet", loot_theme, "", 0, loot_density)
			if far and side > 0.0 and key_item != "":
				_keys.append({"at": Vector3(door_x - room_w * 0.2, y + 0.8, side * (footprint.y * 0.25 + 0.6)), "key": key_item})
				g.box(Vector3(door_x - room_w * 0.2, y + 0.38, side * (footprint.y * 0.25 + 0.6)), Vector3(1.6, 0.76, 0.8), "accent")
			if far and side < 0.0 and safe_table != "":
				_spot(Vector3(door_x - room_w * 0.3, y, side * (footprint.y * 0.5 - 0.9)), "cabinet", safe_table, "Сейф", 1, 1.0)

func _hall(g: RefCounted) -> void:
	var h: float = story_height * float(floors)
	g.box(Vector3(0, -0.15, 0), Vector3(footprint.x, 0.3, footprint.y), "walk")
	g.box(Vector3(0, h, 0), Vector3(footprint.x + 0.8, 0.35, footprint.y + 0.8), "slab")
	var gaps: Dictionary = _hall_gaps(h)
	for side: float in [-1.0, 1.0]:
		var openings: Array = (gaps[side] as Array) + _hall_windows(h, side, gaps[side])
		_wall_x(g, side * footprint.y * 0.5, -footprint.x * 0.5, footprint.x * 0.5, 0.0, h, openings, 0.3)
	for x: float in [-footprint.x * 0.5, footprint.x * 0.5]:
		g.box(Vector3(x, h * 0.5, 0), Vector3(0.3, h, footprint.y), "wall")
	if interior == "":
		# Стойки задают масштаб помещения, но не готовое оформление.
		for x: float in [-footprint.x * 0.28, footprint.x * 0.28]:
			g.box(Vector3(x, 0.6, 1.5), Vector3(4.0, 1.2, 1.2), "accent")
		return
	call("_in_" + interior, g, h)
	if interior == "cinema":
		for sx: float in [-0.25, 0.25]:
			_lamps.append(Vector3(footprint.x * sx, minf(h - 0.5, 3.6), footprint.y * 0.5 - 4.0))
	elif not Engine.is_editor_hint():
		var lc: Dictionary = Balance.BLOCKOUT_LIGHTS
		var n: int = clampi(int(footprint.x / float(lc.step_m)), 1, int(lc.max))
		for i: int in range(n):
			_lamps.append(Vector3(-footprint.x * 0.5 + (float(i) + 0.5) * footprint.x / float(n), minf(h - 0.5, 4.0), 0.0))

## Проёмы в длинных стенах зала: {−1: [[x, ширина, высота], …], 1: […]} (−1 — сторона −Z).
func _hall_gaps(h: float) -> Dictionary:
	var hx: float = footprint.x * 0.5
	match interior:
		"shop":
			if entry_door > 0.0:
				return {1.0: [[0.0, entry_door, 2.2]], -1.0: [[hx - 2.0, 1.2, 2.2]]}
			return {1.0: [[0.0, 2.0, 2.4]], -1.0: [[hx - 2.0, 1.2, 2.2]]}
		"pharmacy":
			return {1.0: [[0.0, 2.0, 2.4]], -1.0: [[-hx + 2.0, 1.2, 2.2]]}
		"supermarket":
			return {1.0: [[-6.0, 3.0, 2.6], [6.0, 3.0, 2.6]], -1.0: [[0.0, 4.0, 3.8]]}
		"terminal":
			return {1.0: [[-footprint.x / 6.0, 2.4, 2.6], [footprint.x / 6.0, 2.4, 2.6]], -1.0: [[0.0, 3.0, 2.6]]}
		"cinema":
			return {1.0: [[0.0, 3.0, 2.8]], -1.0: [[hx - 3.0, 1.4, 2.2]]}
		"depot":
			return {1.0: [[-footprint.x * 0.25, 5.0, 4.6], [footprint.x * 0.25, 5.0, 4.6]], -1.0: [[0.0, 1.2, 2.2]]}
		"workshop":
			return {1.0: [[0.0, 4.0, 4.0]], -1.0: [[-hx + 3.0, 1.2, 2.2]]}
		"warehouse":
			return {1.0: [[0.0, 4.0, 4.2]], -1.0: [[-hx + 3.0, 1.2, 2.2]]}
		"server":
			return {1.0: [[footprint.x * 0.25, 3.0, 3.5]], -1.0: [[hx - 3.0, 1.2, 2.2]]}
		"gym":
			return {1.0: [[0.0, 2.4, 2.6]], -1.0: [[hx - 3.0, 1.4, 2.2]]}
		"lockers":
			return {1.0: [[-hx + 2.5, 1.2, 2.2]], -1.0: [[hx - 2.5, 1.2, 2.2]]}
		"hangar":
			return {-1.0: [[0.0, minf(6.0, footprint.x - 4.0), minf(4.2, h - 0.6)]], 1.0: [[hx - 2.5, 1.2, 2.1]]}
		"storeroom":
			return {-1.0: [[-hx + 2.0, 1.2, 2.2]], 1.0: []}
	return {1.0: [[0.0, 3.0, h - 1.6]], -1.0: [[0.0, 3.0, h - 1.6]]}

## Окна зала с интерьером (дневной свет внутрь, стрельба через окна): витрины у магазинов, высокие ленточные
## окна у цехов и складов (не дотянуться), окна фойе у кинотеатра; в серверную окон нет (заперта на ключ).
## Окно — [x, ширина, верх, низ]; мимо дверей side-стороны.
func _hall_windows(h: float, side: float, doors: Array) -> Array:
	if interior == "":
		return []
	var hx: float = footprint.x * 0.5
	var spec: Array = []  # [низ, верх, ширина, шаг]
	match interior:
		"shop", "pharmacy":
			spec = [0.7, 2.5, 2.0, 3.0] if side > 0.0 else [1.4, 2.3, 1.0, 6.0]
		"supermarket":
			spec = [0.5, 2.8, 3.0, 4.0] if side > 0.0 else []
		"terminal":
			spec = [1.0, minf(4.5, h - 1.0), 2.4, 4.0]
		"cinema":
			spec = [0.8, 3.0, 2.4, 4.0] if side > 0.0 else []
		"depot", "warehouse", "workshop", "server", "gym":
			spec = [maxf(2.6, h - 3.0), h - 0.8, 3.0, 5.0]
		"hangar":
			spec = [maxf(2.6, h - 2.2), h - 0.6, 2.0, 4.0]
		"lockers", "storeroom":
			spec = [1.8, 2.6, 1.0, 4.0]
	if spec.is_empty() or float(spec[1]) - float(spec[0]) < 0.4:
		return []
	var out: Array = []
	var w: float = float(spec[2])
	var x: float = -hx + float(spec[3]) * 0.5
	while x < hx - w * 0.5 - 0.6:
		var clear: bool = x - w * 0.5 > -hx + 0.6
		for d: Array in doors:
			if absf(x - float(d[0])) < (w + float(d[1])) * 0.5 + 0.8:
				clear = false
		if interior == "server" and x - w * 0.5 < -hx + 12.5:
			clear = false
		if clear:
			out.append([x, w, float(spec[1]), float(spec[0])])
		x += float(spec[3])
	return out

## Стена вдоль X (z = const) от x0 до x1, низ y0, высота hh; проёмы [x, ширина, высота, низ?] — низ
## у окна > 0 (подоконник). Толщина t.
func _wall_x(g: RefCounted, z: float, x0: float, x1: float, y0: float, hh: float, gaps: Array, t: float = 0.16) -> void:
	var cuts: Array = gaps.duplicate()
	cuts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var x: float = x0
	for c: Array in cuts:
		var a: float = float(c[0]) - float(c[1]) * 0.5
		var b: float = float(c[0]) + float(c[1]) * 0.5
		var top: float = minf(float(c[2]), hh)
		var low: float = float(c[3]) if c.size() > 3 else 0.0
		if a - x > 0.01:
			g.box(Vector3((x + a) * 0.5, y0 + hh * 0.5, z), Vector3(a - x, hh, t), "wall")
		if hh - top > 0.01:
			g.box(Vector3(float(c[0]), y0 + (hh + top) * 0.5, z), Vector3(b - a, hh - top, t), "wall")
		if low > 0.01:
			g.box(Vector3(float(c[0]), y0 + low * 0.5, z), Vector3(b - a, low, t), "wall")
		x = b
	if x1 - x > 0.01:
		g.box(Vector3((x + x1) * 0.5, y0 + hh * 0.5, z), Vector3(x1 - x, hh, t), "wall")

## То же вдоль Z (x = const) от z0 до z1.
func _wall_z(g: RefCounted, x: float, z0: float, z1: float, y0: float, hh: float, gaps: Array, t: float = 0.16) -> void:
	var cuts: Array = gaps.duplicate()
	cuts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
	var z: float = z0
	for c: Array in cuts:
		var a: float = float(c[0]) - float(c[1]) * 0.5
		var b: float = float(c[0]) + float(c[1]) * 0.5
		var top: float = minf(float(c[2]), hh)
		var low: float = float(c[3]) if c.size() > 3 else 0.0
		if a - z > 0.01:
			g.box(Vector3(x, y0 + hh * 0.5, (z + a) * 0.5), Vector3(t, hh, a - z), "wall")
		if hh - top > 0.01:
			g.box(Vector3(x, y0 + (hh + top) * 0.5, float(c[0])), Vector3(t, hh - top, b - a), "wall")
		if low > 0.01:
			g.box(Vector3(x, y0 + low * 0.5, float(c[0])), Vector3(t, low, b - a), "wall")
		z = b
	if z1 - z > 0.01:
		g.box(Vector3(x, y0 + hh * 0.5, (z + z1) * 0.5), Vector3(t, hh, z1 - z), "wall")

## Место лута: kind — вид мебели data/loot.json → containers (имя, время обыска, доля с лутом);
## look — вид ящика (LootContainer.Look), chance < 0 — доля из данных.
func _spot(at: Vector3, kind_id: String, table: String = "", title: String = "", look: int = 0, chance: float = -1.0) -> void:
	_spots.append({"at": at, "kind": kind_id, "table": table, "title": title, "look": look, "chance": chance})

## Блок мебели с местом лута перед ним (со стороны face — единичный вектор в плоскости XZ).
func _furniture(g: RefCounted, at: Vector3, size: Vector3, face: Vector3, kind_id: String, table: String = "",
		title: String = "", chance: float = -1.0, key: String = "accent") -> void:
	g.box(at, size, key)
	var reach: float = absf(face.x) * size.x * 0.5 + absf(face.z) * size.z * 0.5 + 0.45
	_spot(Vector3(at.x, at.y - size.y * 0.5 + _lp(), at.z) + face * reach, kind_id, table, title, 0, chance)

## Высота точки лута над полом (Balance; в редакторе автозагрузок нет — там места лута не ставятся).
func _lp() -> float:
	return 0.6 if Engine.is_editor_hint() else float(Balance.LOOT_POINT_HEIGHT)

func _theme(fallback: String) -> String:
	return loot_theme if loot_theme != "" else fallback

# ---------------------------------------------------------------- интерьеры залов (пол — y = 0)

## Магазин: стеллажи вдоль торца, две стойки посередине, касса у входа, подсобка у восточного торца.
func _in_shop(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var back: float = hx - 4.0
	var ph: float = minf(h, 3.2)
	_wall_z(g, back, -hz, hz, 0.0, ph, [[0.0, 1.2, 2.2]])
	g.box(Vector3(-hx + 0.45, 1.0, 0), Vector3(0.6, 2.0, footprint.y - 2.0), "accent")
	for z: float in [-hz * 0.5, hz * 0.5]:
		_spot(Vector3(-hx + 1.2, _lp(), z), "shelf_retail", _theme("shelf"), "", 0, 0.3)
	var unit: float = minf(6.0, footprint.x * 0.3)
	for z: float in [-footprint.y * 0.22, footprint.y * 0.22]:
		_furniture(g, Vector3(-footprint.x * 0.12, 0.8, z), Vector3(unit, 1.6, 0.8), Vector3(0, 0, -signf(z)), "shelf_retail", _theme("shelf"), "", 0.3)
	_furniture(g, Vector3(back - 1.6, 0.5, hz * 0.4), Vector3(0.7, 1.0, 3.0), Vector3(1, 0, 0), "checkout", "register")
	if entry_door > 0.0:
		_doors.append({"name": "EntryDoor", "at": Vector3(-entry_door * 0.5, 0.0, hz), "yaw": 0.0, "width": entry_door, "key": ""})
	g.box(Vector3(hx - 0.45, 1.0, 0), Vector3(0.6, 2.0, footprint.y - 2.4), "accent")
	_spot(Vector3(hx - 1.2, _lp(), -hz * 0.4), "shelf_warehouse", _theme("storage"))
	_furniture(g, Vector3(back + 1.4, 0.6, hz - 1.4), Vector3(1.2, 1.2, 1.2), Vector3(0, 0, -1), "box_stack", _theme("storage"))

## Аптека: прилавок поперёк зала, стеллажи и сейф за ним, витрины у входа.
func _in_pharmacy(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var cx0: float = -hx + 0.6
	var cx1: float = hx - 2.6
	g.box(Vector3((cx0 + cx1) * 0.5, 0.55, 1.0), Vector3(cx1 - cx0, 1.1, 0.7), "accent")
	for x: float in [-footprint.x * 0.25, footprint.x * 0.15]:
		_spot(Vector3(x, _lp(), 0.2), "checkout", "register")
	var sx0: float = -hx + 3.5
	var sx1: float = hx - 1.0
	g.box(Vector3((sx0 + sx1) * 0.5, 1.1, -hz + 0.5), Vector3(sx1 - sx0, 2.2, 0.6), "accent")
	for k: int in range(4):
		_spot(Vector3(lerpf(sx0 + 1.5, sx1 - 1.5, float(k) / 3.0), _lp(), -hz + 1.2), "shelf_warehouse", _theme("pharmacy"))
	_furniture(g, Vector3(footprint.x * 0.25, 0.9, -1.6), Vector3(6.0, 1.8, 0.6), Vector3(0, 0, 1), "shelf_warehouse", _theme("pharmacy"))
	_spot(Vector3(-hx + 1.0, 0.0, -1.2), "cabinet", _theme("pharmacy"), "Сейф", 1, 1.0)
	for x: float in [-footprint.x * 0.25, footprint.x * 0.25]:
		_furniture(g, Vector3(x, 0.6, hz - 2.2), Vector3(4.0, 1.2, 0.6), Vector3(0, 0, -1), "shelf_retail", _theme("pharmacy"), "", 0.3)

## Универсам: ряды стеллажей проходами с севера на юг, холодильники у торцов, кассы у входа,
## склад за перегородкой с рампой и конторкой.
func _in_supermarket(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var zb: float = -hz + 6.0
	# служебный коридор: ширина в свету 2 м (правило масштаба E), стена до потолка; дверь у фасада, проём в склад
	var xw: float = -hx + 2.3
	var store_gaps: Array = [[-hx * 0.5, 2.4, 2.6], [hx * 0.5, 2.4, 2.6]]
	if staff_corridor:
		store_gaps.append([(-hx + xw) * 0.5, 1.2, 2.2])
		var dz: float = hz - 2.6
		_wall_z(g, xw, zb, hz, 0.0, h, [[dz, 1.2, 2.2]])
		_doors.append({"name": "StaffDoor", "at": Vector3(xw, 0.0, dz - 0.6), "yaw": -PI * 0.5, "width": 1.2, "key": ""})
	_wall_x(g, zb, -hx, hx, 0.0, minf(h, 4.0), store_gaps)
	for x: float in [-hx + 6.0, -hx + 12.0, hx - 12.0, hx - 6.0]:
		_furniture(g, Vector3(x, 0.7, -hz + 3.0), Vector3(1.2, 1.4, 1.2), Vector3(0, 0, 1), "pallet_boxes", _theme("grocery"))
	for seg: Vector2 in [Vector2(-hx + 1.0, -3.0), Vector2(3.0, hx - 1.0)]:
		g.box(Vector3((seg.x + seg.y) * 0.5, 1.3, -hz + 0.75), Vector3(seg.y - seg.x, 2.6, 0.9), "accent")
		_spot(Vector3((seg.x + seg.y) * 0.5, _lp(), -hz + 1.6), "shelf_warehouse", _theme("grocery"))
	_furniture(g, Vector3(hx - 2.5, 0.38, zb - 1.5), Vector3(1.6, 0.75, 0.8), Vector3(0, 0, 1), "desk", "office")
	var row_z0: float = zb + 3.0
	var row_z1: float = hz - 7.0
	var zc: float = (row_z0 + row_z1) * 0.5
	var run: float = row_z1 - row_z0
	for x: float in [-15.0, -9.0, -3.0, 3.0, 9.0, 15.0]:
		if absf(x) > hx - 2.0:
			continue
		g.box(Vector3(x, 0.95, zc), Vector3(1.0, 1.9, run), "accent")
		for sx: float in [-1.0, 1.0]:
			for dz: float in [-run * 0.25, run * 0.25]:
				_spot(Vector3(x + sx * 0.95, _lp(), zc + dz), "shelf_retail", _theme("grocery"), "", 0, 0.2)
	var fz0: float = zb + 1.0
	var fz1: float = hz - 4.0
	for sx: float in [-1.0, 1.0]:
		# у стены коридора холодильников нет — проход вдоль неё
		if staff_corridor and sx < 0.0:
			continue
		g.box(Vector3(sx * (hx - 0.55), 1.0, (fz0 + fz1) * 0.5), Vector3(0.8, 2.0, fz1 - fz0), "steel")
		_spot(Vector3(sx * (hx - 1.4), _lp(), (fz0 + fz1) * 0.5), "shelf_retail", _theme("grocery"), "Холодильник", 0, 0.3)
	for x: float in [-13.0, -10.0, 10.0, 13.0]:
		if absf(x) > hx - 2.0:
			continue
		_furniture(g, Vector3(x, 0.5, hz - 4.5), Vector3(0.7, 1.0, 2.6), Vector3(signf(x), 0, 0), "checkout", "register")

## Кинотеатр: фойе с буфетом и кассой; зал — ряды на ступенях к экрану, сцена, запасной выход у экрана.
func _in_cinema(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var zl: float = hz - 8.0
	_wall_x(g, zl, -hx, hx, 0.0, h, [[-hx + 1.4, 1.6, 2.6], [hx - 1.4, 1.6, 2.6]])
	_furniture(g, Vector3(0, 0.55, zl + 3.0), Vector3(7.0, 1.1, 0.8), Vector3(0, 0, 1), "kiosk", "kiosk", "Буфет")
	g.box(Vector3(hx - 2.5, 1.2, hz - 2.3), Vector3(2.4, 2.4, 2.0), "accent")
	_spot(Vector3(hx - 2.5, _lp(), hz - 3.8), "checkout", "register", "Касса кинотеатра")
	g.box(Vector3(-hx + 3.0, 0.25, hz - 3.0), Vector3(4.0, 0.5, 0.6), "accent")
	# экран над сценой, сцена (запасной выход у восточного края остаётся свободным)
	g.box(Vector3(0, 5.0, -hz + 0.35), Vector3(footprint.x - 6.0, 4.4, 0.2), "dark", false)
	g.box(Vector3(-2.0, 0.4, -hz + 1.6), Vector3(footprint.x - 6.0, 0.8, 2.6), "concrete")
	# ряды: пандус со ступенями (физика — по наклонной), под ним заполнение, на ступенях — ряды кресел
	var z0: float = -hz + 6.0
	var z1: float = zl - 1.0
	var rows: int = maxi(3, int((z1 - z0) / 1.1))
	var rise: float = 0.3 * float(rows)
	var w: float = footprint.x - 5.0
	g.stairs(Vector3(0, 0, z0), Vector3(0, rise, z1), w, rows, "concrete")
	var step_run: float = (z1 - z0) / float(rows)
	for i: int in range(rows):
		var zi: float = z0 + (float(i) + 0.5) * step_run
		var yi: float = rise * float(i + 1) / float(rows)
		g.box(Vector3(0, yi * 0.5 - 0.1, zi), Vector3(w, maxf(0.05, yi - 0.2), step_run), "concrete", false)
		if yi > 0.45:
			g.collision_box(Vector3(0, (yi - 0.3) * 0.5, zi), Vector3(w, yi - 0.3, step_run))
		var half: float = w * 0.5
		var seat: float = half - 1.1
		for sx: float in [-1.0, 1.0]:
			g.box(Vector3(sx * (0.8 + seat * 0.5), yi + 0.25, zi + 0.2), Vector3(seat, 0.5, 0.45), "accent")
	g.box(Vector3(0, rise - 0.12, (z1 + zl) * 0.5), Vector3(w, 0.24, zl - z1 - 0.1), "concrete")
	g.collision_box(Vector3(0, (rise - 0.3) * 0.5, (z1 + zl) * 0.5), Vector3(w, rise - 0.3, zl - z1 - 0.1))
	g.box(Vector3(0, rise * 0.5 - 0.1, (z1 + zl) * 0.5), Vector3(w, rise - 0.2, zl - z1 - 0.1), "concrete", false)
	_furniture(g, Vector3(hx - 1.2, 1.0, -hz + 4.5), Vector3(0.6, 2.0, 1.2), Vector3(-1, 0, 0), "cabinet", "office", "Шкаф киномеханика")

## Вокзал / автостанция: зал ожидания со скамьями, кассы за перегородкой, служебная комната, киоск.
func _in_terminal(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var xs: float = -hx + 7.0
	var xt: float = hx - 8.0
	_wall_z(g, xs, -hz, hz, 0.0, 3.2, [[0.0, 1.2, 2.2]])
	_wall_z(g, xt, -hz, hz, 0.0, 3.2, [[-hz + 1.6, 1.2, 2.2]])
	g.box(Vector3(-hx + 0.5, 1.0, 0), Vector3(0.6, 2.0, footprint.y - 2.0), "accent")
	_spot(Vector3(-hx + 1.3, _lp(), -hz * 0.4), "box_stack", _theme("storage"))
	_spot(Vector3(-hx + 1.3, _lp(), hz * 0.4), "box_stack", _theme("storage"))
	g.box(Vector3(xt - 0.45, 0.55, hz * 0.3), Vector3(0.6, 1.1, 3.5), "accent")
	_furniture(g, Vector3(hx - 3.0, 0.38, 0.5), Vector3(2.0, 0.75, 1.0), Vector3(-1, 0, 0), "desk", "office")
	_furniture(g, Vector3(hx - 0.5, 1.0, -hz + 2.6), Vector3(0.6, 2.0, 1.2), Vector3(-1, 0, 0), "cabinet", "office")
	_spot(Vector3(xt + 0.8, _lp(), hz * 0.3), "checkout", "register", "Касса")
	var bench_x: Array[float] = [xs + 4.0, (xs + xt) * 0.5, xt - 6.0]
	for x: float in bench_x:
		for z: float in [-hz * 0.35, hz * 0.35]:
			g.box(Vector3(x, 0.23, z), Vector3(4.0, 0.45, 0.55), "accent")
	g.box(Vector3(xs + 2.5, 1.2, hz - 1.6), Vector3(2.6, 2.4, 1.8), "accent")
	_spot(Vector3(xs + 2.5, _lp(), hz - 3.0), "kiosk", "kiosk", "Киоск")
	_furniture(g, Vector3(xt - 4.0, 0.9, -hz + 0.6), Vector3(3.0, 1.8, 0.6), Vector3(0, 0, 1), "cabinet", _theme("storage"), "Камера хранения", 0.5)

## Цех / депо: двое ворот, смотровые места, антресоль с конторкой и лестницей, стеллажи под ней,
## верстаки вдоль задней стены; машина на смотровой (vehicle).
func _in_depot(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	for x: float in [-footprint.x * 0.25, footprint.x * 0.25]:
		g.box(Vector3(x, 0.01, 0), Vector3(1.0, 0.02, footprint.y * 0.5), "dark", false)
	if vehicle == "bus":
		g.box(Vector3(-footprint.x * 0.25, 1.65, -footprint.y * 0.05), Vector3(2.6, 2.7, minf(12.0, footprint.y - 6.0)), "bus")
	var ym: float = minf(3.2, h - 2.4)
	var mx: float = -hx + 8.0
	g.box(Vector3(-hx + 4.0, ym - 0.12, 0), Vector3(8.0, 0.24, footprint.y - 0.6), "slab")
	var z_col: float = -hz + 1.0
	while z_col < hz - 0.5:
		g.box(Vector3(mx, ym * 0.5, z_col), Vector3(0.3, ym, 0.3), "steel")
		z_col += 6.0
	g.box(Vector3(mx, ym + 0.5, -1.8), Vector3(0.06, 1.0, footprint.y - 4.2), "steel")
	g.stairs(Vector3(mx + 5.5, 0, hz - 1.5), Vector3(mx, ym, hz - 1.5), 1.2, 16, "steel")
	_furniture(g, Vector3(-hx + 4.0, ym + 0.38, -hz + 2.0), Vector3(1.8, 0.75, 0.9), Vector3(0, 0, 1), "desk", "office", "Стол мастера")
	_furniture(g, Vector3(-hx + 0.5, ym + 1.0, -1.0), Vector3(0.6, 2.0, 1.2), Vector3(1, 0, 0), "cabinet", "office")
	g.box(Vector3(-hx + 0.5, 1.2, 0), Vector3(0.6, minf(2.4, ym - 0.3), footprint.y - 2.0), "accent")
	for z: float in [-hz * 0.5, 0.0, hz * 0.5]:
		_spot(Vector3(-hx + 1.3, _lp(), z), "shelf_warehouse", _theme("components"))
	var bx: float = mx + 4.0
	while bx < hx - 3.0:
		_furniture(g, Vector3(bx, 0.45, -hz + 0.8), Vector3(2.2, 0.9, 0.9), Vector3(0, 0, 1), "cabinet", "workshop", "Верстак", 0.5, "steel")
		bx += 9.0
	for p: Vector2 in [Vector2(hx - 1.5, hz - 1.5), Vector2(hx - 2.4, hz - 1.5), Vector2(hx - 1.5, hz - 2.4)]:
		g.box(Vector3(p.x, 0.45, p.y), Vector3(0.6, 0.9, 0.6), "rust")
	g.box(Vector3(mx + 2.0, 0.5, -hz + 2.6), Vector3(1.2, 1.0, 1.2), "dark")

## Мастерская: станки двумя рядами, верстаки у торцов, инструментальная кладовка в углу.
func _in_workshop(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	for z: float in [-footprint.y * 0.18, footprint.y * 0.18]:
		for x: float in [-footprint.x * 0.27, -footprint.x * 0.07, footprint.x * 0.13]:
			g.box(Vector3(x, 0.75, z), Vector3(2.4, 1.5, 1.2), "steel")
	for sx: float in [-1.0, 1.0]:
		g.box(Vector3(sx * (hx - 0.6), 0.45, 1.0), Vector3(0.9, 0.9, footprint.y - 8.0), "steel")
		for z: float in [-hz * 0.25, hz * 0.45]:
			_spot(Vector3(sx * (hx - 1.5), _lp(), z), "cabinet", _theme("workshop"), "Верстак", 0, 0.5)
	var cx: float = hx - 8.0
	var cz: float = -hz + 4.0
	_wall_x(g, cz, cx, hx, 0.0, 3.0, [[hx - 6.0, 1.2, 2.2]])
	_wall_z(g, cx, -hz, cz, 0.0, 3.0, [])
	_furniture(g, Vector3(hx - 0.5, 1.0, -hz + 2.0), Vector3(0.6, 2.0, 1.4), Vector3(-1, 0, 0), "cabinet", "components", "Шкаф с инструментом", 0.8)
	_furniture(g, Vector3(hx - 3.0, 1.0, -hz + 0.5), Vector3(2.0, 2.0, 0.6), Vector3(0, 0, 1), "shelf_warehouse", "tools")

## Склад: ряды стеллажей с проходом посередине, поддоны у ворот.
func _in_warehouse(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var z: float = -hz + 2.0
	while z < hz - 4.5:
		for seg: Vector2 in [Vector2(-hx + 1.5, -2.5), Vector2(2.5, hx - 1.5)]:
			if seg.y - seg.x < 2.0:
				continue
			g.box(Vector3((seg.x + seg.y) * 0.5, 1.5, z), Vector3(seg.y - seg.x, 3.0, 1.1), "steel")
			_spot(Vector3((seg.x + seg.y) * 0.5, _lp(), z + 1.0), "shelf_warehouse", _theme("storage"))
		z += 4.5
	for x: float in [-3.5, 3.5]:
		_furniture(g, Vector3(x, 0.5, hz - 2.5), Vector3(1.2, 1.0, 1.2), Vector3(0, 0, 1), "pallet_boxes", _theme("storage"))

## Техкорпус: цех со станками и кабельными барабанами, серверная за запертой дверью (locked_key).
func _in_server(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var xs: float = -hx + 12.0
	_wall_z(g, xs, -hz, hz, 0.0, h, [[0.0, 1.0, 2.2]])
	if locked_key != "":
		_doors.append({"name": "VaultDoor", "at": Vector3(xs, 0.0, -0.5), "yaw": -PI * 0.5, "width": 1.0, "key": locked_key})
	for x: float in [-hx + 3.0, -hx + 6.0, -hx + 9.0]:
		g.box(Vector3(x, 1.0, -0.6), Vector3(0.8, 2.0, footprint.y - 5.0), "dark")
		for z: float in [-hz * 0.45, hz * 0.3]:
			_spot(Vector3(x + 0.85, _lp(), z), "cabinet", "server_rack", "Серверная стойка", 0, 0.6)
	_spot(Vector3(-hx + 1.0, 0.0, hz - 1.2), "cabinet", "security", "Сейф", 1, 1.0)
	for x: float in [-footprint.x * 0.05, footprint.x * 0.2, footprint.x * 0.38]:
		g.box(Vector3(x, 1.0, -hz * 0.3), Vector3(3.0, 2.0, 2.0), "steel")
	for p: Vector2 in [Vector2(footprint.x * 0.1, hz * 0.45), Vector2(footprint.x * 0.32, hz * 0.4)]:
		g.box(Vector3(p.x, 0.8, p.y), Vector3(1.6, 1.6, 1.0), "rust")
	_furniture(g, Vector3(hx - 2.5, 0.38, -hz + 1.5), Vector3(1.8, 0.75, 0.9), Vector3(0, 0, 1), "desk", "office", "Пульт")
	_furniture(g, Vector3(hx - 0.5, 1.0, hz - 2.0), Vector3(0.6, 2.0, 1.2), Vector3(-1, 0, 0), "cabinet", "components")

## Спортзал: трибуны у северной стены, снаряды, стойки щитов, инвентарная в углу.
func _in_gym(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var w: float = footprint.x - 8.0
	var rows: int = 5
	var z0: float = -hz + 6.0
	var z1: float = -hz + 1.0
	var rise: float = 2.0
	g.stairs(Vector3(0, 0, z0), Vector3(0, rise, z1), w, rows, "concrete")
	var step_run: float = (z0 - z1) / float(rows)
	for i: int in range(rows):
		var zi: float = z0 - (float(i) + 0.5) * step_run
		var yi: float = rise * float(i + 1) / float(rows)
		g.box(Vector3(0, yi * 0.5 - 0.1, zi), Vector3(w, maxf(0.05, yi - 0.2), step_run), "concrete", false)
		if yi > 0.45:
			g.collision_box(Vector3(0, (yi - 0.3) * 0.5, zi), Vector3(w, yi - 0.3, step_run))
	for p: Vector2 in [Vector2(-6.0, 3.0), Vector2(5.0, -2.0), Vector2(0.0, 8.0)]:
		g.box(Vector3(p.x, 0.6, p.y), Vector3(1.6, 1.2, 0.6), "accent")
	for sx: float in [-1.0, 1.0]:
		g.box(Vector3(sx * (hx - 1.0), 1.5, 2.0), Vector3(0.3, 3.0, 0.3), "steel")
		g.box(Vector3(sx * (hx - 1.3), 3.2, 2.0), Vector3(0.1, 1.1, 1.8), "stripe", false)
	_wall_x(g, hz - 6.0, hx - 7.0, hx, 0.0, 3.0, [[hx - 3.5, 1.2, 2.2]])
	_wall_z(g, hx - 7.0, hz - 6.0, hz, 0.0, 3.0, [])
	_furniture(g, Vector3(hx - 1.2, 0.6, hz - 1.2), Vector3(1.4, 1.2, 1.4), Vector3(-1, 0, 0), "box_stack", _theme("sport"))
	_furniture(g, Vector3(hx - 0.5, 1.0, hz - 4.0), Vector3(0.6, 2.0, 1.4), Vector3(-1, 0, 0), "cabinet", _theme("sport"))

## Раздевалки: ряды шкафчиков и скамьи.
func _in_lockers(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var x: float = -hx + 5.0
	while x < hx - 4.0:
		g.box(Vector3(x, 0.95, -0.6), Vector3(0.5, 1.9, footprint.y - 3.2), "steel")
		for sx: float in [-1.0, 1.0]:
			_spot(Vector3(x + sx * 0.7, _lp(), -hz * 0.3), "cabinet", _theme("sport"), "Шкафчик", 0, 0.35)
		g.box(Vector3(x + 1.6, 0.22, -0.6), Vector3(0.4, 0.45, footprint.y - 4.0), "accent")
		x += 4.0

## Бокс / ангар: ворота на −Z, дверь сзади, верстак и шкаф у восточного торца, стеллаж у западного,
## покрышки и кран-балка; машина в середине (vehicle = car — на разборке; машину заказа ставит сцена мест).
func _in_hangar(g: RefCounted, h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	_furniture(g, Vector3(hx - 0.6, 0.45, -1.0), Vector3(0.9, 0.9, minf(4.0, footprint.y - 5.0)), Vector3(-1, 0, 0), "cabinet", _theme("workshop"), "Верстак", 1.0, "steel")
	_furniture(g, Vector3(hx - 0.45, 1.0, hz - 2.6), Vector3(0.6, 2.0, 1.2), Vector3(-1, 0, 0), "cabinet", "components", "Шкаф с инструментом", 0.8)
	g.box(Vector3(-hx + 0.45, 1.1, 0.4), Vector3(0.6, 2.2, footprint.y - 3.6), "accent")
	_spot(Vector3(-hx + 1.2, _lp(), 1.0), "shelf_warehouse", "components")
	g.box(Vector3(-hx + 1.6, 0.5, hz - 1.5), Vector3(1.2, 1.0, 1.2), "dark")
	g.box(Vector3(0, minf(h - 0.6, 4.6), 0), Vector3(0.25, 0.3, footprint.y - 0.6), "steel", false)
	if vehicle == "car":
		g.box(Vector3(0, 0.75, 0.6), Vector3(1.8, 0.9, 4.4), "rust")
		g.box(Vector3(0, 1.45, 0.9), Vector3(1.6, 0.6, 2.2), "dark")
		for p: Vector2 in [Vector2(-0.8, -0.8), Vector2(0.8, -0.8), Vector2(-0.8, 2.0), Vector2(0.8, 2.0)]:
			g.box(Vector3(p.x, 0.16, p.y), Vector3(0.3, 0.32, 0.4), "wall")
		_spot(Vector3(1.4, _lp(), -1.2), "box_stack", "components", "Детали с разборки", 0, 1.0)

## Кладовая: стеллажи у трёх стен, вход с −Z у западного угла (тупик — лучший лут глубже).
func _in_storeroom(g: RefCounted, _h: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	g.box(Vector3(0, 1.1, hz - 0.45), Vector3(footprint.x - 1.0, 2.2, 0.6), "accent")
	for x: float in [-hx * 0.5, hx * 0.4]:
		_spot(Vector3(x, _lp(), hz - 1.2), "shelf_warehouse", _theme("components"))
	g.box(Vector3(hx - 0.45, 1.1, -0.3), Vector3(0.6, 2.2, footprint.y - 2.2), "accent")
	g.box(Vector3(-hx + 0.45, 1.1, 0.9), Vector3(0.6, 2.2, footprint.y - 3.6), "accent")
	_spot(Vector3(-hx + 1.2, _lp(), 1.0), "shelf_warehouse", _theme("components"))

# ---------------------------------------------------------------- частный дом

## Дом в 1–2 этажа: двери спереди и сзади, окна, три комнаты на этаже, лестница вдоль западной стены.
func _house(g: RefCounted) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var s: float = story_height
	var y0: float = 0.05
	g.box(Vector3(0, -0.1, 0), Vector3(footprint.x + 0.4, 0.3, footprint.y + 0.4), "concrete")
	var stair_z1: float = hz - 1.2
	var stair_z0: float = stair_z1 - 4.4
	for level: int in range(floors):
		var y: float = y0 + float(level) * s
		var win: Array = []
		var nwin: int = maxi(1, int(footprint.x / 3.5))
		for k: int in range(nwin):
			win.append([-hx + (float(k) + 0.5) * footprint.x / float(nwin), 1.1, 2.1, 0.9])
		for side: float in [-1.0, 1.0]:
			var openings: Array = []
			for wv: Array in win:
				var door_x: float = footprint.x * 0.15 if side > 0.0 else -footprint.x * 0.2
				if level == 0 and absf(float(wv[0]) - door_x) < 1.3:
					continue
				openings.append(wv)
			if level == 0:
				openings.append([footprint.x * 0.15 if side > 0.0 else -footprint.x * 0.2, 1.2 if side > 0.0 else 1.1, 2.1])
			_wall_x(g, side * (hz - 0.15), -hx, hx, y, s, openings, 0.3)
		for side: float in [-1.0, 1.0]:
			_wall_z(g, side * (hx - 0.15), -hz + 0.3, hz - 0.3, y, s, [[0.0, 1.1, 2.1, 0.9]], 0.3)
		var px: float = -footprint.x * 0.1
		_wall_z(g, px, -hz + 0.3, hz - 0.3, y, s, [[footprint.y * 0.2, 1.1, 2.1]])
		var pz: float = -footprint.y * 0.1
		_wall_x(g, pz, px, hx - 0.3, y, s, [[(px + hx) * 0.5, 1.1, 2.1]])
		if level > 0:
			for rect: Rect2 in [Rect2(-hx, -hz, footprint.x, stair_z0 + hz), Rect2(-hx, stair_z1 + 0.2, footprint.x, hz - stair_z1 - 0.2), Rect2(-hx + 1.7, stair_z0, hx * 2.0 - 1.7, stair_z1 + 0.2 - stair_z0)]:
				if rect.size.x > 0.05 and rect.size.y > 0.05:
					g.box(Vector3(rect.get_center().x, y - 0.1, rect.get_center().y), Vector3(rect.size.x, 0.2, rect.size.y), "slab")
		if level < floors - 1:
			g.stairs(Vector3(-hx + 0.95, y, stair_z1), Vector3(-hx + 0.95, y + s, stair_z0), 1.2, 14, "concrete")
		_lamps.append(Vector3((px + hx) * 0.5, y + s - 0.4, 0.0))
		if loot_density > 0.0:
			_furniture(g, Vector3((px + hx) * 0.5 + 1.0, y + 1.0, -hz + 0.65), Vector3(1.2, 2.0, 0.5), Vector3(0, 0, 1), "cabinet", _theme("home"), "", loot_density)
			_furniture(g, Vector3(hx - 0.6, y + 0.4, hz - 1.6), Vector3(0.6, 0.8, 1.4), Vector3(-1, 0, 0), "cabinet", _theme("home"), "Комод", loot_density)
			if level == 0:
				_furniture(g, Vector3(-hx + 2.6, y + 0.38, -hz + 1.2), Vector3(1.4, 0.75, 0.8), Vector3(0, 0, 1), "desk", _theme("home"), "Стол", loot_density)
	g.box(Vector3(0, y0 + float(floors) * s + 0.1, 0), Vector3(footprint.x + 0.4, 0.2, footprint.y + 0.4), "slab")

func _canopy(g: RefCounted) -> void:
	var h: float = story_height
	g.box(Vector3(0, h, 0), Vector3(footprint.x, 0.25, footprint.y), "slab")
	var count: int = maxi(2, int(footprint.x / 6.0))
	for i: int in range(count):
		var x: float = -footprint.x * 0.5 + (float(i) + 0.5) * footprint.x / float(count)
		g.box(Vector3(x, h * 0.5, 0), Vector3(0.25, h, 0.25), "steel")

func _bus(g: RefCounted) -> void:
	g.box(Vector3(0, 1.7, 0), Vector3(12.0, 2.6, 2.55), "bus")
	for side: float in [-1.0, 1.0]:
		g.box(Vector3(0, 2.2, side * 1.285), Vector3(10.4, 0.9, 0.04), "dark", false)
	g.box(Vector3(-6.02, 2.2, 0), Vector3(0.04, 0.9, 2.3), "dark", false)
	for x: float in [-3.6, 3.6]:
		g.box(Vector3(x, 0.5, 0), Vector3(1.0, 0.9, 2.8), "dark", false)

func _crane(g: RefCounted) -> void:
	var h: float = 38.0
	g.box(Vector3(0, 0.5, 0), Vector3(6.0, 1.0, 6.0), "concrete")
	for x: float in [-0.8, 0.8]:
		for z: float in [-0.8, 0.8]:
			g.box(Vector3(x, h * 0.5, z), Vector3(0.18, h, 0.18), "rust")
	for y: int in range(2, 38, 3):
		g.box(Vector3(0, float(y), 0), Vector3(1.8, 0.15, 1.8), "rust", false)
		g.beam(Vector3(-0.8, float(y), -0.8), Vector3(0.8, float(y + 3), -0.8), 0.1, 0.1, "rust")
	g.box(Vector3(12, h, 0), Vector3(56.0, 1.0, 1.4), "rust", false)
	g.box(Vector3(-12, h - 1.0, 0), Vector3(5.0, 2.5, 2.5), "concrete", false)
	g.box(Vector3(3, h - 1.2, 1.2), Vector3(2.2, 2.0, 1.8), "dark", false)
	g.box(Vector3(26, h - 11.0, 0), Vector3(0.045, 21.0, 0.045), "steel", false)

# ---------------------------------------------------------------- лут, двери, ключи (только в игре)

## Контейнеры лута по местам интерьера (доля — из данных мебели или своя, бросок — сидом от имени здания:
## у всех игроков одни и те же), запертая дверь, ключ. Имена постоянные: Gameplay/Loot_N, VaultDoor, Key_N.
func _place_gameplay() -> void:
	var old: Node = get_node_or_null("Gameplay")
	if old:
		old.free()
	if Engine.is_editor_hint() or (_spots.is_empty() and _doors.is_empty() and _keys.is_empty() and _lamps.is_empty()):
		set_meta("loot_count", 0)
		return
	var root := Node3D.new()
	root.name = "Gameplay"
	add_child(root)
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(String(name) + "|" + label)
	var n: int = 0
	for s: Dictionary in _spots:
		var spec: Dictionary = ItemDb.container(String(s.kind))
		var chance: float = float(s.chance) if float(s.chance) >= 0.0 else float(spec.get("chance", 0.5))
		if rng.randf() >= chance:
			continue
		var c := LOOT_SCENE.instantiate() as LootContainer
		c.name = "Loot_%d" % n
		n += 1
		c.display_name = String(s.title) if String(s.title) != "" else String(spec.get("name", "Ящик"))
		c.table = String(s.table) if String(s.table) != "" else String(spec.get("table", "storage"))
		c.search_s = float(spec.get("search", 2.0))
		c.look = int(s.look) as LootContainer.Look
		c.position = s.at
		root.add_child(c)
	for d: Dictionary in _doors:
		var door := DOOR_SCENE.instantiate() as Door
		door.name = String(d.name)
		door.width = float(d.width)
		door.required_key = String(d.key)
		door.position = d.at
		door.rotation.y = float(d.yaw)
		root.add_child(door)
	for i: int in range(_keys.size()):
		var kp := KEY_SCENE.instantiate() as KeyPickup
		kp.name = "Key_%d" % i
		kp.key_id = String(_keys[i].key)
		kp.display_name = ItemDb.item_name(String(_keys[i].key))
		kp.position = _keys[i].at
		root.add_child(kp)
	# лампы — как свет ТЦ: питание решает (нет — темно, аварийное — красные), без теней, гаснут вдали
	var lc: Dictionary = Balance.BLOCKOUT_LIGHTS
	for i: int in range(_lamps.size()):
		var lamp := OmniLight3D.new()
		lamp.name = "Lamp_%d" % i
		lamp.position = _lamps[i]
		lamp.light_color = lc.color
		lamp.light_energy = float(lc.energy)
		# в широком зале лампа светит дальше (до стен по ширине)
		lamp.omni_range = maxf(float(lc.range), footprint.y * float(lc.wide_k)) if kind == "hall" else float(lc.range)
		lamp.shadow_enabled = false
		lamp.distance_fade_enabled = true
		lamp.distance_fade_begin = float(lc.fade_begin)
		lamp.distance_fade_length = float(lc.fade_length)
		lamp.add_to_group("mall_lights")
		root.add_child(lamp)
	set_meta("loot_count", n)
