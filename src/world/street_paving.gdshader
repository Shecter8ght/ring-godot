shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Покрытия «Проспекта» (StreetPaving, стенд tools/paving_probe; фото владельца — референсы/prospekt_paving):
// тротуарный кирпичик 200 × 100 ложком и ёлочкой, плиты площади, асфальт, резиновая крошка. Город брошен
// два года, лето: швы забиты песком и землёй, в них трава; у бордюров нанос песка, мох и бурьян; часть
// кирпичиков просела и легла с наклоном; асфальт в трещинах, трава из трещин, начинаются выбоины; пыль.
//
// Раскладка (layout):
//   0 — сплошное покрытие фотосканом (асфальт, крошка, кирпичик фотосканом): повтор ломается второй выборкой
//       (repeat_break 0 — с поворотом, 1 — сдвигом на целое число плиток узора, швы совпадают); швы у
//       фотоскана — по карте высот (низкое — шов);
//   1 — кирпичик ложком (unit_m — длина × ширина, bond — сдвиг ряда в долях длины);
//   2 — ёлочка 90° из кирпичиков 2 : 1 (unit_m.y — ширина, длина — вдвое больше);
//   3 — плиты сеткой (unit_m, bond — сдвиг ряда).
// У процедурной раскладки каждая плитка берёт свой кусок текстуры поверхности (albedo_tex — бетон
// вибропрессованной плитки): повтора нет; своя тон, наклон (видно по бликам и в сырость), просадка; фаска
// по краю; шов — песок и земля, трава. Узор поворачивается на layout_deg + CUSTOM0.z (рад, у вершин — по
// направлению куска: ложок поперёк тротуара на любом плече).
//
// Края куска (бордюр, стена, газон): UV2 — расстояния до краёв x0, z0, CUSTOM0.xy — до x1, z1 (м, по вершинам
// прямоугольника — интерполяция точная), COLOR — сила каждого края (x0, x1, z0, z1). У края — нанос песка,
// трава в швах гуще, мох. Без данных краёв (use_edges = false) — по всему куску ровно.
// Без текстур (use_maps = false) — то же на процедурном зерне: игра собирается без assets/.
// Сырость — как у paved_ground (плёнка, лужи во впадинах и в просевших плитках, рябь, под крышей сухо).

uniform bool use_maps = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D height_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform bool has_height = false;
// мелкий слой: зерно вблизи (асфальт: крупный слой — трещины на 30 м, мелкий — каменная крошка)
uniform bool use_detail = false;
uniform sampler2D detail_albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D detail_normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float detail_m = 2.1;
uniform float detail_k : hint_range(0.0, 1.0) = 0.6;

group_uniforms look;
uniform float tile_m = 3.0;
uniform vec3 tint = vec3(1.0);
uniform float saturation : hint_range(0.0, 1.5) = 1.0;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
uniform float rough_add : hint_range(-0.5, 0.5) = 0.0;
uniform int repeat_break = 0;
uniform vec2 pattern_shift = vec2(0.0);
uniform float macro_var : hint_range(0.0, 0.5) = 0.12;
uniform float macro_m = 18.0;
uniform vec2 detail_fade = vec2(14.0, 60.0);
group_uniforms;

group_uniforms layout;
uniform int layout = 0;
uniform float layout_deg = 0.0;
// плитка: длина × ширина, м (ёлочка — только ширина), сдвиг ряда в долях длины
uniform vec2 unit_m = vec2(0.2, 0.1);
uniform float bond = 0.5;
// шов и фаска, м
uniform float joint_m = 0.004;
uniform float bevel_m = 0.006;
// разброс тона плиток, наклон (рад), доля просевших и насколько темнее шов вокруг них
uniform float unit_var : hint_range(0.0, 0.4) = 0.08;
uniform float unit_tilt : hint_range(0.0, 0.1) = 0.012;
// пятна текстуры поверхности внутри плитки: 1 — как в наборе, меньше — ровнее (у плитки пятна набора на 20 см
// превращаются в «мрамор»; тон плитке даёт unit_var)
uniform float surface_contrast : hint_range(0.0, 1.0) = 1.0;
uniform float sink : hint_range(0.0, 0.5) = 0.04;
// у фотоскана: шов — где карта высот ниже порога
uniform float joint_h : hint_range(0.0, 1.0) = 0.25;
// полосы плиток другого тона (рамки площади): период и ширина по мировой оси (axis 0 — X, 1 — Z), м
uniform float band_period = 0.0;
uniform float band_w = 0.4;
uniform int band_axis = 0;
uniform vec3 band_tint = vec3(0.6);
group_uniforms;

group_uniforms age;
// два года без людей: песок и земля в швах, трава в швах, пыль
uniform vec3 joint_color : source_color = vec3(0.30, 0.26, 0.20);
uniform float joint_weeds : hint_range(0.0, 1.0) = 0.35;
uniform vec3 weed_color : source_color = vec3(0.24, 0.32, 0.12);
uniform vec3 weed_color2 : source_color = vec3(0.36, 0.40, 0.17);
uniform float dust : hint_range(0.0, 1.0) = 0.2;
uniform vec3 dust_color : source_color = vec3(0.55, 0.52, 0.46);
// масляные пятна и накатанное
uniform float grime : hint_range(0.0, 1.0) = 0.0;
uniform vec3 grime_color : source_color = vec3(0.1, 0.095, 0.09);
uniform float grime_m = 3.0;
// заплаты асфальта: доля клеток, размер клетки, тон
uniform float patch_amount : hint_range(0.0, 1.0) = 0.0;
uniform float patch_cell = 9.0;
uniform float patch_tone = -0.2;
// трещины: доля площади, ширина, размер ячейки сетки (асфальт — «сеткой», плиты — поперёк), трава в них
uniform float cracks : hint_range(0.0, 1.0) = 0.0;
uniform float crack_w = 0.012;
uniform float crack_cell = 1.6;
uniform float crack_weeds : hint_range(0.0, 1.0) = 0.4;
// залитые битумом (старый ремонт)
uniform float seal : hint_range(0.0, 1.0) = 0.0;
// начинающиеся выбоины: доля клеток 7 м, радиус, м
uniform float potholes : hint_range(0.0, 1.0) = 0.0;
uniform float pothole_r = 0.45;
group_uniforms;

group_uniforms edges;
uniform bool use_edges = false;
// нанос песка и земли у края: ширина, м, сила; мох у края
uniform float drift_w = 0.45;
uniform float drift : hint_range(0.0, 1.0) = 0.6;
uniform vec3 drift_color : source_color = vec3(0.42, 0.37, 0.29);
uniform float edge_moss : hint_range(0.0, 1.0) = 0.3;
uniform vec3 moss_color : source_color = vec3(0.16, 0.22, 0.07);
group_uniforms;

group_uniforms fallback;
uniform vec3 base_color : source_color = vec3(0.45, 0.44, 0.42);
uniform float grain : hint_range(0.0, 0.5) = 0.1;
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
// доля луж и зеркальности у этого покрытия (газон — почти без луж, вода уходит в землю)
uniform float puddle_k : hint_range(0.0, 1.0) = 1.0;
group_uniforms;

uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;
varying vec4 edge_d;
varying vec4 edge_w;
varying float lay_rot;

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
mat2 rot2(float a) {
	float c = cos(a);
	float s = sin(a);
	return mat2(vec2(c, s), vec2(-s, c));
}
// расстояние до края ячейки Вороного (трещины): ячейки 1 × 1, f — точка в ячейках
float voronoi_edge(vec2 sp) {
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
	return edge;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	edge_d = vec4(UV2.x, CUSTOM0.x, UV2.y, CUSTOM0.y);
	edge_w = COLOR;
	lay_rot = CUSTOM0.z;
}

void fragment() {
	vec2 xz = wpos.xz;
	float dist = length(CAMERA_POSITION_WORLD - wpos);
	float far = smoothstep(detail_fade.x, detail_fade.y, dist);
	float px_m = max(length(fwidth(xz)), 0.0008);
	float n_low = vnoise(xz * 0.045 + 5.3) * 0.65 + vnoise(xz * 0.11 + 1.7) * 0.35;

	// ---------------------------------------------------------------- раскладка
	float ang = radians(layout_deg) + lay_rot;
	mat2 to_pat = rot2(-ang);
	mat2 to_world = rot2(ang);
	vec2 p = to_pat * xz;
	vec2 dpx = to_pat * dFdx(xz);
	vec2 dpy = to_pat * dFdy(xz);
	vec3 unit_id = vec3(0.0);
	vec2 lm = vec2(0.0);          // точка в плитке, м (x — вдоль длинной стороны)
	vec2 usize = unit_m;
	bool turned = false;          // плитка ёлочки «стоя»: её длинная сторона — по оси y узора
	vec2 ucenter = vec2(0.0);     // середина плитки в осях узора, м
	if (layout == 1 || layout == 3) {
		float row = floor(p.y / unit_m.y);
		float off = mod(row, 2.0) * bond * unit_m.x;
		float col = floor((p.x + off) / unit_m.x);
		lm = vec2(p.x + off - col * unit_m.x, p.y - row * unit_m.y);
		unit_id = vec3(col, row, 0.0);
		ucenter = vec2((col + 0.5) * unit_m.x - off, (row + 0.5) * unit_m.y);
	} else if (layout == 2) {
		float w = unit_m.y;
		usize = vec2(2.0 * w, w);
		vec2 q0 = p / w;
		float mf = floor((q0.x + q0.y) * 0.5);
		float nf = floor((q0.x - q0.y) * 0.25);
		for (int dm = -1; dm <= 1; dm++) {
			for (int dn = -1; dn <= 1; dn++) {
				float m = mf + float(dm);
				float n = nf + float(dn);
				vec2 o = vec2(m + 2.0 * n, m - 2.0 * n);
				vec2 q = q0 - o;
				if (q.x >= 0.0 && q.x < 2.0 && q.y >= 0.0 && q.y < 1.0) {
					unit_id = vec3(m, n, 0.0);
					lm = q * w;
					turned = false;
					ucenter = (o + vec2(1.0, 0.5)) * w;
				}
				vec2 r = q - vec2(2.0, -1.0);
				if (r.x >= 0.0 && r.x < 1.0 && r.y >= 0.0 && r.y < 2.0) {
					unit_id = vec3(m, n, 1.0);
					lm = vec2(r.y, r.x) * w;
					turned = true;
					ucenter = (o + vec2(2.5, 0.0)) * w;
				}
			}
		}
	}
	bool tiled = layout != 0;
	float uh = hash12(unit_id.xy * vec2(1.0, 1.7) + unit_id.z * 13.1 + 0.37);
	float uh2 = hash12(unit_id.xy + unit_id.z * 7.7 + 5.1);
	// до края плитки и куда край (в осях узора)
	float ed = 1.0;
	vec2 edir = vec2(0.0);
	if (tiled) {
		float dx = min(lm.x, usize.x - lm.x);
		float dy = min(lm.y, usize.y - lm.y);
		ed = min(dx, dy);
		vec2 dl = dx < dy ? vec2(sign(lm.x - usize.x * 0.5), 0.0) : vec2(0.0, sign(lm.y - usize.y * 0.5));
		edir = turned ? dl.yx : dl;
	}

	// ---------------------------------------------------------------- поверхность
	// nxy — наклон нормали в мировых осях (x, z); карты нормалей (OpenGL: зелёный — вверх по картинке, к −V)
	// переводятся в мир: (r, −g) в осях выборки, затем поворот
	vec3 alb;
	vec3 arm;
	vec2 nxy;
	vec2 uv = vec2(0.0);
	vec2 uv2 = vec2(0.0);
	float mixk = 0.0;
	float hgt = 0.5;
	if (use_maps) {
		if (tiled) {
			// свой кусок текстуры у каждой плитки; производные — от непрерывной точки узора (без швов мипов)
			vec2 local = lm + hash22(unit_id.xy + unit_id.z * 3.3) * 37.0;
			uv = local / tile_m;
			vec2 gx = (turned ? dpx.yx : dpx) / tile_m;
			vec2 gy = (turned ? dpy.yx : dpy) / tile_m;
			alb = textureGrad(albedo_tex, uv, gx, gy).rgb;
			alb = mix(textureLod(albedo_tex, uv, 11.0).rgb, alb, surface_contrast);
			arm = textureGrad(arm_tex, uv, gx, gy).rgb;
			vec2 n1 = textureGrad(normal_tex, uv, gx, gy).rg * 2.0 - 1.0;
			n1.y = -n1.y;
			nxy = turned ? n1.yx : n1;
			if (has_height) {
				hgt = textureGrad(height_tex, uv, gx, gy).r;
			}
		} else {
			uv = p / tile_m;
			mat2 rot = mat2(vec2(0.62, 0.78), vec2(-0.78, 0.62));
			if (repeat_break == 1) {
				uv2 = uv + pattern_shift;
			} else {
				uv2 = rot * uv * 0.61 + vec2(0.37, 0.71);
			}
			mixk = smoothstep(0.35, 0.65, n_low);
			alb = mix(texture(albedo_tex, uv).rgb, texture(albedo_tex, uv2).rgb, mixk);
			arm = mix(texture(arm_tex, uv).rgb, texture(arm_tex, uv2).rgb, mixk);
			vec2 n1 = texture(normal_tex, uv).rg * 2.0 - 1.0;
			vec2 n2 = texture(normal_tex, uv2).rg * 2.0 - 1.0;
			n1.y = -n1.y;
			n2.y = -n2.y;
			if (repeat_break != 1) {
				// направление в осях второй выборки → в оси первой
				n2 = transpose(rot) * n2;
			}
			nxy = mix(n1, n2, mixk);
			if (has_height) {
				hgt = mix(texture(height_tex, uv).r, texture(height_tex, uv2).r, mixk);
			}
		}
		float l = dot(alb, vec3(0.3, 0.59, 0.11));
		alb = mix(vec3(l), alb, saturation) * tint;
		// нормали в осях узора → в мир
		nxy = to_world * nxy;
		if (use_detail) {
			vec2 duv = xz / detail_m;
			vec3 dalb = texture(detail_albedo_tex, duv).rgb;
			vec3 dmean = textureLod(detail_albedo_tex, duv, 10.0).rgb;
			float dk = detail_k * (1.0 - far);
			alb *= mix(vec3(1.0), dalb / max(dmean, vec3(0.02)), dk);
			vec2 dn = texture(detail_normal_tex, duv).rg * 2.0 - 1.0;
			nxy += vec2(dn.x, -dn.y) * dk;
		}
	} else {
		vec2 g = xz / grain_m;
		float fine = vnoise(g) * 0.6 + vnoise(g * 2.7 + 3.1) * 0.4;
		float mid = vnoise(xz * 1.7);
		fine = mix(fine, 0.5, far);
		alb = base_color * (1.0 + (fine - 0.5) * 2.0 * grain + (mid - 0.5) * grain * 0.6);
		arm = vec3(1.0, base_rough + (fine - 0.5) * 0.1, 0.0);
		float nx = vnoise(g + vec2(0.5, 0.0)) - vnoise(g - vec2(0.5, 0.0));
		float nz = vnoise(g + vec2(0.0, 0.5)) - vnoise(g - vec2(0.0, 0.5));
		nxy = -vec2(nx, nz) * grain * 2.5 * (1.0 - far);
		hgt = fine;
	}

	// крупные пятна тона
	float macro = mix(n_low, vnoise(xz / macro_m + 3.1), 0.6);
	alb *= 1.0 + (macro - 0.5) * 2.0 * macro_var;

	// ---------------------------------------------------------------- плитки: тон, полосы, наклон, просадка, фаска, шов
	float joint = 0.0;
	float sunk = 0.0;
	if (tiled) {
		alb *= 1.0 + (uh - 0.5) * 2.0 * unit_var;
		if (band_period > 0.0) {
			vec2 cw = to_world * ucenter;
			float c = band_axis == 0 ? cw.x : cw.y;
			if (mod(c, band_period) < band_w) {
				alb *= band_tint;
			}
		}
		sunk = step(1.0 - sink, uh2);
		// наклон плитки: у просевших сильнее, к соседу вниз
		vec2 tilt = (hash22(unit_id.xy * 1.3 + unit_id.z + 9.0) - 0.5) * 2.0 * unit_tilt * (1.0 + sunk * 2.5);
		nxy += to_world * tilt * (1.0 - far * 0.7);
		// фаска: у края плитки нормаль наружу, край чуть темнее (тень фаски); шов — песок, земля, трава
		float jh = joint_m * 0.5 * (1.0 + sunk * 0.8);
		float bevel = 1.0 - smoothstep(jh, jh + bevel_m, ed);
		nxy += to_world * edir * bevel * 0.55 * (1.0 - far);
		alb *= 1.0 - bevel * 0.12;
		joint = 1.0 - smoothstep(jh - px_m * 0.5, jh + px_m * 0.5, ed);
		// издали шов тоньше пикселя — по доле площади
		joint = mix(joint, clamp(joint_m * 2.0 / max(px_m, 0.001), 0.0, 0.6), far);
	} else if (has_height && use_maps) {
		// у фотоскана шов — низкое в карте высот
		joint = 1.0 - smoothstep(joint_h - 0.06, joint_h + 0.06, hgt);
	}

	// ---------------------------------------------------------------- края: нанос, мох
	float edge_k = 0.0;
	if (use_edges) {
		vec4 dd = edge_d;
		float wn = vnoise(xz * 1.9 + 4.0) * 0.6 + vnoise(xz * 6.0) * 0.4;
		float w = drift_w * (0.55 + wn * 0.9);
		vec4 k = edge_w * (vec4(1.0) - smoothstep(vec4(0.0), vec4(w), dd));
		edge_k = max(max(k.x, k.y), max(k.z, k.w));
	}

	// ---------------------------------------------------------------- заплаты
	float pat_seam = 0.0;
	if (patch_amount > 0.0) {
		vec2 q = xz;
		vec2 c = floor(q / patch_cell);
		vec2 h = hash22(c + 41.3);
		vec2 hs = hash22(c + 7.7);
		vec2 half_size = mix(vec2(0.18), vec2(0.42), hs) * patch_cell;
		vec2 center = (c + 0.5) * patch_cell + (hash22(c + 2.9) - 0.5) * (patch_cell - 2.0 * half_size);
		vec2 d = abs(q - center) - half_size;
		float inside = max(d.x, d.y);
		float on = step(h.x, patch_amount);
		float pat = on * (1.0 - smoothstep(-px_m, px_m, inside));
		pat_seam = on * (1.0 - smoothstep(0.015, 0.015 + px_m, abs(inside + 0.015))) * (1.0 - far);
		alb *= 1.0 + patch_tone * pat * (hs.y < 0.7 ? 1.0 : -1.0);
		alb = mix(alb, grime_color * 0.8, pat_seam * 0.55);
		arm.g = mix(arm.g, 0.55, pat_seam);
	}

	// ---------------------------------------------------------------- трещины (открытые, с травой) и залитые
	float crack = 0.0;
	float crack_green = 0.0;
	if ((cracks > 0.0 || seal > 0.0) && far < 0.97) {
		float amount = max(cracks, seal);
		float where = smoothstep(1.0 - amount, 1.0 - amount + 0.18, vnoise(xz * 0.04 + 17.0) * 0.6 + vnoise(xz * 0.13) * 0.4);
		// у края (бордюр) асфальт отрывается вдоль — трещина ближе к краю
		where = max(where, edge_k * cracks * 0.8);
		float gaps = smoothstep(0.38, 0.52, vnoise(xz * 0.5 + 2.0));
		if (where * gaps > 0.001) {
			vec2 warp = (vec2(vnoise(xz * 0.9), vnoise(xz * 0.9 + 5.1)) - 0.5) * 0.35;
			float e = voronoi_edge(xz / crack_cell + warp) * crack_cell;
			float wv = crack_w * (0.4 + 1.2 * vnoise(xz * 3.0 + 1.0));
			float line_k = 1.0 - smoothstep(wv * 0.5, wv * 0.5 + px_m, e);
			float k = line_k * where * gaps * (1.0 - far);
			if (cracks > 0.0) {
				crack = k;
				crack_green = k * smoothstep(1.0 - crack_weeds, 1.0 - crack_weeds + 0.2, vnoise(xz * 0.7 + 31.0));
				// кромка трещины выкрошилась: светлее, крупнее зерно
				float lip = (1.0 - smoothstep(wv * 0.5, wv * 0.5 + 0.02, e)) * where * gaps * (1.0 - far) * (1.0 - line_k);
				alb *= 1.0 + lip * 0.12;
			} else {
				alb = mix(alb, grime_color * 0.7, k * 0.8);
				arm.g = mix(arm.g, 0.45, k * 0.8);
			}
		}
	}

	// ---------------------------------------------------------------- выбоины: выкрошенное покрытие до щебня, чаша
	float pit = 0.0;
	if (potholes > 0.0) {
		vec2 c = floor(xz / 7.0);
		vec2 h = hash22(c + 77.0);
		if (h.x < potholes) {
			vec2 center = (c + 0.2 + hash22(c + 3.0) * 0.6) * 7.0;
			vec2 d = xz - center;
			float rr = pothole_r * (0.6 + h.y * 0.8);
			float ragged = (vnoise(xz * 7.0 + c) - 0.5) * 0.35 + (vnoise(xz * 19.0) - 0.5) * 0.12;
			float r = length(d * vec2(1.0, 1.0 + h.y * 0.6)) / rr + ragged;
			pit = 1.0 - smoothstep(0.92, 1.0, r);
			float rim = smoothstep(0.7, 1.0, r) * pit;
			float stones = vnoise(xz * 38.0) * 0.6 + vnoise(xz * 90.0) * 0.4;
			alb = mix(alb, vec3(0.16, 0.15, 0.14) * (0.55 + stones * 0.9), pit * 0.85);
			arm.g = mix(arm.g, 0.95, pit);
			nxy += (r > 0.001 ? -normalize(d) : vec2(0.0)) * rim * 0.9 * (1.0 - far);
			nxy += (vec2(vnoise(xz * 38.0 + 1.0), vnoise(xz * 38.0 + 7.0)) - 0.5) * pit * 0.8 * (1.0 - far);
		}
	}

	// ---------------------------------------------------------------- масляные пятна
	if (grime > 0.0) {
		float gn = vnoise(xz / grime_m + 23.0) * 0.6 + vnoise(xz * 2.3 / grime_m + 2.0) * 0.4;
		float th = 0.66 - grime * 0.2;
		float gs = smoothstep(th, th + 0.05, gn);
		gs *= 0.5 + 0.5 * vnoise(xz * 3.1 + 4.0);
		alb = mix(alb, grime_color, gs * (0.3 + 0.45 * grime));
		arm.g = mix(arm.g, arm.g * 0.82, gs);
	}

	// ---------------------------------------------------------------- шов, трава, нанос, мох, пыль
	float weed_n = vnoise(xz * 2.2 + 11.0) * 0.7 + vnoise(xz * 9.0 + 3.0) * 0.3;
	vec3 weed = mix(weed_color, weed_color2, vnoise(xz * 4.0 + 2.0));
	// шов: песок с землёй; трава — пятнами, гуще у края куска
	float jw = clamp(joint_weeds * (0.6 + edge_k * 1.4), 0.0, 1.0);
	float joint_green = smoothstep(1.0 - jw, 1.0 - jw + 0.25, weed_n);
	vec3 jcol = mix(joint_color * (0.75 + 0.5 * vnoise(xz * 13.0)), weed, joint_green);
	alb = mix(alb, jcol, joint);
	arm.g = mix(arm.g, 1.0, joint);
	arm.r = mix(arm.r, arm.r * 0.6, joint * (1.0 - joint_green));
	// трещина: тень и земля внутри, трава местами
	alb = mix(alb, mix(vec3(0.035, 0.03, 0.025), weed, crack_green / max(crack, 0.001)), crack);
	arm.g = mix(arm.g, 1.0, crack);
	// нанос у края: песок поверх (рыхлый, матовый), в нём мох и трава
	if (use_edges && edge_k > 0.001) {
		float sand = edge_k * drift * smoothstep(0.15, 0.6, vnoise(xz * 3.3 + 8.0) * 0.5 + edge_k * 0.7);
		vec3 dcol = drift_color * (0.8 + 0.4 * vnoise(xz * 17.0));
		float moss = edge_k * edge_moss * smoothstep(0.45, 0.75, vnoise(xz * 1.6 + 21.0));
		alb = mix(alb, dcol, sand);
		alb = mix(alb, moss_color * (0.7 + 0.6 * vnoise(xz * 11.0)), moss);
		arm.g = mix(arm.g, 1.0, max(sand, moss));
		nxy *= 1.0 - sand * 0.7;
	}
	// пыль двух лет: светлее и серее там, где не ходили и не стекала вода
	float dk = dust * smoothstep(0.25, 0.8, vnoise(xz * 0.35 + 50.0) * 0.6 + vnoise(xz * 1.4) * 0.4);
	alb = mix(alb, dust_color * (0.85 + 0.3 * vnoise(xz * 5.0)), dk * 0.35);
	arm.g = mix(arm.g, max(arm.g, 0.9), dk);

	// ---------------------------------------------------------------- сырость
	float rough = clamp(arm.g + rough_add, 0.04, 1.0);
	float film = 0.0;
	float pud = 0.0;
	vec2 rp = vec2(0.0);
	if (wetness > 0.001 || puddles > 0.001) {
		float h = has_height || !use_maps ? hgt : clamp(dot(alb, vec3(0.3, 0.59, 0.11)) * 2.2, 0.0, 1.0);
		float field = fbm(xz * puddle_freq) * (1.0 - height_bias) + (1.0 - h) * height_bias;
		field += (vnoise(xz * 1.3 + 7.0) - 0.5) * 0.12;
		// вода держится в швах, просевших плитках, выбоинах и трещинах
		field += joint * 0.25 + sunk * 0.1 + pit * 0.6 + crack * 0.3 + pat_seam * 0.15;
		float open = step(occ_h(xz), wpos.y + 0.2);
		float w = wetness * open;
		film = clamp((w * 1.35 - (1.0 - field)) / 0.25, 0.0, 1.0);
		film = max(film, smoothstep(0.85, 1.0, w));
		float lvl = 1.0 - puddles * open * 0.5;
		pud = smoothstep(lvl, lvl + 0.03, field) * step(0.001, puddles * open) * puddle_k;
		film = max(film, pud) * mix(0.6, 1.0, puddle_k);
		vec3 wet_alb = pow(alb, vec3(1.15)) * wet_darken;
		alb = mix(alb, wet_alb, film);
		alb *= mix(1.0, 0.55, pud);
		rough = mix(rough, wet_roughness + rough * 0.12, film);
		rough = mix(rough, puddle_roughness, pud);
		rp = ripples(xz, TIME) * pud * rain * (1.0 - far);
	}
	rough = mix(rough, max(rough, 0.3 * (1.0 - film) + 0.08), far * 0.5 * (1.0 - pud));
	float mir = max(film * film_mirror * (1.0 - far * 0.3), pud * puddle_mirror);
	ALBEDO = mix(alb, vec3(0.62), mir);
	ROUGHNESS = rough;
	METALLIC = mir;
	SPECULAR = 0.5;
	AO = arm.r;
	AO_LIGHT_AFFECT = 0.25;

	float ns = normal_strength * mix(1.0, 0.55, film) * (1.0 - pud) * mix(1.0, 0.35, far);
	vec2 slope = nxy * ns;
	float nz = sqrt(max(1.0 - dot(nxy, nxy), 0.04));
	vec3 nw = normalize(vec3(slope.x - rp.x * 0.35, max(nz, 0.2), slope.y - rp.y * 0.35));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
