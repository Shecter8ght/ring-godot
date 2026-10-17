@tool
extends Node3D
## Рельеф и территория серого черновика ТЦ (data/blockouts/mall_study.json, tools/build_mall_study.py).
## Высоты — по принятой схеме: у здания ровно (пол 1-го этажа на 0), север выше до +3,5 м, южная
## парковка спускается террасами −2 и −4 м за подпорными стенками с пандусами, разгрузочный двор —
## в выемке −4 м с доками, трасса внизу (−5 м). Дороги, парковки с брошенными машинами, площадь,
## сквер, водоём, лес, мосты и граница — условные серые формы для прогулки и замера, не отделка.
## Постройки участков (группа mall_study_snap) встают на землю под собой.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const PLAN: String = "res://data/blockouts/mall_study.json"
## Шаг сетки рельефа, м: меш и коллизия.
const STEP_M: float = 3.0
## Полутолщина «ступени» рельефа под стенкой (стенка 0,6 м): уступ вместе с дроблением (SPLIT_MIN_M) — внутри неё.
const WALL_SOFT_M: float = 0.15
## Рельеф у уступов дробится: ребро клетки делят пополам, если земля посередине уходит от прямой между
## концами больше SPLIT_DEV_M, а само ребро длиннее SPLIT_MIN_M. Решение зависит только от ребра —
## соседние треугольники делят его одинаково, щелей нет. Без этого сетка 3 м превращает уступ под
## стенкой в скат на клетку: вдоль стенок «пила», снизу вал, сверху провал.
const SPLIT_DEV_M: float = 0.05
const SPLIT_MIN_M: float = 0.25

var plan: Dictionary = {}
var generated: Node3D
var boundary: PackedVector2Array
var forests: Array[PackedVector2Array] = []
var flat_r: float = 150.0


func _ready() -> void:
	load_plan()
	rebuild()
	snap_buildings.call_deferred()


func load_plan() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PLAN))
	if not parsed is Dictionary:
		push_error("Не прочитан план черновика ТЦ: " + PLAN)
		return
	plan = parsed as Dictionary
	boundary = poly(plan.boundary)
	forests.clear()
	for points: Array in plan.forest:
		forests.append(poly(points))
	flat_r = float((plan.mall as Dictionary).flat_r)


static func poly(points: Array) -> PackedVector2Array:
	var result: PackedVector2Array = PackedVector2Array()
	for p: Array in points:
		result.append(Vector2(float(p[0]), float(p[1])))
	return result


static func line_distance(p: Vector2, line: PackedVector2Array) -> float:
	var nearest: float = INF
	for i: int in range(line.size() - 1):
		nearest = minf(nearest, p.distance_to(Geometry2D.get_closest_point_to_segment(p, line[i], line[i + 1])))
	return nearest


## Угол точки, как у SectorBuilder.polar: от +X к +Z, градусы (−180…180).
static func angle_of(x: float, z: float) -> float:
	return rad_to_deg(atan2(z, x))


## Лежит ли угол a в дуге, идущей от a0 по возрастанию угла до a1 (с переходом через 180°).
static func in_arc(a: float, a0: float, a1: float) -> bool:
	return fposmod(a - a0, 360.0) <= fposmod(a1 - a0, 360.0)


static func angle_gap(a: float, b: float) -> float:
	return absf(wrapf(a - b, -180.0, 180.0))


static func polar(a_deg: float, r: float) -> Vector2:
	return Vector2(cos(deg_to_rad(a_deg)), sin(deg_to_rad(a_deg))) * r


# ---------------------------------------------------------------- высоты

## Земля без террас, двора и водоёма: север выше, юг к трассе ниже, у здания ровно.
func base_height(x: float, z: float) -> float:
	var lv: Dictionary = plan.levels
	var north: float = float(lv.north) * smoothstep(float(lv.north_from), float(lv.north_to), -z)
	var south: float = float(lv.south) * smoothstep(float(lv.south_from), float(lv.south_to), z)
	var h: float = (north + south) * smoothstep(flat_r, flat_r + 35.0, Vector2(x, z).length())
	var hw: Dictionary = plan.highway
	if z >= float(hw.z) - float(hw.width) * 0.5:
		h = float(hw.y)
	return h


func ground(x: float, z: float) -> float:
	var r: float = Vector2(x, z).length()
	var a: float = angle_of(x, z)
	var base: float = base_height(x, z)
	var h: float = base
	# южная парковка: две террасы за подпорными стенками, в пандусах — плавно
	var t: Dictionary = plan.terraces
	var ta: Array = t.a
	if r > 130.0 and r < 252.0 and in_arc(a, float(ta[0]), float(ta[1])):
		var ramp: bool = false
		for ra: Variant in t.ramps:
			ramp = ramp or angle_gap(a, float(ra)) < float(t.ramp_half_deg)
		var soft: float = float(t.ramp_len) * 0.5 if ramp else WALL_SOFT_M
		var level: float = 0.0
		var walls: Array = t.walls
		var steps: Array = t.steps
		var previous: float = 0.0
		for i: int in range(walls.size()):
			level += (float(steps[i]) - previous) * smoothstep(float(walls[i]) - soft, float(walls[i]) + soft, r)
			previous = float(steps[i])
		h = lerpf(minf(level, base), base, smoothstep(236.0, 252.0, r))
	# разгрузочный двор в выемке; пандус для фур к объездной
	var y: Dictionary = plan.yard
	var ya: Array = y.a
	var yr: Array = y.r
	if in_arc(a, float(ya[0]), float(ya[1])):
		if r >= float(yr[0]) - WALL_SOFT_M and r <= float(yr[1]) + WALL_SOFT_M:
			h = float(y.floor)
		var rr: Array = y.ramp_r
		if r > float(yr[1]) and r < float(rr[1]) and angle_gap(a, float(y.ramp_a)) < float(y.ramp_half_deg):
			h = lerpf(float(y.floor), base, (r - float(yr[1])) / (float(rr[1]) - float(yr[1])))
	# противопожарный водоём — чаша в земле
	var pond: Dictionary = plan.pond
	var q: float = _pond_q(x, z)
	if q < 1.0:
		h -= float(pond.depth) * (1.0 - q)
	return h


## Где точка в эллипсе водоёма: 0 — центр, 1 — берег.
func _pond_q(x: float, z: float) -> float:
	var pond: Dictionary = plan.pond
	var at: Array = pond.at
	var size: Array = pond.size
	var d: Vector2 = (Vector2(x, z) - Vector2(float(at[0]), float(at[1]))).rotated(-deg_to_rad(float(pond.yaw)))
	return pow(d.x / (float(size[0]) * 0.5), 2.0) + pow(d.y / (float(size[1]) * 0.5), 2.0)


# ---------------------------------------------------------------- сборка

func rebuild() -> void:
	if plan.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Landscape"
	add_child(generated)
	var g: RefCounted = Geometry.new(generated, _palette())
	_terrain(g)
	_surfaces(g)
	_roads(g)
	_terrace_walls(g)
	_yard(g)
	_plaza(g)
	_cars(g)
	_highway(g)
	_bridges(g)
	_pond_water(g)
	_trees(g)
	_markers(g)
	_boundary(g)
	g.finish()


func _palette() -> Dictionary:
	var result: Dictionary = Geometry.materials()
	var extra: Dictionary = {
		"grass": Color("6a7350"), "plaza": Color("a49c86"), "parking": Color("5f625d"), "pit": Color("6d6b63"),
		"car_a": Color("6f7880"), "car_b": Color("8b8a83"), "car_c": Color("5d5853"), "car_d": Color("8d7a63"),
		"spawn": Color("3d6fb5"), "exit": Color("3c9b5a"), "exit_cond": Color("c48a2c"), "danger": Color("a8473d")}
	for key: String in extra:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = extra[key]
		material.roughness = 0.9
		result[key] = material
	return result


func _terrain(g: RefCounted) -> void:
	var bounds: Array = plan.bounds
	var x0: float = float(bounds[0])
	var z0: float = float(bounds[1])
	var nx: int = int((float(bounds[2]) - x0) / STEP_M)
	var nz: int = int((float(bounds[3]) - z0) / STEP_M)
	var mall_r: float = float((plan.mall as Dictionary).r)
	# высоты считаются один раз на узел сетки
	var heights: PackedFloat32Array = PackedFloat32Array()
	heights.resize((nx + 1) * (nz + 1))
	for iz: int in range(nz + 1):
		for ix: int in range(nx + 1):
			heights[iz * (nx + 1) + ix] = ground(x0 + float(ix) * STEP_M, z0 + float(iz) * STEP_M)
	var faces: PackedVector3Array = PackedVector3Array()
	for iz: int in range(nz):
		for ix: int in range(nx):
			var x: float = x0 + float(ix) * STEP_M
			var z: float = z0 + float(iz) * STEP_M
			# под зданием земли нет — там пол 1-го этажа
			if Vector2(x + STEP_M * 0.5, z + STEP_M * 0.5).length() < mall_r - 3.0:
				continue
			var a: Vector3 = Vector3(x, heights[iz * (nx + 1) + ix], z)
			var b: Vector3 = Vector3(x + STEP_M, heights[iz * (nx + 1) + ix + 1], z)
			var c: Vector3 = Vector3(x + STEP_M, heights[(iz + 1) * (nx + 1) + ix + 1], z + STEP_M)
			var d: Vector3 = Vector3(x, heights[(iz + 1) * (nx + 1) + ix], z + STEP_M)
			var key: String = "grass" if Geometry2D.is_point_in_polygon(Vector2(x, z), boundary) else "ground"
			_terrain_tri(g, faces, a, b, c, key, 0)
			_terrain_tri(g, faces, a, c, d, key, 0)
	var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new()
	shape.set_faces(faces)
	shape.backface_collision = true
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.name = "Terrain"
	cs.shape = shape
	g.body.add_child(cs)


## Треугольник рельефа (или накладки на lift выше): рёбра через уступ делятся (см. SPLIT_DEV_M), остальные — как есть.
func _terrain_tri(g: RefCounted, faces: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3, key: String, depth: int, lift: float = 0.0) -> void:
	var mab: Vector3 = _split_point(a, b, depth, lift)
	var mbc: Vector3 = _split_point(b, c, depth, lift)
	var mca: Vector3 = _split_point(c, a, depth, lift)
	var split: int = int(is_finite(mab.y)) + int(is_finite(mbc.y)) + int(is_finite(mca.y))
	if split == 0:
		g.tri(a, b, c, key)
		faces.append_array(PackedVector3Array([a, b, c]))
		return
	if split == 3:
		_terrain_tri(g, faces, a, mab, mca, key, depth + 1, lift)
		_terrain_tri(g, faces, mab, b, mbc, key, depth + 1, lift)
		_terrain_tri(g, faces, mca, mbc, c, key, depth + 1, lift)
		_terrain_tri(g, faces, mab, mbc, mca, key, depth + 1, lift)
		return
	# одно или два ребра: поворачиваем так, чтобы делилось ab (и bc), а ca — нет
	if split == 1:
		if is_finite(mbc.y):
			_terrain_tri_one(g, faces, b, c, a, mbc, key, depth, lift)
		elif is_finite(mca.y):
			_terrain_tri_one(g, faces, c, a, b, mca, key, depth, lift)
		else:
			_terrain_tri_one(g, faces, a, b, c, mab, key, depth, lift)
		return
	if not is_finite(mca.y):
		_terrain_tri_two(g, faces, a, b, c, mab, mbc, key, depth, lift)
	elif not is_finite(mab.y):
		_terrain_tri_two(g, faces, b, c, a, mbc, mca, key, depth, lift)
	else:
		_terrain_tri_two(g, faces, c, a, b, mca, mab, key, depth, lift)


## Делится только ab (точка m).
func _terrain_tri_one(g: RefCounted, faces: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3, m: Vector3, key: String, depth: int, lift: float) -> void:
	_terrain_tri(g, faces, a, m, c, key, depth + 1, lift)
	_terrain_tri(g, faces, m, b, c, key, depth + 1, lift)


## Делятся ab (m1) и bc (m2), ca — нет.
func _terrain_tri_two(g: RefCounted, faces: PackedVector3Array, a: Vector3, b: Vector3, c: Vector3, m1: Vector3, m2: Vector3, key: String, depth: int, lift: float) -> void:
	_terrain_tri(g, faces, m1, b, m2, key, depth + 1, lift)
	_terrain_tri(g, faces, a, m1, m2, key, depth + 1, lift)
	_terrain_tri(g, faces, a, m2, c, key, depth + 1, lift)


## Середина ребра на земле, если ребро надо делить; иначе y = NAN. Ровные рёбра (перепад концов
## меньше 0,2 м) не проверяются — землю там не спрашиваем, так быстрее.
func _split_point(p: Vector3, q: Vector3, depth: int, lift: float) -> Vector3:
	if depth >= 10 or absf(p.y - q.y) < 0.2 or Vector2(p.x - q.x, p.z - q.z).length() < SPLIT_MIN_M:
		return Vector3(0.0, NAN, 0.0)
	var m: Vector3 = (p + q) * 0.5
	var h: float = ground(m.x, m.z) + lift
	if absf(h - m.y) < SPLIT_DEV_M:
		return Vector3(0.0, NAN, 0.0)
	return Vector3(m.x, h, m.z)


## Накладка поверх рельефа (асфальт, плитка): на уступе дробится, как сама земля, — иначе её край
## ложится скатом поперёк стенки. Коллизии у накладки нет.
func _drape_quad(g: RefCounted, pts: Array[Vector3], key: String, lift: float) -> void:
	var scratch: PackedVector3Array = PackedVector3Array()
	_terrain_tri(g, scratch, pts[0], pts[1], pts[2], key, 0, lift)
	_terrain_tri(g, scratch, pts[0], pts[2], pts[3], key, 0, lift)


## Кольцевой участок по земле (тонкая накладка поверх рельефа).
func _annulus(g: RefCounted, a0: float, a1: float, r0: float, r1: float, key: String, lift: float) -> void:
	var span: float = fposmod(a1 - a0, 360.0)
	if span < 0.01:
		span = 360.0
	var na: int = maxi(2, int(span / 2.0))
	var nr: int = maxi(1, int((r1 - r0) / 4.0))
	for i: int in range(na):
		for j: int in range(nr):
			var pa: float = a0 + span * float(i) / float(na)
			var pb: float = a0 + span * float(i + 1) / float(na)
			var ra: float = lerpf(r0, r1, float(j) / float(nr))
			var rb: float = lerpf(r0, r1, float(j + 1) / float(nr))
			var pts: Array[Vector3] = []
			for v: Vector2 in [polar(pa, ra), polar(pb, ra), polar(pb, rb), polar(pa, rb)]:
				pts.append(Vector3(v.x, ground(v.x, v.y) + lift, v.y))
			_drape_quad(g, pts, key, lift)


func _surfaces(g: RefCounted) -> void:
	var mall: Dictionary = plan.mall
	var lane: Array = mall.fire_lane
	_annulus(g, 0.0, 360.0, float(mall.r), float(mall.podium_r), "walk", 0.03)
	_annulus(g, 0.0, 360.0, float(lane[0]), float(lane[1]), "road", 0.035)
	for p: Dictionary in plan.parkings:
		var a: Array = p.a
		var r: Array = p.r
		_annulus(g, float(a[0]), float(a[1]), float(r[0]), float(r[1]), "parking", 0.03)
	var pl: Dictionary = plan.plaza
	_annulus(g, float(pl.a[0]), float(pl.a[1]), float(pl.r[0]), float(pl.r[1]), "plaza", 0.04)
	var sq: Dictionary = plan.square
	_annulus(g, float(sq.a[0]), float(sq.a[1]), float(sq.r[0]), float(sq.r[1]), "court", 0.03)
	var y: Dictionary = plan.yard
	_annulus(g, float(y.a[0]), float(y.a[1]), float(y.r[0]) + 8.0, float(y.r[1]), "pit", 0.03)


func _strip(g: RefCounted, line: PackedVector2Array, width: float, key: String, offset: float) -> void:
	for i: int in range(line.size() - 1):
		var a: Vector2 = line[i]
		var b: Vector2 = line[i + 1]
		var side: Vector2 = (b - a).normalized().orthogonal() * width * 0.5
		var count: int = maxi(1, int(ceil(a.distance_to(b) / 2.5)))
		for j: int in range(count):
			var p: Vector2 = a.lerp(b, float(j) / float(count))
			var q: Vector2 = a.lerp(b, float(j + 1) / float(count))
			var pts: Array[Vector3] = []
			for v: Vector2 in [p + side, q + side, q - side, p - side]:
				pts.append(Vector3(v.x, ground(v.x, v.y) + offset, v.y))
			_drape_quad(g, pts, key, offset)


func _roads(g: RefCounted) -> void:
	for road: Dictionary in plan.roads:
		var line: PackedVector2Array = poly(road.points)
		var width: float = float(road.width)
		_strip(g, line, width + 2.0, "walk", 0.045)
		_strip(g, line, width, "road", 0.06)


## Подпорная стенка по дуге (или радиусу) между двумя уровнями земли: от нижнего до верхнего + парапет.
func _wall_segment(g: RefCounted, p: Vector2, q: Vector2, probe: Vector2) -> void:
	var mid: Vector2 = (p + q) * 0.5
	var y_a: float = ground(mid.x + probe.x, mid.y + probe.y)
	var y_b: float = ground(mid.x - probe.x, mid.y - probe.y)
	var low: float = minf(y_a, y_b) - 0.3
	var high: float = maxf(y_a, y_b) + 1.0
	if high - low < 1.6:
		return
	var dir: Vector2 = q - p
	g.box(Vector3(mid.x, (low + high) * 0.5, mid.y), Vector3(dir.length() + 0.05, high - low, 0.6), "concrete", true, -atan2(dir.y, dir.x))


## Стенка по дуге от a0 до a1 (меньше 180°) с проёмами точно по краям: gaps — середины пандусов
## шириной ±gap_half, openings — проёмы под лестницы (угол середины, полуширина в градусах).
func _wall_arc(g: RefCounted, r: float, a0: float, a1: float, gaps: Array, gap_half: float, openings: Array[Vector2] = []) -> void:
	var span: float = fposmod(a1 - a0, 360.0)
	var cuts: Array[Vector2] = openings.duplicate()
	for ga: Variant in gaps:
		cuts.append(Vector2(float(ga), gap_half))
	# куски стенки между проёмами — смещения от a0
	var pieces: Array[Vector2] = [Vector2(0.0, span)]
	for cut: Vector2 in cuts:
		var c: float = wrapf(cut.x - a0, -180.0, 180.0)
		var rest: Array[Vector2] = []
		for p: Vector2 in pieces:
			if c + cut.y <= p.x or c - cut.y >= p.y:
				rest.append(p)
				continue
			if c - cut.y > p.x:
				rest.append(Vector2(p.x, c - cut.y))
			if c + cut.y < p.y:
				rest.append(Vector2(c + cut.y, p.y))
		pieces = rest
	for p: Vector2 in pieces:
		var n: int = maxi(1, ceili((p.y - p.x) / 1.5))
		for i: int in range(n):
			var pa: float = a0 + lerpf(p.x, p.y, float(i) / float(n))
			var pb: float = a0 + lerpf(p.x, p.y, float(i + 1) / float(n))
			_wall_segment(g, polar(pa, r), polar(pb, r), polar((pa + pb) * 0.5, 2.0))


func _wall_radial(g: RefCounted, a: float, r0: float, r1: float, inside_sign: float) -> void:
	var n: int = maxi(1, int((r1 - r0) / 3.0))
	var normal: Vector2 = polar(a + 90.0 * inside_sign, 2.0)
	for i: int in range(n):
		_wall_segment(g, polar(a, lerpf(r0, r1, float(i) / float(n))), polar(a, lerpf(r0, r1, float(i + 1) / float(n))), normal)


func _terrace_walls(g: RefCounted) -> void:
	var t: Dictionary = plan.terraces
	var a: Array = t.a
	var half_w: float = float(t.stair_w) * 0.5
	for r: Variant in t.walls:
		var openings: Array[Vector2] = []
		for st: Dictionary in t.stairs:
			if is_equal_approx(float(st.r), float(r)):
				openings.append(Vector2(float(st.a), rad_to_deg((half_w + 0.1) / float(r))))
		_wall_arc(g, float(r), float(a[0]), float(a[1]), t.ramps, float(t.ramp_half_deg), openings)
	# края террас по бокам — тоже стенки, точно по уступу (снаружи террас земля выше); где уступа нет,
	# куски стенки не ставятся (см. _wall_segment)
	_wall_radial(g, float(a[0]), 168.0, 254.0, 1.0)
	_wall_radial(g, float(a[1]), 168.0, 254.0, -1.0)
	# бока пандусов: у стенки террасы пандус ниже соседней земли
	for ra: Variant in t.ramps:
		for w: Variant in t.walls:
			for side: float in [-1.0, 1.0]:
				_wall_radial(g, float(ra) + side * float(t.ramp_half_deg), float(w) - float(t.ramp_len) * 0.5, float(w) + float(t.ramp_len) * 0.5, side)
	# лестницы галереи автостанции через стенки: марш снизу к кромке и площадка наверху в проёме стенки
	for st: Dictionary in t.stairs:
		var sa: float = float(st.a)
		var w: float = float(st.r)
		var low: Vector2 = polar(sa, w + 4.6)
		var high: Vector2 = polar(sa, w + 0.4)
		var upper: Vector2 = polar(sa, w - 2.0)
		var top: float = ground(upper.x, upper.y)
		g.stairs(Vector3(low.x, ground(low.x, low.y), low.y), Vector3(high.x, top, high.y), float(t.stair_w), 12, "concrete")
		var landing: Vector2 = polar(sa, w - 1.8)
		g.box(Vector3(landing.x, top - 0.5, landing.y), Vector3(float(t.stair_w) + 0.6, 1.0, 4.6), "concrete", true, -deg_to_rad(sa + 90.0))


func _yard(g: RefCounted) -> void:
	var y: Dictionary = plan.yard
	var a: Array = y.a
	var r: Array = y.r
	var dock: Array = y.dock
	var top: float = float(y.dock_top)
	var floor_y: float = float(y.floor)
	var a0: float = float(a[0])
	var a1: float = float(a[1])
	var ds: Dictionary = dock_stair()
	# стенка у пожарного проезда: проём под площадку лестницы с доков наверх
	_wall_arc(g, float(r[0]), a0, a1, [], 0.0, [Vector2(float(ds.landing_a), rad_to_deg(1.9 / float(r[0])))])
	_wall_radial(g, a0, float(r[0]), float(r[1]), -1.0)
	_wall_radial(g, a1, float(r[0]), float(r[1]), 1.0)
	_wall_arc(g, float(r[1]), a0, a1, [float(y.ramp_a)], float(y.ramp_half_deg))
	var rr: Array = y.ramp_r
	_wall_radial(g, float(y.ramp_a) - float(y.ramp_half_deg), float(r[1]), float(rr[1]), -1.0)
	_wall_radial(g, float(y.ramp_a) + float(y.ramp_half_deg), float(r[1]), float(rr[1]), 1.0)
	# доковая платформа на высоте кузова: фуры подходят к ней задом
	var span: float = fposmod(a1 - a0, 360.0)
	var n: int = int(span / 1.5)
	var mid_r: float = (float(dock[0]) + float(dock[1])) * 0.5
	for i: int in range(n):
		var pa: float = a0 + span * float(i) / float(n)
		var pb: float = a0 + span * float(i + 1) / float(n)
		var p: Vector2 = polar(pa, mid_r)
		var q: Vector2 = polar(pb, mid_r)
		var mid: Vector2 = (p + q) * 0.5
		var dir: Vector2 = q - p
		g.box(Vector3(mid.x, (floor_y + top) * 0.5, mid.y), Vector3(dir.length() + 0.05, top - floor_y, float(dock[1]) - float(dock[0])), "slab", true, -atan2(dir.y, dir.x))
	# со двора на платформу — две короткие лестницы; с платформы наверх — вдоль стенки к проёму
	for sa: float in [a0 + span * 0.25, a0 + span * 0.75]:
		var low: Vector2 = polar(sa, float(dock[1]) + 4.2)
		var high: Vector2 = polar(sa, float(dock[1]) + 0.1)
		g.stairs(Vector3(low.x, floor_y, low.y), Vector3(high.x, top, high.y), 2.0, 8, "concrete")
	var s0: Vector2 = ds.s0
	var s1: Vector2 = ds.s1
	g.stairs(Vector3(s0.x, top, s0.y), Vector3(s1.x, 0.0, s1.y), 2.0, 16, "concrete")
	# площадка наверху лестницы впритык к последней ступени: через проём в стенке к пожарному проезду
	var landing: Vector2 = ds.landing
	g.box(Vector3(landing.x, -0.48, landing.y), Vector3(5.4, 1.0, float(ds.landing_len)), "concrete", true, -deg_to_rad(float(ds.landing_a) + 90.0))


## Лестница с доковой платформы наверх, к пожарному проезду: низ и верх марша (вдоль платформы),
## площадка у проёма в стенке — впритык к верхней ступени. Её же проходит проверка черновика.
func dock_stair() -> Dictionary:
	var y: Dictionary = plan.yard
	var dock: Array = y.dock
	var stair_up: float = (float(y.a[0]) + float(y.a[1])) * 0.5 + 6.0
	var mid_r: float = (float(dock[0]) + float(dock[1])) * 0.5
	# поперёк — от верхней ступени до 4 м за стенку, по дуге 5,4 м: край заходит на 0,2 м под ступень
	var inner: float = float(y.r[0]) - 4.0
	var outer: float = mid_r + 1.5
	var land_r: float = (inner + outer) * 0.5
	var land_a: float = stair_up + rad_to_deg(2.5 / mid_r)
	return {"s0": polar(stair_up - 3.6, mid_r), "s1": polar(stair_up, mid_r), "landing": polar(land_a, land_r),
		"landing_a": land_a, "landing_len": outer - inner, "top": polar(land_a, float(y.r[0]) - 12.0)}


func _plaza(g: RefCounted) -> void:
	var pl: Dictionary = plan.plaza
	var f: Array = pl.fountain
	var c: Vector2 = Vector2(float(f[0]), float(f[1]))
	var fr: float = float(pl.fountain_r)
	# сухой фонтан: низкий бортик по кругу
	for i: int in range(16):
		var p: Vector2 = c + polar(float(i) * 22.5, fr)
		var q: Vector2 = c + polar(float(i + 1) * 22.5, fr)
		var mid: Vector2 = (p + q) * 0.5
		g.box(Vector3(mid.x, 0.3, mid.y), Vector3(p.distance_to(q) + 0.1, 0.6, 0.5), "concrete", true, -atan2((q - p).y, (q - p).x))
	g.box(Vector3(c.x, 0.6, c.y), Vector3(1.6, 1.6, 1.6), "concrete")
	for planter: Array in pl.planters:
		g.box(Vector3(float(planter[0]), 0.45, float(planter[1])), Vector3(9.0, 0.9, 9.0), "concrete")
		g.box(Vector3(float(planter[0]), 1.3, float(planter[1])), Vector3(7.0, 1.0, 7.0), "foliage", false)
	# детская площадка в сквере — несколько низких форм
	var pg: Array = (plan.square as Dictionary).playground
	for k: int in range(4):
		g.box(Vector3(float(pg[0]) - 5.0 + float(k % 2) * 10.0, ground(float(pg[0]), float(pg[1])) + 0.9, float(pg[1]) - 5.0 + float(k / 2) * 10.0), Vector3(2.4, 1.8, 2.4), "accent")


## Брошенные машины рядами (с пропусками, как после бегства): короб седана с коллизией.
func _car(g: RefCounted, at: Vector2, yaw: float, rng: RandomNumberGenerator) -> void:
	var y: float = ground(at.x, at.y)
	var key: String = ["car_a", "car_b", "car_c", "car_d"][rng.randi_range(0, 3)]
	g.box(Vector3(at.x, y + 0.55, at.y), Vector3(1.9, 0.8, 4.6), key, true, yaw)
	g.box(Vector3(at.x, y + 1.2, at.y), Vector3(1.6, 0.55, 2.4), key, false, yaw)


func _cars(g: RefCounted) -> void:
	var t: Dictionary = plan.terraces
	for p: Dictionary in plan.parkings:
		var rows: Dictionary = p.rows
		var a: Array = rows.a
		var r: Array = p.r
		var rng: RandomNumberGenerator = RandomNumberGenerator.new()
		rng.seed = int(rows.seed)
		var span: float = fposmod(float(a[1]) - float(a[0]), 360.0)
		var rad: float = float(r[0]) + 6.0
		while rad < float(r[1]) - 4.0:
			var count: int = int(deg_to_rad(span) * rad / 3.0)
			for i: int in range(count):
				if rng.randf() > float(rows.density):
					continue
				var ang: float = float(a[0]) + span * (float(i) + 0.5) / float(count)
				var at: Vector2 = polar(ang, rad)
				if _car_blocked(at, ang, rad):
					continue
				_car(g, at, deg_to_rad(90.0 - ang + rng.randf_range(-8.0, 8.0)), rng)
			rad += 16.0


## Машине не место у стенок террас, на пандусах, въездах к зданию и внутри построек.
func _car_blocked(at: Vector2, ang: float, rad: float) -> bool:
	var t: Dictionary = plan.terraces
	for w: Variant in t.walls:
		if absf(rad - float(w)) < 3.0:
			return true
	if in_arc(ang, float(t.a[0]), float(t.a[1])):
		for ra: Variant in t.ramps:
			if angle_gap(ang, float(ra)) < float(t.ramp_half_deg) + 1.0:
				return true
	# стенки по краям террас и лестницы галереи
	for edge: Variant in t.a:
		if angle_gap(ang, float(edge)) < rad_to_deg(4.0 / maxf(rad, 1.0)):
			return true
	for st: Dictionary in t.stairs:
		if polar(float(st.a), float(st.r)).distance_to(at) < 9.0:
			return true
	for road: Dictionary in plan.roads:
		if String(road.id).begins_with("entry_") and line_distance(at, poly(road.points)) < float(road.width) * 0.5 + 2.5:
			return true
	for b: Dictionary in plan.buildings:
		var c: Array = b.at
		var span: Array = b.size
		var local: Vector2 = (at - Vector2(float(c[0]), float(c[1]))).rotated(deg_to_rad(float(b.yaw)))
		if absf(local.x) < float(span[0]) * 0.5 + 2.0 and absf(local.y) < float(span[1]) * 0.5 + 2.0:
			return true
	return false


func _highway(g: RefCounted) -> void:
	var hw: Dictionary = plan.highway
	var xs: Array = hw.x
	var z: float = float(hw.z)
	var line: PackedVector2Array = PackedVector2Array([Vector2(float(xs[0]), z), Vector2(float(xs[1]), z)])
	_strip(g, line, float(hw.width), "road", 0.06)
	for zz: float in [z - 0.15, z + 0.15]:
		_strip(g, PackedVector2Array([Vector2(float(xs[0]), zz), Vector2(float(xs[1]), zz)]), 0.15, "stripe", 0.08)
	# пробка брошенных машин; между рядами — пешеходный пропуск
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 7
	var gap: Array = hw.crossing_x
	for i: int in range(70):
		var x: float = float(xs[0]) + 30.0 + float(i) * 12.5 + rng.randf_range(-3.0, 3.0)
		var lane: float = z + [-8.0, -3.0, 3.0, 8.0][rng.randi_range(0, 3)]
		if rng.randf() > 0.72 or (x > float(gap[0]) - 3.0 and x < float(gap[1]) + 3.0) or absf(x - float((plan.foot_bridge as Dictionary).x)) < 5.0:
			continue
		_car(g, Vector2(x, lane), deg_to_rad(90.0 + rng.randf_range(-6.0, 6.0)), rng)


func _bridges(g: RefCounted) -> void:
	# мост с 2-го яруса паркинга к фасаду ТЦ на высоте 2-го этажа (сам этаж пока закрыт)
	var gb: Dictionary = plan.garage_bridge
	var a: Array = gb.from
	var b: Array = gb.to
	var y: float = float(gb.y)
	var w: float = float(gb.width)
	var mid: Vector2 = (Vector2(float(a[0]), float(a[1])) + Vector2(float(b[0]), float(b[1]))) * 0.5
	var length_m: float = absf(float(a[0]) - float(b[0]))
	g.box(Vector3(mid.x, y - 0.2, mid.y), Vector3(length_m, 0.4, w), "slab")
	for side: float in [-1.0, 1.0]:
		g.box(Vector3(mid.x, y + 0.55, mid.y + side * w * 0.5), Vector3(length_m, 1.1, 0.2), "steel")
	for k: int in range(1, 4):
		var px: float = lerpf(float(b[0]), float(a[0]), float(k) / 4.0)
		g.box(Vector3(px, (y - 0.4) * 0.5, mid.y), Vector3(1.0, y - 0.4, 1.0), "concrete")
	# пешеходный мост через трассу: настил и лестницы с обеих сторон
	var fb: Dictionary = plan.foot_bridge
	var x: float = float(fb.x)
	var zs: Array = fb.z
	var fy: float = float(fb.y)
	var fw: float = float(fb.width)
	var z0: float = float(zs[0])
	var z1: float = float(zs[1])
	g.box(Vector3(x, fy - 0.2, (z0 + z1) * 0.5), Vector3(fw, 0.4, z1 - z0), "slab")
	# перила — только над трассой; на концах настила с запада подходят лестницы
	for side: float in [-1.0, 1.0]:
		g.box(Vector3(x + side * fw * 0.5, fy + 0.6, (z0 + z1) * 0.5), Vector3(0.15, 1.2, z1 - z0 - 8.0), "steel", true)
	for end_z: float in [z0 + 1.6, z1 - 1.6]:
		var bottom: Vector2 = Vector2(x - 22.0, end_z)
		var gy: float = ground(bottom.x, bottom.y)
		g.stairs(Vector3(bottom.x, gy, bottom.y), Vector3(x - fw * 0.5 + 0.2, fy, end_z), 2.6, 34, "concrete")
	var hw: Dictionary = plan.highway
	g.box(Vector3(x, (float(hw.y) + fy) * 0.5 - 0.2, float(hw.z)), Vector3(1.2, fy - float(hw.y) - 0.4, 1.2), "concrete")


func _pond_water(g: RefCounted) -> void:
	var pond: Dictionary = plan.pond
	var at: Array = pond.at
	var size: Array = pond.size
	var c: Vector2 = Vector2(float(at[0]), float(at[1]))
	var water_y: float = base_height(c.x, c.y) - float(pond.depth) * 0.35
	var n: int = 32
	for i: int in range(n):
		var p: Vector2 = c + Vector2(cos(TAU * float(i) / float(n)) * float(size[0]) * 0.46, sin(TAU * float(i) / float(n)) * float(size[1]) * 0.46).rotated(deg_to_rad(float(pond.yaw)))
		var q: Vector2 = c + Vector2(cos(TAU * float(i + 1) / float(n)) * float(size[0]) * 0.46, sin(TAU * float(i + 1) / float(n)) * float(size[1]) * 0.46).rotated(deg_to_rad(float(pond.yaw)))
		g.tri(Vector3(c.x, water_y, c.y), Vector3(p.x, water_y, p.y), Vector3(q.x, water_y, q.y), "water")
	# ливнёвка: бетонный лоток к решётке коллектора
	var drain: PackedVector2Array = poly(pond.drain)
	_strip(g, drain, 1.6, "concrete", 0.08)
	var end: Vector2 = drain[drain.size() - 1]
	g.box(Vector3(end.x, ground(end.x, end.y) + 0.7, end.y), Vector3(3.0, 1.6, 2.0), "steel")


func _trees(g: RefCounted) -> void:
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 20261017
	var trunks: Array[Transform3D] = []
	var crowns: Array[Transform3D] = []
	var spots: Array[Vector2] = []
	var bounds: Array = plan.bounds
	# лесополосы по северу и северо-востоку
	var attempts: int = 0
	while spots.size() < 900 and attempts < 20000:
		attempts += 1
		var p: Vector2 = Vector2(rng.randf_range(float(bounds[0]), float(bounds[2])), rng.randf_range(float(bounds[1]), float(bounds[3])))
		var inside: bool = false
		for f: PackedVector2Array in forests:
			inside = inside or Geometry2D.is_point_in_polygon(p, f)
		if inside and _clear_of_roads(p, 3.0):
			spots.append(p)
	# сквер: деревья между дорожками
	var sq: Dictionary = plan.square
	var sa: Array = sq.a
	var sr: Array = sq.r
	var srng: RandomNumberGenerator = RandomNumberGenerator.new()
	srng.seed = int(sq.seed)
	for i: int in range(int(sq.trees)):
		var p: Vector2 = polar(srng.randf_range(float(sa[0]) + 2.0, float(sa[1]) - 2.0), srng.randf_range(float(sr[0]) + 6.0, float(sr[1]) - 4.0))
		if _clear_of_roads(p, 2.0):
			spots.append(p)
	for p: Vector2 in spots:
		var h: float = rng.randf_range(8.0, 16.0)
		var r: float = rng.randf_range(0.15, 0.28)
		var y: float = ground(p.x, p.y)
		trunks.append(Transform3D(Basis.IDENTITY.scaled(Vector3(r, h, r)), Vector3(p.x, y + h * 0.5, p.y)))
		var w: float = rng.randf_range(3.0, 5.5)
		crowns.append(Transform3D(Basis.IDENTITY.scaled(Vector3(w, h * 0.55, w)), Vector3(p.x, y + h * 0.69, p.y)))
		# коллизия — только стволы: кроны не дают невидимых стен
		var shape: CylinderShape3D = CylinderShape3D.new()
		shape.radius = r
		shape.height = h
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.position = Vector3(p.x, y + h * 0.5, p.y)
		g.body.add_child(cs)
	_multimesh("TreeTrunks", trunks, false, g.palette.bark)
	_multimesh("TreeCrowns", crowns, true, g.palette.foliage)


func _clear_of_roads(p: Vector2, margin: float) -> bool:
	for road: Dictionary in plan.roads:
		if line_distance(p, poly(road.points)) < float(road.width) * 0.5 + margin:
			return false
	for b: Dictionary in plan.buildings:
		var at: Array = b.at
		var span: Array = b.size
		if p.distance_to(Vector2(float(at[0]), float(at[1]))) < maxf(float(span[0]), float(span[1])) * 0.6 + 3.0:
			return false
	return true


func _multimesh(node_name: String, transforms: Array[Transform3D], crown: bool, material: Material) -> void:
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = 0.0 if crown else 0.8
	mesh.bottom_radius = 0.5 if crown else 1.0
	mesh.height = 1.0
	mesh.radial_segments = 6
	mesh.rings = 1
	mesh.material = material
	var multi: MultiMesh = MultiMesh.new()
	multi.transform_format = MultiMesh.TRANSFORM_3D
	multi.mesh = mesh
	multi.instance_count = transforms.size()
	for i: int in range(transforms.size()):
		multi.set_instance_transform(i, transforms[i])
	var visual: MultiMeshInstance3D = MultiMeshInstance3D.new()
	visual.name = node_name
	visual.multimesh = multi
	generated.add_child(visual)


## Точки появления (синие), выходы (зелёные — всегда, жёлтые — по условию), подписи участков.
func _markers(g: RefCounted) -> void:
	for s: Dictionary in plan.spawns:
		var at: Array = s.at
		var y: float = ground(float(at[0]), float(at[1]))
		g.box(Vector3(float(at[0]), y + 1.5, float(at[1])), Vector3(0.5, 3.0, 0.5), "spawn", false)
	for e: Dictionary in plan.exits:
		var at: Array = e.at
		var y: float = ground(float(at[0]), float(at[1]))
		g.box(Vector3(float(at[0]), y + 2.0, float(at[1])), Vector3(0.7, 4.0, 0.7), "exit" if bool(e.always) else "exit_cond", false)
	for loc: Dictionary in plan.locations:
		var at: Array = loc.at
		var label: Label3D = Label3D.new()
		label.text = "%d · %s" % [int(loc.id), String(loc.label)]
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.font_size = 96
		label.pixel_size = 0.02
		label.outline_size = 18
		label.modulate = Color("f1ead8")
		label.position = Vector3(float(at[0]), ground(float(at[0]), float(at[1])) + 14.0, float(at[1]))
		generated.add_child(label)


func _boundary(g: RefCounted) -> void:
	var edge: PackedVector2Array = boundary.duplicate()
	edge.append(boundary[0])
	for i: int in range(edge.size() - 1):
		var a: Vector2 = edge[i]
		var b: Vector2 = edge[i + 1]
		var n: int = maxi(1, int(a.distance_to(b) / 9.0))
		for j: int in range(n):
			var p: Vector2 = a.lerp(b, float(j) / float(n))
			g.box(Vector3(p.x, ground(p.x, p.y) + 0.9, p.y), Vector3(0.16, 1.8, 0.16), "accent", false)
		# невидимая стенка по границе участка — дальше карты не уйти
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = Vector3(a.distance_to(b) + 2.0, 40.0, 1.0)
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		var mid: Vector2 = (a + b) * 0.5
		cs.position = Vector3(mid.x, ground(mid.x, mid.y) + 10.0, mid.y)
		cs.rotation.y = -atan2((b - a).y, (b - a).x)
		g.body.add_child(cs)


## Постройки участков (группа mall_study_snap) — на землю под ними: по низшей точке пятна.
func snap_buildings() -> void:
	if plan.is_empty() or not is_inside_tree():
		return
	for node: Node in get_tree().get_nodes_in_group("mall_study_snap"):
		var b: Node3D = node as Node3D
		if b == null:
			continue
		var fp: Vector2 = b.get("footprint") as Vector2
		var low: float = INF
		for k: Vector2 in [Vector2.ZERO, Vector2(-0.45, -0.45), Vector2(0.45, -0.45), Vector2(0.45, 0.45), Vector2(-0.45, 0.45)]:
			var p: Vector3 = b.global_transform * Vector3(k.x * fp.x, 0.0, k.y * fp.y)
			low = minf(low, ground(p.x, p.z))
		b.global_position.y = low
