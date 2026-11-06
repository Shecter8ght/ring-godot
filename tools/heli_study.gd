extends Node3D
## Серый стенд карты «Плотина» — на ней задание «Вертолёт» (docs/design/mission_helicopter.md): HELI_PLAN=v05 (по умолчанию) — «плотина над долиной»
## (tools/mission_helicopter_v05.py: озеро и вся игра ниже арочной плотины 260 м, водохранилище выше, водослив на севере),
## HELI_PLAN=v04 — прежняя «карта вокруг плотины» (tools/mission_helicopter_v04*.py). Рельеф 2 × 3 км (ходят по ядру, дальше
## горы видом), вода, плотина, места и остановки коробками, лес зоны 1 (ели, сосны, берёзы с дальними карточками), вертолёт
## по маршруту. Это проба геометрии и производительности, не рейд. Снимки и замеры — docs/screens/heli_<версия>/.
##   tools/heli_study.cmd                                                              — прогулка
##   tools/godot.cmd --headless res://tools/heli_study.tscn -- check                   — сборка, счёт, земля под местами
##   tools/godot.cmd --windowed --resolution 1920x1080 --disable-vsync res://tools/heli_study.tscn -- perf
##                                                 — кадры в секунду с точек plan.views → docs/screens/heli_v04/<метка>_*
##   … то же с окном -- shots — одиночные кадры plan.shots (на плотину, с плотины, места, вертолёт, с воздуха)
##                                                 → docs/screens/heli_v04/shots/; HELI_SHOTS_ONLY=имя,имя — выборочно
##   tools/dam_play.cmd — та же карта с настоящим игроком, оружием и ботами (мир — этот стенд без ходока)
##   … то же с окном -- ortho — ортографические кадры мест и остановок по рамкам plan.ortho: план сверху и вид под углом,
##                                                 без дымки → docs/screens/heli_<версия>/ortho/; HELI_ORTHO_ONLY=имя — выборочно
## HELI_FOREST=0…1 — доля деревьев (0 — без леса), HELI_TREE_NEAR — до скольких метров полные модели деревьев (300),
## HELI_QUALITY=low|medium|high, HELI_TIME=day|dusk|night, HELI_WEATHER=clear|overcast|rain|fog, HELI_TAG — метка замера.
## Прогулка: WASD, Shift — бег, Space — прыжок, C — присесть, F — полёт, M — план, 1–9/0 — места, N/B — следующее /
## прошлое, H — к вертолёту, R — к текущему месту, Esc — мышь.

const Walker = preload("res://src/blockout/study_walker.gd")
const Terrain = preload("res://src/blockout/heli_terrain.gd")
const WATER_SHADER: Shader = preload("res://src/world/district_water.gdshader")
const NOISE: String = "res://assets/terrain/zone01_noise.png"
## Порода → модель зоны 1 (и её «_far») и радиус ствола для коллизии.
const SPECIES: Dictionary = {
	"spruce_a": ["spruce_forest_a", 0.3], "spruce_b": ["spruce_forest_b", 0.3], "spruce_young": ["spruce_young_a", 0.2],
	"pine": ["pine_forest", 0.3], "pine_slim": ["pine_slim_a", 0.25], "birch": ["birch_a", 0.21],
}
const COLORS: Dictionary = {
	"building": Color(0.74, 0.72, 0.67), "house": Color(0.68, 0.63, 0.56), "wood": Color(0.42, 0.33, 0.24),
	"logs": Color(0.52, 0.41, 0.28), "concrete": Color(0.63, 0.62, 0.6), "metal": Color(0.33, 0.35, 0.36),
	"metal_shed": Color(0.52, 0.54, 0.52), "military": Color(0.37, 0.41, 0.32), "bus": Color(0.78, 0.64, 0.2),
	"tent": Color(0.33, 0.43, 0.33), "buoy": Color(0.86, 0.42, 0.14),
}
const WARM: int = 150
const MEASURE: int = 300

var plan: Dictionary
var y0: float = 0.0
var plan_path: String = ""
var veg_path: String = ""
var thin_path: String = ""
var out_dir: String = ""
var terrain: Node3D
var walker: CharacterBody3D
var heli: Node3D
var heli_rotor: Node3D
var heli_path: PackedVector3Array = PackedVector3Array()
var heli_len: PackedFloat32Array = PackedFloat32Array()
var heli_s: float = 0.0
var heli_dir: float = 1.0
var heli_wait: float = 0.0
var mode: String = "walk"
var current: int = 0
var stats: Dictionary = {}
var mats: Dictionary = {}
var hud: CanvasLayer
var title: Label
var status: Label
var map_layer: Control
var map_texture: TextureRect
var map_marker: ColorRect
var status_timer: float = 0.0


func _enter_tree() -> void:
	# внутри «игрока и ботов» (tools/dam_play.gd) профиль ставит он
	if not has_meta("embedded"):
		Profile.use_file("user://profile_heli_study_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["check", "perf", "shots", "ortho"]:
			mode = arg
	# мир для tools/dam_play.gd: только карта, свет и вертолёт — без ходока, интерфейса и клавиш прогулки
	if has_meta("embedded"):
		mode = "embed"
	var version: String = _env("HELI_PLAN", "v05")
	plan_path = "res://data/blockouts/heli_%s.json" % version
	veg_path = "res://data/blockouts/heli_%s_vegetation.json" % version
	thin_path = "user://heli_%s_vegetation_thin.json" % version
	out_dir = "res://docs/screens/heli_%s" % version
	DisplayServer.window_set_title("RING · «Плотина» %s · серый стенд (задание «Вертолёт»)" % version)
	plan = JSON.parse_string(FileAccess.get_file_as_string(plan_path)) as Dictionary
	y0 = float(plan.y_offset)
	var quality: String = OS.get_environment("HELI_QUALITY")
	if quality in Settings.QUALITY:
		Settings.quality = quality
		Settings.apply_graphics()
		Settings.changed.emit()
	var started: int = Time.get_ticks_msec()
	_environment()
	_build_terrain()
	_water()
	_dam()
	_structures()
	_forest()
	_walls()
	_helicopter()
	stats.build_ms = Time.get_ticks_msec() - started
	if mode == "embed":
		return
	walker = Walker.new()
	walker.name = "StudyWalker"
	add_child(walker)
	(walker.get("camera") as Camera3D).far = 4000.0
	if mode == "check":
		await _check()
		return
	_ui()
	await _frames(3)
	_jump(0)
	if mode == "perf":
		walker.set("is_probe", true)
		await _perf()
		return
	if mode == "shots":
		walker.set("is_probe", true)
		await _shots()
		return
	if mode == "ortho":
		walker.set("is_probe", true)
		await _ortho()
		return
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	print("heli_study: прогулка; сборка %d мс, деревьев %d" % [int(stats.build_ms), int(stats.get("trees", 0))])


func _env(key: String, fallback: String) -> String:
	var value: String = OS.get_environment(key)
	return value if value != "" else fallback


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().process_frame


# ---------------------------------------------------------------- мир


## Свет и небо — общий свет рейдовых карт (RaidAtmosphere: схема Road to Vostok, DayCycle), как на настоящей карте.
func _environment() -> void:
	RaidConditions.current = RaidConditions.normalized({"time": _env("HELI_TIME", "day"),
		"weather": _env("HELI_WEATHER", "clear"), "power": "on"})
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-40.0, -35.0, 0.0)
	sun.shadow_enabled = true
	add_child(sun)
	var atmosphere: RaidAtmosphere = RaidAtmosphere.new()
	atmosphere.name = "Atmosphere"
	add_child(atmosphere)
	atmosphere.apply()


func _build_terrain() -> void:
	var w: Array = plan.walkable
	var t: Node3D = Terrain.new()
	t.name = "Terrain"
	t.position = Vector3(0.0, y0, 0.0)
	t.set("detail_rect", Rect2(float(w[0]) - 200.0, float(w[2]) - 200.0, float(w[1]) - float(w[0]) + 400.0, float(w[3]) - float(w[2]) + 400.0))
	t.set("collision_rect", Rect2(float(w[0]) - 40.0, float(w[2]) - 40.0, float(w[1]) - float(w[0]) + 80.0, float(w[3]) - float(w[2]) + 80.0))
	t.set("data_path", plan_path)
	add_child(t)
	terrain = t
	stats.tiles = t.get("built")


func ground(x: float, z: float) -> float:
	return y0 + float(terrain.call("height_at", x, z))


func _arc_z(x: float) -> float:
	var d: Dictionary = plan.dam
	var r: float = float(d.radius)
	return float(d.apex) + r - sqrt(maxf(r * r - x * x, 0.0))


func _water_material() -> ShaderMaterial:
	var m: ShaderMaterial = ShaderMaterial.new()
	m.shader = WATER_SHADER
	if ResourceLoader.exists(NOISE):
		m.set_shader_parameter("noise_tex", load(NOISE))
	# водохранилище в горах: глубже и холоднее болота зоны 1
	m.set_shader_parameter("deep_color", Color(0.05, 0.09, 0.09))
	m.set_shader_parameter("murk_color", Color(0.12, 0.18, 0.16))
	m.set_shader_parameter("depth_max", 3.0)
	return m


## Вода: плоские многоугольники (озеро, водохранилище) на своём уровне и реки лентами по руслам. v05 описывает их
## в данных; у v04 — озеро по берегам и верховой грани плотины.
func _water() -> void:
	var material: ShaderMaterial = _water_material()
	var root: Node3D = Node3D.new()
	root.name = "Water"
	add_child(root)
	if plan.has("water"):
		for body: Dictionary in plan.water:
			var outline: PackedVector2Array = PackedVector2Array()
			for q: Array in body.poly:
				outline.append(Vector2(float(q[0]), float(q[1])))
			root.add_child(_flat_water(String(body.name), outline, y0 + float(body.level), material))
		for river: Dictionary in plan.rivers:
			var table: Array = []
			for q: Array in river.points:
				table.append([q[1], q[0]])
			root.add_child(_river(String(river.name), table, float(river.width), material))
		return
	var lake: Dictionary = plan.lake
	var poly: PackedVector2Array = PackedVector2Array()
	for p: Array in lake.west:
		poly.append(Vector2(float(p[1]), float(p[0])))
	for i: int in range(1, 24):
		var x: float = lerpf(-222.0, 222.0, float(i) / 24.0)
		poly.append(Vector2(x, _arc_z(x)))
	var east: Array = lake.east
	for k: int in range(east.size() - 1, -1, -1):
		poly.append(Vector2(float(east[k][1]), float(east[k][0])))
	root.add_child(_flat_water("Lake", poly, y0, material))
	root.add_child(_river("RiverNorth", plan.river_north, 24.0, material))
	root.add_child(_river("RiverGorge", plan.river_gorge, 34.0, material))


## Плоская вода по контуру: край выпущен на 7 м под берег и в тело плотины — щелей у кромки не видно.
func _flat_water(node_name: String, outline: PackedVector2Array, level: float, material: Material) -> MeshInstance3D:
	var poly: PackedVector2Array = outline
	var grown: Array = Geometry2D.offset_polygon(poly, 7.0)
	if not grown.is_empty():
		poly = grown[0]
	var tris: PackedInt32Array = Geometry2D.triangulate_polygon(poly)
	var verts: PackedVector3Array = PackedVector3Array()
	var normals: PackedVector3Array = PackedVector3Array()
	for idx: int in tris:
		verts.append(Vector3(poly[idx].x, level, poly[idx].y))
		normals.append(Vector3.UP)
	return _mesh_instance(node_name, verts, normals, material)


func _river(node_name: String, table: Array, width: float, material: Material) -> MeshInstance3D:
	var line: PackedVector2Array = PackedVector2Array()
	for k: int in range(table.size() - 1):
		var a: Vector2 = Vector2(float(table[k][1]), float(table[k][0]))
		var b: Vector2 = Vector2(float(table[k + 1][1]), float(table[k + 1][0]))
		var n: int = maxi(1, int(a.distance_to(b) / 10.0))
		for i: int in range(n):
			line.append(a.lerp(b, float(i) / float(n)))
	line.append(Vector2(float(table[-1][1]), float(table[-1][0])))
	var verts: PackedVector3Array = PackedVector3Array()
	var normals: PackedVector3Array = PackedVector3Array()
	for k: int in range(line.size() - 1):
		var a: Vector2 = line[k]
		var b: Vector2 = line[k + 1]
		var side: Vector2 = (b - a).normalized().orthogonal() * width * 0.5
		var ya: float = ground(a.x, a.y) + 0.35
		var yb: float = ground(b.x, b.y) + 0.35
		var q: Array[Vector3] = [Vector3(a.x - side.x, ya, a.y - side.y), Vector3(a.x + side.x, ya, a.y + side.y),
			Vector3(b.x + side.x, yb, b.y + side.y), Vector3(b.x - side.x, yb, b.y - side.y)]
		for idx: int in [0, 1, 2, 0, 2, 3]:
			verts.append(q[idx])
			normals.append(Vector3.UP)
	return _mesh_instance(node_name, verts, normals, material)


func _mesh_instance(node_name: String, verts: PackedVector3Array, normals: PackedVector3Array, material: Material) -> MeshInstance3D:
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh: ArrayMesh = ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = node_name
	mi.mesh = mesh
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


## Центр кривизны арки по z и сторона: +1 — верховая грань южнее центра (v05), −1 — севернее (v04).
func _dam_frame() -> Vector2:
	var d: Dictionary = plan.dam
	if d.has("center"):
		return Vector2(float((d.center as Array)[1]), float(d.dir))
	return Vector2(float(d.apex) + float(d.radius), -1.0)


func _arc_point(a: float, r: float, y: float) -> Vector3:
	var f: Vector2 = _dam_frame()
	return Vector3(r * sin(a), y0 + y, f.x + f.y * r * cos(a))


## Арочная плотина: верховая грань по дуге наброска, низовая — с уклоном (10 м по гребню → 60 м у подошвы),
## гребень-дорога с парапетами. Концы уходят в скалу примыканий; ниже земли тело скрыто рельефом.
func _dam() -> void:
	var d: Dictionary = plan.dam
	var r: float = float(d.radius)
	var half: float = deg_to_rad(float(d.half_angle_deg))
	var top: float = float(d.crest)
	var foot: float = float(d.foot)
	var t_top: float = float(d.thick_top)
	var t_base: float = float(d.thick_base)
	var parapet: float = float(d.parapet)
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var n: int = 72
	var lean: float = (t_base - t_top) / (top - foot)
	var side: float = _dam_frame().y
	for i: int in range(n):
		var a0: float = lerpf(-half, half, float(i) / float(n))
		var a1: float = lerpf(-half, half, float(i + 1) / float(n))
		var out0: Vector3 = Vector3(sin(a0), 0.0, side * cos(a0))
		var out1: Vector3 = Vector3(sin(a1), 0.0, side * cos(a1))
		# верховая грань (к озеру)
		_quad(st, _arc_point(a0, r, foot), _arc_point(a1, r, foot), _arc_point(a1, r, top), _arc_point(a0, r, top), out0, out1)
		# низовая грань (к ущелью), чуть смотрит вверх
		var in0: Vector3 = (-out0 + Vector3.UP * lean).normalized()
		var in1: Vector3 = (-out1 + Vector3.UP * lean).normalized()
		_quad(st, _arc_point(a1, r - t_base, foot), _arc_point(a0, r - t_base, foot), _arc_point(a0, r - t_top, top),
			_arc_point(a1, r - t_top, top), in1, in0)
		# гребень
		_quad(st, _arc_point(a0, r, top), _arc_point(a1, r, top), _arc_point(a1, r - t_top, top), _arc_point(a0, r - t_top, top),
			Vector3.UP, Vector3.UP)
		# парапеты по обеим кромкам гребня
		for rr: float in [r - 0.25, r - t_top + 0.25]:
			_quad(st, _arc_point(a0, rr, top), _arc_point(a1, rr, top), _arc_point(a1, rr, top + parapet),
				_arc_point(a0, rr, top + parapet), out0, out1)
	var mesh: ArrayMesh = st.commit()
	var material: StandardMaterial3D = _mat("concrete")
	mesh.surface_set_material(0, material)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "Dam"
	mi.mesh = mesh
	add_child(mi)
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "DamBody"
	body.set_meta("surface", "concrete")
	var col: CollisionShape3D = CollisionShape3D.new()
	var shape: ConcavePolygonShape3D = mesh.create_trimesh_shape()
	# развёрнутая арка (v05) зеркалит обход треугольников: коллизия с обеих сторон, иначе гребень «пустой» сверху
	shape.backface_collision = true
	col.shape = shape
	body.add_child(col)
	add_child(body)


func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, e: Vector3, na: Vector3, nb: Vector3) -> void:
	# развёрнутая арка (v05) зеркалит обход: лицевая сторона должна смотреть по нормали, иначе гребень и грани тёмные
	var order: Array = [[a, na], [b, nb], [c, nb], [a, na], [c, nb], [e, na]]
	if _dam_frame().y > 0.0:
		order = [[a, na], [c, nb], [b, nb], [a, na], [e, na], [c, nb]]
	for pair: Array in order:
		st.set_normal(pair[1])
		st.add_vertex(pair[0])


func _mat(kind: String) -> StandardMaterial3D:
	if mats.has(kind):
		return mats[kind]
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = COLORS.get(kind, Color(0.6, 0.6, 0.6))
	m.roughness = 0.55 if kind in ["metal", "bus", "buoy"] else 0.9
	m.metallic = 0.5 if kind == "metal" else 0.0
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	mats[kind] = m
	return m


## Постройки и остановки — коробки и цилиндры из данных (base: пусто — на земле, число — от уровня озера,
## «top+N» — над землёй на N м); настилы и лестницы — наклонные коробки между точками, тросы — тонкие цилиндры.
func _structures() -> void:
	var root: Node3D = Node3D.new()
	root.name = "Structures"
	add_child(root)
	var count: int = 0
	for s: Dictionary in plan.structures:
		var kind: String = String(s.kind)
		match kind:
			"box", "cyl":
				_solid(root, s)
			"beam":
				var a: Array = s.a
				var b: Array = s.b
				root.add_child(_beam(Vector3(float(a[0]), y0 + float(a[2]), float(a[1])), Vector3(float(b[0]), y0 + float(b[2]), float(b[1])),
					float(s.r), String(s.mat)))
			"wall":
				var a: Array = s.a
				var b: Array = s.b
				var pa: Vector3 = Vector3(float(a[0]), 0.0, float(a[1]))
				var pb: Vector3 = Vector3(float(b[0]), 0.0, float(b[1]))
				var low: float = minf(minf(ground(pa.x, pa.z), ground(pb.x, pb.z)), ground((pa.x + pb.x) * 0.5, (pa.z + pb.z) * 0.5))
				pa.y = low - 0.3
				pb.y = low - 0.3
				_slab(root, pa + Vector3.UP * (float(s.h) * 0.5 + 0.3), pb + Vector3.UP * (float(s.h) * 0.5 + 0.3), float(s.t),
					float(s.h) + 0.6, String(s.mat), true)
			"deck":
				var a: Array = s.a
				var b: Array = s.b
				var ya: float = y0 + (float(a[2]) if a.size() > 2 else float(s.get("y", 0.0)))
				var yb: float = y0 + (float(b[2]) if b.size() > 2 else float(s.get("y", 0.0)))
				_slab(root, Vector3(float(a[0]), ya, float(a[1])), Vector3(float(b[0]), yb, float(b[1])), float(s.w), float(s.t),
					String(s.mat), false)
			"tower_cable":
				var pts: Array = [s.a] + (s.get("via", []) as Array) + [s.b]
				for k: int in range(pts.size() - 1):
					var p: Array = pts[k]
					var q: Array = pts[k + 1]
					var pa: Vector3 = Vector3(float(p[0]), ground(float(p[0]), float(p[1])) + float(s.top), float(p[1]))
					var pb: Vector3 = Vector3(float(q[0]), ground(float(q[0]), float(q[1])) + float(s.top), float(q[1]))
					root.add_child(_beam(pa, pb, float(s.r), String(s.mat)))
		count += 1
	stats.structures = count


func _solid(root: Node3D, s: Dictionary) -> void:
	var x: float = float(s.x)
	var z: float = float(s.z)
	var cylinder: bool = String(s.kind) == "cyl"
	var half_x: float = float(s.r) if cylinder else float(s.w) * 0.5
	var half_z: float = float(s.r) if cylinder else float(s.l) * 0.5
	var h: float = float(s.h)
	var yaw: float = deg_to_rad(float(s.get("yaw", 0.0)))
	var base: Variant = s.get("base")
	var base_y: float
	if base == null:
		# по углам: коробка садится на самую низкую точку и дорастает до самой высокой — не висит над склоном
		var low: float = ground(x, z)
		var high: float = low
		for corner: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			var off: Vector2 = Vector2(corner.x * half_x, corner.y * half_z).rotated(-yaw)
			var g: float = ground(x + off.x, z + off.y)
			low = minf(low, g)
			high = maxf(high, g)
		# на крутом склоне коробка не тянется столбом до самого низа: садится у центра, в гору уходит в склон
		var centre: float = ground(x, z)
		base_y = maxf(low, centre - 3.0) - 0.3
		h += minf(high - base_y, 6.0) + 0.3
	elif base is String:
		base_y = ground(x, z) + float(String(base).trim_prefix("top+"))
	else:
		base_y = y0 + float(base)
	var mi: MeshInstance3D = MeshInstance3D.new()
	var shape: Shape3D
	if cylinder:
		var cm: CylinderMesh = CylinderMesh.new()
		cm.top_radius = float(s.r)
		cm.bottom_radius = float(s.r)
		cm.height = h
		cm.radial_segments = 20
		mi.mesh = cm
		var cs: CylinderShape3D = CylinderShape3D.new()
		cs.radius = float(s.r)
		cs.height = h
		shape = cs
	else:
		var bm: BoxMesh = BoxMesh.new()
		bm.size = Vector3(float(s.w), h, float(s.l))
		mi.mesh = bm
		var bs: BoxShape3D = BoxShape3D.new()
		bs.size = bm.size
		shape = bs
	mi.material_override = _mat(String(s.mat))
	var body: StaticBody3D = StaticBody3D.new()
	body.position = Vector3(x, base_y + h * 0.5, z)
	body.rotation.y = yaw
	body.set_meta("surface", "concrete" if String(s.mat) in ["concrete", "building", "military"] else ("metal" if String(s.mat) in ["metal", "metal_shed", "bus"] else "wood"))
	var col: CollisionShape3D = CollisionShape3D.new()
	col.shape = shape
	body.add_child(col)
	body.add_child(mi)
	root.add_child(body)


## Наклонная или ровная плита между двумя точками (настил, марш лестницы, стенка ограды).
func _slab(root: Node3D, a: Vector3, b: Vector3, width: float, thick: float, mat: String, vertical: bool) -> void:
	var along: Vector3 = b - a
	var length: float = along.length()
	if length < 0.01:
		return
	var dir: Vector3 = along / length
	var side: Vector3 = Vector3.UP.cross(dir).normalized()
	if side.length() < 0.5:
		side = Vector3.RIGHT
	var up: Vector3 = dir.cross(side).normalized()
	var body: StaticBody3D = StaticBody3D.new()
	body.transform = Transform3D(Basis(side, up, dir), (a + b) * 0.5)
	body.set_meta("surface", "metal" if mat == "metal" else ("concrete" if mat == "concrete" else "wood"))
	var size: Vector3 = Vector3(thick if vertical else width, width if vertical else thick, length)
	var bm: BoxMesh = BoxMesh.new()
	bm.size = size
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = bm
	mi.material_override = _mat(mat)
	var bs: BoxShape3D = BoxShape3D.new()
	bs.size = size
	var col: CollisionShape3D = CollisionShape3D.new()
	col.shape = bs
	body.add_child(col)
	body.add_child(mi)
	root.add_child(body)


func _beam(a: Vector3, b: Vector3, radius: float, mat: String) -> MeshInstance3D:
	var along: Vector3 = b - a
	var cm: CylinderMesh = CylinderMesh.new()
	cm.top_radius = radius
	cm.bottom_radius = radius
	cm.height = along.length()
	cm.radial_segments = 8
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.mesh = cm
	mi.material_override = _mat(mat)
	mi.transform = Transform3D(Basis(Quaternion(Vector3.UP, along.normalized())), (a + b) * 0.5)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF if radius < 0.5 else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return mi


## Лес зоны 1: россыпи DistrictScatter по породам; ядро — с коллизией стволов, фон — без. Полные модели до
## HELI_TREE_NEAR м, дальше карточки до 2,4 км крупными клетками. HELI_FOREST < 1 — прореживание (свой файл в user://).
func _forest() -> void:
	var share: float = clampf(float(_env("HELI_FOREST", "1")), 0.0, 1.0)
	stats.trees = 0
	stats.forest_share = share
	if share <= 0.0:
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(veg_path)) as Dictionary
	var path: String = veg_path
	if share < 1.0:
		var thin: Dictionary = {}
		for key: String in data:
			var kept: Array = []
			var list: Array = data[key]
			for i: int in range(list.size()):
				# равномерно по всему списку: доля «золотого сечения» не собирает пропуски в полосы
				if fposmod(float(i) * 0.6180339, 1.0) < share:
					kept.append(list[i])
			thin[key] = kept
		var f: FileAccess = FileAccess.open(thin_path, FileAccess.WRITE)
		f.store_string(JSON.stringify(thin))
		f.close()
		data = thin
		path = thin_path
	var root: Node3D = Node3D.new()
	root.name = "Forest"
	add_child(root)
	var near: float = float(_env("HELI_TREE_NEAR", "300"))
	for key: String in data:
		var list: Array = data[key]
		if list.is_empty():
			continue
		stats.trees = int(stats.trees) + list.size()
		var background: bool = key.ends_with("_bg")
		var spec: Array = SPECIES[key.trim_suffix("_bg")]
		var scatter: DistrictScatter = DistrictScatter.new()
		scatter.name = key
		scatter.data_path = path
		scatter.key = key
		scatter.model = "res://assets/zone01/models/%s.glb" % String(spec[0])
		scatter.far_model = "res://assets/zone01/models/%s_far.glb" % String(spec[0])
		scatter.near_distance = near
		scatter.view_distance = 2400.0
		scatter.cell = 64.0
		scatter.far_cell = 256.0
		scatter.trunk_radius = 0.0 if background else float(spec[1])
		root.add_child(scatter)


## Невидимые стенки: край ядра (дальше — вид), вдоль берегов в воде (по озеру не ходят), над верховым краем гребня.
func _walls() -> void:
	var root: Node3D = Node3D.new()
	root.name = "Walls"
	add_child(root)
	var w: Array = plan.walkable
	var x0: float = float(w[0])
	var x1: float = float(w[1])
	var z0: float = float(w[2])
	var z1: float = float(w[3])
	for pair: Array in [[Vector2(x0, z0), Vector2(x1, z0)], [Vector2(x1, z0), Vector2(x1, z1)], [Vector2(x1, z1), Vector2(x0, z1)],
			[Vector2(x0, z1), Vector2(x0, z0)]]:
		_invisible(root, pair[0], pair[1], y0 - 320.0, y0 + 900.0)
	if plan.has("barriers"):
		for bar: Dictionary in plan.barriers:
			var pts: Array = bar.points
			for k: int in range(pts.size() - 1):
				_invisible(root, Vector2(float(pts[k][0]), float(pts[k][1])), Vector2(float(pts[k + 1][0]), float(pts[k + 1][1])),
					y0 + float(bar.bottom), y0 + float(bar.top))
	else:
		var lake: Dictionary = plan.lake
		var boom: float = float(lake.boom_z)
		for side: Array in [[lake.west, 1.5], [lake.east, -1.5]]:
			var table: Array = side[0]
			for k: int in range(table.size() - 1):
				var za: float = float(table[k][0])
				var zb: float = float(table[k + 1][0])
				if zb < boom:
					continue
				var a: Vector2 = Vector2(float(table[k][1]) + float(side[1]), maxf(za, boom))
				var b: Vector2 = Vector2(float(table[k + 1][1]) + float(side[1]), zb)
				# верх стенки чуть над водой: пирс, понтоны и мостик к башне проходят поверху, с берега в озеро — нет
				_invisible(root, a, b, y0 - 4.0, y0 + 0.25)
	var d: Dictionary = plan.dam
	var half: float = deg_to_rad(float(d.half_angle_deg))
	for i: int in range(24):
		var a0: Vector3 = _arc_point(lerpf(-half, half, float(i) / 24.0), float(d.radius) + 0.3, 0.0)
		var a1: Vector3 = _arc_point(lerpf(-half, half, float(i + 1) / 24.0), float(d.radius) + 0.3, 0.0)
		_invisible(root, Vector2(a0.x, a0.z), Vector2(a1.x, a1.z), y0 + float(d.crest), y0 + float(d.crest) + 3.0)


func _invisible(root: Node3D, a: Vector2, b: Vector2, bottom: float, top: float) -> void:
	var length: float = a.distance_to(b)
	if length < 0.01:
		return
	var body: StaticBody3D = StaticBody3D.new()
	var mid: Vector2 = (a + b) * 0.5
	body.position = Vector3(mid.x, (bottom + top) * 0.5, mid.y)
	body.rotation.y = atan2(b.x - a.x, b.y - a.y)
	var bs: BoxShape3D = BoxShape3D.new()
	bs.size = Vector3(0.6, top - bottom, length + 0.6)
	var col: CollisionShape3D = CollisionShape3D.new()
	col.shape = bs
	body.add_child(col)
	root.add_child(body)


## Вертолёт — коробки по маршруту наброска (42 м/с): с севера над озером, над плотиной в ущелье; у края — пауза
## и обратно (в игре между пролётами минуты, здесь короче — чтобы видеть его чаще).
func _helicopter() -> void:
	heli = Node3D.new()
	heli.name = "Helicopter"
	add_child(heli)
	var dark: StandardMaterial3D = _mat("metal")
	var parts: Array = [[Vector3(3.0, 3.4, 11.0), Vector3(0, 0, 0)], [Vector3(0.9, 1.0, 9.0), Vector3(0, 0.6, 9.5)],
		[Vector3(0.3, 2.4, 1.6), Vector3(0, 1.6, 13.8)]]
	for p: Array in parts:
		var bm: BoxMesh = BoxMesh.new()
		bm.size = p[0]
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.mesh = bm
		mi.position = p[1]
		mi.material_override = dark
		heli.add_child(mi)
	heli_rotor = Node3D.new()
	heli_rotor.position = Vector3(0, 2.1, -0.5)
	heli.add_child(heli_rotor)
	for k: int in range(5):
		var blade: MeshInstance3D = MeshInstance3D.new()
		var bm: BoxMesh = BoxMesh.new()
		bm.size = Vector3(0.5, 0.08, 10.5)
		blade.mesh = bm
		blade.material_override = dark
		blade.rotation.y = TAU * float(k) / 5.0
		blade.position = Vector3(sin(TAU * float(k) / 5.0), 0, cos(TAU * float(k) / 5.0)) * 5.25
		heli_rotor.add_child(blade)
	var total: float = 0.0
	for p: Array in plan.heli:
		var v: Vector3 = Vector3(float(p[0]), y0 + float(p[2]), float(p[1]))
		if not heli_path.is_empty():
			total += heli_path[heli_path.size() - 1].distance_to(v)
		heli_path.append(v)
		heli_len.append(total)
	heli.position = heli_path[0]


func _heli_at(s: float) -> Vector3:
	for k: int in range(heli_path.size() - 1):
		if s <= heli_len[k + 1]:
			var t: float = (s - heli_len[k]) / maxf(heli_len[k + 1] - heli_len[k], 0.001)
			return heli_path[k].lerp(heli_path[k + 1], t)
	return heli_path[heli_path.size() - 1]


func _process(delta: float) -> void:
	if heli and not heli_path.is_empty():
		heli_rotor.rotate_y(delta * 28.0)
		if heli_wait > 0.0:
			heli_wait -= delta
		else:
			var before: Vector3 = heli.position
			heli_s += heli_dir * float(plan.heli_speed) * delta
			var end: float = heli_len[heli_len.size() - 1]
			if heli_s >= end or heli_s <= 0.0:
				heli_s = clampf(heli_s, 0.0, end)
				heli_dir = -heli_dir
				heli_wait = 20.0
			heli.position = _heli_at(heli_s)
			var move: Vector3 = heli.position - before
			if move.length() > 0.01:
				heli.rotation.y = atan2(-move.x, -move.z)
	if hud == null:
		return
	status_timer -= delta
	if status_timer <= 0.0:
		status_timer = 0.25
		_update_status()
	if map_layer.visible:
		_update_marker()


# ---------------------------------------------------------------- прогулка


func _place_at(i: int) -> Array:
	var p: Dictionary = (plan.places as Array)[i]
	var at: Array = p.at
	var pos: Vector3
	if at.size() > 2:
		pos = Vector3(float(at[0]), y0 + float(at[2]) - 1.6, float(at[1]))
	else:
		pos = Vector3(float(at[0]), ground(float(at[0]), float(at[1])) + 0.3, float(at[1]))
	var look: Array = p.look
	return [pos, Vector3(float(look[0]), pos.y + 1.5, float(look[1]))]


func _jump(i: int) -> void:
	var places: Array = plan.places
	current = posmod(i, places.size())
	var target: Array = _place_at(current)
	walker.call("teleport", target[0], target[1])
	if title:
		title.text = "«Плотина» %s · %s" % [_env("HELI_PLAN", "v05"), String((places[current] as Dictionary).name)]


func _unhandled_input(event: InputEvent) -> void:
	if mode != "walk":
		return
	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed and Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if not (event is InputEventKey) or not (event as InputEventKey).pressed or event.is_echo():
		return
	var key: Key = (event as InputEventKey).physical_keycode
	if key == KEY_ESCAPE:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif key == KEY_M:
		map_layer.visible = not map_layer.visible
	elif key >= KEY_1 and key <= KEY_9:
		_jump(int(key - KEY_1))
	elif key == KEY_0:
		_jump(9)
	elif key == KEY_N:
		_jump(current + 1)
	elif key == KEY_B:
		_jump(current - 1)
	elif key == KEY_R:
		_jump(current)
	elif key == KEY_H:
		walker.set("flight", true)
		walker.global_position = heli.position + Vector3(0, 25, 60)
		walker.look_at(heli.position, Vector3.UP)
		walker.rotation.x = 0.0


func _ui() -> void:
	hud = CanvasLayer.new()
	hud.name = "StudyUI"
	add_child(hud)
	var root: Control = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0.035, 0.055, 0.05, 0.85)
	shade.position = Vector2(18, 18)
	shade.size = Vector2(860, 82)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(shade)
	title = Label.new()
	title.position = Vector2(32, 24)
	title.add_theme_font_size_override("font_size", 22)
	title.add_theme_color_override("font_color", Color("e0e3d2"))
	root.add_child(title)
	status = Label.new()
	status.position = Vector2(32, 58)
	status.add_theme_font_size_override("font_size", 16)
	root.add_child(status)
	var controls: Label = Label.new()
	controls.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	controls.position = Vector2(24, -84)
	controls.add_theme_font_size_override("font_size", 16)
	controls.add_theme_color_override("font_shadow_color", Color.BLACK)
	controls.add_theme_constant_override("shadow_outline_size", 8)
	controls.text = ("WASD — идти   Shift — бежать   Space — прыжок   C — присесть   F — полёт (Shift — быстрее)   H — к вертолёту\n"
		+ "M — план   1–9, 0 — места   N / B — следующее / прошлое   R — к месту   Esc — мышь\n"
		+ "Серый стенд для замера: рельеф условный, постройки коробками, лес — модели зоны 1. Не рейд и не принятая карта.")
	root.add_child(controls)
	map_layer = Control.new()
	map_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.hide()
	hud.add_child(map_layer)
	var dim: ColorRect = ColorRect.new()
	dim.color = Color(0, 0, 0, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.add_child(dim)
	map_texture = TextureRect.new()
	map_texture.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map_texture.offset_top = 20
	map_texture.offset_bottom = -20
	map_texture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	map_texture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	map_texture.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var image: Image = Image.load_from_file(ProjectSettings.globalize_path(String(plan.plan_image)))
	if image:
		map_texture.texture = ImageTexture.create_from_image(image)
	map_layer.add_child(map_texture)
	map_marker = ColorRect.new()
	map_marker.color = Color(1.0, 0.2, 0.1)
	map_marker.size = Vector2(14, 14)
	map_marker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_layer.add_child(map_marker)


func _update_marker() -> void:
	if map_texture.texture == null:
		return
	var rect: Array = plan.plan_image_rect
	var tex: Vector2 = map_texture.texture.get_size()
	var area: Vector2 = map_texture.size
	var k: float = minf(area.x / tex.x, area.y / tex.y)
	var offset: Vector2 = map_texture.position + (area - tex * k) * 0.5
	var u: float = (walker.global_position.x - float(rect[0])) / (float(rect[2]) - float(rect[0]))
	var v: float = (walker.global_position.z - float(rect[1])) / (float(rect[3]) - float(rect[1]))
	map_marker.position = offset + Vector2(u, v) * tex * k - map_marker.size * 0.5


func _update_status() -> void:
	var p: Vector3 = walker.global_position
	var draws: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
	status.text = "x %.0f  z %.0f · %+.0f м от уровня озера · %.0f к/с · вызовов %d · пройдено %.0f м за %.0f с%s" % [
		p.x, p.z, p.y - y0, Engine.get_frames_per_second(), draws, float(walker.get("travelled_m")),
		float(walker.get("walking_sec")), " · полёт" if bool(walker.get("flight")) else ""]


# ---------------------------------------------------------------- проверка и замер


func _check() -> void:
	for i: int in range(6):
		await get_tree().physics_frame
	var fails: int = 0
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	print("heli_study check: сборка %d мс; плитки %s; деревьев %d; построек %d" % [int(stats.build_ms), str(stats.tiles),
		int(stats.trees), int(stats.structures)])
	var places: Array = plan.places
	for i: int in range(places.size()):
		var target: Array = _place_at(i)
		var at: Vector3 = target[0]
		var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(at + Vector3.UP * 3.0, at - Vector3.UP * 60.0, 1)
		var hit: Dictionary = space.intersect_ray(query)
		# опора — не дальше 3 м под точкой появления (земля, гребень, настил)
		var ok: bool = not hit.is_empty() and at.y - (hit.position as Vector3).y < 3.0
		if not ok:
			fails += 1
		var where: String = "под ногами пусто"
		if not hit.is_empty():
			where = "опора на %+.1f м от озера%s" % [(hit.position as Vector3).y - y0, "" if ok else " (ниже точки на %.1f м, рельеф %+.1f)" % [
				at.y - (hit.position as Vector3).y, ground(at.x, at.z) - y0]]
		print("  %s %s: %s" % ["ok  " if ok else "НЕТ ", String((places[i] as Dictionary).name), where])
	# гребень — на плотине, а не в воздухе
	var mid: Vector3 = _arc_point(0.0, float((plan.dam as Dictionary).radius) - 5.0, float((plan.dam as Dictionary).crest))
	var crest: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(mid + Vector3.UP * 50.0, mid - Vector3.UP * 400.0, 1)
	var hit_crest: Dictionary = space.intersect_ray(crest)
	var crest_ok: bool = not hit_crest.is_empty() and absf((hit_crest.position as Vector3).y - y0 - float((plan.dam as Dictionary).crest)) < 1.5
	if not crest_ok:
		fails += 1
	print("  %s гребень плотины на +%.0f м" % ["ok  " if crest_ok else "НЕТ ", float((plan.dam as Dictionary).crest)])
	print("heli_study check: провалов %d" % fails)
	get_tree().quit(fails)


func _perf() -> void:
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 0
	hud.visible = false
	var camera: Camera3D = Camera3D.new()
	camera.far = 4000.0
	camera.fov = Settings.fps_fov_v()
	add_child(camera)
	camera.make_current()
	var vp: RID = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp, true)
	var tag: String = _env("HELI_TAG", "замер")
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var size: Vector2i = DisplayServer.window_get_size()
	var lines: PackedStringArray = [
		"«Плотина» %s, серый стенд · %s" % [out_dir.get_file().trim_prefix("heli_"), tag],
		"%s · %dx%d · качество %s · %s, %s · лес %.0f %% (%d деревьев, полные модели до %s м) · сборка %d мс" % [
			RenderingServer.get_video_adapter_name(), size.x, size.y, Settings.quality, String(RaidConditions.current.time),
			String(RaidConditions.current.weather), float(stats.forest_share) * 100.0, int(stats.trees), _env("HELI_TREE_NEAR", "300"),
			int(stats.build_ms)],
		"  %-20s %7s %7s %7s %7s %10s %8s" % ["точка", "к/с", "мс", "1% мс", "GPU мс", "треуг.", "вызовов"],
	]
	print(lines[0])
	print(lines[1])
	print(lines[2])
	var total: float = 0.0
	var count: int = 0
	for v: Dictionary in plan.views:
		var at: Array = v.at
		var pos: Vector3
		if at.size() > 2:
			pos = Vector3(float(at[0]), y0 + float(at[2]), float(at[1]))
		else:
			pos = Vector3(float(at[0]), ground(float(at[0]), float(at[1])) + 1.7, float(at[1]))
		var look: Array = v.look
		walker.global_position = pos - Vector3(0, 1.7, 0)
		camera.global_position = pos
		camera.look_at(Vector3(float(look[0]), y0 + float(look[2]), float(look[1])), Vector3.UP)
		await _frames(WARM)
		var times: Array[float] = []
		var gpu: float = 0.0
		var t0: int = Time.get_ticks_usec()
		for i: int in range(MEASURE):
			await get_tree().process_frame
			var t1: int = Time.get_ticks_usec()
			times.append(float(t1 - t0) / 1000.0)
			t0 = t1
			gpu += RenderingServer.viewport_get_measured_render_time_gpu(vp)
		times.sort()
		var mean: float = 0.0
		for t: float in times:
			mean += t
		mean /= float(times.size())
		var worst: float = times[int(times.size() * 0.99)]
		var tris: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))
		var draws: int = int(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
		var view_name: String = String(v.name)
		var line: String = "  %-20s %7.1f %7.2f %7.2f %7.2f %10d %8d" % [view_name, 1000.0 / mean, mean, worst, gpu / float(MEASURE), tris, draws]
		print(line)
		lines.append(line)
		# вид сверху — для картинки, в среднее по игровым точкам не входит
		if view_name != "сверху":
			total += mean
			count += 1
		var img: Image = get_viewport().get_texture().get_image()
		img.save_png(ProjectSettings.globalize_path("%s/%s_%s.png" % [out_dir, tag, view_name]))
	if count > 0:
		var avg: String = "  среднее по %d точкам на высоте глаз: %.1f к/с (%.2f мс)" % [count, 1000.0 / (total / count), total / count]
		print(avg)
		lines.append(avg)
	var f: FileAccess = FileAccess.open(ProjectSettings.globalize_path("%s/perf_%s.txt" % [out_dir, tag]), FileAccess.WRITE)
	f.store_string("\n".join(lines) + "\n")
	f.close()
	get_tree().quit()


## Вертолёт — в ближайшую к (x, z) точку маршрута, носом по ходу, и стоит (для кадра).
func _park_heli(xz: Array) -> void:
	var target: Vector2 = Vector2(float(xz[0]), float(xz[1]))
	var end: float = heli_len[heli_len.size() - 1]
	var best: float = 0.0
	var best_d: float = INF
	var s: float = 0.0
	while s <= end:
		var p: Vector3 = _heli_at(s)
		var d: float = Vector2(p.x, p.z).distance_to(target)
		if d < best_d:
			best_d = d
			best = s
		s += 5.0
	heli_s = best
	heli.position = _heli_at(best)
	var ahead: Vector3 = _heli_at(minf(best + 5.0, end)) - heli.position
	heli.rotation.y = atan2(-ahead.x, -ahead.z)
	heli_wait = 1.0e9


func _shots() -> void:
	hud.visible = false
	var camera: Camera3D = Camera3D.new()
	camera.far = 4000.0
	add_child(camera)
	camera.make_current()
	var dir: String = out_dir + "/shots"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	var only: PackedStringArray = OS.get_environment("HELI_SHOTS_ONLY").split(",", false)
	for v: Dictionary in plan.shots:
		var shot: String = String(v.name)
		if not only.is_empty() and not shot in only:
			continue
		var at: Array = v.at
		var pos: Vector3
		if at.size() > 2:
			pos = Vector3(float(at[0]), y0 + float(at[2]), float(at[1]))
		else:
			pos = Vector3(float(at[0]), ground(float(at[0]), float(at[1])) + float(v.get("up", 1.7)), float(at[1]))
		var look: Array = v.look
		# вне кадра с вертолётом он стоит за краем карты на севере, чтобы не попадал случайно
		_park_heli(v.get("heli", [0.0, -1700.0]))
		camera.fov = float(v.get("fov", Settings.fps_fov_v()))
		walker.global_position = pos - Vector3(0, 1.7, 0)
		camera.global_position = pos
		camera.look_at(Vector3(float(look[0]), y0 + float(look[2]), float(look[1])), Vector3.UP)
		# освещение экрана (SDFGI, засветка, глаз) догоняет новую точку
		await _frames(110)
		var img: Image = get_viewport().get_texture().get_image()
		img.save_jpg(ProjectSettings.globalize_path("%s/%s.jpg" % [dir, shot]), 0.9)
		print("heli_study shots: %s" % shot)
	get_tree().quit()


## Ортографические кадры мест: рамка с плана (центр, ширина × глубина) целиком в кадре. План — сверху, север вверху;
## вид — под углом с заданной стороны (или с той, что стенд выберет сам, _open_yaw), кадр — ровно по рамке, склоны, лес
## и постройки перед местом срезаны ближней плоскостью; где срез прошёл через склон, видна тёмная подложка — как разрез
## на чертеже. Дымку и туман на время кадров выключаем — иначе даль мутная.
func _ortho() -> void:
	hud.visible = false
	var we: WorldEnvironment = get_node_or_null("WorldEnvironment") as WorldEnvironment
	if we and we.environment:
		we.environment.fog_enabled = false
		we.environment.volumetric_fog_enabled = false
	var sun: DirectionalLight3D = get_node_or_null("Sun") as DirectionalLight3D
	if sun:
		sun.directional_shadow_max_distance = 900.0
	var camera: Camera3D = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.far = 3000.0
	add_child(camera)
	camera.make_current()
	_park_heli([0.0, -1700.0])
	_terrain_full_detail()
	# подложка разреза: лучи, ушедшие под срезанный склон, упираются в неё, а не в небо
	var section: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(8000.0, 8000.0)
	var dark: StandardMaterial3D = StandardMaterial3D.new()
	dark.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dark.albedo_color = Color(0.16, 0.16, 0.17)
	plane.material = dark
	section.mesh = plane
	section.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(section)
	var dir: String = out_dir + "/ortho"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	var only: PackedStringArray = OS.get_environment("HELI_ORTHO_ONLY").split(",", false)
	var view_size: Vector2 = get_viewport().get_visible_rect().size
	var aspect: float = view_size.x / maxf(view_size.y, 1.0)
	for v: Dictionary in plan.get("ortho", []):
		var shot: String = String(v.name)
		if not only.is_empty() and not shot in only:
			continue
		var c: Array = v.center
		var cx: float = float(c[0])
		var cz: float = float(c[1])
		var w: float = float(v.w)
		var h: float = float(v.h)
		var top: float = float(v.top)
		# низ рамки — земля в центре или уровень воды (башня в водохранилище, дебаркадер на озере)
		var gy: float = ground(cx, cz) if v.get("base") == null else y0 + float(v.base)
		walker.global_position = Vector3(cx, gy + 1.0, cz)
		for kind: String in v.views:
			if kind == "top":
				# по ширине кадра — ширина рамки, по высоте — глубина; север вверху. Камера выше всего, что попало
				# в кадр (склон хребта у края выше места — иначе камера в горе и там дыра), тени — на всю глубину кадра.
				camera.size = maxf(h, w / aspect) * 1.08
				var half: Vector2 = Vector2(camera.size * aspect, camera.size) * 0.5
				var hmin: float = gy
				var hmax: float = gy + top
				for i: int in range(25):
					for j: int in range(25):
						var g: float = ground(cx - half.x + half.x * 2.0 * i / 24.0, cz - half.y + half.y * 2.0 * j / 24.0)
						hmin = minf(hmin, g)
						hmax = maxf(hmax, g)
				var pos: Vector3 = Vector3(cx, hmax + 40.0, cz)
				section.position.y = hmin - 25.0
				camera.near = 1.0
				camera.far = pos.y - hmin + 60.0
				camera.look_at_from_position(pos, pos + Vector3.DOWN, Vector3(0, 0, -1))
			else:
				# рамка места по точкам сетки (земля и верх построек) в осях камеры: кадр — ровно по ним, ближняя
				# плоскость — сразу перед ближней точкой места, всё перед ним (склон, лес, соседние постройки) срезано
				var pitch: float = deg_to_rad(float(v.pitch))
				var yaw: float = _open_yaw(cx, cz, w, h, gy, pitch, sun) if v.get("yaw") == null else deg_to_rad(float(v.yaw))
				var target: Vector3 = Vector3(cx, gy + float(v.focus), cz)
				var off: Vector3 = Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
				var forward: Vector3 = -off
				var right: Vector3 = forward.cross(Vector3.UP).normalized()
				var up: Vector3 = right.cross(forward)
				var lo: Vector3 = Vector3(INF, INF, INF)
				var hi: Vector3 = Vector3(-INF, -INF, -INF)
				var gmin: float = gy
				for i: int in range(9):
					for j: int in range(9):
						var x: float = cx - w * 0.5 + w * i / 8.0
						var z: float = cz - h * 0.5 + h * j / 8.0
						# склон ниже места (место на вершине или уступе) в кадр не тянем: низ рамки — не ниже 10 м под центром
						var g: float = maxf(ground(x, z), gy if v.get("base") != null else gy - 10.0)
						gmin = minf(gmin, ground(x, z))
						for y: float in [g, maxf(g, gy + top)]:
							var q: Vector3 = Vector3(x, y, z) - target
							var s: Vector3 = Vector3(q.dot(right), q.dot(up), q.dot(forward))
							lo = lo.min(s)
							hi = hi.max(s)
				var centre: Vector3 = target + right * (lo.x + hi.x) * 0.5 + up * (lo.y + hi.y) * 0.5
				camera.size = maxf(hi.y - lo.y, (hi.x - lo.x) / aspect) * 1.06
				var back: float = 600.0
				camera.near = back + lo.z - 6.0
				camera.far = back + hi.z + 400.0
				camera.look_at_from_position(centre + off * back, centre, Vector3.UP)
				section.position.y = gmin - 25.0
				print("heli_study ortho: %s — курс %d°" % [shot, roundi(rad_to_deg(yaw))])
			if sun:
				sun.directional_shadow_max_distance = camera.far
			await _frames(70)
			var img: Image = get_viewport().get_texture().get_image()
			var label: String = "план" if kind == "top" else "вид"
			img.save_jpg(ProjectSettings.globalize_path("%s/%s_%s.jpg" % [dir, shot, label]), 0.9)
			print("heli_study ortho: %s_%s" % [shot, label])
	get_tree().quit()


## Земля в кадрах — самой подробной ступенью у каждой плитки: ступени переключаются по расстоянию до камеры, а ортокамера
## стоит далеко — на стыке ступеней в плане оставались дыры.
func _terrain_full_detail() -> void:
	var finest: Dictionary = {}
	var tiles: Array[MeshInstance3D] = []
	for n: Node in terrain.find_children("Terrain_*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		# имя плитки — Terrain_<x>_<z>_s<шаг>
		var parts: PackedStringArray = String(mi.name).split("_")
		var key: String = parts[1] + "_" + parts[2]
		var step: int = int(parts[3].substr(1))
		tiles.append(mi)
		if not finest.has(key) or step < int(finest[key]):
			finest[key] = step
	for mi: MeshInstance3D in tiles:
		var parts: PackedStringArray = String(mi.name).split("_")
		mi.visible = int(parts[3].substr(1)) == int(finest[parts[1] + "_" + parts[2]])
		mi.visibility_range_begin = 0.0
		mi.visibility_range_end = 0.0


## Сторона взгляда для вида под углом (перебор через 15°): склон перед местом не должен вставать выше луча взгляда —
## ближняя плоскость его срежет, и в кадре будет разрез, а не место; против солнца место в тени — штраф.
func _open_yaw(cx: float, cz: float, w: float, h: float, gy: float, pitch: float, sun: DirectionalLight3D) -> float:
	var to_sun: Vector2 = Vector2.ZERO
	if sun:
		var z: Vector3 = sun.global_basis.z
		to_sun = Vector2(z.x, z.z).normalized()
	var best: float = 0.0
	var best_score: float = INF
	for k: int in range(24):
		var yaw: float = deg_to_rad(15.0 * k)
		# back — от места к камере по земле, side — поперёк взгляда
		var back: Vector2 = Vector2(sin(yaw), cos(yaw))
		var side: Vector2 = Vector2(back.y, -back.x)
		var depth: float = absf(w * 0.5 * back.x) + absf(h * 0.5 * back.y)
		var width: float = absf(w * 0.5 * side.x) + absf(h * 0.5 * side.y)
		var score: float = 0.0
		for i: int in range(13):
			var d: float = 10.0 * i
			for j: int in range(9):
				var u: float = (float(j) / 4.0 - 1.0) * width * 1.4
				var q: Vector2 = Vector2(cx, cz) + back * (depth + d) + side * u
				score += maxf(0.0, ground(q.x, q.y) - (gy + d * tan(pitch)))
		score += maxf(0.0, (-back).dot(to_sun)) * 400.0
		if score < best_score:
			best_score = score
			best = yaw
	return best
