shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

// GL-AR: weak coating tint by viewing angle; Godot has no thin-film channel.
// The reflector and LED remain visible through the 0.8 mm optical shell.
void fragment() {
	float grazing = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 5.0);
	ALBEDO = mix(vec3(0.96, 0.97, 0.97), vec3(0.53, 0.66, 0.78), grazing * 0.35);
	ALPHA = mix(0.045, 0.15, grazing);
	ROUGHNESS = 0.02;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
