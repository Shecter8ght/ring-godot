extends Node3D
## Стенд «Как в Road to Vostok» (опыт владельца 2026-11-05, разбор — docs/research/road_to_vostok.md): две одинаковые
## поляны — опушка леса, земля, пруд и дом у пруда, — чтобы сравнить картинку с их настройками и с нашими.
## Наша поляна (запад): земля зоны 1 (шейдер district_terrain), наша трава DistrictGrass, берёзы, липы, тополь и сирень
## «Проспекта», вода district_water, корпус R06. Их поляна (восток): та же раскладка из файлов Road to Vostok — земля
## MT_Village, трава MS_Grass, деревья Tree_A–D (масштаб 1–2, как у их разброса), кусты, пни, ветки, камни, вода
## MT_Water, дом House_Village_A. Файлы игры читаются из её папки в Steam только на время запуска (RTV_PCK —
## другой путь), в проект ничего не копируется (AGENTS.md п. 6); нет игры — открывается одна наша поляна.
## Свет: наш общий свет рейдов (RaidAtmosphere, DayCycle, RaidWeather, CameraLook) или их (tools/rtv_look_light.gd).
## Игрок настоящий, с оружием песочницы (1–4 — стволы, V — вид). F1 — свет, F2 — время, F3 — погода, F4 — другая
## поляна, F5 — подсказка. «-- shots» — снимки во всех сочетаниях (RTV_LOOK_OUT, по умолчанию E:/RTV_research/
## rtv_look — вне проекта: на их кадрах их модели) и выход; «-- check» — сборка без окна, сводка и выход.

const RtvLight := preload("res://tools/rtv_look_light.gd")
const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
const URBAN_INDEX: String = "res://data/urban95_models.json"
const OUT_DEFAULT: String = "E:/RTV_research/rtv_look"
## Земля зоны 1: массивы слоёв (газон, редкая трава, лесная подстилка, грязь, камни, щебень) и шум.
const ZONE01_TEX: Dictionary = {
	"albedo_array": "res://assets/terrain/zone01_albedo.jpg",
	"normal_array": "res://assets/terrain/zone01_normal.jpg",
	"arm_array": "res://assets/terrain/zone01_arm.jpg",
	"noise": "res://assets/terrain/zone01_noise.png",
}
const ZONE01_GRASS: PackedStringArray = ["res://assets/zone01/models/ug_grass_tall_a.glb", "res://assets/zone01/models/ug_grass_tall_b.glb",
	"res://assets/zone01/models/ug_grass_small.glb", "res://assets/zone01/models/ug_grass_mid_b.glb", "res://assets/zone01/models/ug_grass2_c.glb"]
const ZONE01_WEEDS: PackedStringArray = ["res://assets/zone01/models/ug_weed_a.glb", "res://assets/zone01/models/ug_weed_b.glb",
	"res://assets/zone01/models/ug_dandelion_c.glb", "res://assets/zone01/models/ug_dandelion_e.glb"]

## Поляны далеко друг от друга: с одной другую не видно.
const CENTERS: Dictionary = {"ours": Vector3(-600.0, 0.0, 0.0), "rtv": Vector3(600.0, 0.0, 0.0)}
const NAMES: Dictionary = {"ours": "наша", "rtv": "Road to Vostok"}
## Поляна 140 × 140 м (локально −70…70), север — −Z. Лес — с севера и по бокам, на юге гребень закрывает горизонт.
const HALF: float = 70.0
## Докуда вокруг поляны холмы и лес (только вид: по ним не ходят).
const OUTER: float = 130.0
const POND := Vector2(16.0, 0.0)
const POND_R := Vector2(10.0, 7.0)
const POND_DEPTH: float = 1.4
const WATER_Y: float = -0.3
## Дом: центр и половина пятна (R06 — 35,4 × 12 м, их дом — 25 × 12 м), длинной стороной вдоль X.
const HOUSE := Vector2(-18.0, 0.0)
const HOUSE_HALF := Vector2(18.0, 6.5)
## Тропа от места появления к дому.
const PATH: Array[Vector2] = [Vector2(4.0, 40.0), Vector2(-3.0, 22.0), Vector2(-9.0, 7.5)]
const SPAWN := Vector2(5.0, 36.0)
const TIMES: Array[String] = ["day", "dusk", "night"]
const WEATHERS: Array[String] = ["clear", "overcast", "rain", "fog"]
const TIME_NAMES: Dictionary = {"day": "день", "dusk": "закат", "night": "ночь"}
const WEATHER_NAMES: Dictionary = {"clear": "ясно", "overcast": "пасмурно", "rain": "дождь", "fog": "туман"}
## Наш час для времени суток стенда; их час подбирается под ту же высоту солнца (ночью — 23:30 у обоих).
const OUR_HOURS: Dictionary = {"day": 12.0, "dusk": 18.5, "night": 23.5}
## Наши деревья: большие и опушка (подрост, кусты).
const OUR_BIG: Array[String] = ["P_birch_a", "P_birch_b", "P_linden_a", "P_linden_b", "P_poplar_a", "P_birch_a", "P_linden_a"]
const OUR_EDGE: Array[String] = ["P_birch_c", "P_linden_c", "P_lilac_a", "P_lilac_b", "P_lilac_c"]
## Их деревья (высота при масштабе 1: A 1,9 м, B 5,9, C 12,9, D 16,9; их разброс — масштаб 1…2) и кусты.
const RTV_BIG: Array[String] = ["res://Nature/Trees/Tree_C.tscn", "res://Nature/Trees/Tree_D.tscn", "res://Nature/Trees/Tree_B.tscn",
	"res://Nature/Trees/Tree_D.tscn", "res://Nature/Trees/Tree_C.tscn", "res://Nature/Trees/Tree_D.tscn", "res://Nature/Trees/Tree_C.tscn"]
const RTV_EDGE: Array[String] = ["res://Nature/Trees/Tree_A.tscn", "res://Nature/Trees/Tree_B.tscn", "res://Nature/Shrubs/Shrub.tscn",
	"res://Nature/Shrubs/Shrub.tscn", "res://Nature/Trees/Tree_A.tscn"]
const RTV_ROCKS: Array[String] = ["res://Nature/Rocks/Rock_A.tscn", "res://Nature/Rocks/Rock_B.tscn", "res://Nature/Rocks/Rock_C.tscn", "res://Nature/Rocks/Rock_D.tscn"]
const RTV_GROUND_MAT: String = "res://Terrains/Village/Files/MT_Village.tres"
const RTV_GRASS_MESH: String = "res://Nature/Grass/Files/MS_Grass.obj"
const RTV_GRASS_MAT: String = "res://Nature/Grass/Files/MT_Grass.tres"
const RTV_WATER_MAT: String = "res://Environment/Water/Files/MT_Water.tres"
const RTV_HOUSE: String = "res://Assets/House_Village_A/House_Village_A.tscn"
## Их разброс мелочи (данные Nature/Data/*.tres — их скрипт у нас не собирается, поэтому сетки, материал и масштаб
## переписаны из этих данных): ближняя и дальняя сетка, масштаб min…max, сколько на м² леса.
const RTV_DEBRIS: Dictionary = {
	"sticks": {"mesh": "res://Nature/Sticks/Files/MS_Sticks.obj", "far": "", "mat": "res://Nature/Sticks/Files/MT_Sticks.tres", "scale": Vector2(1.0, 2.0), "per_m2": 0.04},
	"stumps": {"mesh": "res://Nature/Stumps/Files/MS_Stump_LOD0.obj", "far": "res://Nature/Stumps/Files/MS_Stump_LOD3.obj", "mat": "res://Nature/Stumps/Files/MT_Stump.tres", "scale": Vector2(1.0, 2.0), "per_m2": 0.006},
	"logs": {"mesh": "res://Nature/Logs/Files/MS_Log_LOD0.obj", "far": "res://Nature/Logs/Files/MS_Log_LOD3.obj", "mat": "res://Nature/Logs/Files/MT_Log.tres", "scale": Vector2(2.0, 4.0), "per_m2": 0.0015},
}
## Снимки: место и куда смотреть (локально, высота цели над землёй), условия (время, погода).
const SHOT_VIEWS: Array = [
	["overview", Vector2(6.0, 38.0), Vector3(-4.0, 2.5, -6.0)],
	["pond", Vector2(36.0, 14.0), Vector3(6.0, 1.2, -3.0)],
	["forest", Vector2(-2.0, -6.0), Vector3(-6.0, 4.0, -32.0)],
	["ground", Vector2(-1.0, 26.0), Vector3(-3.0, 0.0, 20.0)],
]
const SHOT_CONDITIONS: Array = [["day", "clear"], ["dusk", "clear"], ["day", "rain"], ["night", "clear"]]

var light_mode: String = "ours"
var time_key: String = "day"
var weather_key: String = "clear"
var clearing: String = "ours"
var player: Player
var rig: CameraRig

var _rtv: Node
var _rtv_ok: bool = false
var _rtv_on: bool = false
var _rtv_hours: Dictionary = {"day": 1200.0, "dusk": 1730.0, "night": 2330.0}
var _atmo: RaidAtmosphere
var _weather: RaidWeather
var _we: WorldEnvironment
var _sun: DirectionalLight3D
var _our_env: Environment
var _hud: Label
var _help: bool = true
var _noise := FastNoiseLite.new()
var _noise_fine := FastNoiseLite.new()
var _index: Dictionary = {}
var _meshes: Dictionary = {}
var _scenes: Dictionary = {}
## Деревья поляны (одни и те же места на обеих): [Vector2 место, поворот, доля 0..1 для масштаба, номер вида, опушка].
var _trees: Array = []
var _saved_view: Dictionary = {}
var _stats: Dictionary = {}


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_noise.seed = 9131
	_noise.frequency = 0.035
	_noise_fine.seed = 4417
	_noise_fine.frequency = 0.21
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(URBAN_INDEX))
	if raw is Dictionary:
		_index = ((raw as Dictionary).get("models", raw)) as Dictionary
	RaidConditions.current = {"time": time_key, "weather": weather_key, "power": "on"}
	_we = WorldEnvironment.new()
	_we.name = "WorldEnvironment"
	_we.environment = Environment.new()
	add_child(_we)
	_sun = DirectionalLight3D.new()
	_sun.name = "Sun"
	_sun.rotation = Vector3(-0.8, deg_to_rad(-35.0), 0.0)
	_sun.shadow_enabled = true
	add_child(_sun)
	_rtv = RtvLight.new()
	_rtv.name = "RtvLight"
	add_child(_rtv)
	_rtv_ok = bool(_rtv.call("mount")) and bool(_rtv.call("build", self))
	if not _rtv_ok:
		push_warning("rtv_look: " + String(_rtv.get("error")))
	_plan_trees()
	_build_clearing("ours")
	if _rtv_ok:
		_build_clearing("rtv")
	_atmo = RaidAtmosphere.new()
	_atmo.name = "Atmosphere"
	add_child(_atmo)
	_atmo.apply()
	_our_env = _we.environment
	_weather = RaidWeather.new()
	_weather.name = "Weather"
	add_child(_weather)
	if _rtv_ok:
		_match_rtv_hours()
	_spawn_player()
	_build_hud()
	await _frames(4)
	_apply_conditions()
	_goto("ours")
	if "check" in args:
		await _check_toggle()
		_print_stats()
		get_tree().quit(0)
		return
	if "shots" in args:
		await _shots()


# ---------------------------------------------------------------- раскладка поляны (общая для обеих)

func _pond_r(x: float, z: float) -> float:
	return Vector2((x - POND.x) / POND_R.x, (z - POND.y) / POND_R.y).length()


func _house_dist(x: float, z: float) -> float:
	var dx: float = maxf(absf(x - HOUSE.x) - HOUSE_HALF.x, 0.0)
	var dz: float = maxf(absf(z - HOUSE.y) - HOUSE_HALF.y, 0.0)
	return sqrt(dx * dx + dz * dz) if dx > 0.0 or dz > 0.0 else -minf(HOUSE_HALF.x - absf(x - HOUSE.x), HOUSE_HALF.y - absf(z - HOUSE.y))


func _path_dist(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var best: float = INF
	for i: int in range(PATH.size() - 1):
		best = minf(best, p.distance_to(Geometry2D.get_closest_point_to_segment(p, PATH[i], PATH[i + 1])))
	return best


## Лес: с севера (z < −16 с изгибом опушки) и по бокам (|x| > 44), к югу бока редеют.
func _forest(x: float, z: float) -> float:
	var wob: float = _noise.get_noise_2d(x * 1.7, z * 1.7) * 7.0
	var north: float = 1.0 - smoothstep(-19.0, -13.0, z + wob)
	var sides: float = smoothstep(42.0, 48.0, absf(x) + wob) * (1.0 - smoothstep(30.0, 46.0, z))
	return clampf(maxf(north, sides), 0.0, 1.0)


## Высота земли (локально): лёгкие волны, подъём к лесу, гребни по краям, ровное пятно под домом, чаша пруда.
func _height(x: float, z: float) -> float:
	var h: float = _noise.get_noise_2d(x, z) * 0.45
	h += (1.0 - smoothstep(-62.0, -14.0, z)) * 2.6
	h += smoothstep(46.0, 68.0, z) * 3.5
	h += smoothstep(50.0, 68.0, absf(x)) * 3.0
	# за краем поляны (её стены — ±68 м) земля уходит вверх холмами: горизонт закрыт лесом и склонами
	h += smoothstep(68.0, 190.0, maxf(absf(x), absf(z))) * 16.0
	h = lerpf(0.0, h, smoothstep(0.5, 5.0, _house_dist(x, z)))
	var pr: float = _pond_r(x, z)
	if pr < 1.6:
		var bowl: float = WATER_Y + 0.12 - POND_DEPTH * maxf(0.0, 1.0 - pr * pr)
		h = lerpf(bowl, h, smoothstep(1.0, 1.6, pr))
	return h


## Из чего земля в точке: r — грязь (тропа, берег, у стен), g — щебень у крыльца, b — лесная подстилка, a — трава.
func _masks(x: float, z: float) -> Color:
	var fine: float = _noise_fine.get_noise_2d(x, z)
	var pr: float = _pond_r(x, z)
	var shore: float = 1.0 - smoothstep(1.05, 1.4 + fine * 0.15, pr)
	var path: float = 1.0 - smoothstep(0.7, 1.7, _path_dist(x, z) + fine * 0.5)
	var hd: float = _house_dist(x, z)
	var yard: float = 1.0 - smoothstep(0.5, 3.0 + fine, hd)
	var porch: float = (1.0 - smoothstep(0.0, 2.5, Vector2(x - PATH[2].x, z - PATH[2].y).length() + fine)) * 0.9
	var forest: float = _forest(x, z)
	var dirt: float = clampf(maxf(maxf(shore, path), yard * 0.6), 0.0, 1.0)
	var grass: float = lerpf(0.85, 0.3, forest) * (1.0 - smoothstep(0.35, 0.7, dirt)) * smoothstep(0.0, 1.0, hd)
	if pr < 1.15:
		grass = 0.0
	return Color(dirt, porch, forest * (1.0 - dirt), clampf(grass, 0.0, 1.0))


## Деревья — одни и те же места на обеих полянах: лес с шагом не меньше 4,8 м, опушка — подрост и кусты,
## несколько одиноких деревьев на лугу.
func _plan_trees() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 26110
	var grid: Dictionary = {}
	for _i: int in range(26000):
		var p := Vector2(rng.randf_range(-OUTER, OUTER), rng.randf_range(-OUTER, OUTER))
		var outer: bool = maxf(absf(p.x), absf(p.y)) > HALF - 4.0
		var f: float = _forest(p.x, p.y) if not outer else maxf(_forest(p.x, p.y), 0.35)
		var edge: bool = not outer and f > 0.2 and f < 0.75
		if f < 0.2 or rng.randf() > f + 0.2 or (outer and rng.randf() > 0.55):
			continue
		if _house_dist(p.x, p.y) < 5.0 or _pond_r(p.x, p.y) < 1.7 or _path_dist(p.x, p.y) < 2.5:
			continue
		var gap: float = 3.2 if edge else (6.0 if outer else 4.8)
		var cell := Vector2i(floori(p.x / 6.0), floori(p.y / 6.0))
		var free: bool = true
		for dx: int in range(-1, 2):
			for dz: int in range(-1, 2):
				for q: Vector2 in grid.get(cell + Vector2i(dx, dz), []):
					if q.distance_squared_to(p) < gap * gap:
						free = false
		if not free:
			continue
		if not grid.has(cell):
			grid[cell] = []
		(grid[cell] as Array).append(p)
		var kinds: int = OUR_EDGE.size() if edge else OUR_BIG.size()
		_trees.append([p, rng.randf() * TAU, rng.randf(), rng.randi() % kinds, edge])
	for p: Vector2 in [Vector2(-30.0, 26.0), Vector2(30.0, 30.0), Vector2(26.0, -10.0)]:
		_trees.append([p, rng.randf() * TAU, rng.randf(), rng.randi() % OUR_BIG.size(), false])


# ---------------------------------------------------------------- сборка поляны

func _build_clearing(kind: String) -> void:
	var root := Node3D.new()
	root.name = "Clearing_" + kind
	root.position = CENTERS[kind]
	add_child(root)
	_build_ground(kind, root)
	_build_outer_ground(kind, root)
	_build_walls(root)
	_build_water(kind, root)
	_build_house(kind, root)
	_build_trees(kind, root)
	if kind == "ours":
		_build_our_grass(root)
	else:
		_build_rtv_grass(root)
		_build_rtv_debris(root)


## Земля сеткой 1 м. Их шейдеру — развёртка 600 м на единицу (как их рельеф 600 × 600 м: плитка 5 м) и слои
## в цвете вершин (R — грязь с камнями, G — щебень); нашему — маска грязи / щебня / подстилки картинкой.
func _build_ground(kind: String, root: Node3D) -> void:
	var n: int = int(HALF * 2.0) + 1
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j: int in range(n):
		for i: int in range(n):
			var x: float = -HALF + float(i)
			var z: float = -HALF + float(j)
			var m: Color = _masks(x, z)
			st.set_color(Color(maxf(m.r, m.b * 0.45), m.g, 0.0, 1.0))
			st.set_uv(Vector2(x + 300.0, z + 300.0) / 600.0)
			st.add_vertex(Vector3(x, _height(x, z), z))
	for j: int in range(n - 1):
		for i: int in range(n - 1):
			var a: int = j * n + i
			st.add_index(a)
			st.add_index(a + 1)
			st.add_index(a + n)
			st.add_index(a + 1)
			st.add_index(a + n + 1)
			st.add_index(a + n)
	st.generate_normals()
	st.generate_tangents()
	var mesh: ArrayMesh = st.commit()
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	mi.mesh = mesh
	mi.material_override = _our_ground_material(root.position) if kind == "ours" else _rtv_ground_material()
	root.add_child(mi)
	var body := StaticBody3D.new()
	body.name = "GroundBody"
	var cs := CollisionShape3D.new()
	cs.shape = mesh.create_trimesh_shape()
	body.add_child(cs)
	root.add_child(body)
	if kind == "ours":
		var ground := OurGround.new()
		ground.name = "OurGround"
		ground.stand = self
		ground.origin = root.position
		ground.material = mi.material_override as ShaderMaterial
		root.add_child(ground)


## Склоны вокруг поляны: сетка 5 м до ±250 м, кроме середины (заходит под край поляны на 4 м и ниже на 5 см).
func _build_outer_ground(kind: String, root: Node3D) -> void:
	var step: float = 5.0
	var far: float = 250.0
	var n: int = int(far * 2.0 / step) + 1
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j: int in range(n):
		for i: int in range(n):
			var x: float = -far + float(i) * step
			var z: float = -far + float(j) * step
			var m: Color = _masks(x, z)
			st.set_color(Color(maxf(m.r, m.b * 0.45), m.g, 0.0, 1.0))
			st.set_uv(Vector2(x + 300.0, z + 300.0) / 600.0)
			st.add_vertex(Vector3(x, _height(x, z) - 0.05, z))
	for j: int in range(n - 1):
		for i: int in range(n - 1):
			var x0: float = -far + float(i) * step
			var z0: float = -far + float(j) * step
			if x0 >= -HALF + 4.0 and x0 + step <= HALF - 4.0 and z0 >= -HALF + 4.0 and z0 + step <= HALF - 4.0:
				continue
			var a: int = j * n + i
			st.add_index(a)
			st.add_index(a + 1)
			st.add_index(a + n)
			st.add_index(a + 1)
			st.add_index(a + n + 1)
			st.add_index(a + n)
	st.generate_normals()
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.name = "OuterGround"
	mi.mesh = st.commit()
	mi.material_override = (root.get_node("Ground") as MeshInstance3D).material_override
	root.add_child(mi)


func _our_ground_material(origin: Vector3) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://src/world/district_terrain.gdshader") as Shader
	for key: String in ZONE01_TEX:
		mat.set_shader_parameter(key, load(String(ZONE01_TEX[key])))
	var size: int = int(HALF * 2.0)
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	for j: int in range(size):
		for i: int in range(size):
			var m: Color = _masks(-HALF + float(i) + 0.5, -HALF + float(j) + 0.5)
			# маска зоны 1: r — грязь, g — камень, b — щебень, a — лесная подстилка
			img.set_pixel(i, j, Color(m.r, 0.0, m.g, m.b))
	mat.set_shader_parameter("splat", ImageTexture.create_from_image(img))
	mat.set_shader_parameter("splat_origin", Vector2(origin.x - HALF, origin.z - HALF))
	mat.set_shader_parameter("splat_size", Vector2(HALF * 2.0, HALF * 2.0))
	mat.set_shader_parameter("layer_tile", PackedFloat32Array([3.0, 3.0, 2.5, 3.0, 4.0, 2.0]))
	return mat


## Их земля: MT_Village без дорог (маска дорог нарисована под их деревню, не под нашу поляну).
func _rtv_ground_material() -> Material:
	var mat: ShaderMaterial = (load(RTV_GROUND_MAT) as ShaderMaterial).duplicate() as ShaderMaterial
	mat.set_shader_parameter("enableRoads", false)
	return mat


## Невидимые стены по краю поляны: за край не упасть.
func _build_walls(root: Node3D) -> void:
	var body := StaticBody3D.new()
	body.name = "Walls"
	for side: Vector3 in [Vector3(1, 0, 0), Vector3(-1, 0, 0), Vector3(0, 0, 1), Vector3(0, 0, -1)]:
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(1.0, 40.0, HALF * 2.0) if side.x != 0.0 else Vector3(HALF * 2.0, 40.0, 1.0)
		cs.shape = box
		cs.position = side * (HALF - 2.0) + Vector3.UP * 10.0
		body.add_child(cs)
	root.add_child(body)


func _build_water(kind: String, root: Node3D) -> void:
	var size := POND_R * 2.0 * 1.35
	if kind == "ours":
		var plane := PlaneMesh.new()
		plane.size = size
		plane.subdivide_width = 8
		plane.subdivide_depth = 8
		var mat := ShaderMaterial.new()
		mat.shader = load("res://src/world/district_water.gdshader") as Shader
		mat.set_shader_parameter("noise_tex", load(String(ZONE01_TEX.noise)))
		var res: int = 64
		var img := Image.create(res, res, false, Image.FORMAT_L8)
		for j: int in range(res):
			for i: int in range(res):
				var x: float = POND.x - size.x * 0.5 + (float(i) + 0.5) / float(res) * size.x
				var z: float = POND.y - size.y * 0.5 + (float(j) + 0.5) / float(res) * size.y
				var d: float = clampf((WATER_Y - _height(x, z)) / POND_DEPTH, 0.0, 1.0)
				img.set_pixel(i, j, Color(d, d, d))
		mat.set_shader_parameter("depth_tex", ImageTexture.create_from_image(img))
		mat.set_shader_parameter("depth_rect", Vector4(root.position.x + POND.x - size.x * 0.5, root.position.z + POND.y - size.y * 0.5, size.x, size.y))
		mat.set_shader_parameter("depth_max", POND_DEPTH)
		mat.set_shader_parameter("duckweed", 0.12)
		plane.material = mat
		var w := MeshInstance3D.new()
		w.name = "Pond"
		w.mesh = plane
		w.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		w.set_script(load("res://src/world/water_body.gd"))
		w.position = Vector3(POND.x, WATER_Y, POND.y)
		root.add_child(w)
		return
	# их вода: волны по развёртке (UV × 40 на их плоскости 1000 м) — своя плоскость с той же плотностью развёртки
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_normal(Vector3.UP)
	var corners: Array[Vector2] = [Vector2(-0.5, -0.5), Vector2(0.5, -0.5), Vector2(0.5, 0.5), Vector2(-0.5, -0.5), Vector2(0.5, 0.5), Vector2(-0.5, 0.5)]
	for c: Vector2 in corners:
		var p := c * size
		st.set_uv((p + POND + Vector2(500.0, 500.0)) / 1000.0)
		st.add_vertex(Vector3(p.x, 0.0, p.y))
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.name = "Pond"
	mi.mesh = st.commit()
	mi.material_override = load(RTV_WATER_MAT) as Material
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.position = Vector3(POND.x, WATER_Y, POND.y)
	root.add_child(mi)


func _build_house(kind: String, root: Node3D) -> void:
	var house: Node3D
	if kind == "ours":
		house = (load("res://assets/models/urban95/R06.gltf") as PackedScene).instantiate() as Node3D
		var body := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(35.37, 6.76, 11.98)
		cs.shape = box
		cs.position = Vector3(0.0, 3.38, 0.0)
		body.add_child(cs)
		house.add_child(body)
	else:
		house = _rtv_scene(RTV_HOUSE)
		if house == null:
			return
	house.name = "House"
	house.position = Vector3(HOUSE.x, 0.0, HOUSE.y)
	root.add_child(house)


## Их сцена без скриптов; без тел «Obstruction» (у них это для взгляда ИИ сквозь крону) и без точек ИИ с подписями
## (их прячет их скрипт, а он у нас снят).
func _rtv_scene(path: String) -> Node3D:
	# их сцены подменены (.remap) — load() перечитывает файл каждый раз, поэтому свой кэш
	if not _scenes.has(path):
		_scenes[path] = load(path) as PackedScene if ResourceLoader.exists(path) else null
	var ps: PackedScene = _scenes[path] as PackedScene
	if ps == null:
		return null
	var n := ps.instantiate() as Node3D
	RtvLight.strip(n)
	var junk: Array[Node] = n.find_children("Obstruction", "", true, false)
	junk.append_array(n.find_children("AI*", "", true, false))
	junk.append_array(n.find_children("*", "Label3D", true, false))
	for o: Node in junk:
		if is_instance_valid(o) and o.get_parent():
			o.get_parent().remove_child(o)
			o.free()
	return n


func _build_trees(kind: String, root: Node3D) -> void:
	var holder := Node3D.new()
	holder.name = "Trees"
	root.add_child(holder)
	var count: int = 0
	for t: Array in _trees:
		var p: Vector2 = t[0]
		var yaw: float = float(t[1])
		var k: float = float(t[2])
		var edge: bool = bool(t[4])
		var y: float = _height(p.x, p.y) - 0.05
		if kind == "ours":
			var id: String = (OUR_EDGE if edge else OUR_BIG)[int(t[3]) % (OUR_EDGE if edge else OUR_BIG).size()]
			if _our_tree(holder, id, Vector3(p.x, y, p.y), yaw, lerpf(0.9, 1.15, k)):
				count += 1
		else:
			var path: String = (RTV_EDGE if edge else RTV_BIG)[int(t[3]) % (RTV_EDGE if edge else RTV_BIG).size()]
			var tree: Node3D = _rtv_scene(path)
			if tree == null:
				continue
			tree.transform = Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * lerpf(1.0, 2.0, k)), Vector3(p.x, y, p.y))
			holder.add_child(tree)
			count += 1
	if kind == "rtv":
		var rng := RandomNumberGenerator.new()
		rng.seed = 771
		for i: int in range(6):
			var rock: Node3D = _rtv_scene(RTV_ROCKS[i % RTV_ROCKS.size()])
			if rock == null:
				continue
			var a: float = rng.randf() * TAU
			var p2 := POND + Vector2(cos(a) * POND_R.x, sin(a) * POND_R.y) * rng.randf_range(1.3, 1.6) if i < 3 else Vector2(rng.randf_range(-40.0, 40.0), rng.randf_range(-40.0, -20.0))
			rock.transform = Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.6, 1.2)), Vector3(p2.x, _height(p2.x, p2.y) - 0.3, p2.y))
			holder.add_child(rock)
	_stats[kind + "_trees"] = count


## Наше дерево из индекса моделей: ступени детализации по дальности (lods), материалы листвы — из materials_dir,
## стволы — коробки solids.
func _our_tree(holder: Node3D, id: String, pos: Vector3, yaw: float, s: float) -> bool:
	var entry: Dictionary = _index.get(id, {})
	if entry.is_empty():
		return false
	var node := Node3D.new()
	node.transform = Transform3D(Basis(Vector3.UP, yaw).scaled(Vector3.ONE * s), pos)
	var begin: float = 0.0
	for lod: Dictionary in entry.get("lods", []):
		var mesh: Mesh = _file_mesh(String(lod.file), String(entry.get("materials_dir", "")))
		if mesh == null:
			continue
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		mi.visibility_range_begin = begin
		mi.visibility_range_end = float(lod.end)
		node.add_child(mi)
		begin = float(lod.end)
	var solids: Array = entry.get("solids", [])
	if not solids.is_empty():
		var body := StaticBody3D.new()
		for sd: Array in solids:
			var cs := CollisionShape3D.new()
			var box := BoxShape3D.new()
			box.size = Vector3(float(sd[1][0]), float(sd[1][1]), float(sd[1][2]))
			cs.shape = box
			cs.position = Vector3(float(sd[0][0]), float(sd[0][1]), float(sd[0][2]))
			body.add_child(cs)
		node.add_child(body)
	holder.add_child(node)
	return true


## Первая сетка файла с материалами из materials_dir (как MallFiller._file_mesh: шейдеры листвы glTF не несёт).
func _file_mesh(file: String, materials_dir: String) -> Mesh:
	if _meshes.has(file):
		return _meshes[file] as Mesh
	var mesh: Mesh = null
	if ResourceLoader.exists(file):
		var root: Node = (load(file) as PackedScene).instantiate()
		var found: Array[Node] = root.find_children("*", "MeshInstance3D", true, false)
		if not found.is_empty():
			mesh = (found[0] as MeshInstance3D).mesh
		root.free()
	if mesh and materials_dir != "":
		mesh = mesh.duplicate() as Mesh
		for i: int in range(mesh.get_surface_count()):
			var material: Material = mesh.surface_get_material(i)
			var path: String = "%s/%s.tres" % [materials_dir, material.resource_name if material else ""]
			if material and ResourceLoader.exists(path):
				mesh.surface_set_material(i, load(path) as Material)
	_meshes[file] = mesh
	return mesh


## Наша трава: густой ярус травинок и пучки-сканы зоны 1 по карте плотности стенда (1 пиксель — 1 м).
func _build_our_grass(root: Node3D) -> void:
	var size: int = int(HALF * 2.0)
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	for j: int in range(size):
		for i: int in range(size):
			var a: float = _masks(-HALF + float(i) + 0.5, -HALF + float(j) + 0.5).a
			img.set_pixel(i, j, Color(a, a * 0.15, 0.0, 1.0))
	var grass := DistrictGrass.new()
	grass.name = "Grass"
	grass.density_texture = ImageTexture.create_from_image(img)
	grass.origin = Vector2(root.position.x - HALF, root.position.z - HALF)
	grass.models = ZONE01_GRASS
	grass.weed_models = ZONE01_WEEDS
	grass.lawn_dryness = 0.12
	add_child(grass)


## Их трава как у их разброса: пучки MS_Grass (2,3 × 0,45 м) по нормали земли, масштаб 1…1,5, куски 50 м,
## видны до 100 м, с тенью.
func _build_rtv_grass(root: Node3D) -> void:
	if not ResourceLoader.exists(RTV_GRASS_MESH):
		return
	var mesh: Mesh = load(RTV_GRASS_MESH) as Mesh
	var mat: Material = load(RTV_GRASS_MAT) as Material
	var rng := RandomNumberGenerator.new()
	rng.seed = 5150
	var chunks: Dictionary = {}
	var step: float = 1.4
	var x: float = -HALF + 2.0
	while x < HALF - 2.0:
		var z: float = -HALF + 2.0
		while z < HALF - 2.0:
			var px: float = x + rng.randf_range(-0.6, 0.6)
			var pz: float = z + rng.randf_range(-0.6, 0.6)
			if rng.randf() < _masks(px, pz).a:
				var key := Vector2i(floori((px + HALF) / 50.0), floori((pz + HALF) / 50.0))
				if not chunks.has(key):
					chunks[key] = []
				var up: Vector3 = _normal(px, pz)
				var b := Basis(Vector3.UP, rng.randf() * TAU)
				b = Basis(Quaternion(Vector3.UP, up)) * b
				(chunks[key] as Array).append(Transform3D(b.scaled(Vector3.ONE * rng.randf_range(1.0, 1.5)), Vector3(px, _height(px, pz), pz)))
			z += step
		x += step
	var total: int = 0
	for key: Vector2i in chunks:
		var list: Array = chunks[key]
		var center := Vector3((float(key.x) + 0.5) * 50.0 - HALF, 0.0, (float(key.y) + 0.5) * 50.0 - HALF)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = list.size()
		for i: int in range(list.size()):
			var t: Transform3D = list[i]
			t.origin -= center
			mm.set_instance_transform(i, t)
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.material_override = mat
		mmi.visibility_range_end = 100.0
		mmi.position = center
		root.add_child(mmi)
		total += list.size()
	_stats["rtv_grass"] = total


## Их ветки, пни и брёвна в лесу и на опушке — сетки и масштаб из их данных разброса.
func _build_rtv_debris(root: Node3D) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 1203
	for key: String in RTV_DEBRIS:
		var conf: Dictionary = RTV_DEBRIS[key]
		if not ResourceLoader.exists(String(conf.mesh)):
			continue
		var mesh: Mesh = load(String(conf.mesh)) as Mesh
		var far_mesh: Mesh = load(String(conf.far)) as Mesh if String(conf.far) != "" and ResourceLoader.exists(String(conf.far)) else null
		var mat: Material = load(String(conf.mat)) as Material if ResourceLoader.exists(String(conf.mat)) else null
		var smin: float = (conf.scale as Vector2).x
		var smax: float = (conf.scale as Vector2).y
		var xfs: Array[Transform3D] = []
		var tries: int = int(HALF * HALF * 4.0 * float(conf.per_m2))
		for _i: int in range(tries * 3):
			if xfs.size() >= tries:
				break
			var px: float = rng.randf_range(-HALF + 3.0, HALF - 3.0)
			var pz: float = rng.randf_range(-HALF + 3.0, HALF - 3.0)
			if _forest(px, pz) < 0.4 or _pond_r(px, pz) < 1.5 or _house_dist(px, pz) < 3.0:
				continue
			var b := Basis(Quaternion(Vector3.UP, _normal(px, pz))) * Basis(Vector3.UP, rng.randf() * TAU)
			xfs.append(Transform3D(b.scaled(Vector3.ONE * rng.randf_range(smin, smax)), Vector3(px, _height(px, pz), pz)))
		for pass_i: int in range(2 if far_mesh else 1):
			var mm := MultiMesh.new()
			mm.transform_format = MultiMesh.TRANSFORM_3D
			mm.mesh = mesh if pass_i == 0 else far_mesh
			mm.instance_count = xfs.size()
			for i: int in range(xfs.size()):
				mm.set_instance_transform(i, xfs[i])
			var mmi := MultiMeshInstance3D.new()
			mmi.name = key + ("" if pass_i == 0 else "_far")
			mmi.multimesh = mm
			if mat:
				mmi.material_override = mat
			if far_mesh:
				mmi.visibility_range_begin = 0.0 if pass_i == 0 else 99.0
				mmi.visibility_range_end = 100.0 if pass_i == 0 else 150.0
			else:
				mmi.visibility_range_end = 100.0
			root.add_child(mmi)
		_stats["rtv_" + key] = xfs.size()


func _normal(x: float, z: float) -> Vector3:
	var e: float = 0.5
	return Vector3(_height(x - e, z) - _height(x + e, z), 2.0 * e, _height(x, z - e) - _height(x, z + e)).normalized()


# ---------------------------------------------------------------- игрок, свет, погода

func _spawn_player() -> void:
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.name = "Player_1"
	add_child(player)
	rig = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	rig.name = "CameraRig"
	rig.target_path = NodePath("../Player_1")
	add_child(rig)


func _goto(kind: String) -> void:
	if kind == "rtv" and not _rtv_ok:
		return
	clearing = kind
	_place_player(SPAWN, Vector3(-2.0, 1.6, -8.0))
	_update_hud()


## Поставить игрока на поляне (локально) и направить взгляд на точку (высота цели — над землёй).
func _place_player(at: Vector2, look: Vector3) -> void:
	var c: Vector3 = CENTERS[clearing]
	var pos := c + Vector3(at.x, _height(at.x, at.y) + 0.1, at.y)
	player.global_position = pos
	player.velocity = Vector3.ZERO
	var target := c + Vector3(look.x, _height(look.x, look.z) + look.y, look.z)
	var dir: Vector3 = target - (pos + Vector3.UP * 1.6)
	var yaw: float = atan2(dir.x, dir.z)
	player.face(yaw)
	rig.set("_look_yaw", yaw)
	rig.set("_look_pitch", atan2(dir.y, Vector2(dir.x, dir.z).length()))


## Их час с той же высотой солнца, что у нашего дня и заката (DayCycle.sun_at); ночь — 23:30 у обоих.
func _match_rtv_hours() -> void:
	for key: String in ["day", "dusk"]:
		var want: float = DayCycle.sun_at(float(OUR_HOURS[key])).x
		var best: float = float(_rtv_hours[key])
		var best_d: float = INF
		var t: float = 900.0 if key == "day" else 1500.0
		while t < (1500.0 if key == "day" else 1795.0):
			var d: float = absf(float(_rtv.call("sun_elevation_at", t)) - want)
			if d < best_d:
				best_d = d
				best = t
			t += 5.0
		_rtv_hours[key] = best
	_stats["rtv_hours"] = _rtv_hours


func _apply_conditions() -> void:
	RaidConditions.current["time"] = time_key
	RaidConditions.current["weather"] = weather_key
	if _rtv_ok:
		_rtv.call("apply", float(_rtv_hours[time_key]), weather_key)
	if light_mode == "rtv" and _rtv_ok:
		_set_rtv_light(true)
		# наши материалы при их свете мокнут по их дождю
		var wet: float = float((RtvLight.WEATHER.get(weather_key, RtvLight.WEATHER.clear) as Dictionary).rain)
		RenderingServer.global_shader_parameter_set("rain_wet", wet)
		WaterBody.set_rain(wet)
	else:
		_set_rtv_light(false)
		_atmo.apply()
		_weather.conditions_changed()
		if DayCycle.current:
			DayCycle.current.set_hour(float(OUR_HOURS[time_key]))
	_update_hud()


## Их свет: их окружение и светила, наши атмосфера, часы, погода и «вид как с камеры» стоят; их камера — без
## автоэкспозиции, сглаживание MSAA 4× (их project.godot). Обратно — всё наше как было.
func _set_rtv_light(on: bool) -> void:
	if on == _rtv_on:
		return
	_rtv_on = on
	var vp: Viewport = get_viewport()
	var look: Node = rig.get("_look") as Node if rig else null
	var cams: Array = []
	if rig:
		for key: String in ["_camera", "_ads_cam", "_scope_cam"]:
			if rig.get(key) is Camera3D:
				cams.append(rig.get(key))
	if on:
		_weather.call("_set_rain", false)
		for n: Node in [_atmo, _weather, DayCycle.current]:
			if n:
				n.process_mode = Node.PROCESS_MODE_DISABLED
		for layer: Node in _weather.find_children("*", "CanvasLayer", true, false):
			(layer as CanvasLayer).visible = false
		_sun.visible = false
		_we.environment = _rtv.get("environment") as Environment
		_rtv.call("set_active", true)
		_saved_view = {"msaa": vp.msaa_3d, "ssaa": vp.screen_space_aa, "taa": vp.use_taa}
		vp.msaa_3d = Viewport.MSAA_4X
		vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
		vp.use_taa = false
		if look:
			look.process_mode = Node.PROCESS_MODE_DISABLED
			var lens: CanvasLayer = look.get("_layer") as CanvasLayer
			if lens:
				lens.visible = false
		for cam: Camera3D in cams:
			cam.attributes = _rtv.get("attributes") as CameraAttributes
	else:
		_we.environment = _our_env
		_rtv.call("set_active", false)
		_sun.visible = true
		for n: Node in [_atmo, _weather, DayCycle.current]:
			if n:
				n.process_mode = Node.PROCESS_MODE_INHERIT
		for layer: Node in _weather.find_children("*", "CanvasLayer", true, false):
			(layer as CanvasLayer).visible = true
		if not _saved_view.is_empty():
			vp.msaa_3d = _saved_view.msaa
			vp.screen_space_aa = _saved_view.ssaa
			vp.use_taa = bool(_saved_view.taa)
		if look:
			look.process_mode = Node.PROCESS_MODE_INHERIT
			var lens2: CanvasLayer = look.get("_layer") as CanvasLayer
			if lens2:
				lens2.visible = true
			look.call("apply_settings")


func _process(_delta: float) -> void:
	if _rtv_ok and player:
		_rtv.call("follow", get_viewport().get_camera_3d(), player.global_position)


func _unhandled_input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k == null or not k.pressed or k.echo:
		return
	match k.keycode:
		KEY_F1:
			if _rtv_ok:
				light_mode = "rtv" if light_mode == "ours" else "ours"
				_apply_conditions()
		KEY_F2:
			time_key = TIMES[(TIMES.find(time_key) + 1) % TIMES.size()]
			_apply_conditions()
		KEY_F3:
			weather_key = WEATHERS[(WEATHERS.find(weather_key) + 1) % WEATHERS.size()]
			_apply_conditions()
		KEY_F4:
			_goto("rtv" if clearing == "ours" else "ours")
		KEY_F5:
			_help = not _help
			_update_hud()
		_:
			return
	get_viewport().set_input_as_handled()


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 5
	add_child(layer)
	_hud = Label.new()
	_hud.position = Vector2(16, 12)
	_hud.add_theme_font_size_override("font_size", 16)
	_hud.add_theme_color_override("font_color", Color(1, 1, 1))
	_hud.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_hud.add_theme_constant_override("outline_size", 5)
	layer.add_child(_hud)


func _update_hud() -> void:
	if _hud == null:
		return
	var hour: String = "%02d:%02d" % [int(OUR_HOURS[time_key]), int(fmod(float(OUR_HOURS[time_key]), 1.0) * 60.0)]
	if light_mode == "rtv":
		var t: float = float(_rtv_hours[time_key])
		hour = "%02d:%02d" % [int(t / 100.0), int(fmod(t, 100.0) * 0.6)]
	var text: String = "Поляна: %s   ·   свет: %s   ·   %s %s, %s" % [NAMES[clearing],
		"Road to Vostok" if light_mode == "rtv" else "наш", TIME_NAMES[time_key], hour, WEATHER_NAMES[weather_key]]
	if not _rtv_ok:
		text += "\nФайлов Road to Vostok нет (%s) — только наша поляна" % String(_rtv.get("error"))
	if _help:
		text += "\nF1 — свет наш / Road to Vostok   F2 — время   F3 — погода   F4 — другая поляна   1–4 — стволы   F5 — скрыть"
	_hud.text = text


# ---------------------------------------------------------------- снимки и проверка

func _shots() -> void:
	var out: String = OS.get_environment("RTV_LOOK_OUT")
	if out == "":
		out = OUT_DEFAULT
	DirAccess.make_dir_recursive_absolute(out)
	_help = false
	var lights: Array[String] = ["ours"]
	if _rtv_ok:
		lights.append("rtv")
	var kinds: Array[String] = lights.duplicate()
	var only: String = OS.get_environment("RTV_LOOK_ONLY")
	for lm: String in lights:
		light_mode = lm
		for cond: Array in SHOT_CONDITIONS:
			time_key = String(cond[0])
			weather_key = String(cond[1])
			_apply_conditions()
			for kind: String in kinds:
				clearing = kind
				for view: Array in SHOT_VIEWS:
					var name: String = "%s__%s__%s_%s__%s" % [lm, kind, time_key, weather_key, view[0]]
					if only != "" and not name.contains(only):
						continue
					_place_player(view[1], view[2])
					_update_hud()
					await _seconds(1.6)
					await RenderingServer.frame_post_draw
					var img: Image = get_viewport().get_texture().get_image()
					img.save_png(out.path_join(name + ".png"))
					print("rtv_look: ", name, "  fps=", Engine.get_frames_per_second())
	print("rtv_look: снимки — ", out)
	get_tree().quit(0)


## Свет туда и обратно: при их свете — их окружение, наше солнце и наши узлы стоят; при нашем — всё как было.
func _check_toggle() -> void:
	var vp: Viewport = get_viewport()
	var msaa: int = vp.msaa_3d
	var look: Node = rig.get("_look") as Node
	var fails: int = 0
	for round_i: int in range(2):
		light_mode = "rtv"
		weather_key = "rain"
		_apply_conditions()
		await _frames(2)
		if _rtv_ok:
			fails += _ok("их свет: их окружение", _we.environment == _rtv.get("environment"))
			fails += _ok("их свет: наше солнце погашено", not _sun.visible)
			fails += _ok("их свет: наши атмосфера и погода стоят", _atmo.process_mode == Node.PROCESS_MODE_DISABLED and _weather.process_mode == Node.PROCESS_MODE_DISABLED)
			fails += _ok("их свет: «вид как с камеры» стоит", look.process_mode == Node.PROCESS_MODE_DISABLED)
			fails += _ok("их свет: MSAA 4×", vp.msaa_3d == Viewport.MSAA_4X)
		light_mode = "ours"
		weather_key = "clear"
		_apply_conditions()
		await _frames(2)
		fails += _ok("наш свет: наше окружение", _we.environment == _our_env)
		fails += _ok("наш свет: солнце", _sun.visible)
		fails += _ok("наш свет: атмосфера и погода идут", _atmo.process_mode == Node.PROCESS_MODE_INHERIT and _weather.process_mode == Node.PROCESS_MODE_INHERIT)
		fails += _ok("наш свет: «вид как с камеры» идёт", look.process_mode == Node.PROCESS_MODE_INHERIT)
		fails += _ok("наш свет: сглаживание как было", vp.msaa_3d == msaa)
	_goto("rtv")
	fails += _ok("F4: игрок на их поляне", not _rtv_ok or player.global_position.distance_to(CENTERS.rtv) < HALF)
	_stats["check_fails"] = fails


func _ok(what: String, good: bool) -> int:
	print("  %s  %s" % ["ок" if good else "ПРОВАЛ", what])
	return 0 if good else 1


func _print_stats() -> void:
	_stats["trees_planned"] = _trees.size()
	_stats["rtv_files"] = _rtv_ok
	print("rtv_look: ", JSON.stringify(_stats))


func _frames(n: int) -> void:
	for _i: int in range(n):
		await get_tree().process_frame


func _seconds(s: float) -> void:
	await get_tree().create_timer(s).timeout


## Наша земля для травы DistrictGrass: высота в мировой точке и «трава издали» в материал земли.
class OurGround:
	extends Node3D
	var stand: Node
	var origin: Vector3
	var material: ShaderMaterial

	func _enter_tree() -> void:
		add_to_group("district_terrain")

	func height_at(x: float, z: float) -> float:
		return float(stand.call("_height", x - origin.x, z - origin.z)) + origin.y

	func set_far_grass(params: Dictionary) -> void:
		for key: String in params:
			material.set_shader_parameter(key, params[key])
