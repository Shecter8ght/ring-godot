shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Покрытие территории по мировым X/Z: асфальт, бетон, плитка, щебень, грунт (PBR-наборы Poly Haven,
// MallGround). Как в жизни у ТЦ (Ярославль: «Глобус», «Вернисаж», «Альтаир», «Аура»): асфальт не ровного
// тона — крупные пятна, заплаты ямочного ремонта со швом, залитые битумом трещины, масляные пятна;
// бетон у доков — плиты с пропилами швов; плитка — с грязью в швах. Повтор плитки текстуры ломается:
// у асфальта и бетона — второй выборкой с поворотом, у узорной плитки — сдвигом на целое число плиток
// (швы совпадают), у плит — своим сдвигом и поворотом на 90° в каждой плите. Сетка заплат и плит —
// мировая или по кольцу вокруг центра ТЦ (ряды парковок и двор доков — дугами).
// Без текстур (use_maps = false) — то же самое на процедурном зерне: игра собирается без assets/.
// Сырость — как у шейдера wet_asphalt (плёнка, лужи во впадинах, рябь от капель, под крышей сухо).

uniform bool use_maps = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
// анизотропия — только у цвета: у шероховатости и нормалей на скользящих углах её не видно, а кадр дешевле
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D height_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
// карта высот есть только у части наборов; без неё впадины — по тёмному в альбедо
uniform bool has_height = false;

group_uniforms look;
// размер плитки текстуры, м (реальный размер набора)
uniform float tile_m = 4.0;
// поворот рисунка отдельного куска вокруг texture_origin; 0 — прежнее поведение
uniform float texture_rotation = 0.0;
uniform vec2 texture_origin = vec2(0.0);
// множитель цвета набора (линейный, не цвет)
uniform vec3 tint = vec3(1.0);
uniform float saturation : hint_range(0.0, 1.5) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
uniform float rough_add : hint_range(-0.5, 0.5) = 0.0;
// 0 — вторая выборка повёрнута и крупнее (асфальт, бетон, щебень, грунт);
// 1 — сдвинута на pattern_shift (целое число плиток узора: швы совпадают, сами плитки — другие)
uniform int repeat_break = 0;
uniform vec2 pattern_shift = vec2(0.0);
// крупные пятна тона: сила и размер, м
uniform float macro_var : hint_range(0.0, 0.5) = 0.15;
uniform float macro_m = 22.0;
// с расстояния (м) рельеф и мелкое гаснут — издали не рябит
uniform vec2 detail_fade = vec2(16.0, 70.0);
group_uniforms;

group_uniforms dirt;
// масляные пятна и накатанное: сила, цвет, размер пятен, м
uniform float grime : hint_range(0.0, 1.0) = 0.0;
uniform vec3 grime_color : source_color = vec3(0.1, 0.095, 0.09);
uniform float grime_m = 5.0;
// грязь и мох в швах плитки (швы — тёмное в альбедо)
uniform float joint_dirt : hint_range(0.0, 1.0) = 0.0;
uniform vec3 joint_color : source_color = vec3(0.16, 0.15, 0.11);
// залитые битумом трещины: доля площади, ширина линии и размер многоугольника сетки, м
uniform float seal : hint_range(0.0, 1.0) = 0.0;
uniform float seal_w = 0.035;
uniform float seal_cell = 1.8;
group_uniforms;

group_uniforms grid;
// сетка заплат и плит по кольцу (дуга × радиус вокруг центра ТЦ), иначе — мировая X × Z
uniform bool polar = false;
// где у кольца шов угла (−180…180), — там, где этого покрытия нет
uniform float polar_seam_deg = -100.0;
// заплаты: доля клеток с заплатой, размер клетки, м, тон (минус — свежий тёмный асфальт)
uniform float patch_amount : hint_range(0.0, 1.0) = 0.0;
uniform float patch_cell = 8.0;
uniform float patch_tone = -0.12;
// плиты с пропилами швов: размер (вдоль дуги / X, по радиусу / Z), ширина шва, разброс тона
uniform bool slabs = false;
uniform vec2 slab_m = vec2(4.5, 4.5);
uniform float joint_m = 0.02;
uniform float slab_var : hint_range(0.0, 0.3) = 0.07;
group_uniforms;

group_uniforms fallback;
// без текстур: тон, зерно, шероховатость
uniform vec3 base_color : source_color = vec3(0.35, 0.35, 0.34);
uniform float grain : hint_range(0.0, 0.5) = 0.12;
uniform float grain_m = 0.03;
uniform float base_rough : hint_range(0.0, 1.0) = 0.85;
group_uniforms;

group_uniforms wet;
uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;
uniform float wet_darken : hint_range(0.2, 1.0) = 0.5;
uniform float wet_roughness : hint_range(0.0, 1.0) = 0.12;
uniform float puddle_roughness : hint_range(0.0, 0.3) = 0.03;
uniform float puddle_mirror : hint_range(0.0, 1.0) = 0.6;
uniform float film_mirror : hint_range(0.0, 1.0) = 0.15;
uniform float puddle_freq = 0.16;
uniform float height_bias : hint_range(0.0, 1.0) = 0.35;
group_uniforms;

// карта «что над головой» (RainOcclusion.bind) — под крышей сухо
uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;

float occ_h(vec2 xz) {
	vec2 uv = (xz - occ_center) / occ_size + 0.5;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return -1e5;
	}
	return occ_base + textureLod(occ_tex, uv, 0.0).r * occ_range;
}
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	float v = 0.0;
	float a = 0.55;
	for (int i = 0; i < 4; i++) {
		v += a * vnoise(p);
		p = rot * p * 2.03 + 11.7;
		a *= 0.47;
	}
	return v / 0.93;
}
// рябь от капель: в каждой клетке 0.55 м своё кольцо со своим тактом
vec2 ripples(vec2 p, float t) {
	vec2 g = vec2(0.0);
	vec2 cell = floor(p / 0.55);
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 c = cell + vec2(float(i), float(j));
			vec2 o = hash22(c);
			float ph = fract(t * 0.85 + hash12(c + 17.0));
			vec2 d = p - (c + o) * 0.55;
			float r = length(d);
			float x = (r - ph * 0.3) * 40.0;
			float wave = sin(x) * exp(-x * x * 0.08) * (1.0 - ph) * (1.0 - ph);
			g += (r > 0.0001 ? d / r : vec2(0.0)) * wave;
		}
	}
	return g;
}
// поворот на k × 90°
mat2 quarter(float k) {
	float c = k < 0.5 ? 1.0 : (k < 1.5 ? 0.0 : (k < 2.5 ? -1.0 : 0.0));
	float s = k < 0.5 ? 0.0 : (k < 1.5 ? 1.0 : (k < 2.5 ? 0.0 : -1.0));
	return mat2(vec2(c, s), vec2(-s, c));
}
// координаты сетки, м: по кольцу — длина дуги на середине ряда шириной row × радиус, иначе — мир X, Z
vec2 grid_coord(vec2 xz, float row) {
	if (!polar) {
		return xz;
	}
	float r = length(xz);
	float a = atan(xz.y, xz.x) - radians(polar_seam_deg);
	a = mod(a + PI, TAU) - PI;
	float r_mid = (floor(r / row) + 0.5) * row;
	return vec2(a * r_mid, r);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float tc = cos(texture_rotation);
	float ts = sin(texture_rotation);
	mat2 texture_turn = mat2(vec2(tc, ts), vec2(-ts, tc));
	vec2 xz = texture_origin + texture_turn * (wpos.xz - texture_origin);
	float dist = length(CAMERA_POSITION_WORLD - wpos);
	float far = smoothstep(detail_fade.x, detail_fade.y, dist);
	// размер пикселя на земле, м: сглаживание швов, заплат и трещин (вне ветвлений по пикселю)
	float px_m = max(length(fwidth(xz)), 0.002);
	// крупный шум: где какая выборка текстуры и крупные пятна тона
	float n_low = vnoise(xz * 0.045 + 5.3) * 0.65 + vnoise(xz * 0.11 + 1.7) * 0.35;

	// плиты с пропилами: номер плиты, расстояние до шва
	vec2 slab_id = vec2(0.0);
	float joint = 0.0;
	vec2 slab_off = vec2(0.0);
	mat2 slab_rot = mat2(1.0);
	if (slabs) {
		vec2 q = grid_coord(xz, slab_m.y) / slab_m;
		slab_id = floor(q);
		vec2 e = min(fract(q), 1.0 - fract(q)) * slab_m;
		float d = min(e.x, e.y);
		joint = 1.0 - smoothstep(joint_m * 0.5, joint_m * 0.5 + px_m, d);
		joint *= 1.0 - far * 0.6;
		slab_off = hash22(slab_id + 3.7) * 7.0;
		slab_rot = quarter(floor(hash12(slab_id + 9.1) * 4.0));
	}

	// заплата: в клетке сетки прямоугольник случайного размера; свой тон и своя выборка, по краю — шов
	float pat = 0.0;
	float pat_seam = 0.0;
	vec2 pat_off = vec2(0.0);
	float pat_sign = 1.0;
	if (patch_amount > 0.0) {
		vec2 q = grid_coord(xz, patch_cell);
		vec2 c = floor(q / patch_cell);
		vec2 h = hash22(c + 41.3);
		vec2 hs = hash22(c + 7.7);
		vec2 half_size = mix(vec2(0.18), vec2(0.42), hs) * patch_cell;
		vec2 center = (c + 0.5) * patch_cell + (hash22(c + 2.9) - 0.5) * (patch_cell - 2.0 * half_size);
		vec2 d = abs(q - center) - half_size;
		float inside = max(d.x, d.y);
		float on = step(h.x, patch_amount);
		pat = on * (1.0 - smoothstep(-px_m, px_m, inside));
		pat_seam = on * (1.0 - smoothstep(0.015, 0.015 + px_m, abs(inside + 0.015))) * (1.0 - far);
		pat_off = h * 13.0;
		pat_sign = hs.y < 0.7 ? 1.0 : -1.0;
	}

	vec3 alb;
	vec3 arm;
	vec2 nxy;
	// где выборки — для карты высот в сырость
	vec2 uv = vec2(0.0);
	vec2 uv2 = vec2(0.0);
	float mixk = 0.0;
	if (use_maps) {
		uv = xz / tile_m;
		mat2 rot = mat2(vec2(0.62, 0.78), vec2(-0.78, 0.62));
		mat2 back = mat2(1.0);
		if (slabs) {
			uv = slab_rot * uv + slab_off;
			back = transpose(slab_rot);
		}
		uv += pat_off * pat;
		if (repeat_break == 1) {
			uv2 = uv + pattern_shift;
		} else {
			uv2 = rot * uv * 0.61 + vec2(0.37, 0.71);
		}
		// обе выборки всегда: ветвление по пикселю с явными производными оказалось не быстрее (tools/mall_ground_perf)
		mixk = smoothstep(0.35, 0.65, n_low);
		alb = mix(texture(albedo_tex, uv).rgb, texture(albedo_tex, uv2).rgb, mixk);
		arm = mix(texture(arm_tex, uv).rgb, texture(arm_tex, uv2).rgb, mixk);
		// нормали (OpenGL), синий канал не читаем — восстанавливаем ниже
		vec2 n1 = texture(normal_tex, uv).rg * 2.0 - 1.0;
		vec2 n2 = texture(normal_tex, uv2).rg * 2.0 - 1.0;
		if (repeat_break != 1) {
			n2 = transpose(rot) * n2;
		}
		nxy = back * mix(n1, n2, mixk);
		// приглушить цвет набора (фотоскан бывает рыжим), подвести тон
		float l = dot(alb, vec3(0.3, 0.59, 0.11));
		alb = mix(vec3(l), alb, saturation) * tint;
	} else {
		// процедурное зерно: мелкие камешки заполнителя и средний шум
		vec2 g = xz / grain_m;
		float fine = vnoise(g) * 0.6 + vnoise(g * 2.7 + 3.1) * 0.4;
		float mid = vnoise(xz * 1.7);
		fine = mix(fine, 0.5, far);
		alb = base_color * (1.0 + (fine - 0.5) * 2.0 * grain + (mid - 0.5) * grain * 0.6);
		arm = vec3(1.0, base_rough + (fine - 0.5) * 0.1, 0.0);
		float nx = vnoise(g + vec2(0.5, 0.0)) - vnoise(g - vec2(0.5, 0.0));
		float nz = vnoise(g + vec2(0.0, 0.5)) - vnoise(g - vec2(0.0, 0.5));
		nxy = vec2(nx, -nz) * grain * 2.5 * (1.0 - far);
	}
	// поворот рисунка поворачивает и его нормали, иначе свет не совпадал бы с камешками
	nxy = transpose(texture_turn) * nxy;

	// крупные пятна тона — разные участки укладки, выгоревшее и затёртое
	float macro = mix(n_low, vnoise(xz / macro_m + 3.1), 0.6);
	alb *= 1.0 + (macro - 0.5) * 2.0 * macro_var;

	// плиты: у каждой свой тон, швы тёмные
	if (slabs) {
		alb *= 1.0 + (hash12(slab_id + 1.3) - 0.5) * 2.0 * slab_var;
		alb = mix(alb, alb * 0.45, joint);
		arm.g = mix(arm.g, 1.0, joint);
	}

	// заплата: темнее (свежая) или светлее (старая), чуть глаже; по краю — полоса битума
	alb *= 1.0 + patch_tone * pat * pat_sign;
	arm.g = mix(arm.g, arm.g * 0.92, pat);
	alb = mix(alb, grime_color * 0.8, pat_seam * 0.55);
	arm.g = mix(arm.g, 0.55, pat_seam);

	// залитые трещины: сетка многоугольников (края ячеек Вороного, чуть волнистые) — так трескается
	// старый асфальт и так его заливают битумом; только участками и с разрывами, блестят.
	// Ячейки считаются только на этих участках и не издали.
	if (seal > 0.0 && far < 0.95) {
		float where = smoothstep(1.0 - seal, 1.0 - seal + 0.15, vnoise(xz * 0.03 + 17.0) * 0.65 + vnoise(xz * 0.09) * 0.35);
		float gaps = smoothstep(0.42, 0.55, vnoise(xz * 0.45 + 2.0));
		if (where * gaps > 0.001) {
			vec2 sp = xz / seal_cell + (vec2(vnoise(xz * 0.8), vnoise(xz * 0.8 + 5.1)) - 0.5) * 0.3;
			vec2 cell = floor(sp);
			vec2 f = fract(sp);
			vec2 mr = vec2(0.0);
			vec2 mc = vec2(0.0);
			float md = 8.0;
			for (int j = -1; j <= 1; j++) {
				for (int i = -1; i <= 1; i++) {
					vec2 b = vec2(float(i), float(j));
					vec2 r = b + hash22(cell + b) - f;
					float dd = dot(r, r);
					if (dd < md) {
						md = dd;
						mr = r;
						mc = b;
					}
				}
			}
			// расстояние до края ячейки — до серединных перпендикуляров соседей
			float edge = 8.0;
			for (int j = -1; j <= 1; j++) {
				for (int i = -1; i <= 1; i++) {
					vec2 b = mc + vec2(float(i), float(j));
					vec2 r = b + hash22(cell + b) - f;
					if (dot(mr - r, mr - r) > 0.00001) {
						edge = min(edge, dot(0.5 * (mr + r), normalize(r - mr)));
					}
				}
			}
			float line_k = 1.0 - smoothstep(seal_w * 0.5, seal_w * 0.5 + px_m, edge * seal_cell);
			float seal_k = line_k * where * gaps * 0.8 * (1.0 - far);
			alb = mix(alb, grime_color * 0.7, seal_k);
			arm.g = mix(arm.g, 0.45, seal_k);
		}
	}

	// масляные пятна и накатанное: тёмные, чуть глаже
	if (grime > 0.0) {
		// край пятна чёткий (масло впитывается пятном), внутри — неровно
		float gn = vnoise(xz / grime_m + 23.0) * 0.6 + vnoise(xz * 2.3 / grime_m + 2.0) * 0.4;
		float th = 0.66 - grime * 0.2;
		float gs = smoothstep(th, th + 0.05, gn);
		gs *= 0.5 + 0.5 * vnoise(xz * 3.1 + 4.0);
		alb = mix(alb, grime_color, gs * (0.3 + 0.45 * grime));
		arm.g = mix(arm.g, arm.g * 0.82, gs);
	}

	// швы плитки: тёмное в альбедо — щели, в них земля и мох
	if (joint_dirt > 0.0) {
		float l = dot(alb, vec3(0.3, 0.59, 0.11));
		float slot = 1.0 - smoothstep(0.06, 0.16, l);
		float spread = smoothstep(0.4, 0.7, vnoise(xz * 0.3 + 9.0));
		alb = mix(alb, joint_color, slot * joint_dirt * (0.5 + 0.5 * spread));
	}

	// ---------------------------------------------------------------- сырость
	float rough = clamp(arm.g + rough_add, 0.04, 1.0);
	float film = 0.0;
	float pud = 0.0;
	vec2 rp = vec2(0.0);
	if (wetness > 0.001 || puddles > 0.001) {
		// впадины: карта высот набора, без неё — тёмное в альбедо
		float hgt;
		if (use_maps && has_height) {
			hgt = mix(texture(height_tex, uv).r, texture(height_tex, uv2).r, mixk);
		} else {
			hgt = clamp(dot(alb, vec3(0.3, 0.59, 0.11)) * 2.2, 0.0, 1.0);
		}
		float field = fbm(xz * puddle_freq) * (1.0 - height_bias) + (1.0 - hgt) * height_bias;
		field += (vnoise(xz * 1.3 + 7.0) - 0.5) * 0.12;
		// в швах плит и заплат вода держится раньше
		field += joint * 0.25 + pat_seam * 0.15;
		float open = step(occ_h(wpos.xz), wpos.y + 0.2);
		float w = wetness * open;
		film = clamp((w * 1.35 - (1.0 - field)) / 0.25, 0.0, 1.0);
		film = max(film, smoothstep(0.85, 1.0, w));
		float lvl = 1.0 - puddles * open * 0.5;
		pud = smoothstep(lvl, lvl + 0.03, field) * step(0.001, puddles * open);
		film = max(film, pud);
		vec3 wet_alb = pow(alb, vec3(1.15)) * wet_darken;
		alb = mix(alb, wet_alb, film);
		alb *= mix(1.0, 0.55, pud);
		rough = mix(rough, wet_roughness + rough * 0.12, film);
		rough = mix(rough, puddle_roughness, pud);
		rp = ripples(xz, TIME) * pud * rain * (1.0 - far);
	}
	// издали — не зеркалить мелочь
	rough = mix(rough, max(rough, 0.3 * (1.0 - film) + 0.08), far * 0.5 * (1.0 - pud));
	float mir = max(film * film_mirror * (1.0 - far * 0.3), pud * puddle_mirror);
	ALBEDO = mix(alb, vec3(0.62), mir);
	ROUGHNESS = rough;
	METALLIC = mir;
	SPECULAR = 0.5;
	AO = arm.r;
	AO_LIGHT_AFFECT = 0.25;

	// рельеф: в плёнке слабее, в луже — гладь с рябью
	rp = transpose(texture_turn) * rp;
	float ns = normal_strength * mix(1.0, 0.55, film) * (1.0 - pud) * mix(1.0, 0.35, far);
	vec2 slope = nxy * ns;
	float nz = sqrt(max(1.0 - dot(nxy, nxy), 0.04));
	vec3 nw = normalize(vec3(slope.x - rp.x * 0.35, max(nz, 0.2), -slope.y - rp.y * 0.35));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
