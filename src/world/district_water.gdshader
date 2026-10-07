shader_type spatial;
render_mode cull_disabled;
// Стоячая и медленная мутная вода: ручей в овраге, отстойники. Зеленоватая взвесь, рябь шумом,
// отражения неба — от движка (SSR/небо), без прозрачности (глубину всё равно не видно).

uniform vec3 deep_color : source_color = vec3(0.07, 0.09, 0.06);
uniform vec3 murk_color : source_color = vec3(0.18, 0.22, 0.12);
uniform float flow = 0.15;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 p = wp.xz * 1.3 + vec2(TIME * flow, TIME * flow * 0.6);
	float n1 = vnoise(p);
	float n2 = vnoise(p * 2.7 - TIME * 0.2);
	vec2 slope = vec2(vnoise(p + vec2(0.1, 0.0)) - n1, vnoise(p + vec2(0.0, 0.1)) - n1) * 4.0
		+ vec2(vnoise(p * 2.7 + vec2(0.1, 0.0)) - n2, vnoise(p * 2.7 + vec2(0.0, 0.1)) - n2) * 2.0;
	NORMAL_MAP = normalize(vec3(slope * 0.5 + 0.5, 1.0));
	NORMAL_MAP_DEPTH = 0.35;
	float murk = vnoise(wp.xz * 0.15);
	ALBEDO = mix(deep_color, murk_color, murk * 0.6);
	ROUGHNESS = 0.06;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
