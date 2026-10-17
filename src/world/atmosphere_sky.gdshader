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
	float hf = (q.y - cloud_base) / (cloud_top - cloud_base);
	if (hf <= 0.0 || hf >= 1.0) {
		return 0.0;
	}
	float t = 1.0 - cloud_coverage;
	float wc = smoothstep(t - 0.08, t + 0.18, texture(cloud_cover, q.xz / cover_tile).r);
	if (wc <= 0.0) {
		return 0.0;
	}
	float top_f = mix(0.45, 1.0, wc);
	float prof = smoothstep(0.0, 0.12, hf) * (1.0 - smoothstep(top_f - 0.35, top_f, hf));
	float k = wc * prof;
	// клубы: плавный шум формы с ячейками (Перлин — Ворли) — края «цветной капустой», а не ватой
	float sh = mix(texture(cloud_shape, q / shape_tile).r, texture(cloud_detail, q / (shape_tile * 0.5)).r, 0.35);
	float base = clamp((sh - (1.0 - k)) / max(k, 0.05), 0.0, 1.0);
	if (detail > 0.0 && base > 0.0) {
		float ero = (1.0 - texture(cloud_detail, q / detail_tile).r) * detail_k * detail;
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
		float den = cloud_density(q, 1.0 - smoothstep(6.0, 20.0, t));
		if (den > 0.002) {
			vec3 up = p / r;
			float mus = dot(up, sd);
			// солнце до облака — сквозь атмосферу: на закате свет красный, после заката облака ещё горят
			vec3 sun_l = transmittance(r, mus) * sun_seen(r, mus) * gain * cloud_sun * sun_k;
			// толща облака до солнца: шаги растут
			float tau = 0.0;
			float ls = 0.08;
			vec3 qq = q;
			for (int k = 0; k < 6; k++) {
				qq += sd * ls;
				tau += cloud_density(qq, 0.0) * ls;
				ls *= 1.8;
			}
			tau *= cloud_sigma;
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
			float up_tau = (cloud_density(q + vec3(0.0, 0.35, 0.0), 0.0) * 0.35
				+ cloud_density(q + vec3(0.0, 1.1, 0.0), 0.0) * 0.75) * cloud_sigma;
			float amb_occ = mix(0.5, 1.0, exp(-up_tau * 0.08));
			vec3 src = sun_l * ms * 4.0 * PI * mix(1.0, powder, 0.5) + cloud_amb * mix(amb_bottom, 1.0, hf) * amb_occ;
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

void sky() {
	if (AT_HALF_RES_PASS) {
		// усиление — здесь же: в буфере половинной точности сумеречные 10⁻⁸ иначе обнуляются
		vec3 a = atmosphere(EYEDIR) * gain;
		vec4 cl = clouds_on ? clouds(EYEDIR, a, POSITION.xz / 1000.0 + cloud_offset, AT_CUBEMAP_PASS ? view_k : 1.0) : vec4(a, 1.0);
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
		if (AT_CUBEMAP_PASS) {
			c = min(c, vec3(radiance_clamp));
		}
		COLOR = c;
	}
}
