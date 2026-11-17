shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, specular_schlick_ggx;

uniform sampler2D room_color : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D room_depth : hint_depth_texture, filter_nearest, repeat_disable;

void fragment() {
	// Два перехода воздух–стекло дают небольшой сдвиг фона. На фоне,
	// оказавшемся перед сосудом, оставляем исходную выборку.
	vec3 n = normalize(NORMAL);
	float facing = max(dot(n, VIEW), 0.0);
	float optical_path = 0.0028 / max(facing, 0.21);
	vec3 offset = (refract(-VIEW, n, 1.0 / 1.52) + VIEW) * optical_path;
	vec4 projected = PROJECTION_MATRIX * vec4(VERTEX + offset, 1.0);
	vec2 through = clamp(0.5 + 0.5 * projected.xy / projected.w, vec2(0.001), vec2(0.999));
	float depth = texture(room_depth, through).r;
	vec4 scene_position = INV_PROJECTION_MATRIX * vec4(through * 2.0 - 1.0, depth, 1.0);
	if (scene_position.z / scene_position.w > VERTEX.z - 0.002) {
		through = SCREEN_UV;
	}
	float fresnel = 0.0426 + 0.9574 * pow(1.0 - facing, 5.0);
	vec3 transmitted = textureLod(room_color, through, 0.15 + 0.30 * fresnel).rgb;
	vec3 absorption = exp(-vec3(6.5, 2.7, 3.5) * optical_path);
	ALBEDO = vec3(0.003);
	ROUGHNESS = 0.052;
	SPECULAR = 0.52;
	EMISSION = transmitted * absorption * (1.0 - 0.56 * fresnel);
	ALPHA = 1.0;
}
