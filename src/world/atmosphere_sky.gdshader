shader_type sky;
render_mode use_half_res_pass;
// Расчётное небо смены суток (DayCycle, режим «расчёт»): цвет неба — рассеяние солнечного света в
// атмосфере (модель Hillaire: Рэлей, Ми, озон; таблицы пропускания и многократного рассеяния —
// data/sky_atmosphere.json из tools/gen_sky_atmosphere.py). Луч взгляда маршится в половине разрешения
// (небо гладкое) вместе с объёмным слоем облаков, солнце диском, Луна и звёзды — в полном. Яркость (gain),
// низ и поправка оттенка отражений — из подгонки по высоте солнца и погоде: свет на земле — как от неба
// из панорам. Облака — в той же карте отражений: светят на землю и видны в лужах.
// Ночь — общий слой sky_night.gdshaderinc. Параметры ставит AtmosphereSky. Без use_debanding: его шум
// в проходе пониженного разрешения после усиления сумерек (×10⁴) заливал небо.

#include "res://src/world/sky_night.gdshaderinc"

// ---- таблицы: пропускание (до верха атмосферы, параметризация Брюнетона) и многократное рассеяние
uniform sampler2D t_lut : filter_linear, repeat_disable;
uniform sampler2D ms_lut : filter_linear, repeat_disable;
// ---- атмосфера, км (те же числа, что в генераторе таблиц)
uniform float r_ground = 6360.0;
uniform float r_top = 6460.0;
uniform vec3 ray_s = vec3(5.802e-3, 13.558e-3, 33.1e-3);
uniform float ray_h = 8.0;
uniform float mie_s = 3.996e-3;
uniform float mie_e = 4.40e-3;
uniform float mie_h = 1.2;
uniform float mie_g = 0.8;
uniform vec3 oz_a = vec3(0.650e-3, 1.881e-3, 0.085e-3);
uniform float oz_c = 25.0;
uniform float oz_w = 15.0;
uniform float view_h = 0.2;
uniform int steps = 32;

// ---- солнце и погода
// направление на солнце (мир)
uniform vec3 sun_dir = vec3(0.0, 0.5, -0.86);
// дымка: во сколько раз больше аэрозоля Ми
uniform float mie_k = 1.0;
// яркость атмосферы при солнце силой 1 → как прежнее небо на этой высоте солнца
uniform float gain = 30.0;
// пелена туч без облачного слоя (veil — доля, небо CIE: к горизонту втрое темнее зенита)
uniform vec3 oc_zenith = vec3(0.3);
uniform float veil : hint_range(0.0, 1.0) = 0.0;
// оттенок для карты отражений и рассеянного света (только в ней)
uniform vec3 amb_tint = vec3(1.0);
// видимое небо при низком солнце темнее карты отражений (та сведена к облачным панорамам и при чистом
// небе на закате белёсая); 1 — как она
uniform float view_k = 1.0;
// нижняя полусфера, ровная яркость; переход от горизонта — ground_blend, °
uniform vec3 ground_col = vec3(0.1);
uniform float ground_blend = 3.0;
// солнце: угловой размер, °; не ярче sun_clamp (цвет сохраняется)
uniform float sun_size = 0.53;
uniform float sun_clamp = 40.0;
uniform float radiance_clamp = 2.5;

// ---- облака: объёмный слой над глазом от cloud_base до cloud_top, км. Шумы (карта покрытия, форма,
// детали) генерирует движок — AtmosphereSky; xz шумов — км по карте, ветер — cloud_offset.
uniform bool clouds_on = false;
uniform sampler2D cloud_cover : filter_linear_mipmap, repeat_enable;
uniform sampler3D cloud_shape : filter_linear, repeat_enable;
uniform sampler3D cloud_detail : filter_linear, repeat_enable;
// доля неба под облаками (1 — сплошные тучи)
uniform float cloud_coverage = 0.4;
// ослабление света в облаке плотности 1, 1/км
uniform float cloud_sigma = 30.0;
uniform float cloud_base = 1.4;
uniform float cloud_top = 3.4;
uniform vec2 cloud_offset = vec2(0.0);
// размер плиток шума, км
uniform float cover_tile = 30.0;
uniform float shape_tile = 9.0;
uniform float detail_tile = 1.6;
// насколько детали выедают края
uniform float detail_k = 0.4;
// свет неба на облака сверху (итоговые единицы); снизу — доля amb_bottom (свет от земли)
uniform vec3 cloud_amb = vec3(0.4);
uniform float amb_bottom = 0.55;
// множитель солнца на облаках
uniform float cloud_sun = 1.0;
// дальше cloud_far, км, облаков нет; дымка до облака — на cloud_haze, км
uniform float cloud_far = 70.0;
uniform float cloud_haze = 35.0;
uniform int cloud_steps = 48;
// ночью облака — тёмные силуэты, у горизонта чуть подсвечены (огни округи); в сплошных тучах — как
// пасмурная ночь неба из панорам, редкие облака лишь чуть светлее неба
uniform vec3 night_cloud = vec3(0.012, 0.013, 0.016);
uniform vec3 night_cloud_hz = vec3(0.03, 0.031, 0.034);

// ---- непогода (Balance.SKY_CALC по погоде): сплошные тучи неровной толщины (deck_var), рваный низ
// (base_rag, км), низкие клочья (scud_*: свой слой, свой ветер), полосы дождя вдали (shafts), молния
uniform float deck_var = 0.0;
uniform float base_rag = 0.0;
uniform float scud_coverage = 0.0;
uniform float scud_base = 0.25;
uniform float scud_top = 0.6;
uniform vec2 scud_offset = vec2(0.0);
uniform int scud_steps = 16;
uniform float shafts = 0.0;
// молния: сила вспышки (0 — нет), где в тучах (как q облаков: км по карте и над глазом), цвет, ядро и
// его радиус, км, общий отсвет неба
uniform float flash = 0.0;
uniform vec3 flash_q = vec3(0.0, 2.0, 5.0);
uniform vec3 flash_color = vec3(0.75, 0.82, 1.0);
uniform float flash_core = 25.0;
uniform float flash_radius = 0.9;
uniform float flash_amb = 0.25;
// канал молнии до земли (AtmosphereSky.lightning): ломаная в картинной плоскости — проекция из глаза на
// плоскость с осью bolt_c (bolt_r — вправо, bolt_u — вверх; отрезки остаются прямыми). Отрезки bolt_seg
// (xy — начало, zw — конец), их сила bolt_k (x, y — у концов, z — толщина, w — 1 у ветвей), bolt_box — рамка
// с ореолом. bolt — яркость канала сейчас, bolt_branch — ветвей; bolt_w — полуширина канала, bolt_glow —
// радиус ореола (в тех же долях), bolt_dist — до канала, км: низкие клочья перед ним его заслоняют.
uniform int bolt_n = 0;
uniform float bolt = 0.0;
uniform float bolt_branch = 0.0;
uniform vec3 bolt_c = vec3(0.0, 0.0, -1.0);
uniform vec3 bolt_r = vec3(1.0, 0.0, 0.0);
uniform vec3 bolt_u = vec3(0.0, 1.0, 0.0);
uniform vec4 bolt_box = vec4(0.0);
uniform vec4 bolt_seg[64];
uniform vec4 bolt_k[64];
uniform float bolt_w = 0.0003;
uniform float bolt_glow = 0.005;
uniform float bolt_dist = 5.0;
uniform float bolt_core = 60.0;
uniform float bolt_halo = 3.0;

vec2 lut_uv(vec2 x, sampler2D tex) {
	vec2 size = vec2(textureSize(tex, 0));
	return 0.5 / size + clamp(x, 0.0, 1.0) * (1.0 - 1.0 / size);
}

// пропускание от точки на высоте r (от центра Земли) под косинусом mu к зениту — до верха атмосферы
vec3 transmittance(float r, float mu) {
	float hh = sqrt(r_top * r_top - r_ground * r_ground);
	float rho = sqrt(max(r * r - r_ground * r_ground, 0.0));
	float d = max(-r * mu + sqrt(max(r * r * (mu * mu - 1.0) + r_top * r_top, 0.0)), 0.0);
	float dmin = r_top - r;
	float dmax = rho + hh;
	return texture(t_lut, lut_uv(vec2((d - dmin) / max(dmax - dmin, 1e-6), rho / hh), t_lut)).rgb;
}

vec3 multiscatter(float r, float mu_s) {
	return texture(ms_lut, lut_uv(vec2(mu_s * 0.5 + 0.5, (r - r_ground) / (r_top - r_ground)), ms_lut)).rgb;
}

// солнце не за Землёй (мягкая граница — по размеру диска)
float sun_seen(float r, float mu_s) {
	float mu_h = -sqrt(max(1.0 - (r_ground / r) * (r_ground / r), 0.0));
	return smoothstep(mu_h - 0.005, mu_h + 0.005, mu_s);
}

float phase_r(float c) {
	return 3.0 / (16.0 * PI) * (1.0 + c * c);
}

float phase_m(float c) {
	float g = mie_g;
	float k = 3.0 / (8.0 * PI) * (1.0 - g * g) / (2.0 + g * g);
	return k * (1.0 + c * c) / pow(max(1.0 + g * g - 2.0 * g * c, 1e-6), 1.5);
}

vec3 atmosphere(vec3 d) {
	float r0 = r_ground + view_h;
	// ниже видимого горизонта луч упёрся бы в землю — берём луч вдоль горизонта (низ рисует sky())
	float mu_h = -sqrt(max(1.0 - (r_ground / r0) * (r_ground / r0), 0.0)) + 0.002;
	vec3 dir = d;
	if (dir.y < mu_h) {
		vec2 hz = vec2(d.x, d.z);
		hz = length(hz) > 1e-5 ? normalize(hz) : vec2(0.0, -1.0);
		float s = sqrt(1.0 - mu_h * mu_h);
		dir = vec3(hz.x * s, mu_h, hz.y * s);
	}
	vec3 sd = normalize(sun_dir);
	float tmax = -r0 * dir.y + sqrt(max(r0 * r0 * (dir.y * dir.y - 1.0) + r_top * r_top, 0.0));
	float cv = dot(dir, sd);
	float pr = phase_r(cv);
	float pm = phase_m(cv);
	vec3 l = vec3(0.0);
	vec3 thr = vec3(1.0);
	float t_prev = 0.0;
	for (int i = 0; i < steps; i++) {
		// шаги гуще у глаза: горизонт и дымка
		float f = (float(i) + 1.0) / float(steps);
		float t_new = tmax * f * f;
		float dt = t_new - t_prev;
		float t = 0.5 * (t_new + t_prev);
		t_prev = t_new;
		vec3 p = dir * t + vec3(0.0, r0, 0.0);
		float r = length(p);
		float h = max(r - r_ground, 0.0);
		float mus = dot(p / r, sd);
		float dr = exp(-h / ray_h);
		float dm = exp(-h / mie_h) * mie_k;
		float doz = max(0.0, 1.0 - abs(h - oz_c) / oz_w);
		vec3 sr = ray_s * dr;
		vec3 sm = vec3(mie_s * dm);
		vec3 se = sr + vec3(mie_e * dm) + oz_a * doz;
		vec3 tsun = transmittance(r, mus) * sun_seen(r, mus);
		vec3 sc = tsun * (sr * pr + sm * pm) + multiscatter(r, mus) * (sr + sm);
		vec3 st = exp(-se * dt);
		l += thr * (sc - sc * st) / max(se, vec3(1e-9));
		thr *= st;
	}
	return l;
}

float hg(float c, float g) {
	float g2 = g * g;
	return (1.0 - g2) / (4.0 * PI * pow(max(1.0 + g2 - 2.0 * g * c, 1e-4), 1.5));
}

// Плотность облака 0..1 в точке q (x, z — км по карте с ветром; y — км над глазом). Карта покрытия решает,
// где облакам быть, профиль — их высоту (чем гуще покрытие, тем выше башни), форма — сами клубы,
// детали выедают края.
float cloud_density(vec3 q, float detail) {
	// рваный низ: основание гуляет по крупным ячейкам (км), а не идёт ровной плоскостью
	float rag = base_rag > 0.0 ? (texture(cloud_detail, vec3(q.x, 0.0, q.z) / (detail_tile * 2.5)).r - 0.5) * base_rag : 0.0;
	float hf = (q.y - cloud_base - rag) / (cloud_top - cloud_base);
	if (hf <= 0.0 || hf >= 1.0) {
		return 0.0;
	}
	float t = 1.0 - cloud_coverage;
	float cov = texture(cloud_cover, q.xz / cover_tile).r;
	float wc = smoothstep(t - 0.08, t + 0.18, cov);
	if (wc <= 0.0) {
		return 0.0;
	}
	// сплошные тучи неровной толщины: где карта покрытия ниже — слой тоньше (светлее, солнце угадывается)
	float thick = mix(1.0, mix(0.35, 1.0, smoothstep(0.25, 0.75, cov)), deck_var);
	float top_f = mix(0.45, 1.0, wc) * thick;
	float prof = smoothstep(0.0, 0.12, hf) * (1.0 - smoothstep(top_f - 0.35, top_f, hf));
	float k = wc * prof;
	// клубы: плавный шум формы с ячейками (Перлин — Ворли) — края «цветной капустой», а не ватой
	float sh = mix(texture(cloud_shape, q / shape_tile).r, texture(cloud_detail, q / (shape_tile * 0.5)).r, 0.35);
	float base = clamp((sh - (1.0 - k)) / max(k, 0.05), 0.0, 1.0);
	if (detail > 0.0 && base > 0.0) {
		// у рваного низа детали выедают сильнее — клочья
		float ero_k = detail_k * mix(1.0 + base_rag * 2.0, 1.0, smoothstep(0.0, 0.25, hf));
		float ero = (1.0 - texture(cloud_detail, q / detail_tile).r) * ero_k * detail;
		base = clamp((base - ero) / max(1.0 - ero, 0.05), 0.0, 1.0);
	}
	return base;
}

// Облака по лучу d над атмосферой atm (её свет за облаками): rgb — итог неба с облаками, a — сколько неба
// видно сквозь них (звёзды, солнце, Луна). sun_k — множитель солнца на облаках (в карте отражений при
// низком солнце — как у видимого неба, иначе розовые облака зари слишком светят на землю).
vec4 clouds(vec3 d, vec3 atm, vec2 cam_km, float sun_k) {
	float rc = r_ground + view_h;
	// у горизонта и ниже — дымка: при сплошных тучах серая, как их низ (свет сверху там приглушён толщей,
	// 0.65 — в среднем), ясного неба под ними не видно
	float oc = cloud_coverage * cloud_coverage;
	vec3 hz = mix(atm, cloud_amb * amb_bottom * 0.65, oc);
	if (d.y <= 0.0) {
		return vec4(hz, 1.0 - oc);
	}
	float rb = rc + cloud_base;
	float rtop = rc + cloud_top;
	float t0 = -rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rb * rb, 0.0));
	float t1 = min(-rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rtop * rtop, 0.0)), cloud_far);
	if (t0 >= t1) {
		return vec4(atm, 1.0);
	}
	vec3 sd = normalize(sun_dir);
	float cs = dot(d, sd);
	// шаги — между сферами постоянной высоты (через dh км), без случайного сдвига: точки выборки сидят на
	// одних высотах при любом направлении — при покачивании взгляда края облаков не «кипят» (любой шум
	// в шагах мерцал: прицел качается на доли пикселя); полосы шагов гасит их частота (cloud_steps)
	float dh = (cloud_top - cloud_base) / float(cloud_steps);
	float t_prev = t0;
	vec3 l = vec3(0.0);
	float tr = 1.0;
	float dsum = 0.0;
	float wsum = 0.0;
	// глубоко в туче (сквозь неё видно меньше трети) свет и затенение берутся с прошлого шага, деталей нет:
	// вклад таких шагов мал, а в сплошных тучах это половина работы
	float tau_last = 0.0;
	float occ_last = 1.0;
	for (int i = 0; i < cloud_steps; i++) {
		if (t_prev >= t1) {
			break;
		}
		float rk = rb + dh * (float(i) + 1.0);
		float t_next = min(-rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rk * rk, 0.0)), t1);
		float dt = t_next - t_prev;
		float t = 0.5 * (t_prev + t_next);
		t_prev = t_next;
		vec3 p = vec3(0.0, rc, 0.0) + d * t;
		float r = length(p);
		vec3 q = vec3(p.x + cam_km.x, r - rc, p.z + cam_km.y);
		bool deep = tr < 0.33;
		float den = cloud_density(q, deep ? 0.0 : 1.0 - smoothstep(6.0, 20.0, t));
		if (den > 0.002) {
			vec3 up = p / r;
			float mus = dot(up, sd);
			// солнце до облака — сквозь атмосферу: на закате свет красный, после заката облака ещё горят
			vec3 sun_l = transmittance(r, mus) * sun_seen(r, mus) * gain * cloud_sun * sun_k;
			// толща облака до солнца: шаги растут
			float tau = tau_last;
			if (!deep) {
				tau = 0.0;
				float ls = 0.08;
				vec3 qq = q;
				for (int k = 0; k < 6; k++) {
					qq += sd * ls;
					tau += cloud_density(qq, 0.0) * ls;
					ls *= 1.8;
				}
				tau *= cloud_sigma;
				tau_last = tau;
			}
			// многократное рассеяние октавами (Wrenninge): ослабление и вытянутость фазы слабеют
			float ms = 0.0;
			float a = 1.0;
			float b = 1.0;
			float c = 1.0;
			for (int o = 0; o < 3; o++) {
				ms += a * exp(-tau * b) * mix(hg(cs, 0.6 * c), hg(cs, -0.2 * c), 0.35);
				a *= 0.45;
				b *= 0.5;
				c *= 0.5;
			}
			// края к солнцу темнее («пудра»): тонкий край рассеивает назад меньше
			float powder = 1.0 - exp(-den * cloud_sigma * 0.1);
			float hf = (q.y - cloud_base) / (cloud_top - cloud_base);
			// свет неба сверху гаснет под толщей облака над точкой: в тучах тёмные пятна, под башнями — тёмное дно
			float amb_occ = occ_last;
			if (!deep) {
				float up_tau = (cloud_density(q + vec3(0.0, 0.35, 0.0), 0.0) * 0.35
					+ cloud_density(q + vec3(0.0, 1.1, 0.0), 0.0) * 0.75) * cloud_sigma;
				amb_occ = mix(0.5, 1.0, exp(-up_tau * 0.08));
				occ_last = amb_occ;
			}
			vec3 src = sun_l * ms * 4.0 * PI * mix(1.0, powder, 0.5) + cloud_amb * mix(amb_bottom, 1.0, hf) * amb_occ;
			// молния светит изнутри тучи: ядро у точки вспышки, свет гаснет за flash_radius
			if (flash > 0.001) {
				src += flash_color * flash * flash_core * exp(-length(q - flash_q) / flash_radius);
			}
			float st = exp(-den * cloud_sigma * dt);
			float w = tr * (1.0 - st);
			l += src * w;
			dsum += t * w;
			wsum += w;
			tr *= st;
			if (tr < 0.02) {
				break;
			}
		}
	}
	tr = max(tr - 0.02, 0.0) / 0.98;
	// дымка между глазом и облаком: дальние облака тонут в цвете неба (в сплошных тучах — в сером)
	float fade = 1.0 - exp(-(dsum / max(wsum, 1e-4)) / cloud_haze);
	l = mix(l, mix(atm, cloud_amb, oc) * (1.0 - tr), fade);
	// у самого горизонта слой сходит в дымку — без среза по дальности
	float edge = smoothstep(0.0, 0.03, d.y);
	return vec4(mix(hz, l + atm * tr, edge), mix(1.0 - oc, tr, edge));
}

// Низкие рваные клочья под тучами: тонкий слой scud_base..scud_top км, свой ветер (scud_offset —
// быстрее и под углом к ветру туч), темнее туч — их освещает только свет из-под туч. rgb — свет
// клочьев, a — сколько видно сквозь них (до tmax, км). Шагов scud_steps — не меньше 48: шум клочьев мелкий,
// при 24 на краях пятен были полосы.
vec4 scud(vec3 d, vec2 cam_km, vec3 haze, float tmax) {
	if (scud_coverage <= 0.0 || d.y <= 0.0) {
		return vec4(0.0, 0.0, 0.0, 1.0);
	}
	float rc = r_ground + view_h;
	float rb = rc + scud_base;
	float rs = rc + scud_top;
	float t0 = -rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rb * rb, 0.0));
	float t1 = min(-rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rs * rs, 0.0)), min(tmax, 12.0));
	if (t0 >= t1) {
		return vec4(0.0, 0.0, 0.0, 1.0);
	}
	float dh = (scud_top - scud_base) / float(scud_steps);
	float t_prev = t0;
	vec3 col = cloud_amb * amb_bottom * 0.5;
	vec3 l = vec3(0.0);
	float tr = 1.0;
	float dsum = 0.0;
	float wsum = 0.0;
	for (int i = 0; i < scud_steps; i++) {
		if (t_prev >= t1) {
			break;
		}
		float rk = rb + dh * (float(i) + 1.0);
		float t_next = min(-rc * d.y + sqrt(max(rc * rc * (d.y * d.y - 1.0) + rk * rk, 0.0)), t1);
		float dt = t_next - t_prev;
		float t = 0.5 * (t_prev + t_next);
		t_prev = t_next;
		vec3 p = vec3(0.0, rc, 0.0) + d * t;
		float r = length(p);
		vec3 q = vec3(p.x + cam_km.x, r - rc, p.z + cam_km.y);
		float hf = (q.y - scud_base) / (scud_top - scud_base);
		// клочья мелкие (пятна ~2 км, рваные ячейки ~0.3 км) и только поблизости: вдали их пятна сливались
		// в ровный слой с плоским верхом
		float wc = smoothstep(1.0 - scud_coverage - 0.1, 1.0 - scud_coverage + 0.2, texture(cloud_cover, q.xz / (cover_tile * 0.08)).r);
		float prof = smoothstep(0.0, 0.3, hf) * (1.0 - smoothstep(0.55, 1.0, hf));
		float sh = texture(cloud_detail, q / (shape_tile * 0.15)).r * prof;
		float den = clamp((sh - (1.0 - wc * 0.75)) / 0.25, 0.0, 1.0) * wc * (1.0 - smoothstep(3.0, 12.0, t));
		if (den > 0.002) {
			float st = exp(-den * cloud_sigma * 0.35 * dt);
			float w = tr * (1.0 - st);
			l += col * w;
			dsum += t * w;
			wsum += w;
			tr *= st;
		}
	}
	float fade = 1.0 - exp(-(dsum / max(wsum, 1e-4)) / (cloud_haze * 0.35));
	l = mix(l, haze * (1.0 - tr), fade);
	return vec4(l, tr);
}

// Полосы дождя вдали: от земли до низа туч — серые завесы под самыми толстыми (тёмными) местами туч,
// той же картой покрытия, — сверху столб уходит в тёмное днище; к низу туч реже, по азимуту — пряди.
// Ложатся поверх всего, что за ними: rgb — цвет, a — непрозрачность.
vec4 rain_shafts(vec3 d, vec2 cam_km, vec3 col) {
	if (shafts <= 0.0 || d.y < -0.01 || d.y > 0.3) {
		return vec4(0.0);
	}
	float tau = 0.0;
	float t_prev = 1.5;
	for (int i = 0; i < 10; i++) {
		// 1.5 … 27 км, шаги гуще у глаза
		float t_next = 1.5 * pow(18.0, float(i + 1) / 10.0);
		float dt = t_next - t_prev;
		float t = 0.5 * (t_prev + t_next);
		t_prev = t_next;
		// высота луча над землёй с поправкой на кривизну, км
		float h = t * d.y + t * t / (2.0 * r_ground);
		if (h > cloud_base) {
			break;
		}
		vec2 xz = d.xz * t + cam_km;
		float rain = smoothstep(0.6, 0.8, texture(cloud_cover, xz / cover_tile).r);
		float strand = texture(cloud_detail, vec3(xz.x * 3.0, h * 0.15, xz.y * 3.0) / detail_tile).r;
		tau += rain * mix(0.08, 1.0, strand * strand) * mix(1.0, 0.45, h / cloud_base) * dt;
	}
	// пряди по азимуту: быстро меняются вбок, медленно — по высоте
	float streak = texture(cloud_detail, vec3(atan(d.x, d.z) * 12.0, d.y * 1.5, 0.37)).r;
	return vec4(col, (1.0 - exp(-tau * shafts)) * mix(0.35, 1.0, streak));
}

// Канал молнии по лучу d: ядро (не тоньше пикселя — иначе рвётся на точки) и ореол в дожде. Ломаная —
// в картинной плоскости (bolt_*); низкие клочья между глазом и каналом его заслоняют.
vec3 bolt_light(vec3 d, vec2 scud_km) {
	float w = dot(d, bolt_c);
	vec2 p = vec2(dot(d, bolt_r), dot(d, bolt_u)) / max(w, 0.05);
	// размер пикселя в тех же долях — до любых ветвлений (производные — по соседним пикселям)
	float px = max(max(fwidth(p.x), fwidth(p.y)), 1e-6);
	if (w < 0.3 || p.x < bolt_box.x || p.y < bolt_box.y || p.x > bolt_box.z || p.y > bolt_box.w) {
		return vec3(0.0);
	}
	float core = 0.0;
	float glow = 0.0;
	for (int i = 0; i < bolt_n; i++) {
		vec4 s = bolt_seg[i];
		vec4 k = bolt_k[i];
		vec2 ba = s.zw - s.xy;
		vec2 pa = p - s.xy;
		float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-12), 0.0, 1.0);
		float dist = length(pa - ba * h);
		float e = mix(k.x, k.y, h) * mix(bolt, bolt_branch, k.w);
		float hw = max(bolt_w * k.z, px * 0.6);
		core = max(core, e * clamp((hw - dist) / px + 0.5, 0.0, 1.0));
		glow = max(glow, e * exp(-dist / (bolt_glow * k.z)));
	}
	if (core + glow < 0.001) {
		return vec3(0.0);
	}
	float tr = scud(d, scud_km, vec3(0.0), bolt_dist).a;
	return (mix(vec3(1.0), flash_color, 0.35) * core * bolt_core + flash_color * glow * bolt_halo) * tr;
}

void sky() {
	if (AT_HALF_RES_PASS) {
		// усиление — здесь же: в буфере половинной точности сумеречные 10⁻⁸ иначе обнуляются (и под тучами её не
		// пропускать: сквозь тонкие места туч светлеет сторона солнца — это её свечение)
		vec3 a = atmosphere(EYEDIR) * gain;
		vec4 cl = clouds_on ? clouds(EYEDIR, a, POSITION.xz / 1000.0 + cloud_offset, AT_CUBEMAP_PASS ? view_k : 1.0) : vec4(a, 1.0);
		if (clouds_on) {
			// клочья — ближе туч, полосы дождя — ближе всего
			vec3 haze = mix(a, cloud_amb * amb_bottom * 0.65, cloud_coverage * cloud_coverage);
			vec4 sc = scud(EYEDIR, POSITION.xz / 1000.0 + scud_offset, haze, 12.0);
			cl = vec4(sc.rgb + cl.rgb * sc.a, cl.a * sc.a);
			vec4 rs = rain_shafts(EYEDIR, POSITION.xz / 1000.0 + cloud_offset, cloud_amb * amb_bottom * 0.6);
			cl = vec4(mix(cl.rgb, rs.rgb, rs.a), cl.a * (1.0 - rs.a));
		}
		COLOR = cl.rgb;
		ALPHA = cl.a;
		// туман движок наложит на итог полного прохода — здесь отменяем (иначе небо затуманится дважды)
		FOG = vec4(cl.rgb, 1.0);
	} else {
		vec3 d = EYEDIR;
		float elev = degrees(asin(clamp(d.y, -1.0, 1.0)));
		vec4 q = HALF_RES_COLOR;
		vec3 c = q.rgb;
		float vis = clouds_on ? q.a : 1.0;
		if (!AT_CUBEMAP_PASS) {
			c *= view_k;
		}
		// пелена без облачного слоя: к горизонту втрое темнее зенита (небо CIE)
		c = mix(c, oc_zenith * (1.0 + 2.0 * max(d.y, 0.0)) / 3.0, veil);
		// солнце диском: цвет — пропускание атмосферы по лучу взгляда, край темнее (потемнение к краю)
		vec3 sd = normalize(sun_dir);
		float rad = radians(sun_size) * 0.5;
		float ang = acos(clamp(dot(d, sd), -1.0, 1.0));
		if (ang < rad * 1.2 && veil < 0.999 && vis > 0.001) {
			float r0 = r_ground + view_h;
			float x = ang / rad;
			float limb = 1.0 - 0.6 * (1.0 - sqrt(max(1.0 - x * x, 0.0)));
			float edge = 1.0 - smoothstep(0.9, 1.1, x);
			vec3 sl = transmittance(r0, d.y) * sun_seen(r0, d.y) * limb * edge * gain / (TAU * (1.0 - cos(rad)));
			sl *= min(1.0, sun_clamp / max(max(sl.r, max(sl.g, sl.b)), 1e-6));
			c += sl * (1.0 - veil) * vis;
		}
		// молния: всё небо под тучами на миг светлеет
		if (flash > 0.001) {
			c += flash_color * flash * flash_amb * (1.0 - vis * 0.7);
		}
		// под горизонтом — земля ровной яркостью
		c = mix(c, ground_col, smoothstep(0.0, -ground_blend, elev));
		if (AT_CUBEMAP_PASS) {
			c *= amb_tint;
		}
		c = night_layer(d, c, vis);
		if (clouds_on) {
			float nk = mix(0.08, 1.0, cloud_coverage * cloud_coverage * cloud_coverage);
			c += (1.0 - vis) * mix(night_cloud, night_cloud_hz, smoothstep(0.25, 0.0, abs(d.y))) * nk * night_k * step(0.0, d.y);
		}
		// канал молнии — только на экране: в карте отражений тонкая линия теряется, землю освещает отсвет неба
		if (!AT_CUBEMAP_PASS && bolt_n > 0 && max(bolt, bolt_branch) > 0.001) {
			c += bolt_light(d, POSITION.xz / 1000.0 + scud_offset);
		}
		if (AT_CUBEMAP_PASS) {
			c = min(c, vec3(radiance_clamp));
		}
		COLOR = c;
	}
}
