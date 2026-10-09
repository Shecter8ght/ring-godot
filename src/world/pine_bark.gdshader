shader_type spatial;
// Кора сосны (tools/build_pine.py): снизу толстая серо-бурая плитчатая с рыжими трещинами, выше —
// тонкая оранжевая чешуйчатая («зеркало»). Доля плитчатой — альфа цвета вершин (у толстых сосен
// выше, граница неровная, «языками»). Затенение в кроне — цвет вершин r, ветер — общий с хвоей,
// у комля — мох с северной стороны (север = −Z).

#include "res://src/world/spruce_wind.gdshaderinc"

uniform sampler2D bark_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bark_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bark_arm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 plate_tint : source_color = vec3(0.86, 0.8, 0.76);
uniform float plate_saturation = 0.6;
// тонкая кора: тёмные щели и светлые оранжевые чешуйки — по яркости той же текстуры, мельче
uniform vec3 thin_dark : source_color = vec3(0.42, 0.2, 0.1);
uniform vec3 thin_light : source_color = vec3(0.94, 0.6, 0.38);
uniform float thin_scale = 1.8;
uniform float thin_normal = 0.45;
uniform vec3 moss_color : source_color = vec3(0.2, 0.25, 0.1);
uniform float moss = 0.4;
uniform float uv_scale = 1.0;
// сырость в дождь (RainFx): темнее, глаже, блестит
global uniform float rain_wet;

varying float v_h;
varying float v_ao;
varying float v_plate;
varying vec3 v_wn;

void vertex() {
	v_h = VERTEX.y;
	v_plate = clamp(COLOR.a, 0.0, 1.0);
	VERTEX = spruce_wind(VERTEX, COLOR, MODEL_MATRIX, TIME);
	v_ao = clamp(COLOR.r, 0.0, 1.0);
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec3 pc = texture(bark_albedo, uv).rgb;
	float pl = dot(pc, vec3(0.333));
	pc = mix(vec3(pl), pc, plate_saturation) * plate_tint;
	vec2 tuv = uv * vec2(thin_scale, thin_scale * 0.7);
	vec3 tc = texture(bark_albedo, tuv).rgb;
	float tl = dot(tc, vec3(0.333));
	vec3 thin = mix(thin_dark, thin_light, smoothstep(0.12, 0.5, tl));
	// плитки отслаиваются неровно: на границе — пятна рыжего среди серого
	float k = smoothstep(0.35, 0.75, v_plate + (pl - 0.35) * 0.6);
	vec3 col = mix(thin, pc, k);
	vec3 arm = mix(texture(bark_arm, tuv).rgb, texture(bark_arm, uv).rgb, k);
	vec3 n_thin = mix(vec3(0.5, 0.5, 1.0), texture(bark_normal, tuv).rgb, thin_normal);
	float mk = moss * k * (1.0 - smoothstep(0.3, 1.4, v_h)) * smoothstep(-0.1, -0.7, v_wn.z) * smoothstep(0.3, 0.55, pl);
	col = mix(col, moss_color, clamp(mk, 0.0, 0.8));
	col *= 1.0 - 0.45 * rain_wet;
	arm.g = mix(arm.g, 0.3, rain_wet);
	ALBEDO = col * mix(1.0, v_ao, 0.55);
	NORMAL_MAP = mix(n_thin, texture(bark_normal, uv).rgb, k);
	ROUGHNESS = arm.g;
	AO = arm.r * mix(1.0, v_ao, 0.8);
	AO_LIGHT_AFFECT = 0.2;
}
