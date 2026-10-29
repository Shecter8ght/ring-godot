// Мозаичная крошка ступеней и площадок лестницы (ambientCG Terrazzo005): серый цементный фон, затёртый до
// полуглянца, грязь пятнами — как «Ступени_мозаика» в tools/dorm_modules/texture_modules.py (шаг карты 0,5 м).

#ifndef DORM_TERRAZZO
#define DORM_TERRAZZO

uniform sampler2D terrazzo_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D terrazzo_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D terrazzo_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;

void terrazzo_layer(vec2 uv, vec4 nz, vec3 t, vec3 b, vec3 n, out vec3 color, out float rough, out vec3 nrm) {
	vec2 m = map_uv(uv);
	color = texture(terrazzo_albedo, m).rgb * rgb(141.0, 138.0, 130.0);
	float dirt = clamp((nz.g - 0.45) / 0.35, 0.0, 1.0);
	color = mix(color, color * rgb(74.0, 70.0, 62.0), dirt * 0.45);
	rough = texture(terrazzo_rough, m).r * 0.3 + dirt * 0.25 + 0.32;
	vec2 tn = nxy(texture(terrazzo_normal, m)) * 0.6;
	nrm = to_world(vec3(tn, rebuild_z(tn)), t, b, n);
}

#endif
