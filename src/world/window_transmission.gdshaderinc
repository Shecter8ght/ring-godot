uniform sampler2D opaque_scene : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform float transmission_blur : hint_range(0.0, 4.0) = 1.2;

vec3 transmitted_window(vec2 screen_uv, vec3 normal, float lod) {
	// Буфер непрозрачных объектов. Сдвиг ниже пикселя сохраняет прямые контуры на витраже.
	vec2 sample_uv = clamp(screen_uv + normal.xy * 0.00044, vec2(0.0), vec2(1.0));
	return textureLod(opaque_scene, sample_uv, lod).rgb;
}