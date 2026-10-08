shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap;
// Хвоя ели: карточки атласа лап (tools/build_spruce.py). Нормали кроны уже направлены «наружу» —
// крона освещается как объём; здесь — затенение в глубине кроны (цвет вершин r), просвет на солнце,
// небольшая разница оттенка между деревьями, ветер. Альфа поднимается на мелких мипах — дальние
// ели не «лысеют». far = true — дальний силуэт (своя текстура, затенение уже в ней).

#include "res://src/world/spruce_wind.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform vec3 tint : source_color = vec3(1.0);
uniform float alpha_cut = 0.45;
uniform float ao_strength = 1.0;
uniform vec3 translucency : source_color = vec3(0.13, 0.16, 0.05);
uniform float variation = 0.14;
uniform bool far = false;
// сырость в дождь (RainFx): темнее, глаже, блестит
global uniform float rain_wet;

varying float v_ao;
varying vec3 v_var;

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void vertex() {
	VERTEX = spruce_wind(VERTEX, COLOR, MODEL_MATRIX, TIME);
	v_ao = far ? 1.0 : pow(clamp(COLOR.r, 0.0, 1.0), 0.6);
	vec2 o = MODEL_MATRIX[3].xz;
	v_var = vec3(1.0 + (hash(o) - 0.5) * variation, 1.0 + (hash(o + 3.1) - 0.5) * variation * 0.7,
			1.0 + (hash(o + 7.3) - 0.5) * variation);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	vec2 sz = vec2(textureSize(albedo_tex, 0));
	vec2 dx = dFdx(UV * sz);
	vec2 dy = dFdy(UV * sz);
	float mip = max(0.0, 0.5 * log2(max(dot(dx, dx), dot(dy, dy))));
	ALPHA = a.a * (1.0 + mip * 0.22);
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	ALBEDO = a.rgb * tint * v_var * mix(1.0, v_ao, ao_strength * 0.6);
	AO = mix(1.0, v_ao, ao_strength);
	AO_LIGHT_AFFECT = 0.25;
	// обратная сторона карточки освещается как лицевая (нормали кроны общие)
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = far ? 0.6 : 1.0;
	// мокрая хвоя и листья — темнее и с бликом
	ALBEDO *= 1.0 - 0.2 * rain_wet;
	ROUGHNESS = mix(0.9, 0.4, rain_wet);
	SPECULAR = mix(0.12, 0.5, rain_wet);
	BACKLIGHT = translucency * (0.4 + 0.6 * v_ao);
}
