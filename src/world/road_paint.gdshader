shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Краска по покрытию «Проспекта» (StreetPaving): разметка (зебра бело-жёлтая, линии), покрытие корта.
// Лежит тонкой пластиной на 2 мм над покрытием; стёртое — дырами (ALPHA_SCISSOR), сквозь них видно покрытие.
// Два года без обновления: стёрта пятнами по колее и по краю полосы, грязь, трещины покрытия видны сквозь.
// UV — 0…1 по полосе, UV2 — размер полосы, м (у краёв стирается сильнее); у колец и дуг UV2 = 0 — без краёв.
// Зерно покрытия под краской — нормали мелкого слоя асфальта (grain), краска повторяет шероховатость.

uniform vec3 paint_color : source_color = vec3(0.9, 0.9, 0.88);
uniform float wear : hint_range(0.0, 1.0) = 0.35;
uniform float wear_m = 0.4;
uniform float dirt : hint_range(0.0, 1.0) = 0.3;
uniform vec3 dirt_color : source_color = vec3(0.36, 0.34, 0.31);
uniform float paint_rough : hint_range(0.0, 1.0) = 0.55;
uniform bool use_grain = false;
uniform sampler2D grain_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float grain_m = 2.1;
uniform float grain_k : hint_range(0.0, 1.5) = 0.8;

uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;
uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float occ_h(vec2 xz) {
	vec2 uv = (xz - occ_center) / occ_size + 0.5;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return -1e5;
	}
	return occ_base + textureLod(occ_tex, uv, 0.0).r * occ_range;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 xz = wpos.xz;
	// стирание: крупно — колея и где ходили, мелко — зерно покрытия проступает сквозь краску
	float n = vnoise(xz / wear_m) * 0.35 + vnoise(xz / wear_m * 2.7 + 3.0) * 0.2 + vnoise(xz * 70.0) * 0.3
		+ vnoise(xz * 160.0) * 0.15;
	float e = 1.0;
	if (UV2.x > 0.0) {
		vec2 d = min(UV, 1.0 - UV) * UV2;
		e = smoothstep(0.0, 0.05, min(d.x, d.y));
	}
	float keep = n - wear + (e - 1.0) * 0.25;
	ALPHA = smoothstep(-0.015, 0.015, keep);
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	vec3 alb = mix(paint_color, dirt_color, dirt * smoothstep(0.3, 0.8, vnoise(xz * 1.7 + 5.0)));
	// краска истончилась: местами просвечивает тёмное
	alb *= 0.85 + 0.15 * smoothstep(0.0, 0.25, keep);
	float rough = paint_rough;
	vec2 g = vec2(0.0);
	if (use_grain) {
		vec2 gn = texture(grain_normal, xz / grain_m).rg * 2.0 - 1.0;
		g = vec2(gn.x, -gn.y) * grain_k;
	}
	float open = step(occ_h(xz), wpos.y + 0.2);
	float film = clamp(wetness * open * 1.2, 0.0, 1.0);
	alb = mix(alb, alb * 0.75, film);
	rough = mix(rough, 0.15, film);
	ALBEDO = alb;
	ROUGHNESS = rough;
	SPECULAR = 0.5;
	vec3 nw = normalize(vec3(g.x * (1.0 - film * 0.6), 1.0, g.y * (1.0 - film * 0.6)));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
