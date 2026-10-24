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
	_markers(g)
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
		var holes: Array = walk_holes if String(s.id).begins_with("walk") else []
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
