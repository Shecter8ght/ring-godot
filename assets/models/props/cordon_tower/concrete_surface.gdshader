shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D albedo_map : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D normal_map : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D orm_map : filter_linear_mipmap_anisotropic, repeat_disable;
// RG — мелкий рельеф фотоскана, B — яркость на масштабе пор.
uniform sampler2D pore_detail : filter_linear_mipmap_anisotropic, repeat_enable;

void fragment() {
	vec3 base = texture(albedo_map, UV).rgb;
	vec2 normal_xy = texture(normal_map, UV).rg * 2.0 - 1.0;
	vec3 orm = texture(orm_map, UV).rgb;
	float near_weight = 1.0 - smoothstep(0.65, 2.9, length(VERTEX));
	vec3 pores = texture(pore_detail, UV * 24.0).rgb * 2.0 - 1.0;
	ALBEDO = base * (1.0 + pores.b * (0.17 * near_weight));
	normal_xy += pores.rg * (0.27 * near_weight);
	float normal_z = sqrt(max(0.0, 1.0 - dot(normal_xy, normal_xy)));
	NORMAL_MAP = vec3(normal_xy, normal_z) * 0.5 + 0.5;
	AO = orm.r;
	ROUGHNESS = orm.g;
	METALLIC = orm.b;
}
