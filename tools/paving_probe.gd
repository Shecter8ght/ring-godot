extends Node3D
## Стенд покрытий «Проспекта» (владелец 2026-11-07: «покрытие на проспекте, все покрытия, по которым ходит игрок, —
## гиперреалистичные»; город брошен 2 года, лето; тротуары, площадь у вокзала и бордюры — по его фото, они лежат
## в референсы/prospekt_paving; текстуры только бесплатные; «высоко» — на RTX 4050). Порядок: стенд образцов → выбор
## владельца → вся карта.
## Три одинаковых куска улицы рядом — А, Б, В: газон (не косили два года) | тротуарный бордюр БР 100.20.8 | тротуар |
## дорожный бордюр БР 100.30.15 | дорога в две полосы с бело-жёлтой зеброй и решёткой ливнёвки | бордюр | площадь у
## вокзала. Варианты тротуара, дороги и площади — StreetPaving.SURFACES (walk_*, road_*, plaza_*); люки — чугунный
## ГОСТ 1968 года и полимерный. Отдельно — детская площадка (резиновая крошка) и корт (краска по покрытию).
## Свет — общий свет рейдов (TodLight, RaidAtmosphere, погода), настоящий игрок с камерой.
## Клавиши: F2 — время (день 13:00 / закат 18:30 / ночь), F3 — погода (ясно / пасмурно / дождь), F5 / F6 / F7 — к куску
## А / Б / В, F8 — к площадкам, F1 — подсказка.
## tools/paving_probe.cmd; снимки: tools/paving_probe.cmd -- shots → docs/screens/paving_probe/ (PAVING_ONLY=части имени
## через запятую, PAVING_OUT — папка), в лог — кадры в секунду и время кадра на видеокарте на каждом виде; качество графики
## на время стенда — PAVING_QUALITY=low|medium|high; PAVING_PLAIN=1 — покрытия и бордюры простыми серыми материалами (сколько
## стоят шейдеры покрытий: время видеокарты с ними и без на тех же видах).

const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
const OUT_DEFAULT: String = "res://docs/screens/paving_probe"

const TIMES: Array[String] = ["day", "dusk", "night"]
## вечер — закат по игровым часам (в 20:00 у DayCycle уже ночь)
const HOURS: Dictionary = {"day": 13.0, "dusk": 18.5, "night": 23.5}
const TIME_NAMES: Dictionary = {"day": "день 13:00", "dusk": "закат 18:30", "night": "ночь 23:30"}
const WEATHERS: Array[String] = ["clear", "overcast", "rain"]
const WEATHER_NAMES: Dictionary = {"clear": "ясно", "overcast": "пасмурно", "rain": "дождь"}

## Куски улицы: какие варианты тротуара, дороги, площади.
const SLICES: Array = [
	{"tag": "А", "walk": "walk_a", "road": "road_a", "plaza": "plaza_a", "iron": ["manhole_gost", "walk"]},
	{"tag": "Б", "walk": "walk_b", "road": "road_b", "plaza": "plaza_b", "iron": ["manhole_gost", "road"]},
	{"tag": "В", "walk": "walk_c", "road": "road_c", "plaza": "plaza_c", "iron": ["manhole_polymer", "plaza"]},
]
const SLICE_W: float = 26.0
const SLICE_GAP: float = 8.0
## Поперечник куска (z, м): газон | бордюр 0,08 | тротуар | бордюр 0,15 | дорога 7 м | бордюр | площадь.
const Z_LAWN: float = -11.5
const Z_WALK_CURB: float = -9.5
const Z_WALK: float = -9.42
const Z_ROAD_CURB: float = -5.0
const Z_ROAD: float = -4.85
const Z_ROAD_END: float = 2.15
const Z_PLAZA: float = 2.30
const Z_PLAZA_END: float = 11.3
const H_WALK: float = 0.15            # тротуар и площадь над дорогой
const H_LAWN: float = 0.12            # газон

const GRASS_LAWN: PackedStringArray = ["res://assets/zone01/models/ug_grass_tall_a.glb", "res://assets/zone01/models/ug_grass_tall_b.glb",
	"res://assets/zone01/models/ug_grass_mid_b.glb", "res://assets/zone01/models/ug_grass_mid_c.glb", "res://assets/zone01/models/ug_grass2_d.glb"]
const GRASS_SMALL: PackedStringArray = ["res://assets/zone01/models/ug_grass_small.glb", "res://assets/zone01/models/ug_grass2_c.glb"]
const WEEDS: PackedStringArray = ["res://assets/zone01/models/ug_weed_a.glb", "res://assets/zone01/models/ug_weed_b.glb",
	"res://assets/zone01/models/ug_dandelion_c.glb", "res://assets/zone01/models/ug_dandelion_e.glb"]
const NETTLE: PackedStringArray = ["res://assets/zone01/models/ug_nettle_mid_a.glb", "res://assets/zone01/models/ug_nettle_mid_b.glb"]

## Виды для снимков: имя, где стоит игрок (локально куска: x от начала, z), куда смотрит (x, высота над землёй, z).
const VIEWS: Array = [
	["walk", Vector2(2.0, -8.6), Vector3(14.0, 0.0, -7.6)],
	["road", Vector2(6.0, -5.6), Vector3(16.0, -0.2, 3.0)],
	["plaza", Vector2(10.0, 4.5), Vector3(12.5, -0.9, 7.0)],
	["gutter", Vector2(17.0, -5.4), Vector3(19.5, -1.2, -4.6)],
	["across", Vector2(13.0, 9.5), Vector3(13.0, -0.3, -9.0)],
]
const PAD_VIEWS: Array = [
	["rubber", Vector2(-27.0, 21.0), Vector3(-36.0, -0.6, 24.0)],
	["court", Vector2(-1.0, 36.5), Vector3(-12.0, -0.5, 25.0)],
]
const SHOT_CONDITIONS: Array = [["day", "clear"], ["dusk", "clear"], ["day", "rain"], ["night", "clear"]]

var time_key: String = "day"
var weather_key: String = "clear"
var player: Player
var rig: CameraRig
var _atmo: RaidAtmosphere
var _weather: RaidWeather
var _we: WorldEnvironment
var _sun: DirectionalLight3D
var _hud: Label
var _help: bool = true
var _root: Node3D
var _rng := RandomNumberGenerator.new()
var _meshes: Dictionary = {}
var _soil: StandardMaterial3D
var _scatter: Dictionary = {}          # путь модели → Array[Transform3D]
var _stats: Dictionary = {}
var _plain_mode: bool = OS.get_environment("PAVING_PLAIN") == "1"
var _plain_cache: Dictionary = {}


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_rng.seed = 7112026
	var quality: String = OS.get_environment("PAVING_QUALITY")
	if quality in Settings.QUALITY:
		Settings.quality = quality
		Settings.apply_graphics()
		Settings.changed.emit()
	RaidConditions.current = {"time": time_key, "weather": weather_key, "power": "on"}
	_we = WorldEnvironment.new()
	_we.name = "WorldEnvironment"
	_we.environment = Environment.new()
	add_child(_we)
	_sun = DirectionalLight3D.new()
	_sun.name = "Sun"
	_sun.shadow_enabled = true
	add_child(_sun)
	_root = Node3D.new()
	_root.name = "Stand"
	add_child(_root)
	_soil = StandardMaterial3D.new()
	_soil.albedo_color = Color(0.24, 0.21, 0.17)
	_soil.roughness = 1.0
	_build()
	_atmo = RaidAtmosphere.new()
	_atmo.name = "Atmosphere"
	add_child(_atmo)
	_atmo.apply()
	_weather = RaidWeather.new()
	_weather.name = "Weather"
	add_child(_weather)
	_spawn_player()
	_build_hud()
	await _frames(4)
	_apply_conditions()
	_goto(0)
	if "check" in args:
		print("paving_probe: ", JSON.stringify(_stats))
		get_tree().quit(0)
		return
	if "shots" in args or OS.get_environment("PAVING_SHOTS") == "1":
		await _shots()


func _process(delta: float) -> void:
	StreetPaving.sync_weather(delta)


# ---------------------------------------------------------------- сборка

func _build() -> void:
	# земля стенда — газон без травы (между кусками и вокруг)
	var ground := MeshInstance3D.new()
	ground.mesh = StreetPaving.surface_mesh(Rect2(-90.0, -40.0, 180.0, 100.0), -0.02, Color(0, 0, 0, 0))
	ground.material_override = StreetPaving.material("lawn")
	_root.add_child(ground)
	_collider(Vector3(0.0, -0.27, 10.0), Vector3(180.0, 0.5, 100.0))
	var x_start: float = -(SLICE_W * 3.0 + SLICE_GAP * 2.0) * 0.5
	for i: int in range(SLICES.size()):
		_slice(x_start + float(i) * (SLICE_W + SLICE_GAP), SLICES[i] as Dictionary, i)
	_pads()
	for path: String in _scatter:
		_multimesh(path, _scatter[path] as Array)
	_stats["weed_models"] = _scatter.size()


func _slice(xs: float, spec: Dictionary, index: int) -> void:
	var xe: float = xs + SLICE_W
	# покрытия: прямоугольник, высота, сила краёв (x0, x1, z0, z1)
	_surface("lawn", Rect2(xs, Z_LAWN, SLICE_W, Z_WALK_CURB - Z_LAWN), H_LAWN, Color(0, 0, 0, 1))
	_surface(String(spec.walk), Rect2(xs, Z_WALK, SLICE_W, Z_ROAD_CURB - Z_WALK), H_WALK, Color(0, 0, 1, 0.7))
	_surface(String(spec.road), Rect2(xs, Z_ROAD, SLICE_W, Z_ROAD_END - Z_ROAD), 0.0, Color(0, 0, 1, 1))
	_surface(String(spec.plaza), Rect2(xs, Z_PLAZA, SLICE_W, Z_PLAZA_END - Z_PLAZA), H_WALK, Color(0, 0, 0.7, 0))
	# бордюры: тротуарный между газоном и тротуаром (лицом к тротуару), дорожные с двух сторон дороги
	_curb("walk", Vector3(xe, H_WALK, Z_WALK), PI, 11 + index * 7)
	_curb("road", Vector3(xe, 0.0, Z_ROAD), PI, 12 + index * 7)
	_curb("road", Vector3(xs, 0.0, Z_ROAD_END), 0.0, 13 + index * 7)
	# торцы насыпных покрытий — земля
	for x: float in [xs, xe]:
		_skirt(Vector3(x, 0.0, (Z_LAWN + Z_ROAD_CURB) * 0.5), Vector3(0.04, H_WALK * 2.0, Z_ROAD_CURB - Z_LAWN))
		_skirt(Vector3(x, 0.0, (Z_PLAZA + Z_PLAZA_END) * 0.5), Vector3(0.04, H_WALK * 2.0, Z_PLAZA_END - Z_PLAZA))
	# разметка: осевая прерывистая, зебра бело-жёлтая (полосы вдоль движения по 0,45 м)
	var mid: float = (Z_ROAD + Z_ROAD_END) * 0.5
	var x: float = xs + 1.0
	while x < xe - 3.0:
		if x < xs + 15.0 or x > xs + 21.5:
			_paint("line", Vector3(x + 1.5, 0.003, mid), Vector2(3.0, 0.12))
		x += 9.0
	var z: float = Z_ROAD + 0.35
	var k: int = 0
	while z < Z_ROAD_END - 0.3:
		_paint("white" if k % 2 == 0 else "yellow", Vector3(xs + 18.0, 0.003, z + 0.225), Vector2(4.0, 0.45))
		z += 0.5
		k += 1
	# решётка ливнёвки у бордюра, люк
	_iron("drain_grate", Vector3(xs + 21.0, 0.004, Z_ROAD + 0.32), 0.0)
	var iron: Array = spec.iron
	var at: Vector3 = {"walk": Vector3(xs + 8.0, H_WALK + 0.004, -7.2), "road": Vector3(xs + 11.0, 0.004, mid + 1.6),
		"plaza": Vector3(xs + 9.0, H_WALK + 0.004, 6.5)}[String(iron[1])]
	_iron(String(iron[0]), at, _rng.randf_range(0.0, TAU))
	# подписи
	_label(Vector3(xs + 1.0, 2.6, Z_LAWN + 0.5), "Кусок " + String(spec.tag), 96)
	_label(Vector3(xs + 0.6, 1.2, (Z_WALK + Z_ROAD_CURB) * 0.5), String(StreetPaving.SURFACES[spec.walk].name), 36)
	_label(Vector3(xs + 0.6, 1.0, mid), String(StreetPaving.SURFACES[spec.road].name), 36)
	_label(Vector3(xs + 0.6, 1.2, (Z_PLAZA + Z_PLAZA_END) * 0.5), String(StreetPaving.SURFACES[spec.plaza].name), 36)
	# трава и бурьян: газон не косили два года; у бордюров и в швах — пучки
	var broken: float = [1.0, 1.2, 1.8][index]
	_scatter_strip(GRASS_LAWN, Rect2(xs + 0.1, Z_LAWN + 0.1, SLICE_W - 0.2, Z_WALK_CURB - Z_LAWN - 0.2), H_LAWN, 9.0, Vector2(0.35, 0.75))
	_scatter_strip(WEEDS, Rect2(xs + 0.1, Z_LAWN + 0.1, SLICE_W - 0.2, Z_WALK_CURB - Z_LAWN - 0.2), H_LAWN, 0.8, Vector2(0.25, 0.5))
	_scatter_strip(NETTLE, Rect2(xs + 0.1, Z_LAWN + 0.1, SLICE_W - 0.2, 0.6), H_LAWN, 0.25, Vector2(0.6, 0.95))
	# у тротуарного бордюра (со стороны тротуара) и в канаве у дорожных бордюров
	_scatter_strip(GRASS_SMALL, Rect2(xs, Z_WALK, SLICE_W, 0.18), H_WALK, 5.0 * broken, Vector2(0.1, 0.28))
	_scatter_strip(WEEDS, Rect2(xs, Z_WALK, SLICE_W, 0.18), H_WALK, 0.5 * broken, Vector2(0.1, 0.24))
	for zz: Array in [[Z_ROAD, 0.22], [Z_ROAD_END - 0.22, 0.22]]:
		_scatter_strip(GRASS_SMALL, Rect2(xs, float(zz[0]), SLICE_W, float(zz[1])), 0.0, 4.0 * broken, Vector2(0.12, 0.32))
		_scatter_strip(WEEDS, Rect2(xs, float(zz[0]), SLICE_W, float(zz[1])), 0.0, 0.6 * broken, Vector2(0.1, 0.26))
	# редкие пучки в швах тротуара и площади
	_scatter_strip(GRASS_SMALL, Rect2(xs, Z_WALK, SLICE_W, Z_ROAD_CURB - Z_WALK), H_WALK, 0.12 * broken, Vector2(0.06, 0.16))
	_scatter_strip(GRASS_SMALL, Rect2(xs, Z_PLAZA, SLICE_W, Z_PLAZA_END - Z_PLAZA), H_WALK, 0.1 * broken, Vector2(0.06, 0.16))
	_scatter_strip(GRASS_SMALL, Rect2(xs, Z_PLAZA, SLICE_W, 0.18), H_WALK, 2.0 * broken, Vector2(0.1, 0.25))
	# на разбитой дороге — трава из трещин посреди полос
	if index == 2:
		_scatter_strip(GRASS_SMALL, Rect2(xs, Z_ROAD + 0.3, SLICE_W, Z_ROAD_END - Z_ROAD - 0.6), 0.0, 0.25, Vector2(0.08, 0.22))
	# коллизии насыпных покрытий и бордюров
	_collider(Vector3(xs + SLICE_W * 0.5, H_LAWN - 0.25, (Z_LAWN + Z_WALK_CURB) * 0.5), Vector3(SLICE_W, 0.5, Z_WALK_CURB - Z_LAWN))
	_collider(Vector3(xs + SLICE_W * 0.5, H_WALK - 0.25, (Z_WALK_CURB + Z_ROAD) * 0.5), Vector3(SLICE_W, 0.5, Z_ROAD - Z_WALK_CURB))
	_collider(Vector3(xs + SLICE_W * 0.5, H_WALK - 0.25, (Z_ROAD_END + Z_PLAZA_END) * 0.5), Vector3(SLICE_W, 0.5, Z_PLAZA_END - Z_ROAD_END))
	_collider(Vector3(xs + SLICE_W * 0.5, H_WALK + 0.025, (Z_WALK_CURB + Z_WALK) * 0.5), Vector3(SLICE_W, 0.05, Z_WALK - Z_WALK_CURB))


## Площадки: детская (резиновая крошка) и корт (серый камуфляж, оранжевое поле, синяя трёхочковая зона, белые линии).
func _pads() -> void:
	_surface("rubber", Rect2(-40.0, 18.0, 10.0, 10.0), 0.03, Color(1, 1, 1, 1))
	_collider(Vector3(-35.0, -0.22, 23.0), Vector3(10.0, 0.5, 10.0))
	_label(Vector3(-39.5, 1.2, 18.5), String(StreetPaving.SURFACES.rubber.name), 36)
	_scatter_strip(GRASS_SMALL, Rect2(-40.0, 18.0, 10.0, 0.2), 0.03, 3.0, Vector2(0.1, 0.3))
	_scatter_strip(GRASS_SMALL, Rect2(-40.0, 27.8, 10.0, 0.2), 0.03, 3.0, Vector2(0.1, 0.3))
	# корт 28 × 18: основа, камуфляж, поле 22 × 12, синяя зона у кольца, белые линии
	var c0 := Vector2(-20.0, 16.0)
	_surface("court", Rect2(c0.x, c0.y, 28.0, 18.0), 0.03, Color(1, 1, 1, 1))
	_collider(Vector3(c0.x + 14.0, -0.22, c0.y + 9.0), Vector3(28.0, 0.5, 18.0))
	_label(Vector3(c0.x + 0.5, 1.2, c0.y + 0.5), "Корт — краска по покрытию (камуфляж, поле, зона, линии), стёрлась за два года", 36)
	var y: float = 0.032
	_paint("court_grey", Vector3(c0.x + 14.0, y, c0.y + 9.0), Vector2(27.6, 17.6))
	for b: int in range(26):
		var at := Vector2(c0.x + _rng.randf_range(1.0, 27.0), c0.y + _rng.randf_range(1.0, 17.0))
		_paint_arc("court_grey2", Vector3(at.x, y + 0.0005 + float(b) * 0.00002, at.y), 0.0, _rng.randf_range(0.6, 2.2), 0.0, TAU)
	var y1: float = y + 0.002
	_paint("court_orange", Vector3(c0.x + 14.0, y1, c0.y + 9.0), Vector2(22.0, 12.0))
	var basket := Vector3(c0.x + 3.0 + 1.575, y1 + 0.0005, c0.y + 9.0)
	_paint_arc("court_blue", basket, 0.0, 6.75, -PI * 0.5, PI * 0.5)
	_paint("court_blue", Vector3(c0.x + 3.0 + 0.8, y1 + 0.0005, c0.y + 9.0), Vector2(1.6, 13.5))
	_paint("court_grey", Vector3(c0.x + 3.0 + 2.9, y1 + 0.001, c0.y + 9.0), Vector2(5.8, 4.9))
	var yl: float = y1 + 0.0015
	var w: float = 0.05
	for side: float in [-1.0, 1.0]:
		_paint("court_line", Vector3(c0.x + 14.0, yl, c0.y + 9.0 + side * 6.0), Vector2(22.0, w))
		_paint("court_line", Vector3(c0.x + 14.0 + side * 11.0, yl, c0.y + 9.0), Vector2(w, 12.0))
		_paint("court_line", Vector3(c0.x + 3.0 + 2.9, yl, c0.y + 9.0 + side * 2.45), Vector2(5.8, w))
	_paint("court_line", Vector3(c0.x + 3.0 + 5.8, yl, c0.y + 9.0), Vector2(w, 4.9))
	_paint("court_line", Vector3(c0.x + 14.0, yl, c0.y + 9.0), Vector2(w, 12.0))
	_paint_arc("court_line", Vector3(c0.x + 14.0, yl, c0.y + 9.0), 1.8 - w, 1.8, 0.0, TAU)
	_paint_arc("court_line", Vector3(basket.x, yl, basket.z), 6.75 - w, 6.75, -PI * 0.5, PI * 0.5)
	_paint_arc("court_line", Vector3(c0.x + 3.0 + 5.8, yl, c0.y + 9.0), 1.8 - w, 1.8, -PI * 0.5, PI * 0.5)
	# по краю корта — трава из-под края
	for zz: float in [c0.y, c0.y + 17.8]:
		_scatter_strip(GRASS_SMALL, Rect2(c0.x, zz, 28.0, 0.2), 0.03, 3.0, Vector2(0.1, 0.3))
		_scatter_strip(WEEDS, Rect2(c0.x, zz, 28.0, 0.2), 0.03, 0.6, Vector2(0.15, 0.35))


func _surface(key: String, rect: Rect2, y: float, edges: Color) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = StreetPaving.surface_mesh(rect, y, edges)
	mi.material_override = _plain(StreetPaving.SURFACES[key].color as Color) if _plain_mode else StreetPaving.material(key)
	_root.add_child(mi)


func _curb(kind: String, at: Vector3, yaw: float, seed_value: int) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = StreetPaving.curb_mesh(kind, SLICE_W, seed_value)
	mi.material_override = _plain(StreetPaving.CURBS[kind].color as Color) if _plain_mode else StreetPaving.curb_material(kind)
	_root.add_child(mi)
	mi.position = at
	mi.rotation.y = yaw
	var prof: Dictionary = StreetPaving.CURB_PROFILES[kind]
	var w: float = float(prof.w)
	var h: float = float(prof.h)
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(SLICE_W, h + 0.06, w)
	cs.shape = shape
	body.add_child(cs)
	mi.add_child(body)
	body.position = Vector3(SLICE_W * 0.5, (h - 0.06) * 0.5, w * 0.5)


## Простой материал того же цвета (замер стоимости шейдеров покрытий).
func _plain(c: Color) -> StandardMaterial3D:
	if not _plain_cache.has(c):
		var m := StandardMaterial3D.new()
		m.albedo_color = c
		m.roughness = 0.9
		_plain_cache[c] = m
	return _plain_cache[c]


func _paint(key: String, at: Vector3, size: Vector2) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = StreetPaving.paint_quad(size, 0.0)
	mi.material_override = StreetPaving.paint_material(key)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(mi)
	mi.position = at


func _paint_arc(key: String, at: Vector3, r0: float, r1: float, a0: float, a1: float) -> void:
	var mi := MeshInstance3D.new()
	mi.mesh = StreetPaving.paint_arc(r0, r1, a0, a1, 0.0, 64)
	mi.material_override = StreetPaving.paint_material(key)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(mi)
	mi.position = at


func _iron(name: String, at: Vector3, yaw: float) -> void:
	var mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(1.0, 1.0)
	mi.mesh = plane
	mi.material_override = StreetPaving.iron_material(name)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_root.add_child(mi)
	mi.position = at
	mi.rotation.y = yaw


func _skirt(at: Vector3, size: Vector3) -> void:
	var mi := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mi.mesh = box
	mi.material_override = _soil
	_root.add_child(mi)
	mi.position = at


func _collider(at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(cs)
	_root.add_child(body)
	body.position = at


func _label(at: Vector3, text: String, size: int) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = size
	l.pixel_size = 0.006
	l.outline_size = 10
	l.modulate = Color(1.0, 0.95, 0.65)
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	_root.add_child(l)
	l.position = at


## Пучки по прямоугольнику: density — штук на м², высота — от и до, м (модель масштабируется под высоту).
func _scatter_strip(models: PackedStringArray, rect: Rect2, y: float, density: float, height: Vector2) -> void:
	var count: int = int(round(rect.get_area() * density))
	for i: int in range(count):
		var path: String = models[_rng.randi() % models.size()]
		if not ResourceLoader.exists(path):
			continue
		var p := Vector3(_rng.randf_range(rect.position.x, rect.end.x), y, _rng.randf_range(rect.position.y, rect.end.y))
		var h: float = _rng.randf_range(height.x, height.y)
		var t := Transform3D(Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3.ONE * h), p)
		if not _scatter.has(path):
			_scatter[path] = []
		(_scatter[path] as Array).append(t)


## Пучки одной модели — одним MultiMesh; масштаб в преобразованиях — желаемая высота, делим на высоту модели.
func _multimesh(path: String, transforms: Array) -> void:
	var mesh: Mesh = _model_mesh(path)
	if mesh == null or transforms.is_empty():
		return
	var model_h: float = maxf(mesh.get_aabb().size.y, 0.05)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = transforms.size()
	for i: int in range(transforms.size()):
		var t: Transform3D = transforms[i]
		var s: float = t.basis.get_scale().x / model_h
		mm.set_instance_transform(i, Transform3D(t.basis.orthonormalized().scaled(Vector3.ONE * s), t.origin))
	var mmi := MultiMeshInstance3D.new()
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	_root.add_child(mmi)
	_stats[path.get_file()] = transforms.size()


func _model_mesh(path: String) -> Mesh:
	if _meshes.has(path):
		return _meshes[path]
	var mesh: Mesh = null
	var scene := load(path) as PackedScene
	if scene:
		var inst := scene.instantiate()
		var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
		if inst is MeshInstance3D:
			found.push_front(inst)
		if not found.is_empty():
			var mi := found[0] as MeshInstance3D
			mesh = mi.mesh.duplicate() as Mesh
			for s: int in range(mesh.get_surface_count()):
				var over: Material = mi.get_surface_override_material(s)
				if over:
					mesh.surface_set_material(s, over)
		inst.free()
	_meshes[path] = mesh
	return mesh


# ---------------------------------------------------------------- игрок, свет, погода

func _spawn_player() -> void:
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.name = "Player_1"
	add_child(player)
	rig = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	rig.name = "CameraRig"
	rig.target_path = NodePath("../Player_1")
	add_child(rig)


func _slice_x(i: int) -> float:
	return -(SLICE_W * 3.0 + SLICE_GAP * 2.0) * 0.5 + float(i) * (SLICE_W + SLICE_GAP)


func _goto(i: int) -> void:
	if i < 3:
		_place(Vector3(_slice_x(i) + 2.0, H_WALK + 0.1, -8.6), Vector3(_slice_x(i) + 14.0, H_WALK + 1.0, -6.0))
	else:
		_place(Vector3(-27.0, 0.15, 21.0), Vector3(-36.0, 1.0, 24.0))


func _place(pos: Vector3, look: Vector3) -> void:
	player.global_position = pos
	player.velocity = Vector3.ZERO
	var dir: Vector3 = look - (pos + Vector3.UP * 1.6)
	var yaw: float = atan2(dir.x, dir.z)
	player.face(yaw)
	rig.set("_look_yaw", yaw)
	rig.set("_look_pitch", atan2(dir.y, Vector2(dir.x, dir.z).length()))


func _apply_conditions() -> void:
	RaidConditions.current["time"] = time_key
	RaidConditions.current["weather"] = weather_key
	_atmo.apply()
	_weather.conditions_changed()
	if DayCycle.current:
		DayCycle.current.set_hour(float(HOURS[time_key]))
	_update_hud()


func _unhandled_input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k == null or not k.pressed or k.echo:
		return
	match k.keycode:
		KEY_F1:
			_help = not _help
			_update_hud()
		KEY_F2:
			time_key = TIMES[(TIMES.find(time_key) + 1) % TIMES.size()]
			_apply_conditions()
		KEY_F3:
			weather_key = WEATHERS[(WEATHERS.find(weather_key) + 1) % WEATHERS.size()]
			_apply_conditions()
		KEY_F5:
			_goto(0)
		KEY_F6:
			_goto(1)
		KEY_F7:
			_goto(2)
		KEY_F8:
			_goto(3)
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
	var text: String = "Стенд покрытий «Проспекта»   ·   %s, %s   ·   качество: %s" % [TIME_NAMES[time_key], WEATHER_NAMES[weather_key],
		Settings.QUALITY_NAMES.get(Settings.quality, Settings.quality)]
	if _help:
		text += "\nF2 — время   F3 — погода   F5 / F6 / F7 — кусок А / Б / В   F8 — детская и корт   F1 — скрыть"
	_hud.text = text


# ---------------------------------------------------------------- снимки

func _shots() -> void:
	var out: String = OS.get_environment("PAVING_OUT")
	if out == "":
		out = ProjectSettings.globalize_path(OUT_DEFAULT)
	DirAccess.make_dir_recursive_absolute(out)
	_help = false
	var only: PackedStringArray = OS.get_environment("PAVING_ONLY").split(",", false)
	var fps: Dictionary = {}
	var gpu: Dictionary = {}
	var vp_rid: RID = get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(vp_rid, true)
	for cond: Array in SHOT_CONDITIONS:
		time_key = String(cond[0])
		weather_key = String(cond[1])
		# после дождя: плёнка и лужи сразу (в игре копятся за минуты)
		StreetPaving.override_wet = 1.0 if weather_key == "rain" else 0.0
		StreetPaving.override_puddles = 0.35 if weather_key == "rain" else 0.0
		_apply_conditions()
		var views: Array = []
		for i: int in range(SLICES.size()):
			for v: Array in VIEWS:
				var xs: float = _slice_x(i)
				var at: Vector2 = v[1]
				var look: Vector3 = v[2]
				var base: float = H_WALK if at.y < Z_ROAD or at.y > Z_ROAD_END else 0.0
				views.append(["%s_%s" % ["abc"[i], String(v[0])], Vector3(xs + at.x, base + 0.1, at.y),
					Vector3(xs + look.x, base + 1.6 + look.y, look.z)])
		for v: Array in PAD_VIEWS:
			var at2: Vector2 = v[1]
			var look2: Vector3 = v[2]
			views.append([String(v[0]), Vector3(at2.x, 0.15, at2.y), Vector3(look2.x, 1.6 + look2.y, look2.z)])
		for view: Array in views:
			var name: String = "%s_%s__%s" % [time_key, weather_key, String(view[0])]
			var wanted: bool = only.is_empty()
			for part: String in only:
				wanted = wanted or name.contains(part)
			if not wanted:
				continue
			_place(view[1], view[2])
			_update_hud()
			await _seconds(1.5)
			# кадры в секунду — по числу кадров за секунду
			var f0: int = Engine.get_frames_drawn()
			await _seconds(1.0)
			var f: int = Engine.get_frames_drawn() - f0
			# время кадра на видеокарте — среднее за 30 кадров
			var ms: float = 0.0
			for _k: int in range(30):
				await RenderingServer.frame_post_draw
				ms += RenderingServer.viewport_get_measured_render_time_gpu(vp_rid) / 30.0
			gpu[name] = ms
			get_viewport().get_texture().get_image().save_png(out.path_join(name + ".png"))
			fps[name] = f
			print("paving_probe: %s  к/с=%d  видеокарта=%.2f мс" % [name, f, ms])
	StreetPaving.override_wet = -1.0
	StreetPaving.override_puddles = -1.0
	var vals: Array = fps.values()
	vals.sort()
	if not vals.is_empty():
		print("paving_probe: к/с — меньше всего %d, медиана %d, видов %d" % [vals[0], vals[vals.size() / 2], vals.size()])
	var g: Array = gpu.values()
	g.sort()
	if not g.is_empty():
		print("paving_probe: видеокарта — больше всего %.2f мс, медиана %.2f мс" % [g[g.size() - 1], g[g.size() / 2]])
	print("paving_probe: снимки — ", out)
	get_tree().quit(0)


func _frames(n: int) -> void:
	for _i: int in range(n):
		await get_tree().process_frame


func _seconds(s: float) -> void:
	await get_tree().create_timer(s).timeout
