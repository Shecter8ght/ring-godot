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


## Газоны (разделительные, газон рощи, приподнятые газоны сквера) — некошеная два года трава травяным покровом зоны 1
## (DistrictGrass: густые травинки и пучки высокой травы, бурьян, одуванчики — растительность Poly Haven) по карте
## плотности 1 пиксель = 1 м; верх газона — узел LawnGround (группа district_terrain, как у двора убежища).
const LAWN_GRASS: PackedStringArray = ["res://assets/zone01/models/ug_grass_tall_a.glb", "res://assets/zone01/models/ug_grass_tall_b.glb",
	"res://assets/zone01/models/ug_grass_small.glb", "res://assets/zone01/models/ug_grass_mid_b.glb", "res://assets/zone01/models/ug_grass2_c.glb"]
const LAWN_WEEDS: PackedStringArray = ["res://assets/zone01/models/ug_weed_a.glb", "res://assets/zone01/models/ug_weed_b.glb",
	"res://assets/zone01/models/ug_dandelion_c.glb", "res://assets/zone01/models/ug_dandelion_e.glb"]
const LAWN_DRYNESS: float = 0.08
## Лето: пучки зеленее (у зоны 1 — поздняя осень, тон тёплый, сухой).
const LAWN_TINT: Color = Color(0.66, 0.84, 0.5)
const LAWN_WEED_SHARE: float = 0.25

## Газоны: [середина xz, полуразмеры, поворот, верх].
var _lawns: Array = []


func _lawn_grass() -> void:
	if Engine.is_editor_hint():
		return
	_lawns.clear()
	for s: Dictionary in plan.surfaces:
		if String(s.mat) != "grass":
			continue
		var r: Array = s.rect
		var rect: Rect2 = Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		var top: float = float(s.get("y", 0.0)) + float(s.get("t", 0.08))
		for piece: Rect2 in _minus(rect, s.get("holes", []) as Array):
			_lawns.append([piece.get_center(), piece.size * 0.5, 0.0, top])
	for bx: Dictionary in plan.boxes:
		if String(bx.get("mat", "")) != "grass":
			continue
		var at: Array = bx.at
		var size: Array = bx.size
		_lawns.append([Vector2(float(at[0]), float(at[2])), Vector2(float(size[0]), float(size[2])) * 0.5,
			deg_to_rad(float(bx.get("yaw", 0.0))), float(at[1]) + float(size[1]) * 0.5])
	if _lawns.is_empty():
		return
	var b: Array = plan.bounds
	var origin := Vector2(floor(float(b[0])), floor(float(b[1])))
	var w: int = int(ceil(float(b[2]) - origin.x)) + 1
	var h: int = int(ceil(float(b[3]) - origin.y)) + 1
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 1))
	for lawn: Array in _lawns:
		var c: Vector2 = lawn[0]
		var half: Vector2 = lawn[1]
		var reach: float = half.length()
		for pz: int in range(maxi(0, int(c.y - reach - origin.y)), mini(h, int(c.y + reach - origin.y) + 2)):
			for px: int in range(maxi(0, int(c.x - reach - origin.x)), mini(w, int(c.x + reach - origin.x) + 2)):
				var p := Vector2(origin.x + float(px) + 0.5, origin.y + float(pz) + 0.5)
				if _in_lawn(p, lawn):
					img.set_pixel(px, pz, Color(1.0, LAWN_WEED_SHARE, 0.0, 1.0))
	var ground := LawnGround.new()
	ground.name = "LawnGround"
	ground.landscape = self
	generated.add_child(ground)
	var grass := DistrictGrass.new()
	grass.name = "LawnGrass"
	grass.density_texture = ImageTexture.create_from_image(img)
	grass.origin = origin
	grass.models = LAWN_GRASS
	grass.weed_models = LAWN_WEEDS
	grass.lawn_dryness = LAWN_DRYNESS
	grass.tint = LAWN_TINT
	generated.add_child(grass)


func _in_lawn(p: Vector2, lawn: Array) -> bool:
	var d: Vector2 = p - (lawn[0] as Vector2)
	var yaw: float = float(lawn[2])
	var lx: float = d.x * cos(yaw) - d.y * sin(yaw)
	var lz: float = d.x * sin(yaw) + d.y * cos(yaw)
	var half: Vector2 = lawn[1]
	return absf(lx) <= half.x and absf(lz) <= half.y


## Верх газона в точке (для травы), вне газонов — земля.
func lawn_top(x: float, z: float) -> float:
	var best: float = 0.0
	for lawn: Array in _lawns:
		if _in_lawn(Vector2(x, z), lawn):
			best = maxf(best, float(lawn[3]))
	return best


## Высота для травяного покрова (группа district_terrain): верх газона. Своих сеток нет — дождь его не трогает.
class LawnGround:
	extends Node3D
	var landscape: Node

	func _enter_tree() -> void:
		add_to_group("district_terrain")

	func height_at(x: float, z: float) -> float:
		return float(landscape.call("lawn_top", x, z)) if landscape else 0.0


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
	_lawn_grass()


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

## Бурьян (два года без людей): пучков на метр у бордюра со стороны дороги и тротуара, у стены и газона (край куска),
## на м² в швах площадей и тротуаров и в разбитых дворах; высота пучков, м.
const WEED_GUTTER_PER_M: float = 1.1
const WEED_CURB_BACK_PER_M: float = 0.6
const WEED_EDGE_PER_M: float = 0.7
const WEED_JOINT_PER_M2: float = 0.025
const WEED_BROKEN_PER_M2: float = 0.09
const WEED_GRASS_H: Vector2 = Vector2(0.08, 0.26)
const WEED_TALL_H: Vector2 = Vector2(0.12, 0.32)

## Куски покрытий для проверки краёв: [Rect2, верх, вид]; полосы поворота: [середина xz, полуразмеры, поворот, верх, вид].
var _pave_rects: Array = []
## Пучки бурьяна: «путь модели|клетка x|клетка z» → [Transform3D]; следы зданий (не сажать внутри): [середина, полуразмеры, поворот].
var _weeds: Dictionary = {}
var _weed_rng := RandomNumberGenerator.new()
var _footprints: Array = []
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
	_weed_rng.seed = 2026
	_weeds.clear()
	_collect_footprints()
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
			if String(s.mat) == "fountain_floor":
				# дно сухого фонтана: бетон, сверху облезлая голубая краска
				g.box(at, Vector3(piece.size.x, t, piece.size.y), "paving_side", true)
				StreetPaving.paint_node(generated, "fountain_blue", Vector3(at.x, y + t + 0.003, at.z), piece.size)
				continue
			if key == "":
				g.box(at, Vector3(piece.size.x, t, piece.size.y), String(s.mat), true)
				continue
			g.box(at, Vector3(piece.size.x, t, piece.size.y), "paving_side", true)
			if not streams.has(key):
				streams[key] = StreetPaving.begin_surfaces()
			# узор — вдоль длинной стороны куска (ложок тротуара — вдоль тротуара на любом плече)
			var angle: float = 0.0 if piece.size.x >= piece.size.y else PI * 0.5
			var edges: Color = _edge_weights(piece, y + t, String(PAVING_KIND[key]))
			StreetPaving.add_surface_quad(streams[key] as SurfaceTool, piece, y + t + 0.003, edges, angle)
			_weeds_on_piece(piece, y + t + 0.003, edges, key)
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


## Следы зданий плана (пучки внутри не сажаются).
func _collect_footprints() -> void:
	_footprints.clear()
	for b: Dictionary in plan.get("buildings", []):
		var at: Array = b.at
		var size: Array = b.size
		_footprints.append([Vector2(float(at[0]), float(at[1])), Vector2(float(size[0]), float(size[1])) * 0.5 + Vector2(0.15, 0.15),
			deg_to_rad(float(b.get("yaw", 0.0)))])


func _inside_building(p: Vector2) -> bool:
	for f: Array in _footprints:
		var d: Vector2 = p - (f[0] as Vector2)
		var yaw: float = float(f[2])
		var lx: float = d.x * cos(yaw) - d.y * sin(yaw)
		var lz: float = d.x * sin(yaw) + d.y * cos(yaw)
		var half: Vector2 = f[1]
		if absf(lx) <= half.x and absf(lz) <= half.y:
			return true
	return false


## Пучок: модель из набора, высота из диапазона, поворот случайный; клетка — для отсечения вдали кусками.
func _weed(models: PackedStringArray, p: Vector2, y: float, h: Vector2) -> void:
	if _inside_building(p):
		return
	var path: String = models[_weed_rng.randi() % models.size()]
	var t := Transform3D(Basis(Vector3.UP, _weed_rng.randf() * TAU).scaled(Vector3.ONE * _weed_rng.randf_range(h.x, h.y)),
		Vector3(p.x, y, p.y))
	var key: String = "%s|%d|%d" % [path, int(floor(p.x / StreetPaving.WEED_CHUNK_M)), int(floor(p.y / StreetPaving.WEED_CHUNK_M))]
	if not _weeds.has(key):
		_weeds[key] = []
	(_weeds[key] as Array).append(t)


## Полоса вдоль отрезка a → b шириной w в сторону n: пучков per_m на метр (трава и изредка бурьян).
func _weeds_strip(a: Vector2, b: Vector2, n: Vector2, w: float, y: float, per_m: float) -> void:
	var length: float = a.distance_to(b)
	var count: int = int(round(length * per_m * _weed_rng.randf_range(0.7, 1.3)))
	for i: int in range(count):
		var p: Vector2 = a.lerp(b, _weed_rng.randf()) + n * _weed_rng.randf_range(0.02, w)
		if _weed_rng.randf() < 0.18:
			_weed(StreetPaving.WEED_TALL, p, y, WEED_TALL_H)
		else:
			_weed(StreetPaving.WEED_GRASS, p, y, WEED_GRASS_H)


## Пучки на куске покрытия: у краёв с наносом (стена, газон, бордюр) — полосой, в швах — редко, в разбитом асфальте — чаще.
func _weeds_on_piece(r: Rect2, y: float, edges: Color, key: String) -> void:
	if key == "court":
		return
	var corners: Array[Vector2] = [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]
	# края: x0 (углы 0 → 3), x1 (1 → 2), z0 (0 → 1), z1 (3 → 2); нормаль — внутрь куска
	var sides: Array = [[0, 3, Vector2(1.0, 0.0), edges.r], [1, 2, Vector2(-1.0, 0.0), edges.g],
		[0, 1, Vector2(0.0, 1.0), edges.b], [3, 2, Vector2(0.0, -1.0), edges.a]]
	var per_m: float = WEED_EDGE_PER_M * (1.8 if key == "road_c" else 1.0)
	for side: Array in sides:
		if float(side[3]) > 0.5:
			_weeds_strip(corners[int(side[0])], corners[int(side[1])], side[2] as Vector2, 0.2, y, per_m)
	var per_m2: float = WEED_BROKEN_PER_M2 if key == "road_c" else (0.0 if key == "road_a" else WEED_JOINT_PER_M2)
	var count: int = int(round(r.get_area() * per_m2))
	for i: int in range(count):
		var p := Vector2(_weed_rng.randf_range(r.position.x, r.end.x), _weed_rng.randf_range(r.position.y, r.end.y))
		_weed(StreetPaving.WEED_GRASS, p, y, Vector2(0.06, 0.18))


## Пучки — по кускам карты (отсечение вдали кусками, мелкая трава — ближе).
func _plant_weeds() -> void:
	for key: String in _weeds:
		var path: String = key.get_slice("|", 0)
		var tall: bool = StreetPaving.WEED_TALL.has(path)
		var node: MultiMeshInstance3D = StreetPaving.scatter_node(generated, path, _weeds[key] as Array,
			StreetPaving.WEED_FAR_M.y if tall else StreetPaving.WEED_FAR_M.x)
		if node != null:
			node.name = "Weeds_%s" % key.get_file().replace("|", "_").replace(".glb", "")


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
	_plant_weeds()


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
	# бурьян: в канаве у лицевой грани (на асфальте) и за тыльной гранью (на тротуаре)
	if road_plus or road_minus:
		_weeds_strip(start, start + a * length, n, 0.25, base_y + 0.083, WEED_GUTTER_PER_M)
		var back: Vector2 = start - n * w
		_weeds_strip(back, back + a * length, -n, 0.18, top + 0.003, WEED_CURB_BACK_PER_M)
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
	# линии колонн паркинга −1 (под землёй) — буквами по порядку, колонны в линии — номерами, как в зале D стенда
	var pit_lines: Array[float] = []
	for c: Dictionary in plan.columns:
		if float(c.y0) < -5.0 and not pit_lines.has(float((c.rect as Array)[1])):
			pit_lines.append(float((c.rect as Array)[1]))
	pit_lines.sort()
	for c: Dictionary in plan.columns:
		var r: Array = c.rect
		var grid: float = float(c.grid)
		var size: float = float(c.size)
		var y0: float = float(c.y0)
		var y1: float = float(c.y1)
		var line: int = pit_lines.find(float(r[1])) if y0 < -5.0 else -1
		var x: float = float(r[0])
		var k: int = 1
		while x <= float(r[2]) + 0.01:
			var z: float = float(r[1])
			while z <= float(r[3]) + 0.01:
				g.box(Vector3(x, (y0 + y1) * 0.5, z), Vector3(size, y1 - y0, size), String(c.get("mat", "concrete")))
				if line >= 0:
					_column_tag(Vector3(x, y0 + 2.0, z), size, "%s%d" % [char(65 + line), k])
				z += grid
			x += grid
			k += 1


## Номер колонны тёмной краской на четырёх гранях.
func _column_tag(at: Vector3, size: float, tag: String) -> void:
	for f: Vector3 in [Vector3(0, 0, 1), Vector3(0, 0, -1), Vector3(1, 0, 0), Vector3(-1, 0, 0)]:
		var t := Label3D.new()
		t.text = tag
		t.font_size = 96
		t.pixel_size = 0.004
		t.modulate = Color(0.08, 0.08, 0.08)
		t.outline_size = 0
		t.shaded = true
		generated.add_child(t)
		t.position = at + f * (size * 0.5 + 0.012)
		t.look_at(t.position + f, Vector3.UP)
		t.rotate_object_local(Vector3.UP, PI)


## Уличные лестницы шириной от STAIR_MARK_W (спуски в переход, у вокзала, на насыпь): кромка первой и последней ступени —
## жёлтой краской (фото владельца 06, кассы вокзала; по нормам — контрастная полоса на крайних ступенях).
const STAIR_MARK_W: float = 1.8
const STAIR_STRIPE_M: float = 0.08


func _stairs(g: RefCounted) -> void:
	for s: Dictionary in plan.stairs:
		var a: Array = s.from
		var b: Array = s.to
		var start := Vector3(float(a[0]), float(a[1]), float(a[2]))
		var finish := Vector3(float(b[0]), float(b[1]), float(b[2]))
		var width: float = float(s.width)
		var count: int = int(s.count)
		var mat: String = String(s.get("mat", "concrete"))
		g.stairs(start, finish, width, count, mat)
		if mat == "concrete" and width >= STAIR_MARK_W and count >= 2:
			_stair_marks(start, finish, width, count)


## Жёлтая полоса у кромки ступени: те же размеры шагов, что у Geometry.stairs (верх ступени i — на (i + 1) / count подъёма).
func _stair_marks(start: Vector3, finish: Vector3, width: float, count: int) -> void:
	var delta: Vector3 = finish - start
	var flat := Vector3(delta.x, 0.0, delta.z)
	var dir: Vector3 = flat.normalized()
	var depth: float = flat.length() / float(count)
	var yaw: float = -atan2(dir.x, -dir.z)
	# кромка — со стороны нижней соседней ступени
	var nose: Vector3 = -dir if delta.y > 0.0 else dir
	for i: int in [0, count - 1]:
		var centre: Vector3 = start + flat * ((float(i) + 0.5) / float(count))
		var top: float = start.y + delta.y * float(i + 1) / float(count)
		var at: Vector3 = centre + nose * (depth * 0.5 - STAIR_STRIPE_M * 0.5 - 0.01)
		StreetPaving.paint_node(generated, "yellow", Vector3(at.x, top + 0.004, at.z), Vector2(width - 0.1, STAIR_STRIPE_M), yaw)


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


## Паркинг −1 как в зале D стенда паркинга (tools/parking_probe, выбор владельца 2026-10-29; владелец 2026-11-07: «сделать
## как на стенде»): жёлто-чёрная разметка низа колонн, красные трубы спринклеров, кабельные лотки, зелёные указатели выезда.
const PIT_COLORS: Dictionary = {"hazard_yellow": Color(0.85, 0.66, 0.08), "pipe_red": Color(0.62, 0.1, 0.08),
	"tray": Color(0.4, 0.42, 0.44), "exit_sign": Color(0.1, 0.55, 0.25)}
## Светильники паркинга: люминесцентные полосы, холодный свет; каждый третий не горит.
const PIT_LAMP_COLOR: Color = Color(0.92, 0.97, 1.0)
const PIT_LAMP_ENERGY: float = 1.3
const PIT_LAMP_RANGE: float = 15.0
## Рассеянная подсветка паркинга (владелец 2026-11-07: «пару источников запечённого рассеянного света сбоку или снизу,
## чтобы совсем темноты не было»): неподвижные, без теней и бликов.
##   снизу — отражённый от бетонного пола свет под каждым горящим светильником (подсвечивает потолок, балки, днища машин);
##   сбоку — дневной свет из проёмов двух рамп вдоль торцевых проездов, по времени рейда (ночью почти нет);
##   нижняя граница — снимок отражений на весь паркинг один раз при загрузке с тусклым постоянным рассеянным светом.
const PIT_BOUNCE_COLOR: Color = Color(0.86, 0.85, 0.82)
const PIT_BOUNCE_ENERGY: float = 0.32
const PIT_BOUNCE_RANGE: float = 10.0
const PIT_BOUNCE_LIFT: float = 0.6
const PIT_RAMP_COLOR: Color = Color(0.84, 0.9, 1.0)
const PIT_RAMP_ENERGY: float = 2.2
const PIT_RAMP_RANGE: float = 34.0
const PIT_RAMP_ANGLE: float = 62.0
const PIT_RAMP_BY_TIME: Dictionary = {"day": 1.0, "dusk": 0.5, "night": 0.06}
const PIT_AMBIENT_COLOR: Color = Color(0.55, 0.58, 0.62)
const PIT_AMBIENT_ENERGY: float = 0.45


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
	result["fountain_floor"] = side
	result["fountain_tile"] = StreetPaving.tile_material()
	# газон — основа под травой DistrictGrass; паркинг −1 — как в зале D стенда паркинга
	result["grass"] = StreetPaving.material("lawn", false)
	result["pit_floor"] = StreetPaving.material("pit_floor", false)
	for key: String in PIT_COLORS:
		var pm := StandardMaterial3D.new()
		pm.albedo_color = PIT_COLORS[key]
		pm.roughness = 0.6 if key == "pipe_red" else (0.5 if key == "tray" else 0.8)
		pm.metallic = 0.6 if key == "tray" else 0.0
		if key == "exit_sign":
			pm.emission_enabled = true
			pm.emission = PIT_COLORS[key]
			pm.emission_energy_multiplier = 1.6
		result[key] = pm
	for key: String in EXTRA_COLORS:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		m.albedo_color = EXTRA_COLORS[key]
		m.roughness = 0.6
		if key.begins_with("loot"):
			m.emission_enabled = true
			m.emission = m.albedo_color * 0.35
		result[key] = m
	return result


## Свет перехода — аварийный (тёплый); в паркинге −1 — люминесцентные светильники как в зале D стенда: холодный свет,
## каждый третий погас (видна только полоса).
func _lamps() -> void:
	var pit: Rect2 = _pit_rect()
	var lit_mat := StandardMaterial3D.new()
	lit_mat.albedo_color = Color(0.9, 0.93, 0.95)
	lit_mat.emission_enabled = true
	lit_mat.emission = PIT_LAMP_COLOR
	lit_mat.emission_energy_multiplier = 4.0
	var off_mat := StandardMaterial3D.new()
	off_mat.albedo_color = Color(0.75, 0.77, 0.78)
	off_mat.roughness = 0.5
	var n: int = 0
	for l: Array in plan.get("lamps", []):
		var at := Vector3(float(l[0]), float(l[1]), float(l[2]))
		var in_pit: bool = pit.has_point(Vector2(at.x, at.z)) and at.y < -0.5
		if in_pit:
			var lit: bool = n % 3 != 2
			var fixture := MeshInstance3D.new()
			var box := BoxMesh.new()
			box.size = Vector3(1.4, 0.07, 0.22)
			fixture.mesh = box
			fixture.material_override = lit_mat if lit else off_mat
			fixture.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			generated.add_child(fixture)
			fixture.position = at + Vector3(0.0, 0.06, 0.0)
			n += 1
			if not lit:
				continue
		var light: OmniLight3D = OmniLight3D.new()
		light.light_energy = PIT_LAMP_ENERGY if in_pit else float(l[3])
		light.omni_range = PIT_LAMP_RANGE if in_pit else float(l[4])
		light.light_color = PIT_LAMP_COLOR if in_pit else Color(1.0, 0.85, 0.6)
		light.shadow_enabled = false
		generated.add_child(light)
		light.position = at
		if in_pit:
			_soft_light(Vector3(at.x, _pit_floor_y() + PIT_BOUNCE_LIFT, at.z), PIT_BOUNCE_COLOR, PIT_BOUNCE_ENERGY, PIT_BOUNCE_RANGE)
	if pit.has_area():
		_pit_fill(pit)


## Неподвижный рассеянный свет без теней и бликов (подсветка, как запечённая).
func _soft_light(at: Vector3, color: Color, energy: float, reach: float) -> OmniLight3D:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = reach
	l.omni_attenuation = 0.6
	l.light_specular = 0.0
	l.shadow_enabled = false
	l.light_bake_mode = Light3D.BAKE_STATIC
	generated.add_child(l)
	l.position = at
	return l


## Сбоку — дневной свет из проёмов рамп (рампы плана, что уходят под землю): широкий мягкий прожектор у низа рампы
## вдоль неё внутрь; нижняя граница — снимок отражений на весь паркинг с тусклым постоянным рассеянным светом.
func _pit_fill(pit: Rect2) -> void:
	var floor_y: float = _pit_floor_y()
	var by_time: float = float(PIT_RAMP_BY_TIME.get(String(RaidConditions.current.get("time", "day")), 1.0))
	for r: Dictionary in plan.get("ramps", []):
		var y0: float = float(r.y0)
		var y1: float = float(r.y1)
		if minf(y0, y1) > floor_y + 0.5 or String(r.get("mat", "")) != "concrete":
			continue
		var x: float = (float(r.x0) + float(r.x1)) * 0.5
		var z_low: float = float(r.z1) if y1 < y0 else float(r.z0)
		var inward: float = signf(z_low - (float(r.z0) if y1 < y0 else float(r.z1)))
		var spot := SpotLight3D.new()
		spot.light_color = PIT_RAMP_COLOR
		spot.light_energy = PIT_RAMP_ENERGY * by_time
		spot.spot_range = PIT_RAMP_RANGE
		spot.spot_angle = PIT_RAMP_ANGLE
		spot.spot_attenuation = 0.7
		spot.light_specular = 0.0
		spot.shadow_enabled = false
		spot.light_bake_mode = Light3D.BAKE_STATIC
		generated.add_child(spot)
		spot.position = Vector3(x, floor_y + 4.0, z_low - inward * 2.0)
		spot.look_at(Vector3(x, floor_y + 0.5, z_low + inward * 14.0), Vector3.UP)
	var probe := ReflectionProbe.new()
	probe.name = "PitAmbient"
	var top: float = -0.4
	probe.size = Vector3(pit.size.x, top - floor_y, pit.size.y)
	probe.position = Vector3(pit.get_center().x, (floor_y + top) * 0.5, pit.get_center().y)
	probe.interior = true
	probe.box_projection = true
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.ambient_mode = ReflectionProbe.AMBIENT_COLOR
	probe.ambient_color = PIT_AMBIENT_COLOR
	probe.ambient_color_energy = PIT_AMBIENT_ENERGY
	probe.max_distance = maxf(pit.size.x, pit.size.y)
	generated.add_child(probe)


func _pit_floor_y() -> float:
	for sl: Dictionary in plan.get("slabs", []):
		if String(sl.get("id", "")) == "pit_floor":
			return float(sl.y_top)
	return -7.3


## Паркинг −1 в плане: пол — плита pit_floor.
func _pit_rect() -> Rect2:
	for sl: Dictionary in plan.get("slabs", []):
		if String(sl.get("id", "")) == "pit_floor":
			var r: Array = sl.rect
			return Rect2(float(r[0]), float(r[1]), float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
	return Rect2()


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
