class_name RainFx
extends Node3D
## Дождь шейдерами (без частиц): капли-штрихи и брызги считаются в вершинном шейдере из
## времени и случайного сида каждой капли, привязаны к миру (идёшь — капли не едут за тобой).
## Под крышей не капает: RainOcclusion даёт высоту верхней поверхности, капля ниже неё
## отбрасывается, брызги ложатся ровно на неё. Мокрая земля — второй проход материалов пола
## (темнее, блестит, лужи с рябью от капель) только там, где открыто небу.
## В изометрии потолки не рисуются — над крышами дождь не показываем (иначе «дождь в комнате»).
## Создаёт RaidWeather.

const DROPS := 16000
const SPLASHES := 1800
## Материалы пола, на которые ложится мокрый слой (под крышей его гасит карта).
## Асфальт с текстурами мокнет сам (шейдер wet_asphalt, сырость — RaidWeather); здесь — его
## серая замена без ассетов.
const WET_MATS := ["asphalt_02", "gbf_asphalt", "concrete_floor_worn_001", "gbf_concrete", "gbf_tile"]

var occlusion: RainOcclusion
var _drops: MeshInstance3D
var _splash: MeshInstance3D
var _drop_mat: ShaderMaterial
var _splash_mat: ShaderMaterial
var _wet_mat: ShaderMaterial
var _wet_on: Array[BaseMaterial3D] = []
var _k: float = 0.0

const COMMON := """
uniform sampler2D occ_tex : filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 96.0;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;
float occ_h(vec2 xz) {
	vec2 uv = (xz - occ_center) / occ_size + 0.5;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return -1e5;
	}
	return occ_base + textureLod(occ_tex, uv, 0.0).r * occ_range;
}
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}
"""

const DROP_SHADER := """
shader_type spatial;
render_mode unshaded, world_vertex_coords, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;
#COMMON
uniform vec3 box_center = vec3(0.0);
uniform vec3 box_size = vec3(40.0, 24.0, 40.0);
uniform float amount : hint_range(0.0, 1.0) = 1.0;
uniform float speed = 10.5;
uniform vec2 wind = vec2(0.9, 0.45);
uniform float drop_len = 0.6;
uniform float drop_w = 0.011;
uniform vec4 tint : source_color = vec4(0.72, 0.76, 0.82, 0.38);
uniform float cover_cut = 100000.0;
// капля — линза: показывает то, что за ней, чуть сдвинутым и светлее; на тёмном фоне и против
// света заметна, на ровном сером небе почти пропадает (как в жизни)
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform float visibility = 1.0;
varying vec3 wpos;
varying float fade;
void vertex() {
	vec3 rnd = COLOR.rgb;
	float ph = COLOR.a;
	vec3 bmin = box_center - box_size * 0.5;
	float t = TIME + ph * 7.0;
	vec3 base = rnd * vec3(box_size.x, 64.0, box_size.z);
	base.y -= speed * t;
	base.xz += wind * t;
	vec3 p;
	p.xz = bmin.xz + mod(base.xz - bmin.xz, box_size.xz);
	p.y = bmin.y + mod(base.y - bmin.y, box_size.y);
	vec3 dir = normalize(vec3(wind.x, -speed, wind.y));
	vec3 to_cam = CAMERA_POSITION_WORLD - p;
	float dist = length(to_cam);
	vec3 side = normalize(cross(dir, to_cam));
	// толщина не растёт с расстоянием — дальние капли тонут, а не превращаются в полосы
	float w = drop_w * clamp(dist * 0.05, 1.0, 2.0);
	float l = drop_len;
	// UV.x — поперёк, UV.y — вдоль (0 — низ капли)
	VERTEX = p - dir * l * UV.y + side * (UV.x - 0.5) * w;
	wpos = VERTEX;
	vec3 q = abs(p - box_center) / (box_size * 0.5);
	fade = (1.0 - smoothstep(0.6, 1.0, max(q.x, q.z))) * (1.0 - smoothstep(0.8, 1.0, q.y));
	fade *= step(ph, amount);
	// вблизи (< 1.5 м) и вдали (> 14 м) не видно: там дождь — это дымка и брызги
	fade *= smoothstep(0.8, 1.6, dist) * (1.0 - smoothstep(7.0, 14.0, dist));
}
void fragment() {
	float h = occ_h(wpos.xz);
	if (wpos.y < h || h > cover_cut || fade <= 0.001) {
		discard;
	}
	float across = 1.0 - abs(UV.x * 2.0 - 1.0);
	float along = smoothstep(0.0, 0.3, UV.y) * (1.0 - smoothstep(0.5, 1.0, UV.y));
	vec2 suv = SCREEN_UV + vec2((UV.x - 0.5) * 0.004, 0.0);
	vec3 behind = textureLod(screen_tex, suv, 1.5).rgb;
	ALBEDO = behind * 1.12 + tint.rgb * 0.05;
	ALPHA = clamp(tint.a * visibility * fade * across * across * along, 0.0, 1.0);
}
"""

const SPLASH_SHADER := """
shader_type spatial;
render_mode unshaded, world_vertex_coords, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;
#COMMON
uniform vec3 box_center = vec3(0.0);
uniform vec2 box_size = vec2(24.0, 24.0);
uniform float amount : hint_range(0.0, 1.0) = 1.0;
uniform float rate = 2.4;
uniform vec4 tint : source_color = vec4(0.8, 0.84, 0.9, 0.5);
uniform float cover_cut = 100000.0;
uniform float scale = 1.0;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
varying float age;
varying float vis;
varying float seed;
void vertex() {
	vec3 rnd = COLOR.rgb;
	float ph = COLOR.a;
	float cyc = TIME * rate + ph * 13.0;
	float idx = floor(cyc);
	age = fract(cyc);
	vec2 jitter = hash22(vec2(idx, ph * 97.0));
	seed = hash12(vec2(idx, ph * 31.0));
	vec2 bmin = box_center.xz - box_size * 0.5;
	vec2 xz = bmin + mod(rnd.xy * box_size + jitter * box_size - bmin, box_size);
	// высота — по карте «что сверху» в самой точке и по соседям: на изломе (бордюр, склон, край
	// крыши) соседи расходятся — брызги там не ставим, иначе висят в воздухе или тонут
	float h = occ_h(xz);
	float d = 0.2;
	float hx0 = occ_h(xz - vec2(d, 0.0));
	float hx1 = occ_h(xz + vec2(d, 0.0));
	float hz0 = occ_h(xz - vec2(0.0, d));
	float hz1 = occ_h(xz + vec2(0.0, d));
	float spread = max(max(hx0, hx1), max(hz0, hz1)) - min(min(hx0, hx1), min(hz0, hz1));
	// брызги живут 12 % цикла (~50 мс), остальное — пауза
	vis = step(age, 0.12) * step(ph, amount) * step(-1e4, h) * step(h, cover_cut) * step(spread, 0.12);
	age = age / 0.12;
	// стоячий квад к камере (ось — вверх): корона из капель над точкой удара
	vec3 right = normalize(vec3(INV_VIEW_MATRIX[0].x, 0.0, INV_VIEW_MATRIX[0].z));
	float s = mix(0.035, 0.07, seed) * scale * vis;
	VERTEX = vec3(xz.x, h + 0.003, xz.y) + right * (UV.x - 0.5) * s * 2.0 + vec3(0.0, (1.0 - UV.y) * s * 1.4, 0.0);
	vec2 q = abs(xz - box_center.xz) / (box_size * 0.5);
	vis *= 1.0 - smoothstep(0.5, 1.0, max(q.x, q.y));
}
void fragment() {
	if (vis <= 0.001) {
		discard;
	}
	// капли короны: 5 брызг по дугам от центра основания, разлетаются и падают
	vec2 p = vec2(UV.x * 2.0 - 1.0, (1.0 - UV.y) * 1.4);
	float a = 0.0;
	for (int i = 0; i < 5; i++) {
		float k = float(i) / 4.0 * 2.0 - 1.0 + (hash12(vec2(seed * 91.0, float(i))) - 0.5) * 0.4;
		float sp = 0.55 + 0.45 * hash12(vec2(float(i), seed * 17.0));
		vec2 c = vec2(k * age * 0.9, (sp * age - 0.9 * age * age) * 1.6 + 0.05);
		a = max(a, 1.0 - smoothstep(0.03, 0.09, length(p - c)));
	}
	vec3 behind = textureLod(screen_tex, SCREEN_UV, 1.0).rgb;
	ALBEDO = behind * 1.25 + tint.rgb * 0.15;
	ALPHA = a * vis * tint.a * 0.7 * (1.0 - age * 0.6);
}
"""

## Мокрый слой: второй проход по материалам пола. Темнит, блестит, лужи по шуму, в лужах —
## кольца ряби от капель. Под крышей (ниже верхней поверхности карты) — ничего.
const WET_SHADER := """
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, specular_schlick_ggx;
#COMMON
uniform float amount : hint_range(0.0, 1.0) = 1.0;
uniform float puddles = 0.3;
uniform vec3 sky_tint : source_color = vec3(0.36, 0.39, 0.43);
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
varying vec3 wpos;
varying vec3 wnrm;
void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
// три октавы с поворотом — без квадратных «ступенек» у краёв луж
float fbm(vec2 p) {
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	float v = 0.0;
	float a = 0.55;
	for (int i = 0; i < 3; i++) {
		v += a * vnoise(p);
		p = rot * p * 2.03 + 11.7;
		a *= 0.45;
	}
	return v / 0.8;
}
// отражение в луже: луч от глаза, отражённый поверхностью, идёт по экрану, пока не уйдёт за
// нарисованную глубину — там и есть то, что отражается (здания, фонари). Не нашли — небо.
vec4 reflect_ss(vec3 vpos, vec3 vn, mat4 proj, mat4 inv_proj) {
	vec3 r = reflect(normalize(vpos), vn);
	float stp = 0.35;
	vec3 p = vpos;
	for (int i = 0; i < 28; i++) {
		p += r * stp;
		stp *= 1.13;
		vec4 c = proj * vec4(p, 1.0);
		if (c.w <= 0.0) {
			break;
		}
		vec2 uv = c.xy / c.w * 0.5 + 0.5;
		if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
			break;
		}
		float d = texture(depth_tex, uv).r;
		vec4 s = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
		float sz = s.z / s.w;
		if (p.z < sz && sz - p.z < 2.5 + stp) {
			// у краёв экрана — растворить, иначе видно, где отражение обрывается
			vec2 e = smoothstep(0.0, 0.08, uv) * (1.0 - smoothstep(0.92, 1.0, uv));
			return vec4(textureLod(screen_tex, uv, 0.0).rgb, e.x * e.y);
		}
	}
	return vec4(0.0);
}
// рябь: в каждой клетке 0.6 м своё кольцо со своим тактом; берём соседей, чтобы кольца не резались
vec2 ripples(vec2 p, float t) {
	vec2 g = vec2(0.0);
	vec2 cell = floor(p / 0.6);
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 c = cell + vec2(float(i), float(j));
			vec2 o = hash22(c);
			float ph = fract(t * 0.9 + hash12(c + 17.0));
			vec2 d = p - (c + o) * 0.6;
			float r = length(d);
			float rad = ph * 0.32;
			float x = (r - rad) * 38.0;
			float wave = sin(x) * exp(-x * x * 0.08) * (1.0 - ph) * (1.0 - ph);
			g += (r > 0.0001 ? d / r : vec2(0.0)) * wave;
		}
	}
	return g;
}
void fragment() {
	float h = occ_h(wpos.xz);
	float open = step(h, wpos.y + 0.2) * smoothstep(0.6, 0.85, wnrm.y);
	if (open * amount <= 0.001) {
		discard;
	}
	// лужи — во впадинах: крупный шум задаёт где, мелкий рвёт край
	float n = fbm(wpos.xz * 0.42);
	float t = 1.0 - puddles;
	float pud = smoothstep(t, t + 0.035, n) * amount;
	// у самой лужи чуть мокрее — узкая кайма, не пятна
	float damp = smoothstep(t - 0.05, t, n) * 0.5;
	vec2 rp = ripples(wpos.xz, TIME) * pud;
	vec3 n_ws = normalize(vec3(-rp.x * 0.35, 1.0, -rp.y * 0.35));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_ws, 0.0)).xyz);
	// вода отражает небо: чем площе взгляд, тем больше (Френель), поэтому лужа не «дыра»
	float fres = pow(1.0 - clamp(dot(normalize(CAMERA_POSITION_WORLD - wpos), n_ws), 0.0, 1.0), 4.0);
	vec3 refl = sky_tint * (0.6 + 0.4 * fres);
	if (pud > 0.05) {
		vec4 ss = reflect_ss(VERTEX, NORMAL, PROJECTION_MATRIX, INV_PROJECTION_MATRIX);
		refl = mix(refl, ss.rgb * 0.85, ss.a);
	}
	ALBEDO = vec3(0.02);
	EMISSION = refl * pud;
	ROUGHNESS = mix(0.36 - damp * 0.12, 0.03, pud);
	METALLIC = 0.0;
	SPECULAR = mix(0.5, 0.7, pud);
	ALPHA = open * amount * mix(0.2 + damp * 0.1, 0.72 + fres * 0.2, pud);
}
"""


## Капли на объективе — модуль RainLens (симуляция и «жидкое стекло»).
var _lens: RainLens


func _ready() -> void:
	_lens = RainLens.new()
	_lens.name = "RainLens"
	add_child(_lens)
	occlusion = RainOcclusion.new()
	occlusion.name = "RainOcclusion"
	add_child(occlusion)
	_drop_mat = _shader_mat(DROP_SHADER)
	_splash_mat = _shader_mat(SPLASH_SHADER)
	_wet_mat = _shader_mat(WET_SHADER)
	for m in [_drop_mat, _splash_mat, _wet_mat]:
		occlusion.bind(m)
	_drops = _quads("RainDrops", DROPS, _drop_mat)
	_splash = _quads("RainSplash", SPLASHES, _splash_mat)
	# мокрый асфальт под крышей сух — ему та же карта
	var asph := SectorMaterials.get_material("asphalt_02") as ShaderMaterial
	if asph:
		occlusion.bind(asph)
	for id in WET_MATS:
		for cut in [false, true]:
			var m := SectorMaterials.get_material(id, cut) as BaseMaterial3D
			if m and m.next_pass == null and not _wet_on.has(m):
				m.next_pass = _wet_mat
				_wet_on.append(m)
	# рельеф и покрытия районов (DistrictTerrain, DistrictPaving): лужи во впадинах, на земле реже
	_wet_ground = _wet_mat.duplicate() as ShaderMaterial
	_wet_ground.set_shader_parameter("puddles", 0.14)
	occlusion.bind(_wet_ground)
	_wet_ground_on.clear()
	for root: Node in get_tree().get_nodes_in_group("district_terrain"):
		for mi: Node in root.find_children("*", "MeshInstance3D", true, false):
			_add_wet((mi as MeshInstance3D).mesh.surface_get_material(0) if (mi as MeshInstance3D).mesh else null, _wet_ground)
	for n: Node in get_tree().current_scene.find_children("*", "StaticBody3D", true, false) if get_tree().current_scene else []:
		if n is DistrictPaving:
			var surf := n.get_node_or_null("_Surface") as MeshInstance3D
			if surf:
				_add_wet(surf.material_override, _wet_mat)
	set_amount(0.0)


var _wet_ground: ShaderMaterial
var _wet_ground_on: Array[Material] = []


func _add_wet(m: Material, wet: ShaderMaterial) -> void:
	if m == null or m.next_pass != null or _wet_ground_on.has(m):
		return
	m.next_pass = wet
	_wet_ground_on.append(m)


func _exit_tree() -> void:
	# карта уходит вместе с дождём — асфальт считает всё открытым (сохнет везде одинаково)
	var asph := SectorMaterials.get_material("asphalt_02") as ShaderMaterial
	if asph:
		# без карты (occ_size ~ 0) всё вне её — открыто небу
		asph.set_shader_parameter("occ_tex", null)
		asph.set_shader_parameter("occ_size", 0.0001)
	for m in _wet_on:
		if is_instance_valid(m) and m.next_pass == _wet_mat:
			m.next_pass = null
	_wet_on.clear()
	for m in _wet_ground_on:
		if is_instance_valid(m):
			m.next_pass = null
	_wet_ground_on.clear()
	RenderingServer.global_shader_parameter_set("rain_wet", 0.0)


func _shader_mat(code: String) -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = code.replace("#COMMON", COMMON)
	var m := ShaderMaterial.new()
	m.shader = sh
	return m


## Меш из n одинаковых квадов: у каждой капли свой сид в COLOR (rgb — место, a — фаза/доля).
func _quads(nm: String, n: int, mat: ShaderMaterial) -> MeshInstance3D:
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(nm)
	var verts := PackedVector3Array()
	var uvs := PackedVector2Array()
	var cols := PackedColorArray()
	var idx := PackedInt32Array()
	verts.resize(n * 4)
	uvs.resize(n * 4)
	cols.resize(n * 4)
	idx.resize(n * 6)
	var corners := [Vector2(0, 0), Vector2(1, 0), Vector2(1, 1), Vector2(0, 1)]
	for i in range(n):
		var c := Color(rng.randf(), rng.randf(), rng.randf(), rng.randf())
		for k in range(4):
			verts[i * 4 + k] = Vector3.ZERO
			uvs[i * 4 + k] = corners[k]
			cols[i * 4 + k] = c
		var b := i * 4
		var o := i * 6
		idx[o] = b
		idx[o + 1] = b + 1
		idx[o + 2] = b + 2
		idx[o + 3] = b
		idx[o + 4] = b + 2
		idx[o + 5] = b + 3
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_TEX_UV] = uvs
	arr[Mesh.ARRAY_COLOR] = cols
	arr[Mesh.ARRAY_INDEX] = idx
	var am := ArrayMesh.new()
	am.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	am.custom_aabb = AABB(Vector3(-1e4, -1e3, -1e4), Vector3(2e4, 2e3, 2e4))
	var mi := MeshInstance3D.new()
	mi.name = nm
	mi.mesh = am
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	add_child(mi)
	return mi


## Сила дождя 0..1 (плавно начинается и кончается).
func set_amount(k: float) -> void:
	_k = k
	for m in [_drop_mat, _splash_mat, _wet_mat, _wet_ground]:
		if m:
			m.set_shader_parameter("amount", k)
	# сырость поверхностей (фасады, кора, хвоя, рельеф — шейдеры карты читают глобальный rain_wet);
	# дождь пошёл в сырую погоду — не суше, чем было
	RenderingServer.global_shader_parameter_set("rain_wet", maxf(k, RaidWeather.surface_damp()))
	_drops.visible = k > 0.001
	_splash.visible = k > 0.001


## Каждый кадр: где камера и игрок, какой вид, какой свет (капли ночью темнее).
func track(me: Node3D, cam: Camera3D, first_person: bool, brightness: float, outdoor: bool = true) -> void:
	if cam == null or me == null:
		return
	# капли на объективе: под открытым небом, дождь, взгляд вверх от 45°
	_lens.step(get_process_delta_time(), _k, (-cam.global_basis.z).y, outdoor)
	var focus := me.global_position
	occlusion.follow(focus)
	var cut := 100000.0 if first_person else focus.y + 2.6
	# от первого лица верх крыши выше глаз не виден — брызги там не рисуем (просвечивали бы)
	var splash_cut := minf(cut, cam.global_position.y - 0.3)
	if first_person:
		_drop_mat.set_shader_parameter("drop_w", 0.006)
		_drop_mat.set_shader_parameter("drop_len", 0.32)
		_splash_mat.set_shader_parameter("scale", 1.0)
		_drop_mat.set_shader_parameter("box_center", cam.global_position + Vector3(0, 2.0, 0))
		_drop_mat.set_shader_parameter("box_size", Vector3(26.0, 14.0, 26.0))
		_splash_mat.set_shader_parameter("box_center", cam.global_position)
		_splash_mat.set_shader_parameter("box_size", Vector2(18.0, 18.0))
	else:
		# изометрия: камера далеко — капли толще и длиннее, брызги крупнее, иначе не видно
		_drop_mat.set_shader_parameter("drop_w", 0.02)
		_drop_mat.set_shader_parameter("drop_len", 1.1)
		_splash_mat.set_shader_parameter("scale", 2.2)
		_drop_mat.set_shader_parameter("box_center", focus + Vector3(0, 9.0, 0))
		_drop_mat.set_shader_parameter("box_size", Vector3(60.0, 22.0, 60.0))
		_splash_mat.set_shader_parameter("box_center", focus)
		_splash_mat.set_shader_parameter("box_size", Vector2(44.0, 44.0))
	_drop_mat.set_shader_parameter("cover_cut", cut)
	_splash_mat.set_shader_parameter("cover_cut", splash_cut)
	var b := clampf(brightness, 0.08, 1.0)
	_drop_mat.set_shader_parameter("tint", Color(0.72 * b, 0.76 * b, 0.82 * b, 0.2 + 0.15 * b))
	_splash_mat.set_shader_parameter("tint", Color(0.8 * b, 0.84 * b, 0.9 * b, 0.35 + 0.25 * b))
	_wet_mat.set_shader_parameter("sky_tint", Color(0.5 * b, 0.53 * b, 0.58 * b))
