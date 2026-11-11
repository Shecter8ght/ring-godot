extends RefCounted
## Метки звуков относительно начала и конца выбранного клипа перезарядки.

const PATH := "user://reload_audio.cfg"
const RECORDINGS := "user://reload_audio"
const CLIP_ROLES: Array[String] = ["reload", "reload_empty", "reload_fast", "reload_fast_empty"]

static var _config: ConfigFile
static var _streams: Dictionary = {}

var marks: Dictionary = {}
var _played: Dictionary = {}
var _duration: float = 0.0
var _clip_start: float = 0.0


static func mode(empty: bool, fast: bool = false) -> String:
	return CLIP_ROLES[int(empty) + 2 * int(fast)]


static func _settings() -> ConfigFile:
	if _config == null:
		_config = ConfigFile.new()
		_config.load(PATH)
	return _config


static func saved(weapon_id: String, role: String) -> Dictionary:
	var value: Variant = _settings().get_value(weapon_id, role, {})
	return (value as Dictionary).duplicate(true) if value is Dictionary else {}


static func save(weapon_id: String, role: String, value: Dictionary) -> Error:
	var config := _settings()
	var previous: Dictionary = saved(weapon_id, role)
	config.set_value(weapon_id, role, value if not value.is_empty() else null)
	var pending: String = PATH + ".tmp"
	var error: Error = config.save(pending)
	if error == OK:
		error = DirAccess.rename_absolute(ProjectSettings.globalize_path(pending), ProjectSettings.globalize_path(PATH))
	if error != OK:
		config.set_value(weapon_id, role, previous if not previous.is_empty() else null)
	return error


static func defaults(weapon_id: String, role: String) -> Dictionary:
	var weapon: Dictionary = WeaponDb.weapon(weapon_id)
	var rig: Dictionary = weapon.get("rig", {})
	var phases: Dictionary = rig.get("reload", {})
	if String(rig.get("mechanism", "")) == "break_action":
		return {
			"breech_open": {"at": float(phases.get("open_start", 0.1))},
			"round_insert": {"at": float(phases.get("insert_end", 0.7))},
			"breech_close": {"at": float(phases.get("close_end", 0.8))},
		}
	var result: Dictionary = {
		"mag_out": {"at": float(phases.get("mag_out", 0.0))},
		"mag_in": {"at": float(phases.get("mag_in", 1.0))},
	}
	if rig.is_empty() or role.ends_with("empty"):
		var start: float = float(phases.get("charge", 1.0))
		result.charge = {"at": start, "end": float(phases.get("charge_end", start))}
	return result


static func gain(slot: String) -> float:
	return -5.0 if slot == "charge" else -4.0


static func recording(mark: Dictionary) -> AudioStream:
	var path: String = String(mark.get("file", ""))
	if not path.begins_with(RECORDINGS + "/") or path.get_base_dir() != RECORDINGS:
		return null
	if not _streams.has(path):
		var stream: AudioStream = Audio.load_audio_file(path)
		if stream != null:
			_streams[path] = stream
	return _streams.get(path) as AudioStream


func start(weapon_id: String, role: String, duration: float, insert_only: bool = false, clip_start: float = 0.0) -> void:
	marks = saved(weapon_id, role)
	_played.clear()
	if insert_only:
		_played.mag_out = true
	_duration = duration
	_clip_start = clampf(clip_start, 0.0, 1.0)


func switch_to(weapon_id: String, role: String, remaining: float, elapsed: float) -> void:
	var fast: Dictionary = saved(weapon_id, role)
	if not fast.is_empty():
		marks = fast
		_duration = remaining
	else:
		_duration = elapsed + remaining


func due(remaining: float) -> Array[String]:
	var result: Array[String] = []
	var progress: float = 1.0 - maxf(remaining, 0.0) / maxf(_duration, 0.001)
	var fraction: float = lerpf(_clip_start, 1.0, progress)
	for slot: String in marks:
		if bool(marks[slot].get("enabled", true)) and not _played.has(slot) and fraction + 0.00001 >= float(marks[slot].at):
			_played[slot] = true
			result.append(slot)
	return result


func mark_played(slot: String) -> void:
	_played[slot] = true


func clear() -> void:
	marks.clear()
	_played.clear()
