class_name LabTuning
extends RefCounted
## Именованные варианты стендов. Черновики действуют только пока открыт стенд;
## игра получает лишь сохранённый и явно включённый профиль. Проверки используют свой файл.

static var storage_path: String = "user://development_labs.cfg"
static var _loaded: bool = false
static var _data: Dictionary = {}
static var _preview: Dictionary = {}
static var revision: int = 0


static func defaults(domain: String) -> Dictionary:
	var result: Dictionary = {}
	for key: String in Balance.lab_rules(domain):
		result[key] = (Balance.lab_rules(domain)[key] as Array)[1]
	return result


static func sanitize(domain: String, values: Dictionary) -> Dictionary:
	var result: Dictionary = defaults(domain)
	for key: String in result:
		var rule: Array = Balance.lab_rules(domain)[key]
		var item: Variant = values.get(key, rule[1])
		if rule[1] is Color:
			if item is Color:
				var color: Color = item as Color
				if is_finite(color.r) and is_finite(color.g) and is_finite(color.b):
					result[key] = Color(clampf(color.r, 0, 1), clampf(color.g, 0, 1), clampf(color.b, 0, 1), 1)
		elif rule[1] is Array:
			if item is PackedStringArray:
				result[key] = (item as PackedStringArray).duplicate()
		elif (item is float or item is int) and is_finite(float(item)):
			result[key] = clampf(float(item), float(rule[2]), float(rule[3]))
	return result


static func _ensure() -> void:
	if _loaded:
		return
	_loaded = true
	_data = {}
	var config: ConfigFile = ConfigFile.new()
	if config.load(storage_path) != OK:
		return
	for domain: String in config.get_sections():
		if Balance.lab_rules(domain).is_empty():
			continue
		var raw: Variant = config.get_value(domain, "presets", {})
		var presets: Dictionary = {}
		if raw is Dictionary:
			for name: String in raw:
				if raw[name] is Dictionary:
					presets[name] = sanitize(domain, raw[name])
		_data[domain] = {"active": String(config.get_value(domain, "active", "Мой вариант")),
			"enabled": bool(config.get_value(domain, "enabled", false)), "presets": presets}


static func names(domain: String) -> Array:
	_ensure()
	var record: Dictionary = _data.get(domain, {})
	return (record.get("presets", {}) as Dictionary).keys()


static func active_name(domain: String) -> String:
	_ensure()
	return String((_data.get(domain, {}) as Dictionary).get("active", "Мой вариант"))


static func enabled(domain: String) -> bool:
	_ensure()
	return bool((_data.get(domain, {}) as Dictionary).get("enabled", false))


static func preset(domain: String, name: String = "") -> Dictionary:
	_ensure()
	var record: Dictionary = _data.get(domain, {})
	var presets: Dictionary = record.get("presets", {})
	return sanitize(domain, presets.get(name if not name.is_empty() else active_name(domain), {}))


static func value(domain: String, key: String) -> Variant:
	_ensure()
	# Пересборка словарей нужна только при загрузке, а не на каждом кадре/луче ИИ.
	if _preview.has(domain):
		return (_preview[domain] as Dictionary).get(key, (Balance.lab_rules(domain)[key] as Array)[1])
	var record: Dictionary = _data.get(domain, {})
	if bool(record.get("enabled", false)):
		var presets: Dictionary = record.get("presets", {})
		var selected: Dictionary = presets.get(String(record.get("active", "")), {})
		if selected.has(key):
			return selected[key]
	return (Balance.lab_rules(domain)[key] as Array)[1]


static func preview(domain: String, values: Dictionary) -> void:
	_preview[domain] = sanitize(domain, values)
	revision += 1


static func end_preview(domain: String) -> void:
	_preview.erase(domain)
	revision += 1


static func save(domain: String, name: String, values: Dictionary, apply_in_game: bool) -> Error:
	_ensure()
	name = name.strip_edges().left(60)
	if name.is_empty():
		return ERR_INVALID_PARAMETER
	var previous: Dictionary = _data.duplicate(true)
	var record: Dictionary = _data.get(domain, {"presets": {}})
	(record.presets as Dictionary)[name] = sanitize(domain, values)
	record.active = name
	record.enabled = apply_in_game
	_data[domain] = record
	var config: ConfigFile = ConfigFile.new()
	for section: String in _data:
		for key: String in ["active", "enabled", "presets"]:
			config.set_value(section, key, _data[section][key])
	var error: Error = config.save(storage_path)
	if error != OK:
		_data = previous
	revision += 1
	return error


static func reload() -> void:
	_loaded = false
	_ensure()
	revision += 1
