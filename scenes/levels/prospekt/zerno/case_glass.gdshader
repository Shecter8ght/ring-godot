shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx, cull_disabled, depth_prepass_alpha;

uniform sampler2D case_map : hint_default_black, filter_linear_mipmap, repeat_disable;

void fragment() {
	vec3 detail = texture(case_map, UV).rgb;
	float line = detail.g;
	ALBEDO = mix(vec3(0.23, 0.27, 0.26), vec3(0.71, 0.77, 0.71), line);
	ROUGHNESS = mix(0.12, 0.57, clamp(line + detail.r * 0.63, 0.0, 1.0));
	SPECULAR = 0.63;
	ALPHA = clamp(0.13 + line * 0.70 + detail.r * 0.31, 0.0, 0.92);
}

