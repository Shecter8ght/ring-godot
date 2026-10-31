// Ступени и площадки лестницы — гладкий бетон, затёртый и пошарпанный (владелец 2026-10-31: «не мраморная крошка»):
// Poly Haven Concrete Floor Worn 001 (CC0, assets/textures/concrete_floor_worn_001), шаг карты 2 м. Грязь пятнами по
// шуму места; проступи затёрты ногами до лёгкого блеска, подступёнки и низ — матовые.

#ifndef DORM_CONCRETE
#define DORM_CONCRETE

uniform sampler2D concrete_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D concrete_arm : filter_linear_mipmap, repeat_enable;
uniform sampler2D concrete_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;

void concrete_layer(vec2 uv, vec4 nz, bool tread, vec3 t, vec3 b, vec3 n, out vec3 color, out float rough, out vec3 nrm) {
	vec2 m = map_uv(uv);
	vec3 arm = texture(concrete_arm, m).rgb;
	// карта темновата для серого бетона клетки (среднее 86 sRGB) — светлее и чуть теплее
	color = texture(concrete_albedo, m).rgb * vec3(1.42, 1.40, 1.36);
	color *= mix(1.0, arm.r, 0.7);
	float dirt = clamp((nz.g - 0.42) / 0.35, 0.0, 1.0) * smoothstep(0.3, 0.6, nz.b);
	color = mix(color, color * rgb(92.0, 84.0, 72.0), dirt * 0.55);
	// затёртость ног — пятнами по месту, только на проступях
	float polish = tread ? smoothstep(0.35, 0.65, nz.a) * 0.18 : 0.0;
	rough = clamp(arm.g * 0.85 + 0.12 + dirt * 0.12 - polish, 0.38, 0.98);
	vec2 tn = nxy(texture(concrete_normal, m)) * 0.8;
	nrm = to_world(vec3(tn, rebuild_z(tn)), t, b, n);
}

#endif
