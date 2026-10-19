shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;
// Износ оружия по прочности экземпляра поверх рабочего состояния 100 % (решение владельца 2026-10-17:
// новые стволы и обвесы текстурируются только в нём, тяжелее износ рисует шейдер).
// Основа — те же карты и правила, что у StandardMaterial3D модели (цвет, нормали, шероховатость, металл,
// AO на непрямой свет); WeaponCondition.wear_material переносит их сюда из материала GLB.
// Маска модели <карты>_wear.png (Non-Color): R — выпуклые кромки, G — углубления, B — места хвата
// (формат — навык godot-asset-preparation, менять только вместе).
// condition — прочность 0..1, своя у каждой модели (instance uniform: материал общий на все экземпляры).
// 1 — ровно карты 100 %. Ниже: покрытие тускнеет и вытирается в местах хвата, кромки стираются до основы,
// царапины, грязь и пыль в углублениях; ниже 0.2 — коррозия: металл ржавеет, фенопласт и пластик
// выцветают и грубеют. Всё — от непрерывных порогов, без ступеней.
// Детальные тайлы общие для всех стволов (tools/gen_weapon_wear_tiles.py): R царапины, G налёт, B ржавчина,
// A сколы — трипланарно в осях модели, размер плитки в метрах один на любой атлас.

uniform vec4 albedo_color : source_color = vec4(1.0);
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_roughness_normal, filter_linear_mipmap, repeat_enable;
uniform float normal_scale = 1.0;
uniform sampler2D roughness_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 roughness_channel = vec4(0.0, 1.0, 0.0, 0.0);
uniform float roughness = 1.0;
uniform sampler2D metallic_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 metallic_channel = vec4(0.0, 0.0, 1.0, 0.0);
uniform float metallic = 0.0;
uniform float specular = 0.5;
uniform sampler2D ao_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 ao_channel = vec4(1.0, 0.0, 0.0, 0.0);
uniform float ao_light_affect = 0.0;
uniform vec3 uv1_scale = vec3(1.0);
uniform vec3 uv1_offset = vec3(0.0);

// Жировая плёнка рук (отпечатки, ладони, масло) — маска <карты>_coat.png (R), если есть (в Blender — Coat Weight от
// канала стека Oil film). Не слоем Clearcoat: лак Godot всегда почти зеркальный и без карты нормалей — вся деталь
// выходила стеклянной («полированный пластик с керамикой», владелец 2026-10-19). След гладит основной слой: там, где
// он есть, шероховатость опускается к film_roughness — в лоб почти не виден, под углом к свету даёт мягкий отблеск.
uniform sampler2D coat_tex : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform float coat_weight = 1.0;
uniform float film_roughness = 0.3;
// Свечение по карте (светонакопительные цифры магазина ВЕРАС-54): emission_tex × emission_color × emission_energy.
uniform sampler2D emission_tex : source_color, hint_default_black, filter_linear_mipmap, repeat_enable;
uniform vec3 emission_color = vec3(0.0);
uniform float emission_energy = 0.0;

uniform sampler2D wear_tex : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform sampler2D detail_tex : hint_default_black, filter_linear_mipmap_anisotropic, repeat_enable;
// плиток детализации на метр модели (8 — плитка ≈ 12 см)
uniform float detail_scale = 8.0;
// Цвета износа — линейные (без source_color: значение по умолчанию тогда не пересчитывается из sRGB и
// выходит вчетверо светлее задуманного). В скобках — то же в sRGB.
// металл под стёртым воронением / краской (0.56) — как стёртые кромки ручных карт ПМ 20
uniform vec3 bare_steel = vec3(0.27, 0.27, 0.285);
// жирная грязь в углублениях (0.07 0.062 0.052) и сухая пыль поверх неё при сильном износе (0.30 0.27 0.22)
uniform vec3 grime_color = vec3(0.006, 0.005, 0.004);
uniform vec3 dust_color = vec3(0.073, 0.06, 0.04);
// ржавчина: тёмная (0.09 0.045 0.028) и рыжая (0.27 0.13 0.06)
uniform vec3 rust_dark = vec3(0.008, 0.0035, 0.0022);
uniform vec3 rust_light = vec3(0.06, 0.015, 0.005);
// насколько оружие намокает в дождь (глобальный rain_wet от RainFx)
uniform float wet_k = 0.7;

instance uniform float condition : hint_range(0.0, 1.0) = 1.0;
global uniform float rain_wet;

varying vec3 obj_pos;
varying vec3 obj_nrm;

void vertex() {
	UV = UV * uv1_scale.xy + uv1_offset.xy;
	obj_pos = VERTEX;
	obj_nrm = NORMAL;
}

// Трипланарная выборка детальных тайлов в осях модели (у подвижных деталей — в осях детали: следы едут с ней).
vec4 detail(vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(4.0));
	w /= max(w.x + w.y + w.z, 1e-4);
	vec3 q = p * detail_scale;
	return texture(detail_tex, q.zy) * w.x
		+ texture(detail_tex, q.xz + vec2(0.37, 0.11)) * w.y
		+ texture(detail_tex, q.xy + vec2(0.71, 0.53)) * w.z;
}

void fragment() {
	vec3 col = (texture(albedo_tex, UV) * albedo_color).rgb;
	float rough = dot(texture(roughness_tex, UV), roughness_channel) * roughness;
	float metal = dot(texture(metallic_tex, UV), metallic_channel) * metallic;
	float ao = dot(texture(ao_tex, UV), ao_channel);
	float spec = specular;
	float u = 1.0 - clamp(condition, 0.0, 1.0);
	// жировая плёнка: с износом остаётся (рукой берут и потёртое), под грязью и пылью тускнеет (ниже)
	float film = texture(coat_tex, UV).r * coat_weight;
	// пористое (грязь, ржавчина, фенопласт) темнеет от воды, металл — только блестит
	float porous = 1.0 - metal;
	if (u > 0.001) {
		vec3 m = texture(wear_tex, UV).rgb;
		vec4 d = detail(obj_pos, obj_nrm);
		float edge = m.r;
		float cav = m.g;
		float hand = m.b;
		float mt = smoothstep(0.3, 0.7, metal);
		// до глубоких мест (канал ствола, щели) рука и ткань не достают — там не вытирается
		float reach = smoothstep(0.3, 0.75, ao);
		// 1. Покрытие в целом тускнеет: тёмное воронение чуть сереет и матовеет (на видимых плоскостях
		// ручных карт ПМ 60/20 оно остаётся почти чёрным — вытирание дают кромки, хват и патина ниже);
		// светлую сталь (ствол) не трогает. Фенопласт и пластик тускнеют и чуть темнеют.
		float c1 = smoothstep(0.0, 0.5, u) * 0.7 + u * 0.3;
		float lum = dot(col, vec3(0.333));
		float coat = (1.0 - smoothstep(0.05, 0.15, lum)) * mt;
		col = mix(col, mix(vec3(lum), col, 0.6) * 1.4, c1 * coat);
		rough = mix(rough, max(rough, 0.42), c1 * coat * (1.0 - hand * 0.5));
		col = mix(col, mix(vec3(lum), col, 0.95) * 0.85, c1 * (1.0 - mt));
		rough = mix(rough, max(rough, 0.26), c1 * (1.0 - mt));
		// 2. Патина: воронение по плоскостям вытирается до серого плавными облаками (B), гуще в местах хвата
		// и у кромок
		// (защищённые места — углубления, канал ствола — не вытираются)
		float pn = (d.b * 0.6 + d.a * 0.15) * (0.35 + 0.65 * max(hand, edge)) + hand * 0.3 + edge * 0.3;
		float tp = 1.3 - 1.3 * u;
		float patina = smoothstep(tp, tp + 0.55, pn) * coat * reach * (1.0 - smoothstep(0.45, 0.85, cav));
		col = mix(col, mix(bare_steel * 0.35, vec3(0.14, 0.125, 0.11), d.g * 0.6), patina * 0.6);
		metal = mix(metal, 1.0, patina * 0.5);
		rough = mix(rough, 0.42, patina * 0.6);
		// 3. Места хвата полируются: металл светлеет и блестит, пластик лоснится и чуть темнеет
		float rub = clamp(hand * smoothstep(0.0, 0.7, u) * (0.6 + 0.5 * d.g), 0.0, 1.0);
		col = mix(col, mix(col, bare_steel * 0.4, 0.35), rub * 0.6 * coat);
		col = mix(col, col * 0.85, rub * 0.45 * (1.0 - mt));
		rough = mix(rough, rough * mix(0.75, 0.6, mt), rub * mix(1.0, coat, mt));
		// 4. Царапины: гуще на кромках и в местах хвата; на металле — до стали, на пластике — белёсые
		float scr = smoothstep(0.35, 0.7, d.r) * smoothstep(0.1, 0.7, u) * mix(0.45, 1.0, max(edge, hand));
		col = mix(col, bare_steel * 0.8, scr * 0.55 * mt);
		col = mix(col, col * 1.6 + 0.035, scr * 0.4 * (1.0 - mt));
		rough = mix(rough, mt > 0.5 ? 0.35 : 0.7, scr * 0.5);
		// 5. Кромки до основы: порог опускается с износом, сколы рвут край, рука стирает сильнее
		// сколы только рвут край кромки (множитель), на плоскости металл не вскрывают
		float e = edge * mix(0.7, 1.35, d.a) * (1.0 + hand * 0.4 * u);
		float te = max(1.1 - 1.7 * u, 0.1);
		// тонкие стенки (канал ствола) маска отмечает кромкой целиком — в защищённом месте не стираются
		float shelter = 1.0 - smoothstep(0.45, 0.85, cav);
		float bare = smoothstep(te, te + 0.15, e) * smoothstep(0.0, 0.08, u) * reach * shelter;
		// стирать нечего у светлой стали (ствол): кромка там остаётся какой была
		float strip = bare * (1.0 - smoothstep(0.08, 0.2, lum) * mt);
		col = mix(col, mix(col * 1.3 + 0.015, bare_steel * mix(0.82, 1.05, d.r), mt), strip * mix(0.3, 1.0, mt));
		metal = mix(metal, 1.0, strip * mt);
		rough = mix(rough, 0.3, strip * mix(0.3, 1.0, mt));
		// 6. Грязь в углублениях и щелях: сперва жирный тёмный налёт, при сильном износе — сухая пыль поверх
		// в самых глубоких местах: широкое дно углубления (эмблема, паз) не заливается целиком
		float g = cav * cav * (0.5 + 0.7 * d.g);
		float tg = max(1.15 - 1.3 * u, 0.12);
		float grime = smoothstep(tg, tg + 0.3, g) * (1.0 - strip);
		// сухая пыль — у краёв углублений, на покрытии и пластике; светлая смазанная сталь (канал ствола) копит
		// тёмный нагар: пыль там, освещённая лампой без тени, читалась светлым пятном
		float dust = smoothstep(0.45, 1.0, u) * smoothstep(0.35, 0.8, d.g) * reach * (1.0 - smoothstep(0.55, 0.9, cav))
				* mix(1.0, coat, mt);
		// на металле цвет под грязью темнеет быстрее, чем падает металличность: иначе полупокрытая светлая
		// сталь (канал ствола) становится светлым матовым диэлектриком и белеет под лампой
		float gcov = grime * mix(0.5, 0.85, mt);
		col = mix(col, mix(grime_color, dust_color, dust), mix(gcov, min(gcov * 2.0, 1.0), mt));
		metal = mix(metal, 0.0, gcov);
		// жирный нагар лоснится (матовый — френелевским бликом белел бы в канале ствола), сухая пыль матовая
		rough = mix(rough, mix(0.5, 0.95, dust), gcov);
		// нагар и сажа почти не отражают; в глубине (канал ствола) свет лампы движок не затеняет — блик гасим
		spec = mix(spec, 0.15 * (1.0 - 0.8 * smoothstep(0.6, 1.0, cav)), gcov);
		// 7. Ниже 20 % — коррозия: металл буреет и ржавеет из углублений и стёртых мест, фенопласт и пластик
		// тускнеют и грубеют
		float k = 1.0 - smoothstep(0.0, 0.2, condition);
		if (k > 0.001) {
			col = mix(col, col * vec3(1.2, 0.98, 0.82), k * 0.6 * mt * (1.0 - strip));
			float r = d.b * 0.65 + cav * 0.3 + strip * 0.2 + patina * 0.15 + d.g * 0.1;
			float tr = mix(1.3, 0.45, k);
			float rust = smoothstep(tr, tr + 0.22, r) * mt;
			col = mix(col, mix(rust_dark, rust_light, smoothstep(0.4, 0.95, d.b * 0.6 + d.g * 0.5)), min(rust * 1.6, 0.95));
			metal = mix(metal, 0.0, rust);
			rough = mix(rough, 0.88, rust);
			porous = max(porous, rust);
			float age = k * (1.0 - mt);
			col = mix(col, mix(col, vec3(dot(col, vec3(0.333))), 0.3) * 0.9, age * 0.5);
			rough = mix(rough, 0.78, age * 0.5);
		}
		porous = max(porous, grime);
		film *= 1.0 - max(gcov, dust * 0.8);
	}
	// жировой след сглаживает поверхность (не грубее film_roughness), карта нормалей остаётся
	rough = mix(rough, min(rough, film_roughness), clamp(film, 0.0, 1.0));
	// дождь: вода сглаживает отражение, пористое темнеет
	float wet = clamp(rain_wet * wet_k, 0.0, 1.0);
	col *= 1.0 - 0.3 * wet * porous;
	rough = mix(rough, min(rough, 0.16), wet * 0.8);
	ALBEDO = col;
	ROUGHNESS = clamp(rough, 0.04, 1.0);
	METALLIC = clamp(metal, 0.0, 1.0);
	SPECULAR = spec;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_scale;
	AO = ao;
	AO_LIGHT_AFFECT = ao_light_affect;
	EMISSION = texture(emission_tex, UV).rgb * emission_color * emission_energy;
}
