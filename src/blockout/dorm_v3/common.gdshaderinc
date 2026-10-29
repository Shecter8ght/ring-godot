// Общее для материалов общежития v03 (карты — tools/dorm_modules/gen_*_v3.py → assets/textures/dorm_v3,
// исходные узлы Blender — tools/dorm_modules/*_v3.py; числа те же).
// Оси карты на поверхности считаются из нормали грани: стена — вдоль стены и вверх, пол и потолок — x, z мира.
// v карт смотрит вверх (строки картинки — вниз), поэтому выборка — по (u, −v). T × B = N.

uniform sampler2D wear_noise : filter_linear_mipmap, repeat_enable;

vec3 lin(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

vec3 rgb(float r, float g, float b) {
	return lin(vec3(r, g, b) / 255.0);
}

float lum(vec3 c) {
	return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

vec2 map_uv(vec2 uv) {
	return vec2(uv.x, -uv.y);
}

// Четыре гладких шума по миру (тайл 8 м): R — износ по месту (~3 м), G ~1 м, B ~0,5 м, A ~1,6 м. Среднее 0,5.
vec4 noise_at(vec3 p) {
	return texture(wear_noise, vec2(p.x + 0.37 * p.y, p.z - 0.61 * p.y) / 8.0);
}

void surface_frame(vec3 n, bool diag, out vec3 t, out vec3 b, out vec3 nn) {
	if (abs(n.y) > 0.5) {
		nn = vec3(0.0, sign(n.y), 0.0);
		t = diag ? vec3(0.70710678, 0.0, 0.70710678) : vec3(1.0, 0.0, 0.0);
		b = cross(nn, t);
	} else {
		nn = abs(n.x) > abs(n.z) ? vec3(sign(n.x), 0.0, 0.0) : vec3(0.0, 0.0, sign(n.z));
		b = vec3(0.0, 1.0, 0.0);
		t = cross(b, nn);
	}
}

vec2 surface_uv(vec3 p, vec3 t, vec3 b, float scale) {
	return vec2(dot(p, t), dot(p, b)) * scale;
}

// Нормаль из карты (OpenGL, 0…1): z восстанавливается — у сжатых BC5 карт синего канала нет.
vec2 nxy(vec4 texel) {
	return texel.xy * 2.0 - 1.0;
}

float rebuild_z(vec2 xy) {
	return sqrt(max(1.0 - dot(xy, xy), 0.0));
}

vec3 to_world(vec3 n, vec3 t, vec3 b, vec3 nn) {
	return normalize(n.x * t + n.y * b + n.z * nn);
}

// Яма в толщину слоя: сдвиг по поверхности на метр глубины — от глаза, тем больше, чем острее угол.
vec3 march_dir(vec3 inc, vec3 n) {
	float idn = max(dot(inc, n), 0.08);
	return -(inc - n * dot(inc, n)) / idn;
}

// Стенка ямы смотрит к глазу и чуть вверх (кромки скруглены) — ловит немного верхнего света.
vec3 side_normal(vec3 inc, vec3 n, float up) {
	vec3 ih = normalize(inc - n * dot(inc, n) + vec3(1e-5));
	return normalize(ih + n * up);
}
