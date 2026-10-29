shader_type spatial;
// Краска на модулях общежития (tools/dorm_modules/texture_modules.py: painted_wood / painted_metal), по развёртке модуля:
// mode 0 — крашеное дерево (фактура и трещины краски ambientCG PaintedWood008A перекрашены по яркости: тёмные щели
// остаются тёмными), 1 — краска по металлу (фактура green_metal_rust перекрашена, редкие точки ржавчины внизу).

uniform int mode = 0;
uniform vec3 paint : source_color = vec3(0.42, 0.3, 0.2);
uniform float rough_base = 0.42;
uniform float uv_scale = 1.0;
uniform float rust = 0.0;
uniform sampler2D wood_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wood_rough : filter_linear_mipmap, repeat_enable;
uniform sampler2D wood_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wood_ao : filter_linear_mipmap, repeat_enable;
uniform sampler2D metal_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D metal_arm : filter_linear_mipmap, repeat_enable;
uniform sampler2D metal_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;

varying vec3 local_at;

void vertex() {
	local_at = VERTEX;
}

float lum(vec3 c) {
	return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

void fragment() {
	vec2 uv = UV * uv_scale;
	if (mode == 0) {
		vec3 a = texture(wood_albedo, uv).rgb;
		float l = clamp(lum(a) * 1.55, 0.0, 1.0);
		ALBEDO = mix(vec3(0.012, 0.008, 0.006), paint, l) * texture(wood_ao, uv).r;
		ROUGHNESS = clamp(texture(wood_rough, uv).r * 0.4 + rough_base - 0.15, 0.05, 1.0);
		NORMAL_MAP = texture(wood_normal, uv).rgb;
		NORMAL_MAP_DEPTH = 0.8;
	} else {
		vec3 a = texture(metal_albedo, uv).rgb;
		float l = clamp(lum(a) * 3.2, 0.0, 1.0);
		vec3 c = paint * (l * 0.35 + 0.65);
		// ржавчина — точками, чаще внизу
		float low = clamp(1.0 - local_at.y * 2.2, 0.0, 1.0);
		float spots = step(0.82, lum(texture(metal_albedo, uv * 0.37 + 0.13).rgb) * 2.2) * (low + 0.2) * rust;
		ALBEDO = mix(c, vec3(0.102, 0.043, 0.016), clamp(spots, 0.0, 1.0));
		ROUGHNESS = clamp(texture(metal_arm, uv).g * 0.3 + rough_base - 0.1, 0.05, 1.0);
		NORMAL_MAP = texture(metal_normal, uv).rgb;
		NORMAL_MAP_DEPTH = 0.5;
	}
}
