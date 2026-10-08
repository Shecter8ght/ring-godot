shader_type spatial;
// Рельеф района: шесть фототекстур (массивы слоёв) по маске и уклону.
// Слои: 0 осенний газон, 1 редкая трава, 2 опавшая листва, 3 грязь, 4 камень, 5 щебень.
// Маска (R грязь, G камень, B щебень, A листва) — из tools/build_zone01.py, 1 пиксель = 1 м.

uniform sampler2DArray albedo_array : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray normal_array : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray arm_array : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D splat : filter_linear, repeat_disable;
// бесшовный шум (R крупные пятна, G смешение выборок, B края слоёв, A рябь), см. build_zone01.py
uniform sampler2D noise : filter_linear_mipmap, repeat_enable;
uniform vec2 splat_origin = vec2(0.0);
uniform vec2 splat_size = vec2(1.0);
uniform float layer_tile[6];
// поздняя осень: газон темнее и оливковее фототекстуры
uniform vec3 grass_tint : source_color = vec3(0.5, 0.56, 0.38);
// опавшая листва и грязь — темнее и тусклее фототекстур (сырая поздняя осень)
uniform vec3 litter_tint : source_color = vec3(0.56, 0.5, 0.38);
// листва и грязь: насыщенность фототекстур (осенняя листва скана слишком оранжевая)
uniform float litter_saturation = 0.7;
// Камень выходит сам, когда склон круче этого (косинус угла с вертикалью).
uniform float rock_slope_start = 0.82;
uniform float rock_slope_end = 0.62;
// отладка: 1 — вес редкой травы, 2 — крупные пятна, 3 — смешение выборок
uniform int debug_view = 0;
// сырость в дождь (RainFx): темнее, глаже, блестит
global uniform float rain_wet;

varying vec3 world_pos;
varying vec3 world_nrm;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_nrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// Слой с поворотом второй выборки — ломает повтор плитки на больших полях.
void layer(int i, vec2 wp, float mixr, out vec3 alb, out vec3 nrm, out vec3 arm) {
	vec2 uv = wp / layer_tile[i];
	alb = texture(albedo_array, vec3(uv, float(i))).rgb;
	nrm = texture(normal_array, vec3(uv, float(i))).rgb;
	arm = texture(arm_array, vec3(uv, float(i))).rgb;
	// вторая повёрнутая выборка ломает повтор — только у газона (он на всю карту), остальным дорого
	if (i <= 1 && mixr > 0.01) {
		vec2 uv2 = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * wp / (layer_tile[i] * 1.37) + 0.37;
		vec3 a2 = texture(albedo_array, vec3(uv2, float(i))).rgb;
		vec3 n2 = texture(normal_array, vec3(uv2, float(i))).rgb;
		vec2 n2xy = mat2(vec2(0.8, -0.6), vec2(0.6, 0.8)) * (n2.xy * 2.0 - 1.0);
		alb = mix(alb, a2, mixr);
		nrm = mix(nrm, vec3(n2xy * 0.5 + 0.5, n2.z), mixr);
	}
}

void fragment() {
	vec2 wp = world_pos.xz;
	vec4 m = texture(splat, (wp - splat_origin) / splat_size);
	float macro = texture(noise, wp / 700.0).r;
	float mixr = smoothstep(0.3, 0.7, texture(noise, wp / 260.0).g);
	float up = clamp(world_nrm.y, 0.0, 1.0);
	float slope_rock = 1.0 - smoothstep(rock_slope_end, rock_slope_start, up);

	// веса: газон с пятнами редкой травы, сверху маска; слои с нулевым весом не читаются
	float w[6];
	w[1] = smoothstep(0.45, 0.75, macro) * 0.85;
	w[2] = m.a;
	w[3] = m.r;
	w[4] = max(m.g, slope_rock);
	w[5] = m.b;
	vec3 out_a;
	vec3 out_n;
	vec3 out_r;
	layer(0, wp, mixr, out_a, out_n, out_r);
	out_a *= grass_tint;
	for (int i = 1; i < 6; i++) {
		if (w[i] < 0.01) {
			continue;
		}
		vec3 a;
		vec3 n;
		vec3 r;
		layer(i, wp, mixr, a, n, r);
		if (i == 1) {
			a *= grass_tint;
		} else if (i == 2 || i == 3) {
			a = mix(vec3(dot(a, vec3(0.333))), a, litter_saturation) * litter_tint;
		}
		float k = w[i];
		if (i > 1) {
			// переход по «высоте» альбедо и шуму — рваный край, а не размытая граница
			float h = dot(a, vec3(0.33)) * 0.6 + texture(noise, wp / 23.0 + float(i) * 0.137).b * 0.4;
			k = clamp(smoothstep(0.0, 0.25, w[i] - (1.0 - h) * 0.45 * (1.0 - w[i])), 0.0, 1.0);
		}
		out_a = mix(out_a, a, k);
		out_n = mix(out_n, n, k);
		out_r = mix(out_r, r, k);
	}
	// крупные пятна: сырые низины темнее, выгоревшие бугры светлее — не «ковёр»
	out_a *= mix(0.82, 1.08, macro);
	// мокрая земля темнее и с бликом; крутые склоны (камень) — меньше
	float wk = rain_wet * (0.65 + 0.35 * up);
	out_a *= 1.0 - 0.38 * wk;
	out_r.g = mix(out_r.g, 0.38, wk);
	ALBEDO = out_a;
	if (debug_view == 1) { ALBEDO = vec3(w[1]); }
	if (debug_view == 2) { ALBEDO = vec3(macro); }
	if (debug_view == 3) { ALBEDO = vec3(mixr); }
	NORMAL_MAP = out_n;
	AO = out_r.r;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = clamp(out_r.g, 0.35, 1.0);
	METALLIC = 0.0;
}
