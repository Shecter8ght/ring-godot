extends RefCounted
## Материалы берём у тех же сборщиков, что и карты. Категория шага указывается отдельно от вида.

const MallGround := preload("res://src/blockout/mall_ground.gd")
const PROSPEKT: String = "res://src/blockout/prospekt_landscape.gd"
const STREET: String = "res://src/world/street_paving.gd"


static func rows() -> Dictionary:
	var result: Dictionary = {}
	if ResourceLoader.exists(STREET):
		var street: Script = load(STREET) as Script
		var types: Dictionary = (load(PROSPEKT) as Script).get_script_constant_map()
		var paving: Dictionary = types.get("PAVING_SURFACE", {})
		var floors: Dictionary = types.get("SURFACE_BY_MAT", {})
		var row: Array[Dictionary] = []
		for entry: Array in [["road_a", "Дорожный асфальт"], ["walk_a", "Тротуар из кирпичика"],
				["plaza_ab2", "Плиты площади"], ["rubber", "Резиновая крошка"], ["court", "Корт"],
				["road_c", "Разбитый асфальт"], ["pit_floor", "Бетон паркинга"],
				["tunnel_floor", "Гранитные плиты перехода"], ["lawn", "Газон"]]:
			var id: String = entry[0]
			if not (street.get_script_constant_map().get("SURFACES", {}) as Dictionary).has(id):
				continue
			row.append({"name": entry[1], "kind": paving.get(id, floors.get(id, "grass")),
				"material": street.call("material", id, false)})
		if not row.is_empty():
			result["Проспект"] = row
	if not result.has("Проспект"):
		result["Проспект"] = [
			{"name": "Асфальт блокаута", "kind": "concrete", "material": MallGround.material("road")},
			{"name": "Мощение блокаута", "kind": "concrete", "material": MallGround.material("walk")},
		]
	result["Пригород"] = _terrain_row("res://data/sectors/zone01_mall.json", "res://src/world/district_terrain.gdshader", [
		["Газон", "grass", Color(0, 0, 0, 0)], ["Опавшая листва", "dirt", Color(0, 0, 0, 1)],
		["Грязь", "mud", Color(1, 0, 0, 0)], ["Каменистый грунт", "gravel", Color(0, 1, 0, 0)],
		["Щебень", "gravel", Color(0, 0, 1, 0)]])
	(result["Пригород"] as Array).append(_sector("Асфальт проезда", "asphalt", "asphalt_02"))
	var dam: Array[Dictionary] = _terrain_row("res://data/blockouts/heli_v05.json", "res://src/blockout/heli_terrain.gdshader", [
		["Газон", "grass", Color(0, 0, 0, 0)], ["Опавшая листва", "dirt", Color(0, 0, 0, 1)],
		["Грязь", "mud", Color(1, 0, 0, 0)], ["Камень", "gravel", Color(0, 1, 0, 0)],
		["Щебень", "gravel", Color(0, 0, 1, 0)]])
	if not dam.is_empty():
		result["Плотина"] = dam
	var mall: Array[Dictionary] = [
		_sector("Плиточный пол блокаута", "tile", "gbf_tile"),
		_sector("Бетонный пол блокаута", "concrete", "gbf_concrete"),
	]
	# Накладки MallLandscape не имеют своей коллизии, тип задаёт лежащий под ними бетон блокаута.
	for entry: Array in [["road", "Пожарный проезд"], ["parking", "Асфальт парковки"], ["pit", "Двор доков"],
			["apron", "Бетон перед доками"], ["slab", "Бетонные площадки"], ["walk", "Тротуар"],
			["plaza", "Плитка входной площади"], ["paving", "Мощение сквера"], ["gravel", "Щебень обочины"],
			["path", "Грунтовая тропа"], ["dirt", "Земля"], ["mud", "Сырая земля"],
			["field", "Пашня"], ["court", "Газон сквера"]]:
		mall.append({"name": entry[1], "kind": "concrete", "material": MallGround.material(entry[0])})
	result["ТЦ «РИНГ»"] = mall
	var sanatorium: Array[Dictionary] = _terrain_row("res://data/blockouts/sanatorium_terrain.json",
		"res://src/world/sanatorium_ground.gdshader", [
		["Газон", "grass", Color(0, 0, 0, 0)], ["Вытоптанный газон", "grass", Color(1, 0, 0, 0)],
		["Хвойная подстилка", "dirt", Color(0, 1, 0, 0)], ["Мох", "grass", Color(0, 0, 1, 0)],
		["Грунтовая тропа", "dirt", Color(0, 0, 0, 1)], ["Гранит", "gravel", Color(0, 0, 0, 0), Color(1, 0, 0, 0)],
		["Щебень", "gravel", Color(0, 0, 0, 0), Color(0, 1, 0, 0)],
		["Песок", "sand", Color(0, 0, 0, 0), Color(0, 0, 1, 0)]])
	if not sanatorium.is_empty():
		result["Санаторий"] = sanatorium
	var shelter: Array[Dictionary] = []
	for entry: Array in [["MainHub", "Главный зал"], ["Living", "Жилая комната"], ["Trader", "Торговец"],
			["Armory", "Оружейная"], ["Generator", "Генераторная"], ["Workshop", "Мастерская"],
			["Storage", "Склад"], ["NorthGallery", "Галерея"], ["Entry", "Вход"],
			["BoilerHall", "Котельный зал"], ["Sleeping", "Спальня"]]:
		var path: String = "res://levels/shelter/props/Floor_%s_00.res" % String(entry[0])
		if ResourceLoader.exists(path, "Mesh"):
			var mesh: Mesh = load(path) as Mesh
			if mesh != null and mesh.get_surface_count() > 0 and mesh.surface_get_material(0) != null:
				shelter.append({"name": entry[1], "kind": "concrete", "material": mesh.surface_get_material(0)})
	if not shelter.is_empty():
		result["Убежище"] = shelter
	return result


static func _sector(title: String, kind: String, material: String) -> Dictionary:
	return {"name": title, "kind": kind, "material": SectorMaterials.get_material(material)}


static func _terrain_row(path: String, shader_path: String, entries: Array) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if not FileAccess.file_exists(path) or not ResourceLoader.exists(shader_path):
		return out
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary or not data.get("terrain") is Dictionary:
		return out
	var terrain: Dictionary = data.terrain
	var base: ShaderMaterial = ShaderMaterial.new()
	base.shader = load(shader_path) as Shader
	for key: String in ["albedo_array", "normal_array", "arm_array", "noise"]:
		var texture: String = String((terrain.get("textures", {}) as Dictionary).get(key, ""))
		if not ResourceLoader.exists(texture):
			return out
		base.set_shader_parameter(key, load(texture))
	base.set_shader_parameter("layer_tile", PackedFloat32Array(terrain.layer_tiles))
	if terrain.has("layer_gain"):
		base.set_shader_parameter("layer_gain", PackedFloat32Array(terrain.layer_gain))
	for entry: Array in entries:
		var material: ShaderMaterial = base.duplicate() as ShaderMaterial
		material.set_shader_parameter("splat", _mask(entry[2]))
		if entry.size() > 3:
			material.set_shader_parameter("splat2", _mask(entry[3]))
		out.append({"name": entry[0], "kind": entry[1], "material": material})
	return out


static func _mask(color: Color) -> ImageTexture:
	var image: Image = Image.create_empty(1, 1, false, Image.FORMAT_RGBA8)
	image.fill(color)
	return ImageTexture.create_from_image(image)
