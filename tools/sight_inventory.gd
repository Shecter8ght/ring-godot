extends Node
## Инвентаризация текущих прицелов через игровые правила креплений и выбора добычи.
## tools/godot.cmd --headless res://tools/sight_inventory.tscn
## Обновляет docs/design/sight_inventory.json; профиль и игровые данные не меняет.

const OUT: String = "res://docs/design/sight_inventory.json"

var _issues: Array[String] = []


func _enter_tree() -> void:
	Profile.use_file("user://sight_inventory_test.json", true)


func _ready() -> void:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(WeaponDb.WEAPONS_PATH)) as Dictionary
	var trader: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/trader.json")) as Dictionary
	var loot: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/loot.json")) as Dictionary
	var devices: Dictionary = {}
	for raw_id: Variant in data.attachments:
		var id: String = String(raw_id)
		var item: Dictionary = data.attachments[id]
		var att: Dictionary = WeaponDb.attachment(id)
		if not WeaponDb.is_optic(id) and not att.has("laser"):
			continue
		var spec: Dictionary = att.get("model", {})
		var asset: String = String(spec.get("scene", att.get("asset", "")))
		var direct: Dictionary = {}
		var example: Dictionary = {}
		for weapon_id: String in WeaponDb.weapon_ids():
			var entry: Dictionary = {"id": weapon_id, "n": 1, "dur": 100.0, "mods": {}}
			var places: Array[Dictionary] = _places(entry, id)
			if places.is_empty():
				continue
			direct[weapon_id] = places
			if example.is_empty():
				var inserted: Array = WeaponBuild.insert(entry, String(places[0].key), {"id": id, "dur": 100.0}, int(places[0].first_slot))
				example = inserted[0]
		var reticle: String = String(spec.get("reticle", ""))
		var icon_exists: bool = ResourceLoader.exists("res://assets/icons/" + id + ".png")
		if not icon_exists:
			_issues.append("Нет иконки " + id)
		if reticle != "" and not ResourceLoader.exists(reticle):
			_issues.append("Нет сетки " + reticle)
		devices[id] = {
			"name": item.name, "type": att.type, "fits": att.get("fits", []), "role": att.get("role", ""),
			"zoom": att.get("zoom", 0), "zoom_min": att.get("zoom_min", att.get("zoom", 0)),
			"zoom_max": att.get("zoom_max", att.get("zoom", 0)), "weight_kg": item.weight,
			"tier": item.tier, "catalog": (trader.catalog as Dictionary).get(id, 0),
			"in_stock": id in trader.stock, "buy_price": Profile.buy_price(id), "effects": att.get("fx", {}),
			"laser": att.get("laser", {}), "aim_k": att.get("aim_k", 1.0), "clamp_m": att.get("clamp_m", 0.0),
			"blocks": att.get("blocks", []), "asset": asset, "resource": _resource(asset),
			"icon_exists": icon_exists,
			"reticle": reticle, "reticle_exists": reticle != "" and ResourceLoader.exists(reticle),
			"illumination": bool(spec.get("illum", false)), "loot": _loot_sources(id, loot),
			"direct": direct, "example": _example(example)
		}
	var adapters: Dictionary = {}
	for raw_id: Variant in data.attachments:
		var id: String = String(raw_id)
		var att: Dictionary = WeaponDb.attachment(id)
		if (att.get("provides", {}) as Dictionary).is_empty():
			continue
		var host: String = "wpn_hg_01" if id == "mount_pm_k1" else "wpn_ar_01"
		var entry: Dictionary = {"id": host, "n": 1, "dur": 100.0, "mods": {}}
		var place: Dictionary = WeaponBuild.free_place(entry, id)
		var children: Dictionary = {}
		var rejected: Dictionary = {}
		if not place.is_empty():
			entry = WeaponBuild.insert(entry, String(place.key), {"id": id, "dur": 100.0}, int(place.slot))[0]
			for device_id: String in devices:
				var key: String = String(place.key) + "/rail"
				var slots: Array[int] = WeaponBuild.valid_slots(entry, key, device_id)
				if slots.is_empty():
					rejected[device_id] = WeaponBuild.block(entry, key, device_id)
					continue
				children[device_id] = {"key": key, "first_slot": slots[0], "slot_count": slots.size()}
				if (devices[device_id].example as Dictionary).is_empty():
					var child: Dictionary = WeaponBuild.insert(entry, key, {"id": device_id, "dur": 100.0}, slots[0])[0]
					devices[device_id].example = _example(child)
		var asset: String = String(att.get("asset", ""))
		adapters[id] = {"name": (data.attachments[id] as Dictionary).name, "host": host,
			"catalog": (trader.catalog as Dictionary).get(id, 0), "in_stock": id in trader.stock,
			"asset": asset, "resource": _resource(asset), "children": children, "rejected": rejected}
	for id: String in devices:
		if (devices[id].example as Dictionary).is_empty():
			_issues.append("Не найдена сборка для " + id)
	var weapons: Dictionary = {}
	for id: String in WeaponDb.weapon_ids():
		var weapon: Dictionary = WeaponDb.weapon(id)
		var model: Node3D = WeaponModels.build(id)
		weapons[id] = {"name": ItemDb.item_name(id), "model": weapon.model, "asset": weapon.get("asset", ""),
			"asset_loaded": bool(model.get_meta("asset_loaded", false)) or model is WeaponRig,
			"sight_line": model.has_meta("sight_h"), "ocular": model.has_meta("ocular"),
			"integral": weapon.get("integral", {}), "mounts": WeaponDb.mounts_of(id)}
		model.free()
	var result: Dictionary = {"schema": 1, "devices": devices, "adapters": adapters, "weapons": weapons, "issues": _issues}
	var file: FileAccess = FileAccess.open(OUT, FileAccess.WRITE)
	if file == null:
		push_error("Не удалось записать " + OUT)
		get_tree().quit(1)
		return
	file.store_string(JSON.stringify(result, "\t") + "\n")
	file.close()
	print("sight_inventory: устройств %d, переходников %d, оружия %d, ошибок ресурсов %d" % [devices.size(), adapters.size(), weapons.size(), _issues.size()])
	for issue: String in _issues:
		print("  ", issue)
	get_tree().quit(0 if _issues.is_empty() else 1)


func _places(entry: Dictionary, id: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for key: String in WeaponBuild.candidate_keys(entry, id):
		if WeaponBuild.leaf(key).contains(WeaponBuild.MULTI):
			continue
		var slots: Array[int] = WeaponBuild.valid_slots(entry, key, id)
		if not slots.is_empty():
			out.append({"key": key, "first_slot": slots[0], "slot_count": slots.size()})
	return out


func _loot_sources(id: String, loot: Dictionary) -> Array[String]:
	var out: Array[String] = []
	for table_id: String in loot.tables:
		for row: Array in (loot.tables[table_id] as Dictionary).get("entries", []):
			var query: String = String(row[0])
			if query == id:
				out.append(table_id)
			elif query.begins_with("pick:"):
				for match_row: Array in WeaponDb.matching(query.trim_prefix("pick:")):
					if String(match_row[0]) == id and not table_id in out:
						out.append(table_id)
	return out


func _resource(path: String) -> Dictionary:
	if path == "":
		return {"kind": "procedural"}
	var exists: bool = ResourceLoader.exists(path)
	var scene: PackedScene = load(path) as PackedScene if exists else null
	var valid: bool = scene != null and scene.can_instantiate()
	if not valid:
		_issues.append("Не загружается модель " + path)
	return {"kind": "asset", "exists": exists, "loadable": valid}


func _example(entry: Dictionary) -> Dictionary:
	if entry.is_empty():
		return {}
	var model: Node3D = WeaponModels.build(String(entry.id), entry.mods)
	var stats: Dictionary = WeaponStats.compute(entry)
	var out: Dictionary = {"weapon": entry.id, "mods": entry.mods, "sight_line": model.has_meta("sight_h"),
		"ocular": model.has_meta("ocular"), "scoped": stats.scoped, "zoom": stats.zoom,
		"reticle": model.get_meta("reticle_tex", ""), "mesh_count": model.find_children("*", "MeshInstance3D", true, false).size()}
	if not bool(out.sight_line) or int(out.mesh_count) == 0 or (bool(out.scoped) and not bool(out.ocular)):
		_issues.append("Неполная модель прицела в сборке " + str(entry))
	model.free()
	return out
