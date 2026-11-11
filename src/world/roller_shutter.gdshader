shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Роллета магазинчика в подземном переходе «Проспекта»: горизонтальные ламели из оцинковки с краской (шаг по мировой
// высоте), у каждой роллеты свой тон; брошено два года — краска выгорела, ржавчина в стыках ламелей и потёки снизу,
// пыль. Своё, без текстур: выпуклость ламели — наклоном нормали по высоте.

uniform float slat_m = 0.077;
uniform float shop_m = 4.2;
uniform float shop_offset = 0.0;
uniform vec3 paint_color : source_color = vec3(0.47, 0.5, 0.52);
uniform vec3 rust_color : source_color = vec3(0.36, 0.22, 0.13);
uniform float base_y = 0.0;
uniform float rust : hint_range(0.0, 1.0) = 0.5;

varying vec3 wpos;
varying vec3 wnorm;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnorm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float along = abs(wnorm.x) > abs(wnorm.z) ? wpos.z : wpos.x;
	float shop = floor((along - shop_offset) / shop_m);
	float h = hash12(vec2(shop, 3.7));
	// у каждой роллеты свой тон: серая, синеватая, бежевая
	vec3 paint = paint_color * (0.85 + h * 0.3);
	paint = mix(paint, vec3(0.55, 0.52, 0.45), step(0.7, h) * 0.6);
	float t = fract(wpos.y / slat_m);
	float px = max(fwidth(wpos.y) / slat_m, 0.002);
	// стык ламелей — тёмная щель
	float groove = 1.0 - smoothstep(0.0, 0.06 + px, min(t, 1.0 - t));
	vec3 alb = paint * (0.93 + vnoise(vec2(along * 3.0, wpos.y * 0.5)) * 0.12);
	// выгорело и в пыли: светлее и матовее сверху, грязь у пола
	float hy = wpos.y - base_y;
	float dirt = 1.0 - smoothstep(0.0, 0.5 + vnoise(vec2(along * 2.0, 1.0)) * 0.4, hy);
	// ржавчина: в стыках и потёками снизу, пятнами
	float stain = smoothstep(0.55, 0.8, vnoise(vec2(along * 1.3, wpos.y * 1.1) + h * 9.0));
	float drip = smoothstep(0.5, 0.85, vnoise(vec2(along * 14.0, hy * 0.8))) * (1.0 - smoothstep(0.1, 0.9, hy));
	float r = clamp((groove * 0.8 + stain * 0.6 + drip * 0.7) * rust, 0.0, 1.0);
	alb = mix(alb, rust_color * (0.8 + vnoise(wpos.xy * 40.0 + wpos.z) * 0.4), r);
	alb = mix(alb, vec3(0.03), groove * 0.55);
	alb = mix(alb, vec3(0.3, 0.27, 0.22), dirt * 0.6);
	ALBEDO = alb;
	ROUGHNESS = mix(0.55, 0.95, max(r, dirt));
	METALLIC = mix(0.35, 0.0, max(r, dirt));
	SPECULAR = 0.5;
	// выпуклая ламель: нормаль наклоняется вверх в верхней половине и вниз в нижней
	vec3 up_view = (VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz;
	NORMAL = normalize(NORMAL + up_view * ((t - 0.5) * 0.9 - groove * sign(t - 0.5) * 0.6));
}
