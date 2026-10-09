shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

uniform sampler2D crack_map : filter_linear_mipmap;
uniform bool cracked = false;

void fragment() {
	// Исходная LensUV перенесена в первый игровой UV-канал линзы.
	float crack = cracked ? texture(crack_map, UV).r : 0.0;
	ALBEDO = mix(vec3(0.52, 0.76, 0.64), vec3(0.8), crack);
	ALPHA = 0.055 + crack * 0.65;
	ROUGHNESS = 0.035 + crack * 0.75;
	METALLIC = 0.0;
	SPECULAR = 0.3;
}
