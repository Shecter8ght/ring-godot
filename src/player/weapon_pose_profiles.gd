class_name WeaponPoseProfiles
extends RefCounted
## Личные поправки к готовой позе: оси камеры, метры и градусы. Нулевые значения сохраняют
## позу из Balance/Blender. Черновик стенда отделён от сохранённых игровых настроек.

const PATH: String = "user://weapon_poses.cfg"
const POSES: Array[String] = ["hip", "ads", "low"]
const POSITION_LIMIT: Vector3 = Vector3(0.5, 0.5, 0.75)
const ROTATION_LIMIT: float = 45.0

static var storage_path: String = PATH
static var _loaded: bool = false
static var _enabled: bool = true
static var _profiles: Dictionary = {}


static func snapshot() -> Dictionary:
	_ensure()
	return _profiles.duplicate(true)


static func enabled() -> bool:
	_ensure()
	return _enabled


static func active() -> Dictionary:
	_ensure()
	return _profiles if _enabled else {}


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
	for section: String in config.get_sections():
		if section == "settings":
			continue
		for pose: String in POSES:
			put(_profiles, section, pose,
				_safe_vector(config.get_value(section, pose + "/position", Vector3.ZERO), POSITION_LIMIT),
				_safe_vector(config.get_value(section, pose + "/rotation", Vector3.ZERO), Vector3.ONE * ROTATION_LIMIT))


static func _safe_vector(value: Variant, limit: Vector3) -> Vector3:
	if not value is Vector3:
		return Vector3.ZERO
	var vector: Vector3 = value as Vector3
	if not vector.is_finite():
		return Vector3.ZERO
	return vector.clamp(-limit, limit)


static func put(profiles: Dictionary, weapon: String, pose: String, position: Vector3, rotation: Vector3) -> void:
	if weapon.is_empty() or not pose in POSES:
		return
	if not profiles.has(weapon):
		profiles[weapon] = {}
	(profiles[weapon] as Dictionary)[pose] = {
		"position": _safe_vector(position, POSITION_LIMIT),
		"rotation": _safe_vector(rotation, Vector3.ONE * ROTATION_LIMIT)}


static func values(profiles: Dictionary, weapon: String, pose: String) -> Dictionary:
	var entry: Dictionary = profiles.get(weapon, {})
	var value: Dictionary = entry.get(pose, {})
	return {"position": value.get("position", Vector3.ZERO), "rotation": value.get("rotation", Vector3.ZERO)}


static func _pose(profiles: Dictionary, weapon: String, pose: String) -> Transform3D:
	var value: Dictionary = values(profiles, weapon, pose)
	return Transform3D(Basis.from_euler((value.rotation as Vector3) * (PI / 180.0)), value.position as Vector3)


## Поправка не накапливается; поворот идёт вокруг начала оружия, перенос — по осям камеры.
static func apply(base: Transform3D, profiles: Dictionary, weapon: String, aim: float, low: float) -> Transform3D:
	if not profiles.has(weapon):
		return base
	var offset: Transform3D = _pose(profiles, weapon, "hip").interpolate_with(_pose(profiles, weapon, "ads"), clampf(aim, 0.0, 1.0))
	offset = offset.interpolate_with(_pose(profiles, weapon, "low"), clampf(low, 0.0, 1.0))
	return Transform3D(offset.basis * base.basis, base.origin + offset.origin)


static func save_profiles(profiles: Dictionary, use_in_game: bool) -> Error:
	var config: ConfigFile = ConfigFile.new()
	config.set_value("settings", "version", 1)
	config.set_value("settings", "enabled", use_in_game)
	for weapon: String in profiles:
		for pose: String in POSES:
			var value: Dictionary = values(profiles, weapon, pose)
			config.set_value(weapon, pose + "/position", value.position)
			config.set_value(weapon, pose + "/rotation", value.rotation)
	var result: Error = config.save(storage_path)
	if result == OK:
		_profiles = profiles.duplicate(true)
		_enabled = use_in_game
		_loaded = true
	return result
