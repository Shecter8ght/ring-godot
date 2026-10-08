shader_type sky;
// Небо смены суток (DayCycle): днём и в сумерки — две HDR-панорамы (дневная и закатная, под погоду)
// смешиваются по высоте солнца и поворачиваются за ним (солнце панорамы — по азимуту игрового);
// солнце садится — панорамы гаснут, проступает ночь: тёмный свод, звёзды (точки из звёздной
// панорамы, медленно вращаются) и Луна со своим путём. Параметры выставляет DayCycle.

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
uniform float overcast : hint_range(0.0, 1.0) = 0.0;
uniform vec3 tint : source_color = vec3(1.0);
uniform vec3 overcast_color : source_color = vec3(0.62, 0.65, 0.68);
uniform float horizon_cut = 0.0;
uniform float horizon_blend = 4.0;
uniform float haze = 0.0;
uniform float haze_height = 10.0;
uniform vec3 ground_color : source_color = vec3(0.16, 0.15, 0.12);

// ---- ночь
uniform float night_k : hint_range(0.0, 1.0) = 0.0;
uniform sampler2D stars_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_stars_tex = false;
uniform float stars_energy = 0.25;
uniform float stars_floor = 0.6;
uniform float stars_max = 8.0;
// поворот звёзд, градусы (за час — 15°)
uniform float stars_rotation = 0.0;
uniform vec3 zenith_color : source_color = vec3(0.008, 0.02, 0.04);
uniform vec3 horizon_color : source_color = vec3(0.028, 0.063, 0.125);
uniform float horizon_height = 0.14;
uniform vec3 night_ground : source_color = vec3(0.01, 0.011, 0.013);
uniform sampler2D moon_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_moon_tex = false;
// направление на Луну (мир)
uniform vec3 moon_dir = vec3(0.0, 0.5, 0.86);
uniform float moon_size = 2.2;
uniform float moon_energy = 5.0;
uniform vec3 moon_tint : source_color = vec3(1.0, 0.97, 0.92);
uniform float halo_strength = 0.12;
uniform float halo_size = 5.0;
// яркость Луны днём (бледный диск) — доля ночной
uniform float moon_day = 0.15;

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

vec3 night_sky(vec3 d) {
	float up = d.y;
	vec3 col;
	if (up < 0.0) {
		col = night_ground;
	} else {
		col = mix(horizon_color, zenith_color, smoothstep(0.0, horizon_height, up));
		if (has_stars_tex) {
			// звёзды вращаются (поворот панорамы звёзд вокруг вертикали)
			float a = radians(stars_rotation);
			vec3 sd = vec3(d.x * cos(a) - d.z * sin(a), d.y, d.x * sin(a) + d.z * cos(a));
			vec2 uv = vec2(atan(sd.x, -sd.z) / TAU + 0.5, acos(clamp(sd.y, -1.0, 1.0)) / PI);
			vec3 raw = texture(stars_tex, uv).rgb;
			vec3 bg = textureLod(stars_tex, uv, 6.0).rgb;
			vec3 st = min(max(raw - bg * 1.6 - vec3(stars_floor), vec3(0.0)), vec3(stars_max));
			col += st * stars_energy * smoothstep(0.0, 0.18, up) * (1.0 - overcast * 0.95);
		}
	}
	return col;
}

void sky() {
	vec3 d = EYEDIR;
	vec3 c = vec3(0.0);
	if (hdri_k > 0.001) {
		c += day_sky(d) * hdri_k;
	}
	if (night_k > 0.001) {
		c += night_sky(d) * night_k;
		// пасмурная ночь: низкие облака чуть подсвечены снизу
		c = mix(c, mix(vec3(0.012, 0.013, 0.016), vec3(0.03, 0.031, 0.034), smoothstep(0.25, 0.0, abs(d.y))), overcast * step(0.0, d.y) * 0.9 * night_k);
	}
	// Луна: своим путём; днём — бледный диск, за тучами не видно
	vec3 md = normalize(moon_dir);
	float cosa = dot(d, md);
	float ang = acos(clamp(cosa, -1.0, 1.0));
	float rad = radians(moon_size) * 0.5;
	float veil = 1.0 - overcast;
	float mk = mix(moon_day, 1.0, night_k) * veil;
	if (mk > 0.001 && ang < rad && md.y > -0.05) {
		vec3 upv = normalize(vec3(0.0, 1.0, 0.0) - md * md.y + vec3(0.0, 0.0, 1e-4));
		vec3 rt = normalize(cross(upv, md));
		vec2 p = vec2(dot(d, rt), dot(d, upv)) / sin(rad);
		float r2 = dot(p, p);
		vec3 n = vec3(p, sqrt(max(1.0 - r2, 0.0)));
		vec2 uv = vec2(0.5 + atan(n.x, n.z) / 6.2831853, 0.5 - asin(clamp(n.y, -1.0, 1.0)) / 3.1415927);
		vec3 surf = has_moon_tex ? texture(moon_tex, uv).rgb : vec3(0.62);
		float limb = mix(0.55, 1.0, pow(n.z, 0.45));
		float edge = 1.0 - smoothstep(0.92, 1.0, sqrt(r2));
		c = mix(c, max(c, surf * moon_tint * moon_energy * limb * mk), edge);
	}
	float hs = radians(halo_size);
	float halo = exp(-(ang * ang) / (hs * hs)) * 0.8 + exp(-(ang * ang) / (hs * hs * 9.0)) * 0.2;
	c += moon_tint * halo * halo_strength * night_k * veil * step(-0.05, md.y);
	if (AT_CUBEMAP_PASS) {
		c = min(c, vec3(radiance_clamp));
	}
	COLOR = c;
}
