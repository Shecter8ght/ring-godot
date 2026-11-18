shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

// Внутренняя гладь остаётся в непрозрачном проходе: Godot даёт ей SSR и отражения проб.
uniform vec3 shallow_color : source_color = vec3(0.045, 0.052, 0.047);
uniform vec3 deep_color : source_color = vec3(0.018, 0.025, 0.024);
uniform float ripple_strength : hint_range(0.0, 1.0) = 0.035;

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
	return vnoise(p) * 0.60 + vnoise(p * 2.07 + 5.2) * 0.28 + vnoise(p * 4.13 + 17.1) * 0.12;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 p = world_pos.xz;
	float radial = length(UV * 2.0);
	float body = 1.0 - smoothstep(0.68, 1.04, radial);
	float e = 0.035;
	float h = fbm(p * 7.0) * 0.65 + fbm(p * 19.0 + 8.0) * 0.35;
	float hx = fbm((p + vec2(e, 0.0)) * 7.0) * 0.65 + fbm((p + vec2(e, 0.0)) * 19.0 + 8.0) * 0.35;
	float hz = fbm((p + vec2(0.0, e)) * 7.0) * 0.65 + fbm((p + vec2(0.0, e)) * 19.0 + 8.0) * 0.35;
	vec2 slope = vec2(hx - h, hz - h) * ripple_strength;
	vec3 world_normal = normalize(vec3(slope.x, 1.0, slope.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);
	ALBEDO = mix(shallow_color, deep_color, body);
	ROUGHNESS = clamp(mix(0.24, 0.09, body) + (fbm(p * 12.0) - 0.5) * 0.025, 0.065, 0.30);
	SPECULAR = mix(0.25, 0.48, body);
	METALLIC = 0.0;
}
