shader_type spatial;
// Земля «Санатория» (src/blockout/sanatorium_ground.gd): восемь грунтов 4K (tools/build_sanatorium_ground.py) по двум
// маскам генератора (tools/build_sanatorium.py). Против видимого повтора у каждого слоя две выборки — обычная и
// повёрнутая со своим масштабом, между ними выбирает шум и высота (видна та, что выше, — без «двоения»); издали ещё
// выборка крупнее. Переходы между грунтами — по высоте: камешки тропы проступают сквозь траву, хвоя лежит между
// травинками, песок затекает в низины. Крупные пятна тона и выгоревшие пятна газона — по шуму.
// Слои: 0 газон, 1 вытоптанный газон, 2 хвоя, 3 мох, 4 тропа, 5 гранит, 6 щебень, 7 песок.
// splat:  R вытоптанный газон, G хвоя, B мох, A тропа; splat2: R гранит, G щебень, B песок, A сырость у воды.
// arm_array: R — AO, G — шероховатость, B — высота (растянута на весь диапазон у каждого слоя).

uniform sampler2DArray albedo_array : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray normal_array : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray arm_array : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D splat : filter_linear, repeat_disable;
uniform sampler2D splat2 : filter_linear, repeat_disable, hint_default_black;
// бесшовный шум зоны 1 (R крупные пятна, G смешение выборок, B края, A рябь)
uniform sampler2D noise : filter_linear_mipmap, repeat_enable;
uniform vec2 splat_origin = vec2(0.0);
uniform vec2 splat_size = vec2(1.0);
// плитка слоя, м (по размеру скана: трава 1,4 м, иглы 2 м …)
uniform float layer_tile[8];
// выравнивание яркости фотографий, линейный множитель (у щебня скан вдвое светлее гранита)
uniform float layer_gain[8];
uniform vec3 grass_tint : source_color = vec3(0.95, 0.97, 0.80);
// насыщенность газона: скан стриженой травы слишком «изумрудный» для двух лет без ухода
uniform float grass_saturation = 0.74;
// выгоревшие пятна газона (лето, 2 года без ухода)
uniform vec3 grass_dry : source_color = vec3(1.30, 1.12, 0.74);
uniform float grass_dry_amount = 0.55;
// мох с сором: в скане рыжие листья — к оливковому
uniform vec3 moss_tint : source_color = vec3(0.86, 0.96, 0.70);
uniform vec3 sand_tint : source_color = vec3(1.0, 0.93, 0.80);
uniform float far_mul = 3.7;
uniform float far_start = 14.0;
uniform float far_end = 80.0;
// мягкость перехода по высоте между грунтами (меньше — резче, рваный край)
uniform float height_blend = 0.16;
uniform float normal_depth = 1.15;
uniform float cliff_tile = 9.0;
uniform float rock_slope_start = 0.80;
uniform float rock_slope_end = 0.60;
// «Трава издали» (Balance.GRASS.far_look, ставит DistrictGrass через DistrictTerrain.set_far_grass): там, где
// травинки уходят в землю, газон берёт их вид — без тёмной полосы за кольцом травы. Множитель far_tint_k —
// поправка к общему тону (он подобран к тёмной фотографии газона зоны 1, наш скан светлее).
uniform sampler2D grass_density : filter_linear, repeat_disable, hint_default_black;
uniform vec2 grass_origin = vec2(0.0);
uniform vec2 grass_size = vec2(1.0);
uniform float grass_density_from = 0.02;
uniform float grass_density_full = 0.22;
uniform float grass_far_start = 100000.0;
uniform float grass_far_end = 100001.0;
uniform vec3 grass_far_tint = vec3(1.0);
uniform float grass_far_flat = 0.0;
uniform vec2 grass_far_clumps = vec2(1.0);
uniform float far_tint_k = 0.5;
// отладка: 1 — номер преобладающего грунта, 2 — выбор выборки (против повтора), 3 — выборка издали
uniform int debug_view = 0;
global uniform float rain_wet;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

mat2 rot2(float a) {
	return mat2(vec2(cos(a), sin(a)), vec2(-sin(a), cos(a)));
}

// Слой с двумя выборками и выборкой издали; nrm — карта нормалей (0…1), arm — AO, шероховатость, высота.
void layer(int i, vec2 wp, float far_k, out vec3 alb, out vec3 nrm, out vec3 arm, out float pick) {
	float t = layer_tile[i];
	float li = float(i);
	vec2 uv1 = wp / t;
	float ang = 0.65 + li * 0.91;
	mat2 r = rot2(ang);
	vec2 uv2 = r * (wp / (t * 1.31)) + vec2(0.37, 0.71) * (li + 1.0);
	vec3 a1 = texture(albedo_array, vec3(uv1, li)).rgb;
	vec3 m1 = texture(arm_array, vec3(uv1, li)).rgb;
	vec3 n1 = texture(normal_array, vec3(uv1, li)).rgb;
	vec3 a2 = texture(albedo_array, vec3(uv2, li)).rgb;
	vec3 m2 = texture(arm_array, vec3(uv2, li)).rgb;
	vec3 n2 = texture(normal_array, vec3(uv2, li)).rgb;
	// нормаль повёрнутой выборки — обратно в оси мира
	vec2 n2xy = transpose(r) * (n2.xy * 2.0 - 1.0);
	n2 = vec3(n2xy * 0.5 + 0.5, n2.z);
	// пятна выбора 8–15 м, свои у каждого слоя; по высоте — видна та выборка, что выше
	float s = texture(noise, wp / (9.0 + li * 0.8) + li * 0.173).g;
	pick = clamp((m2.b - m1.b) * 2.4 + (s - 0.5) * 3.2 + 0.5, 0.0, 1.0);
	alb = mix(a1, a2, pick);
	nrm = mix(n1, n2, pick);
	arm = mix(m1, m2, pick);
	if (far_k > 0.01) {
		vec2 uv3 = rot2(ang + 1.7) * wp / (t * far_mul) + 0.53;
		vec3 a3 = texture(albedo_array, vec3(uv3, li)).rgb;
		vec3 m3 = texture(arm_array, vec3(uv3, li)).rgb;
		alb = mix(alb, a3, far_k * 0.5);
		arm = mix(arm, m3, far_k * 0.35);
		nrm = mix(nrm, vec3(0.5, 0.5, 1.0), far_k * 0.35);
	}
	alb *= layer_gain[i];
}

// Гранит на крутом — с трёх сторон, чтобы на обрыве текстура не тянулась полосами.
void cliff(vec3 p, vec3 n, out vec3 alb, out vec3 nrm, out vec3 arm) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= (w.x + w.y + w.z);
	vec2 px = p.zy / cliff_tile;
	vec2 py = p.xz / cliff_tile;
	vec2 pz = p.xy / cliff_tile;
	alb = (texture(albedo_array, vec3(px, 5.0)).rgb * w.x + texture(albedo_array, vec3(py, 5.0)).rgb * w.y
		+ texture(albedo_array, vec3(pz, 5.0)).rgb * w.z) * layer_gain[5];
	arm = texture(arm_array, vec3(px, 5.0)).rgb * w.x + texture(arm_array, vec3(py, 5.0)).rgb * w.y
		+ texture(arm_array, vec3(pz, 5.0)).rgb * w.z;
	// нормаль трипланара грубо: сверху — карта, по бокам — плоско (стена уже даёт рельеф геометрией)
	nrm = mix(vec3(0.5, 0.5, 1.0), texture(normal_array, vec3(py, 5.0)).rgb, w.y);
}

void fragment() {
	vec2 wp = wpos.xz;
	vec2 suv = (wp - splat_origin) / splat_size;
	vec4 m = texture(splat, suv);
	vec4 m2 = texture(splat2, suv);
	float dist = distance(wpos, CAMERA_POSITION_WORLD);
	float far_k = smoothstep(far_start, far_end, dist);
	// нормаль грани: на гранях выемки и обрывах нормаль вершины усреднена с соседними — проекция тянется полосами
	vec3 fn = normalize(cross(dFdx(wpos), dFdy(wpos)));
	float up = clamp(min(wnrm.y, abs(fn.y)), 0.0, 1.0);
	float steep = 1.0 - smoothstep(rock_slope_end, rock_slope_start, up);

	float w[8];
	w[1] = m.r;
	w[2] = m.g;
	w[3] = m.b;
	w[4] = m.a;
	w[5] = max(m2.r, steep);
	w[6] = m2.g;
	w[7] = m2.b;
	float top = 0.0;
	for (int i = 1; i < 8; i++) {
		top = max(top, w[i]);
	}
	w[0] = 1.0 - top;

	// грунты с весом читаются, остальные нет; смешение по высоте: побеждает тот, у кого вес + высота больше
	vec3 A[8];
	vec3 N[8];
	vec3 R[8];
	float ha[8];
	float hmax = -10.0;
	float pick0 = 0.0;
	float far_dbg = far_k;
	for (int i = 0; i < 8; i++) {
		ha[i] = -10.0;
		if (w[i] < 0.01) {
			continue;
		}
		float pk;
		if (i == 5 && steep > 0.05) {
			cliff(wpos, fn, A[i], N[i], R[i]);
			pk = 0.0;
		} else {
			layer(i, wp, far_k, A[i], N[i], R[i], pk);
		}
		if (i == 0) {
			pick0 = pk;
		}
		ha[i] = w[i] + R[i].b * 0.6;
		hmax = max(hmax, ha[i]);
	}
	vec3 out_a = vec3(0.0);
	vec3 out_n = vec3(0.0);
	vec3 out_r = vec3(0.0);
	float sum = 0.0;
	int dom = 0;
	float dom_b = 0.0;
	for (int i = 0; i < 8; i++) {
		if (ha[i] < -5.0) {
			continue;
		}
		float b = max(ha[i] - (hmax - height_blend), 0.0);
		if (b <= 0.0) {
			continue;
		}
		vec3 a = A[i];
		if (i <= 1) {
			// газон: оттенок лета и выгоревшие пятна по крупному шуму
			float dry = smoothstep(0.42, 0.80, texture(noise, wp / 41.0 + 0.31).r * 0.65 + texture(noise, wp / 13.0 + 0.77).b * 0.35);
			float luma = dot(a, vec3(0.3, 0.59, 0.11));
			a = mix(vec3(luma), a, grass_saturation) * grass_tint;
			// выгоревшее — солома: яркость травы, цвет соломы
			a = mix(a, luma * grass_dry, dry * grass_dry_amount);
		} else if (i == 3) {
			a *= moss_tint;
		} else if (i == 7) {
			a *= sand_tint;
		}
		out_a += a * b;
		out_n += N[i] * b;
		out_r += R[i] * b;
		sum += b;
		if (b > dom_b) {
			dom_b = b;
			dom = i;
		}
	}
	out_a /= sum;
	out_n /= sum;
	out_r /= sum;
	vec4 gd = texture(grass_density, (wp - grass_origin) / grass_size);
	float gk = smoothstep(grass_far_start, grass_far_end, distance(wp, CAMERA_POSITION_WORLD.xz))
		* smoothstep(grass_density_from, grass_density_full, gd.r + gd.g * 0.5);
	if (gk > 0.001) {
		float clump = mix(grass_far_clumps.x, grass_far_clumps.y, texture(noise, wp / 4.0).a);
		vec3 tint = mix(vec3(1.0), grass_far_tint, far_tint_k);
		out_a *= mix(vec3(1.0), tint * clump, gk);
		out_n = mix(out_n, vec3(0.5, 0.5, 1.0), grass_far_flat * gk);
	}
	// крупные пятна тона: сырые низины темнее, бугры светлее — не «ковёр»
	float macro = texture(noise, wp / 520.0).r;
	out_a *= mix(0.86, 1.07, macro);
	// у воды и в дождь — темнее и глаже
	float wet = clamp(max(m2.a, rain_wet * (0.6 + 0.4 * up)), 0.0, 1.0);
	out_a *= 1.0 - 0.36 * wet;
	ALBEDO = out_a;
	if (debug_view == 1) {
		ALBEDO = vec3(float(dom & 1), float((dom >> 1) & 1), float((dom >> 2) & 1)) * 0.8 + 0.1;
	}
	if (debug_view == 2) {
		ALBEDO = vec3(pick0);
	}
	if (debug_view == 3) {
		ALBEDO = vec3(far_dbg);
	}
	NORMAL_MAP = out_n;
	NORMAL_MAP_DEPTH = normal_depth;
	AO = out_r.r;
	AO_LIGHT_AFFECT = 0.4;
	ROUGHNESS = mix(clamp(out_r.g, 0.55, 1.0), 0.32, wet);
	SPECULAR = 0.35;
}
