shader_type spatial;

uniform sampler2D paint_color : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D paint_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D paint_orm : filter_linear_mipmap_anisotropic;

varying vec3 facade_pos;

void vertex() {
	facade_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

float cell_noise(vec2 p) {
	vec2 cell = floor(p);
	vec2 f = smoothstep(vec2(0.0), vec2(1.0), fract(p));
	vec4 phase = dot(cell, vec2(23.73, 61.57)) + vec4(0.0, 23.73, 61.57, 85.30);
	vec4 values = fract(sin(phase) * 14653.273);
	return mix(mix(values.x, values.y, f.x), mix(values.z, values.w, f.x), f.y);
}

void fragment() {
	vec2 face = vec2(facade_pos.x, facade_pos.y);
	float sun_fade = cell_noise(face * vec2(1.4, 6.0));
	float runoff = smoothstep(0.52, 0.89, cell_noise(face * vec2(17.0, 1.6)));
	float spots = smoothstep(0.58, 0.94, cell_noise(face * 44.0));
	vec3 paint = texture(paint_color, UV).rgb;
	vec3 orm = texture(paint_orm, UV).rgb;
	float gray = dot(paint, vec3(0.2126, 0.7152, 0.0722));
	ALBEDO = mix(paint, vec3(gray), 0.22 + sun_fade * 0.21) * (0.87 - runoff * 0.20 - spots * 0.10);
	ROUGHNESS = clamp(orm.g + 0.20 + runoff * 0.15 + spots * 0.10, 0.43, 0.94);
	METALLIC = orm.b;
	NORMAL_MAP = texture(paint_normal, UV).rgb;
}
