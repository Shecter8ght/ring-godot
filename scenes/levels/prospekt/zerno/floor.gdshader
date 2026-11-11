shader_type spatial;
render_mode diffuse_burley, specular_schlick_ggx, cull_back;

uniform sampler2D ceramic_color : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D ceramic_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D ceramic_rough : hint_default_white, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D local_mask : hint_default_black, filter_linear_mipmap_anisotropic, repeat_disable;
uniform sampler2D stock_mask : hint_default_black, filter_linear_mipmap_anisotropic, repeat_disable;
uniform bool stockroom = false;

void fragment() {
	vec3 base = texture(ceramic_color, UV).rgb;
	vec4 stains = texture(local_mask, UV2);
	float dust = smoothstep(0.13, 0.69, stains.r) * 0.18;
	float dried_water = smoothstep(0.07, 0.47, stains.g) * 0.32;
	float wet = smoothstep(0.08, 0.96, stains.b);
	float tread = stains.a * 0.78;
	if (stockroom) {
		vec2 local = vec2(UV2.x * 11.69 - 7.77, (1.0 - UV2.y) * 10.54 - 5.27);
		vec2 stock_uv = vec2((local.x - 4.08) / 3.69, 1.0 - (local.y + 0.35) / 5.63);
		vec3 stock = texture(stock_mask, stock_uv).rgb;
		dust = stock.r * 0.32;
		dried_water = stock.g * 0.23;
		wet = 0.0;
		tread = stock.b * 0.76;
	}
	base = mix(base, vec3(0.151, 0.119, 0.080), dust);
	base = mix(base, vec3(0.052, 0.041, 0.029), dried_water);
	base = mix(base, vec3(0.023, 0.015, 0.010), tread);
	ALBEDO = base * mix(1.0, 0.69, wet);
	ROUGHNESS = mix(mix(texture(ceramic_rough, UV).r, 0.86, tread), 0.058, wet);
	METALLIC = 0.0;
	SPECULAR = mix(0.44, 0.52, wet);
	NORMAL_MAP = texture(ceramic_normal, UV).rgb;
	NORMAL_MAP_DEPTH = mix(0.96, 0.13, wet);
}

