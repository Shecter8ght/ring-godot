shader_type spatial;
// Повреждённая панель стекла (GlassPanes): трещины, крошка и дырки — с текстуры панели (GlassCracks:
// R — трещины, G — крошка, B — дырка), у закалённого — сетка мелких кубиков по всей панели (crazed).
// Трещины блестят: нормаль — по перепаду яркости трещин. dissolve_r — закалённое осыпается волной
// от точки удара. fall — режим осколков (GlassShatter): вершины летят по своим данным, CUSTOM0 —
// центр осколка (м, оси панели), задержка, свой поворот; CUSTOM1 — скорость (м/с) и вращение (рад/с).
render_mode blend_mix, depth_draw_opaque, cull_disabled, specular_schlick_ggx;

uniform sampler2D crack_tex : filter_linear_mipmap, repeat_disable;
uniform vec2 texel = vec2(0.002);
uniform vec2 pane_size = vec2(1.0);
uniform vec2 hit_uv = vec2(0.5);
uniform float crazed = 0.0;
uniform float dissolve_r = -1.0;
uniform bool fall = false;
uniform float t = 0.0;
uniform float floor_y = -1.0;
uniform vec3 glass_tint : source_color = vec3(0.62, 0.72, 0.78);

varying vec2 puv;

mat3 axis_rotation(vec3 a, float ang) {
	float c = cos(ang);
	float s = sin(ang);
	float ic = 1.0 - c;
	return mat3(
		vec3(c + a.x * a.x * ic, a.y * a.x * ic + a.z * s, a.z * a.x * ic - a.y * s),
		vec3(a.x * a.y * ic - a.z * s, c + a.y * a.y * ic, a.z * a.y * ic + a.x * s),
		vec3(a.x * a.z * ic + a.y * s, a.y * a.z * ic - a.x * s, c + a.z * a.z * ic));
}

void vertex() {
	puv = UV;
	if (fall) {
		vec3 c = vec3(CUSTOM0.xy, 0.0);
		float te = max(0.0, t - CUSTOM0.z);
		float yaw = CUSTOM0.w * 6.2831853;
		vec3 v = CUSTOM1.xyz;
		vec3 axis = normalize(vec3(cos(yaw), 0.4, sin(yaw)));
		// когда коснётся пола: c.y + v.y·t − g·t²/2 = floor_y
		float h = max(c.y - floor_y, 0.0);
		float tl = (v.y + sqrt(v.y * v.y + 19.62 * h)) / 9.81;
		vec3 local = VERTEX - c;
		if (te < tl) {
			mat3 r = axis_rotation(axis, CUSTOM1.w * te);
			VERTEX = c + v * te + vec3(0.0, -4.905 * te * te, 0.0) + r * local;
			NORMAL = r * NORMAL;
			TANGENT = r * TANGENT;
			BINORMAL = r * BINORMAL;
		} else {
			// лёг плашмя (своя Z — вверх), чуть проехал по полу
			mat3 lie = axis_rotation(vec3(0.0, 1.0, 0.0), yaw) * mat3(vec3(1.0, 0.0, 0.0), vec3(0.0, 0.0, -1.0), vec3(0.0, 1.0, 0.0));
			vec3 land = c + v * tl;
			land.y = floor_y + 0.005;
			land += vec3(v.x, 0.0, v.z) * 0.12 * (1.0 - exp(-(te - tl) * 5.0));
			VERTEX = land + lie * local;
			NORMAL = lie * NORMAL;
			TANGENT = lie * TANGENT;
			BINORMAL = lie * BINORMAL;
		}
	}
}

float hash1(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

vec2 hash2(vec2 p) {
	return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453);
}

// Закалённое: сетка мелких кубиков (ячейки ~1,5 см); вдали — ровная матовость вместо ряби.
float craze(vec2 p) {
	vec2 g = p * 50.0;
	vec2 i = floor(g);
	float md = 8.0;
	float md2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 o = vec2(float(x), float(y));
			vec2 q = o + hash2(i + o) * 0.85 - fract(g);
			float dd = dot(q, q);
			if (dd < md) {
				md2 = md;
				md = dd;
			} else if (dd < md2) {
				md2 = dd;
			}
		}
	}
	float edge = 1.0 - smoothstep(0.02, 0.09, sqrt(md2) - sqrt(md));
	float blur = smoothstep(0.25, 0.9, fwidth(g.x));
	return mix(edge, 0.32, blur);
}

void fragment() {
	vec4 c = texture(crack_tex, puv);
	if (c.b > 0.5) {
		discard;
	}
	vec2 p = puv * pane_size;
	if (dissolve_r > 0.0) {
		float d = distance(p, hit_uv * pane_size) + (hash1(floor(p * 60.0)) - 0.5) * 0.06;
		if (d < dissolve_r) {
			discard;
		}
	}
	float cz = crazed > 0.0 ? craze(p) * crazed : 0.0;
	float k = max(max(c.r, c.g), cz);
	float rx = texture(crack_tex, puv + vec2(texel.x, 0.0)).r - texture(crack_tex, puv - vec2(texel.x, 0.0)).r;
	float ry = texture(crack_tex, puv + vec2(0.0, texel.y)).r - texture(crack_tex, puv - vec2(0.0, texel.y)).r;
	NORMAL_MAP = normalize(vec3(-rx * 0.6, ry * 0.6, 1.0)) * 0.5 + 0.5;
	ALBEDO = mix(glass_tint, vec3(0.93, 0.96, 0.98), k);
	// трещины блестят, крошка и закалённая сетка — матовые
	ROUGHNESS = mix(0.06, 0.5, max(c.g, cz));
	METALLIC = 0.1;
	SPECULAR = 0.8 + 0.2 * c.r;
	ALPHA = clamp(mix(0.22, 0.9, k), 0.0, 1.0);
}
