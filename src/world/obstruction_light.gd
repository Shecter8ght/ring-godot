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
var _on: bool = false

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
	_light.position = Vector3(0, 0.1, 0)
	add_child(_light)
	_t = randf() * 3.0
	_refresh()
	if RaidWeather.current:
		RaidWeather.current.changed.connect(_refresh)


## Темно или туман — горит.
func _refresh() -> void:
	var c: Dictionary = RaidConditions.current
	_on = String(c.get("time", "day")) != "day" or String(c.get("weather", "clear")) == "fog"
	visible = _on
	set_process(_on)
	if _on:
		_apply(1.0)


func _process(delta: float) -> void:
	if not flashing:
		return
	# вспышка раз в 1.5 с, плавно (лампа, не стробоскоп)
	_t += delta
	var ph := fmod(_t, 1.5) / 1.5
	_apply(clampf(sin(ph * PI) * 1.6, 0.0, 1.0) if ph < 0.5 else 0.0)


func _apply(k: float) -> void:
	var fog := String(RaidConditions.current.get("weather", "clear")) == "fog"
	(_lamp.material_override as StandardMaterial3D).emission_energy_multiplier = 6.0 * k
	# в тумане ореол шире и ярче — свет рассеивается
	var hm := _halo.material_override as ShaderMaterial
	hm.set_shader_parameter("power", k * (1.6 if fog else 1.0))
	_halo.scale = Vector3.ONE * (1.8 if fog else 1.0)
	_light.light_energy = 3.0 * k
	_light.visible = k > 0.01
