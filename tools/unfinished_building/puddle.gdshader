shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;

// Спокойная лужа на бетоне: мокрая кромка просвечивает, микрорельеф слегка ломает отражение.
uniform vec3 shallow_color : source_color = vec3(0.055, 0.060, 0.052);
uniform vec3 deep_color : source_color = vec3(0.018, 0.025, 0.024);
uniform float ripple_strength : hint_range(0.0, 1.0) = 0.055;
uniform float edge_width : hint_range(0.02, 0.5) = 0.22;

varying vec3 world_pos;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}

float fbm(vec2 p) {
	float value = vnoise(p) * 0.60 + vnoise(p * 2.07 + 5.2) * 0.28 + vnoise(p * 4.13 + 17.1) * 0.12;
	return value;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float radial = length(UV * 2.0);
	float ragged = (fbm(p * 5.0) - 0.5) * 0.055;
	float distance_to_edge = 1.0 - radial + ragged;
	float body = smoothstep(0.035, edge_width * 1.3, distance_to_edge);

	float e = 0.035;
	float h = fbm(p * 7.0) * 0.65 + fbm(p * 19.0 + 8.0) * 0.35;
	float hx = fbm((p + vec2(e, 0.0)) * 7.0) * 0.65 + fbm((p + vec2(e, 0.0)) * 19.0 + 8.0) * 0.35;
	float hz = fbm((p + vec2(0.0, e)) * 7.0) * 0.65 + fbm((p + vec2(0.0, e)) * 19.0 + 8.0) * 0.35;
	vec2 slope = vec2(hx - h, hz - h) * ripple_strength;
	vec3 world_normal = normalize(vec3(slope.x, 1.0, slope.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);

	ALBEDO = mix(shallow_color, deep_color, body);
	ROUGHNESS = clamp(mix(0.32, 0.16, body) + (fbm(p * 12.0) - 0.5) * 0.035, 0.12, 0.38);
	SPECULAR = 0.22;
	METALLIC = 0.0;
	float ring_in = smoothstep(0.64, 0.84, radial - ragged);
	float ring_out = 1.0 - smoothstep(0.88, 1.10, radial - ragged);
	ALPHA = ring_in * ring_out * 0.78;
}
