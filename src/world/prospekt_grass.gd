extends RefCounted
## Кандидаты земли и травы «Проспекта». Общие материалы стенда и одного тестового газона;
## отсутствие необязательных файлов не мешает прежнему процедурному варианту.

const GROUND_SHADER: Shader = preload("res://src/world/prospekt_grass_ground.gdshader")
const TEX: String = "res://assets/textures/prospekt_grass/%s_%s.jpg"
const MODEL: String = "res://assets/models/prospekt_grass/%s_lod%d.gltf"
const BASE_ASSETS: PackedStringArray = ["grass_bermuda_01_a", "grass_bermuda_01_b", "grass_bermuda_01_c"]
const CLUMP_ASSETS: PackedStringArray = ["grass_medium_01_a", "grass_medium_01_b", "grass_medium_01_tall"]
const WEED_ASSETS: PackedStringArray = ["weed_plant_02_a", "weed_plant_02_b"]

static var _cache: Dictionary = {}


static func model_path(asset: String, lod: int = 0) -> String:
	return MODEL % [asset, lod]


static func model_paths(assets: PackedStringArray, lod: int = 0) -> PackedStringArray:
	var result := PackedStringArray()
	for asset: String in assets:
		result.append(model_path(asset, lod))
	return result


static func map_files_ready() -> bool:
	for candidate: String in ["leafy", "soil"]:
		for map: String in ["albedo", "normal", "arm"]:
			if not ResourceLoader.exists(TEX % [candidate, map]):
				return false
	for assets: PackedStringArray in [BASE_ASSETS, CLUMP_ASSETS, WEED_ASSETS]:
		for asset: String in assets:
			for lod: int in range(2):
				if not ResourceLoader.exists(model_path(asset, lod)):
					return false
	return true


static func make_scatter(label: String, density: Texture2D, map_origin: Vector2, mode: String) -> DistrictGrass:
	var grass := DistrictGrass.new()
	grass.name = label
	grass.density_texture = density
	grass.origin = map_origin
	grass.build_per_frame = 8
	if mode == "current":
		grass.models = PackedStringArray(["res://assets/zone01/models/ug_grass_tall_a.glb", "res://assets/zone01/models/ug_grass_tall_b.glb",
			"res://assets/zone01/models/ug_grass_small.glb", "res://assets/zone01/models/ug_grass_mid_b.glb", "res://assets/zone01/models/ug_grass2_c.glb"])
		grass.weed_models = PackedStringArray(["res://assets/zone01/models/ug_weed_a.glb", "res://assets/zone01/models/ug_weed_b.glb",
			"res://assets/zone01/models/ug_dandelion_c.glb", "res://assets/zone01/models/ug_dandelion_e.glb"])
		grass.lawn_dryness = 0.08
		grass.tint = Color(0.66, 0.84, 0.5)
		return grass
	grass.lawn = false
	grass.lod1_models = model_paths(CLUMP_ASSETS, 1)
	grass.weed_lod1_models = model_paths(WEED_ASSETS, 1)
	grass.lod_switch_m = 9.0
	grass.lod_margin_m = 2.0
	grass.alpha_cut = 0.32
	grass.radius = 32.0
	grass.scan_dryness = 0.14
	grass.tint = Color(1.2, 1.28, 1.1)
	if mode == "base":
		grass.models = model_paths(BASE_ASSETS)
		grass.lod1_models = model_paths(BASE_ASSETS, 1)
		grass.weed_models = PackedStringArray()
		grass.weed_lod1_models = PackedStringArray()
		grass.per_m2 = 24.0
		grass.scale_range = Vector2(0.8, 1.25)
	else:
		grass.models = model_paths(CLUMP_ASSETS)
		grass.weed_models = model_paths(WEED_ASSETS)
		grass.model_weights = PackedFloat32Array([0.48, 0.44, 0.08])
		grass.per_m2 = 1.2
		grass.scale_range = Vector2(0.8, 1.2)
	return grass


static func ground_material(candidate: String, mixed: bool = false) -> Material:
	if candidate == "current":
		return StreetPaving.material("lawn", false)
	var cache_key: String = candidate + ("/mixed" if mixed else "/pure")
	if _cache.has(cache_key):
		return _cache[cache_key] as Material
	var material := ShaderMaterial.new()
	material.shader = GROUND_SHADER
	var source: String = "leafy" if candidate in ["leafy", "mixed", "mega"] else candidate
	var has_maps: bool = ResourceLoader.exists(TEX % [source, "albedo"])
	material.set_shader_parameter("use_maps", has_maps)
	if has_maps:
		for map: String in ["albedo", "normal", "arm", "height"]:
			var path: String = TEX % [source, map]
			if ResourceLoader.exists(path):
				material.set_shader_parameter(map + "_tex", load(path) as Texture2D)
		material.set_shader_parameter("has_height", ResourceLoader.exists(TEX % [source, "height"]))
	material.set_shader_parameter("tile_m", 1.4 if source == "grass001" else 2.0)
	material.set_shader_parameter("saturation", 0.76 if mixed else 0.86)
	material.set_shader_parameter("macro_var", 0.14)
	material.set_shader_parameter("normal_strength", 1.0)
	material.set_shader_parameter("parallax_scale", 0.035 if source == "leafy" else 0.022)
	material.set_shader_parameter("tint", Color(0.5, 0.62, 0.64) if source == "leafy" else Color(0.8, 0.75, 0.85))
	if mixed:
		material.set_shader_parameter("tint", Color(0.48, 0.6, 0.62))
		material.set_shader_parameter("soil_amount", 0.28)
		var soil_ready: bool = ResourceLoader.exists(TEX % ["soil", "albedo"])
		material.set_shader_parameter("use_soil", soil_ready)
		if soil_ready:
			for map: String in ["albedo", "normal", "arm"]:
				material.set_shader_parameter("soil_" + map + "_tex", load(TEX % ["soil", map]) as Texture2D)
	_cache[cache_key] = material
	return material
