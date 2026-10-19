@tool
extends RefCounted
## Покрытия территории ТЦ (шейдер src/world/paved_ground.gdshader): асфальт дорог, парковок и двора,
## бетон у доков и на площадках, тротуарная плитка, площадь, дорожки сквера, щебень, грунт, газон сквера.
## Подбор — по ярославским ТЦ («Глобус», «Вернисаж», «Альтаир», «Аура», владелец 2026-10-19): парковки —
## светлый выветренный асфальт с заплатами и масляными пятнами, дороги темнее и с залитыми трещинами,
## двор доков — асфальт, перед воротами доков — бетонные плиты, тротуары — серая «волна», у входа —
## узорная плитка, обочины — щебень. Наборы — Poly Haven, CC0 (tools/fetch_polyhaven.py, build_textures.py).
## Нет assets/textures — тот же шейдер на процедурном зерне (use_maps = false); посмотреть его при текстурах —
## переменная окружения MALL_GROUND_FALLBACK=1.
## Материалы общие для всех узлов черновика (MallLandscape, MallStreets, MallPark) — один кэш.

const SHADER: Shader = preload("res://src/world/paved_ground.gdshader")
const TEX_DIR: String = "res://assets/textures/%s/%s.jpg"

## Поверхность → набор текстур (set), размер плитки (tile, м) и параметры шейдера; fallback — тон и
## зерно процедурного варианта, slabs_fb — плиты процедурного варианта (у плитки — размер плитки).
const SURFACES: Dictionary = {
	# дороги: асфальт темнее, трещины залиты битумом, ямочные заплаты, обочина — щебень
	"road": {"set": "asphalt_02", "tile": 4.5, "height": true, "tint": Color(0.96, 0.96, 0.97), "saturation": 0.55,
		"macro_var": 0.16, "macro_m": 26.0, "grime": 0.2, "grime_m": 3.0, "seal": 0.3, "seal_cell": 2.6, "patch_amount": 0.15,
		"patch_cell": 9.0, "patch_tone": -0.25, "fallback": Color(0.27, 0.27, 0.27), "grain": 0.14},
	# парковки: светлый выветренный асфальт, заплаты дугами вдоль рядов, масляные пятна
	"parking": {"set": "asphalt_04", "tile": 4.0, "height": true, "tint": Color(0.86, 0.86, 0.87), "saturation": 0.45,
		"macro_var": 0.14, "macro_m": 30.0, "grime": 0.3, "grime_m": 2.0, "seal": 0.2, "seal_cell": 2.0, "polar": true,
		"patch_amount": 0.14, "patch_cell": 8.0, "patch_tone": -0.28, "fallback": Color(0.4, 0.4, 0.39), "grain": 0.12},
	# двор доков: тот же асфальт, грязнее — фуры, масло, поддоны
	"pit": {"set": "asphalt_04", "tile": 4.0, "height": true, "tint": Color(0.72, 0.715, 0.71), "saturation": 0.4,
		"macro_var": 0.2, "macro_m": 18.0, "grime": 0.5, "grime_m": 2.0, "seal": 0.3, "seal_cell": 1.6, "polar": true,
		"patch_amount": 0.25, "patch_cell": 7.0, "patch_tone": -0.3, "fallback": Color(0.34, 0.34, 0.33), "grain": 0.13},
	# перед воротами доков: бетонные плиты с пропилами швов
	"apron": {"set": "concrete_floor_worn_001", "tile": 3.0, "tint": Color(1.18, 1.16, 1.12), "saturation": 0.6,
		"macro_var": 0.12, "macro_m": 14.0, "grime": 0.35, "grime_m": 1.8, "polar": true, "slabs": true,
		"slab_m": Vector2(6.0, 4.0), "joint_m": 0.025, "slab_var": 0.08, "rough_add": 0.05,
		"fallback": Color(0.5, 0.5, 0.48), "grain": 0.08},
	# бетонные площадки плана (ground.zones «concrete»)
	"slab": {"set": "concrete_floor_worn_001", "tile": 3.0, "tint": Color(1.18, 1.16, 1.12), "saturation": 0.6,
		"macro_var": 0.14, "macro_m": 14.0, "grime": 0.2, "grime_m": 2.0, "slabs": true, "slab_m": Vector2(3.0, 3.0),
		"joint_m": 0.02, "slab_var": 0.1, "rough_add": 0.05, "fallback": Color(0.5, 0.5, 0.48), "grain": 0.08},
	# тротуары и кольцо у здания: серая «волна» (период узора — 1/11 текстуры по диагонали)
	"walk": {"set": "brick_pavement_03", "tile": 2.5, "tint": Color(1.0, 1.0, 1.0), "saturation": 0.7,
		"repeat_break": 1, "pattern_shift": Vector2(4.0 / 11.0, 2.0 / 11.0), "macro_var": 0.12, "macro_m": 16.0,
		"grime": 0.08, "grime_m": 2.0, "joint_dirt": 0.35, "fallback": Color(0.46, 0.45, 0.43), "grain": 0.08,
		"slabs_fb": Vector2(0.23, 0.23)},
	# площадь у входа и аллея (период узора — 1/5)
	"plaza": {"set": "patterned_paving", "tile": 2.0, "tint": Color(1.02, 0.98, 0.95), "saturation": 0.8,
		"repeat_break": 1, "pattern_shift": Vector2(0.4, 0.6), "macro_var": 0.1, "macro_m": 18.0,
		"grime": 0.05, "grime_m": 2.0, "joint_dirt": 0.25, "fallback": Color(0.5, 0.45, 0.42), "grain": 0.08,
		"slabs_fb": Vector2(0.4, 0.4)},
	# дорожки и площадки сквера (период узора — 1/3 и полтекстуры по диагонали)
	"paving": {"set": "patterned_brick_floor", "tile": 1.81, "tint": Color(0.97, 0.97, 0.96), "saturation": 0.7,
		"repeat_break": 1, "pattern_shift": Vector2(1.0 / 3.0 + 0.5, 0.5), "macro_var": 0.1, "macro_m": 14.0,
		"grime": 0.06, "grime_m": 2.0, "joint_dirt": 0.4, "fallback": Color(0.55, 0.54, 0.52), "grain": 0.08,
		"slabs_fb": Vector2(0.3, 0.3)},
	# щебень: обочины, площадки
	"gravel": {"set": "gravel_stones", "tile": 2.0, "tint": Color(1.25, 1.24, 1.2), "saturation": 0.5,
		"macro_var": 0.18, "macro_m": 12.0, "grime": 0.15, "grime_m": 3.0, "rough_add": 0.05,
		"fallback": Color(0.42, 0.41, 0.39), "grain": 0.3, "grain_m": 0.025},
	# грунт: тропы, грунтовки, колеи, площадки, пашня под колосьями
	"path": {"set": "mud_forest", "tile": 3.0, "tint": Color(1.12, 1.06, 1.0), "saturation": 0.8,
		"macro_var": 0.2, "macro_m": 10.0, "fallback": Color(0.3, 0.25, 0.19), "grain": 0.2},
	"dirt": {"set": "mud_forest", "tile": 3.0, "tint": Color(1.18, 1.1, 1.02), "saturation": 0.75,
		"macro_var": 0.22, "macro_m": 12.0, "fallback": Color(0.33, 0.28, 0.21), "grain": 0.2},
	"mud": {"set": "mud_forest", "tile": 3.0, "tint": Color(0.85, 0.82, 0.78), "saturation": 0.8,
		"macro_var": 0.2, "macro_m": 8.0, "rough_add": -0.15, "fallback": Color(0.22, 0.19, 0.15), "grain": 0.18},
	"field": {"set": "mud_forest", "tile": 3.0, "tint": Color(1.05, 0.98, 0.9), "saturation": 0.85,
		"macro_var": 0.18, "macro_m": 20.0, "fallback": Color(0.3, 0.25, 0.18), "grain": 0.2},
	# газон сквера
	"court": {"set": "leafy_grass", "tile": 3.0, "tint": Color(0.92, 1.0, 0.85), "saturation": 1.1,
		"macro_var": 0.18, "macro_m": 16.0, "fallback": Color(0.3, 0.36, 0.2), "grain": 0.2},
}

## Где у кольца шов угла сетки заплат и плит: там (сквер, север) кольцевых покрытий нет.
const POLAR_SEAM_DEG: float = -100.0
## Как быстро рябь от капель набирает силу и гаснет (как дождь у RaidWeather), с.
const RAIN_FADE_SEC: float = 12.0

static var _cache: Dictionary = {}
static var _rain_k: float = 0.0
static var _occlusion_id: int = 0


static func keys() -> Array:
	return SURFACES.keys()


static func material(key: String) -> ShaderMaterial:
	if _cache.has(key):
		return _cache[key]
	var spec: Dictionary = SURFACES[key]
	var m: ShaderMaterial = ShaderMaterial.new()
	m.shader = SHADER
	var maps: bool = ResourceLoader.exists(TEX_DIR % [spec.set, "albedo"]) and OS.get_environment("MALL_GROUND_FALLBACK") != "1"
	m.set_shader_parameter("use_maps", maps)
	if maps:
		m.set_shader_parameter("albedo_tex", load(TEX_DIR % [spec.set, "albedo"]))
		m.set_shader_parameter("normal_tex", load(TEX_DIR % [spec.set, "normal"]))
		m.set_shader_parameter("arm_tex", load(TEX_DIR % [spec.set, "arm"]))
		var height: bool = bool(spec.get("height", false)) and ResourceLoader.exists(TEX_DIR % [spec.set, "height"])
		m.set_shader_parameter("has_height", height)
		if height:
			m.set_shader_parameter("height_tex", load(TEX_DIR % [spec.set, "height"]))
	m.set_shader_parameter("tile_m", float(spec.tile))
	m.set_shader_parameter("polar_seam_deg", POLAR_SEAM_DEG)
	var fallback: Color = spec.get("fallback", Color(0.4, 0.4, 0.4))
	m.set_shader_parameter("base_color", fallback)
	for name: String in ["saturation", "macro_var", "macro_m", "grime", "grime_m", "joint_dirt", "seal", "seal_cell", "patch_amount",
			"patch_cell", "patch_tone", "joint_m", "slab_var", "rough_add", "grain", "grain_m", "normal_strength"]:
		if spec.has(name):
			m.set_shader_parameter(name, float(spec[name]))
	for name: String in ["polar", "slabs"]:
		if spec.has(name):
			m.set_shader_parameter(name, bool(spec[name]))
	if spec.has("tint"):
		m.set_shader_parameter("tint", spec.tint as Color)
	if spec.has("repeat_break"):
		m.set_shader_parameter("repeat_break", int(spec.repeat_break))
		m.set_shader_parameter("pattern_shift", spec.pattern_shift)
	if spec.has("slab_m"):
		m.set_shader_parameter("slab_m", spec.slab_m)
	# без текстур плитка — процедурными плитками своего размера
	if not maps and spec.has("slabs_fb"):
		m.set_shader_parameter("slabs", true)
		m.set_shader_parameter("slab_m", spec.slabs_fb)
		m.set_shader_parameter("joint_m", 0.012)
		m.set_shader_parameter("slab_var", 0.06)
	_cache[key] = m
	return m


## Сырость покрытий — от погоды рейда (RaidWeather: плёнка и лужи копятся в дождь, сохнут после),
## под крышей сухо — карта RainOcclusion дождя (RainFx), пока он идёт. Зовёт MallLandscape раз в несколько кадров.
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
	_rain_k = move_toward(_rain_k, 1.0 if raining else 0.0, delta / RAIN_FADE_SEC)
	var fx_id: int = fx.get_instance_id() if fx != null and fx.occlusion != null else 0
	for m: ShaderMaterial in _cache.values():
		m.set_shader_parameter("wetness", wet)
		m.set_shader_parameter("puddles", puddles)
		m.set_shader_parameter("rain", _rain_k)
		if fx_id != _occlusion_id:
			if fx_id != 0:
				fx.occlusion.bind(m)
			else:
				# дождя (и карты) нет — всё открыто небу
				m.set_shader_parameter("occ_tex", null)
				m.set_shader_parameter("occ_size", 0.0001)
	_occlusion_id = fx_id
