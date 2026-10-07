#[compute]
#version 450
// Размытие в движении, шаг 2: мазок вдоль вектора движения пикселя (кадр к прошлому кадру, доли
// экрана) — «выдержка» strength от него, длина не больше max_len; выборки со сдвигом по шуму, чтобы
// вместо ступенек было мелкое зерно. Руки и оружие у лица (глубина ближе near_k) не смазываются и
// не затягиваются в фон — иначе за ними при повороте тянется хвост.

layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
layout(set = 0, binding = 0) uniform sampler2D src_tex;
layout(set = 0, binding = 1) uniform sampler2D vel_tex;
layout(rgba16f, set = 0, binding = 2) uniform restrict writeonly image2D dst_img;
layout(set = 0, binding = 3) uniform sampler2D depth_tex;
layout(push_constant, std430) uniform Params {
	vec2 size;
	float strength;
	float max_len;
	float frame;
	float samples;
	float near_k;
	float pad;
} p;

void main() {
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	if (px.x >= int(p.size.x) || px.y >= int(p.size.y)) {
		return;
	}
	vec2 uv = (vec2(px) + 0.5) / p.size;
	vec2 v = texelFetch(vel_tex, px, 0).xy * p.strength;
	float len = length(v);
	if (len > p.max_len) {
		v *= p.max_len / len;
	}
	vec4 base = texelFetch(src_tex, px, 0);
	// обратная глубина: больше — ближе; выше near_k — руки и оружие
	if (texelFetch(depth_tex, px, 0).r > p.near_k || length(v * p.size) < 0.75) {
		imageStore(dst_img, px, base);
		return;
	}
	float noise = fract(52.9829189 * fract(dot(vec2(px), vec2(0.06711056, 0.00583715)) + p.frame * 0.618034));
	int n = int(p.samples);
	vec4 acc = vec4(0.0);
	float w = 0.0;
	for (int i = 0; i < n; i++) {
		float t = (float(i) + noise) / float(n) - 0.5;
		vec2 suv = uv + v * t;
		if (textureLod(depth_tex, suv, 0.0).r > p.near_k) {
			continue;
		}
		acc += textureLod(src_tex, suv, 0.0);
		w += 1.0;
	}
	imageStore(dst_img, px, w > 0.0 ? acc / w : base);
}
