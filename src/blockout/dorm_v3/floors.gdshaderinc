// Этажи общежития: отметка пола и высота в свету под точкой (как в dorm_finish.gdshader), граница краски,
// где корпус и пристройка (снаружи — фасад).

uniform vec4 floors = vec4(0.48, 4.42, 7.66, 10.90);
uniform float fifth_floor = 14.14;
uniform vec4 heights = vec4(3.7, 3.0, 3.0, 3.0);
uniform vec4 main_bounds = vec4(0.0, -8.88, 43.41, 8.88);
uniform vec4 annex_bounds = vec4(33.9, -39.0, 43.41, -9.52);
uniform float paint_fraction = 0.6667;

void floor_at(float y, out float base, out float height) {
	base = floors.x;
	height = heights.x;
	if (y >= floors.y - 0.001) { base = floors.y; height = heights.y; }
	if (y >= floors.z - 0.001) { base = floors.z; height = heights.z; }
	if (y >= floors.w - 0.001) { base = floors.w; height = heights.w; }
	if (y >= fifth_floor - 0.001) { base = fifth_floor; height = heights.w; }
}

bool inside_building(vec3 p) {
	bool in_main = p.x >= main_bounds.x - 0.001 && p.x <= main_bounds.z + 0.001 && p.z >= main_bounds.y - 0.001 && p.z <= main_bounds.w + 0.001;
	bool in_annex = p.x >= annex_bounds.x - 0.001 && p.x <= annex_bounds.z + 0.001 && p.z >= annex_bounds.y - 0.001 && p.z <= annex_bounds.w + 0.001;
	return in_main || in_annex;
}

// Атрибут «Износ» модулей Blender здесь заменён расчётом: R — у пола и пятнами, G — куски до кирпича выше краски.
vec2 wear_attr(float rel, vec4 nz, float line_h) {
	float r = 0.55 * max(1.0 - rel / 0.7, 0.0) + 0.15 * nz.g * 2.0;
	float g = rel > line_h ? max(nz.b - 0.52, 0.0) * 6.0 : 0.0;
	return vec2(min(r, 1.0), min(g, 1.0));
}
