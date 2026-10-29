// Паркет «ёлочкой» v03 (tools/dorm_modules/floor_v3.py): дуб под старым лаком; выбитые и обломанные планки — ямы
// в толщину планки (15 мм): видна боковая грань соседней планки, мастика на дне сдвинута вдаль по взгляду.
// Раскладка повёрнута на 45° (surface_frame diag), тайл 2,1 м. Номер планки и её «плохое место» — без сглаживания:
// порог «выбита» не должен плыть на стыках.

uniform sampler2D floor_wood : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D floor_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D floor_masks : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D floor_masks_n : filter_nearest, repeat_enable;
uniform sampler2D floor_wear : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D floor_mastic : filter_linear_mipmap, repeat_enable;
uniform sampler2D floor_break : filter_linear_mipmap, repeat_enable;
uniform sampler2D floor_break_n : filter_nearest, repeat_enable;
uniform sampler2D floor_break_normal : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float parquet_missing = 0.05;
uniform float parquet_broken = 0.14;
uniform float parquet_cracked = 0.12;
uniform float parquet_gouged = 0.25;
uniform float parquet_worn = 1.0;
uniform float parquet_dirt = 1.0;
uniform vec3 parquet_lacquer : source_color = vec3(0.549, 0.424, 0.298);

const float PLANK_DEPTH_M = 0.015;
const float PARQUET_SCALE = 1.0 / 2.1;

float parquet_m(float cluster) {
	return parquet_missing * max(cluster * 1.6 - 0.3, 0.0);
}

// 1 — на месте ямы: выбита целиком или отломанная часть обломанной планки.
float parquet_hole(vec2 uv, out float gd) {
	float rid = texture(floor_masks_n, uv).r;
	gd = texture(floor_masks, uv).g * 4.0;
	float cluster = texture(floor_break_n, uv).a;
	float piece = texture(floor_break, uv).r;
	float m = parquet_m(cluster);
	float k = m / max(parquet_missing, 0.0001);
	float m2 = m + parquet_broken * k;
	float whole = step(rid, m - 1e-6);
	float part = step(m, rid) * step(rid, m2 - 1e-6);
	return max(whole, part * smoothstep(0.45, 0.55, piece));
}

float mastic_h(vec2 uv) {
	vec4 mm = texture(floor_mastic, uv);
	return mm.g * 0.4 + mm.b * 0.6;
}

void parquet_layer(vec3 p, vec3 inc, vec3 noise, out vec3 color, out float rough, out vec3 normal) {
	vec3 t, b, n;
	surface_frame(vec3(0.0, 1.0, 0.0), true, t, b, n);
	vec2 uv = map_uv(surface_uv(p, t, b, PARQUET_SCALE));
	vec3 wood = texture(floor_wood, uv).rgb;
	vec2 fn = nxy(texture(floor_normal, uv));
	vec4 fm = texture(floor_masks, uv);
	vec4 fmn = texture(floor_masks_n, uv);
	vec4 wr = texture(floor_wear, uv);
	vec4 br = texture(floor_break, uv);
	float cluster = texture(floor_break_n, uv).a;
	vec2 bn = nxy(texture(floor_break_normal, uv));
	float RID = fmn.r, RID2 = fmn.a, GD = fm.g, SPLIT = fm.b;
	float SCR = wr.r, DENT = wr.g, WATER = wr.b, GRIME = wr.a;
	float PIECE = br.r, FRINGE = br.g, GOUGE = br.b;

	float m = parquet_m(cluster);
	float spot_k = m / max(parquet_missing, 0.0001);
	float m2 = m + parquet_broken * spot_k;
	float whole = step(RID, m - 1e-6);
	float part = step(m, RID) * step(RID, m2 - 1e-6);
	float missing = max(whole, part * smoothstep(0.45, 0.55, PIECE));
	float m3 = m2 + parquet_cracked * spot_k;
	float broken = step(m2, RID) * step(RID, m3 - 1e-6) * SPLIT;
	float fresh = part * FRINGE;
	float gouge = step(RID2, parquet_gouged * (0.4 + spot_k)) * GOUGE;
	float raw = max(fresh, gouge);
	float worn = min(smoothstep(0.42, 0.75, noise.x) * parquet_worn, 1.0);
	float gd = GD * 4.0;

	// дерево под старым лаком
	vec3 calm = mix(wood, vec3(lum(wood)), 0.55);
	vec3 aged = calm * parquet_lacquer * 0.95;
	vec3 bare = mix(calm, rgb(154.0, 143.0, 128.0) * lum(wood), 0.7) * 0.72;
	vec3 c = mix(aged, bare, worn);
	c = mix(c, rgb(168.0, 148.0, 120.0), SCR * 0.12 * (1.0 - worn));
	c = mix(c, rgb(58.0, 44.0, 32.0), DENT * 0.4);
	c = mix(c, c * rgb(90.0, 80.0, 72.0), min(WATER * 0.45, 1.0));
	c = mix(c, c * rgb(106.0, 96.0, 86.0), min(GRIME * parquet_dirt * (0.45 + worn * 0.4), 1.0));
	float gap = 1.0 - smoothstep(0.15, 0.9, gd);
	c = mix(c, rgb(23.0, 17.0, 12.0), gap * 0.9);
	c = mix(c, rgb(18.0, 13.0, 9.0), broken * 0.92);
	vec3 raw_c = mix(calm, rgb(160.0, 138.0, 108.0), 0.45) * 0.85;
	raw_c = mix(raw_c, raw_c * rgb(94.0, 79.0, 64.0), gouge * 0.6);
	c = mix(c, raw_c, raw * 0.9);
	float r = mix(0.3 + RID2 * 0.1, 0.72, worn);
	r += SCR * (1.0 - worn) * 0.35 + GRIME * 0.15 + WATER * 0.12;
	r = mix(r, 0.9, gap);
	r = mix(r, 0.85, raw);
	vec3 n_wood = to_world(vec3(fn + bn * raw, rebuild_z(fn)), t, b, n);

	color = c;
	rough = r;
	normal = n_wood;
	if (missing > 0.001) {
		// яма: шаги вглубь до толщины планки
		vec3 dvec = march_dir(inc, n);
		float hit = 0.0, t_wall = 1.0, gd_floor = 0.0;
		for (int k = 1; k <= 8; k++) {
			float tk = float(k) / 8.0;
			vec3 pk = p + dvec * PLANK_DEPTH_M * tk;
			float gdk;
			float solid = 1.0 - parquet_hole(map_uv(surface_uv(pk, t, b, PARQUET_SCALE)), gdk);
			float nw = solid * (1.0 - hit);
			t_wall = mix(t_wall, tk, nw);
			hit = max(hit, solid);
			gd_floor = gdk;
		}
		vec2 uvb = map_uv(surface_uv(p + dvec * PLANK_DEPTH_M, t, b, PARQUET_SCALE));
		vec4 mm = texture(floor_mastic, uvb);
		vec3 mastic = rgb(21.0, 18.0, 16.0) * (0.75 + mm.r * 0.5);
		mastic = mix(mastic, rgb(38.0, 33.0, 28.0), mm.g * 0.2);
		mastic = mix(mastic, calm * 0.45, mm.b * 0.7);
		mastic = mix(mastic, rgb(78.0, 73.0, 67.0), mm.a * 0.5);
		float hole_ao = 1.0 - smoothstep(0.0, 9.0, gd_floor);
		mastic *= 1.0 - hole_ao * 0.65;
		// торец старой планки пропитан мастикой и пылью — темнее лакированного верха; сверху — кромка под лаком
		vec3 side = mix(aged, rgb(58.0, 42.0, 28.0), 0.35) * (0.7 - t_wall * 0.4);
		side = mix(side, aged, (1.0 - smoothstep(0.0, 0.1, t_wall)) * 0.5);
		vec3 hole_c = mix(mastic, side, hit);
		color = mix(c, hole_c, missing);
		rough = mix(r, mix(mix(0.78, 0.95, mm.a), 0.85, hit), missing);
		// мастика: рельеф гребней по разности соседних выборок (как узел Bump: сила 0,6, высота 0,4 мм)
		float e = 1.0 / 2048.0;
		float h0 = mastic_h(uvb);
		float hu = (mastic_h(uvb + vec2(e, 0.0)) - h0) / e * PARQUET_SCALE;
		float hv = -(mastic_h(uvb + vec2(0.0, e)) - h0) / e * PARQUET_SCALE;
		vec3 n_mastic = normalize(n - 0.6 * 0.0004 * (hu * t + hv * b));
		vec3 n_hole = normalize(mix(n_mastic, side_normal(inc, n, 0.45), hit));
		normal = normalize(mix(n_wood, n_hole, missing));
	}
}
