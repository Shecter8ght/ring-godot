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

## Сетка поиска земляных работ наполнения, м.
const EARTH_CELL: float = 32.0
## Клетка растра «лес / не лес» для окраски земли, м (между клетками — плавно).
const RASTER_CELL: float = 6.0

## Окраска земли (владелец, 2026-10-17: «всё зелёное, будто ТЦ в поле»): трава, сухостой, проплешины,
## подстилка, у воды — грязь и песок, на крутом — глина и камень. Цвет в вершинах, поверх — мелкий шум.
const GRASS_GREEN: Color = Color(0.33, 0.42, 0.22)
const GRASS_LUSH: Color = Color(0.26, 0.37, 0.19)
const GRASS_DRY: Color = Color(0.53, 0.52, 0.33)
const EARTH: Color = Color(0.42, 0.35, 0.26)
const ROCK_FACE: Color = Color(0.53, 0.52, 0.49)
const FOREST_FLOOR: Color = Color(0.33, 0.3, 0.22)
## Мягкие пятна плана (ground.soil): земля, щебень, грязь, песок, сухая трава, гарь — как в mall_study_ground.py.
const SOIL_COLORS: Array[Color] = [Color(0.5, 0.42, 0.31), Color(0.6, 0.59, 0.55), Color(0.34, 0.3, 0.23),
	Color(0.71, 0.65, 0.51), Color(0.66, 0.61, 0.41), Color(0.19, 0.18, 0.16)]
## Площадки плана (ground.zones) и тропы.
const ZONE_COLORS: Dictionary = {"gravel": Color(0.56, 0.55, 0.51), "concrete": Color(0.62, 0.62, 0.58),
	"dirt": Color(0.47, 0.4, 0.3), "path": Color(0.45, 0.39, 0.29)}
## Дальше этого от середины русла речка землю не трогает, м.
const RIVER_REACH: float = 26.0

var plan: Dictionary = {}
var generated: Node3D
var boundary: PackedVector2Array
var forests: Array[PackedVector2Array] = []
var flat_r: float = 150.0
## Где за машиной, стенкой или фонтаном можно укрыться — для замера открытых кусков на подходах.
var cover_spots: PackedVector2Array = PackedVector2Array()
## Земляные работы наполнения (tools/mall_study_filler.py): котлован стройки, отвалы, воронка, кювет у трассы.
## Запись — [вид, параметры…]; сетка по EARTH_CELL отвечает, какие из них рядом с точкой.
var _earth: Array[PackedFloat32Array] = []
var _earth_grid: Dictionary = {}
## Речка рельефа (tools/mall_study_relief.py): вершины русла, расстояние вдоль него, уровни воды, крутизна
## берегов по отрезкам (x — слева, y — справа от хода), броды (x — где вдоль русла, y — полудлина),
## полоса трассы на насыпи, под которой речка в трубе.
var _river: PackedVector2Array = PackedVector2Array()
var _river_s: PackedFloat32Array = PackedFloat32Array()
var _river_water: PackedFloat32Array = PackedFloat32Array()
var _river_banks: PackedVector2Array = PackedVector2Array()
var _river_fords: PackedVector2Array = PackedVector2Array()
var _river_grid: Dictionary = {}
var _river_dry: Vector2 = Vector2.ZERO
var _river_bed_half: float = 3.0
var _river_depth: float = 1.1
## Окраска земли: сетка с цветом в вершинах, кэш цвета по точке, шумы, растр леса, пятна по клеткам.
var _soil_st: SurfaceTool
var _soil_cache: Dictionary = {}
var _noise_low: FastNoiseLite
var _noise_mid: FastNoiseLite
var _noise_hi: FastNoiseLite
var _forest_raster: PackedFloat32Array = PackedFloat32Array()
var _raster_size: Vector2i = Vector2i.ZERO
var _raster_origin: Vector2 = Vector2.ZERO
var _soil_spots: Array = []
var _soil_grid: Dictionary = {}
var _detail: NoiseTexture2D


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
	_load_earth()
	_load_soil()


func _load_earth() -> void:
	_earth.clear()
	_earth_grid.clear()
	var earth: Dictionary = (plan.get("filler", {}) as Dictionary).get("earth", {}) as Dictionary
	for m: Array in earth.get("mounds", []):
		_add_earth(PackedFloat32Array([0.0, m[0], m[1], m[2], m[3], deg_to_rad(float(m[4])), m[5]]),
			Vector2(float(m[0]), float(m[1])), maxf(float(m[2]), float(m[3])))
	for c: Array in earth.get("craters", []):
		_add_earth(PackedFloat32Array([1.0, c[0], c[1], c[2], c[3], c[4]]), Vector2(float(c[0]), float(c[1])), float(c[2]) * 1.6)
	for pit: Array in earth.get("pits", []):
		_add_earth(PackedFloat32Array([2.0, pit[0], pit[1], pit[2], pit[3], deg_to_rad(float(pit[4])), pit[5], pit[6], pit[7], pit[8]]),
			Vector2(float(pit[0]), float(pit[1])), Vector2(float(pit[2]), float(pit[3])).length() * 0.5 + 1.0)
	# горки и утёсы рельефа
	var relief: Dictionary = plan.get("relief", {}) as Dictionary
	for hill: Array in relief.get("hills", []):
		_add_earth(PackedFloat32Array([4.0, hill[0], hill[1], hill[2], hill[3]]), Vector2(float(hill[0]), float(hill[1])), float(hill[2]))
	for cliff: Dictionary in relief.get("cliffs", []):
		var edge: PackedVector2Array = poly(cliff.points)
		var entry: PackedFloat32Array = PackedFloat32Array([5.0, float(cliff.height), float(cliff.fall), float(cliff.side), float(edge.size())])
		var reach: Rect2 = Rect2(edge[0], Vector2.ZERO)
		for q: Vector2 in edge:
			entry.append(q.x)
			entry.append(q.y)
			reach = reach.expand(q)
		var cliff_index: int = _earth.size()
		_earth.append(entry)
		_grid_add(cliff_index, reach.grow(float(cliff.fall) + 2.0))
	_load_river(relief.get("river", {}) as Dictionary)
	for ditch: Dictionary in earth.get("ditches", []):
		var pts: PackedVector2Array = poly(ditch.points)
		var half: float = float(ditch.width) * 0.5
		for i: int in range(pts.size() - 1):
			var a: Vector2 = pts[i]
			var b: Vector2 = pts[i + 1]
			var index: int = _earth.size()
			_earth.append(PackedFloat32Array([3.0, a.x, a.y, b.x, b.y, half, float(ditch.depth)]))
			var box: Rect2 = Rect2(a, Vector2.ZERO).expand(b).grow(half)
			_grid_add(index, box)


## Окраска земли: шумы, растр леса (клетка RASTER_CELL), мягкие пятна плана по клеткам EARTH_CELL.
func _load_soil() -> void:
	_soil_cache.clear()
	_noise_low = _noise(20261017, 0.006, 3)
	_noise_mid = _noise(20261018, 0.035, 3)
	_noise_hi = _noise(20261019, 0.22, 1)
	var bounds: Array = plan.bounds
	_raster_origin = Vector2(float(bounds[0]), float(bounds[1]))
	_raster_size = Vector2i(ceili((float(bounds[2]) - float(bounds[0])) / RASTER_CELL) + 1,
		ceili((float(bounds[3]) - float(bounds[1])) / RASTER_CELL) + 1)
	_forest_raster.resize(_raster_size.x * _raster_size.y)
	for j: int in range(_raster_size.y):
		for i: int in range(_raster_size.x):
			var p: Vector2 = _raster_origin + Vector2(i, j) * RASTER_CELL
			var inside: float = 0.0
			for f: PackedVector2Array in forests:
				if Geometry2D.is_point_in_polygon(p, f):
					inside = 1.0
					break
			_forest_raster[j * _raster_size.x + i] = inside
	_soil_spots = (plan.get("ground", {}) as Dictionary).get("soil", []) as Array
	_soil_grid.clear()
	for index: int in range(_soil_spots.size()):
		var s: Array = _soil_spots[index]
		var reach: float = float(s[2]) * 1.3
		for cx: int in range(floori((float(s[0]) - reach) / EARTH_CELL), floori((float(s[0]) + reach) / EARTH_CELL) + 1):
			for cz: int in range(floori((float(s[1]) - reach) / EARTH_CELL), floori((float(s[1]) + reach) / EARTH_CELL) + 1):
				var key: Vector2i = Vector2i(cx, cz)
				var list: PackedInt32Array = _soil_grid.get(key, PackedInt32Array())
				list.append(index)
				_soil_grid[key] = list


static func _noise(seed_value: int, frequency: float, octaves: int) -> FastNoiseLite:
	var n: FastNoiseLite = FastNoiseLite.new()
	n.seed = seed_value
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	n.frequency = frequency
	n.fractal_octaves = octaves
	return n


## Растр в точке — с плавным переходом между клетками.
func _raster_at(raster: PackedFloat32Array, x: float, z: float) -> float:
	var f: Vector2 = (Vector2(x, z) - _raster_origin) / RASTER_CELL
	var i: int = clampi(floori(f.x), 0, _raster_size.x - 2)
	var j: int = clampi(floori(f.y), 0, _raster_size.y - 2)
	var u: float = clampf(f.x - float(i), 0.0, 1.0)
	var v: float = clampf(f.y - float(j), 0.0, 1.0)
	var w: int = _raster_size.x
	return lerpf(lerpf(raster[j * w + i], raster[j * w + i + 1], u), lerpf(raster[(j + 1) * w + i], raster[(j + 1) * w + i + 1], u), v)


## Цвет земли в точке без уклона: трава и сухостой по шуму, высоте и влажности, проплешины, лесная
## подстилка, грязь у воды, мягкие пятна плана. Считается один раз на точку (кэш по четверти метра).
func _soil_base(x: float, z: float) -> Color:
	var key: Vector2i = Vector2i(roundi(x * 4.0), roundi(z * 4.0))
	if _soil_cache.has(key):
		return _soil_cache[key]
	var low: float = _noise_low.get_noise_2d(x, z)
	var mid: float = _noise_mid.get_noise_2d(x, z)
	var hi: float = _noise_hi.get_noise_2d(x, z)
	var h: float = base_height(x, z)
	var rd: float = river_distance(Vector2(x, z))
	var pq: float = _pond_q(x, z)
	var wet: float = 0.0
	if rd < 32.0:
		wet = 1.0 - smoothstep(8.0, 32.0, rd)
	wet = maxf(wet, 1.0 - smoothstep(1.0, 2.4, pq))
	# сухость: крупный шум, выше по рельефу — суше, у воды — сочнее
	var dry: float = clampf(0.38 + low * 1.0 + h * 0.03, 0.0, 1.0) * (1.0 - wet)
	var c: Color = GRASS_GREEN.lerp(GRASS_DRY, smoothstep(0.45, 0.9, dry))
	c = c.lerp(GRASS_LUSH, wet * 0.75)
	# проплешины и вытоптанное — средний шум
	c = c.lerp(EARTH, smoothstep(0.32, 0.65, mid) * 0.6)
	c = c.lerp(FOREST_FLOOR, _raster_at(_forest_raster, x, z) * 0.85)
	# у кромки речки и водоёма — грязь
	var mud: float = 1.0 - smoothstep(_river_bed_half + 2.5, _river_bed_half + 7.0, rd)
	mud = maxf(mud, 1.0 - smoothstep(0.85, 1.3, pq))
	c = c.lerp(SOIL_COLORS[2], mud * 0.9)
	# мягкие пятна плана: край рваный (тот же средний шум)
	var cell: Vector2i = Vector2i(floori(x / EARTH_CELL), floori(z / EARTH_CELL))
	if _soil_grid.has(cell):
		for index: int in _soil_grid[cell] as PackedInt32Array:
			var s: Array = _soil_spots[index]
			var r: float = float(s[2])
			var d: float = Vector2(x - float(s[0]), z - float(s[1])).length() + mid * r * 0.35
			var w: float = 1.0 - smoothstep(r * 0.5, r * 1.1, d)
			if w > 0.0:
				c = c.lerp(SOIL_COLORS[int(s[3])], w * 0.9)
	c = c * (1.0 + hi * 0.08)
	c.a = 1.0
	_soil_cache[key] = c
	return c


## Треугольник земли с цветом в вершинах; крутой склон — глина, обрыв — камень.
func _soil_tri(a: Vector3, b: Vector3, c: Vector3) -> void:
	var normal: Vector3 = (c - a).cross(b - a).normalized()
	var steep: float = 1.0 - smoothstep(0.66, 0.86, normal.y)
	var rocky: float = 1.0 - smoothstep(0.5, 0.68, normal.y)
	_soil_st.set_normal(normal)
	for v: Vector3 in [a, b, c]:
		var col: Color = _soil_base(v.x, v.z).lerp(EARTH, steep * 0.75).lerp(ROCK_FACE, rocky)
		_soil_st.set_color(col)
		_soil_st.add_vertex(v)


## Мелкий шум поверх цвета (мировые координаты, без швов): трава и асфальт не плоские.
func _detail_texture() -> NoiseTexture2D:
	if _detail != null:
		return _detail
	var n: FastNoiseLite = _noise(7, 0.045, 4)
	_detail = NoiseTexture2D.new()
	_detail.width = 256
	_detail.height = 256
	_detail.seamless = true
	_detail.noise = n
	var ramp: Gradient = Gradient.new()
	ramp.set_color(0, Color(0.74, 0.74, 0.74))
	ramp.set_color(1, Color(1.0, 1.0, 1.0))
	_detail.color_ramp = ramp
	return _detail


func _with_detail(material: StandardMaterial3D, scale: float) -> StandardMaterial3D:
	material.albedo_texture = _detail_texture()
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.uv1_scale = Vector3.ONE * scale
	material.albedo_color = material.albedo_color * 1.14
	return material


func _add_earth(entry: PackedFloat32Array, at: Vector2, reach: float) -> void:
	var index: int = _earth.size()
	_earth.append(entry)
	_grid_add(index, Rect2(at - Vector2(reach, reach), Vector2(reach, reach) * 2.0))


func _grid_add(index: int, box: Rect2) -> void:
	for i: int in range(floori(box.position.x / EARTH_CELL), floori(box.end.x / EARTH_CELL) + 1):
		for j: int in range(floori(box.position.y / EARTH_CELL), floori(box.end.y / EARTH_CELL) + 1):
			var key: Vector2i = Vector2i(i, j)
			if not _earth_grid.has(key):
				_earth_grid[key] = PackedInt32Array()
			var list: PackedInt32Array = _earth_grid[key]
			list.append(index)
			_earth_grid[key] = list


## Утёс: [5, высота, fall, сторона, число точек, x0, z0, x1, z1…]; сторона +1 — верх слева от хода кромки.
func _cliff_offset(e: PackedFloat32Array, p: Vector2) -> float:
	var count: int = int(e[4])
	var best: float = INF
	var signed: float = 0.0
	var along: float = 0.0
	var walked: float = 0.0
	for j: int in range(count - 1):
		var a: Vector2 = Vector2(e[5 + j * 2], e[6 + j * 2])
		var b: Vector2 = Vector2(e[7 + j * 2], e[8 + j * 2])
		var ab: Vector2 = b - a
		var t: float = clampf((p - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		var d: float = p.distance_to(a + ab * t)
		if d < best:
			best = d
			signed = d if ab.cross(p - a) * e[3] > 0.0 else -d
			along = walked + ab.length() * t
		walked += ab.length()
	var taper: float = smoothstep(0.0, 15.0, along) * smoothstep(0.0, 15.0, walked - along)
	return e[1] * taper * smoothstep(-0.8, 0.8, signed) * (1.0 - smoothstep(e[2] * 0.35, e[2], signed))


func _load_river(river: Dictionary) -> void:
	_river = PackedVector2Array()
	_river_s = PackedFloat32Array()
	_river_water = PackedFloat32Array()
	_river_banks = PackedVector2Array()
	_river_fords = PackedVector2Array()
	_river_grid.clear()
	if river.is_empty():
		return
	_river = poly(river.points)
	var walked: float = 0.0
	for i: int in range(_river.size()):
		if i > 0:
			walked += _river[i - 1].distance_to(_river[i])
		_river_s.append(walked)
		_river_water.append(float((river.water as Array)[i]))
	for bank: Array in river.banks:
		_river_banks.append(Vector2(float(bank[0]), float(bank[1])))
	for ford: Dictionary in river.fords:
		_river_fords.append(Vector2(float(ford.s), float(ford.half)))
	var dry: Array = river.dry_z
	_river_dry = Vector2(float(dry[0]), float(dry[1]))
	_river_bed_half = float(river.bed_half)
	_river_depth = float(river.depth)
	for i: int in range(_river.size() - 1):
		var box: Rect2 = Rect2(_river[i], Vector2.ZERO).expand(_river[i + 1]).grow(RIVER_REACH)
		for cx: int in range(floori(box.position.x / EARTH_CELL), floori(box.end.x / EARTH_CELL) + 1):
			for cz: int in range(floori(box.position.y / EARTH_CELL), floori(box.end.y / EARTH_CELL) + 1):
				var key: Vector2i = Vector2i(cx, cz)
				var list: PackedInt32Array = _river_grid.get(key, PackedInt32Array())
				list.append(i)
				_river_grid[key] = list


## Ближайшее место русла: [расстояние, индекс отрезка, доля по отрезку, сторона (0 — слева, 1 — справа)].
func _river_near(p: Vector2) -> Array:
	var key: Vector2i = Vector2i(floori(p.x / EARTH_CELL), floori(p.y / EARTH_CELL))
	if not _river_grid.has(key):
		return [INF, -1, 0.0, 0]
	var best: Array = [INF, -1, 0.0, 0]
	for i: int in _river_grid[key] as PackedInt32Array:
		var a: Vector2 = _river[i]
		var ab: Vector2 = _river[i + 1] - a
		var t: float = clampf((p - a).dot(ab) / ab.length_squared(), 0.0, 1.0)
		var d: float = p.distance_to(a + ab * t)
		if d < float(best[0]):
			best = [d, i, t, 0 if ab.cross(p - a) > 0.0 else 1]
	return best


## Сколько от точки до середины русла (для посадки деревьев и проверок); далеко — INF.
func river_distance(p: Vector2) -> float:
	return float(_river_near(p)[0]) if not _river_grid.is_empty() else INF


## Русло: ровное дно, берега с крутизной своей стороны; на броде дно поднято и берега пологие.
## Под трассой на насыпи речка в трубе — землю там не режет.
func _river_carve(x: float, z: float, h: float) -> float:
	if z > _river_dry.x and z < _river_dry.y:
		return h
	var near: Array = _river_near(Vector2(x, z))
	var d: float = near[0]
	if d > RIVER_REACH:
		return h
	var i: int = near[1]
	var t: float = near[2]
	var water: float = lerpf(_river_water[i], _river_water[i + 1], t)
	var along: float = lerpf(_river_s[i], _river_s[i + 1], t)
	var k: float = _river_banks[i].x if int(near[3]) == 0 else _river_banks[i].y
	var bed: float = water - _river_depth
	for ford: Vector2 in _river_fords:
		var w: float = 1.0 - smoothstep(ford.y, ford.y + 4.0, absf(along - ford.x))
		bed = lerpf(bed, water - 0.35, w)
		k = lerpf(k, 0.2, w)
	return minf(h, bed + maxf(0.0, d - _river_bed_half) * k)


## Уровень воды и полуширина зеркала в точке вдоль русла (s) по сторонам.
func river_water_at(i: int, t: float) -> Vector3:
	var water: float = lerpf(_river_water[i], _river_water[i + 1], t)
	var along: float = lerpf(_river_s[i], _river_s[i + 1], t)
	var depth: float = _river_depth
	var kl: float = _river_banks[i].x
	var kr: float = _river_banks[i].y
	for ford: Vector2 in _river_fords:
		var w: float = 1.0 - smoothstep(ford.y, ford.y + 4.0, absf(along - ford.x))
		depth = lerpf(depth, 0.35, w)
		kl = lerpf(kl, 0.2, w)
		kr = lerpf(kr, 0.2, w)
	return Vector3(water, _river_bed_half + depth / kl, _river_bed_half + depth / kr)


## Поправка высоты от земляных работ в точке.
func _earth_offset(x: float, z: float) -> float:
	var key: Vector2i = Vector2i(floori(x / EARTH_CELL), floori(z / EARTH_CELL))
	if not _earth_grid.has(key):
		return 0.0
	var dh: float = 0.0
	for index: int in _earth_grid[key] as PackedInt32Array:
		var e: PackedFloat32Array = _earth[index]
		match int(e[0]):
			0:
				# отвал: приподнятый косинус по эллипсу
				var d: Vector2 = Vector2(x - e[1], z - e[2]).rotated(-e[5])
				var q: float = sqrt(pow(d.x / e[3], 2.0) + pow(d.y / e[4], 2.0))
				if q < 1.0:
					dh += e[6] * 0.5 * (1.0 + cos(PI * q))
			1:
				# воронка: чаша и невысокий вал по краю
				var q: float = Vector2(x - e[1], z - e[2]).length() / e[3]
				if q < 1.0:
					dh -= e[4] * (1.0 - q * q)
				if q < 1.6:
					dh += e[5] * exp(-pow((q - 1.0) / 0.22, 2.0))
			2:
				# котлован: откосы по краям, на +X — длинный пандус для машин в полосе ramp_w
				var d: Vector2 = Vector2(x - e[1], z - e[2]).rotated(-e[5])
				var hx: float = e[3] * 0.5
				var hz: float = e[4] * 0.5
				if absf(d.x) < hx and absf(d.y) < hz:
					var slope: float = e[7]
					var east: float = lerpf(e[8], slope, smoothstep(e[9] * 0.5 - 2.0, e[9] * 0.5 + 2.0, absf(d.y)))
					var k: float = minf(minf(smoothstep(0.0, slope, d.x + hx), smoothstep(0.0, east, hx - d.x)),
						minf(smoothstep(0.0, slope, d.y + hz), smoothstep(0.0, slope, hz - d.y)))
					dh -= e[6] * k
			4:
				# горка: приподнятый косинус
				var q: float = Vector2(x - e[1], z - e[2]).length() / e[3]
				if q < 1.0:
					dh += e[4] * 0.5 * (1.0 + cos(PI * q))
			5:
				# утёс: уступ по кромке, верх сходит к земле за fall; концы кромки сходят на нет — обойти можно
				dh += _cliff_offset(e, Vector2(x, z))
			3:
				# кювет: косинус поперёк отрезка, концы скруглены
				var p: Vector2 = Vector2(x, z)
				var dist: float = Geometry2D.get_closest_point_to_segment(p, Vector2(e[1], e[2]), Vector2(e[3], e[4])).distance_to(p)
				if dist < e[5]:
					dh -= e[6] * 0.5 * (1.0 + cos(PI * dist / e[5]))
	return dh


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
	if not _earth_grid.is_empty():
		h += _earth_offset(x, z)
	if not _river_grid.is_empty():
		h = _river_carve(x, z, h)
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
	cover_spots = PackedVector2Array()
	var g: RefCounted = Geometry.new(generated, _palette())
	_terrain(g)
	_ground_cover(g)
	_surfaces(g)
	_roads(g)
	_terrace_walls(g)
	_yard(g)
	_plaza(g)
	_cars(g)
	_highway(g)
	_bridges(g)
	_pond_water(g)
	_river_features(g)
	_trees(g)
	_markers(g)
	_boundary(g)
	g.finish()


func _palette() -> Dictionary:
	var result: Dictionary = Geometry.materials()
	var extra: Dictionary = {
		"grass": Color("6a7350"), "plaza": Color("a49c86"), "parking": Color("5f625d"), "pit": Color("6d6b63"),
		"car_a": Color("6f7880"), "car_b": Color("8b8a83"), "car_c": Color("5d5853"), "car_d": Color("8d7a63"),
		"spawn": Color("3d6fb5"), "exit": Color("3c9b5a"), "exit_cond": Color("c48a2c"), "danger": Color("a8473d"),
		"rock": Color("6f6c63"), "timber": Color("6e5a43")}
	for key: String in ZONE_COLORS:
		extra[key] = ZONE_COLORS[key]
	for key: String in extra:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = extra[key]
		material.roughness = 0.9
		result[key] = material
	# асфальт, плитка, щебень и грунт — с тем же мелким шумом, что и земля: не плоские заливки
	for key: String in ["road", "walk", "parking", "plaza", "court", "pit", "mud"] + ZONE_COLORS.keys():
		var material: StandardMaterial3D = (result[key] as StandardMaterial3D).duplicate() as StandardMaterial3D
		result[key] = _with_detail(material, 0.22)
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
	# земля — одна сетка с цветом в вершинах (см. _soil_base)
	_soil_st = SurfaceTool.new()
	_soil_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var soil_material: StandardMaterial3D = StandardMaterial3D.new()
	soil_material.vertex_color_use_as_albedo = true
	soil_material.roughness = 0.95
	_soil_st.set_material(_with_detail(soil_material, 0.16))
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
			_terrain_tri(g, faces, a, b, c, "soil", 0)
			_terrain_tri(g, faces, a, c, d, "soil", 0)
	var soil_mesh: MeshInstance3D = MeshInstance3D.new()
	soil_mesh.name = "Mesh_soil"
	soil_mesh.mesh = _soil_st.commit()
	generated.add_child(soil_mesh)
	_soil_st = null
	_soil_cache.clear()
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
		if key == "soil":
			_soil_tri(a, b, c)
		else:
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
			# обход — как у клеток рельефа (лицом вверх); прежний обратный прятал площадь, парковки,
			# пожарный проезд и дно двора — сверху была видна трава
			for v: Vector2 in [polar(pa, ra), polar(pa, rb), polar(pb, rb), polar(pb, ra)]:
				pts.append(Vector3(v.x, ground(v.x, v.y) + lift, v.y))
			_drape_quad(g, pts, key, lift)


## Прямоугольник по земле (площадка, двор): центр, размер (по X и Z до поворота), поворот в градусах.
func _rect_drape(g: RefCounted, center: Vector2, size: Vector2, yaw_deg: float, key: String, lift: float) -> void:
	var nx: int = maxi(1, ceili(size.x / 4.0))
	var nz: int = maxi(1, ceili(size.y / 4.0))
	var yaw: float = deg_to_rad(yaw_deg)
	for i: int in range(nx):
		for j: int in range(nz):
			var pts: Array[Vector3] = []
			for k: Vector2 in [Vector2(i, j), Vector2(i + 1, j), Vector2(i + 1, j + 1), Vector2(i, j + 1)]:
				var v: Vector2 = center + (Vector2(k.x / float(nx) - 0.5, k.y / float(nz) - 0.5) * size).rotated(yaw)
				pts.append(Vector3(v.x, ground(v.x, v.y) + lift, v.y))
			_drape_quad(g, pts, key, lift)


func _surfaces(g: RefCounted) -> void:
	var mall: Dictionary = plan.mall
	var lane: Array = mall.fire_lane
	var pl: Dictionary = plan.plaza
	_annulus(g, 0.0, 360.0, float(mall.r), float(mall.podium_r), "walk", 0.03)
	# пожарный проезд через площадь — её плиткой (машины сюда не ездят, у краёв площади — столбики)
	_annulus(g, float(pl.a[1]), float(pl.a[0]), float(lane[0]), float(lane[1]), "road", 0.035)
	for p: Dictionary in plan.parkings:
		var a: Array = p.a
		var r: Array = p.r
		_annulus(g, float(a[0]), float(a[1]), float(r[0]), float(r[1]), "parking", 0.03)
	_annulus(g, float(pl.a[0]), float(pl.a[1]), float(pl.r[0]), float(pl.r[1]), "plaza", 0.04)
	# аллея от кольцевой к площади — той же плиткой, поверх парковки
	var alley: Dictionary = plan.get("alley", {}) as Dictionary
	if not alley.is_empty():
		_strip(g, poly(alley.points), float(alley.width), "plaza", 0.045)
	# площадки (автобусы у автостанции): прямоугольник по земле
	for apron: Dictionary in plan.get("aprons", []):
		var rect: Array = apron.rect
		_rect_drape(g, Vector2(float(rect[0]), float(rect[1])), Vector2(float(rect[2]), float(rect[3])), float(rect[4]),
			"road" if String(apron.kind) == "road" else String(apron.kind), 0.055)
	var sq: Dictionary = plan.square
	_annulus(g, float(sq.a[0]), float(sq.a[1]), float(sq.r[0]), float(sq.r[1]), "court", 0.03)
	var y: Dictionary = plan.yard
	_annulus(g, float(y.a[0]), float(y.a[1]), float(y.r[0]) + 8.0, float(y.r[1]), "pit", 0.03)


## Площадки (щебень, бетон, асфальт, грунт — с чёткими краями) и грунтовые тропы плана ground.
func _ground_cover(g: RefCounted) -> void:
	var cover: Dictionary = plan.get("ground", {}) as Dictionary
	for zone: Dictionary in cover.get("zones", []):
		var rect: Array = zone.rect
		var kind: String = String(zone.kind)
		_rect_drape(g, Vector2(float(rect[0]), float(rect[1])), Vector2(float(rect[2]), float(rect[3])), float(rect[4]),
			"road" if kind == "asphalt" else kind, 0.02)
	var width: float = float(cover.get("path_width", 1.7))
	for path: Array in cover.get("paths", []):
		_strip(g, poly(path), width, "path", 0.024)


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


## Полоса по земле (колея, тропа) для соседних узлов черновика: дробится на уступах, как земля.
func drape_strip(g: RefCounted, line: PackedVector2Array, width: float, key: String, lift: float) -> void:
	_strip(g, line, width, key, lift)


## Круг по земле (площадка скругления перекрёстка): веер из треугольников, дробится на уступах.
func drape_disk(g: RefCounted, center: Vector2, radius: float, key: String, lift: float) -> void:
	var scratch: PackedVector3Array = PackedVector3Array()
	var c: Vector3 = Vector3(center.x, ground(center.x, center.y) + lift, center.y)
	var n: int = 18
	for i: int in range(n):
		var p: Vector2 = center + polar(360.0 * float(i) / float(n), radius)
		var q: Vector2 = center + polar(360.0 * float(i + 1) / float(n), radius)
		_terrain_tri(g, scratch, c, Vector3(p.x, ground(p.x, p.y) + lift, p.y), Vector3(q.x, ground(q.x, q.y) + lift, q.y), key, 0, lift)


## Занято ли место ряда парковки (стенки террас, пандусы, въезды, аллея, галерея, постройки) — для разметки мест.
func parking_spot_blocked(at: Vector2, ang: float, rad: float) -> bool:
	return _car_blocked(at, ang, rad)


func _roads(g: RefCounted) -> void:
	for road: Dictionary in plan.roads:
		var line: PackedVector2Array = poly(road.points)
		var width: float = float(road.width)
		# у главных — тротуар за бордюром, у местных и загородных — щебёночная обочина
		if String(road.get("class", "main")) == "main":
			_strip(g, line, width + 4.5, "walk", 0.045)
		else:
			_strip(g, line, width + 3.2, "gravel", 0.04)
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
	cover_spots.append(mid)
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
	cover_spots.append(c)
	for planter: Array in pl.planters:
		cover_spots.append(Vector2(float(planter[0]), float(planter[1])))
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
	cover_spots.append(at)
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
		if String(road.id) != "loop" and line_distance(at, poly(road.points)) < float(road.width) * 0.5 + 2.5:
			return true
	# аллея к площади и галерея автостанции идут через парковку — машины не под ними
	var alley: Dictionary = plan.get("alley", {}) as Dictionary
	if not alley.is_empty() and line_distance(at, poly(alley.points)) < float(alley.width) * 0.5 + 2.5:
		return true
	var gallery: Dictionary = plan.get("gallery", {}) as Dictionary
	for part: Array in gallery.get("parts", []):
		if line_distance(at, poly(part)) < float(gallery.width) * 0.5 + 3.0:
			return true
	# теплотрасса наполнения идёт через восточную парковку
	var heat: Array = ((plan.get("filler", {}) as Dictionary).get("lines", {}) as Dictionary).get("heat", {}).get("points", [])
	if heat.size() > 1 and line_distance(at, poly(heat)) < 4.5:
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
	_strip(g, line, float(hw.width) + 5.0, "gravel", 0.045)
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
	# лесополосы по северу и северо-востоку; под ЛЭП наполнения — просека
	var power: PackedVector2Array = poly(((plan.get("filler", {}) as Dictionary).get("lines", {}) as Dictionary).get("power", {}).get("towers", []))
	var attempts: int = 0
	while spots.size() < 1900 and attempts < 45000:
		attempts += 1
		var p: Vector2 = Vector2(rng.randf_range(float(bounds[0]), float(bounds[2])), rng.randf_range(float(bounds[1]), float(bounds[3])))
		var inside: bool = false
		for f: PackedVector2Array in forests:
			inside = inside or Geometry2D.is_point_in_polygon(p, f)
		if inside and _clear_of_roads(p, 3.0) and (power.size() < 2 or line_distance(p, power) > 12.0) and _clear_for_tree(p):
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


## Дереву не место у воды и на откосе русла, на кромке утёса, на трассе, на тропах проверки и у точек
## появления и выходов.
func _clear_for_tree(p: Vector2) -> bool:
	if river_distance(p) < 11.0 or (p.y > 298.0 and p.y < 338.0):
		return false
	for route: Dictionary in plan.probe_routes:
		if line_distance(p, poly(route.points)) < 4.0:
			return false
	for list: String in ["spawns", "exits"]:
		for point: Dictionary in plan.get(list, []):
			if p.distance_to(Vector2(float(point.at[0]), float(point.at[1]))) < 8.0:
				return false
	for loc: Dictionary in plan.locations:
		if p.distance_to(Vector2(float(loc.spawn[0]), float(loc.spawn[1]))) < 8.0:
			return false
	for cliff: Dictionary in (plan.get("relief", {}) as Dictionary).get("cliffs", []):
		if line_distance(p, poly(cliff.points)) < 3.0:
			return false
	return true


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


# ---------------------------------------------------------------- речка и утёсы

## Зеркало воды по руслу, мосты (дорожный у КПП и пешеходный у АЗС), трубы под трассой, камни утёсов.
func _river_features(g: RefCounted) -> void:
	var relief: Dictionary = plan.get("relief", {}) as Dictionary
	var river: Dictionary = relief.get("river", {}) as Dictionary
	if not river.is_empty():
		for i: int in range(_river.size() - 1):
			var a: Vector2 = _river[i]
			var b: Vector2 = _river[i + 1]
			var dir: Vector2 = (b - a).normalized()
			var left: Vector2 = Vector2(-dir.y, dir.x)
			var count: int = maxi(1, ceili(a.distance_to(b) / 3.0))
			var previous: Array = []
			for k: int in range(count + 1):
				var t: float = float(k) / float(count)
				var c: Vector2 = a.lerp(b, t)
				var w: Vector3 = river_water_at(i, t)
				var dry: bool = c.y > _river_dry.x - 1.0 and c.y < _river_dry.y + 1.0
				var edge: Array = [Vector3(c.x + left.x * w.y, w.x, c.y + left.y * w.y), Vector3(c.x - left.x * w.z, w.x, c.y - left.y * w.z), dry]
				if not previous.is_empty() and not bool(previous[2]) and not dry:
					g.quad(previous[0] as Vector3, edge[0] as Vector3, edge[1] as Vector3, previous[1] as Vector3, "water")
				previous = edge
		for bridge: Dictionary in river.bridges:
			_bridge(g, bridge)
		for culvert: Dictionary in river.culverts:
			var at: Array = culvert.at
			var yaw: float = deg_to_rad(float(culvert.yaw))
			var base: float = float((plan.highway as Dictionary).y)
			# оголовок трубы в откосе насыпи: бетонная рамка и тёмное отверстие
			g.box(Vector3(float(at[0]), base - 1.4, float(at[1])), Vector3(6.0, 3.0, 1.0), "concrete", true, yaw)
			g.box(Vector3(float(at[0]), base - 1.9, float(at[1])), Vector3(3.2, 2.0, 1.06), "dark", false, yaw)
	# глыбы по лицу утёсов и валуны у подножия — наборы наполнения (tools/mall_study_filler.py, cliff_rocks)


## Мост поперёк русла: настил вровень с берегами, перила, опоры; дорожный — на ширину дороги.
func _bridge(g: RefCounted, bridge: Dictionary) -> void:
	var at: Vector2 = Vector2(float(bridge.at[0]), float(bridge.at[1]))
	# вдоль русла (yaw — как у наборов: локальная Z смотрит по ходу), мост — поперёк, across — влево от хода
	var along: Vector2 = Vector2(sin(deg_to_rad(float(bridge.yaw))), cos(deg_to_rad(float(bridge.yaw))))
	var across: Vector2 = Vector2(-along.y, along.x)
	var left: float = float(bridge.get("half_left", float(bridge.length) * 0.5))
	var right: float = float(bridge.get("half_right", float(bridge.length) * 0.5))
	var center: Vector2 = at + across * (left - right) * 0.5
	var length_m: float = left + right
	var width: float = float(bridge.width)
	var deck: float = float(bridge.deck)
	var yaw: float = -atan2(across.y, across.x)
	var road: bool = String(bridge.kind) == "road"
	g.box(Vector3(center.x, deck - 0.25, center.y), Vector3(length_m, 0.5, width), "concrete" if road else "timber", true, yaw)
	for side: float in [-1.0, 1.0]:
		var rail: Vector2 = center + along * side * (width * 0.5 - 0.1)
		g.box(Vector3(rail.x, deck + 0.55, rail.y), Vector3(length_m, 0.1, 0.1), "steel", true, yaw)
		for k: int in range(int(length_m / 2.5) + 1):
			var post: Vector2 = rail + across * (float(k) * 2.5 - length_m * 0.5)
			g.box(Vector3(post.x, deck + 0.3, post.y), Vector3(0.08, 0.6, 0.08), "steel", false)
	# опоры у кромок русла
	for side: float in [-1.0, 1.0]:
		var pier: Vector2 = at + across * side * (_river_bed_half + 1.0)
		var foot: float = ground(pier.x, pier.y)
		g.box(Vector3(pier.x, (foot + deck - 0.5) * 0.5, pier.y), Vector3(0.8, maxf(0.2, deck - 0.5 - foot), width * 0.8), "concrete", true, yaw)
