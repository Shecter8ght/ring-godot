@tool
extends "res://src/blockout/mall_landscape.gd"
## Земля карты «Проспект» (docs/design/prospekt_map.md, план — data/blockouts/prospekt.json, генератор —
## tools/build_prospekt.py): плоская площадка с вырезами под подземный переход и паркинг −1, проспект с тротуарами,
## плиты и стены, лестницы, пандус, колонны, маркеры появления и выходов, граница. Наследует ландшафт ТЦ, чтобы
## узел наполнения MallFiller (../Filler) работал без правок: ему нужны plan.filler и ground(x, z). Рельефа нет —
## земля ровная (ground = 0), подземное — геометрией, не высотами.

const PROSPEKT_PLAN: String = "res://data/blockouts/prospekt.json"


func load_plan() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PROSPEKT_PLAN))
	if not parsed is Dictionary:
		push_error("Не прочитан план «Проспекта»: " + PROSPEKT_PLAN)
		return
	plan = parsed as Dictionary
	boundary = poly(plan.boundary)
	forests.clear()


## Земля ровная; подземные уровни — отдельными плитами, а не высотами.
func ground(_x: float, _z: float) -> float:
	return 0.0


func base_height(_x: float, _z: float) -> float:
	return 0.0


func rebuild() -> void:
	if plan.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Landscape"
	add_child(generated)
	cover_spots = PackedVector2Array()
	var g: RefCounted = Geometry.new(generated, _palette())
	_ground_plate(g)
	_surfaces_flat(g)
	_slabs(g)
	_walls(g)
	_boxes(g)
	_columns(g)
	_stairs(g)
	_ramps(g)
	_beams(g)
	_markers(g)
	_loot(g)
	_boundary(g)
	g.finish()
	_lamps()
	_signs()


## Плита земли 0,5 м толщиной по границам с вырезами (переход, паркинг, траншея пандуса).
func _ground_plate(g: RefCounted) -> void:
	var b: Array = plan.bounds
	var rect: Rect2 = Rect2(float(b[0]), float(b[1]), float(b[2]) - float(b[0]), float(b[3]) - float(b[1]))
	for piece: Rect2 in _minus(rect, plan.get("ground_holes", []) as Array):
		# верх земли на 2 см ниже нуля: полы залов StudyBuilding и покрытия лежат на нуле, без мерцания
		g.box(Vector3(piece.position.x + piece.size.x * 0.5, -0.27, piece.position.y + piece.size.y * 0.5),
			Vector3(piece.size.x, 0.5, piece.size.y), "ground")


## Покрытия — тонкие коробки на земле; тротуары — с вырезами под лестницы перехода.
func _surfaces_flat(g: RefCounted) -> void:
	var walk_holes: Array = plan.get("walk_holes", []) as Array
	for s: Dictionary in plan.surfaces:
		var r: Array = s.rect
		var rect: Rect2 = Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		var t: float = float(s.get("t", 0.08))
		var y: float = float(s.get("y", 0.0))
		# свои вырезы покрытия (лестницы паркинга под парковкой) или общие вырезы тротуаров (переход)
		var holes: Array = s.get("holes", walk_holes if String(s.id).begins_with("walk") else []) as Array
		for piece: Rect2 in _minus(rect, holes):
			g.box(Vector3(piece.position.x + piece.size.x * 0.5, y + t * 0.5, piece.position.y + piece.size.y * 0.5),
				Vector3(piece.size.x, t, piece.size.y), String(s.mat), true)


func _slabs(g: RefCounted) -> void:
	for s: Dictionary in plan.slabs:
		var r: Array = s.rect
		var rect: Rect2 = Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		var t: float = float(s.t)
		var top: float = float(s.y_top)
		for piece: Rect2 in _minus(rect, s.get("holes", []) as Array):
			g.box(Vector3(piece.position.x + piece.size.x * 0.5, top - t * 0.5, piece.position.y + piece.size.y * 0.5),
				Vector3(piece.size.x, t, piece.size.y), String(s.mat))


func _walls(g: RefCounted) -> void:
	for w: Dictionary in plan.walls:
		var r: Array = w.rect
		var y0: float = float(w.y0)
		var y1: float = float(w.y1)
		g.box(Vector3((float(r[0]) + float(r[2])) * 0.5, (y0 + y1) * 0.5, (float(r[1]) + float(r[3])) * 0.5),
			Vector3(float(r[2]) - float(r[0]), y1 - y0, float(r[3]) - float(r[1])), String(w.get("mat", "wall")))


func _boxes(g: RefCounted) -> void:
	for bx: Dictionary in plan.boxes:
		var at: Array = bx.at
		var size: Array = bx.size
		g.box(Vector3(float(at[0]), float(at[1]), float(at[2])), Vector3(float(size[0]), float(size[1]), float(size[2])),
			String(bx.get("mat", "wall")), bool(bx.get("solid", true)), deg_to_rad(float(bx.get("yaw", 0.0))))


func _columns(g: RefCounted) -> void:
	for c: Dictionary in plan.columns:
		var r: Array = c.rect
		var grid: float = float(c.grid)
		var size: float = float(c.size)
		var y0: float = float(c.y0)
		var y1: float = float(c.y1)
		var x: float = float(r[0])
		while x <= float(r[2]) + 0.01:
			var z: float = float(r[1])
			while z <= float(r[3]) + 0.01:
				g.box(Vector3(x, (y0 + y1) * 0.5, z), Vector3(size, y1 - y0, size), String(c.get("mat", "concrete")))
				z += grid
			x += grid


func _stairs(g: RefCounted) -> void:
	for s: Dictionary in plan.stairs:
		var a: Array = s.from
		var b: Array = s.to
		g.stairs(Vector3(float(a[0]), float(a[1]), float(a[2])), Vector3(float(b[0]), float(b[1]), float(b[2])),
			float(s.width), int(s.count), String(s.get("mat", "concrete")))


## Пандус вдоль Z: наклонная плита (вид — четырёхугольники, физика — выпуклая призма), как у лестниц.
func _ramps(g: RefCounted) -> void:
	for r: Dictionary in plan.ramps:
		var x0: float = float(r.x0)
		var x1: float = float(r.x1)
		var z0: float = float(r.z0)
		var z1: float = float(r.z1)
		var y0: float = float(r.y0)
		var y1: float = float(r.y1)
		var key: String = String(r.get("mat", "concrete"))
		var t: float = 0.3
		g.quad(Vector3(x0, y0, z0), Vector3(x1, y0, z0), Vector3(x1, y1, z1), Vector3(x0, y1, z1), key)
		g.quad(Vector3(x0, y1 - t, z1), Vector3(x1, y1 - t, z1), Vector3(x1, y0 - t, z0), Vector3(x0, y0 - t, z0), key)
		g.quad(Vector3(x0, y0, z0), Vector3(x0, y1, z1), Vector3(x0, y1 - t, z1), Vector3(x0, y0 - t, z0), key)
		g.quad(Vector3(x1, y0 - t, z0), Vector3(x1, y1 - t, z1), Vector3(x1, y1, z1), Vector3(x1, y0, z0), key)
		var shape: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
		shape.points = PackedVector3Array([
			Vector3(x0, y0, z0), Vector3(x1, y0, z0), Vector3(x0, y1, z1), Vector3(x1, y1, z1),
			Vector3(x0, y0 - t, z0), Vector3(x1, y0 - t, z0), Vector3(x0, y1 - t, z1), Vector3(x1, y1 - t, z1)])
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		(g.body as StaticBody3D).add_child(cs)


## Наклонные балки (решётка фасада банка, раскосы): [от, до, ширина, толщина, материал].
func _beams(g: RefCounted) -> void:
	for b: Array in plan.get("beams", []):
		var a: Array = b[0]
		var c: Array = b[1]
		g.beam(Vector3(float(a[0]), float(a[1]), float(a[2])), Vector3(float(c[0]), float(c[1]), float(c[2])),
			float(b[2]), float(b[3]), String(b[4]))


## Места лута (замечание владельца 2026-10-24, п. 8): маркер по виду места, цвет — по ценности. Это схема для
## левел-дизайна — настоящие контейнеры ставит рейдовая сборка; в залах StudyBuilding свои места лута.
const LOOT_SIZE: Dictionary = {
	"crate": Vector3(0.8, 0.5, 0.6), "backpack": Vector3(0.4, 0.5, 0.3), "suitcase": Vector3(0.6, 0.22, 0.42),
	"body": Vector3(0.55, 0.3, 1.8), "car": Vector3(0.35, 0.35, 0.35), "register": Vector3(0.5, 0.35, 0.4),
	"safe": Vector3(0.7, 0.9, 0.6), "cabinet": Vector3(0.9, 1.6, 0.45), "loose": Vector3(0.25, 0.12, 0.25),
	"cells": Vector3(1.2, 0.5, 0.3), "weapon": Vector3(1.2, 0.35, 0.45), "med": Vector3(0.5, 0.3, 0.35)}
const LOOT_TIER: Dictionary = {"common": "loot_common", "med": "loot_med", "good": "loot_good", "weapon": "loot_weapon", "quest": "spawn"}


func _loot(g: RefCounted) -> void:
	for l: Dictionary in plan.get("loot", []):
		var at: Array = l.at
		var size: Vector3 = LOOT_SIZE.get(String(l.kind), Vector3(0.4, 0.4, 0.4)) as Vector3
		g.box(Vector3(float(at[0]), float(at[1]) + size.y * 0.5, float(at[2])), size,
			String(LOOT_TIER.get(String(l.get("tier", "common")), "loot_common")), false, deg_to_rad(float(l.get("yaw", 0.0))))


## Свои цвета карты: маркеры лута по ценности (светятся, чтобы читались в тени), граффити, хаки, стекло.
const EXTRA_COLORS: Dictionary = {"loot_common": Color("c8b48a"), "loot_med": Color("4fae63"), "loot_good": Color("e3b23c"),
	"loot_weapon": Color("c4493b"), "graffiti": Color("7a6f8f"), "olive": Color("5b6243"), "glass": Color("5d6f74"),
	"wood": Color("7a6046"), "paint_blue": Color("24477a")}


func _palette() -> Dictionary:
	var result: Dictionary = super()
	for key: String in EXTRA_COLORS:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.albedo_color = EXTRA_COLORS[key]
		m.roughness = 0.6
		if key.begins_with("loot"):
			m.emission_enabled = true
			m.emission = m.albedo_color * 0.35
		result[key] = m
	return result


## Аварийный свет паркинга и перехода (вне игры питания нет — просто лампы).
func _lamps() -> void:
	for l: Array in plan.get("lamps", []):
		var light: OmniLight3D = OmniLight3D.new()
		light.light_energy = float(l[3])
		light.omni_range = float(l[4])
		light.light_color = Color(1.0, 0.85, 0.6)
		light.shadow_enabled = false
		generated.add_child(light)
		light.position = Vector3(float(l[0]), float(l[1]), float(l[2]))


func _signs() -> void:
	for s: Dictionary in plan.get("signs", []):
		var at: Array = s.at
		var label: Label3D = Label3D.new()
		label.text = String(s.text)
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.font_size = int(s.get("size", 56))
		label.pixel_size = 0.02
		label.outline_size = 14
		label.modulate = Color("f1ead8")
		label.no_depth_test = false
		generated.add_child(label)
		label.position = Vector3(float(at[0]), float(at[1]), float(at[2]))


## Постройки стоят на ровной земле; башни — на подъёме из метаданных (lift), не на земле.
func snap_buildings() -> void:
	if plan.is_empty() or not is_inside_tree():
		return
	for node: Node in get_tree().get_nodes_in_group("mall_study_snap"):
		var b: Node3D = node as Node3D
		if b == null:
			continue
		b.global_position.y = float(b.get_meta("lift", 0.0))


## Прямоугольник минус прямоугольники (все — по осям): остаток полосами вокруг каждого выреза.
static func _minus(rect: Rect2, holes: Array) -> Array[Rect2]:
	var pieces: Array[Rect2] = [rect]
	for h: Array in holes:
		var hole: Rect2 = Rect2(float(h[0]), float(h[1]), float(h[2]) - float(h[0]), float(h[3]) - float(h[1]))
		var next: Array[Rect2] = []
		for p: Rect2 in pieces:
			var cut: Rect2 = p.intersection(hole)
			if cut.size.x <= 0.001 or cut.size.y <= 0.001:
				next.append(p)
				continue
			# полосы слева и справа от выреза на всю высоту, сверху и снизу — между ними
			if cut.position.x > p.position.x:
				next.append(Rect2(p.position.x, p.position.y, cut.position.x - p.position.x, p.size.y))
			if cut.end.x < p.end.x:
				next.append(Rect2(cut.end.x, p.position.y, p.end.x - cut.end.x, p.size.y))
			if cut.position.y > p.position.y:
				next.append(Rect2(cut.position.x, p.position.y, cut.size.x, cut.position.y - p.position.y))
			if cut.end.y < p.end.y:
				next.append(Rect2(cut.position.x, cut.end.y, cut.size.x, p.end.y - cut.end.y))
		pieces = next
	return pieces
