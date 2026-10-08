// Ветер для ели (общий у хвои и коры, чтобы ветки двигались вместе с лапами).
// Цвет вершин из tools/build_spruce.py: g — гибкость (0 у ствола, 1 на концах длинных веток), b — фаза ветки.
// Ствол качается целиком (сильнее к вершине), лапы — своей дрожью. Фаза дерева — от его положения.

uniform float wind_strength : hint_range(0.0, 3.0) = 1.0;
uniform vec2 wind_dir = vec2(0.8, 0.6);

vec3 spruce_wind(vec3 v, vec4 col, mat4 model, float time) {
	vec3 origin = model[3].xyz;
	vec3 w = normalize(vec3(wind_dir.x, 0.0, wind_dir.y));
	// направление ветра в осях модели (поворот и равномерный масштаб — транспонированная матрица)
	vec3 lw = normalize(transpose(mat3(model)) * w);
	float h = max(v.y, 0.0);
	float seed = dot(origin.xz, vec2(0.071, 0.113));
	float sway = sin(time * 0.55 + seed) * 0.6 + sin(time * 1.21 + seed * 1.7) * 0.4;
	float ph = col.b * 6.2831 + seed;
	float flutter = sin(time * 2.3 + ph) * 0.6 + sin(time * 3.7 + ph * 1.9) * 0.4;
	v += lw * wind_strength * (sway * 0.0002 * h * h + flutter * 0.05 * col.g);
	v.y += wind_strength * flutter * 0.02 * col.g;
	return v;
}
