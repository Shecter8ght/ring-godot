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


## Сырость покрытий StreetPaving — от погоды рейда (покрытия ТЦ — MallGround, в _process предка).
var _paving_weather_t: float = 0.0


func _process(delta: float) -> void:
	super(delta)
	_paving_weather_t += delta
	if _paving_weather_t >= WEATHER_SYNC_SEC:
		StreetPaving.sync_weather(_paving_weather_t)
		_paving_weather_t = 0.0


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


## Покрытия по выбору владельца на стенде tools/paving_probe (2026-11-07, docs/design/prospekt_paving.md): тротуары —
## серый кирпичик ложком (walk_a), дороги и парковки — асфальт А (road_a), площади у вокзала, сквер и площадки у «Вершины» —
## плиты 500 × 500 с розовыми рядами и полосами тёмной ёлочки (plaza_ab2), детские — резиновая крошка, корт — краска по
## покрытию; старые дворы и пустырь — разбитый асфальт (road_c). Ключ StreetPaving — по началу id куска плана, иначе по
## материалу; трава, грунт и бетонные площадки — прежние (MallGround).
const PAVING_BY_ID: Array = [
	["station_", "plaza_ab2"], ["square_", "plaza_ab2"], ["fore_", "plaza_ab2"], ["plaza_", "plaza_ab2"],
	["playground", "rubber"], ["court_bb", "court"], ["house7_yard", "road_c"], ["yard_e", "road_c"], ["evac_field", "road_c"]]
const PAVING_BY_MAT: Dictionary = {"walk": "walk_a", "road": "road_a", "parking": "road_a", "court": "court"}
## Что у края считается тем же покрытием (стык без наноса песка): тротуары с площадями, проезжие части между собой.
const PAVING_KIND: Dictionary = {"walk_a": "walk", "plaza_ab2": "walk", "rubber": "pad", "court": "pad", "road_a": "road",
	"road_c": "road"}
const BOX_KIND: Dictionary = {"walk": "walk", "road": "road", "parking": "road"}
## Люки и решётки: решётка ливнёвки у дорожного бордюра через столько метров, люк в тротуаре — через столько.
const DRAIN_STEP_M: float = 32.0
const MANHOLE_STEP_M: float = 46.0

## Куски покрытий для проверки краёв: [Rect2, верх, вид]; полосы поворота: [середина xz, полуразмеры, поворот, верх, вид].
var _pave_rects: Array = []
var _pave_boxes: Array = []
var _iron_rng := RandomNumberGenerator.new()


func _paving_key(s: Dictionary) -> String:
	var id: String = String(s.id)
	for pair: Array in PAVING_BY_ID:
		if id.begins_with(String(pair[0])):
			return String(pair[1])
	return String(PAVING_BY_MAT.get(String(s.mat), ""))


## Покрытия — тонкие коробки на земле (коллизия и бока), сверху — прямоугольник покрытия StreetPaving с данными краёв;
## тротуары — с вырезами под лестницы перехода.
func _surfaces_flat(g: RefCounted) -> void:
	var walk_holes: Array = plan.get("walk_holes", []) as Array
	_iron_rng.seed = 7112026
	_collect_paving_regions(walk_holes)
	var streams: Dictionary = {}
	for s: Dictionary in plan.surfaces:
		var r: Array = s.rect
		var rect: Rect2 = Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		var t: float = float(s.get("t", 0.08))
		var y: float = float(s.get("y", 0.0))
		# свои вырезы покрытия (лестницы паркинга под парковкой) или общие вырезы тротуаров (переход)
		var holes: Array = s.get("holes", walk_holes if String(s.id).begins_with("walk") else []) as Array
		var key: String = _paving_key(s)
		for piece: Rect2 in _minus(rect, holes):
			if piece.get_area() < 0.01:
				continue
			var at := Vector3(piece.position.x + piece.size.x * 0.5, y + t * 0.5, piece.position.y + piece.size.y * 0.5)
			if key == "":
				g.box(at, Vector3(piece.size.x, t, piece.size.y), String(s.mat), true)
				continue
			g.box(at, Vector3(piece.size.x, t, piece.size.y), "paving_side", true)
			if not streams.has(key):
				streams[key] = StreetPaving.begin_surfaces()
			# узор — вдоль длинной стороны куска (ложок тротуара — вдоль тротуара на любом плече)
			var angle: float = 0.0 if piece.size.x >= piece.size.y else PI * 0.5
			StreetPaving.add_surface_quad(streams[key] as SurfaceTool, piece, y + t + 0.003,
				_edge_weights(piece, y + t, String(PAVING_KIND[key])), angle)
			if key == "walk_a" and String(s.id).begins_with("walk"):
				_manholes(piece, y + t + 0.003)
		if key == "court":
			StreetPaving.court_paint(generated, rect, y + t + 0.003, 152)
	for key: String in streams:
		var mi := MeshInstance3D.new()
		mi.name = "Paving_" + key
		mi.mesh = (streams[key] as SurfaceTool).commit()
		mi.material_override = StreetPaving.material(key)
		generated.add_child(mi)


func _collect_paving_regions(walk_holes: Array) -> void:
	_pave_rects.clear()
	_pave_boxes.clear()
	for s: Dictionary in plan.surfaces:
		var key: String = _paving_key(s)
		if key == "":
			continue
		var r: Array = s.rect
		var rect: Rect2 = Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		var holes: Array = s.get("holes", walk_holes if String(s.id).begins_with("walk") else []) as Array
		for piece: Rect2 in _minus(rect, holes):
			_pave_rects.append([piece, float(s.get("y", 0.0)) + float(s.get("t", 0.08)), String(PAVING_KIND[key])])
	for bx: Dictionary in plan.boxes:
		var kind: String = String(BOX_KIND.get(String(bx.get("mat", "")), ""))
		if kind == "":
			continue
		var at: Array = bx.at
		var size: Array = bx.size
		_pave_boxes.append([Vector2(float(at[0]), float(at[2])), Vector2(float(size[0]), float(size[2])) * 0.5,
			deg_to_rad(float(bx.get("yaw", 0.0))), float(at[1]) + float(size[1]) * 0.5, kind])


## Вид покрытия в точке (того же уровня по высоте) — по кускам и полосам поворота; "" — другое.
func _kind_at(p: Vector2, top: float) -> String:
	for e: Array in _pave_rects:
		if absf(float(e[1]) - top) < 0.06 and (e[0] as Rect2).has_point(p):
			return String(e[2])
	for b: Array in _pave_boxes:
		if absf(float(b[3]) - top) > 0.06:
			continue
		var d: Vector2 = p - (b[0] as Vector2)
		var yaw: float = float(b[2])
		var lx: float = d.x * cos(yaw) - d.y * sin(yaw)
		var lz: float = d.x * sin(yaw) + d.y * cos(yaw)
		var half: Vector2 = b[1]
		if absf(lx) <= half.x and absf(lz) <= half.y:
			return String(b[4])
	return ""


## Сила краёв куска (x0, x1, z0, z1): 0 — за краем то же покрытие (стык), 1 — бордюр, стена, газон, другое покрытие.
func _edge_weights(r: Rect2, top: float, kind: String) -> Color:
	var w: Array[float] = [0.0, 0.0, 0.0, 0.0]
	for e: int in range(4):
		var same: int = 0
		for k: int in range(5):
			var t: float = (float(k) + 0.5) / 5.0
			var p: Vector2
			match e:
				0:
					p = Vector2(r.position.x - 0.3, lerpf(r.position.y, r.end.y, t))
				1:
					p = Vector2(r.end.x + 0.3, lerpf(r.position.y, r.end.y, t))
				2:
					p = Vector2(lerpf(r.position.x, r.end.x, t), r.position.y - 0.3)
				_:
					p = Vector2(lerpf(r.position.x, r.end.x, t), r.end.y + 0.3)
			if _kind_at(p, top) == kind:
				same += 1
		w[e] = 0.0 if same >= 3 else 1.0
	return Color(w[0], w[1], w[2], w[3])


## Люки в тротуаре: чугунные ГОСТ через MANHOLE_STEP_M вдоль куска, у середины ширины со сдвигом.
func _manholes(piece: Rect2, y: float) -> void:
	var along_x: bool = piece.size.x >= piece.size.y
	var length: float = maxf(piece.size.x, piece.size.y)
	var s: float = _iron_rng.randf_range(8.0, MANHOLE_STEP_M)
	while s < length - 4.0:
		var across: float = _iron_rng.randf_range(0.3, 0.7)
		var at := Vector3(piece.position.x + (s if along_x else piece.size.x * across), y,
			piece.position.y + (piece.size.y * across if along_x else s))
		StreetPaving.iron_node(generated, "manhole_gost", at, _iron_rng.randf_range(0.0, TAU))
		s += MANHOLE_STEP_M * _iron_rng.randf_range(0.8, 1.25)


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


## Коробки плана; светлые «stripe» на земле — бордюры (0,2 × 0,15, твёрдые) и разметка (2 см) — заменяются: бордюр —
## камнями по профилю ГОСТ 6665 лицом к дороге (StreetPaving.curb_mesh; коллизия — прежней коробкой), разметка —
## краской road_paint, зебры бело-жёлтые (жёлтая полоса — в промежутке между белыми, как на фото владельца).
func _boxes(g: RefCounted) -> void:
	var curbs: SurfaceTool = null
	var zebra: Dictionary = {}
	for i: int in range(plan.boxes.size()):
		var bx: Dictionary = plan.boxes[i]
		var at: Array = bx.at
		var size: Array = bx.size
		var pos := Vector3(float(at[0]), float(at[1]), float(at[2]))
		var sz := Vector3(float(size[0]), float(size[1]), float(size[2]))
		var yaw: float = deg_to_rad(float(bx.get("yaw", 0.0)))
		var mat: String = String(bx.get("mat", "wall"))
		var narrow: float = minf(sz.x, sz.z)
		if mat == "stripe" and bool(bx.get("solid", true)) and sz.y > 0.12 and sz.y < 0.18 and narrow > 0.15 and narrow < 0.25:
			if curbs == null:
				curbs = SurfaceTool.new()
				curbs.begin(Mesh.PRIMITIVE_TRIANGLES)
			_curb(g, curbs, pos, sz, yaw, i)
			continue
		if mat == "stripe" and sz.y <= 0.03:
			if narrow > 0.8 and maxf(sz.x, sz.z) > 3.0:
				var along_x: bool = sz.x > sz.z
				var gkey: String = "%s/%d" % ["x" if along_x else "z", int(round((pos.x if along_x else pos.z) * 2.0))]
				if not zebra.has(gkey):
					zebra[gkey] = []
				(zebra[gkey] as Array).append([pos, sz, yaw])
			else:
				StreetPaving.paint_node(generated, "line", Vector3(pos.x, pos.y - sz.y * 0.5 + 0.012, pos.z), Vector2(sz.x, sz.z), yaw)
			continue
		g.box(pos, sz, mat, bool(bx.get("solid", true)), yaw)
	if curbs != null:
		var mi := MeshInstance3D.new()
		mi.name = "Curbs"
		mi.mesh = curbs.commit()
		mi.material_override = StreetPaving.curb_material("road")
		generated.add_child(mi)
	_zebras(zebra)


## Бордюр по коробке: длинная ось, сторона дороги (где асфальт ниже бордюра), камни БР 100.30.15 тыльной гранью к тротуару.
func _curb(g: RefCounted, st: SurfaceTool, pos: Vector3, sz: Vector3, yaw: float, index: int) -> void:
	var b := Basis(Vector3.UP, yaw)
	var along_x: bool = sz.x >= sz.z
	var axis3: Vector3 = b * (Vector3.RIGHT if along_x else Vector3.BACK)
	var a := Vector2(axis3.x, axis3.z).normalized()
	var length: float = maxf(sz.x, sz.z)
	var half_w: float = minf(sz.x, sz.z) * 0.5
	var c := Vector2(pos.x, pos.z)
	var n := Vector2(a.y, -a.x)
	var top: float = pos.y + sz.y * 0.5
	var road_plus: bool = _kind_at(c + n * (half_w + 0.35), top - 0.07) == "road"
	var road_minus: bool = _kind_at(c - n * (half_w + 0.35), top - 0.07) == "road"
	if road_minus and not road_plus:
		a = -a
		n = Vector2(a.y, -a.x)
	var base_y: float = pos.y - sz.y * 0.5
	var w: float = float((StreetPaving.CURB_PROFILES.road as Dictionary).w)
	# лицевая грань (z = 0 сетки) — со стороны дороги, камень уходит к тротуару (+z сетки = −n)
	var start: Vector2 = c - a * length * 0.5 - n * half_w + n * w
	var xform := Transform3D(Basis(Vector3(a.x, 0.0, a.y), Vector3.UP, Vector3(-n.x, 0.0, -n.y)), Vector3(start.x, base_y, start.y))
	st.append_from(StreetPaving.curb_mesh("road", length, 300 + index), 0, xform)
	var shape := BoxShape3D.new()
	shape.size = sz
	var cs := CollisionShape3D.new()
	cs.shape = shape
	cs.position = pos
	cs.rotation.y = yaw
	(g.body as StaticBody3D).add_child(cs)
	# решётки ливнёвки у бордюра со стороны дороги, изредка люк на полосе
	if length > 20.0 and (road_plus or road_minus):
		var s: float = _iron_rng.randf_range(4.0, DRAIN_STEP_M)
		while s < length - 2.0:
			var p2: Vector2 = start + a * s + n * 0.32
			StreetPaving.iron_node(generated, "drain_grate", Vector3(p2.x, base_y + 0.083, p2.y), atan2(-a.y, a.x))
			s += DRAIN_STEP_M
		if _iron_rng.randf() < 0.5:
			var p3: Vector2 = start + a * _iron_rng.randf_range(6.0, length - 6.0) + n * 2.2
			StreetPaving.iron_node(generated, "manhole_gost", Vector3(p3.x, base_y + 0.083, p3.y), _iron_rng.randf_range(0.0, TAU))


## Зебры: белые полосы плана и жёлтые в промежутках между соседними белыми.
func _zebras(groups: Dictionary) -> void:
	for gkey: String in groups:
		var list: Array = groups[gkey]
		var along_x: bool = gkey.begins_with("x")
		list.sort_custom(func(p: Array, q: Array) -> bool:
			var pa: Vector3 = p[0]
			var qa: Vector3 = q[0]
			return (pa.z if along_x else pa.x) < (qa.z if along_x else qa.x))
		for k: int in range(list.size()):
			var pos: Vector3 = list[k][0]
			var sz: Vector3 = list[k][1]
			var y: float = pos.y - sz.y * 0.5 + 0.012
			StreetPaving.paint_node(generated, "white", Vector3(pos.x, y, pos.z), Vector2(sz.x, sz.z), float(list[k][2]))
			if k + 1 < list.size():
				var nxt: Vector3 = list[k + 1][0]
				var gap: float = (nxt.z - pos.z) if along_x else (nxt.x - pos.x)
				if gap < 3.0:
					var mid: Vector3 = (pos + nxt) * 0.5
					StreetPaving.paint_node(generated, "yellow", Vector3(mid.x, y, mid.z), Vector2(sz.x, sz.z), float(list[k][2]))


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
		# откос насыпи — сплошной клин, а не плита над пустотой: под ним не ходят ни люди, ни навигация
		if bool(r.get("fill", false)):
			var low: float = minf(y0, y1)
			var wedge: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
			wedge.points = PackedVector3Array([
				Vector3(x0, low, z0), Vector3(x1, low, z0), Vector3(x0, low, z1), Vector3(x1, low, z1),
				Vector3(x0, y0, z0), Vector3(x1, y0, z0), Vector3(x0, y1, z1), Vector3(x1, y1, z1)])
			var ws: CollisionShape3D = CollisionShape3D.new()
			ws.shape = wedge
			(g.body as StaticBody3D).add_child(ws)
			for x: float in [x0, x1]:
				g.tri(Vector3(x, low, z0), Vector3(x, y0, z0), Vector3(x, y1, z1), key)
				g.tri(Vector3(x, low, z0), Vector3(x, y1, z1), Vector3(x, low, z1), key)
				g.tri(Vector3(x, low, z0), Vector3(x, y1, z1), Vector3(x, y0, z0), key)
				g.tri(Vector3(x, low, z0), Vector3(x, low, z1), Vector3(x, y1, z1), key)


## Граница карты (владелец 2026-10-25: «по периметру — логичные преграды, а не невидимая стена»): видимое — забор
## района, вышки, насыпь и город за ними (наполнение генератора); здесь только страховка — невидимая стенка по
## линии границы за забором, без столбиков-меток черновика ТЦ.
func _boundary(g: RefCounted) -> void:
	var edge: PackedVector2Array = boundary.duplicate()
	edge.append(boundary[0])
	for i: int in range(edge.size() - 1):
		var a: Vector2 = edge[i]
		var b: Vector2 = edge[i + 1]
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = Vector3(a.distance_to(b) + 2.0, 40.0, 1.0)
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		var mid: Vector2 = (a + b) * 0.5
		cs.position = Vector3(mid.x, 10.0, mid.y)
		cs.rotation.y = -atan2((b - a).y, (b - a).x)
		g.body.add_child(cs)


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
	"wood": Color("7a6046"), "paint_blue": Color("24477a"), "paint_white": Color("d9d9d4"), "black": Color("1a1a1a")}


func _palette() -> Dictionary:
	var result: Dictionary = super()
	# полосы поворота и прочие коробки покрытий — материалами стенда без данных краёв; бока кусков покрытий — бетон
	for mat: String in PAVING_BY_MAT:
		result[mat] = StreetPaving.material(String(PAVING_BY_MAT[mat]), false)
	var side := StandardMaterial3D.new()
	side.albedo_color = Color(0.42, 0.41, 0.39)
	side.roughness = 0.95
	result["paving_side"] = side
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
