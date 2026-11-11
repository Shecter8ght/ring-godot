shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Подвесной потолок подземного перехода «Проспекта»: плиты 0,6 × 0,6 в металлической решётке (нижняя грань коробки,
// по мировым X/Z); бока — бетон. Брошен два года: часть плит выпала (за ними темно, видны кабели и бетон перекрытия),
// плиты в разводах от протечек и пятнах плесени, решётка местами ржавая. Своё, без текстур.

uniform float panel_m = 0.6;
uniform float bar_m = 0.024;
uniform vec3 panel_color : source_color = vec3(0.80, 0.79, 0.75);
uniform vec3 bar_color : source_color = vec3(0.62, 0.62, 0.6);
uniform vec3 void_color : source_color = vec3(0.04, 0.04, 0.045);
uniform vec3 concrete_color : source_color = vec3(0.45, 0.44, 0.42);
uniform float missing : hint_range(0.0, 1.0) = 0.12;
uniform float stains : hint_range(0.0, 1.0) = 0.6;

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
	vec3 alb;
	float rough = 0.9;
	float metal = 0.0;
	if (wnorm.y < -0.5) {
		vec2 q = wpos.xz / panel_m;
		vec2 cell = floor(q);
		vec2 f = fract(q) * panel_m;
		float ed = min(min(f.x, panel_m - f.x), min(f.y, panel_m - f.y));
		float px = max(length(fwidth(wpos.xz)), 0.0005);
		float bar = 1.0 - smoothstep(bar_m * 0.5, bar_m * 0.5 + px, ed);
		float h = hash12(cell + 0.37);
		bool gone = h < missing;
		if (gone) {
			// дыра: темнота, кабели и бетон перекрытия едва видны
			float cable = smoothstep(0.48, 0.5, abs(fract(wpos.x * 2.3 + vnoise(wpos.xz * 0.7)) - 0.5));
			alb = mix(void_color, void_color * 2.5, cable * 0.5);
			rough = 1.0;
		} else {
			alb = panel_color * (0.92 + hash12(cell + 5.1) * 0.12);
			// мелкая перфорация плиты и разводы от протечек
			float speck = vnoise(wpos.xz * 160.0);
			alb *= 0.96 + speck * 0.06;
			float ring = smoothstep(0.55, 0.85, vnoise(wpos.xz * 0.9 + 4.0)) * stains;
			float edge_ring = ring * smoothstep(0.0, 0.08, abs(fract(vnoise(wpos.xz * 0.9 + 4.0) * 6.0) - 0.5) - 0.38);
			alb = mix(alb, alb * vec3(0.72, 0.62, 0.45), ring * 0.55 + edge_ring * 0.3);
			float mould = smoothstep(0.7, 0.85, vnoise(wpos.xz * 3.0 + 9.0)) * stains;
			alb = mix(alb, vec3(0.12, 0.13, 0.1), mould * 0.6);
		}
		// решётка: металл, местами ржавый
		vec3 bc = mix(bar_color, vec3(0.38, 0.24, 0.14), smoothstep(0.6, 0.85, vnoise(wpos.xz * 1.5)));
		alb = mix(alb, bc, bar * (gone ? 0.7 : 1.0));
		metal = bar * 0.6;
		rough = mix(rough, 0.45, bar);
	} else {
		float g = vnoise(wpos.xz * 30.0 + wpos.y * 7.0) * 0.5 + vnoise(wpos.xz * 4.0) * 0.5;
		alb = concrete_color * (0.85 + g * 0.3);
	}
	ALBEDO = alb;
	ROUGHNESS = rough;
	METALLIC = metal;
	SPECULAR = 0.5;
}
