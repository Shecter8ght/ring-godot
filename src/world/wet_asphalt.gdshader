shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Мокрый асфальт: PBR-набор (Poly Haven Asphalt 02) + сырость одной величиной.
// wetness 0 — сухо, 0.3 — сырые пятна, 0.7 — мокро целиком, puddles — насколько налиты лужи
// (вода собирается во впадинах: крупный шум + карта высот). Сырой — темнее и гладкий, в лужах —
// зеркало с рябью от капель (rain). Отражения — движка (SSR, небо, пробы). Под крышей — сухо
// (карта RainOcclusion). Сырость ведёт RainFx: копится в дождь, сохнет после — сначала плёнка,
// лужи последними. Повтор плитки ломается второй выборкой с поворотом по крупному шуму.

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D height_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;

group_uniforms surface;
// размер плитки текстуры, м (реально 3 м; крупнее — издали не рябит)
uniform float tile_m = 4.5;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
// с расстояния (м) рельеф и мелкие блики гаснут — изометрия не мерцает
uniform vec2 detail_fade = vec2(14.0, 55.0);
uniform float macro_var : hint_range(0.0, 0.5) = 0.18;
group_uniforms;

group_uniforms wet;
uniform float wetness : hint_range(0.0, 1.0) = 0.0;
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;
// во сколько раз темнеет сырой асфальт (пористое намокает)
uniform float wet_darken : hint_range(0.2, 1.0) = 0.45;
uniform float wet_roughness : hint_range(0.0, 1.0) = 0.11;
uniform float puddle_roughness : hint_range(0.0, 0.3) = 0.03;
// сила отражения: вода под острым углом отражает мало (Френель ~5–15 %) — лужи вышли бы просто
// тёмными; для кадра «всё отражает» — доля зеркала (0 — честная вода, 1 — зеркало)
uniform float puddle_mirror : hint_range(0.0, 1.0) = 0.6;
uniform float film_mirror : hint_range(0.0, 1.0) = 0.18;
// размер пятен луж: частота крупного шума, 1/м
uniform float puddle_freq = 0.16;
// насколько вода держится впадин (карта высот) против крупных пятен
uniform float height_bias : hint_range(0.0, 1.0) = 0.35;
group_uniforms;

// карта «что над головой» (RainOcclusion.bind) — под крышей сухо
uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;

float occ_h(vec2 xz) {
	vec2 uv = (xz - occ_center) / occ_size + 0.5;
	if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) {
		return -1e5;
	}
	return occ_base + textureLod(occ_tex, uv, 0.0).r * occ_range;
}
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	float v = 0.0;
	float a = 0.55;
	for (int i = 0; i < 4; i++) {
		v += a * vnoise(p);
		p = rot * p * 2.03 + 11.7;
		a *= 0.47;
	}
	return v / 0.93;
}
// рябь от капель: в каждой клетке 0.55 м своё кольцо со своим тактом (соседи — чтобы не резались)
vec2 ripples(vec2 p, float t) {
	vec2 g = vec2(0.0);
	vec2 cell = floor(p / 0.55);
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 c = cell + vec2(float(i), float(j));
			vec2 o = hash22(c);
			float ph = fract(t * 0.85 + hash12(c + 17.0));
			vec2 d = p - (c + o) * 0.55;
			float r = length(d);
			float x = (r - ph * 0.3) * 40.0;
			float wave = sin(x) * exp(-x * x * 0.08) * (1.0 - ph) * (1.0 - ph);
			g += (r > 0.0001 ? d / r : vec2(0.0)) * wave;
		}
	}
	return g;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 xz = wpos.xz;
	vec2 uv = xz / tile_m;
	// вторая выборка — крупнее и повёрнута; смесь по крупному шуму ломает повтор плитки
	mat2 rot = mat2(vec2(0.62, 0.78), vec2(-0.78, 0.62));
	vec2 uv2 = rot * uv * 0.61 + vec2(0.37, 0.71);
	float mixk = smoothstep(0.35, 0.65, fbm(xz * 0.045));
	vec3 alb = mix(texture(albedo_tex, uv).rgb, texture(albedo_tex, uv2).rgb, mixk);
	vec3 arm = mix(texture(arm_tex, uv).rgb, texture(arm_tex, uv2).rgb, mixk);
	// нормали (OpenGL): вторая выборка — повёрнута обратно в оси плитки
	vec3 n1 = texture(normal_tex, uv).rgb * 2.0 - 1.0;
	vec3 n2 = texture(normal_tex, uv2).rgb * 2.0 - 1.0;
	n2.xy = transpose(rot) * n2.xy;
	// синий канал не читаем: сжатие карт нормалей его отбрасывает — восстанавливаем
	vec3 nt = vec3(mix(n1.xy, n2.xy, mixk), 0.0);
	nt.z = sqrt(max(1.0 - dot(nt.xy, nt.xy), 0.0));
	float hgt = mix(texture(height_tex, uv).r, texture(height_tex, uv2).r, mixk);
	// крупные пятна — затёртое, заплаты: асфальт не ровного тона
	float macro = fbm(xz * 0.07 + 3.1);
	alb *= 1.0 + (macro - 0.5) * 2.0 * macro_var;

	float dist = length(CAMERA_POSITION_WORLD - wpos);
	float far = smoothstep(detail_fade.x, detail_fade.y, dist);

	// где стоит вода: крупные пятна + мелкий рваный край + впадины рельефа
	float field = fbm(xz * puddle_freq) * (1.0 - height_bias) + (1.0 - hgt) * height_bias;
	field += (fbm(xz * 1.3 + 7.0) - 0.5) * 0.12;
	// под крышей — сухо
	float open = step(occ_h(xz), wpos.y + 0.2);
	float w = wetness * open;
	// плёнка: при малой сырости — пятна и трещины, при большой — всё
	float film = clamp((w * 1.35 - (1.0 - field)) / 0.25, 0.0, 1.0);
	film = max(film, smoothstep(0.85, 1.0, w));
	float lvl = 1.0 - puddles * open * 0.5;
	float pud = smoothstep(lvl, lvl + 0.03, field) * step(0.001, puddles * open);
	film = max(film, pud);

	// сырой — темнее, чуть насыщеннее; в луже — ещё темнее (вода поверх)
	vec3 wet_alb = pow(alb, vec3(1.15)) * wet_darken;
	alb = mix(alb, wet_alb, film);
	alb *= mix(1.0, 0.55, pud);
	float rough = arm.g;
	rough = mix(rough, wet_roughness + rough * 0.12, film);
	rough = mix(rough, puddle_roughness, pud);
	// издали — не зеркалить мелочь (иначе блики мерцают), но мокрое остаётся гладким
	rough = mix(rough, max(rough, 0.08 + 0.1 * (1.0 - film)), far * 0.6 * (1.0 - pud));

	// зеркальность: металличность с серым цветом отражения — отражения (SSR, небо, фонари) ярче
	float mir = max(film * film_mirror * (1.0 - far * 0.3), pud * puddle_mirror);
	ALBEDO = mix(alb, vec3(0.62), mir);
	ROUGHNESS = rough;
	METALLIC = mir;
	SPECULAR = 0.5;
	AO = arm.r;
	AO_LIGHT_AFFECT = 0.25;
	// рельеф: в плёнке слабее, в луже — гладь с рябью
	float ns = normal_strength * mix(1.0, 0.55, film) * (1.0 - pud) * mix(1.0, 0.35, far);
	vec2 rp = ripples(xz, TIME) * pud * rain * (1.0 - far);
	// плитка лежит в мировых осях (u = x, v = z; зелёный вверх по картинке = −z) — нормаль сразу в мире
	vec2 slope = nt.xy * ns;
	vec3 nw = normalize(vec3(slope.x - rp.x * 0.35, max(nt.z, 0.2), -slope.y - rp.y * 0.35));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
