@tool
extends Node3D
## Рельеф, дороги и условная растительность отдельного масштабного исследования.
## Положение мест снято с центрального плана референса, не с его фотографий-врезок.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const PLAN: String = "res://data/blockouts/urban_belt_study.json"

var plan: Dictionary = {}
var generated: Node3D
var swamp: PackedVector2Array
var boundary: PackedVector2Array
var ridges: Array[PackedVector2Array] = []
var tracks: PackedVector2Array
var river_line: PackedVector2Array

func _ready() -> void:
	load_plan()
	rebuild()

func poly(points: Array) -> PackedVector2Array:
	var result: PackedVector2Array = PackedVector2Array()
	for p: Array in points:
		result.append(Vector2(float(p[0]), float(p[1])))
	return result

func load_plan() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PLAN))
	if not parsed is Dictionary:
		push_error("Не прочитан план блокаута: " + PLAN)
		return
	plan = parsed as Dictionary
	swamp = poly(plan.swamp)
	boundary = poly(plan.boundary)
	tracks = poly(plan.tracks)
	river_line = poly(plan.river)
	ridges.clear()
	for points: Array in plan.dry_ridges:
		ridges.append(poly(points))

static func line_distance(p: Vector2, line: PackedVector2Array) -> float:
	var nearest: float = INF
	for i: int in range(line.size() - 1):
		nearest = minf(nearest, p.distance_to(Geometry2D.get_closest_point_to_segment(p, line[i], line[i + 1])))
	return nearest

func ground(x: float, z: float) -> float:
	var p: Vector2 = Vector2(x, z)
	var height: float = 0.0
	if Geometry2D.is_point_in_polygon(p, swamp):
		var edge: PackedVector2Array = swamp.duplicate()
		edge.append(swamp[0])
		var shore: float = line_distance(p, edge)
		height = -1.15 * smoothstep(0.0, 7.0, shore)
		for ridge: PackedVector2Array in ridges:
			var distance: float = line_distance(p, ridge)
			height = maxf(height, lerpf(0.04, -1.15, smoothstep(2.0, 5.5, distance)))
	var rail_distance: float = line_distance(p, tracks)
	if rail_distance < 16.0:
		height = maxf(height, 2.4 * (1.0 - smoothstep(5.0, 16.0, rail_distance)))
	var river_distance: float = line_distance(p, river_line)
	if river_distance < 8.0:
		height = minf(height, -1.1 * (1.0 - smoothstep(3.0,8.0,river_distance)))
	return height

func rebuild() -> void:
	if plan.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Landscape"
	add_child(generated)
	var g: RefCounted = Geometry.new(generated, Geometry.materials())
	_terrain(g)
	_roads(g)
	_water(g)
	_sports(g)
	_railway(g)
	_forest(g)
	_swamp_remains(g)
	_site_details(g)
	_boundary(g)
	g.finish()

func _terrain(g: RefCounted) -> void:
	var faces: PackedVector3Array = PackedVector3Array()
	var step_m: float = 3.0
	var min_x: float = -400.0
	var min_z: float = -360.0
	for ix: int in range(260):
		for iz: int in range(240):
			var x: float = min_x + float(ix) * step_m
			var z: float = min_z + float(iz) * step_m
			var a: Vector3 = Vector3(x, ground(x, z), z)
			var b: Vector3 = Vector3(x + step_m, ground(x + step_m, z), z)
			var c: Vector3 = Vector3(x + step_m, ground(x + step_m, z + step_m), z + step_m)
			var d: Vector3 = Vector3(x, ground(x, z + step_m), z + step_m)
			var key: String = "mud" if Geometry2D.is_point_in_polygon(Vector2(x + 2, z + 2), swamp) else "ground"
			g.quad(a, b, c, d, key)
			faces.append_array(PackedVector3Array([a, b, c, a, c, d]))
	var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new()
	shape.set_faces(faces)
	shape.backface_collision = true
	var cs: CollisionShape3D = CollisionShape3D.new()
	cs.name = "Terrain"
	cs.shape = shape
	g.body.add_child(cs)

func _strip(g: RefCounted, line: PackedVector2Array, width: float, key: String, offset: float) -> void:
	for i: int in range(line.size() - 1):
		var a: Vector2 = line[i]
		var b: Vector2 = line[i + 1]
		var perpendicular: Vector2 = (b - a).normalized().orthogonal() * width * 0.5
		var count: int = maxi(1, int(ceil(a.distance_to(b) / 2.5)))
		for j: int in range(count):
			var p: Vector2 = a.lerp(b, float(j) / float(count))
			var q: Vector2 = a.lerp(b, float(j + 1) / float(count))
			var points: Array[Vector3] = []
			for v: Vector2 in [p + perpendicular, q + perpendicular, q - perpendicular, p - perpendicular]:
				points.append(Vector3(v.x, ground(v.x, v.y) + offset, v.y))
			g.quad(points[0], points[1], points[2], points[3], key)

func _roads(g: RefCounted) -> void:
	for road: Dictionary in plan.roads:
		var line: PackedVector2Array = poly(road.points)
		var width: float = float(road.width)
		if width > 4.0:
			_strip(g, line, width + 2.4, "walk", 0.022)
		_strip(g, line, width, "road" if width > 4.0 else "walk", 0.04)
		if width > 7.0:
			for i: int in range(line.size() - 1):
				var length_m: float = line[i].distance_to(line[i + 1])
				for mark: int in range(int(length_m / 9.0)):
					var a: Vector2 = line[i].lerp(line[i + 1], (float(mark) * 9.0 + 1.0) / length_m)
					var b: Vector2 = line[i].lerp(line[i + 1], minf((float(mark) * 9.0 + 4.0) / length_m, 1.0))
					_strip(g, PackedVector2Array([a, b]), 0.14, "stripe", 0.055)
	for pad: Dictionary in plan.pads:
		var p: Array = pad.at
		var size_m: Array = pad.size
		g.box(Vector3(float(p[0]), -0.12, float(p[1])), Vector3(float(size_m[0]), 0.25, float(size_m[1])), "road", false, deg_to_rad(float(pad.get("yaw", 0.0))))

func _water(g: RefCounted) -> void:
	var indices: PackedInt32Array = Geometry2D.triangulate_polygon(swamp)
	for i: int in range(0, indices.size(), 3):
		var p: Vector2 = swamp[indices[i]]
		var q: Vector2 = swamp[indices[i + 1]]
		var r: Vector2 = swamp[indices[i + 2]]
		g.tri(Vector3(p.x, -0.5, p.y), Vector3(q.x, -0.5, q.y), Vector3(r.x, -0.5, r.y), "water")
	# Граница воды — условная гладкая поверхность; острова выступают через неё.
	var river: PackedVector2Array = poly(plan.river)
	for i: int in range(river.size() - 1):
		var p: Vector2 = river[i]
		var q: Vector2 = river[i + 1]
		var side: Vector2 = (q - p).normalized().orthogonal() * 5.0
		g.quad(Vector3(p.x + side.x, 0.03, p.y + side.y), Vector3(q.x + side.x, 0.03, q.y + side.y), Vector3(q.x - side.x, 0.03, q.y - side.y), Vector3(p.x - side.x, 0.03, p.y - side.y), "water")

func _sports(g: RefCounted) -> void:
	var p: Array = plan.sports_at
	var center: Vector3 = Vector3(float(p[0]), 0.06, float(p[1]))
	g.box(center, Vector3(48.0, 0.12, 32.0), "court", false)
	for z: float in [-14.0, 14.0, 0.0]:
		g.box(center + Vector3(0, 0.07, z), Vector3(44.0, 0.02, 0.11), "stripe", false)
	for x: float in [-22.0, 22.0, 0.0]:
		g.box(center + Vector3(x, 0.07, 0), Vector3(0.11, 0.02, 28.0), "stripe", false)
	# Ограждение с тремя проходами, поэтому площадку можно пересечь насквозь.
	for x: float in [-25.0, 25.0]:
		for z: int in range(-17, 18, 4):
			g.box(center + Vector3(x, 1.5, float(z)), Vector3(0.1, 3.0, 0.1), "steel")
		for z: float in [-10.5, 10.5]:
			g.box(center + Vector3(x, 1.2, z), Vector3(0.12, 0.08, 13.0), "steel", false)
	for z: float in [-17.0, 17.0]:
		for x: float in [-15.0, 15.0]:
			g.box(center + Vector3(x, 0.6, z), Vector3(16.0, 1.2, 0.2), "concrete")
	# Скамьи трибуны задают человеческий масштаб.
	for row: int in range(3):
		g.box(center + Vector3(0, float(row) * 0.3 + 0.2, 22.0 + float(row) * 0.8), Vector3(26.0, 0.4 + float(row) * 0.6, 0.7), "concrete")

func _railway(g: RefCounted) -> void:
	for track_offset: float in [-2.8, 2.8]:
		for i: int in range(tracks.size() - 1):
			var a: Vector2 = tracks[i]
			var b: Vector2 = tracks[i + 1]
			var along: Vector2 = (b - a).normalized()
			var side: Vector2 = along.orthogonal()
			for rail: float in [-0.76, 0.76]:
				var p: Vector2 = a + side * (track_offset + rail)
				var q: Vector2 = b + side * (track_offset + rail)
				g.beam(Vector3(p.x, 2.52, p.y), Vector3(q.x, 2.52, q.y), 0.09, 0.12, "steel")
			for sleeper: int in range(int(a.distance_to(b) / 1.2)):
				var p: Vector2 = a + along * (float(sleeper) * 1.2) + side * track_offset
				g.box(Vector3(p.x, 2.44, p.y), Vector3(2.4, 0.12, 0.22), "bark", false, -atan2(side.y, side.x))
			for pole: int in range(int(a.distance_to(b) / 28.0)):
				var p: Vector2 = a + along * (float(pole) * 28.0) + side * 7.5
				g.box(Vector3(p.x, 6.4, p.y), Vector3(0.3, 8.0, 0.3), "concrete")
	# Открытый перрон имеет длинный пологий подход вместо непроходимого борта.
	var platform: Array = plan.platform
	_strip(g, poly(platform), 5.5, "walk", 0.08)

func _forest(g: RefCounted) -> void:
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 20261016
	var trunks: Array[Transform3D] = []
	var crowns: Array[Transform3D] = []
	var attempts: int = 0
	while trunks.size() < 650 and attempts < 12000:
		attempts += 1
		var p: Vector2 = Vector2(rng.randf_range(-365, 365), rng.randf_range(-335, 335))
		var inside: bool = Geometry2D.is_point_in_polygon(p, boundary)
		var wet: bool = Geometry2D.is_point_in_polygon(p, swamp)
		var rim: bool = not inside or p.y < -255.0 or p.x < -285.0 or p.y > 275.0
		if not rim and not wet:
			continue
		var clear: bool = true
		for road: Dictionary in plan.roads:
			if line_distance(p, poly(road.points)) < float(road.width) * 0.5 + 3.0:
				clear = false
				break
		for ridge: PackedVector2Array in ridges:
			if line_distance(p,ridge) < 1.5:
				clear = false
		if not clear:
			continue
		for site: Dictionary in plan.buildings:
			var at: Array = site.at
			var span: Array = site.size
			if p.distance_to(Vector2(float(at[0]), float(at[1]))) < maxf(float(span[0]), float(span[1])) * 0.55 + 5.0:
				clear = false
				break
		if not clear:
			continue
		var h: float = rng.randf_range(7.0, 15.0)
		var r: float = rng.randf_range(0.14, 0.27)
		var y: float = ground(p.x, p.y)
		trunks.append(Transform3D(Basis.IDENTITY.scaled(Vector3(r, h, r)), Vector3(p.x, y + h * 0.5, p.y)))
		if not wet or rng.randf() < 0.28:
			var w: float = rng.randf_range(3.0, 5.5)
			crowns.append(Transform3D(Basis.IDENTITY.scaled(Vector3(w, h * 0.55, w)), Vector3(p.x, y + h * 0.69, p.y)))
		if inside:
			# Коллизии только у стволов; кроны не образуют сплошных невидимых стен.
			var shape: CylinderShape3D = CylinderShape3D.new()
			shape.radius = r
			shape.height = h
			var cs: CollisionShape3D = CollisionShape3D.new()
			cs.shape = shape
			cs.position = Vector3(p.x, y + h * 0.5, p.y)
			g.body.add_child(cs)
	_multimesh("TreeTrunks", trunks, false, g.palette.bark)
	_multimesh("TreeCrowns", crowns, true, g.palette.foliage)

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

func _swamp_remains(g: RefCounted) -> void:
	for points: Array in plan.dry_ridges:
		var ridge: PackedVector2Array = poly(points)
		for i: int in range(2, ridge.size() - 1, 2):
			var p: Vector2 = ridge[i] + Vector2(2.0, 2.0)
			g.box(Vector3(p.x, 0.8, p.y), Vector3(0.4, 2.0, 0.4), "concrete")
	var origin: Vector2 = poly(plan.swamp_remains)[0]
	for x: int in range(4):
		for z: int in range(3):
			g.box(Vector3(origin.x + float(x) * 4.0, 0.7, origin.y + float(z) * 4.0), Vector3(0.45, 3.0, 0.45), "concrete")
	# Никаких деревянных мостков: здесь пока только грунтовые гряды и старые опоры.

func _boundary(g: RefCounted) -> void:
	var edge: PackedVector2Array = boundary.duplicate()
	edge.append(boundary[0])
	for i: int in range(edge.size() - 1):
		var a: Vector2 = edge[i]
		var b: Vector2 = edge[i + 1]
		for j: int in range(maxi(1, int(a.distance_to(b) / 9.0))):
			var p: Vector2 = a.lerp(b, float(j) / float(maxi(1, int(a.distance_to(b) / 9.0))))
			g.box(Vector3(p.x, ground(p.x, p.y) + 0.45, p.y), Vector3(0.16, 0.9, 0.16), "accent", false)
	# Мягкая граница исследования: за столбиками можно выйти в запасную полосу.
	for x: float in [-388.0, 368.0]:
		g.collision_box(Vector3(x, 8.0, 0), Vector3(2.0, 24.0, 720.0))
	for z: float in [-348.0, 348.0]:
		g.collision_box(Vector3(-10.0, 8.0, z), Vector3(756.0, 24.0, 2.0))

func _pixel(p: Vector2, y: float = 0.0) -> Vector3:
	return Vector3((p.x-775.0)*0.8,y,(p.y-420.0)*0.8)

func _site_details(g: RefCounted) -> void:
	# Крупные укрытия нужны для проверки открытых пространств, а не для декора.
	# Переправа пока задаёт только габарит и коллизию старого бетонного моста.
	g.box(_pixel(Vector2(1093,142),0.0),Vector3(34.0,0.4,8.0),"concrete")
	for z: float in [-3.8,3.8]:
		g.box(_pixel(Vector2(1093,142),0.7)+Vector3(0,0,z),Vector3(34.0,1.0,0.2),"concrete")
	var fence_segments: Array[PackedVector2Array] = [
		PackedVector2Array([Vector2(787,185),Vector2(787,274)]),
		PackedVector2Array([Vector2(787,287),Vector2(788,354)]),
		PackedVector2Array([Vector2(787,185),Vector2(999,213)]),
		PackedVector2Array([Vector2(999,213),Vector2(995,302)]),
		PackedVector2Array([Vector2(993,330),Vector2(987,373)]),
		PackedVector2Array([Vector2(987,373),Vector2(913,367)]),
		PackedVector2Array([Vector2(853,361),Vector2(788,354)])]
	for segment: PackedVector2Array in fence_segments:
		g.beam(_pixel(segment[0],0.9),_pixel(segment[1],0.9),0.18,1.8,"steel",true)
	for p: Vector2 in [Vector2(476,370),Vector2(500,397),Vector2(493,461),Vector2(618,376),Vector2(683,465),Vector2(673,533),Vector2(700,454)]:
		var at: Vector3 = _pixel(p)
		g.box(at+Vector3(0,0.55,0),Vector3(4.6,1.1,1.8),"dark")
		g.box(at+Vector3(0,1.35,0),Vector3(2.7,0.55,1.6),"steel")
	for segment: PackedVector2Array in [PackedVector2Array([Vector2(455,416),Vector2(486,416)]),PackedVector2Array([Vector2(600,470),Vector2(619,470)]),PackedVector2Array([Vector2(670,412),Vector2(695,412)])]:
		g.beam(_pixel(segment[0],0.5),_pixel(segment[1],0.5),0.25,1.0,"concrete",true)
	for p: Vector2 in [Vector2(455,430),Vector2(477,429),Vector2(609,452),Vector2(680,430),Vector2(703,360),Vector2(696,503)]:
		g.box(_pixel(p,0.8),Vector3(7.0,1.6,2.5),"foliage",false)
	for p: Vector2 in [Vector2(830,339),Vector2(965,276),Vector2(875,346)]:
		g.box(_pixel(p,1.1),Vector3(6.0,2.2,2.5),"concrete")
