class_name WeaponCondition
extends RefCounted
## Непрерывный ресурс экземпляра; три внешних вида и отказ на нуле.
## Износ установленного обвеса не зависит от ресурса самого оружия.

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
	return "|".join(parts)


## Общий след использования до появления собственных карт модели; руки и обвесы отдельно.
static func apply_visual(root: Node3D, entry: Dictionary) -> void:
	var visual: int = stage(entry)
	if int(root.get_meta("condition_visual", -1)) == visual:
		return
	root.set_meta("condition_visual", visual)
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
