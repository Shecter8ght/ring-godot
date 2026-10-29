// Плитка 200 × 200 v03 (tools/dorm_modules/tiles_v3.py): глазурь с бликами по плиткам, цек, потёки ржавчины,
// известь, грязный шов; выбитая плитка — яма в толщину плитки (8 мм) с клеем на дне, скол — черепок.
// Решение «выбита / скол / трещина» — одно на плитку: шум берётся в центре плитки (сетка 0,2 м мира).

uniform sampler2D tile_masks : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tile_masks_n : filter_nearest, repeat_enable;
uniform sampler2D tile_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tile_tone : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tile_glue : filter_linear_mipmap, repeat_enable;
uniform float tile_missing = 0.06;
uniform float tile_chipped = 0.12;
uniform float tile_cracked = 0.16;
uniform float tile_rust = 1.0;
uniform float tile_lime = 1.0;

const float TILE_DEPTH_M = 0.008;

float tile_m(vec3 p) {
	vec3 c = (floor(p * 5.0 + 0.0002) + 0.5) * 0.2;
	float nz = noise_at(c).a;
	return tile_missing * max(nz * 1.6 - 0.3, 0.0);
}

float glue_h(vec2 uv) {
	vec4 g = texture(tile_glue, uv);
	return g.r * 0.8 + g.g * 0.2;
}

// glaze, body — цвет глазури и черепка (у метлахской плитки окрашен насквозь); floor_dirt 1 — пол; low — низ стены.
void tile_layer(vec3 p, vec3 inc, vec3 t, vec3 b, vec3 n, vec3 glaze, vec3 body, float floor_dirt, float low_k,
		out vec3 color, out float rough, out vec3 normal) {
	vec2 uv = map_uv(surface_uv(p, t, b, 0.5));
	vec4 mk = texture(tile_masks, uv);
	float RID = texture(tile_masks_n, uv).r;
	vec4 tt = texture(tile_tone, uv);
	vec2 tn = nxy(texture(tile_normal, uv));
	vec4 gl = texture(tile_glue, uv);
	float DE = mk.g, CRK = mk.b, CHIP = mk.a;
	float TONE = tt.r, CRAZE = tt.g, RUST = tt.b, LIME = tt.a;
	float BISC = gl.b, GDIRT = gl.a;

	float m1 = tile_m(p);
	float spot = m1 / max(tile_missing, 0.0001);
	float m2 = m1 + tile_chipped * spot;
	float m3 = m2 + tile_cracked * spot;
	float missing = step(RID, m1 - 1e-6);
	float chipped = step(m1, RID) * step(RID, m2 - 1e-6) * CHIP;
	float cracked = step(m2, RID) * step(RID, m3 - 1e-6) * CRK;
	float de = DE * 8.0;
	float grout = 1.0 - smoothstep(0.0, 0.25, de);

	float low = low_k * (1.0 - floor_dirt);
	vec3 c = glaze * (0.78 + TONE * 0.44);
	c = mix(c, rgb(140.0, 138.0, 130.0), CRAZE * 0.35);
	float rust_w = RUST * tile_rust * (1.0 - floor_dirt);
	c = mix(c, c * rgb(122.0, 70.0, 32.0), min(rust_w, 1.0));
	c = mix(c, c * rgb(184.0, 173.0, 148.0), (0.15 + GDIRT * 0.3) * (1.0 - floor_dirt));
	c = mix(c, rgb(220.0, 214.0, 196.0), min(LIME * tile_lime * (0.12 + low * 0.3), 1.0));
	c = mix(c, c * rgb(138.0, 128.0, 112.0), low * 0.35 + floor_dirt * (0.25 + GDIRT * 0.35));
	vec3 grout_c = rgb(126.0, 122.0, 114.0) * (1.0 - GDIRT * 0.6);
	grout_c = mix(grout_c, rgb(44.0, 42.0, 36.0), min(low * 0.9 + floor_dirt * 0.5, 1.0));
	c = mix(c, grout_c, grout);
	c = mix(c, rgb(42.0, 39.0, 34.0), cracked * 0.9);
	vec3 bisc = body * (0.8 + BISC * 0.35);
	c = mix(c, bisc, chipped);
	float r = 0.07 + LIME * tile_lime * 0.35 + CRAZE * 0.08 + floor_dirt * 0.3 + low * 0.15;
	r = mix(r, 0.92, grout);
	r = mix(r, 0.85, chipped);
	vec3 n_tile = to_world(vec3(tn, rebuild_z(tn)), t, b, n);

	color = c;
	rough = r;
	normal = n_tile;
	if (missing > 0.5) {
		vec3 dvec = march_dir(inc, n);
		float hit = 0.0, t_wall = 1.0, de_floor = 0.0;
		for (int k = 1; k <= 8; k++) {
			float tk = float(k) / 8.0;
			vec3 pk = p + dvec * TILE_DEPTH_M * tk;
			vec2 uk = map_uv(surface_uv(pk, t, b, 0.5));
			float solid = 1.0 - step(texture(tile_masks_n, uk).r, tile_m(pk) - 1e-6);
			float nw = solid * (1.0 - hit);
			t_wall = mix(t_wall, tk, nw);
			hit = max(hit, solid);
			de_floor = texture(tile_masks, uk).g * 8.0;
		}
		vec2 uvb = map_uv(surface_uv(p + dvec * TILE_DEPTH_M, t, b, 0.5));
		vec4 gb = texture(tile_glue, uvb);
		vec3 glue = rgb(143.0, 138.0, 126.0) * (0.7 + gb.g * 0.4);
		glue = mix(glue, rgb(168.0, 163.0, 150.0), gb.r * 0.3);
		float ao = 1.0 - smoothstep(0.0, 10.0, de_floor + 1.5);
		glue *= 1.0 - ao * 0.55;
		// кромка соседней плитки: сверху глазурь ~0,5 мм, ниже черепок; книзу темнее
		vec3 edge = mix(glaze, body * 0.95, smoothstep(0.05, 0.12, t_wall));
		edge *= 1.1 - t_wall * 0.5;
		color = mix(glue, edge, hit);
		rough = mix(0.9, 0.8, hit);
		float e = 1.0 / 2048.0;
		float h0 = glue_h(uvb);
		float hu = (glue_h(uvb + vec2(e, 0.0)) - h0) / e * 0.5;
		float hv = -(glue_h(uvb + vec2(0.0, e)) - h0) / e * 0.5;
		vec3 n_glue = normalize(n - 0.7 * 0.0008 * (hu * t + hv * b));
		normal = normalize(mix(n_glue, side_normal(inc, n, 0.35), hit));
	}
}
