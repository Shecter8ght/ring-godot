shader_type particles;
// Один слой выброса попадания (ImpactBurst): разлёт конусом, тяжесть, сопротивление воздуха,
// трепет лёгких частиц (травинки, бумага), отскок от двух плоскостей — поверхности, в которую
// попали (plane_a, дальше plane_a_radius от точки удара её нет — край стола, капот), и пола под
// точкой (plane_b). Позицию по скорости двигает сам движок после process().
// CUSTOM.xyz — скорость (по ней тянутся полосы искр и веера), CUSTOM.w — доля прожитой жизни.
// USERDATA1: возраст, своя жизнь, размер, угол поворота; USERDATA2: ось и скорость вращения;
// USERDATA3: x — оттенок (затемнение), y/z — фаза трепета; USERDATA4: скорость до выпуска и
// выпущена ли (волна release_*: частица ждёт невидимой, пока до неё не дойдёт волна от точки).

uniform vec3 origin = vec3(0.0);
uniform vec3 direction = vec3(0.0, 1.0, 0.0);
uniform float spread = 30.0;
uniform vec2 speed = vec2(1.0, 4.0);
// > 1 — больше медленных (основная масса рядом, редкие — далеко)
uniform float speed_bias = 1.0;
uniform vec2 life = vec2(0.4, 0.8);
uniform vec2 size = vec2(0.01, 0.03);
uniform float gravity = 9.81;
uniform float drag = 0.5;
uniform float spin = 7.0;
uniform float flutter = 0.0;
// > 0 — полоса: длина = размер + скорость × stretch, не длиннее stretch_max
uniform float stretch = 0.0;
uniform float stretch_max = 0.4;
// размер к концу жизни (дым растёт, искра гаснет точкой)
uniform float size_end = 1.0;
uniform float jitter = 0.01;
// вылет из прямоугольника (полуразмеры в осях узла: панель стекла), а не из точки
uniform vec3 emit_box = vec3(0.0);
// волна выпуска: от точки release_from со скоростью release_speed (м/с); 0 — все сразу
uniform vec3 release_from = vec3(0.0);
uniform float release_speed = 0.0;
uniform float bounce = 0.3;
uniform float friction = 0.6;
uniform vec4 plane_a = vec4(0.0, 1.0, 0.0, -100000.0);
uniform float plane_a_radius = 100000.0;
uniform vec4 plane_b = vec4(0.0, 1.0, 0.0, -100000.0);
uniform sampler2D color_ramp : source_color, repeat_disable, filter_linear;
uniform vec4 tint : source_color = vec4(1.0);
uniform vec4 tint_alt : source_color = vec4(1.0);
uniform float alt_share = 0.0;
uniform float shade_var = 0.3;

float hash(uint x) {
	x = ((x >> 16u) ^ x) * 0x45d9f3bu;
	x = ((x >> 16u) ^ x) * 0x45d9f3bu;
	x = (x >> 16u) ^ x;
	return float(x) / 4294967295.0;
}

vec3 cone(vec3 d, float half_angle, float r1, float r2) {
	float c = mix(1.0, cos(half_angle), r1);
	float s = sqrt(max(0.0, 1.0 - c * c));
	float phi = r2 * TAU;
	vec3 t = normalize(abs(d.y) < 0.99 ? cross(d, vec3(0.0, 1.0, 0.0)) : cross(d, vec3(1.0, 0.0, 0.0)));
	vec3 b = cross(d, t);
	return normalize(d * c + (t * cos(phi) + b * sin(phi)) * s);
}

mat3 axis_rotation(vec3 a, float ang) {
	float c = cos(ang);
	float s = sin(ang);
	float ic = 1.0 - c;
	return mat3(
		vec3(c + a.x * a.x * ic, a.y * a.x * ic + a.z * s, a.z * a.x * ic - a.y * s),
		vec3(a.x * a.y * ic - a.z * s, c + a.y * a.y * ic, a.z * a.y * ic + a.x * s),
		vec3(a.x * a.z * ic + a.y * s, a.y * a.z * ic - a.x * s, c + a.z * a.z * ic));
}

// Встречу с плоскостью ловим по следующей позиции: скорость разворачиваем до шага движка.
void collide(vec4 plane, float dt, inout vec3 vel, inout vec3 pos, inout float spin_k) {
	vec3 n = plane.xyz;
	float now = dot(n, pos) - plane.w;
	if (now < 0.0) {
		pos -= n * now;
	}
	float next = dot(n, pos + vel * dt) - plane.w;
	float vn = dot(vel, n);
	if (next < 0.0 && vn < 0.0) {
		vec3 vt = vel - n * vn;
		float out_n = -vn * bounce;
		// слабый отскок гасим — кусок лёг и скользит
		if (out_n < 0.45) {
			out_n = 0.0;
		}
		vel = vt * friction + n * out_n;
		spin_k *= 0.5;
	} else if (now < 0.004 && abs(vn) < 0.05) {
		// лежит: трение о поверхность
		vel -= (vel - n * vn) * min(1.0, 5.0 * dt);
	}
}

void start() {
	uint s = NUMBER * 747796405u + RANDOM_SEED * 2891336453u + 1u;
	vec3 d = cone(normalize(direction), radians(spread), hash(s), hash(s + 1u));
	float v = mix(speed.x, speed.y, pow(hash(s + 2u), speed_bias));
	VELOCITY = d * v;
	vec3 offset = (vec3(hash(s + 3u), hash(s + 4u), hash(s + 5u)) - 0.5) * 2.0 * jitter;
	offset += mat3(EMISSION_TRANSFORM) * ((vec3(hash(s + 17u), hash(s + 18u), hash(s + 19u)) - 0.5) * 2.0 * emit_box);
	float own_size = mix(size.x, size.y, hash(s + 6u));
	float own_life = mix(life.x, life.y, hash(s + 7u));
	USERDATA1 = vec4(0.0, own_life, own_size, hash(s + 8u) * TAU);
	vec3 axis = normalize(vec3(hash(s + 9u), hash(s + 10u), hash(s + 11u)) - 0.5 + vec3(0.001));
	USERDATA2 = vec4(axis, (hash(s + 12u) * 2.0 - 1.0) * spin);
	float alt = step(hash(s + 13u), alt_share);
	USERDATA3 = vec4(1.0 - shade_var * hash(s + 14u), hash(s + 15u) * TAU, hash(s + 16u) * TAU, alt);
	TRANSFORM = mat4(1.0);
	TRANSFORM[0].x = own_size;
	TRANSFORM[1].y = own_size;
	TRANSFORM[2].z = own_size;
	TRANSFORM[3] = vec4(EMISSION_TRANSFORM[3].xyz + offset, 1.0);
	vec4 base = mix(tint, tint_alt, alt);
	COLOR = base * texture(color_ramp, vec2(0.0, 0.5)) * vec4(vec3(USERDATA3.x), 1.0);
	CUSTOM = vec4(VELOCITY, 0.0);
	USERDATA4 = vec4(VELOCITY, 1.0);
	if (release_speed > 0.0) {
		float wait = distance(TRANSFORM[3].xyz, release_from) / release_speed;
		USERDATA4.w = 0.0;
		USERDATA1.x = -wait;
		VELOCITY = vec3(0.0);
	}
}

void process() {
	float dt = DELTA;
	USERDATA1.x += dt;
	if (USERDATA4.w < 0.5 && USERDATA1.x < 0.0) {
		// ждёт волну: невидима и неподвижна
		VELOCITY = vec3(0.0);
		TRANSFORM = mat4(vec4(0.0), vec4(0.0), vec4(0.0), TRANSFORM[3]);
	} else {
		if (USERDATA4.w < 0.5) {
			VELOCITY = USERDATA4.xyz;
			USERDATA4.w = 1.0;
		}
		float t = clamp(USERDATA1.x / max(USERDATA1.y, 0.001), 0.0, 1.0);
		if (USERDATA1.x >= USERDATA1.y) {
			ACTIVE = false;
		}
		vec3 vel = VELOCITY;
		vel.y -= gravity * dt;
		vel *= exp(-drag * dt);
		if (flutter > 0.0) {
			float age = USERDATA1.x;
			vel += vec3(sin(age * 9.0 + USERDATA3.y), 0.35 * sin(age * 6.0 + USERDATA3.z), cos(age * 7.0 + USERDATA3.z)) * flutter * dt;
		}
		vec3 pos = TRANSFORM[3].xyz;
		float spin_k = 1.0;
		vec2 off = (pos - origin).xz;
		if (dot(off, off) < plane_a_radius * plane_a_radius) {
			collide(plane_a, dt, vel, pos, spin_k);
		}
		collide(plane_b, dt, vel, pos, spin_k);
		VELOCITY = vel;
		USERDATA2.w *= spin_k;
		USERDATA1.w += USERDATA2.w * dt;
		// конец жизни — уходит в точку, а не исчезает целиком
		float sz = USERDATA1.z * mix(1.0, size_end, t) * (1.0 - smoothstep(0.82, 1.0, t));
		mat3 basis;
		if (stretch > 0.0) {
			// поворот полосы по скорости делает шейдер отрисовки, здесь — только ширина и длина
			float len = clamp(sz + length(vel) * stretch, sz, max(stretch_max, sz));
			basis = mat3(vec3(sz, 0.0, 0.0), vec3(0.0, len, 0.0), vec3(0.0, 0.0, sz));
		} else {
			basis = axis_rotation(USERDATA2.xyz, USERDATA1.w) * sz;
		}
		TRANSFORM = mat4(vec4(basis[0], 0.0), vec4(basis[1], 0.0), vec4(basis[2], 0.0), vec4(pos, 1.0));
		vec4 base = mix(tint, tint_alt, USERDATA3.w);
		COLOR = base * texture(color_ramp, vec2(t, 0.5)) * vec4(vec3(USERDATA3.x), 1.0);
		CUSTOM = vec4(vel, t);
	}
}
