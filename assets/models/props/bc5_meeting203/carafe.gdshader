shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, specular_schlick_ggx, shadows_disabled;

uniform sampler2D room_color : hint_screen_texture, filter_linear_mipmap, repeat_disable;

void fragment() {
	// Стенка графина преломляет фон. У кромки доля отражённого света растёт.
	vec3 n = normalize(NORMAL);
	float facing = clamp(dot(n, VIEW), 0.0, 1.0);
	float fresnel = 0.041 + 0.959 * pow(1.0 - facing, 5.0);
	vec2 displaced = clamp(SCREEN_UV + n.xy * (0.010 + fresnel * 0.007), vec2(0.0), vec2(1.0));
	vec3 transmitted = textureLod(room_color, displaced, 0.0).rgb;
	ALBEDO = vec3(0.016, 0.022, 0.026);
	ROUGHNESS = 0.078;
	SPECULAR = 0.92;
	EMISSION = transmitted * vec3(0.94, 0.98, 1.0) * (1.0 - 0.43 * fresnel);
	ALPHA = 1.0;
}