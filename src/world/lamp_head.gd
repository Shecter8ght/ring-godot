class_name LampHead
extends Node3D
## Светильник готового фонарного столба (DistrictModel.lamp_head): свет вниз и светящееся стекло.
## Горит как StreetLamp — в сумерки и ночью, если подстанция даёт ток (Raid.switches[switch_id]),
## включается и гаснет плавно; сила, цвет, дальность — Balance.STREET_LAMP. Узел — у низа стекла.

var switch_id: String = "street_lights"

var _light: SpotLight3D
var _lens: StandardMaterial3D
var _t: float = 0.0
var _k: float = 0.0
var _want: bool = false


func _ready() -> void:
	var ls: Dictionary = Balance.STREET_LAMP
	# стекло-рассеиватель: светится само (тот же наклон 8°, что у головки «кобра»)
	_lens = StandardMaterial3D.new()
	_lens.albedo_color = Color(0.9, 0.9, 0.85)
	_lens.emission_enabled = true
	_lens.emission = Color(1.0, 0.86, 0.66)
	var glass := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(0.25, 0.01, 0.46)
	glass.mesh = bm
	glass.material_override = _lens
	glass.rotation_degrees.x = 8.0
	glass.position.y = -0.012
	glass.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(glass)
	_light = SpotLight3D.new()
	_light.name = "Light"
	_light.position.y = -0.04
	_light.rotation.x = -PI * 0.5
	_light.light_color = ls.color
	_light.spot_range = float(ls.range)
	_light.spot_angle = float(ls.angle)
	_light.spot_angle_attenuation = 0.6
	_light.light_indirect_energy = float(ls.indirect)
	_light.light_volumetric_fog_energy = float(ls.fog)
	_light.shadow_enabled = true
	_light.distance_fade_enabled = true
	_light.distance_fade_begin = float(ls.fade_begin)
	_light.distance_fade_length = 25.0
	_light.distance_fade_shadow = float(ls.shadow_m)
	add_child(_light)
	_want = is_lit()
	_k = 1.0 if _want else 0.0
	_apply_k()


func _process(delta: float) -> void:
	_t -= delta
	if _t <= 0.0:
		_t = 0.5
		_want = is_lit()
		if _k > 0.0:
			_light.light_specular = lerpf(0.5, 1.0, RaidWeather.wetness())
	var goal := 1.0 if _want else 0.0
	if _k != goal:
		_k = move_toward(_k, goal, delta / float(Balance.OUTDOOR_LIGHTS.fade_sec))
		_apply_k()


func is_lit() -> bool:
	var powered := Raid.current == null or bool(Raid.current.switches.get(switch_id, true))
	return RaidWeather.street_lights_wanted() and powered


func _apply_k() -> void:
	_light.visible = _k > 0.001
	_light.light_energy = float(Balance.STREET_LAMP.energy) * _k
	_lens.emission_energy_multiplier = float(Balance.STREET_LAMP.lens) * _k
