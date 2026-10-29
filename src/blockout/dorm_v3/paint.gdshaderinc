// Облупленная масляная краска v03 (tools/dorm_modules/paint_v3.py). Износ wear — доля снятой краски.
// По полю отслоения ef и его крутизне — расстояние s до кромки в мм (s > 0 — краска): кромка, загиб валиком,
// приподнятые края кусков у кромки; под краской ступеньками старый слой, шпаклёвка, штукатурка (фотоскан).

#include "res://src/blockout/dorm_v3/scan.gdshaderinc"

uniform sampler2D paint_peel_e : filter_linear_mipmap, repeat_enable;
uniform sampler2D paint_peel_dir : filter_linear_mipmap, repeat_enable;
uniform sampler2D paint_masks : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D paint_tone : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D paint_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D paint_cup_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D paint_under : filter_linear_mipmap, repeat_enable;
uniform sampler2D paint_under_cells : filter_linear_mipmap, repeat_enable;
uniform vec3 paint_color : source_color = vec3(0.298, 0.431, 0.353);
uniform vec3 paint_old_color : source_color = vec3(0.71, 0.663, 0.529);
uniform float paint_old_share = 0.6;
uniform float paint_curl_share = 1.0;
uniform float paint_relief = 1.0;
uniform float paint_roughness = 0.24;

void paint_layer(vec2 uv0, float wear, vec3 t, vec3 b, vec3 n, out vec3 color, out float rough, out vec3 normal) {
	vec2 uv = map_uv(uv0);
	vec3 col_paint = paint_color;
	float ef = texture(paint_peel_e, uv).r;
	vec3 dir = texture(paint_peel_dir, uv).rgb;
	vec4 mk = texture(paint_masks, uv);
	vec4 tn = texture(paint_tone, uv);
	vec4 un = texture(paint_under, uv);
	vec4 uc = texture(paint_under_cells, uv);
	vec2 pn = nxy(texture(paint_normal, uv));
	vec2 cn = nxy(texture(paint_cup_normal, uv));
	vec3 pl_alb = texture(plaster_albedo, uv).rgb;
	vec2 pl_n = nxy(texture(plaster_normal, uv));
	float pl_r = texture(plaster_rough, uv).r;
	float Q = mk.r, RND = mk.b, NOCURL = mk.a;
	float TONE = tn.r, DRIP = tn.g, SPECK = tn.b, CHALK = tn.a;
	float PUTTY = un.r, OLD = un.g, GRIME = un.b, CURL = un.a;
	float OC = uc.r, PC = uc.b, ET = uc.a;

	float G = max(pow(10.0, dir.r * 5.0 - 5.0), 0.0004);
	float s = clamp((ef - wear) / G, -80.0, 80.0);
	float du = dir.g * 2.0 - 1.0, dv = dir.b * 2.0 - 1.0;
	float peeled = 1.0 - smoothstep(-0.15, 0.15, s);
	float inside = max(-s, 0.0);

	// краска
	float dmg = 1.0 - smoothstep(0.0, 18.0, s);
	float opening = 1.0 + dmg * 1.4;
	float crack = 1.0 - smoothstep(opening * 0.85, opening * 1.6, Q * 4.0);
	float lift = pow(dmg, 1.4) * (0.4 + RND * 0.6);
	vec3 c = col_paint * (0.7 + TONE * 0.6);
	c = mix(c, rgb(167.0, 173.0, 155.0), CHALK * 0.08);
	c = mix(c, rgb(78.0, 74.0, 54.0), DRIP * 0.28);
	c = mix(c, rgb(31.0, 27.0, 21.0), SPECK * 0.85);
	c = mix(c, rgb(36.0, 30.0, 24.0), crack * 0.93);
	float rim = (1.0 - smoothstep(0.05, 0.5, s)) * (1.0 - peeled);
	c = mix(c, rgb(195.0, 196.0, 178.0), rim * 0.12);
	float r_paint = paint_roughness + (1.0 - TONE) * 0.1 + CHALK * 0.1 + SPECK * 0.15;
	r_paint = mix(r_paint + DRIP * 0.08, 0.88, crack);

	// загиб кромки — только на кромке большого поля краски
	float cw = 2.4 + CURL * 3.8;
	float tt = inside / cw;
	float s_main = abs((ET - wear) / G);
	float main_edge = 1.0 - smoothstep(2.5, 7.0, s_main);
	float pres = min(smoothstep(0.4, 0.72, CURL) * paint_curl_share * (1.0 - NOCURL) * main_edge, 1.0);
	float in_curl = pres * smoothstep(0.0, 0.04, tt) * (1.0 - smoothstep(0.9, 1.0, tt));
	float x = clamp(tt * 2.0 - 1.0, -1.0, 1.0);
	float nzc = sqrt(max(1.0 - x * x, 0.0));
	vec3 under_side = mix(col_paint * 1.05, rgb(214.0, 212.0, 198.0), smoothstep(0.0, 0.9, x) * 0.45);
	vec3 curl_c = under_side * (0.35 + nzc * 0.65);
	float shadow = pres * smoothstep(0.95, 1.05, tt) * (1.0 - smoothstep(1.1, 2.3, tt));

	// под краской
	float t_old = (max(OLD - 0.5, 0.0) * 0.3 + (OC - 0.5) * 0.025) * paint_old_share;
	float t_putty = max(PUTTY - 0.3, 0.0) * 0.22 + (PC - 0.5) * 0.03;
	float s_old = (ef - wear + t_old) / G;
	float s_putty = (ef - wear + t_old + t_putty) / G;
	float old = peeled * smoothstep(-0.2, 0.2, s_old);
	float putty = peeled * (1.0 - old) * smoothstep(-0.2, 0.2, s_putty);
	vec3 plaster = pl_alb * rgb(196.0, 182.0, 168.0) * 1.05;
	plaster = mix(plaster, plaster * rgb(109.0, 98.0, 90.0), GRIME * 0.6);
	plaster = mix(plaster, col_paint, (1.0 - smoothstep(0.0, 5.0, inside)) * 0.2);
	vec3 putty_c = rgb(194.0, 187.0, 168.0) * (0.55 + lum(pl_alb) * 0.75);
	putty_c = mix(putty_c, putty_c * rgb(125.0, 111.0, 92.0), GRIME * 0.5);
	vec3 u = mix(plaster, putty_c, putty);
	u = mix(u, paint_old_color * (0.8 + TONE * 0.4), old);
	float step_dirt = (1.0 - smoothstep(0.0, 0.9, inside)) * (1.0 - pres);
	u *= 1.0 - (step_dirt * 0.5 + shadow * 0.7);
	float r_under = mix(pl_r, 0.9, putty);
	r_under = mix(r_under, 0.72, old);
	float ledge_o = old * (1.0 - smoothstep(0.05, 0.5, s_old));
	float ledge_p = putty * (1.0 - smoothstep(0.05, 0.6, s_putty));
	float foot = peeled * (1.0 - (old + putty)) * (1.0 - smoothstep(0.0, 0.8, -s_putty));
	u *= 1.0 - min(foot, 1.0) * 0.35;
	color = mix(c, u, peeled);
	color = mix(color, curl_c, in_curl);
	rough = mix(r_paint, r_under, peeled);
	rough = mix(rough, 0.75, in_curl);

	// нормаль
	float px = (pn.x + cn.x * lift * 0.8 - du * rim * 0.6) * paint_relief;
	float py = (pn.y + cn.y * lift * 0.8 - dv * rim * 0.6) * paint_relief;
	float pls = 0.45 - putty * 0.2;
	float ux = pl_n.x * pls - du * (ledge_o * 0.35 + ledge_p * 0.3);
	float uy = pl_n.y * pls - dv * (ledge_o * 0.35 + ledge_p * 0.3);
	float nx = mix(px, ux, peeled);
	float ny = mix(py, uy, peeled);
	float nz = mix(rebuild_z(pn), rebuild_z(pl_n), peeled);
	nx = mix(nx, x * du * -0.9, in_curl);
	ny = mix(ny, x * dv * -0.9, in_curl);
	nz = mix(nz, nzc, in_curl);
	normal = to_world(vec3(nx, ny, nz), t, b, n);
}
