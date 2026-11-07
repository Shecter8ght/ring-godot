shader_type spatial;
render_mode cull_disabled, depth_draw_always;
// Горное озеро «Санатория» под плотиной (владелец 2026-11-08: вода из того, по чему ходим, — натурально): чистая
// холодная вода. Дно видно сквозь неё — кадр под водой (экранная текстура) с преломлением по ряби, свет поглощается
// с глубиной столба воды: у кромки песок и камни как есть, к 3–5 м — бирюза, глубже — тёмная гладь. Глубина столба —
// по буферу глубины (отдельной карты не нужно). У кромки — полоса пены пятнами, рябь — шумом района (три масштаба,
// движется), в дождь — круги от капель. Отражение: прозрачной воде движок не даёт отражений экрана (SSR) — отражалось
// бы одно светлое небо и озеро белело. Луч, отражённый ниже гребня гор вокруг (reflect_ridge), упирается в лесистые
// склоны — там отражение тёмное (цвет склона, освещается как поверхность), выше — небо от движка; блики солнца — всегда.

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_buf : hint_depth_texture, filter_nearest, repeat_disable;
// бесшовный шум района (R, G, B, A — разные пятна), assets/terrain/zone01_noise.png
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
// цвет рассеяния в толще (освещённый): мелко — зеленовато-бирюзовый, глубоко — тёмный сине-зелёный
uniform vec3 shallow_color : source_color = vec3(0.16, 0.29, 0.28);
uniform vec3 deep_color : source_color = vec3(0.015, 0.055, 0.07);
// поглощение по каналам, 1/м: красный гаснет первым (вода горного озера)
uniform vec3 absorb = vec3(0.55, 0.22, 0.17);
// мутность (рассеяние), 1/м
uniform float turbidity = 0.32;
uniform float refraction = 0.035;
uniform float wave_strength = 1.0;
uniform float flow = 0.12;
// пена у кромки (прибоя нет — тонкая полоска): ширина по глубине, м, и густота
uniform float foam_depth = 0.07;
uniform float foam_amount = 0.6;
uniform float rain = 0.0;
// отражённый луч ниже/выше этого синуса возвышения — склоны / небо (котловина: гребни на 10–25°)
uniform vec2 reflect_ridge = vec2(0.16, 0.42);
uniform vec3 slope_reflection : source_color = vec3(0.05, 0.065, 0.045);

// круг от капли в ячейке: смещение нормали (дождь), как у district_water
vec2 drop_ring(vec2 p, float t) {
	vec2 cell = floor(p);
	vec2 f = fract(p) - 0.5;
	float h = fract(sin(dot(cell, vec2(127.1, 311.7))) * 43758.5453);
	float ph = fract(t * 0.9 + h);
	float r = length(f);
	float front = ph * 0.48;
	float ring = sin((r - front) * 48.0) * smoothstep(0.07, 0.0, abs(r - front)) * (1.0 - ph);
	return f / max(r, 0.001) * ring;
}

// наклон глади: шум с конечными разностями в масштабе scale
vec2 ripple(vec2 xz, float scale, vec2 drift, float ch_mix) {
	vec2 p = xz / scale + drift;
	float e = 0.5 / 256.0;
	vec4 a = texture(noise_tex, p);
	vec4 bx = texture(noise_tex, p + vec2(e, 0.0));
	vec4 bz = texture(noise_tex, p + vec2(0.0, e));
	float h0 = mix(a.a, a.b, ch_mix);
	return vec2(h0 - mix(bx.a, bx.b, ch_mix), h0 - mix(bz.a, bz.b, ch_mix)) / e / 256.0;
}

// мировая точка под пикселем экрана по буферу глубины
vec3 world_at(vec2 uv, mat4 inv_proj, mat4 inv_view) {
	float d = texture(depth_buf, uv).r;
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
	v.xyz /= v.w;
	return (inv_view * vec4(v.xyz, 1.0)).xyz;
}

void fragment() {
	vec3 wp = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * flow;
	vec2 slope = ripple(wp.xz, 11.0, vec2(t * 0.10, t * 0.06), 0.0) * 0.9
		+ ripple(wp.xz, 3.7, vec2(-t * 0.21, t * 0.17), 1.0) * 0.55
		+ ripple(wp.xz, 1.3, vec2(t * 0.37, -t * 0.29), 0.5) * 0.25;
	slope *= wave_strength;
	if (rain > 0.01) {
		vec2 rings = drop_ring(wp.xz * 1.6, TIME) + drop_ring(wp.xz * 1.6 + vec2(0.5, 0.31), TIME + 0.43);
		slope += rings * rain * 0.9;
	}
	vec3 n_ts = normalize(vec3(slope * 0.35, 1.0));
	NORMAL_MAP = n_ts * 0.5 + 0.5;
	NORMAL_MAP_DEPTH = 1.0;

	// глубина столба под гладью — по буферу глубины
	vec3 bottom = world_at(SCREEN_UV, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX);
	float column = max(wp.y - bottom.y, 0.0);
	float path = max(distance(bottom, wp), 0.0);
	// преломление: сдвиг по ряби, сильнее на глубине; если сдвинутый пиксель над водой (берег, столб) — без сдвига
	vec2 ruv = SCREEN_UV + slope * refraction * clamp(column, 0.0, 1.5) / max(1.0, -VERTEX.z * 0.08);
	vec3 rb = world_at(ruv, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX);
	if (rb.y > wp.y - 0.02) {
		ruv = SCREEN_UV;
		rb = bottom;
	}
	float rpath = distance(rb, wp);
	float rcol = max(wp.y - rb.y, 0.0);
	vec3 under = textureLod(screen_tex, ruv, 0.0).rgb;
	// поглощение по пути луча в воде, рассеяние — к цвету толщи (мелко — бирюза, глубоко — тёмная)
	vec3 trans = exp(-absorb * rpath);
	float scatter = 1.0 - exp(-turbidity * rpath);
	vec3 body = mix(shallow_color, deep_color, smoothstep(1.0, 9.0, rcol));
	vec3 seen = under * trans * (1.0 - scatter);
	// Френель: под скользящим углом — отражение (от движка), сквозь воду видно меньше
	vec3 view = normalize(-VERTEX);
	float fres = 0.02 + 0.98 * pow(1.0 - clamp(dot(view, NORMAL), 0.0, 1.0), 5.0);
	// пена у кромки: пятна шума, бегут вдоль берега
	float shore = 1.0 - smoothstep(0.0, foam_depth, column);
	float fn = texture(noise_tex, wp.xz / 1.7 + vec2(t * 0.6, -t * 0.4)).r * 0.6 + texture(noise_tex, wp.xz / 0.6 - vec2(t, t * 0.7)).g * 0.4;
	float foam = smoothstep(0.66, 0.82, fn + shore * 0.5) * shore * foam_amount;
	// куда смотрит отражённый луч: в склоны котловины или в небо
	vec3 to_cam = normalize(CAMERA_POSITION_WORLD - wp);
	float sky_k = smoothstep(reflect_ridge.x, reflect_ridge.y, to_cam.y);
	// у самой кромки вода сходит на нет (без шва по линии берега)
	float edge = smoothstep(0.0, 0.06, column);
	vec3 refl = slope_reflection * fres * (1.0 - sky_k) * 6.0;
	ALBEDO = mix(body * scatter * (1.0 - fres) + refl, vec3(0.82, 0.84, 0.82), foam);
	EMISSION = seen * (1.0 - fres) * (1.0 - foam);
	ROUGHNESS = mix(0.025, 0.7, foam);
	SPECULAR = mix(0.1, 0.5, sky_k);
	METALLIC = 0.0;
	ALPHA = edge;
}
