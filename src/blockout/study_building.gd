@tool
extends Node3D
## Временная архитектура в метрах. Пять и девять этажей имеют реальную высоту.
## Отдельные узлы зданий сохраняются в сцене и заменяются готовыми ассетами.

const Geometry = preload("res://src/blockout/study_geometry.gd")

@export_enum("mass", "apartments", "skeleton", "hall", "canopy", "bus", "crane") var kind: String = "mass":
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

var generated: Node3D
var stair_origin: Vector2
var queued: bool = false

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
		_:
			_mass(g)
	g.finish()
	set_meta("height_m", float(floors) * story_height)
	set_meta("enterable", kind in ["skeleton", "apartments", "hall"])

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
	# Сквозной коридор и простые комнаты; западные 10 м отданы лестнице.
	var x0: float = stair_origin.x + 3.0
	var room_count: int = maxi(1, int((footprint.x * 0.5 - x0) / 6.0))
	var room_w: float = (footprint.x * 0.5 - x0) / float(room_count)
	for i: int in range(room_count):
		var x: float = x0 + float(i) * room_w
		for side: float in [-1.0, 1.0]:
			g.box(Vector3(x, y + story_height * 0.5, side * (footprint.y * 0.25 + 0.6)), Vector3(0.16, story_height, footprint.y * 0.5 - 1.2), "wall")
			var door_x: float = x + room_w * 0.5
			for edge: float in [-1.0, 1.0]:
				g.box(Vector3(door_x + edge * (room_w + 1.1) * 0.25, y + story_height * 0.5, side * 1.2), Vector3((room_w - 1.1) * 0.5, story_height, 0.16), "wall")
			g.box(Vector3(door_x, y + 2.6, side * 1.2), Vector3(1.1, 0.8, 0.16), "wall")

func _hall(g: RefCounted) -> void:
	var h: float = story_height * float(floors)
	g.box(Vector3(0, -0.15, 0), Vector3(footprint.x, 0.3, footprint.y), "walk")
	g.box(Vector3(0, h, 0), Vector3(footprint.x + 0.8, 0.35, footprint.y + 0.8), "slab")
	for side: float in [-1.0, 1.0]:
		var z: float = side * footprint.y * 0.5
		var gap: float = 3.0
		for direction: float in [-1.0, 1.0]:
			g.box(Vector3(direction * (footprint.x + gap) * 0.25, h * 0.5, z), Vector3((footprint.x - gap) * 0.5, h, 0.3), "wall")
		g.box(Vector3(0, h - 0.8, z), Vector3(gap, 1.6, 0.3), "wall")
	for x: float in [-footprint.x * 0.5, footprint.x * 0.5]:
		g.box(Vector3(x, h * 0.5, 0), Vector3(0.3, h, footprint.y), "wall")
	# Стойки задают масштаб помещения, но не готовое оформление.
	for x: float in [-footprint.x * 0.28, footprint.x * 0.28]:
		g.box(Vector3(x, 0.6, 1.5), Vector3(4.0, 1.2, 1.2), "accent")

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
