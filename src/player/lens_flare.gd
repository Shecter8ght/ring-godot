class_name LensFlare
extends ColorRect
## «Зайчики» объектива от ярких источников в кадре: цепочка едва заметных полупрозрачных
## восьмиугольников разного размера и оттенка с чётким краем на линии «источник → центр кадра →
## дальше» — смещаются вместе с камерой. У самого источника ничего не рисуется (ни лучей, ни ореола —
## решение владельца 2026-10-07). Источники — Light3D сцены: сила по яркости и расстоянию, у прожектора
## и фонаря — насколько он смотрит в камеру, солнце — по направлению. Источник за стеной или
## предметом (луч от глаз) — без зайчиков; появление и пропадание плавные. Рисуется поверх кадра
## (CameraLook), под интерфейсом.

const MAX_SOURCES := 6
const RESCAN_SEC := 1.0

const SHADER := """
shader_type canvas_item;
render_mode blend_add;
uniform vec4 src[6];
uniform vec4 col[6];
uniform int count = 0;
uniform float aspect = 1.7777;
uniform float strength = 0.26;
// правильный многоугольник: расстояние до края (минус — внутри)
float poly(vec2 p, float r, float n, float rot) {
	float a = atan(p.y, p.x) + rot;
	float seg = 6.2831853 / n;
	return cos(floor(0.5 + a / seg) * seg - a) * length(p) - r;
}
// положение на линии источник → центр → дальше (1 — зеркально через центр), радиус, сила, оттенок
const float GT[8] = float[](0.22, 0.4, 0.55, 0.78, 1.0, 1.18, 1.42, 1.7);
const float GR[8] = float[](0.010, 0.026, 0.016, 0.042, 0.020, 0.065, 0.03, 0.095);
const float GA[8] = float[](0.55, 0.35, 0.5, 0.26, 0.5, 0.17, 0.32, 0.11);
const vec3 GC[8] = vec3[](vec3(0.75, 0.65, 1.0), vec3(1.0, 0.72, 0.82), vec3(0.6, 0.8, 1.0), vec3(0.85, 0.7, 1.0),
	vec3(1.0, 0.86, 0.62), vec3(0.72, 0.66, 1.0), vec3(0.62, 1.0, 0.82), vec3(0.82, 0.72, 1.0));
void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 acc = vec3(0.0);
	for (int s = 0; s < 6; s++) {
		if (s >= count) {
			break;
		}
		vec2 S = src[s].xy;
		float I = src[s].z;
		vec3 C = mix(col[s].rgb, vec3(1.0), 0.5);
		vec2 axis = (vec2(0.5) - S) * 2.0;
		for (int g = 0; g < 8; g++) {
			vec2 P = S + axis * GT[g];
			float sd = poly((uv - P) * vec2(aspect, 1.0), GR[g], 8.0, 0.3);
			float fill = 1.0 - smoothstep(-0.0025, 0.0025, sd);
			float edge = 1.0 - smoothstep(0.0, 0.0035, abs(sd));
			float toward_rim = smoothstep(-GR[g], 0.0, sd);
			acc += GC[g] * C * (fill * (0.35 + 0.65 * toward_rim) + edge * 0.5) * GA[g] * I * strength;
		}
	}
	COLOR = vec4(acc, 1.0);
}
"""

## Яркость источника (энергия × свет, с расстоянием), при которой зайчики полные.
var reference: float = 1.0
var _lights: Array[Light3D] = []
var _rescan: float = 0.0
var _vis: Dictionary = {}


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh: Shader = Shader.new()
	sh.code = SHADER
	var m: ShaderMaterial = ShaderMaterial.new()
	m.shader = sh
	material = m


func _process(delta: float) -> void:
	var m: ShaderMaterial = material as ShaderMaterial
	var cam: Camera3D = get_viewport().get_camera_3d()
	if not visible or cam == null:
		m.set_shader_parameter("count", 0)
		return
	_rescan -= delta
	if _rescan <= 0.0:
		_rescan = RESCAN_SEC
		_lights.clear()
		for n: Node in get_tree().root.find_children("*", "Light3D", true, false):
			_lights.append(n as Light3D)
	var size: Vector2 = get_viewport().get_visible_rect().size
	var eye: Vector3 = cam.global_position
	var found: Array = []
	for l: Light3D in _lights:
		if not is_instance_valid(l) or not l.is_inside_tree() or not l.is_visible_in_tree() or l.light_energy <= 0.01 or l.has_meta("own"):
			continue
		var p: Vector3
		var score: float
		var e: float = l.light_energy * maxf(l.light_color.get_luminance(), 0.2)
		if l is DirectionalLight3D:
			p = eye + l.global_basis.z * 2000.0
			score = e * 3.0
		else:
			p = l.global_position
			var dist: float = eye.distance_to(p)
			if l is SpotLight3D:
				var facing: float = (-l.global_basis.z).dot((eye - p).normalized())
				var cone: float = smoothstep(cos(deg_to_rad((l as SpotLight3D).spot_angle)), 1.0, facing)
				score = e * 4.0 * cone * cone / (1.0 + 0.02 * dist * dist)
			else:
				score = e / (1.0 + 0.12 * dist * dist)
		if score < reference * 0.03 or cam.is_position_behind(p):
			continue
		var uv: Vector2 = cam.unproject_position(p) / size
		if uv.x < -0.05 or uv.x > 1.05 or uv.y < -0.05 or uv.y > 1.05:
			continue
		found.append([score, l, p, uv])
	found.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) > float(b[0]))
	var space: PhysicsDirectSpaceState3D = cam.get_world_3d().direct_space_state
	var srcs: Array = []
	var cols: Array = []
	var seen: Dictionary = {}
	for f: Array in found.slice(0, MAX_SOURCES):
		var l: Light3D = f[1]
		var p: Vector3 = f[2]
		var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(eye, p - (p - eye).normalized() * 0.45)
		var clear: bool = space.intersect_ray(q).is_empty()
		var id: int = l.get_instance_id()
		var v: float = move_toward(float(_vis.get(id, 0.0)), 1.0 if clear else 0.0, delta * 8.0)
		seen[id] = v
		if v <= 0.001:
			continue
		var uv: Vector2 = f[3]
		srcs.append(Vector4(uv.x, uv.y, clampf(float(f[0]) / reference, 0.0, 1.0) * v, 0.0))
		cols.append(Vector4(l.light_color.r, l.light_color.g, l.light_color.b, 1.0))
	_vis = seen
	var used: int = srcs.size()
	while srcs.size() < MAX_SOURCES:
		srcs.append(Vector4.ZERO)
		cols.append(Vector4.ZERO)
	m.set_shader_parameter("src", srcs)
	m.set_shader_parameter("col", cols)
	m.set_shader_parameter("count", used)
	m.set_shader_parameter("aspect", size.x / maxf(1.0, size.y))
