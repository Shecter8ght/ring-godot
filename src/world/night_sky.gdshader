shader_type sky;
// Ночное небо: HDRI (Poly Haven Qwantani Night, Pure Sky) — только фон со звёздами, приглушённый;
// небо почти чёрное с холодным оттенком, у горизонта — лёгкая дымка. Луна — отдельно: диск с
// картой NASA (LRO LROC), объём шара (край темнее), мягкий ореол. Стоит там, куда смотрит первый
// DirectionalLight3D (лунный свет) — диск и свет всегда совпадают; куда поставить Луну на рейде —
// moon_azimuth / moon_elevation (RaidAtmosphere поворачивает свет). Попадает в отражения (лужи,
// мокрый асфальт) через карту неба. Без HDRI — процедурные звёзды, без карты — серый диск.

group_uniforms stars;
uniform sampler2D stars_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_stars_tex = false;
// сколько от HDRI оставить (оно яркое — звёзды читаются, небо не синеет)
uniform float stars_energy : hint_range(0.0, 4.0) = 0.25;
// ниже порога яркость HDRI гасится — чёрное небо между звёзд (фон этого HDRI ~0.5, звёзды 1…16+)
uniform float stars_floor : hint_range(0.0, 2.0) = 0.6;
group_uniforms;

group_uniforms sky;
// тон неба в зените и у горизонта (#02050A – #071020)
uniform vec3 zenith_color : source_color = vec3(0.008, 0.02, 0.04);
uniform vec3 horizon_color : source_color = vec3(0.028, 0.063, 0.125);
uniform float horizon_height : hint_range(0.01, 0.6) = 0.14;
uniform vec3 ground_color : source_color = vec3(0.01, 0.011, 0.013);
// дождь: облака закрывают звёзды и Луну (0 — ясно)
uniform float overcast : hint_range(0.0, 1.0) = 0.0;
group_uniforms;

group_uniforms moon;
uniform sampler2D moon_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform bool has_moon_tex = false;
// где Луна на рейде (градусы): курс и высота над горизонтом — RaidAtmosphere ставит туда свет
uniform float moon_azimuth : hint_range(-180.0, 180.0) = 140.0;
uniform float moon_elevation : hint_range(5.0, 85.0) = 32.0;
// угловой диаметр диска, градусы (в жизни 0.52 — в игре крупнее, иначе не читается)
uniform float moon_size : hint_range(0.3, 6.0) = 2.2;
uniform float moon_energy : hint_range(0.0, 30.0) = 5.0;
uniform vec3 moon_tint : source_color = vec3(1.0, 0.97, 0.92);
uniform float halo_strength : hint_range(0.0, 2.0) = 0.12;
// ширина ореола, градусы
uniform float halo_size : hint_range(0.5, 30.0) = 5.0;
group_uniforms;

float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

// процедурные звёзды (если HDRI нет): редкие точки на сфере разной яркости
vec3 proc_stars(vec3 d) {
	vec3 g = d * 220.0;
	vec3 c = floor(g);
	float h = hash13(c);
	if (h < 0.992) {
		return vec3(0.0);
	}
	vec3 f = fract(g) - 0.5;
	float s = exp(-dot(f, f) * 60.0) * (h - 0.992) * 120.0;
	return vec3(s) * mix(vec3(0.8, 0.85, 1.0), vec3(1.0, 0.9, 0.8), hash13(c + 7.0));
}

void sky() {
	vec3 d = EYEDIR;
	float up = d.y;
	vec3 col;
	if (up < 0.0) {
		col = ground_color;
	} else {
		col = mix(horizon_color, zenith_color, smoothstep(0.0, horizon_height, up));
		vec3 st = has_stars_tex ? texture(stars_tex, SKY_COORDS).rgb : proc_stars(d);
		st = max(st - vec3(stars_floor), vec3(0.0));
		// у горизонта звёзды тонут в дымке
		col += st * stars_energy * smoothstep(0.0, 0.18, up) * (1.0 - overcast * 0.95);
	}
	// Луна: направление первого направленного света (или своё, если его нет)
	vec3 md = LIGHT0_ENABLED ? normalize(LIGHT0_DIRECTION) : normalize(vec3(
		sin(radians(moon_azimuth)) * cos(radians(moon_elevation)), sin(radians(moon_elevation)),
		cos(radians(moon_azimuth)) * cos(radians(moon_elevation))));
	float cosa = dot(d, md);
	float ang = acos(clamp(cosa, -1.0, 1.0));
	float rad = radians(moon_size) * 0.5;
	float veil = 1.0 - overcast * 0.85;
	if (ang < rad && md.y > -0.05) {
		vec3 upv = normalize(vec3(0.0, 1.0, 0.0) - md * md.y + vec3(0.0, 0.0, 1e-4));
		vec3 rt = normalize(cross(upv, md));
		vec2 p = vec2(dot(d, rt), dot(d, upv)) / sin(rad);
		float r2 = dot(p, p);
		vec3 n = vec3(p, sqrt(max(1.0 - r2, 0.0)));
		vec2 uv = vec2(0.5 + atan(n.x, n.z) / 6.2831853, 0.5 - asin(clamp(n.y, -1.0, 1.0)) / 3.1415927);
		vec3 surf = has_moon_tex ? texture(moon_tex, uv).rgb : vec3(0.62);
		// край диска темнее (объём шара), сам край — мягкий
		float limb = mix(0.55, 1.0, pow(n.z, 0.45));
		float edge = 1.0 - smoothstep(0.92, 1.0, sqrt(r2));
		col = mix(col, surf * moon_tint * moon_energy * limb * veil, edge);
	}
	// ореол: мягкий, без огромного ореола — узкое ядро и слабое широкое
	float hs = radians(halo_size);
	float halo = exp(-(ang * ang) / (hs * hs)) * 0.8 + exp(-(ang * ang) / (hs * hs * 9.0)) * 0.2;
	col += moon_tint * halo * halo_strength * mix(1.0, 0.6, overcast) * step(-0.05, md.y);
	COLOR = col;
}
