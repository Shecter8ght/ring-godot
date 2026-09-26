class_name ObstructionLight
extends Node3D
## Заградительный огонь (для самолётов: «здесь высокое здание»): маленький красный фонарь,
## вокруг — мягкий ореол и тёплое пятно света на кровле и стене. Горит только в темноте
## (закат, ночь) и в тумане — днём в ясную погоду выключен. Питание своё (аккумулятор): при
## отключении света в ТЦ не гаснет. flashing — мигает (верхняя точка, как у настоящих).
## Ставится руками в сцене (Node3D с этим скриптом) или SectorBuilder по краю крыши.

@export var flashing: bool = false
@export var color: Color = Color(1.0, 0.08, 0.04)

var _lamp: MeshInstance3D
var _halo: MeshInstance3D
var _light: OmniLight3D
var _t: float = 0.0
## Плавный уровень 0..1 и решение общей системы (RaidWeather.beacons_wanted), проверяется дважды в секунду.
var _k: float = 0.0
var _want: bool = false
var _check_t: float = 0.0
var _shown: float = -1.0

const HALO_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;
uniform vec4 color : source_color;
uniform float power = 1.0;
void vertex() {
	// всегда лицом к камере
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
}
void fragment() {
	float r = length(UV * 2.0 - 1.0);
	// мягкое ядро + широкий ореол: так «светится воздух» вокруг фонаря
	float core = exp(-r * r * 140.0);
	float glow = exp(-r * r * 9.0) * 0.4;
	float wide = exp(-r * r * 2.2) * 0.12;
	// к краю квадрата — строго в ноль, иначе виден квадрат
	float edge = 1.0 - smoothstep(0.55, 1.0, r);
	ALBEDO = color.rgb * (core * 3.5 + glow + wide) * power * edge;
}
"""


func _ready() -> void:
	add_to_group("obstruction_lights")
	_lamp = MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.09
	sm.height = 0.18
	sm.radial_segments = 12
	sm.rings = 6
	_lamp.mesh = sm
	var lm := StandardMaterial3D.new()
	lm.albedo_color = color.darkened(0.6)
	lm.emission_enabled = true
	lm.emission = color
	lm.emission_energy_multiplier = 0.0
	_lamp.material_override = lm
	_lamp.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_lamp)
	_halo = MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2(4.5, 4.5)
	_halo.mesh = qm
	var sh := Shader.new()
	sh.code = HALO_SHADER
	var hm := ShaderMaterial.new()
	hm.shader = sh
	hm.set_shader_parameter("color", color)
	_halo.material_override = hm
	_halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_halo.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	add_child(_halo)
	_light = OmniLight3D.new()
	_light.light_color = color
	_light.omni_range = 13.0
	_light.omni_attenuation = 0.6
	_light.light_energy = 0.0
	_light.light_specular = 0.2
	_light.light_volumetric_fog_energy = 5.0
	_light.shadow_enabled = false
	# вдали источник света гаснет — остаются лампа и ореол (дёшево); вблизи он светит на кровлю и фасад
	var ol: Dictionary = Balance.OUTDOOR_LIGHTS
	_light.distance_fade_enabled = true
	_light.distance_fade_begin = float(ol.beacon_light_m)
	_light.distance_fade_length = float(ol.beacon_fade_m)
	_light.position = Vector3(0, 0.1, 0)
	add_child(_light)
	_t = randf() * 3.0
	# при появлении — сразу как есть, дальше включается и гаснет плавно
	_want = RaidWeather.beacons_wanted()
	_k = 1.0 if _want else 0.0
	visible = _want
	if _want:
		_apply(_flash())


func _process(delta: float) -> void:
	_check_t -= delta
	if _check_t <= 0.0:
		_check_t = 0.5
		_want = RaidWeather.beacons_wanted()
		_shown = -1.0
	var goal := 1.0 if _want else 0.0
	if goal == 0.0 and _k == 0.0:
		visible = false
		return
	_k = move_toward(_k, goal, delta / float(Balance.OUTDOOR_LIGHTS.fade_sec))
	visible = true
	_t += delta
	var k := _k * _flash()
	if absf(k - _shown) > 0.002:
		_shown = k
		_apply(k)


## Мигающий — вспышка раз в 1.5 с (лампа, не стробоскоп); обычный — ровно.
func _flash() -> float:
	if not flashing:
		return 1.0
	var ph := fmod(_t, 1.5) / 1.5
	return clampf(sin(ph * PI) * 1.6, 0.0, 1.0) if ph < 0.5 else 0.0


func _apply(k: float) -> void:
	var fog := RaidWeather.current.low_visibility if RaidWeather.current else String(RaidConditions.current.get("weather", "clear")) == "fog"
	(_lamp.material_override as StandardMaterial3D).emission_energy_multiplier = 6.0 * k
	# в тумане ореол шире и ярче — свет рассеивается
	var hm := _halo.material_override as ShaderMaterial
	hm.set_shader_parameter("power", k * (1.6 if fog else 1.0))
	_halo.scale = Vector3.ONE * (1.8 if fog else 1.0)
	_light.light_energy = 3.0 * k
	# на мокрой кровле, фасаде и асфальте — заметный красный блик
	_light.light_specular = lerpf(0.2, 1.0, RaidWeather.wetness())
	_light.visible = k > 0.01
