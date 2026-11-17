shader_type spatial;

uniform sampler2D scan_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D finish_variation : filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 tint : source_color = vec4(0.71, 0.68, 0.63, 1.0);
uniform float is_floor = 0.0;

varying vec3 position_m;

void vertex() {
	position_m = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 scan = texture(scan_color, UV).rgb;
	float variation = texture(finish_variation, UV).r;
	float abrasion = texture(finish_variation, UV * 0.37 + vec2(0.21, 0.09)).r;
	float base_dirt = (1.0 - smoothstep(0.04, 0.62, position_m.y + 4.20)) * (1.0 - is_floor);
	float entrance_dirt = smoothstep(3.8, 7.68, position_m.z) * is_floor * 0.32;
	float dirt = (base_dirt * 0.48 + entrance_dirt) * smoothstep(0.38, 0.78, abrasion);
	ALBEDO = mix(mix(tint.rgb, scan, mix(0.25, 0.29, is_floor)), vec3(0.085, 0.065, 0.049), dirt);
	float smooth_finish = mix(mix(0.095, 0.184, variation), mix(0.065, 0.13, variation), is_floor);
	ROUGHNESS = mix(smooth_finish, 0.62, dirt);
	SPECULAR = mix(0.57, 0.70, is_floor);
	CLEARCOAT = mix(0.44, 0.60, is_floor) * (1.0 - dirt);
	CLEARCOAT_ROUGHNESS = mix(0.067, 0.48, dirt);
}
