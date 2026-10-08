shader_type spatial;
// Кора ели: снизу — старая чешуйчатая (серо-бурая), выше old_height — гладкая серая, у комля — мох
// с северной стороны (север = −Z). Затенение в кроне — цвет вершин r, ветер — общий с хвоей.

#include "res://src/world/spruce_wind.gdshaderinc"

uniform sampler2D old_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D old_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D old_arm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D young_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D young_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D young_arm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float old_height = 7.0;
uniform vec3 old_tint : source_color = vec3(0.8, 0.74, 0.72);
uniform float old_saturation = 0.55;
uniform vec3 young_tint : source_color = vec3(0.82, 0.8, 0.78);
uniform vec3 moss_color : source_color = vec3(0.2, 0.25, 0.1);
uniform float moss = 0.55;
uniform float uv_scale = 1.0;

varying float v_h;
varying float v_ao;
varying vec3 v_wn;

void vertex() {
	v_h = VERTEX.y;
	VERTEX = spruce_wind(VERTEX, COLOR, MODEL_MATRIX, TIME);
	v_ao = clamp(COLOR.r, 0.0, 1.0);
	v_wn = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 uv = UV * uv_scale;
	float k = old_height <= 0.0 ? 1.0 : smoothstep(old_height * 0.6, old_height, v_h);
	vec3 oc = texture(old_albedo, uv).rgb;
	float ol = dot(oc, vec3(0.333));
	oc = mix(vec3(ol), oc, old_saturation) * old_tint;
	vec3 yc = texture(young_albedo, uv).rgb * young_tint;
	vec3 col = mix(oc, yc, k);
	vec3 arm = mix(texture(old_arm, uv).rgb, texture(young_arm, uv).rgb, k);
	float mk = moss * (1.0 - smoothstep(0.3, 1.6, v_h)) * smoothstep(-0.1, -0.7, v_wn.z) * smoothstep(0.35, 0.6, ol);
	col = mix(col, moss_color, clamp(mk, 0.0, 0.85));
	ALBEDO = col * mix(1.0, v_ao, 0.55);
	NORMAL_MAP = mix(texture(old_normal, uv).rgb, texture(young_normal, uv).rgb, k);
	ROUGHNESS = arm.g;
	AO = arm.r * mix(1.0, v_ao, 0.8);
	AO_LIGHT_AFFECT = 0.2;
}
