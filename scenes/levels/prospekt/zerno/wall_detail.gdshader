shader_type spatial;

uniform sampler2D wall_color : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D wall_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D wall_orm : filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D plaster_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool rear_wall;
uniform float grain_strength = 0.26;

varying vec3 wall_world;

void vertex() {
	wall_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 plaster_uv = vec2(rear_wall ? wall_world.x : -wall_world.z, -wall_world.y) / 1.5;
	vec2 baked = texture(wall_normal, UV).rg * 2.0 - 1.0;
	vec2 grain = texture(plaster_normal, plaster_uv).rg * 2.0 - 1.0;
	vec2 tangent = baked + grain * grain_strength;
	tangent /= max(1.0, length(tangent) * 1.02);
	vec3 orm = texture(wall_orm, UV).rgb;
	ALBEDO = texture(wall_color, UV).rgb;
	ROUGHNESS = orm.g;
	METALLIC = orm.b;
	NORMAL_MAP = vec3(tangent, sqrt(max(0.0, 1.0 - dot(tangent, tangent)))) * 0.5 + 0.5;
}
