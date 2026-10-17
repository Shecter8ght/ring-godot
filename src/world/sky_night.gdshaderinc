// Ночь неба смены суток (DayCycle) — общая для неба из панорам (day_cycle_sky) и расчётного
// (atmosphere_sky): тёмный свод, звёзды (точки из звёздной панорамы, медленно вращаются), Луна своим
// путём (днём — бледный диск) и ореол; пасмурно — звёзд и Луны не видно, низкие тучи ночью чуть
// подсвечены снизу. Параметры выставляет DayCycle. vis — доля чистого неба по лучу (облака расчётного
// неба закрывают звёзды и Луну; у неба из панорам — 1).

uniform float overcast : hint_range(0.0, 1.0) = 0.0;
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

vec3 night_sky(vec3 d, float vis) {
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
			col += st * stars_energy * smoothstep(0.0, 0.18, up) * (1.0 - overcast * 0.95) * vis;
		}
	}
	return col;
}

// Поверх дневного неба c: ночь (доля night_k), тучи ночью, Луна и её ореол.
vec3 night_layer(vec3 d, vec3 c, float vis) {
	if (night_k > 0.001) {
		c += night_sky(d, vis) * night_k;
		// пасмурная ночь: низкие облака чуть подсвечены снизу
		c = mix(c, mix(vec3(0.012, 0.013, 0.016), vec3(0.03, 0.031, 0.034), smoothstep(0.25, 0.0, abs(d.y))), overcast * step(0.0, d.y) * 0.9 * night_k);
	}
	// Луна: своим путём; днём — бледный диск, за тучами не видно
	vec3 md = normalize(moon_dir);
	float cosa = dot(d, md);
	float ang = acos(clamp(cosa, -1.0, 1.0));
	float rad = radians(moon_size) * 0.5;
	float veil = (1.0 - overcast) * vis;
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
	return c;
}
