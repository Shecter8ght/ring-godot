shader_type spatial;
render_mode cull_disabled;
// Стоячая и медленная мутная вода: болото и ручей в овраге зоны 1. Зеленоватая взвесь, рябь шумом,
// отражения неба — от движка (SSR/небо), без прозрачности (глубину всё равно не видно, и так дешевле).
// Болото (владелец 2026-10-18: брод по пояс, «нормальный вид воды, но чтобы компьютер не улетел»):
// по карте глубины у берега мелко и мутно (ил просвечивает), на глубине тёмная гладь; пятна ряски;
// в дождь — круги от капель (rain — от RaidWeather через WaterBody.set_rain; сырость без дождя их не рисует).
// Всё — несколько выборок текстур, без прозрачности.

uniform vec3 deep_color : source_color = vec3(0.07, 0.09, 0.06);
uniform vec3 murk_color : source_color = vec3(0.18, 0.22, 0.12);
uniform float flow = 0.15;

// бесшовный шум района (R, G — разные масштабы), см. tools/build_zone01.py
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;

// глубина под гладью (R = глубина / depth_max) в прямоугольнике depth_rect (x0, z0, ширина, длина, м);
// без карты (ручей) — везде «глубоко», вид как прежде
uniform sampler2D depth_tex : filter_linear, repeat_disable, hint_default_white;
uniform vec4 depth_rect = vec4(0.0, 0.0, 1.0, 1.0);
uniform float depth_max = 1.5;
uniform vec3 mud_color : source_color = vec3(0.21, 0.18, 0.12);
// ряска: доля поверхности (0 — нет), цвет
uniform float duckweed = 0.0;
uniform vec3 weed_color : source_color = vec3(0.17, 0.25, 0.07);

// сила дождя 0..1
uniform float rain = 0.0;

// круг от капли в ячейке: смещение нормали (дождь)
vec2 drop_ring(vec2 p, float t) {
	vec2 cell = floor(p);
	vec2 f = fract(p) - 0.5;
	float h = fract(sin(dot(cell, vec2(127.1, 311.7))) * 43758.5453);
	float ph = fract(t * 0.9 + h);
	float r = length(f);
	float front = ph * 0.48;
	float ring = sin((r - front) * 48.0) * smoothstep(0.07, 0.0, abs(r - front)) * (1.0 - ph);
	return f / max(r, 0.001) * ring;
}

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 p = wp.xz / 9.0 + vec2(TIME * flow, TIME * flow * 0.6) * 0.1;
	vec2 q = wp.xz / 4.0 - vec2(TIME * flow * 0.07, TIME * flow * 0.13);
	float e = 0.004;
	float n1 = texture(noise_tex, p).a + texture(noise_tex, q).b * 0.5;
	float nx = texture(noise_tex, p + vec2(e, 0.0)).a + texture(noise_tex, q + vec2(e, 0.0)).b * 0.5;
	float nz = texture(noise_tex, p + vec2(0.0, e)).a + texture(noise_tex, q + vec2(0.0, e)).b * 0.5;
	vec2 slope = vec2(n1 - nx, n1 - nz) * 6.0;

	float d = texture(depth_tex, (wp.xz - depth_rect.xy) / depth_rect.zw).r * depth_max;
	float shallow = 1.0 - smoothstep(0.0, 0.45, d);
	// ряска пятнами (≈ шестая часть глади при duckweed 0,25), гуще у берега — открытая вода остаётся тёмной
	float wn = texture(noise_tex, wp.xz / 26.0).g * 0.65 + texture(noise_tex, wp.xz / 6.0).r * 0.35;
	float weed = duckweed > 0.0 ? smoothstep(0.72 - duckweed * 0.3 - shallow * 0.1, 0.76 - duckweed * 0.3 - shallow * 0.1, wn) : 0.0;
	// дождь: круги от капель в двух сдвинутых сетках
	if (rain > 0.01) {
		vec2 rings = drop_ring(wp.xz * 1.6, TIME) + drop_ring(wp.xz * 1.6 + vec2(0.5, 0.31), TIME + 0.43);
		slope += rings * rain * 0.9;
	}
	slope *= 1.0 - weed * 0.85;
	NORMAL_MAP = normalize(vec3(slope.x + 0.5, slope.y + 0.5, 1.0));
	NORMAL_MAP_DEPTH = 0.4;
	float murk = texture(noise_tex, wp.xz / 60.0).r;
	vec3 water = mix(deep_color, murk_color, murk * 0.6);
	water = mix(water, mud_color, shallow * 0.75);
	ALBEDO = mix(water, weed_color * (0.8 + 0.4 * wn), weed);
	ROUGHNESS = mix(mix(0.06, 0.24, shallow), 0.85, weed);
	METALLIC = 0.0;
	SPECULAR = mix(0.5, 0.25, weed);
}
