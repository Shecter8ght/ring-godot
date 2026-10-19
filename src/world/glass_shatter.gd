class_name GlassShatter
extends MeshInstance3D
## Панель обычного стекла рассыпается (GlassPanes): куски — ячейки вокруг точек попадания клиньями
## между лучами трещин и кольцами по дугам (GlassCracks.hits), дальше от дырок — крупные. Падают
## волной от места удара, по ходу пуль, вращаются и ложатся на пол плашмя; часть кусков у рамы
## остаётся торчать «зубьями». Трещины на кусках — те же (текстура панели). Движение — в шейдере
## glass_damaged (один вызов отрисовки на панель), время — параметр t; крупные куски, ударившись
## о пол, бьются блёстками (ImpactFx.debris_at). Раскладка — от номера панели и попаданий: у всех
## peer одна.

## Пока куски летят; потом t замирает — лежат до конца рейда.
var _t: float = 0.0
var _end_t: float = 0.0
var _material: ShaderMaterial


## size — панель (м), hits — GlassCracks.hits (или пусто — удар без точки), side — куда летят
## (+1 — по нормали панели), floor_local — пол в осях панели, material — материал панели (копия).
func build(size: Vector2, hits: Array, side: float, floor_local: float, seed_value: int, material: ShaderMaterial) -> void:
	var cfg: Dictionary = Balance.GLASS
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = seed_value
	var centers: Array[Vector2] = []
	var half: Vector2 = size * 0.5
	var sources: Array = hits.duplicate()
	if sources.is_empty():
		sources.append({"at": Vector2(rng.randf_range(-half.x, half.x) * 0.5, rng.randf_range(-half.y, half.y) * 0.5), "angles": PackedFloat32Array(), "arcs": PackedFloat32Array()})
	for hit: Dictionary in sources:
		_wedges(hit, size, rng, centers)
	var spread_count: int = int(size.x * size.y * float(cfg.shards_per_m2)) + 4
	for i: int in range(spread_count):
		centers.append(Vector2(rng.randf_range(-half.x, half.x), rng.randf_range(-half.y, half.y)))
	# мелкие ячейки вдоль рамы — из них «зубья», что остаются торчать
	var edge_count: int = int((size.x + size.y) * 2.0 * float(cfg.teeth_per_m))
	for i: int in range(edge_count):
		var along: float = rng.randf()
		var inset: float = rng.randf_range(0.03, 0.09)
		var p: Vector2
		match rng.randi_range(0, 3):
			0:
				p = Vector2(lerpf(-half.x, half.x, along), half.y - inset)
			1:
				p = Vector2(lerpf(-half.x, half.x, along), -half.y + inset)
			2:
				p = Vector2(half.x - inset, lerpf(-half.y, half.y, along))
			_:
				p = Vector2(-half.x + inset, lerpf(-half.y, half.y, along))
		centers.append(p)
	while centers.size() > int(cfg.shards_max):
		centers.remove_at(rng.randi_range(centers.size() / 3, centers.size() - 1))
	var cells: Array[PackedVector2Array] = _voronoi(centers, half)
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA_FLOAT)
	st.set_custom_format(1, SurfaceTool.CUSTOM_RGBA_FLOAT)
	var thick: float = float(cfg.shard_thick)
	var speed: Vector2 = cfg.fall_speed
	var spin: Vector2 = cfg.fall_spin
	var landings: Array[Dictionary] = []
	for cell: PackedVector2Array in cells:
		if cell.size() < 3:
			continue
		var area: float = absf(_area(cell))
		var center: Vector2 = _centroid(cell)
		var nearest: Vector2 = _nearest(center, sources)
		var dist: float = center.distance_to(nearest)
		var tooth: bool = _touches_frame(cell, half) and area < float(cfg.teeth_max_m2) and dist > 0.25 and rng.randf() < float(cfg.teeth_share)
		var delay: float = 1000000.0 if tooth else dist * float(cfg.wave_s_per_m) + rng.randf_range(0.0, 0.06)
		var away: Vector2 = (center - nearest).normalized() if dist > 0.001 else Vector2.ZERO
		var velocity: Vector3 = Vector3(away.x, away.y + rng.randf_range(0.0, 0.3), 0.0) * rng.randf_range(0.0, 0.7)
		velocity.z = side * rng.randf_range(speed.x, speed.y)
		var custom0: Color = Color(center.x, center.y, delay, rng.randf())
		var custom1: Color = Color(velocity.x, velocity.y, velocity.z, rng.randf_range(spin.x, spin.y) * (1.0 if rng.randf() < 0.5 else -1.0))
		_slab(st, cell, thick, size, custom0, custom1)
		if not tooth:
			var h: float = maxf(center.y - floor_local, 0.0)
			var tl: float = (velocity.y + sqrt(velocity.y * velocity.y + 19.62 * h)) / 9.81
			_end_t = maxf(_end_t, delay + tl + 0.6)
			landings.append({"area": area, "time": delay + tl, "at": Vector3(center.x + velocity.x * tl, floor_local, velocity.z * tl)})
	mesh = st.commit()
	_material = material
	_material.set_shader_parameter("fall", true)
	_material.set_shader_parameter("floor_y", floor_local)
	_material.set_shader_parameter("t", 0.0)
	material_override = _material
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	custom_aabb = AABB(Vector3(-half.x - 3.0, floor_local - 0.5, -3.0), Vector3(size.x + 6.0, half.y - floor_local + 1.0, 6.0))
	landings.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.area) > float(b.area))
	for i: int in range(mini(int(cfg.land_bursts), landings.size())):
		var land: Dictionary = landings[i]
		get_tree().create_timer(float(land.time)).timeout.connect(_landed.bind(land.at as Vector3, i))


func _process(delta: float) -> void:
	_t += delta
	_material.set_shader_parameter("t", _t)
	if _t > _end_t:
		set_process(false)


## Крупный кусок ударился о пол — разбился блёстками.
func _landed(at_local: Vector3, index: int) -> void:
	if not is_inside_tree():
		return
	var at: Vector3 = global_transform * at_local
	ImpactFx.debris_at("glass", at, Vector3.UP, Vector3.DOWN)
	if index < 2:
		Audio.play("glass_shards", at, -10.0)


## Ячейки клиньями между лучами попадания: на кольцах (дуги и между ними) — посередине сектора.
func _wedges(hit: Dictionary, size: Vector2, rng: RandomNumberGenerator, out: Array[Vector2]) -> void:
	var at: Vector2 = hit.at
	var angles: PackedFloat32Array = hit.angles
	if angles.size() < 3:
		angles = PackedFloat32Array()
		var a: float = rng.randf() * TAU
		for i: int in range(rng.randi_range(6, 10)):
			angles.append(a)
			a += TAU / 8.0 * rng.randf_range(0.6, 1.4)
	var rings: Array[float] = [0.035, 0.08]
	for r: float in hit.arcs:
		rings.append(r)
	rings.append(0.3 * rng.randf_range(0.8, 1.3))
	rings.append(0.55 * rng.randf_range(0.8, 1.3))
	rings.sort()
	var half: Vector2 = size * 0.5
	var sorted: Array[float] = []
	for angle: float in angles:
		sorted.append(fposmod(angle, TAU))
	sorted.sort()
	for ring_index: int in range(rings.size()):
		var keep: float = 1.0 - float(ring_index) * 0.12
		for i: int in range(sorted.size()):
			var a0: float = sorted[i]
			var a1: float = sorted[(i + 1) % sorted.size()]
			if a1 <= a0:
				a1 += TAU
			if rng.randf() > keep:
				continue
			var a: float = lerpf(a0, a1, rng.randf_range(0.35, 0.65))
			var r: float = rings[ring_index] * rng.randf_range(0.85, 1.15)
			var p: Vector2 = at + Vector2(cos(a), sin(a)) * r
			if absf(p.x) < half.x - 0.01 and absf(p.y) < half.y - 0.01:
				out.append(p)


## Ячейки Вороного в прямоугольнике панели: у каждого центра — пересечение полуплоскостей
## к соседям (ближние — по порядку, дальние уже не режут).
func _voronoi(centers: Array[Vector2], half: Vector2) -> Array[PackedVector2Array]:
	var cells: Array[PackedVector2Array] = []
	var frame: PackedVector2Array = PackedVector2Array([Vector2(-half.x, -half.y), Vector2(half.x, -half.y), Vector2(half.x, half.y), Vector2(-half.x, half.y)])
	for i: int in range(centers.size()):
		var c: Vector2 = centers[i]
		var others: Array[Vector2] = []
		for j: int in range(centers.size()):
			if j != i and centers[j].distance_squared_to(c) > 0.000001:
				others.append(centers[j])
		others.sort_custom(func(a: Vector2, b: Vector2) -> bool: return a.distance_squared_to(c) < b.distance_squared_to(c))
		var cell: PackedVector2Array = frame
		for o: Vector2 in others:
			var reach: float = 0.0
			for v: Vector2 in cell:
				reach = maxf(reach, v.distance_to(c))
			if o.distance_to(c) > reach * 2.0:
				break
			var n: Vector2 = (o - c).normalized()
			var m: Vector2 = (o + c) * 0.5
			var perp: Vector2 = Vector2(-n.y, n.x) * 20.0
			var halfplane: PackedVector2Array = PackedVector2Array([m + perp, m - perp, m - perp - n * 20.0, m + perp - n * 20.0])
			var cut: Array[PackedVector2Array] = Geometry2D.intersect_polygons(cell, halfplane)
			if cut.is_empty():
				cell = PackedVector2Array()
				break
			cell = cut[0]
		if cell.size() >= 3:
			cells.append(cell)
	return cells


## Плитка стекла по контуру ячейки: лицо, изнанка, торцы. UV — точка на панели (трещины на месте).
## Касательные — явно: у торца UV лица и изнанки совпадают, и рассчитанная касательная выходит NaN —
## шейдер с картой нормалей рисует торец чёрным, а свечение раздувает его в белый ореол.
func _slab(st: SurfaceTool, cell: PackedVector2Array, thick: float, size: Vector2, c0: Color, c1: Color) -> void:
	var poly: PackedVector2Array = cell
	if _area(poly) < 0.0:
		poly.reverse()
	var z: float = thick * 0.5
	var along: Plane = Plane(Vector3.RIGHT, 1.0)
	for i: int in range(1, poly.size() - 1):
		_tri(st, Vector3(poly[0].x, poly[0].y, z), Vector3(poly[i].x, poly[i].y, z), Vector3(poly[i + 1].x, poly[i + 1].y, z), Vector3.BACK, along, size, c0, c1)
		_tri(st, Vector3(poly[0].x, poly[0].y, -z), Vector3(poly[i + 1].x, poly[i + 1].y, -z), Vector3(poly[i].x, poly[i].y, -z), Vector3.FORWARD, Plane(Vector3.RIGHT, -1.0), size, c0, c1)
	var across: Plane = Plane(Vector3.BACK, 1.0)
	for i: int in range(poly.size()):
		var a: Vector2 = poly[i]
		var b: Vector2 = poly[(i + 1) % poly.size()]
		var edge: Vector2 = b - a
		# вырожденное ребро (повтор вершины после обрезки) — без торца: нормаль была бы нулевой
		if edge.length_squared() < 1e-10:
			continue
		var n: Vector3 = Vector3(edge.y, -edge.x, 0.0).normalized()
		_tri(st, Vector3(a.x, a.y, z), Vector3(b.x, b.y, z), Vector3(b.x, b.y, -z), n, across, size, c0, c1)
		_tri(st, Vector3(a.x, a.y, z), Vector3(b.x, b.y, -z), Vector3(a.x, a.y, -z), n, across, size, c0, c1)


## Треугольник лицевой стороной наружу (обход по часовой стрелке снаружи — лицо у Godot).
func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, n: Vector3, tangent: Plane, size: Vector2, c0: Color, c1: Color) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var swap: Vector3 = b
		b = c
		c = swap
	for v: Vector3 in [a, b, c]:
		st.set_normal(n)
		st.set_tangent(tangent)
		st.set_uv(Vector2(v.x / size.x + 0.5, 0.5 - v.y / size.y))
		st.set_custom(0, c0)
		st.set_custom(1, c1)
		st.add_vertex(v)


static func _area(poly: PackedVector2Array) -> float:
	var s: float = 0.0
	for i: int in range(poly.size()):
		var a: Vector2 = poly[i]
		var b: Vector2 = poly[(i + 1) % poly.size()]
		s += a.x * b.y - b.x * a.y
	return s * 0.5


static func _centroid(poly: PackedVector2Array) -> Vector2:
	var sum: Vector2 = Vector2.ZERO
	for v: Vector2 in poly:
		sum += v
	return sum / float(poly.size())


static func _nearest(p: Vector2, sources: Array) -> Vector2:
	var best: Vector2 = (sources[0] as Dictionary).at
	for hit: Dictionary in sources:
		if (hit.at as Vector2).distance_squared_to(p) < best.distance_squared_to(p):
			best = hit.at
	return best


static func _touches_frame(poly: PackedVector2Array, half: Vector2) -> bool:
	for v: Vector2 in poly:
		if absf(absf(v.x) - half.x) < 0.003 or absf(absf(v.y) - half.y) < 0.003:
			return true
	return false
