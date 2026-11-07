shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Облицовка плиткой по граням коробок (сухой фонтан сквера «Проспекта» — фото владельца 05: бортик в бежевой
// керамической плитке, верх — серый бетонный парапет). Своё, без текстур: сетка плиток по мировым осям грани,
// у каждой плитки свой тон, шов затёрт тёмным, глазурь местами отбита, грязь и потёки снизу, сверху — бетон.
// Два года без людей: швы позеленели, у земли нанос, плитка выгорела.

uniform vec2 tile_m = vec2(0.3, 0.15);
uniform float joint_m = 0.004;
uniform vec3 tile_color : source_color = vec3(0.78, 0.70, 0.58);
uniform float tile_var : hint_range(0.0, 0.3) = 0.08;
uniform vec3 joint_color : source_color = vec3(0.32, 0.30, 0.26);
uniform vec3 top_color : source_color = vec3(0.52, 0.51, 0.48);
uniform float base_y = 0.0;
uniform float dirt_h = 0.18;
uniform vec3 dirt_color : source_color = vec3(0.32, 0.28, 0.21);
uniform float chips : hint_range(0.0, 1.0) = 0.25;
uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;

varying vec3 wpos;
varying vec3 wnorm;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnorm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 alb;
	float rough;
	float n_up = wnorm.y;
	if (n_up > 0.6) {
		// верх бортика — бетонный парапет
		float g = vnoise(wpos.xz * 40.0) * 0.5 + vnoise(wpos.xz * 7.0) * 0.5;
		alb = top_color * (0.85 + g * 0.3);
		rough = 0.9;
	} else {
		// грань: вдоль — горизонталь по грани, поперёк — высота
		vec2 uv = vec2(abs(wnorm.x) > abs(wnorm.z) ? wpos.z : wpos.x, wpos.y);
		float row = floor(uv.y / tile_m.y);
		float off = mod(row, 2.0) * 0.5 * tile_m.x;
		vec2 cell = vec2(floor((uv.x + off) / tile_m.x), row);
		vec2 lp = vec2(uv.x + off - cell.x * tile_m.x, uv.y - row * tile_m.y);
		float ed = min(min(lp.x, tile_m.x - lp.x), min(lp.y, tile_m.y - lp.y));
		float px = max(length(fwidth(uv)), 0.0005);
		float joint = 1.0 - smoothstep(joint_m * 0.5, joint_m * 0.5 + px, ed);
		float h = hash12(cell + floor(wpos.xz * 0.1));
		alb = tile_color * (1.0 + (h - 0.5) * 2.0 * tile_var);
		rough = 0.35 + (1.0 - vnoise(uv * 3.0)) * 0.25;
		// отбитая глазурь: светлый бетон под ней, шершаво
		float chip = chips * smoothstep(0.72, 0.76, vnoise(uv * 9.0 + h * 7.0)) * smoothstep(0.0, 0.03, ed);
		alb = mix(alb, top_color * 1.1, chip);
		rough = mix(rough, 0.95, chip);
		// шов: тёмный, местами позеленел
		vec3 jc = mix(joint_color, vec3(0.18, 0.24, 0.10), smoothstep(0.55, 0.8, vnoise(uv * 4.0 + 3.0)));
		alb = mix(alb, jc, joint);
		rough = mix(rough, 1.0, joint);
	}
	// грязь, нанос и потёки снизу; выгорело сверху
	float hy = wpos.y - base_y;
	float dk = 1.0 - smoothstep(0.0, dirt_h * (0.6 + vnoise(wpos.xz * 2.0 + wpos.y) * 0.8), hy);
	float streak = smoothstep(0.6, 0.9, vnoise(vec2((wpos.x + wpos.z) * 9.0, hy * 1.5))) * (1.0 - smoothstep(0.0, 0.5, hy)) * (1.0 - n_up);
	alb = mix(alb, dirt_color, max(dk * 0.85, streak * 0.4));
	rough = mix(rough, 1.0, dk);
	// сырость
	alb = mix(alb, alb * 0.6, wetness * 0.8);
	rough = mix(rough, 0.12 + rough * 0.15, wetness);
	ALBEDO = alb;
	ROUGHNESS = rough;
	SPECULAR = 0.5;
}
