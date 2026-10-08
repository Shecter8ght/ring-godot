shader_type spatial;
// Береста (tools/build_birch_textures.py) и тёмный трещиноватый низ ствола (ambientCG Bark001):
// у комля кора чёрная с серыми гребнями, граница рваная и поднимается пятнами; с северной
// стороны (−Z) у земли — мох. Тонкие ветви (branch = true) — тёмные, буро-серые.
// Ветер и затенение в кроне — как у ели (цвет вершин: r — затенение, g — гибкость, b — фаза).

#include "res://src/world/spruce_wind.gdshaderinc"

uniform sampler2D birch_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D birch_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D birch_arm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dark_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dark_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
// высота тёмного низа, м (0 — без него)
uniform float dark_height = 1.6;
uniform vec3 moss_color : source_color = vec3(0.19, 0.23, 0.1);
uniform float moss = 0.5;
uniform bool branch = false;
uniform vec3 branch_tint : source_color = vec3(0.34, 0.29, 0.27);
// сырость в дождь (RainFx): темнее, глаже, блестит
global uniform float rain_wet;

varying float v_h;
varying float v_ao;
varying vec3 v_wn;
varying vec3 v_lp;

void vertex() {
	v_h = VERTEX.y;
	v_lp = VERTEX;
	VERTEX = spruce_wind(VERTEX, COLOR, MODEL_MATRIX, TIME);
	v_ao = clamp(COLOR.r, 0.0, 1.0);
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 wc = texture(birch_albedo, UV).rgb;
	vec3 arm = texture(birch_arm, UV).rgb;
	vec3 nrm = texture(birch_normal, UV).rgb;
	float dark = 0.0;
	if (!branch && dark_height > 0.0) {
		// рваная граница: шум по окружности и высоте, вытянутые вверх «языки»
		float n = texture(noise_tex, vec2(UV.x * 0.37, v_h * 0.08)).b;
		float n2 = texture(noise_tex, vec2(UV.x * 1.3 + 0.2, v_h * 0.35)).a;
		float edge = dark_height * (0.55 + 0.9 * n) + (n2 - 0.5) * 0.35;
		dark = 1.0 - smoothstep(edge - 0.18, edge + 0.05, v_h);
	}
	vec3 dc = texture(dark_albedo, UV * vec2(1.0, 2.0)).rgb;
	float dl = dot(dc, vec3(0.333));
	// трещины чёрные, гребни серые
	vec3 dcol = mix(vec3(0.035, 0.033, 0.03), vec3(0.42, 0.41, 0.39), smoothstep(0.12, 0.42, dl));
	vec3 col = mix(wc, dcol, dark);
	nrm = mix(nrm, texture(dark_normal, UV * vec2(1.0, 2.0)).rgb, dark);
	float mk = moss * (1.0 - smoothstep(0.2, 1.3, v_h)) * smoothstep(-0.1, -0.7, v_wn.z) * (0.5 + 0.5 * dark);
	col = mix(col, moss_color, clamp(mk, 0.0, 0.8));
	if (branch) {
		col = wc * branch_tint;
	}
	col *= 1.0 - 0.3 * rain_wet;
	arm.g = mix(arm.g, 0.3, rain_wet);
	ALBEDO = col * mix(1.0, v_ao, 0.55);
	NORMAL_MAP = nrm;
	NORMAL_MAP_DEPTH = mix(0.8, 1.3, dark);
	ROUGHNESS = mix(arm.g, 0.95, dark);
	AO = arm.r * mix(1.0, v_ao, 0.8);
	AO_LIGHT_AFFECT = 0.2;
}
