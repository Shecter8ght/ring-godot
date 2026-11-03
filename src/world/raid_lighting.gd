class_name RaidLighting
extends RefCounted
## Общий свет рейдов: старые поля light/look/sky_hdri карты больше не меняют картинку.
## Новая карта получает тот же профиль при первом RaidAtmosphere.apply().

const ENVIRONMENT: String = "res://data/lighting/raid_environment.tres"
const SKY: String = "res://data/lighting/sky.json"
static var _sky: Dictionary = {}


static func prepare(we: WorldEnvironment, sun: DirectionalLight3D) -> void:
	if we and (we.environment == null or not we.environment.has_meta("shared_lighting")):
		we.environment = (load(ENVIRONMENT) as Environment).duplicate(true) as Environment
		we.environment.set_meta("shared_lighting", true)
		Settings._apply_env(we)
	if sun:
		sun.set_meta("authored_shadow", true)
		sun.shadow_enabled = true


static func sky_conf() -> Dictionary:
	if _sky.is_empty():
		var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(SKY))
		if value is Dictionary:
			_sky = value
	return _sky


static func light_conf() -> Dictionary:
	return Balance.WORLD_LIGHT.duplicate(true)


static func look() -> Dictionary:
	return {"exposure_scale_raid": Balance.lab_number("atmosphere", "adapt_scale"),
		"adapt_up": Balance.lab_number("atmosphere", "adapt_up"),
		"adapt_up_indoor": Balance.lab_number("atmosphere", "adapt_indoor")}


static func fog(weather: String) -> Dictionary:
	var conf: Dictionary = (Balance.WORLD_FOG.get(weather, Balance.DEPTH_FOG.get(weather, Balance.DEPTH_FOG.clear)) as Dictionary).duplicate()
	var distance: float = Balance.lab_number("atmosphere", "fog_distance")
	conf.begin = float(conf.begin) * distance
	conf.end = float(conf.end) * distance
	conf.curve = float(conf.curve) * Balance.lab_number("atmosphere", "fog_curve")
	return conf
