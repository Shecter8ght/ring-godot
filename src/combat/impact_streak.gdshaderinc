// Полоса частицы попадания: смотрит в камеру и тянется вдоль скорости (CUSTOM.xyz из
// impact_particles). Голова — в точке частицы, хвост позади неё. Ширина — X базиса частицы,
// длина — Y. Квад 1×1: UV.y = 0 у головы.

// своя доля узора у каждой полосы, чтобы зерно не повторялось
varying float v_seed;
// вдали полоса не уже ~1,5 пикселя (иначе мерцает и пропадает), яркость — на ту же долю меньше
varying float v_thin;
uniform float min_width_k = 0.0011;

void vertex() {
	v_seed = float(INSTANCE_ID % 13) * 0.173;
	vec3 pos = MODEL_MATRIX[3].xyz;
	float w_own = length(MODEL_MATRIX[0].xyz);
	float w = max(w_own, length(INV_VIEW_MATRIX[3].xyz - pos) * min_width_k);
	v_thin = sqrt(w_own / max(w, 1e-5));
	float l = length(MODEL_MATRIX[1].xyz);
	vec3 vel = INSTANCE_CUSTOM.xyz;
	vec3 to_cam = normalize(INV_VIEW_MATRIX[3].xyz - pos);
	vec3 axis = dot(vel, vel) > 1e-6 ? normalize(vel) : INV_VIEW_MATRIX[1].xyz;
	vec3 side = cross(axis, to_cam);
	side = dot(side, side) > 1e-6 ? normalize(side) : INV_VIEW_MATRIX[0].xyz;
	vec3 face = normalize(cross(side, axis));
	mat4 m = mat4(vec4(side * w, 0.0), vec4(axis * l, 0.0), vec4(face, 0.0), vec4(pos - axis * l * 0.5, 1.0));
	MODELVIEW_MATRIX = VIEW_MATRIX * m;
	MODELVIEW_NORMAL_MATRIX = mat3(VIEW_MATRIX) * mat3(side, axis, face);
}

// Мягкая форма полосы: края поперёк гаснут, голова плотная, хвост растворяется.
float streak_shape(vec2 uv) {
	float across = 1.0 - abs(uv.x * 2.0 - 1.0);
	float head = smoothstep(0.0, 0.12, uv.y);
	float tail = 1.0 - smoothstep(0.25, 1.0, uv.y);
	return smoothstep(0.0, 0.7, across) * mix(head, 1.0, 0.6) * tail;
}
