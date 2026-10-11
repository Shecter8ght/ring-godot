shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled;

uniform sampler2D crack_map : filter_linear_mipmap;
uniform bool cracked = false;
// ПНВ на голове: стекло не бликует и почти исчезает — трубка усиливала блик от ИК-подсветки и
// едва заметный оттенок стекла до сплошного пятна, через окно ничего не было видно.
uniform float head_nvg = 0.0;
// Ночной режим самого прицела (кнопка NV): в окне — усиленная зелёная картинка того, что за ним.
// Без ПНВ и фонаря видно только в этом окошке.
uniform float window_nv = 0.0;
// Усиление слабого света и дальность собственной ИК-подсветки окна, м.
uniform float nv_gain = 46.0;
uniform float nv_ir_range = 55.0;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;

void fragment() {
	// Исходная LensUV перенесена в первый игровой UV-канал линзы.
	float crack = cracked ? texture(crack_map, UV).r : 0.0;
	if (window_nv > 0.5) {
		vec3 src = texture(screen_tex, SCREEN_UV).rgb;
		float lum = dot(src, vec3(0.299, 0.587, 0.114));
		// слабый свет усиливается, яркий не выжигается
		float amp = 1.0 - exp(-lum * nv_gain);
		// своя ИК-подсветка: в полной темноте усиливать нечего — ближнее светлее дальнего, как под
		// ИК-фонарём, и по перепадам глубины читаются стены и фигуры
		float depth = texture(depth_tex, SCREEN_UV).r;
		vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
		float dist = -view.z / view.w;
		float ir = pow(clamp(1.0 - dist / nv_ir_range, 0.0, 1.0), 1.6) * 0.42;
		amp = clamp(amp + ir * (1.0 - amp), 0.0, 1.0);
		// зерно трубки
		float n = fract(sin(dot(floor(SCREEN_UV * VIEWPORT_SIZE * 0.5) + vec2(TIME * 61.0, TIME * 37.0), vec2(12.9898, 78.233))) * 43758.5453);
		amp = clamp(amp + (n - 0.5) * 0.035 * (0.4 + amp), 0.0, 1.0);
		// затемнение к краю окна
		vec2 c = UV - vec2(0.5);
		amp *= 1.0 - smoothstep(0.32, 0.72, length(c));
		ALBEDO = vec3(0.0);
		EMISSION = mix(vec3(0.05, 0.62, 0.14), vec3(0.55, 1.0, 0.62), amp) * amp * 1.5 + vec3(0.8) * crack * 0.2;
		ALPHA = 1.0;
		ROUGHNESS = 1.0;
		SPECULAR = 0.0;
		METALLIC = 0.0;
	} else {
		ALBEDO = mix(vec3(0.52, 0.76, 0.64), vec3(0.8), crack);
		ALPHA = mix(0.055, 0.008, head_nvg) + crack * mix(0.65, 0.25, head_nvg);
		ROUGHNESS = mix(0.035, 1.0, head_nvg) + crack * 0.75;
		METALLIC = 0.0;
		SPECULAR = mix(0.3, 0.0, head_nvg);
	}
}
