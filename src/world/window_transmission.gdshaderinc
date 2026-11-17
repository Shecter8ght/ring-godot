uniform sampler2D opaque_scene : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform float transmission_blur : hint_range(0.0, 4.0) = 1.2;
uniform sampler2D transmission_dust_mask : filter_linear_mipmap, repeat_enable;
uniform float transmission_dust_strength : hint_range(0.0, 1.0) = 0.0;
uniform float transmission_warp : hint_range(0.0, 0.005) = 0.0;

float window_dust(vec2 surface) {
	if (transmission_dust_strength <= 0.0) {
		return 0.0;
	}
	// Маска лежит в плоскости стекла, чтобы налёт оставался на том же месте при движении.
	float patches = textureLod(transmission_dust_mask, surface * vec2(0.63, 0.46), 2.4).a;
	float film = textureLod(transmission_dust_mask, surface * vec2(-0.31, 0.37) + 0.29, 3.0).a;
	return transmission_dust_strength * (0.18 + 0.55 * patches + 0.27 * film);
}

vec3 transmitted_window(vec2 screen_uv, vec3 normal, vec2 surface, float lod, float dust) {
	vec2 wave_phase = vec2(dot(surface, vec2(3.1, 1.7)), dot(surface, vec2(-2.4, 3.6)));
	vec2 waves = sin(wave_phase + 0.58 * sin(surface.yx * vec2(5.9, 4.2)));
	vec2 offset = normal.xy * 0.00044 + waves * transmission_warp;
	vec2 sample_uv = clamp(screen_uv + offset, vec2(0.0), vec2(1.0));
	return textureLod(opaque_scene, sample_uv, lod + 1.3 * dust).rgb;
}
