shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back;
uniform bool optical_coating = false;
void fragment() {
	float grazing = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 5.0);
	vec3 tint = optical_coating ? vec3(0.23, 0.31, 0.38) : vec3(0.83, 0.88, 0.91);
	ALBEDO = tint;
	METALLIC = 0.0;
	ROUGHNESS = 0.02;
	SPECULAR = 0.5;
	ALPHA = (optical_coating ? 0.12 : 0.04) + 0.45 * grazing;
}
