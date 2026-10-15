shader_type spatial;
render_mode blend_mix, depth_draw_never, depth_test_disabled, cull_front, diffuse_burley, specular_schlick_ggx;
// Растекающаяся кровь (BloodFx): лужа под телом, подтёк на стене. Узел — коробка 1×1×1 (масштабом —
// размер): ось Y — нормаль поверхности (вдоль неё проецируем), Z — куда течёт (вниз по уклону / по
// стене). Поверхность под коробкой берём из глубины кадра — кровь ложится на асфальт, ступени, землю,
// траву как есть (своя «декаль» с шейдером: у Decal движка шейдеров нет).
// Карта (tools/gen_blood_maps.py): R — когда сюда дотечёт (0..1), G — толщина слоя, B — неровность.
// Прогресс растёт быстро, потом всё медленнее; за фронтом слой толстеет. Свежая — тёмно-красная, тонкая
// плёнка светлее и прозрачнее, гладкая, с бликом по краю (мениск); за dry_sec темнеет до бурого и
// матовеет, края — раньше середины.

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform sampler2D normal_rough_tex : hint_normal_roughness_texture, filter_nearest;
uniform sampler2D maps : filter_linear, repeat_disable;
// без карт (ассетов нет) — форма из шума
uniform bool has_maps = true;
uniform sampler2D fallback_noise : filter_linear, repeat_enable;
uniform vec3 wet_thin : source_color = vec3(0.36, 0.02, 0.018);
uniform vec3 wet_thick : source_color = vec3(0.13, 0.006, 0.006);
uniform vec3 dried_color : source_color = vec3(0.12, 0.045, 0.035);
uniform float normal_k = 3.0;

// часы эффектов (BloodFx): глобальные, не TIME — тот обнуляется раз в час
global uniform float fx_time;

// xy — начало клетки атласа, zw — её размер
instance uniform vec4 cell_rect = vec4(0.0, 0.0, 1.0, 1.0);
// x — когда началось, y — за сколько растечётся, z — когда остановилась (подняли, утащили), w — до какой доли
instance uniform vec4 timing = vec4(0.0, 30.0, 1e9, 1.0);
// x — своя случайность, y — за сколько высохнет, с
instance uniform vec4 look = vec4(0.0, 420.0, 0.0, 0.0);

varying mat4 v_inv;

void vertex() {
	v_inv = inverse(MODEL_MATRIX);
}

vec4 sample_map(vec2 uv) {
	if (!has_maps) {
		vec2 c = uv - vec2(0.5, 0.42);
		float n = texture(fallback_noise, uv * 1.7 + look.x).r;
		float a = length(c * vec2(1.0, 0.8)) * 2.1 * (0.75 + 0.5 * n);
		return vec4(clamp(a, 0.0, 1.0), clamp(1.0 - a, 0.0, 1.0) * 0.8, n, 1.0);
	}
	vec2 tex = vec2(textureSize(maps, 0));
	vec2 half_px = 0.5 / (tex * cell_rect.zw);
	return texture(maps, cell_rect.xy + clamp(uv, half_px, 1.0 - half_px) * cell_rect.zw);
}

void fragment() {
	float depth = texture(depth_tex, SCREEN_UV).r;
	vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	view.xyz /= view.w;
	vec3 world = (INV_VIEW_MATRIX * vec4(view.xyz, 1.0)).xyz;
	vec3 local = (v_inv * vec4(world, 1.0)).xyz;
	if (abs(local.x) > 0.5 || abs(local.y) > 0.5 || abs(local.z) > 0.5) {
		discard;
	}
	// поверхность, на которую ложимся: стены у края лужи и бока тел не красим
	vec3 nv = texture(normal_rough_tex, SCREEN_UV).xyz * 2.0 - 1.0;
	vec3 nw = normalize((INV_VIEW_MATRIX * vec4(nv, 0.0)).xyz);
	vec3 bx = normalize(MODEL_MATRIX[0].xyz);
	vec3 by = normalize(MODEL_MATRIX[1].xyz);
	vec3 bz = normalize(MODEL_MATRIX[2].xyz);
	float facing = dot(nw, by);
	// камешки асфальта наклонены по карте нормалей — отсекаем только стены и бока предметов
	if (facing < 0.2) {
		discard;
	}
	vec2 uv = local.xz + 0.5;
	vec4 m = sample_map(uv);
	float arrival = m.r;
	if (arrival > 0.995) {
		discard;
	}
	float t = min(fx_time, timing.z) - timing.x;
	float k = clamp(t / max(timing.y, 0.01), 0.0, 1.0);
	float p = (1.0 - pow(1.0 - k, 2.4)) * timing.w;
	float front = 1.0 - smoothstep(p - 0.012, p + 0.002, arrival);
	if (front <= 0.002) {
		discard;
	}
	// за фронтом слой нарастает
	float behind = clamp((p - arrival) / 0.14, 0.0, 1.0);
	float th = m.g * (0.3 + 0.7 * behind);
	// сохнет: сперва тонкие края, толстая середина — позже
	float age = fx_time - timing.x;
	float dry = clamp(age / max(look.y, 1.0) * (1.6 - th), 0.0, 1.0);
	dry = smoothstep(0.0, 1.0, dry);
	vec3 col = mix(wet_thin, wet_thick, smoothstep(0.05, 0.75, th));
	col *= 0.95 + 0.1 * m.b;
	col = mix(col, dried_color * (0.75 + 0.5 * (1.0 - th)), dry);
	// нормаль от толщины: блик на мениске по краю и на сгустках
	vec2 px = 1.0 / vec2(textureSize(maps, 0)) / max(cell_rect.zw, vec2(0.001));
	float tx = sample_map(uv + vec2(px.x, 0.0)).g - sample_map(uv - vec2(px.x, 0.0)).g;
	float tz = sample_map(uv + vec2(0.0, px.y)).g - sample_map(uv - vec2(0.0, px.y)).g;
	vec3 nl = normalize(vec3(-tx * normal_k * (1.0 - dry * 0.6), 1.0, -tz * normal_k * (1.0 - dry * 0.6)));
	// густая кровь заливает неровности: поверхность гладкая (ось коробки), тонкая плёнка — по рельефу
	vec3 up = normalize(mix(nw, by, smoothstep(0.0, 0.12, th)));
	vec3 n = normalize(bx * nl.x + up * nl.y + bz * nl.z);
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
	LIGHT_VERTEX = view.xyz;
	ALBEDO = col;
	// у прозрачного нет отражений окружения (SSR): гладкая лужа отражала бы одно светлое небо и
	// белела. Затеняем рассеянный свет и отражение неба, как будто вокруг стены и тела; прямой
	// свет (солнце, фонари) и его блик — как есть
	AO = 0.45;
	AO_LIGHT_AFFECT = 0.0;
	METALLIC = 0.0;
	// под скользящим углом гладкая лужа отражала бы небо почти целиком — а в жизни там отражаются
	// стены и тела рядом; гасим отражение к горизонту (малый SPECULAR в движке гасит и край Френеля)
	float ndv = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	SPECULAR = mix(0.42, 0.3, dry) * mix(0.08, 1.0, smoothstep(0.12, 0.55, ndv));
	ROUGHNESS = mix(mix(0.1, 0.24, 1.0 - smoothstep(0.0, 0.4, th)), 0.62, dry);
	ALPHA = front * mix(0.72, 0.97, smoothstep(0.0, 0.35, th)) * smoothstep(0.2, 0.45, facing);
}
