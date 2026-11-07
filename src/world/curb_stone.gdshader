shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Бордюрный камень «Проспекта» (StreetPaving.curb_mesh): вибропрессованный бетон, камни по 1 м с зазором,
// профиль по ГОСТ 6665 (дорожный БР 100.30.15 — скруглённая кромка к дороге, тротуарный БР 100.20.8).
// Развёртка сетки: UV.x — вдоль камня от его начала, м; UV.y — по обводу профиля, м; UV2.x — номер камня
// (свой кусок текстуры и тон), UV2.y — длина камня; COLOR.r — близость к ребру (сбитые кромки).
// Два года без людей: грязь и песок снизу у дороги, в зазорах между камнями земля, мох и трава, сколы
// рёбер, пыль на верхней грани. Без текстур — процедурное зерно. Сырость — StreetPaving.sync_weather.

uniform bool use_maps = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float tile_m = 2.0;
uniform vec3 tint = vec3(1.0);
uniform float saturation : hint_range(0.0, 1.5) = 0.4;
uniform float block_var : hint_range(0.0, 0.3) = 0.07;
uniform vec3 base_color : source_color = vec3(0.55, 0.55, 0.53);
// низ: высота над base_y, м, где копится грязь (у дороги — брызги колёс и нанос)
uniform float base_y = 0.0;
uniform float dirt_h = 0.07;
uniform float dirt : hint_range(0.0, 1.0) = 0.6;
uniform vec3 dirt_color : source_color = vec3(0.30, 0.26, 0.20);
uniform float chips : hint_range(0.0, 1.0) = 0.4;
uniform float moss : hint_range(0.0, 1.0) = 0.3;
uniform vec3 moss_color : source_color = vec3(0.16, 0.22, 0.07);
uniform float dust : hint_range(0.0, 1.0) = 0.3;
uniform vec3 dust_color : source_color = vec3(0.6, 0.57, 0.5);

uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;
uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;
varying vec3 wnorm;
varying float block;
varying float block_len;
varying float edge;

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
float occ_h(vec2 xz) {
	vec2 uv = (xz - occ_center) / occ_size + 0.5;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return -1e5;
	}
	return occ_base + textureLod(occ_tex, uv, 0.0).r * occ_range;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnorm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	block = UV2.x;
	block_len = UV2.y;
	edge = COLOR.r;
}

void fragment() {
	float hb = hash12(vec2(block, 3.7));
	vec2 uv = (UV + vec2(hb * 7.3, hash12(vec2(block, 9.1)) * 5.1)) / tile_m;
	vec3 alb;
	float rough;
	float ao = 1.0;
	vec3 nmap = vec3(0.5, 0.5, 1.0);
	if (use_maps) {
		alb = texture(albedo_tex, uv).rgb;
		vec3 arm = texture(arm_tex, uv).rgb;
		rough = arm.g;
		ao = arm.r;
		nmap = texture(normal_tex, uv).rgb;
		float l = dot(alb, vec3(0.3, 0.59, 0.11));
		alb = mix(vec3(l), alb, saturation) * tint;
	} else {
		float g = vnoise(UV * 90.0) * 0.6 + vnoise(UV * 230.0) * 0.4;
		alb = base_color * (0.9 + g * 0.2);
		rough = 0.85;
	}
	alb *= 1.0 + (hb - 0.5) * 2.0 * block_var;
	// торцы камня: зазор забит землёй — темнее, к торцу шершавее
	float endd = min(UV.x, block_len - UV.x);
	float endk = 1.0 - smoothstep(0.0, 0.015, endd);
	// сколы рёбер: пятнами вдоль ребра, свежий бетон светлее и грубее
	float cn = vnoise(vec2(UV.x * 16.0 + block * 3.1, UV.y * 16.0)) * 0.7 + vnoise(UV * 60.0) * 0.3;
	float chip = max(edge, endk * 0.6) * chips * smoothstep(0.6, 0.66, cn);
	alb = mix(alb, alb * 1.15 + vec3(0.02), chip);
	rough = mix(rough, 0.95, chip);
	// грязь снизу и в зазорах
	float hy = wpos.y - base_y;
	float dk = dirt * (1.0 - smoothstep(0.0, dirt_h * (0.5 + vnoise(wpos.xz * 3.0 + block) * 1.0), hy));
	dk = max(dk, endk * 0.8);
	alb = mix(alb, dirt_color * (0.8 + 0.4 * vnoise(wpos.xz * 9.0)), dk);
	rough = mix(rough, 1.0, dk);
	// мох: в зазорах и у низа, пятнами
	float mk = moss * smoothstep(0.55, 0.8, vnoise(wpos.xz * 2.1 + wpos.y * 3.0 + 7.0)) * max(endk, 1.0 - smoothstep(0.0, 0.12, hy));
	alb = mix(alb, moss_color * (0.7 + 0.6 * vnoise(wpos.xz * 13.0)), mk);
	// пыль на верхней грани
	float up = smoothstep(0.6, 0.95, wnorm.y);
	alb = mix(alb, dust_color, up * dust * 0.4 * smoothstep(0.3, 0.7, vnoise(wpos.xz * 1.3)));
	// сырость
	float open = step(occ_h(wpos.xz), wpos.y + 0.2);
	float film = clamp(wetness * open * 1.2, 0.0, 1.0);
	alb = mix(alb, pow(alb, vec3(1.15)) * 0.55, film);
	rough = mix(rough, 0.2 + rough * 0.15, film);
	ALBEDO = alb;
	ROUGHNESS = rough;
	AO = ao * (1.0 - endk * 0.4);
	AO_LIGHT_AFFECT = 0.25;
	SPECULAR = 0.5;
	NORMAL_MAP = mix(nmap, vec3(0.5, 0.5, 1.0), film * 0.4);
}
