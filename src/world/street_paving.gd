class_name StreetPaving
extends RefCounted
## Покрытия «Проспекта» (владелец 2026-11-07: гиперреалистичные покрытия всего, по чему ходит игрок; город брошен
## два года, лето; тротуары, площадь у вокзала и бордюры — по его фото, референсы/prospekt_paving; текстуры только
## бесплатные; «высоко» — на RTX 4050). Сейчас — варианты для стенда образцов tools/paving_probe; выбранные лягут
## на карту (ProspektLandscape) после выбора владельца.
##   street_paving.gdshader — покрытие (кирпичик ложком и ёлочкой и плиты строит сам, асфальт и крошка — фотосканы);
##   curb_stone.gdshader — бордюрный камень (сетка — curb_mesh по профилю ГОСТ 6665);
##   road_paint.gdshader — разметка и покрытие корта (тонкая пластина, стёртое — дырами).
## Наборы текстур — Poly Haven, CC0 (tools/fetch_polyhaven.py); люки и решётка — свои (tools/gen_street_iron_textures.py).
## Без assets/textures — те же шейдеры на процедурном зерне.

const SHADER: Shader = preload("res://src/world/street_paving.gdshader")
const CURB_SHADER: Shader = preload("res://src/world/curb_stone.gdshader")
const PAINT_SHADER: Shader = preload("res://src/world/road_paint.gdshader")
const TEX: String = "res://assets/textures/%s/%s.jpg"
const IRON: String = "res://assets/textures/street_iron/%s_%s.png"

## Средний цвет наборов (линейный, посчитан по картам): «color» вида задаёт цвет в sRGB, множитель — от него.
const TEX_MEAN: Dictionary = {
	"pavement_04": Color(0.0677, 0.0560, 0.0407),
	"herringbone_pavement_03": Color(0.0567, 0.0443, 0.0316),
	"aerial_asphalt_01": Color(0.1352, 0.1237, 0.1378),
	"clean_asphalt": Color(0.0592, 0.0612, 0.0618),
	"road_damaged": Color(0.0681, 0.0406, 0.0267),
	"rubberized_track": Color(0.1742, 0.0466, 0.0362),
	"concrete_floor_02": Color(0.1956, 0.1640, 0.1102),
	"rough_concrete": Color(0.4854, 0.4668, 0.3378),
	"asphalt_02": Color(0.1073, 0.1055, 0.0935),
	"asphalt_04": Color(0.2384, 0.2227, 0.2108),
	"sparse_grass": Color(0.0810, 0.0485, 0.0082),
}

## Виды покрытий для стенда: «set» — набор, «tile» — его размер, м, «color» — цвет в sRGB сухим днём; остальное —
## параметры шейдера street_paving. «name» — подпись на стенде.
const SURFACES: Dictionary = {
	# ------------------------------------------------ тротуары: серый кирпичик 200 × 100 (фото 01, 08, 17, 19)
	"walk_a": {"name": "Тротуар А — кирпичик ложком, фотоскан", "set": "pavement_04", "tile": 3.1, "height": true,
		"color": Color8(118, 116, 110), "saturation": 0.35, "repeat_break": 1, "pattern_shift": Vector2(0.5, 0.3),
		"joint_h": 0.28, "joint_weeds": 0.35, "dust": 0.25, "macro_var": 0.1, "drift": 0.65, "edge_moss": 0.35},
	"walk_b": {"name": "Тротуар Б — кирпичик ложком поперёк, каждая плитка своя", "set": "concrete_floor_02", "tile": 3.0,
		"color": Color8(124, 122, 116), "saturation": 0.3, "layout": 1, "layout_deg": 90.0, "unit_m": Vector2(0.2, 0.1),
		"bond": 0.5, "joint_m": 0.005, "bevel_m": 0.006, "unit_var": 0.07, "surface_contrast": 0.45, "unit_tilt": 0.014, "sink": 0.05,
		"joint_weeds": 0.4, "dust": 0.25, "macro_var": 0.1, "drift": 0.7, "edge_moss": 0.35},
	"walk_c": {"name": "Тротуар В — старый асфальт, трещины с травой", "set": "asphalt_04", "tile": 4.0, "height": true,
		"color": Color8(104, 102, 98), "saturation": 0.4, "detail": "clean_asphalt", "detail_k": 0.35, "cracks": 0.55,
		"crack_cell": 1.3, "crack_w": 0.014, "crack_weeds": 0.55, "patch_amount": 0.12, "patch_cell": 5.0, "patch_tone": -0.2,
		"dust": 0.3, "macro_var": 0.14, "drift": 0.75, "edge_moss": 0.3},
	# ------------------------------------------------ площадь у вокзала (фото 02, 05, 10)
	"plaza_a": {"name": "Площадь А — ёлочка, светлая, тёмные полосы-рамки (Стрелка)", "set": "concrete_floor_02",
		"tile": 3.0, "color": Color8(150, 147, 140), "saturation": 0.3, "layout": 2, "layout_deg": 45.0,
		"unit_m": Vector2(0.2, 0.1), "joint_m": 0.004, "bevel_m": 0.006, "unit_var": 0.06, "surface_contrast": 0.45, "unit_tilt": 0.012, "sink": 0.04,
		"band_period": 6.0, "band_w": 0.6, "band_axis": 0, "band_tint": Vector3(0.45, 0.45, 0.47),
		"joint_weeds": 0.3, "dust": 0.3, "macro_var": 0.08, "drift": 0.6, "edge_moss": 0.25},
	"plaza_b": {"name": "Площадь Б — плиты 500 × 500, розовые ряды (как у фонтана)", "set": "concrete_floor_02",
		"tile": 3.0, "color": Color8(142, 140, 134), "saturation": 0.35, "layout": 3, "unit_m": Vector2(0.5, 0.5),
		"bond": 0.0, "joint_m": 0.006, "bevel_m": 0.004, "unit_var": 0.06, "surface_contrast": 0.5, "unit_tilt": 0.01, "sink": 0.06,
		"band_period": 5.0, "band_w": 1.0, "band_axis": 0, "band_tint": Vector3(1.06, 0.8, 0.76), "cracks": 0.25,
		"crack_cell": 2.5, "crack_w": 0.008, "crack_weeds": 0.3, "joint_weeds": 0.4, "dust": 0.3, "macro_var": 0.08,
		"drift": 0.6, "edge_moss": 0.25},
	"plaza_c": {"name": "Площадь В — тёмная ёлочка, фотоскан", "set": "herringbone_pavement_03", "tile": 2.4, "height": true,
		"color": Color8(108, 106, 101), "saturation": 0.35, "repeat_break": 1, "pattern_shift": Vector2(0.5, 0.5),
		"joint_h": 0.3, "joint_weeds": 0.35, "dust": 0.25, "macro_var": 0.1, "drift": 0.6, "edge_moss": 0.3},
	# ------------------------------------------------ проезжая часть (фото 03, 04, 07)
	"road_a": {"name": "Дорога А — асфальт с трещинами без повтора (30 м)", "set": "aerial_asphalt_01", "tile": 30.0,
		"height": true, "color": Color8(90, 90, 89), "saturation": 0.35, "detail": "clean_asphalt", "detail_k": 0.35,
		"macro_var": 0.08, "grime": 0.15, "grime_m": 2.5, "cracks": 0.3, "crack_cell": 2.2, "crack_w": 0.01, "crack_weeds": 0.35,
		"dust": 0.2, "drift": 0.7, "edge_moss": 0.25},
	"road_b": {"name": "Дорога Б — тёмный асфальт, залитые трещины и заплаты", "set": "asphalt_02", "tile": 4.5,
		"height": true, "color": Color8(72, 72, 70), "saturation": 0.4, "detail": "clean_asphalt", "detail_k": 0.3,
		"macro_var": 0.14, "macro_m": 26.0, "grime": 0.25, "grime_m": 2.5, "seal": 0.35, "crack_cell": 2.6, "crack_w": 0.03,
		"patch_amount": 0.18, "patch_cell": 8.0, "patch_tone": -0.25, "dust": 0.2, "drift": 0.7, "edge_moss": 0.2},
	"road_c": {"name": "Дорога В — разбитый асфальт, выбоины, трава", "set": "road_damaged", "tile": 2.2, "height": true,
		"color": Color8(88, 86, 82), "saturation": 0.25, "detail": "clean_asphalt", "detail_k": 0.3, "macro_var": 0.16,
		"cracks": 0.6, "crack_cell": 1.5, "crack_w": 0.016, "crack_weeds": 0.6, "potholes": 0.35, "pothole_r": 0.5,
		"grime": 0.15, "dust": 0.25, "drift": 0.8, "edge_moss": 0.3},
	# ------------------------------------------------ площадки (фото 12–16)
	"rubber": {"name": "Детская площадка — резиновая крошка", "set": "rubberized_track", "tile": 2.0, "height": true,
		"color": Color8(118, 64, 56), "saturation": 0.85, "macro_var": 0.16, "macro_m": 6.0, "dust": 0.35,
		"dust_color": Color8(150, 140, 120), "drift": 0.8, "drift_w": 0.6, "edge_moss": 0.25, "cracks": 0.2, "crack_cell": 3.0,
		"crack_w": 0.006, "crack_weeds": 0.5},
	"court": {"name": "Корт — покрытие под краской", "set": "clean_asphalt", "tile": 2.1, "height": true,
		"color": Color8(96, 98, 100), "saturation": 0.3, "macro_var": 0.08, "cracks": 0.25, "crack_cell": 3.5,
		"crack_w": 0.006, "crack_weeds": 0.4, "dust": 0.3, "drift": 0.7, "edge_moss": 0.2},
	# газон (основа под травой)
	"lawn": {"name": "Газон", "set": "sparse_grass", "tile": 3.0, "color": Color8(78, 74, 52), "saturation": 0.6,
		"macro_var": 0.2, "macro_m": 8.0, "dust": 0.0, "joint_weeds": 0.0, "puddle_k": 0.0},
}

## Бордюры: набор, размер, цвет (sRGB), параметры curb_stone.
const CURBS: Dictionary = {
	"road": {"set": "rough_concrete", "tile": 1.6, "color": Color8(150, 149, 144), "saturation": 0.25, "dirt": 0.7,
		"dirt_h": 0.07, "chips": 0.45, "moss": 0.3},
	"walk": {"set": "rough_concrete", "tile": 1.6, "color": Color8(146, 145, 140), "saturation": 0.25, "dirt": 0.6,
		"dirt_h": 0.05, "chips": 0.35, "moss": 0.35},
}

## Профили бордюров (поперёк: z от лицевой грани, y от низа видимой части): точки обвода по кругу и где рёбра.
## БР 100.30.15 — дорожный: 150 × 300, на виду 150 над дорогой, кромка к дороге скруглена R 35 мм.
## БР 100.20.8 — тротуарный: 80 × 200, на виду 50 над тротуаром, кромки R 10 мм.
const CURB_PROFILES: Dictionary = {
	"road": {"w": 0.15, "h": 0.15, "below": 0.06, "r_front": 0.035, "r_back": 0.006},
	"walk": {"w": 0.08, "h": 0.05, "below": 0.06, "r_front": 0.01, "r_back": 0.01},
}

## Краска: цвет (sRGB), стёрто, грязь.
const PAINTS: Dictionary = {
	"white": {"color": Color8(196, 196, 188), "wear": 0.3, "dirt": 0.4},
	"yellow": {"color": Color8(206, 168, 46), "wear": 0.34, "dirt": 0.4},
	"line": {"color": Color8(196, 196, 188), "wear": 0.36, "dirt": 0.45},
	"court_orange": {"color": Color8(205, 88, 48), "wear": 0.12, "dirt": 0.25, "rough": 0.7},
	"court_blue": {"color": Color8(48, 62, 140), "wear": 0.12, "dirt": 0.25, "rough": 0.7},
	"court_grey": {"color": Color8(120, 126, 132), "wear": 0.1, "dirt": 0.25, "rough": 0.7},
	"court_grey2": {"color": Color8(84, 90, 98), "wear": 0.1, "dirt": 0.25, "rough": 0.7},
	"court_line": {"color": Color8(232, 232, 228), "wear": 0.2, "dirt": 0.25, "rough": 0.6},
}

const RAIN_FADE_SEC: float = 12.0

## Для снимков: сырость и лужи задать руками (≥ 0), иначе — от погоды рейда.
static var override_wet: float = -1.0
static var override_puddles: float = -1.0
static var _cache: Dictionary = {}
static var _rain_k: float = 0.0
static var _occlusion_id: int = 0


static func has_maps(set_id: String) -> bool:
	return ResourceLoader.exists(TEX % [set_id, "albedo"])


## Множитель цвета набора: из его среднего (с учётом насыщенности) в нужный цвет.
static func _tint(set_id: String, target: Color, saturation: float) -> Vector3:
	var mean: Color = TEX_MEAN.get(set_id, Color(0.18, 0.18, 0.18)) as Color
	var l: float = mean.r * 0.3 + mean.g * 0.59 + mean.b * 0.11
	var desat := Vector3(l + (mean.r - l) * saturation, l + (mean.g - l) * saturation, l + (mean.b - l) * saturation)
	var lin: Color = target.srgb_to_linear()
	return Vector3(lin.r / maxf(desat.x, 0.002), lin.g / maxf(desat.y, 0.002), lin.b / maxf(desat.z, 0.002))


static func material(key: String) -> ShaderMaterial:
	if _cache.has(key):
		return _cache[key]
	var spec: Dictionary = SURFACES[key]
	var m := ShaderMaterial.new()
	m.shader = SHADER
	var set_id: String = spec.set
	var maps: bool = has_maps(set_id)
	m.set_shader_parameter("use_maps", maps)
	if maps:
		for map: String in ["albedo", "normal", "arm"]:
			m.set_shader_parameter(map + "_tex", load(TEX % [set_id, map]))
		var height: bool = bool(spec.get("height", false)) and ResourceLoader.exists(TEX % [set_id, "height"])
		m.set_shader_parameter("has_height", height)
		if height:
			m.set_shader_parameter("height_tex", load(TEX % [set_id, "height"]))
		var detail: String = String(spec.get("detail", ""))
		if detail != "" and has_maps(detail):
			m.set_shader_parameter("use_detail", true)
			m.set_shader_parameter("detail_albedo_tex", load(TEX % [detail, "albedo"]))
			m.set_shader_parameter("detail_normal_tex", load(TEX % [detail, "normal"]))
	var sat: float = float(spec.get("saturation", 1.0))
	m.set_shader_parameter("tint", _tint(set_id, spec.get("color", Color(0.5, 0.5, 0.5)) as Color, sat))
	m.set_shader_parameter("base_color", spec.get("color", Color(0.5, 0.5, 0.5)) as Color)
	m.set_shader_parameter("tile_m", float(spec.tile))
	for name: String in ["saturation", "normal_strength", "rough_add", "macro_var", "macro_m", "layout_deg", "bond", "joint_m",
			"bevel_m", "unit_var", "unit_tilt", "sink", "joint_h", "band_period", "band_w", "joint_weeds", "dust", "grime", "grime_m",
			"patch_amount", "patch_cell", "patch_tone", "cracks", "crack_w", "crack_cell", "crack_weeds", "seal", "potholes",
			"pothole_r", "drift_w", "drift", "edge_moss", "detail_k", "surface_contrast", "puddle_k"]:
		if spec.has(name):
			m.set_shader_parameter(name, float(spec[name]))
	for name: String in ["layout", "repeat_break", "band_axis"]:
		if spec.has(name):
			m.set_shader_parameter(name, int(spec[name]))
	for name: String in ["unit_m", "pattern_shift"]:
		if spec.has(name):
			m.set_shader_parameter(name, spec[name] as Vector2)
	if spec.has("band_tint"):
		m.set_shader_parameter("band_tint", spec.band_tint as Vector3)
	if spec.has("dust_color"):
		m.set_shader_parameter("dust_color", spec.dust_color as Color)
	_cache[key] = m
	return m


static func curb_material(key: String) -> ShaderMaterial:
	var cache_key: String = "curb/" + key
	if _cache.has(cache_key):
		return _cache[cache_key]
	var spec: Dictionary = CURBS[key]
	var m := ShaderMaterial.new()
	m.shader = CURB_SHADER
	var set_id: String = spec.set
	var maps: bool = has_maps(set_id)
	m.set_shader_parameter("use_maps", maps)
	if maps:
		for map: String in ["albedo", "normal", "arm"]:
			m.set_shader_parameter(map + "_tex", load(TEX % [set_id, map]))
	var sat: float = float(spec.get("saturation", 0.4))
	m.set_shader_parameter("tint", _tint(set_id, spec.color as Color, sat))
	m.set_shader_parameter("base_color", spec.color as Color)
	m.set_shader_parameter("tile_m", float(spec.tile))
	for name: String in ["saturation", "dirt", "dirt_h", "chips", "moss"]:
		if spec.has(name):
			m.set_shader_parameter(name, float(spec[name]))
	_cache[cache_key] = m
	return m


## Краска: base_y бордюра не нужен; зерно — нормали мелкого слоя асфальта.
static func paint_material(key: String) -> ShaderMaterial:
	var cache_key: String = "paint/" + key
	if _cache.has(cache_key):
		return _cache[cache_key]
	var spec: Dictionary = PAINTS[key]
	var m := ShaderMaterial.new()
	m.shader = PAINT_SHADER
	m.set_shader_parameter("paint_color", spec.color as Color)
	m.set_shader_parameter("wear", float(spec.wear))
	m.set_shader_parameter("dirt", float(spec.dirt))
	m.set_shader_parameter("paint_rough", float(spec.get("rough", 0.55)))
	if has_maps("clean_asphalt"):
		m.set_shader_parameter("use_grain", true)
		m.set_shader_parameter("grain_normal", load(TEX % ["clean_asphalt", "normal"]))
	_cache[cache_key] = m
	return m


## Люк или решётка: своя карта с воротником (вне воротника прозрачно — видно покрытие).
static func iron_material(name: String) -> StandardMaterial3D:
	var cache_key: String = "iron/" + name
	if _cache.has(cache_key):
		return _cache[cache_key]
	var m := StandardMaterial3D.new()
	if ResourceLoader.exists(IRON % [name, "albedo"]):
		m.albedo_texture = load(IRON % [name, "albedo"])
		m.normal_enabled = true
		m.normal_texture = load(IRON % [name, "normal"])
		m.orm_texture = load(IRON % [name, "orm"])
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
		m.ao_enabled = true
		m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
		m.metallic = 1.0
		m.roughness = 1.0
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		m.alpha_scissor_threshold = 0.5
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	else:
		m.albedo_color = Color(0.2, 0.17, 0.14)
		m.roughness = 0.8
	_cache[cache_key] = m
	return m


## Прямоугольник покрытия на высоте y: вершины несут расстояния до краёв (UV2 — до x0 и z0, CUSTOM0.xy — до x1 и z1),
## силу краёв (COLOR: x0, x1, z0, z1 — у бордюра, стены и газона 1, у стыка с тем же покрытием 0) и поворот узора
## (CUSTOM0.z, рад).
static func surface_mesh(rect: Rect2, y: float, edges: Color, angle: float = 0.0) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_custom_format(0, SurfaceTool.CUSTOM_RGBA_FLOAT)
	var corners: Array[Vector2] = [rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)]
	# у Godot лицевая сторона — обход по часовой, если смотреть сверху
	for i: int in [0, 1, 2, 0, 2, 3]:
		var c: Vector2 = corners[i]
		st.set_normal(Vector3.UP)
		st.set_color(edges)
		st.set_uv(c)
		st.set_uv2(Vector2(c.x - rect.position.x, c.y - rect.position.y))
		st.set_custom(0, Color(rect.end.x - c.x, rect.end.y - c.y, angle, 0.0))
		st.add_vertex(Vector3(c.x, y, c.y))
	return st.commit()


## Бордюр вдоль +X длиной length (локально: лицевая грань — в плоскости z = 0, камень — в +Z, низ видимой части —
## y = 0): камни по block_m с зазором gap, у каждого чуть свой сдвиг и наклон (уложен руками). Развёртка — для
## curb_stone (UV.x вдоль камня, UV.y по обводу, UV2 — номер и длина камня, COLOR.r — у ребра).
static func curb_mesh(kind: String, length: float, seed_value: int, block_m: float = 1.0, gap: float = 0.004) -> ArrayMesh:
	var prof: Dictionary = CURB_PROFILES[kind]
	var pts: PackedVector2Array = _curb_profile(prof)
	var edge_k: PackedFloat32Array = _curb_edges(prof, pts)
	var centre := Vector2.ZERO
	for p: Vector2 in pts:
		centre += p / float(pts.size())
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var x0: float = 0.0
	var index: int = 0
	while x0 < length - 0.05:
		var x1: float = minf(x0 + block_m, length)
		var len_b: float = x1 - x0 - gap
		var dy: float = rng.randf_range(-0.003, 0.003)
		var dz: float = rng.randf_range(-0.003, 0.004)
		var yaw: float = rng.randf_range(-0.004, 0.004)
		var id: float = float(seed_value % 997) * 31.0 + float(index)
		var basis := Basis(Vector3.UP, yaw)
		var origin := Vector3(x0 + gap * 0.5, dy, dz)
		var uv2 := Vector2(id, len_b)
		# бока по обводу профиля; наружная нормаль — от середины профиля (профиль выпуклый)
		var per: float = 0.0
		for i: int in range(pts.size()):
			var j: int = (i + 1) % pts.size()
			var a: Vector2 = pts[i]
			var b: Vector2 = pts[j]
			var seg: float = a.distance_to(b)
			var n2: Vector2 = Vector2(b.y - a.y, -(b.x - a.x)).normalized()
			if n2.dot((a + b) * 0.5 - centre) < 0.0:
				n2 = -n2
			var n: Vector3 = basis * Vector3(0.0, n2.y, n2.x)
			var va0 := origin + basis * Vector3(0.0, a.y, a.x)
			var va1 := origin + basis * Vector3(len_b, a.y, a.x)
			var vb0 := origin + basis * Vector3(0.0, b.y, b.x)
			var vb1 := origin + basis * Vector3(len_b, b.y, b.x)
			_tri(st, [va0, vb0, vb1], n, [Vector2(0.0, per), Vector2(0.0, per + seg), Vector2(len_b, per + seg)], uv2,
				[edge_k[i], edge_k[j], edge_k[j]])
			_tri(st, [va0, vb1, va1], n, [Vector2(0.0, per), Vector2(len_b, per + seg), Vector2(len_b, per)], uv2,
				[edge_k[i], edge_k[j], edge_k[i]])
			per += seg
		# торцы
		var tris: PackedInt32Array = Geometry2D.triangulate_polygon(pts)
		for end: int in [0, 1]:
			var x: float = 0.0 if end == 0 else len_b
			var n: Vector3 = basis * Vector3(-1.0 if end == 0 else 1.0, 0.0, 0.0)
			for t: int in range(0, tris.size(), 3):
				var vs: Array = []
				var uvs: Array = []
				var ks: Array = []
				for k: int in [tris[t], tris[t + 1], tris[t + 2]]:
					var p: Vector2 = pts[k]
					vs.append(origin + basis * Vector3(x, p.y, p.x))
					uvs.append(Vector2(x, p.x + p.y))
					ks.append(edge_k[k])
				_tri(st, vs, n, uvs, uv2, ks)
		x0 = x1
		index += 1
	st.generate_tangents()
	return st.commit()


## Треугольник с нужной стороной: у Godot лицевая сторона — обход по часовой, если смотреть на неё (векторное
## произведение рёбер смотрит от зрителя) — порядок переставляется под нормаль.
static func _tri(st: SurfaceTool, v: Array, n: Vector3, uv: Array, uv2: Vector2, k: Array) -> void:
	var order: Array[int] = [0, 1, 2]
	if ((v[1] as Vector3) - (v[0] as Vector3)).cross((v[2] as Vector3) - (v[0] as Vector3)).dot(n) > 0.0:
		order = [0, 2, 1]
	for i: int in order:
		st.set_normal(n)
		st.set_uv(uv[i])
		st.set_uv2(uv2)
		st.set_color(Color(float(k[i]), 0.0, 0.0))
		st.add_vertex(v[i])


## Обвод профиля (z, y): от низа лицевой грани вверх, скругление к верху, верх, задняя кромка, вниз.
static func _curb_profile(prof: Dictionary) -> PackedVector2Array:
	var w: float = float(prof.w)
	var h: float = float(prof.h)
	var below: float = float(prof.below)
	var rf: float = float(prof.r_front)
	var rb: float = float(prof.r_back)
	var pts := PackedVector2Array()
	pts.append(Vector2(0.0, -below))
	# лицевая кромка: дуга от (0, h − rf) до (rf, h)
	for i: int in range(9):
		var a: float = PI - (PI * 0.5) * float(i) / 8.0
		pts.append(Vector2(rf + cos(a) * rf, h - rf + sin(a) * rf))
	for i: int in range(5):
		var a: float = PI * 0.5 - (PI * 0.5) * float(i) / 4.0
		pts.append(Vector2(w - rb + cos(a) * rb, h - rb + sin(a) * rb))
	pts.append(Vector2(w, -below))
	return pts


## Близость к ребру у точек обвода: на скруглениях 1, на гранях 0 (сколы — у рёбер).
static func _curb_edges(prof: Dictionary, pts: PackedVector2Array) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	var h: float = float(prof.h)
	for p: Vector2 in pts:
		out.append(1.0 if p.y > h - maxf(float(prof.r_front), float(prof.r_back)) - 0.002 else 0.0)
	return out


## Полоса краски: прямоугольник size (м) с центром at, повёрнутый на yaw; UV 0…1 по полосе, UV2 — её размер.
static func paint_quad(size: Vector2, y: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var hx: float = size.x * 0.5
	var hz: float = size.y * 0.5
	var c: Array = [[Vector3(-hx, y, -hz), Vector2(0, 0)], [Vector3(hx, y, -hz), Vector2(1, 0)], [Vector3(hx, y, hz), Vector2(1, 1)],
		[Vector3(-hx, y, hz), Vector2(0, 1)]]
	for i: int in [0, 1, 2, 0, 2, 3]:
		st.set_normal(Vector3.UP)
		st.set_uv(c[i][1])
		st.set_uv2(size)
		st.add_vertex(c[i][0])
	return st.commit()


## Кольцо или дуга краски (линии корта): радиусы r0…r1, углы a0…a1 (рад, от +X к +Z); UV2 = 0 — без краёв.
static func paint_arc(r0: float, r1: float, a0: float, a1: float, y: float, segments: int = 48) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i: int in range(segments):
		var t0: float = lerpf(a0, a1, float(i) / float(segments))
		var t1: float = lerpf(a0, a1, float(i + 1) / float(segments))
		var q: Array[Vector3] = [Vector3(cos(t0) * r0, y, sin(t0) * r0), Vector3(cos(t0) * r1, y, sin(t0) * r1),
			Vector3(cos(t1) * r1, y, sin(t1) * r1), Vector3(cos(t1) * r0, y, sin(t1) * r0)]
		for k: int in [0, 1, 2, 0, 2, 3]:
			st.set_normal(Vector3.UP)
			st.set_uv(Vector2(0.5, 0.5))
			st.set_uv2(Vector2.ZERO)
			st.add_vertex(q[k])
	var mesh: ArrayMesh = st.commit()
	return mesh


## Сырость всех материалов покрытий — от погоды рейда (как MallGround.sync_weather); под крышей сухо.
static func sync_weather(delta: float) -> void:
	if _cache.is_empty():
		return
	var weather: RaidWeather = RaidWeather.current
	var wet: float = 0.0
	var puddles: float = 0.0
	var raining: bool = false
	var fx: RainFx = null
	if weather != null and is_instance_valid(weather):
		wet = weather.wet
		puddles = weather.puddles
		raining = weather.is_raining()
		if weather.get_parent() != null:
			fx = weather.get_parent().get_node_or_null("Rain") as RainFx
	if override_wet >= 0.0:
		wet = override_wet
	if override_puddles >= 0.0:
		puddles = override_puddles
	_rain_k = move_toward(_rain_k, 1.0 if raining else 0.0, delta / RAIN_FADE_SEC)
	var fx_id: int = fx.get_instance_id() if fx != null and fx.occlusion != null else 0
	for m: Material in _cache.values():
		var sm := m as ShaderMaterial
		if sm == null:
			continue
		sm.set_shader_parameter("wetness", wet)
		sm.set_shader_parameter("puddles", puddles)
		sm.set_shader_parameter("rain", _rain_k)
		if fx_id != _occlusion_id:
			if fx_id != 0:
				fx.occlusion.bind(sm)
			else:
				sm.set_shader_parameter("occ_tex", null)
				sm.set_shader_parameter("occ_size", 0.0001)
	_occlusion_id = fx_id
