shader_type canvas_item;
// Резкость поверх кадра (нерезкая маска): картинка плюс её разница с размытой на пиксель — мелкая фактура
// читается чётче, как в EFT. Свет «Проспекта» (tools/prospekt_light.py); слой ставят до интерфейса.
uniform sampler2D screen: hint_screen_texture, filter_linear;
uniform float amount = 1.8;

void fragment() {
	vec2 px = SCREEN_PIXEL_SIZE;
	vec3 c = texture(screen, SCREEN_UV).rgb;
	vec3 blur = (texture(screen, SCREEN_UV + vec2(px.x, 0.0)).rgb + texture(screen, SCREEN_UV - vec2(px.x, 0.0)).rgb
		+ texture(screen, SCREEN_UV + vec2(0.0, px.y)).rgb + texture(screen, SCREEN_UV - vec2(0.0, px.y)).rgb) * 0.25;
	COLOR = vec4(max(c + (c - blur) * amount, vec3(0.0)), 1.0);
}
