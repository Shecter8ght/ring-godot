shader_type sky;
// Небо смены суток (DayCycle): днём и в сумерки — две HDR-панорамы (дневная и закатная, под погоду)
// смешиваются по высоте солнца и поворачиваются за ним (солнце панорамы — по азимуту игрового);
// солнце садится — панорамы гаснут, проступает ночь: тёмный свод, звёзды (точки из звёздной
// панорамы, медленно вращаются) и Луна со своим путём — общий с расчётным небом слой
// sky_night.gdshaderinc. Параметры выставляет DayCycle.

#include "res://src/world/sky_night.gdshaderinc"

// ---- дневные панорамы
uniform sampler2D sky_a : source_color, filter_linear, repeat_enable;
uniform sampler2D sky_b : source_color, filter_linear, repeat_enable;
uniform bool has_b = false;
uniform float mix_b : hint_range(0.0, 1.0) = 0.0;
uniform float rotation_a = 0.0;
uniform float rotation_b = 0.0;
// яркость панорам: × время суток и погоду; hdri_k — доля панорам (0 — ночь)
uniform float exposure = 1.0;
uniform float hdri_k : hint_range(0.0, 1.0) = 1.0;
uniform float clamp_max = 40.0;
uniform float radiance_clamp = 2.5;
// рассеянный свет ночью — «пол» карты неба (только освещение и отражения): SDFGI берёт свет неба из неё,
// ровный цвет окружения под ним не действует (DayCycle, NIGHT_ENV.sky_floor)
uniform vec3 amb_floor = vec3(0.0);
uniform vec3 tint : source_color = vec3(1.0);
uniform vec3 overcast_color : source_color = vec3(0.62, 0.65, 0.68);
uniform float horizon_cut = 0.0;
uniform float horizon_blend = 4.0;
uniform float haze = 0.0;
uniform float haze_height = 10.0;
uniform vec3 ground_color : source_color = vec3(0.16, 0.15, 0.12);

vec2 pano_uv(vec3 d, float rot) {
	float phi = atan(d.x, -d.z) + radians(rot);
	return vec2(phi / TAU + 0.5, acos(clamp(d.y, -1.0, 1.0)) / PI);
}

vec3 sample_sky(vec3 d) {
	vec3 c = texture(sky_a, pano_uv(d, rotation_a)).rgb;
	if (has_b) {
		c = mix(c, texture(sky_b, pano_uv(d, rotation_b)).rgb, mix_b);
	}
	return min(c, vec3(clamp_max));
}

vec3 day_sky(vec3 d) {
	float elev = degrees(asin(clamp(d.y, -1.0, 1.0)));
	vec3 c = sample_sky(d);
	if (horizon_cut > 0.0 && elev < horizon_cut + horizon_blend) {
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
	float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
	float flat_lum = mix(lum, 1.0 - exp(-lum * 1.4), overcast);
	c = mix(c, overcast_color * flat_lum * 1.6, overcast * 0.85);
	return c * tint * exposure;
}

void sky() {
	vec3 d = EYEDIR;
	vec3 c = vec3(0.0);
	if (hdri_k > 0.001) {
		c += day_sky(d) * hdri_k;
	}
	c = night_layer(d, c, 1.0);
	if (AT_CUBEMAP_PASS) {
		c = min(c + amb_floor, vec3(radiance_clamp));
	}
	COLOR = c;
}
