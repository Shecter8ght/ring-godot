shader_type spatial;
render_mode cull_disabled;
// Стоячая и медленная мутная вода: ручей в овраге, отстойники. Зеленоватая взвесь, рябь шумом,
// отражения неба — от движка (SSR/небо), без прозрачности (глубину всё равно не видно).

uniform vec3 deep_color : source_color = vec3(0.07, 0.09, 0.06);
uniform vec3 murk_color : source_color = vec3(0.18, 0.22, 0.12);
uniform float flow = 0.15;

// бесшовный шум района (R, G — разные масштабы), см. tools/build_zone01.py
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 p = wp.xz / 9.0 + vec2(TIME * flow, TIME * flow * 0.6) * 0.1;
	vec2 q = wp.xz / 4.0 - vec2(TIME * flow * 0.07, TIME * flow * 0.13);
	float e = 0.004;
	float n1 = texture(noise_tex, p).a + texture(noise_tex, q).b * 0.5;
	float nx = texture(noise_tex, p + vec2(e, 0.0)).a + texture(noise_tex, q + vec2(e, 0.0)).b * 0.5;
	float nz = texture(noise_tex, p + vec2(0.0, e)).a + texture(noise_tex, q + vec2(0.0, e)).b * 0.5;
	NORMAL_MAP = normalize(vec3((n1 - nx) * 6.0 + 0.5, (n1 - nz) * 6.0 + 0.5, 1.0));
	NORMAL_MAP_DEPTH = 0.4;
	float murk = texture(noise_tex, wp.xz / 60.0).r;
	ALBEDO = mix(deep_color, murk_color, murk * 0.6);
	ROUGHNESS = 0.06;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
