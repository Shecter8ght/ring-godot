class_name HandGripProfiles
extends RefCounted
## Поправки к готовому хвату от первого лица. Перенос и поворот — в осях оружия,
## пальцы — относительно исходного сгиба. Черновик стенда не попадает в игру до сохранения.

const PATH: String = "user://hand_grips.cfg"
const SIDES: Array[String] = ["Left", "Right"]
const FINGERS: Array[String] = ["Index", "Middle", "Ring", "Pinky", "Thumb"]
const POSITION_LIMIT: float = 0.2
const ROTATION_LIMIT: float = 120.0
const BEND_LIMIT: float = 100.0
const SPREAD_LIMIT: float = 45.0
const TWIST_LIMIT: float = 90.0
const JOINT_ROTATION_LIMIT: float = 180.0

static var storage_path: String = PATH
static var _loaded: bool = false
static var _enabled: bool = true
static var _profiles: Dictionary = {}


## Правая кисть общая для ствола; левая — отдельная для каждой рукоятки / устройства
## под цевьём. Смена прицела не теряет хват, а передвижение рукоятки сохраняет поправку.
static func keys(weapon: String, mods: Dictionary) -> Dictionary:
	var support: String = ""
	if String(WeaponDb.weapon(weapon).get("model", "")) != "pistol":
		var under: String = WeaponGrips._under_key(mods)
		if under != "":
			support = WeaponDb.mod_id(mods[under])
	return {"Right": weapon, "Left": weapon + ("@" + support if support != "" else "")}


static func snapshot() -> Dictionary:
	_ensure()
	return _profiles.duplicate(true)


static func active() -> Dictionary:
	_ensure()
	return _profiles if _enabled else {}


static func enabled() -> bool:
	_ensure()
	return _enabled


static func reload() -> void:
	_loaded = false
	_ensure()


static func _ensure() -> void:
	if _loaded:
		return
	_loaded = true
	_profiles = {}
	_enabled = true
	var config: ConfigFile = ConfigFile.new()
	if config.load(storage_path) != OK or int(config.get_value("settings", "version", 0)) != 1:
		return
	_enabled = bool(config.get_value("settings", "enabled", true))
	for key: String in config.get_sections():
		if key == "settings":
			continue
		for side: String in SIDES:
			var raw: Variant = config.get_value(key, side, {})
			if raw is Dictionary and not (raw as Dictionary).is_empty():
				put(_profiles, key, side, raw as Dictionary)


static func _vector(value: Variant, limit: float) -> Vector3:
	if not value is Vector3 or not (value as Vector3).is_finite():
		return Vector3.ZERO
	return (value as Vector3).clamp(Vector3.ONE * -limit, Vector3.ONE * limit)


static func _number(value: Variant, limit: float) -> float:
	if not (value is float or value is int) or not is_finite(float(value)):
		return 0.0
	return clampf(float(value), -limit, limit)


static func sanitize(value: Dictionary) -> Dictionary:
	var fingers: Dictionary = {}
	var source: Dictionary = value.get("fingers", {}) if value.get("fingers", {}) is Dictionary else {}
	for finger: String in FINGERS:
		var entry: Dictionary = source.get(finger, {}) if source.get(finger, {}) is Dictionary else {}
		var raw_turns: Array = entry.get("rotation", []) if entry.get("rotation", []) is Array else []
		var turns: Array[Vector3] = []
		for joint: int in range(3):
			turns.append(_vector(raw_turns[joint] if joint < raw_turns.size() else Vector3.ZERO, JOINT_ROTATION_LIMIT))
		fingers[finger] = {"bend": _vector(entry.get("bend"), BEND_LIMIT),
			"spread": _number(entry.get("spread"), SPREAD_LIMIT),
			"twist": _number(entry.get("twist"), TWIST_LIMIT), "rotation": turns}
	return {"position": _vector(value.get("position"), POSITION_LIMIT),
		"rotation": _vector(value.get("rotation"), ROTATION_LIMIT), "fingers": fingers}


static func values(profiles: Dictionary, key: String, side: String) -> Dictionary:
	var entry: Dictionary = profiles.get(key, {})
	return sanitize(entry.get(side, {}) as Dictionary)


static func put(profiles: Dictionary, key: String, side: String, value: Dictionary) -> void:
	if key.is_empty() or not side in SIDES:
		return
	if not profiles.has(key):
		profiles[key] = {}
	(profiles[key] as Dictionary)[side] = sanitize(value)


static func save_profiles(profiles: Dictionary, use_in_game: bool) -> Error:
	var config: ConfigFile = ConfigFile.new()
	config.set_value("settings", "version", 1)
	config.set_value("settings", "enabled", use_in_game)
	for key: String in profiles:
		for side: String in SIDES:
			if (profiles[key] as Dictionary).has(side):
				config.set_value(key, side, values(profiles, key, side))
	var result: Error = config.save(storage_path)
	if result == OK:
		_loaded = false
		_ensure()
	return result
