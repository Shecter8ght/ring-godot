shader_type sky;
render_mode use_debanding;
// Небо рейдов (TodLight): цвет неба по времени суток — из таблицы data/lighting/time_of_day.json (схема Road to Vostok,
// решение владельца 2026-11-05), облака — наша панорама, приведённая к их средней яркости. Поверх (владелец 2026-11-19:
// небо «как наклейка», в пасмурно горизонт выбелен, закат бурый): ясное небо к зениту темнее и синее, к горизонту
// светлее, со стороны солнца светлее; пасмурное — зенит светлее горизонта, туман и дождь стирают облака в пелену
// (veil); у горизонта небо уходит в цвет дымки — тот же, что у дымки вдаль (дальние дома растворяются ровно в небо);
// тёплый цвет заката — со стороны солнца и у горизонта, зенит и противоположная сторона остаются холодными.
// Ниже горизонта — земля (свет неба и солнца × её альбедо): свет снизу в рассеянном свете. Диск и ореол солнца и
// луны, звёзды ночью. Для карты отражений и рассеянного света небо умножается на reflection. Код свой.

uniform vec3 sky_color : source_color = vec3(0.94, 0.96, 1.0);
uniform float sky_gain = 1.0;
uniform vec3 ground_color : source_color = vec3(0.2, 0.2, 0.2);
uniform vec3 haze_color : source_color = vec3(0.7, 0.72, 0.75);
uniform float haze_amount : hint_range(0.0, 1.0) = 0.8;
uniform float horizon_pow = 5.0;
uniform float overcast : hint_range(0.0, 1.0) = 0.0;
uniform float veil : hint_range(0.0, 1.0) = 0.0;
uniform float reflection = 1.0;

// градиент: ясное небо — зенит (яркость и оттенок) и горизонт против середины; пасмурное — то же для пелены
uniform float zenith = 0.62;
uniform vec3 zenith_tint : source_color = vec3(0.8, 0.9, 1.0);
uniform float horizon_k = 1.35;
uniform float overcast_zenith = 1.2;
uniform float overcast_horizon = 0.7;
// со стороны солнца небо светлее; sun_through — сколько светила видно сквозь погоду (диск и ореол)
uniform float sun_side = 0.55;
uniform float sun_through : hint_range(0.0, 1.0) = 1.0;

// облака: панорамы HDR, выровненные по направлениям (делятся на свою размытую копию — у фотографии облака со
// стороны от солнца тёмные, а солнце в игре ходит) и приведённые к средней яркости
uniform sampler2D clouds_clear : filter_linear, repeat_enable;
uniform sampler2D clouds_overcast : filter_linear, repeat_enable;
uniform sampler2D clear_blur : filter_linear, repeat_enable;
uniform sampler2D overcast_blur : filter_linear, repeat_enable;
uniform bool has_clouds = false;
uniform float clear_mean = 0.546;
uniform float overcast_mean = 0.241;
uniform float clear_contrast = 1.0;
uniform float overcast_contrast = 1.0;
uniform float clouds_shift = 0.0;

uniform vec3 sun_dir = vec3(0.0, 0.7, -0.7);
uniform vec3 sun_color : source_color = vec3(1.0, 0.9, 0.7);
uniform float sun_size = 0.05;
uniform float sun_blur = 1.0;
uniform float sun_glow_size = 0.5;
uniform float sun_glow_intensity = 1.0;
uniform float sun_reflection = 20.0;

uniform vec3 moon_dir = vec3(0.0, 0.7, 0.7);
uniform vec3 moon_color : source_color = vec3(0.78, 0.82, 0.86);
uniform sampler2D moon_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_moon_tex = false;
uniform float moon_size = 0.05;
uniform float moon_glow_size = 0.2;
uniform float moon_glow_intensity = 0.05;
uniform float moon_reflection = 20.0;

// звёзды — из нашей ночной панорамы: панорама минус размытый фон и порог, не ярче stars_max, × stars_energy
uniform sampler2D stars_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_stars_tex = false;
uniform float stars_energy = 0.25;
uniform float stars_floor = 0.6;
uniform float stars_max = 8.0;
uniform float stars_reflection = 5.0;

const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

// облако из панорамы: яркость относительно окрестности × средняя, засвет (солнце в панораме) не выше белого
vec3 cloud(sampler2D tex, sampler2D blur, vec2 uv, float mean, float contrast) {
	float around = max(dot(texture(blur, uv).rgb, LUMA), 0.0001);
	vec3 c = texture(tex, uv).rgb * (mean / around);
	return clamp(vec3(mean) + (c - vec3(mean)) * contrast, vec3(0.0), vec3(1.0));
}

void sky() {
	vec3 eye = normalize(EYEDIR);
	float up = smoothstep(-0.04, 0.02, eye.y);
	float h = clamp(eye.y, 0.0, 1.0);
	vec3 sd = normalize(sun_dir);
	float sun_mask = smoothstep(-0.1, 0.0, sd.y);
	float toward = max(dot(eye, sd), 0.0);

	vec2 uv = vec2(SKY_COORDS.x + clouds_shift, SKY_COORDS.y);
	float mean = mix(clear_mean, overcast_mean, overcast);
	vec3 clouds = vec3(mean);
	if (has_clouds) {
		clouds = mix(cloud(clouds_clear, clear_blur, uv, clear_mean, clear_contrast),
			cloud(clouds_overcast, overcast_blur, uv, overcast_mean, overcast_contrast), overcast);
	}
	// тучи серые: наша пасмурная панорама — с синими просветами, под сплошными тучами неба не видно
	clouds = mix(clouds, vec3(dot(clouds, LUMA)), overcast);
	// пелена пасмурного неба, тумана и дождя: рисунок облаков стирается к ровному серому
	clouds = mix(clouds, vec3(mean), veil);

	// цвет неба: тёплый цвет заката и рассвета — у солнца и над горизонтом; остальное небо — той же яркости, но холоднее
	float sky_l = dot(sky_color, LUMA);
	vec3 cool = sky_l * vec3(0.9, 0.97, 1.08);
	vec2 eh = normalize(eye.xz + vec2(0.00001));
	vec2 sh = normalize(sd.xz + vec2(0.00001));
	float sunward = 0.5 + 0.5 * dot(eh, sh);
	float warm = clamp(0.3 + 0.7 * sunward * sunward * (1.0 - 0.75 * h), 0.0, 1.0);
	vec3 tint = mix(cool, sky_color, mix(warm, 1.0, overcast * 0.6));

	// градиент яркости: ясное — зенит темнее и синее, горизонт светлее; пасмурное — наоборот, зенит светлее
	float hz = pow(h, 0.45);
	vec3 grad_clear = mix(vec3(horizon_k), zenith * zenith_tint, hz);
	vec3 grad_over = vec3(mix(overcast_horizon, overcast_zenith, pow(h, 0.7)));
	vec3 grad = mix(grad_clear, grad_over, overcast);
	// со стороны солнца небо и облака светлее
	grad *= 1.0 + sun_side * pow(toward, 3.0) * sun_mask * sun_through;

	vec3 sky_part = tint * clouds * grad * sky_gain;
	// дымка у горизонта — тот же цвет, что у дымки вдаль
	sky_part = mix(sky_part, haze_color, pow(1.0 - h, horizon_pow) * haze_amount);
	// земля под горизонтом
	sky_part = mix(ground_color, sky_part, up);

	float sun_d = distance(eye, sd);
	float sun_p = 1.0 - clamp(sun_d / sun_size, 0.0, 1.0);
	vec3 sun_core = sun_color * clamp(sun_p / sun_blur, sun_p, 1.0) * sun_mask * sun_through * up;
	float glow_p = 1.0 - clamp(sun_d / sun_glow_size, 0.0, 1.0);
	// сквозь пелену — широкое бледное пятно вместо диска
	vec3 sun_glow = sun_color * glow_p * glow_p * sun_glow_intensity * sun_mask * mix(sun_through, sqrt(sun_through), veil) * up;

	vec3 md = normalize(moon_dir);
	float moon_mask = smoothstep(-0.1, 0.0, md.y);
	float moon_d = distance(eye, md);
	float moon_p = 1.0 - clamp(moon_d / moon_size, 0.0, 1.0);
	vec3 moon_core = vec3(0.0);
	float md_dot = dot(eye, md);
	float disc = sqrt(1.0 - moon_size * moon_size);
	if (md_dot > disc - 0.01) {
		// наша карта Луны (равнопромежуточная) на шаре диска
		vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), md));
		vec3 upv = normalize(cross(md, right));
		vec3 local = eye - md * md_dot;
		vec2 q = vec2(dot(local, right), dot(local, upv)) / moon_size;
		float r2 = dot(q, q);
		vec3 tex = vec3(1.0);
		if (has_moon_tex && r2 < 1.0) {
			float z = sqrt(1.0 - r2);
			vec2 muv = vec2(atan(q.x, z) / 6.2831853 + 0.5, 0.5 - asin(clamp(q.y, -1.0, 1.0)) / 3.1415927);
			tex = texture(moon_tex, muv).rgb;
		}
		moon_core = moon_color * tex * moon_p * moon_mask * smoothstep(disc - 0.01, disc, md_dot) * (1.0 - overcast);
	}
	float mglow_p = 1.0 - clamp(moon_d / moon_glow_size, 0.0, 1.0);
	vec3 moon_glow = moon_color * mglow_p * mglow_p * moon_glow_intensity * moon_mask * (1.0 - overcast * 0.7);

	vec3 stars = vec3(0.0);
	if (has_stars_tex) {
		float night = smoothstep(0.0, 0.5, -sd.y);
		vec3 raw = texture(stars_tex, uv).rgb;
		vec3 bg = textureLod(stars_tex, uv, 6.0).rgb;
		vec3 st = min(max(raw - bg * 1.6 - vec3(stars_floor), vec3(0.0)), vec3(stars_max)) * stars_energy;
		stars = st * 0.5 * clouds * (1.0 - overcast) * (1.0 - veil) * smoothstep(0.0, 0.75, eye.y) * night;
	}

	if (AT_CUBEMAP_PASS) {
		COLOR = (sky_part + sun_glow + sun_core * sun_reflection + moon_glow + moon_core * moon_reflection
			+ stars * stars_reflection) * reflection;
	} else {
		COLOR = sky_part + sun_glow + sun_core + moon_glow + moon_core + stars;
	}
}
