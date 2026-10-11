shader_type spatial;
// Метка голографического прицела ЛУМАР рисуется здесь, а не сеткой из модели: форму (shape), цвет и
// толщину (bold) игрок выбирает в окне настройки прицела (SightMenu, Settings.reticle). Лежит на
// квадрате в окне прицела; светится сама, сцену не освещает.
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;

// 0 — точка, 1 — кольцо с точкой, 2 — шеврон, 3 — крест, 4 — кольцо с перекрестием
uniform int shape = 1;
uniform vec3 tint : source_color = vec3(1.0, 0.12, 0.05);
// толщина линий: 1 — тонкая, 1.7 — обычная, 2.6 — жирная
uniform float bold = 1.7;
// яркость: износ прицела и ПНВ на голове (в трубке яркая метка заливает всё окно)
uniform float energy = 1.0;

float seg(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

float line(float d, float w) {
	return 1.0 - smoothstep(w, w + 0.012, d);
}

void fragment() {
	vec2 p = (UV - vec2(0.5)) * 2.0;
	p.y = -p.y;
	float w = 0.016 * bold;
	float r = length(p);
	float dot_ = 1.0 - smoothstep(0.03 * bold, 0.03 * bold + 0.012, r);
	float a = 0.0;
	if (shape == 0) {
		a = 1.0 - smoothstep(0.05 * bold, 0.05 * bold + 0.014, r);
	} else if (shape == 1) {
		float ring = line(abs(r - 0.62), w);
		// четыре засечки снаружи кольца
		float ticks = 0.0;
		ticks = max(ticks, line(seg(p, vec2(0.0, 0.62), vec2(0.0, 0.78)), w));
		ticks = max(ticks, line(seg(p, vec2(0.0, -0.62), vec2(0.0, -0.78)), w));
		ticks = max(ticks, line(seg(p, vec2(0.62, 0.0), vec2(0.78, 0.0)), w));
		ticks = max(ticks, line(seg(p, vec2(-0.62, 0.0), vec2(-0.78, 0.0)), w));
		a = max(max(ring, ticks), dot_);
	} else if (shape == 2) {
		// шеврон: вершина — точка попадания
		float d = min(seg(p, vec2(0.0, 0.0), vec2(0.34, -0.42)), seg(p, vec2(0.0, 0.0), vec2(-0.34, -0.42)));
		a = line(d, w * 1.2);
	} else if (shape == 3) {
		// крест с разрывом в центре и точкой
		float d = min(min(seg(p, vec2(0.14, 0.0), vec2(0.6, 0.0)), seg(p, vec2(-0.14, 0.0), vec2(-0.6, 0.0))),
			min(seg(p, vec2(0.0, 0.14), vec2(0.0, 0.6)), seg(p, vec2(0.0, -0.14), vec2(0.0, -0.6))));
		a = max(line(d, w), dot_);
	} else {
		// кольцо с тонким перекрестием внутри
		float ring = line(abs(r - 0.62), w);
		float d = min(seg(p, vec2(-0.5, 0.0), vec2(0.5, 0.0)), seg(p, vec2(0.0, -0.5), vec2(0.0, 0.5)));
		a = max(ring, line(d, w * 0.55));
	}
	ALBEDO = tint * energy * 2.2;
	ALPHA = clamp(a, 0.0, 1.0);
}
