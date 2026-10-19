class_name WeaponCondition
extends RefCounted
## Непрерывный ресурс экземпляра; внешний вид по прочности и отказ на нуле.
## Износ установленного обвеса не зависит от ресурса самого оружия.

## Износ шейдером по маске <карты>_wear.png (новые стволы и обвесы — одно состояние 100 %).
const WEAR_SHADER: String = "res://src/combat/weapon_wear.gdshader"
## Общие детальные тайлы износа (tools/gen_weapon_wear_tiles.py).
const WEAR_DETAIL: String = "res://assets/textures/weapon_wear/wear_detail.png"

static var _materials: Dictionary = {}

static func supported(id: String) -> bool:
	return WeaponDb.is_weapon(id) or not WeaponDb.attachment(id).is_empty()


static func percent(entry: Dictionary) -> float:
	return clampf(float(entry.get("dur", Balance.CONDITION.full)), 0.0, float(Balance.CONDITION.full))


static func broken(entry: Dictionary) -> bool:
	return percent(entry) <= 0.0


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


## Ресурс не входит в ключ целиком: выстрел не должен заново создавать модель/анимацию.
static func model_key(id: String, mods: Dictionary, dur: float = 100.0, mag: String = "*") -> String:
	var parts: Array[String] = [id, str(stage({"dur": dur})), "mag:" + mag]
	for mount: Variant in mods:
		var rec: Dictionary = mod_entry(mods[mount])
		parts.append("%s:%s:%d" % [mount, rec.id, stage(rec)])
		# Паз, сторона и поворот меняют геометрию сборки; фонарь, ЛЦУ и кратность — её состояние.
		for placement: String in ["slot", "flip", "angle"]:
			if rec.has(placement):
				parts.append("%s=%s" % [placement, str(rec[placement])])
	return "|".join(parts)


## Вид по прочности; руки и обвесы отдельно. Порядок: у материалов есть маска износа — шейдер (плавно при
## любой прочности); у оружия ручные карты состояний (weapon.state_maps: ПМ, для сравнения) — они; иначе общий налёт.
static func apply_visual(root: Node3D, entry: Dictionary) -> void:
	if root.get_meta("wear_shader", false):
		update_wear(root, percent(entry))
		return
	var visual: int = stage(entry)
	if int(root.get_meta("condition_visual", -1)) == visual:
		return
	root.set_meta("condition_visual", visual)
	var shaded: bool = _apply_wear_shader(root)
	# обвесы с маской (WeaponMods._model_part) несут свой ресурс — в общий список, чтобы обновлять без пересборки
	var meshes: Array[GeometryInstance3D] = []
	for raw: Node in root.find_children("*", "GeometryInstance3D", true, false):
		if raw.has_meta("wear_k"):
			meshes.append(raw as GeometryInstance3D)
	if not meshes.is_empty():
		root.set_meta("wear_meshes", meshes)
	if shaded:
		root.set_meta("wear_shader", true)
		update_wear(root, percent(entry))
		return
	# у модели свои карты износа (weapon.state_maps) — общий налёт не нужен
	var maps: String = String(WeaponDb.weapon(String(entry.get("id", ""))).get("state_maps", ""))
	if maps != "" and visual < int(Balance.CONDITION.full) and _apply_state_maps(root, maps, visual):
		return
	var amount: float = float(Balance.CONDITION.grime_worn if visual == int(Balance.CONDITION.worn) else Balance.CONDITION.grime_used) if visual < int(Balance.CONDITION.full) else 0.0
	if amount <= 0.0:
		return
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		var parent: Node = mesh
		var skip: bool = false
		while parent != null and parent != root:
			if parent.has_meta("condition_part") or String(parent.name).contains("Arms"):
				skip = true
				break
			parent = parent.get_parent()
		if skip or mesh.has_meta("reticle_dot") or mesh.mesh == null:
			continue
		for surface: int in range(mesh.mesh.get_surface_count()):
			var material: Material = mesh.get_active_material(surface)
			if material is StandardMaterial3D:
				var source: StandardMaterial3D = material as StandardMaterial3D
				if source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED or source.emission_enabled:
					continue
				var key: String = "%d:%d" % [source.get_instance_id(), visual]
				if not _materials.has(key):
					if _materials.size() >= int(Balance.CONDITION.cache_entries):
						_materials.clear()
					var worn: StandardMaterial3D = source.duplicate() as StandardMaterial3D
					worn.albedo_color = source.albedo_color.lerp(Color(0.24, 0.22, 0.19, source.albedo_color.a), amount)
					worn.roughness = lerpf(source.roughness, 0.92, amount)
					_materials[key] = worn
				# Глобальный override имеет приоритет над поверхностями процедурной модели.
				if mesh.material_override != null:
					mesh.material_override = _materials[key] as Material
					break
				mesh.set_surface_override_material(surface, _materials[key] as Material)


## Прочность в шейдер износа без пересборки модели (ресурс меняется с каждым выстрелом): тело — по ресурсу
## оружия dur (проценты), обвес с маской — по своему из mods. Значение уходит, только когда изменилось.
static func update_wear(root: Node3D, dur: float, mods: Dictionary = {}) -> void:
	if root == null or not root.has_meta("wear_meshes"):
		return
	var body: float = clampf(dur, 0.0, float(Balance.CONDITION.full)) / float(Balance.CONDITION.full)
	for raw: Variant in root.get_meta("wear_meshes") as Array:
		if not is_instance_valid(raw):
			continue
		var mesh: GeometryInstance3D = raw as GeometryInstance3D
		var k: float = body
		var mount: String = String(mesh.get_meta("wear_mount", ""))
		if mount != "":
			if not mods.has(mount):
				continue
			k = effectiveness(mod_entry(mods[mount]))
		if absf(float(mesh.get_meta("wear_k", -1.0)) - k) > 0.0001:
			mesh.set_meta("wear_k", k)
			mesh.set_instance_shader_parameter("condition", k)


## Маска износа рядом с картами материала: <карты>_albedo.png (у обвесов <карты>_base_color.png) →
## <карты>_wear.png. Пусто — маски нет.
static func wear_mask_path(material: StandardMaterial3D) -> String:
	if material == null or material.albedo_texture == null:
		return ""
	var path: String = material.albedo_texture.resource_path
	for suffix: String in ["_albedo.png", "_base_color.png"]:
		if path.ends_with(suffix):
			var mask: String = path.trim_suffix(suffix) + "_wear.png"
			return mask if ResourceLoader.exists(mask) else ""
	return ""


## Материал шейдера износа с картами и настройками исходного StandardMaterial3D (общий на все экземпляры;
## прочность — instance uniform condition). Нет маски — null.
static func wear_material(source: StandardMaterial3D) -> ShaderMaterial:
	var key: String = "wear:%d" % source.get_instance_id()
	if _materials.has(key):
		return _materials[key] as ShaderMaterial
	var mask: String = wear_mask_path(source)
	if mask == "":
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
	material.set_shader_parameter("wear_tex", load(mask) as Texture2D)
	# жировая плёнка рук (ВЕРАС-54 v13): <карты>_coat.png рядом с маской износа — слой Clearcoat шейдера
	var coat: String = mask.trim_suffix("_wear.png") + "_coat.png"
	if ResourceLoader.exists(coat):
		material.set_shader_parameter("coat_tex", load(coat) as Texture2D)
	# свечение по карте (светонакопительные цифры магазина)
	if source.emission_enabled and source.emission_texture:
		material.set_shader_parameter("emission_tex", source.emission_texture)
		material.set_shader_parameter("emission_color", Vector3(source.emission.r, source.emission.g, source.emission.b))
		material.set_shader_parameter("emission_energy", source.emission_energy_multiplier)
	if ResourceLoader.exists(WEAR_DETAIL):
		material.set_shader_parameter("detail_tex", load(WEAR_DETAIL) as Texture2D)
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


## Шейдер износа всем поверхностям тела оружия, у чьих карт есть маска; обвесы (condition_part) — своим путём.
## false — масок нет (дальше ручные карты или налёт).
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
			if not mesh.has_meta("wear_k"):
				mesh.set_meta("wear_k", -1.0)
			done = true
	return done


## Собственные карты состояния модели: материалу «GAME • <Поверхность> • 100» из GLB ставятся цвет,
## нормали и ORM из <maps>_<Поверхность>_<состояние>_*.png (tools/veras54_game_materials.py --states).
## Обвесы и руки не трогаются. false — карт нет (остаётся общий налёт).
static func _apply_state_maps(root: Node3D, maps: String, visual: int) -> bool:
	var done: bool = false
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		var parent: Node = mesh
		var skip: bool = false
		# руки не отсекаются по имени узла: во вьюмодели оружие висит на кости рига рук, а материал рук
		# и так не «GAME • …»
		while parent != null and parent != root:
			if parent.has_meta("condition_part"):
				skip = true
				break
			parent = parent.get_parent()
		if skip or mesh.mesh == null:
			continue
		for surface: int in range(mesh.mesh.get_surface_count()):
			var source: StandardMaterial3D = mesh.mesh.surface_get_material(surface) as StandardMaterial3D
			if source == null:
				continue
			var parts: PackedStringArray = source.resource_name.split(" • ")
			if parts.size() < 3 or parts[0] != "GAME":
				continue
			var prefix: String = "%s_%s_%d_" % [maps, parts[1], visual]
			var key: String = "maps:%d:%s" % [source.get_instance_id(), prefix]
			if not _materials.has(key):
				if not ResourceLoader.exists(prefix + "albedo.png"):
					continue
				var worn: StandardMaterial3D = source.duplicate() as StandardMaterial3D
				worn.albedo_texture = load(prefix + "albedo.png") as Texture2D
				if ResourceLoader.exists(prefix + "normal.png"):
					worn.normal_texture = load(prefix + "normal.png") as Texture2D
				if ResourceLoader.exists(prefix + "orm.png"):
					var orm: Texture2D = load(prefix + "orm.png") as Texture2D
					worn.roughness_texture = orm
					worn.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
					worn.metallic_texture = orm
					worn.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
				_materials[key] = worn
			mesh.set_surface_override_material(surface, _materials[key] as Material)
			done = true
	return done
