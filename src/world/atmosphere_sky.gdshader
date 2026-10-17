shader_type sky;
render_mode use_quarter_res_pass;
// Расчётное небо смены суток (DayCycle, режим «расчёт»): цвет неба — рассеяние солнечного света в
// атмосфере (модель Hillaire: Рэлей, Ми, озон; таблицы пропускания и многократного рассеяния —
// data/sky_atmosphere.json из tools/gen_sky_atmosphere.py). Луч взгляда маршится в четверть разрешения
// (небо гладкое), солнце диском, Луна и звёзды — в полном. Яркость (gain), пелена туч, низ и поправка
// оттенка отражений — из подгонки по высоте солнца и погоде: свет на земле — как от неба из панорам.
// Ночь — общий слой sky_night.gdshaderinc. Параметры ставит AtmosphereSky. Без use_debanding: его шум
// в проходе четверти разрешения после усиления сумерек (×10⁴) заливал небо.

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
// пасмурно: яркость зенита туч (к горизонту втрое темнее — небо CIE)
uniform vec3 oc_zenith = vec3(0.3);
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

void sky() {
	if (AT_QUARTER_RES_PASS) {
		// усиление — здесь же: в буфере половинной точности сумеречные 10⁻⁸ иначе обнуляются
		vec3 a = atmosphere(EYEDIR) * gain;
		COLOR = a;
		// туман движок наложит на итог полного прохода — здесь отменяем (иначе небо затуманится дважды)
		FOG = vec4(a, 1.0);
	} else {
		vec3 d = EYEDIR;
		float elev = degrees(asin(clamp(d.y, -1.0, 1.0)));
		vec3 c = QUARTER_RES_COLOR.rgb;
		if (!AT_CUBEMAP_PASS) {
			c *= view_k;
		}
		// пасмурно: ровная пелена, к горизонту втрое темнее зенита (небо CIE)
		c = mix(c, oc_zenith * (1.0 + 2.0 * max(d.y, 0.0)) / 3.0, overcast);
		// солнце диском: цвет — пропускание атмосферы по лучу взгляда, край темнее (потемнение к краю)
		vec3 sd = normalize(sun_dir);
		float rad = radians(sun_size) * 0.5;
		float ang = acos(clamp(dot(d, sd), -1.0, 1.0));
		if (ang < rad * 1.2 && overcast < 0.999) {
			float r0 = r_ground + view_h;
			float x = ang / rad;
			float limb = 1.0 - 0.6 * (1.0 - sqrt(max(1.0 - x * x, 0.0)));
			float edge = 1.0 - smoothstep(0.9, 1.1, x);
			vec3 sl = transmittance(r0, d.y) * sun_seen(r0, d.y) * limb * edge * gain / (TAU * (1.0 - cos(rad)));
			sl *= min(1.0, sun_clamp / max(max(sl.r, max(sl.g, sl.b)), 1e-6));
			c += sl * (1.0 - overcast);
		}
		// под горизонтом — земля ровной яркостью
		c = mix(c, ground_col, smoothstep(0.0, -ground_blend, elev));
		if (AT_CUBEMAP_PASS) {
			c *= amb_tint;
		}
		c = night_layer(d, c);
		if (AT_CUBEMAP_PASS) {
			c = min(c, vec3(radiance_clamp));
		}
		COLOR = c;
	}
}
