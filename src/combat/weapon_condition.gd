class_name WeaponCondition
extends RefCounted
## Непрерывный ресурс экземпляра и отказ на нуле. Износ установленного обвеса не зависит от ресурса
## самого оружия.
## Внешний вид один (решение владельца 2026-10-19): модель всегда выглядит так, как её текстурировали
## в Blender; прочность показывается процентами и работает логикой — разброс, задержки, отказ на нуле
## (WeaponStats), тусклая марка и слабый фонарь обвеса (WeaponMods.update_condition).

## Шейдер материалов с жировыми следами рук (<карты>_coat.png): следы, свечение по карте, дождь.
const WEAR_SHADER: String = "res://src/combat/weapon_wear.gdshader"

static var _materials: Dictionary = {}

static func supported(id: String) -> bool:
	return WeaponDb.is_weapon(id) or not WeaponDb.attachment(id).is_empty()


static func percent(entry: Dictionary) -> float:
	return clampf(float(entry.get("dur", Balance.CONDITION.full)), 0.0, float(Balance.CONDITION.full))


static func broken(entry: Dictionary) -> bool:
	return percent(entry) <= 0.0


## Ступень прочности (100 / 60 / 20) — для подписи и цвета в окнах; на вид модели не влияет.
static func stage(entry: Dictionary) -> int:
	var dur: float = percent(entry)
	if dur <= float(Balance.CONDITION.worn):
		return int(Balance.CONDITION.worn)
	if dur <= float(Balance.CONDITION.used):
		return int(Balance.CONDITION.used)
	return int(Balance.CONDITION.full)


static func mod_entry(value: Variant) -> Dictionary:
	var entry: Dictionary = value.duplicate(true) if value is Dictionary else {"id": String(value)}
	entry["id"] = WeaponDb.mod_id(value)
	entry["dur"] = percent(entry)
	entry["n"] = 1
	return entry


static func normalize(entry: Dictionary) -> Dictionary:
	var out: Dictionary = entry.duplicate(true)
	if supported(String(out.get("id", ""))):
		out["dur"] = percent(out)
		out["n"] = 1
	if WeaponDb.is_weapon(String(out.get("id", ""))):
		var mods: Dictionary = out.get("mods", {})
		for mount: Variant in mods:
			mods[mount] = mod_entry(mods[mount])
		out["mods"] = mods
	return out


static func effectiveness(entry: Dictionary) -> float:
	return percent(entry) / float(Balance.CONDITION.full)


## Один согласованный с хостом выстрел: тело оружия и независимый ресурс обвесов.
static func wear_shots(entry: Dictionary, shots: int) -> void:
	if shots <= 0:
		return
	var stats: Dictionary = WeaponDb.weapon(String(entry.id)).get("stats", {})
	entry["dur"] = maxf(0.0, percent(entry) - float(stats.get("wear", Balance.CONDITION.weapon_wear)) * shots)
	var mods: Dictionary = entry.get("mods", {})
	for mount: Variant in mods:
		var rec: Dictionary = mod_entry(mods[mount])
		var attachment: Dictionary = WeaponDb.attachment(String(rec.id))
		var kind: String = String(attachment.get("type", ""))
		var rates: Dictionary = Balance.CONDITION.shot_wear
		var rate: float = float(rates.get(kind, Balance.CONDITION.mod_wear))
		rec["dur"] = maxf(0.0, percent(rec) - rate * shots)
		mods[mount] = rec
	entry["mods"] = mods


static func repair_price(entry: Dictionary) -> int:
	if not supported(String(entry.get("id", ""))) or percent(entry) >= float(Balance.CONDITION.full):
		return 0
	var factor: float = float(Balance.CONDITION.repair_weapon if WeaponDb.is_weapon(String(entry.id)) else Balance.CONDITION.repair_mod)
	return maxi(int(Balance.CONDITION.repair_min), ceili(ItemDb.value(String(entry.id)) * factor * (1.0 - effectiveness(entry))))


## Ключ модели: основа, магазин и обвесы с их местом. Прочности в нём нет — вид один, выстрел и износ модель не
## пересобирают; _dur остался в подписи ради прежних вызовов.
static func model_key(id: String, mods: Dictionary, _dur: float = 100.0, mag: String = "*") -> String:
	var parts: Array[String] = [id, "mag:" + mag]
	for mount: Variant in mods:
		var rec: Dictionary = mod_entry(mods[mount])
		parts.append("%s:%s" % [mount, rec.id])
		# Паз, сторона и поворот меняют геометрию сборки; фонарь, ЛЦУ и кратность — её состояние.
		for placement: String in ["slot", "flip", "angle"]:
			if rec.has(placement):
				parts.append("%s=%s" % [placement, str(rec[placement])])
	return "|".join(parts)


## Материалы модели с жировыми следами рук — на шейдер следов; руки и обвесы (condition_part) отдельно.
## Повторный вызов на той же модели ничего не делает (meta wear_shader — был ли шейдер).
static func apply_visual(root: Node3D) -> void:
	if root.has_meta("wear_shader"):
		return
	root.set_meta("wear_shader", _apply_wear_shader(root))


## Карта рядом с картой цвета материала: <карты>_albedo.png / <карты>_base_color.png → <карты><suffix>.
## Пусто — файла нет.
static func _beside(material: StandardMaterial3D, suffix: String) -> String:
	if material == null or material.albedo_texture == null:
		return ""
	var path: String = material.albedo_texture.resource_path
	for color: String in ["_albedo.png", "_base_color.png"]:
		if path.ends_with(color):
			var found: String = path.trim_suffix(color) + suffix
			return found if ResourceLoader.exists(found) else ""
	return ""


## Материал шейдера следов с картами и настройками исходного StandardMaterial3D (общий на все экземпляры).
## Нужна карта жировых следов <карты>_coat.png; нет её — null (остаётся StandardMaterial3D модели).
static func wear_material(source: StandardMaterial3D) -> ShaderMaterial:
	var key: String = "wear:%d" % source.get_instance_id()
	if _materials.has(key):
		return _materials[key] as ShaderMaterial
	# жировые следы рук (ВЕРАС-54 v13)
	var coat: String = _beside(source, "_coat.png")
	if coat == "":
		return null
	if _materials.size() >= int(Balance.CONDITION.cache_entries):
		_materials.clear()
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = load(WEAR_SHADER) as Shader
	material.resource_name = source.resource_name
	material.set_shader_parameter("albedo_color", source.albedo_color)
	material.set_shader_parameter("albedo_tex", source.albedo_texture)
	if source.normal_enabled and source.normal_texture:
		material.set_shader_parameter("normal_tex", source.normal_texture)
		material.set_shader_parameter("normal_scale", source.normal_scale)
	if source.roughness_texture:
		material.set_shader_parameter("roughness_tex", source.roughness_texture)
		material.set_shader_parameter("roughness_channel", _channel(source.roughness_texture_channel))
	material.set_shader_parameter("roughness", source.roughness)
	if source.metallic_texture:
		material.set_shader_parameter("metallic_tex", source.metallic_texture)
		material.set_shader_parameter("metallic_channel", _channel(source.metallic_texture_channel))
	material.set_shader_parameter("metallic", source.metallic)
	material.set_shader_parameter("specular", source.metallic_specular)
	if source.ao_enabled and source.ao_texture:
		material.set_shader_parameter("ao_tex", source.ao_texture)
		material.set_shader_parameter("ao_channel", _channel(source.ao_texture_channel))
		material.set_shader_parameter("ao_light_affect", source.ao_light_affect)
	material.set_shader_parameter("uv1_scale", source.uv1_scale)
	material.set_shader_parameter("uv1_offset", source.uv1_offset)
	material.set_shader_parameter("coat_tex", load(coat) as Texture2D)
	# свечение по карте (светонакопительные цифры магазина)
	if source.emission_enabled and source.emission_texture:
		material.set_shader_parameter("emission_tex", source.emission_texture)
		material.set_shader_parameter("emission_color", Vector3(source.emission.r, source.emission.g, source.emission.b))
		material.set_shader_parameter("emission_energy", source.emission_energy_multiplier)
	_materials[key] = material
	return material


static func _channel(channel: BaseMaterial3D.TextureChannel) -> Vector4:
	match channel:
		BaseMaterial3D.TEXTURE_CHANNEL_RED:
			return Vector4(1, 0, 0, 0)
		BaseMaterial3D.TEXTURE_CHANNEL_GREEN:
			return Vector4(0, 1, 0, 0)
		BaseMaterial3D.TEXTURE_CHANNEL_BLUE:
			return Vector4(0, 0, 1, 0)
		BaseMaterial3D.TEXTURE_CHANNEL_ALPHA:
			return Vector4(0, 0, 0, 1)
	return Vector4(0.333333, 0.333333, 0.333333, 0)


## Шейдер следов всем поверхностям тела оружия, у чьих карт есть жировые следы; обвесы (condition_part) —
## своим путём. false — следов нет ни у одной поверхности.
static func _apply_wear_shader(root: Node3D) -> bool:
	var done: bool = false
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		var parent: Node = mesh
		var skip: bool = false
		while parent != null and parent != root:
			if parent.has_meta("condition_part"):
				skip = true
				break
			parent = parent.get_parent()
		if skip or mesh.mesh == null or mesh.material_override != null:
			continue
		for surface: int in range(mesh.mesh.get_surface_count()):
			var source: StandardMaterial3D = mesh.mesh.surface_get_material(surface) as StandardMaterial3D
			# свечение без карты (марки, точки прицелов) — мимо шейдера; по карте (цифры магазина) шейдер передаёт сам
			if source == null or source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED \
					or (source.emission_enabled and source.emission_texture == null):
				continue
			var material: ShaderMaterial = wear_material(source)
			if material == null:
				continue
			mesh.set_surface_override_material(surface, material)
			done = true
	return done
