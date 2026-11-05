shader_type sky;
render_mode use_debanding;
// Небо по схеме Road to Vostok (решение владельца 2026-11-05: их свет на все рейдовые карты): ровный цвет неба по
// времени суток (TodLight по таблице data/lighting/time_of_day.json), ниже горизонта — цвет земли, облака — наша
// панорама (облачная днём, сплошная пелена в пасмурно), приведённая к их средней яркости и умноженная на цвет неба;
// свечение у горизонта, диск и ореол солнца и луны, звёзды ночью. Для карты отражений и рассеянного света небо
// умножается на reflection (ночью у них ×4), солнце и луна там ярче (sun_reflection). Код свой.

// цвет неба, горизонта (у них — небо × 0,8) и земли (небо × 0,5)
uniform vec3 sky_color : source_color = vec3(0.94, 0.96, 1.0);
uniform vec3 horizon_color : source_color = vec3(0.75, 0.77, 0.8);
uniform vec3 ground_color : source_color = vec3(0.47, 0.48, 0.5);
uniform float overcast : hint_range(0.0, 1.0) = 0.0;
uniform float reflection = 1.0;
uniform float horizon_blur = 0.1;

// облака: панорамы HDR, выровненные по направлениям (делятся на свою размытую копию — у фотографии облака со
// стороны от солнца тёмные, у их картинки облака освещены ровно) и приведённые к средней яркости их облачного неба
uniform sampler2D clouds_clear : filter_linear, repeat_enable;
uniform sampler2D clouds_overcast : filter_linear, repeat_enable;
uniform sampler2D clear_blur : filter_linear, repeat_enable;
uniform sampler2D overcast_blur : filter_linear, repeat_enable;
uniform bool has_clouds = false;
uniform float clear_mean = 0.546;
uniform float overcast_mean = 0.241;
// контраст облаков: разброс их картинки облаков против нашей выровненной панорамы
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

// звёзды — из нашей ночной панорамы, как в night_sky.gdshader: панорама минус размытый фон и порог, не ярче
// stars_max, × stars_energy (иначе вся ночная панорама с облаками светит, как небо днём)
uniform sampler2D stars_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_stars_tex = false;
uniform float stars_energy = 0.25;
uniform float stars_floor = 0.6;
uniform float stars_max = 8.0;
uniform float stars_reflection = 5.0;

// облако из панорамы: яркость относительно окрестности × их средняя, засвет (солнце в панораме) не выше белого
vec3 cloud(sampler2D tex, sampler2D blur, vec2 uv, float mean, float contrast) {
	float around = max(dot(texture(blur, uv).rgb, vec3(0.2126, 0.7152, 0.0722)), 0.0001);
	vec3 c = texture(tex, uv).rgb * (mean / around);
	return clamp(vec3(mean) + (c - vec3(mean)) * contrast, vec3(0.0), vec3(1.0));
}

void sky() {
	vec3 eye = normalize(EYEDIR);
	float up = smoothstep(-0.1, 0.1, eye.y);
	vec3 base = mix(ground_color, sky_color, up);
	vec2 uv = vec2(SKY_COORDS.x + clouds_shift, SKY_COORDS.y);
	vec3 clouds = vec3(1.0);
	if (has_clouds) {
		clouds = mix(cloud(clouds_clear, clear_blur, uv, clear_mean, clear_contrast),
			cloud(clouds_overcast, overcast_blur, uv, overcast_mean, overcast_contrast), overcast);
	}
	vec3 sky_part = mix(base, base * clouds, up);
	vec3 horizon = horizon_color * pow(1.0 - abs(eye.y), 1.0 / horizon_blur);

	vec3 sd = normalize(sun_dir);
	float sun_mask = smoothstep(-0.1, 0.0, sd.y);
	float sun_d = distance(eye, sd);
	float sun_p = 1.0 - clamp(sun_d / sun_size, 0.0, 1.0);
	vec3 sun_core = sun_color * clamp(sun_p / sun_blur, sun_p, 1.0) * sun_mask * (1.0 - overcast);
	float glow_p = 1.0 - clamp(sun_d / sun_glow_size, 0.0, 1.0);
	vec3 sun_glow = sun_color * glow_p * glow_p * sun_glow_intensity * sun_mask * (1.0 - overcast);

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
	vec3 moon_glow = moon_color * mglow_p * mglow_p * moon_glow_intensity * moon_mask * (1.0 - overcast);

	vec3 stars = vec3(0.0);
	if (has_stars_tex) {
		float night = smoothstep(0.0, 0.5, -sd.y);
		vec3 raw = texture(stars_tex, uv).rgb;
		vec3 bg = textureLod(stars_tex, uv, 6.0).rgb;
		vec3 st = min(max(raw - bg * 1.6 - vec3(stars_floor), vec3(0.0)), vec3(stars_max)) * stars_energy;
		stars = st * 0.5 * clouds * (1.0 - overcast) * smoothstep(0.0, 0.75, eye.y) * night;
	}

	if (AT_CUBEMAP_PASS) {
		COLOR = (sky_part + horizon + sun_glow + sun_core * sun_reflection + moon_glow + moon_core * moon_reflection
			+ stars * stars_reflection) * reflection;
	} else {
		COLOR = sky_part + horizon + sun_glow + sun_core + moon_glow + moon_core + stars;
	}
}
