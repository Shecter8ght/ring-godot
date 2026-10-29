// Побелка → старый слой с синькой → штукатурка → кирпич / бетон, v03 (tools/dorm_modules/plaster_v3.py).
// Два износа: облетание побелки (wash) и отвал штукатурки (loss). Отвал — яма в толщину штукатурки (20 мм):
// торец слоя на дальней стороне, кирпич сдвинут вдаль по взгляду. Шкала карт — 0,5 на метр (тайл 2 м).

#include "res://src/blockout/dorm_v3/scan.gdshaderinc"

uniform sampler2D wash_peel_e : filter_linear_mipmap, repeat_enable;
uniform sampler2D wash_peel_dir : filter_linear_mipmap, repeat_enable;
uniform sampler2D loss_peel_e : filter_linear_mipmap, repeat_enable;
uniform sampler2D loss_peel_dir : filter_linear_mipmap, repeat_enable;
uniform sampler2D wash_masks : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wash_tone : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D loss_masks : filter_linear_mipmap, repeat_enable;
uniform sampler2D wash_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wash_cup_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D brick_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D brick_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D brick_rough : filter_linear_mipmap, repeat_enable;
uniform vec3 wash_color : source_color = vec3(0.827, 0.816, 0.773);
uniform vec3 wash_old_color : source_color = vec3(0.776, 0.8, 0.796);
uniform float wash_old_share = 0.7;
uniform float wash_stains = 1.0;
uniform float wash_mold = 1.0;

const float PLASTER_DEPTH_M = 0.02;

void wash_layer(vec3 p, vec3 inc, vec2 uv0, float wash_wear, float loss_wear, vec3 t, vec3 b, vec3 n, bool concrete,
		float stains, float mold, out vec3 color, out float rough, out vec3 normal) {
	vec2 uv = map_uv(uv0);
	float EW = texture(wash_peel_e, uv).r;
	vec3 dw = texture(wash_peel_dir, uv).rgb;
	float EL = texture(loss_peel_e, uv).r;
	vec3 dl = texture(loss_peel_dir, uv).rgb;
	vec4 wm = texture(wash_masks, uv);
	vec4 wt = texture(wash_tone, uv);
	vec4 lm = texture(loss_masks, uv);
	vec2 wn = nxy(texture(wash_normal, uv));
	vec2 cn = nxy(texture(wash_cup_normal, uv));
	vec3 pl_alb = texture(plaster_albedo, uv).rgb;
	vec2 pl_n = nxy(texture(plaster_normal, uv));
	float pl_r = texture(plaster_rough, uv).r;
	float QW = wm.r, RFW = wm.b, QL = wm.a;
	float TONE = wt.r, STAIN = wt.g, MOLD = wt.b, THIN = wt.a;
	float RES = lm.r, CRUMB = lm.g;
	float k_stain = wash_stains * stains;
	float k_mold = wash_mold * mold;

	float Gw = max(pow(10.0, dw.r * 5.0 - 5.0), 0.0004);
	float Gl = max(pow(10.0, dl.r * 5.0 - 5.0), 0.0004);
	float s_w = clamp((EW - wash_wear) / Gw, -80.0, 80.0);
	float s_l = clamp((EL - loss_wear) / Gl, -80.0, 80.0);
	float duw = dw.g * 2.0 - 1.0, dvw = dw.b * 2.0 - 1.0;
	float dul = dl.g * 2.0 - 1.0, dvl = dl.b * 2.0 - 1.0;
	float flaked = 1.0 - smoothstep(-0.15, 0.15, s_w);
	float hole = 1.0 - smoothstep(-0.2, 0.2, s_l);
	float in_w = max(-s_w, 0.0);
	float in_l = max(-s_l, 0.0);

	// побелка
	float dmg = 1.0 - smoothstep(0.0, 9.0, s_w);
	float lift = pow(dmg, 1.3) * (0.35 + RFW * 0.65);
	float crack_w = 1.0 - smoothstep(0.85, 1.6, QW * 4.0);
	float crack_l = 1.0 - smoothstep(0.85, 1.7, QL * 4.0);
	vec3 plaster = pl_alb * rgb(194.0, 188.0, 176.0) * 1.08;
	vec3 white = wash_color * (0.72 + TONE * 0.56);
	white = mix(white, plaster * 1.1, THIN * 0.18);
	white = mix(white, rgb(133.0, 128.0, 117.0), crack_w * 0.55);
	float rim_w = (1.0 - smoothstep(0.05, 0.4, s_w)) * (1.0 - flaked);
	white = mix(white, rgb(242.0, 240.0, 232.0), rim_w * 0.25);
	float t_old = wash_old_share * (0.06 + THIN * 0.1);
	float s_old = (EW - wash_wear + t_old) / Gw;
	float old = flaked * smoothstep(-0.2, 0.2, s_old);
	vec3 under_w = mix(plaster, wash_old_color * (0.85 + TONE * 0.3), old);
	float foot = flaked * (1.0 - smoothstep(0.0, 0.7, in_w));
	under_w *= 1.0 - foot * 0.3;
	vec3 c = mix(white, under_w, flaked);
	float r = mix(0.9 + THIN * 0.04, mix(pl_r, 0.88, old), flaked);
	c = mix(c, rgb(63.0, 58.0, 51.0), crack_l * 0.85);
	float st = min(STAIN * k_stain * 0.6, 1.0);
	c = mix(c, c * rgb(176.0, 154.0, 116.0), st);
	float m = min(MOLD * k_mold, 1.0);
	c = mix(c, rgb(47.0, 51.0, 42.0), m * 0.85);
	r = mix(r, 0.75, m);

	// штукатурка до кирпича / бетона
	float rimw = 3.0 + CRUMB * 7.0;
	float rim_l = (1.0 - hole) * (1.0 - smoothstep(0.0, rimw, s_l));
	c = mix(c, pl_alb * rgb(140.0, 134.0, 123.0), rim_l);
	r = mix(r, 0.95, rim_l);
	float shade = hole * (1.0 - smoothstep(0.0, 22.0, in_l));

	vec3 base = vec3(0.0);
	float rb = 0.9;
	vec3 bn = n;
	if (hole > 0.001) {
		// яма: дальняя стенка (торец штукатурки) и сдвинутый кирпич
		vec3 dvec = march_dir(inc, n);
		float hit = 0.0, t_wall = 1.0;
		for (int k = 1; k <= 8; k++) {
			float tk = float(k) / 8.0;
			vec3 pk = p + dvec * PLASTER_DEPTH_M * tk;
			float el = texture(loss_peel_e, map_uv(surface_uv(pk, t, b, 0.5))).r;
			float solid = 1.0 - step(el, loss_wear);
			float nw = solid * (1.0 - hit);
			t_wall = mix(t_wall, tk, nw);
			hit = max(hit, solid);
		}
		vec2 uvb = map_uv(surface_uv(p + dvec * PLASTER_DEPTH_M, t, b, 0.5));
		if (!concrete) {
			vec2 buv = uvb * 0.72;                     // кирпич 250 мм: тайл скана против тайла 2 м
			vec3 b_alb = texture(brick_albedo, buv).rgb;
			vec2 b_n = nxy(texture(brick_normal, buv));
			float b_r = texture(brick_rough, buv).r;
			base = mix(b_alb, vec3(lum(b_alb)), 0.35) * 0.8;
			float near = 1.0 - smoothstep(0.0, 25.0, in_l);
			float res = smoothstep(0.55, 0.62, RES + near * 0.35);
			base = mix(base, pl_alb * rgb(168.0, 162.0, 150.0), res * 0.85);
			rb = mix(b_r, 0.92, res);
			bn = to_world(vec3(b_n, rebuild_z(b_n)), t, b, n);
		} else {
			vec3 pb = texture(plaster_albedo, uvb).rgb;
			base = pb * rgb(143.0, 141.0, 136.0);
			bn = to_world(vec3(pl_n * 0.3, rebuild_z(pl_n)), t, b, n);
		}
		base *= 1.0 - shade * 0.7;
		vec3 side = pl_alb * rgb(156.0, 150.0, 138.0);
		side = mix(side, wash_color, 1.0 - smoothstep(0.02, 0.06, t_wall));
		side *= 1.0 - t_wall * 0.45;
		base = mix(base, side, hit);
		rb = mix(rb, 0.95, hit);
		bn = normalize(mix(bn, side_normal(inc, n, 0.3), hit));
	}
	color = mix(c, base, hole);
	rough = mix(r, rb, hole);

	// нормаль
	float wx = wn.x + cn.x * lift * 0.8 - duw * rim_w * 0.5;
	float wy = wn.y + cn.y * lift * 0.8 - dvw * rim_w * 0.5;
	float nx = mix(wx, pl_n.x * 0.3, flaked);
	float ny = mix(wy, pl_n.y * 0.3, flaked);
	float nz = mix(rebuild_z(wn), rebuild_z(pl_n), flaked);
	nx -= dul * rim_l * 1.4;
	ny -= dvl * rim_l * 1.4;
	vec3 nw = to_world(vec3(nx, ny, nz), t, b, n);
	normal = normalize(mix(nw, bn, hole));
}
