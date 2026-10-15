// Трава: ветер и примятие — общее у густого яруса (grass_blades) и пучков-сканов (grass_scan).
// Ветер: волны порывов бегут по полю (шум в мировых координатах сдвигается по ветру) + своя дрожь
// у каждой травинки. Примятие: карта следов GrassTrample вокруг камеры (RG — куда отогнута,
// B — насколько), её держит процессор: кто прошёл — полоса легла, потом за trample_recover_sec
// поднимается. Всё — смещение вершин, тени и физики нет.

// xy — направление ветра, z — сила (1 — обычный летний ветер), w — скорость волн
global uniform vec4 grass_wind;
global uniform sampler2D grass_trample;
// xy — центр окна карты следов (мир xz), z — сторона окна, м, w — 1, если карта есть
global uniform vec4 grass_trample_area;

uniform sampler2D wind_noise : filter_linear_mipmap, repeat_enable;

// Насколько примята трава в точке мира: xy — направление (мир xz), z — сила 0..1.
vec3 grass_trample_at(vec2 world_xz) {
	if (grass_trample_area.w < 0.5 || grass_trample_area.z <= 0.0) {
		return vec3(0.0);
	}
	vec2 rel = world_xz - grass_trample_area.xy;
	// окно повторяется по кругу: дальше половины окна — чужие клетки, их не читаем
	float edge = 1.0 - smoothstep(grass_trample_area.z * 0.38, grass_trample_area.z * 0.46, max(abs(rel.x), abs(rel.y)));
	if (edge <= 0.0) {
		return vec3(0.0);
	}
	vec4 t = texture(grass_trample, fract(world_xz / grass_trample_area.z));
	vec2 dir = t.rg * 2.0 - 1.0;
	float s = t.b * edge;
	float len = length(dir);
	dir = len > 0.001 ? dir / len : vec2(0.0);
	return vec3(dir, s);
}

// Отгиб верхушки травинки (мир xz, м) от ветра. root — корень в мире, h — высота травинки, м,
// phase — своя фаза травинки 0..1, t — время.
vec2 grass_wind_bend(vec3 root, float h, float phase, float t) {
	vec2 wd = length(grass_wind.xy) > 0.001 ? normalize(grass_wind.xy) : vec2(1.0, 0.0);
	float ws = grass_wind.z;
	float speed = max(grass_wind.w, 0.05);
	// порывы: светлые волны, бегущие по полю
	vec2 p = root.xz * 0.045 - wd * t * 0.16 * speed;
	float gust = texture(wind_noise, p).r;
	gust = smoothstep(0.3, 0.8, gust);
	float wave = texture(wind_noise, root.xz * 0.21 - wd * t * 0.55 * speed).r;
	// раскачка — медленная у всей травинки, быстрая дрожь у верхушки
	float sway = sin(t * 1.7 * speed + phase * 6.2832 + dot(root.xz, wd) * 0.35);
	float flutter = sin(t * 5.3 + phase * 19.0) * 0.5 + sin(t * 8.1 + phase * 31.0) * 0.5;
	vec2 side = vec2(-wd.y, wd.x);
	float push = ws * (0.07 + 0.38 * gust + 0.12 * wave);
	vec2 bend = wd * push + wd * sway * ws * (0.05 + 0.09 * gust) + side * flutter * ws * 0.035;
	return bend * h;
}

// Изгиб вершины по дуге: смещение верхушки bend (м по xz) у травинки высоты h; f — доля высоты
// вершины 0..1. Длина сохраняется примерно: вершина опускается тем сильнее, чем дальше отогнута.
vec3 grass_bend_offset(vec2 bend, float h, float f) {
	float blen = length(bend);
	float maxb = h * 0.96;
	if (blen > maxb) {
		bend *= maxb / blen;
		blen = maxb;
	}
	float k = f * f * (1.6 - 0.6 * f);
	vec2 off = bend * k;
	float drop = h * f * (1.0 - sqrt(max(0.0, 1.0 - (blen / max(h, 0.001)) * (blen / max(h, 0.001))))) * (0.6 + 0.4 * f);
	return vec3(off.x, -drop, off.y);
}

// Во сколько раз ниже вершины примятой травы (1 — стоит, ~0.15 — легла).
float grass_squash(float flat_k) {
	return 1.0 - 0.85 * smoothstep(0.15, 0.85, flat_k);
}

// Полный отгиб (ветер + примятие) верхушки травинки в точке root. Примятая трава к ветру глуха.
vec2 grass_total_bend(vec3 root, float h, float phase, float t, out float flat_k) {
	vec3 tr = grass_trample_at(root.xz);
	flat_k = tr.z;
	vec2 wind = grass_wind_bend(root, h, phase, t);
	// легла почти плашмя по направлению следа, слегка вразброс
	vec2 jitter = vec2(sin(phase * 41.0), cos(phase * 37.0)) * 0.35;
	vec2 trample = normalize(tr.xy + jitter * 0.6 + vec2(0.0001)) * h * 0.95 * smoothstep(0.0, 0.75, tr.z);
	return mix(wind, trample, smoothstep(0.0, 0.5, tr.z));
}
