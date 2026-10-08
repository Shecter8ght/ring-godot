shader_type sky;
// Небо из HDR-панорамы (Poly Haven, CC0) с подстройкой под условия рейда: поворот под игровое
// солнце, экспозиция по времени суток, «пасмурность» по погоде (серее, ровнее, темнее — дождь,
// туман) и плавное смешивание со второй панорамой (например, ясное ↔ затянутое небо).
// Параметры выставляет RaidAtmosphere из данных карты ("sky_hdri") и Balance.HDRI_WEATHER.

uniform sampler2D sky_a : source_color, filter_linear, repeat_enable;
uniform sampler2D sky_b : source_color, filter_linear, repeat_enable;
uniform bool has_b = false;
uniform float mix_b : hint_range(0.0, 1.0) = 0.0;
// поворот панорамы вокруг вертикали, градусы
uniform float rotation = 0.0;
uniform float exposure = 1.0;
// диск солнца на панораме ограничивается: само солнце светит лампой сцены, а пересвет неба
// в отражениях и окружающем свете даёт «выжженную» картинку
uniform float clamp_max = 40.0;
uniform float radiance_clamp = 2.5;
uniform float overcast : hint_range(0.0, 1.0) = 0.0;
uniform vec3 tint : source_color = vec3(1.0);
// цвет «пелены» в пасмурную погоду
uniform vec3 overcast_color : source_color = vec3(0.62, 0.65, 0.68);
// низ панорамы (земля, горы, склоны) заменяется небом над этой высотой, градусы; 0 — как снято
uniform float horizon_cut = 0.0;
uniform float horizon_blend = 4.0;
// дымка к горизонту: доля и высота, до которой она тянется, градусы
uniform float haze = 0.0;
uniform float haze_height = 10.0;
// ниже горизонта — тёмная земля (иначе отражённый снизу свет как от неба)
uniform vec3 ground_color : source_color = vec3(0.16, 0.15, 0.12);

vec2 pano_uv(vec3 d) {
	float phi = atan(d.x, -d.z) + radians(rotation);
	return vec2(phi / TAU + 0.5, acos(clamp(d.y, -1.0, 1.0)) / PI);
}

vec3 sample_sky(vec3 d) {
	vec2 uv = pano_uv(d);
	vec3 c = texture(sky_a, uv).rgb;
	if (has_b) {
		c = mix(c, texture(sky_b, uv).rgb, mix_b);
	}
	return min(c, vec3(clamp_max));
}

void sky() {
	vec3 d = EYEDIR;
	float elev = degrees(asin(clamp(d.y, -1.0, 1.0)));
	vec3 c = sample_sky(d);
	if (horizon_cut > 0.0 && elev < horizon_cut + horizon_blend) {
		// небо над хребтом, слегка растянутое вниз — облачная пелена продолжается к горизонту
		// среднее по полосе неба над хребтом (по высоте и чуть по азимуту) — без вертикальных «потёков»
		vec3 flat_d = normalize(vec3(d.x, 0.0, d.z));
		vec3 side = vec3(-flat_d.z, 0.0, flat_d.x);
		vec3 above = vec3(0.0);
		for (int k = 0; k < 8; k++) {
			float src = radians(horizon_cut + horizon_blend + 1.0 + float(k) * 1.6);
			vec3 h = normalize(flat_d + side * (float(k % 3) - 1.0) * 0.035);
			above += sample_sky(normalize(h * cos(src) + vec3(0.0, sin(src), 0.0)));
		}
		above /= 8.0;
		c = mix(c, above, smoothstep(horizon_cut + horizon_blend, horizon_cut, elev));
		float al = dot(above, vec3(0.2126, 0.7152, 0.0722));
		c = mix(c, ground_color * al, smoothstep(-0.5, -4.0, elev));
	}
	if (haze > 0.0) {
		float hl = dot(c, vec3(0.2126, 0.7152, 0.0722));
		float hk = (1.0 - smoothstep(-1.0, haze_height, elev)) * haze;
		c = mix(c, overcast_color * hl * 1.25, hk);
	}
	// пасмурность: яркость сжимается к средней (солнце за пеленой), цвет — к серому
	float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
	float flat_lum = mix(lum, 1.0 - exp(-lum * 1.4), overcast);
	vec3 veiled = overcast_color * flat_lum * 1.6;
	c = mix(c, veiled, overcast * 0.85);
	// отражения и окружающий свет (кубическая карта) — без диска солнца: солнце светит лампой
	// сцены, которую закрывают тени; иначе в тени дома земля и стены «бликуют» солнцем
	if (AT_CUBEMAP_PASS) {
		c = min(c, vec3(radiance_clamp));
	}
	COLOR = c * tint * exposure;
}
