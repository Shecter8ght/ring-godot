shader_type spatial;
// Веер мелкого материала (пыль бетона, грунт, щепа): освещаемые полосы вдоль скорости.
// Быстрые — вытянуты, сопротивление воздуха гасит скорость — полоса сжимается в клубок и тает.
render_mode depth_draw_never, cull_disabled, shadows_disabled, specular_disabled, diffuse_lambert_wrap;

#include "res://src/combat/impact_streak.gdshaderinc"

uniform sampler2D mask : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D depth_texture : hint_depth_texture, filter_linear;
// мягкий стык с землёй и стеной: ближе этого — прозрачнее, м
uniform float soft_m = 0.08;

// Клуб: мягкий эллипс вдоль скорости, у головы плотнее, к хвосту реже.
float puff_shape(vec2 uv) {
	vec2 q = vec2(uv.x * 2.0 - 1.0, uv.y * 2.0 - 1.0);
	float d = length(q);
	return (1.0 - smoothstep(0.15, 1.0, d)) * mix(1.0, 0.55, uv.y);
}

void fragment() {
	float shape = puff_shape(UV);
	float grain = texture(mask, UV * vec2(0.5, 0.9) + vec2(v_seed, v_seed * 2.3)).r;
	float depth = texture(depth_texture, SCREEN_UV).r;
	vec4 world = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	float scene_z = -world.z / world.w;
	float soft = clamp((scene_z - (-VERTEX.z)) / soft_m, 0.0, 1.0);
	ALBEDO = COLOR.rgb;
	ALPHA = clamp(COLOR.a * shape * mix(0.35, 1.25, grain), 0.0, 1.0) * soft;
}
