shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;
// Бетон построек территории ТЦ: подпорные стенки террас и двора доков, ступени и площадки лестниц,
// доковая платформа, бортики фонтана и кадки, опоры мостов, отбойники «Нью-Джерси», бордюрный камень
// (MallGround.concrete, наборы Poly Haven). Текстура — по граням коробок StudyGeometry без развёртки:
// боковая грань — мировая горизонталь вдоль грани × высота (линии опалубки горизонтальны и продолжаются на
// соседний кусок той же плоскости), верх — мировые X/Z и свой набор (затёртый бетон). У каждой плоскости свой
// сдвиг и тон (от направления и положения грани): куски стенки по дуге не повторяют друг друга.
// Как стареет бетон у ярославских ТЦ: грязь и брызги у земли, тёмные потёки от верхней кромки, белёсые
// высолы у швов, мох на кромках, затёртые и сбитые рёбра. Где грань — по расстояниям до рёбер (UV/UV2,
// StudyGeometry._edges): тёмный шов на стыке кусков, фаска на верхней кромке.
// Без текстур (use_maps = false) — то же на процедурном зерне. Сырость — от погоды (MallGround.sync_weather).

uniform bool use_maps = true;
// стенки (боковые грани)
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
// верх: свой набор (затёртый бетон), иначе — тот же, что у стенок
uniform bool has_top = false;
uniform sampler2D top_albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D top_normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D top_arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;

group_uniforms look;
// размер плитки текстуры, м (реальный размер набора): стенки и верх
uniform float tile_m = 2.7;
uniform float top_tile_m = 2.0;
// множитель цвета набора (линейный) и насыщенность: стенки и верх
uniform vec3 tint = vec3(1.0);
uniform vec3 top_tint = vec3(1.0);
uniform float saturation : hint_range(0.0, 1.5) = 0.5;
uniform float top_saturation : hint_range(0.0, 1.5) = 0.5;
uniform float normal_strength : hint_range(0.0, 2.0) = 1.0;
uniform float rough_add : hint_range(-0.5, 0.5) = 0.0;
// вторая выборка в пятнах шума ломает повтор внутри грани: у стенок — сдвиг вдоль (линии опалубки
// остаются на своих местах), у верха — поворот и масштаб; 0 — нет
uniform float break_side : hint_range(0.0, 1.0) = 0.0;
uniform float break_top : hint_range(0.0, 1.0) = 1.0;
// крупные пятна тона: сила и размер, м; разный тон граней (разные заливки и камни)
uniform float macro_var : hint_range(0.0, 0.5) = 0.12;
uniform float macro_m = 6.0;
uniform float face_var : hint_range(0.0, 0.3) = 0.06;
// с расстояния (м) рельеф и мелкое гаснут — издали не рябит
uniform vec2 detail_fade = vec2(14.0, 60.0);
group_uniforms;

group_uniforms joints;
// секции вдоль длинной стороны (бордюрный камень около 1 м): кусок делится на равные, м; 0 — нет
uniform float section_m = 0.0;
// шов на стыке кусков: тёмная линия на расстоянии joint_at от ребра, полуширина joint_w, м. Куски стенок
// StudyGeometry кладутся внахлёст по 0,025 м с каждой стороны: линия ровно по стыку одинакова у обоих
// кусков — в нахлёсте не мерцает
uniform float joint_at = 0.025;
uniform float joint_w = 0.007;
uniform float joint_dark : hint_range(0.0, 1.0) = 0.4;
// фаска на верхней кромке, м
uniform float bevel_w = 0.025;
// сколы и затёртость рёбер
uniform float edge_wear : hint_range(0.0, 1.0) = 0.35;
group_uniforms;

group_uniforms weathering;
// грязь и брызги у земли: высота от низа коробки (до трети её высоты), сила, цвет
uniform float base_h = 0.7;
uniform float base_dirt : hint_range(0.0, 1.0) = 0.5;
uniform vec3 base_color : source_color = vec3(0.2, 0.18, 0.14);
// потёки от верхней кромки: длина, м, сила, цвет
uniform float streak_len = 1.8;
uniform float streaks : hint_range(0.0, 1.0) = 0.5;
uniform vec3 streak_color : source_color = vec3(0.13, 0.13, 0.115);
// высолы: белёсые разводы под швами и у кромки
uniform float efflorescence : hint_range(0.0, 1.0) = 0.2;
uniform vec3 effl_color : source_color = vec3(0.8, 0.79, 0.74);
// мох и зелень: на верхе у кромок и внизу у земли
uniform float moss : hint_range(0.0, 1.0) = 0.15;
uniform vec3 moss_color : source_color = vec3(0.13, 0.15, 0.08);
group_uniforms;

group_uniforms fallback;
// без текстур: тон, зерно, щиты опалубки (0 — без швов щитов), м
uniform vec3 base_tone : source_color = vec3(0.42, 0.42, 0.4);
uniform vec3 top_tone : source_color = vec3(0.4, 0.4, 0.38);
uniform float grain : hint_range(0.0, 0.5) = 0.1;
uniform vec2 fb_panel = vec2(0.0);
group_uniforms;

group_uniforms wet;
uniform float wetness : hint_range(0.0, 1.0) = 0.0;
// лужи у бетона не держатся — параметр общий с покрытиями (MallGround.sync_weather)
uniform float puddles : hint_range(0.0, 1.0) = 0.0;
uniform float rain : hint_range(0.0, 1.0) = 0.0;
uniform float wet_darken : hint_range(0.2, 1.0) = 0.55;
uniform float wet_roughness : hint_range(0.0, 1.0) = 0.3;
group_uniforms;

// карта «что над головой» (RainOcclusion.bind) — под крышей сухо
uniform sampler2D occ_tex : hint_default_black, filter_linear, repeat_disable;
uniform vec2 occ_center = vec2(0.0);
uniform float occ_size = 0.0001;
uniform float occ_base = 0.0;
uniform float occ_range = 128.0;

varying vec3 wpos;
varying vec3 wnrm;
// мировые оси текстуры: +u и «вверх по картинке»
varying vec3 ft;
varying vec3 fu;
// координаты текстуры на грани, м (со сдвигом плоскости), тон грани, верх ли это
varying vec2 fuv;
varying float fkey;
varying float ftop;

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
float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 n = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	wnrm = n;
	// положение плоскости грани: у всех её вершин одно и то же — сдвиг и тон грани ровные
	float d = dot(n, wpos);
	if (abs(n.y) < 0.7) {
		ft = normalize(vec3(n.z, 0.0, -n.x));
		fu = cross(n, ft);
		// сдвиг от направления грани: соседние куски дуги (1,5°) — разные места текстуры
		float a = atan(n.z, n.x);
		vec2 off = vec2(sin(a * 61.0 + d * 0.71) * 7.3, sin(a * 37.0 + d * 0.53 + 1.7) * 3.1);
		fuv = vec2(dot(wpos, ft), -dot(wpos, fu)) + off;
		fkey = 0.5 + 0.5 * sin(a * 29.0 + d * 1.9);
		ftop = 0.0;
	} else {
		ft = vec3(1.0, 0.0, 0.0);
		fu = normalize(cross(n, ft));
		fuv = vec2(wpos.x, wpos.z) + vec2(d * 3.7, d * 2.9);
		fkey = 0.5 + 0.5 * sin(d * 7.3);
		ftop = 1.0;
	}
}

void fragment() {
	vec3 n = normalize(wnrm);
	bool top = ftop > 0.5;
	float dist = length(CAMERA_POSITION_WORLD - wpos);
	float far = smoothstep(detail_fade.x, detail_fade.y, dist);
	// размер пикселя на грани, м: сглаживание швов и кромок
	float px = max(length(fwidth(wpos)), 0.001);
	// вдоль грани, м, без сдвига плоскости — для потёков и шума по мировой горизонтали
	float along_w = dot(wpos, ft);

	// где рёбра: у стенки — до вертикальных рёбер, от низа, до верха; у верха — до кромок поперёк, вдоль
	float e_side = min(UV.x, UV.y);
	float h_bot = UV2.x;
	float h_top = UV2.y;
	float box_h = UV2.x + UV2.y;
	float s_along = top ? UV2.x : UV.x;
	float len_along = top ? UV2.x + UV2.y : UV.x + UV.y;
	// шов: на стыке кусков (вертикальные рёбра стенки) и между секциями — у секций и на верху тоже
	float jd = top ? 99.0 : abs(e_side - joint_at);
	if (section_m > 0.0) {
		float count = max(1.0, round(len_along / section_m));
		float sec = len_along / count;
		float js = abs(fract(s_along / sec + 0.5) - 0.5) * sec;
		jd = min(jd, abs(js - joint_at));
	}
	float joint = (1.0 - smoothstep(joint_w, joint_w + px, jd)) * (1.0 - far * 0.7);
	// до кромки: у стенки — верхняя, у верха — поперечные
	float e_edge = top ? min(UV.x, UV.y) : h_top;

	vec3 alb;
	vec3 arm;
	vec2 nxy;
	vec2 g = fuv;
	if (use_maps) {
		float tile = top ? top_tile_m : tile_m;
		vec2 uv = fuv / tile;
		vec2 uv2;
		mat2 rot = mat2(vec2(0.62, 0.78), vec2(-0.78, 0.62));
		float brk = top ? break_top : break_side;
		if (top) {
			uv2 = rot * uv * 0.61 + vec2(0.37, 0.71);
		} else {
			// только вдоль: горизонтальные линии опалубки не двоятся
			uv2 = uv + vec2(0.437, 0.0);
		}
		float n_low = vnoise(fuv * 0.31 + 5.3) * 0.65 + vnoise(fuv * 0.83 + 1.7) * 0.35;
		float mixk = smoothstep(0.35, 0.65, n_low) * brk;
		vec3 a1;
		vec3 a2;
		vec3 r1;
		vec3 r2;
		vec2 n1;
		vec2 n2;
		if (top && has_top) {
			a1 = texture(top_albedo_tex, uv).rgb;
			a2 = texture(top_albedo_tex, uv2).rgb;
			r1 = texture(top_arm_tex, uv).rgb;
			r2 = texture(top_arm_tex, uv2).rgb;
			n1 = texture(top_normal_tex, uv).rg * 2.0 - 1.0;
			n2 = texture(top_normal_tex, uv2).rg * 2.0 - 1.0;
		} else {
			a1 = texture(albedo_tex, uv).rgb;
			a2 = texture(albedo_tex, uv2).rgb;
			r1 = texture(arm_tex, uv).rgb;
			r2 = texture(arm_tex, uv2).rgb;
			n1 = texture(normal_tex, uv).rg * 2.0 - 1.0;
			n2 = texture(normal_tex, uv2).rg * 2.0 - 1.0;
		}
		if (top) {
			n2 = transpose(rot) * n2;
		}
		alb = mix(a1, a2, mixk);
		arm = mix(r1, r2, mixk);
		nxy = mix(n1, n2, mixk);
		// приглушить цвет набора (фотоскан бывает рыжим), подвести тон
		float l = dot(alb, vec3(0.3, 0.59, 0.11));
		alb = top ? mix(vec3(l), alb, top_saturation) * top_tint : mix(vec3(l), alb, saturation) * tint;
	} else {
		// процедурное зерно: заполнитель и раковины, у стенок — швы щитов опалубки
		vec2 q = g / 0.03;
		float fine = vnoise(q) * 0.6 + vnoise(q * 2.7 + 3.1) * 0.4;
		float mid = vnoise(g * 1.7);
		fine = mix(fine, 0.5, far);
		vec3 tone = top ? top_tone : base_tone;
		alb = tone * (1.0 + (fine - 0.5) * 2.0 * grain + (mid - 0.5) * grain * 0.8);
		arm = vec3(1.0, 0.85 + (fine - 0.5) * 0.1, 0.0);
		float nx = vnoise(q + vec2(0.5, 0.0)) - vnoise(q - vec2(0.5, 0.0));
		float ny = vnoise(q + vec2(0.0, 0.5)) - vnoise(q - vec2(0.0, 0.5));
		nxy = vec2(nx, -ny) * grain * 1.2 * (1.0 - far);
		if (!top && fb_panel.x > 0.0) {
			vec2 pq = fuv / fb_panel;
			vec2 e = min(fract(pq), 1.0 - fract(pq)) * fb_panel;
			float line_k = 1.0 - smoothstep(0.004, 0.004 + px, min(e.x, e.y));
			alb *= 1.0 - line_k * 0.25 * (1.0 - far);
		}
	}

	// крупные пятна тона и свой тон у каждой грани (разные заливки)
	float macro = vnoise(fuv / macro_m + 3.1) * 0.6 + vnoise(fuv * 2.7 / macro_m) * 0.4;
	alb *= (1.0 + (macro - 0.5) * 2.0 * macro_var) * (1.0 + (fkey - 0.5) * 2.0 * face_var);
	if (section_m > 0.0) {
		float count = max(1.0, round(len_along / section_m));
		alb *= 1.0 + (hash12(vec2(floor(s_along / len_along * count), fkey * 31.0 + len_along)) - 0.5) * 2.0 * face_var;
	}

	// рёбра: сбитые и затёртые — светлее и шершавее, местами
	float wear_line = 1.0 - smoothstep(0.0, 0.035 + px, e_edge);
	float wear = wear_line * edge_wear * smoothstep(0.3, 0.6, vnoise(vec2(s_along * 9.0, fkey * 17.0)));
	alb = mix(alb, alb * 1.2 + 0.015, wear);
	arm.g = mix(arm.g, 0.95, wear);

	float streak = 0.0;
	float base_k = 0.0;
	if (!top) {
		// грязь и брызги у земли: неровная граница, внизу плотнее, местами зелень
		float band = min(base_h, box_h * 0.33);
		float edge_n = (vnoise(vec2(along_w * 2.3, 1.7)) - 0.5) * band * 0.6;
		base_k = 1.0 - smoothstep(band * 0.15, band, h_bot + edge_n);
		base_k *= 0.75 + 0.25 * vnoise(vec2(along_w * 6.0, h_bot * 9.0));
		alb = mix(alb, base_color, base_k * base_dirt);
		float green = smoothstep(0.55, 0.8, vnoise(vec2(along_w * 0.8, 4.4)));
		alb = mix(alb, moss_color, base_k * green * moss);
		// потёки от верхней кромки: дорожки разной длины с разрывами, чуть виляют
		if (streaks > 0.0 && far < 0.98) {
			float su = along_w + (vnoise(vec2(along_w * 0.7, h_top * 1.3)) - 0.5) * 0.12;
			float lane = vnoise(vec2(su * 2.2, 3.1)) * 0.6 + vnoise(vec2(su * 7.5, 9.7)) * 0.4;
			float len_k = mix(0.2, 1.0, vnoise(vec2(su * 0.9, 5.3))) * min(streak_len, box_h * 0.8);
			streak = smoothstep(0.45, 0.75, lane) * (1.0 - smoothstep(0.0, len_k, h_top));
			streak *= 0.55 + 0.45 * vnoise(vec2(su * 13.0, h_top * 3.0));
			// под самой кромкой — сплошная тёмная полоса стока
			streak = max(streak, (1.0 - smoothstep(0.0, 0.12, h_top)) * 0.5);
			streak *= 1.0 - far * 0.5;
			alb = mix(alb, streak_color, streak * streaks);
		}
		// высолы: белёсое под швами кусков и пятнами у кромки
		if (efflorescence > 0.0) {
			float near_joint = 1.0 - smoothstep(0.05, 0.45, e_side);
			float bloom = smoothstep(0.45, 0.75, vnoise(vec2(along_w * 1.7, h_top * 0.7 + 2.0)));
			float ek = near_joint * bloom * (1.0 - smoothstep(0.0, box_h * 0.7, h_top));
			alb = mix(alb, effl_color, ek * efflorescence);
		}
	} else if (moss > 0.0) {
		// верх: зелень и грязь у кромок и в углах
		float mk = smoothstep(0.5, 0.8, vnoise(wpos.xz * 1.3 + 2.0)) * (1.0 - smoothstep(0.0, 0.18, e_edge));
		alb = mix(alb, moss_color, mk * moss);
	}

	// шов: тёмная щель, шершавее
	alb = mix(alb, alb * (1.0 - joint_dark), joint);
	arm.g = mix(arm.g, 1.0, joint);

	// ---------------------------------------------------------------- сырость
	float rough = clamp(arm.g + rough_add, 0.04, 1.0);
	if (wetness > 0.001) {
		// под крышей сухо: у стенки — что над землёй перед ней (над самой стенкой карта видит её верх)
		vec2 probe = wpos.xz + (top ? vec2(0.0) : n.xz * 0.5);
		float open = step(occ_h(probe), wpos.y + 0.2);
		float wk = wetness * open;
		// стенки мокнут потёками сверху и брызгами внизу, верх — целиком
		if (!top) {
			wk *= clamp(0.55 + streak * 0.6 + base_k * 0.4, 0.0, 1.0);
		}
		float film = clamp(wk * (0.9 + 0.4 * vnoise(fuv * 1.1)), 0.0, 1.0);
		alb = mix(alb, pow(alb, vec3(1.15)) * wet_darken, film);
		rough = mix(rough, wet_roughness + rough * 0.15, film);
	}
	// издали — не блестеть мелочью
	rough = mix(rough, max(rough, 0.5), far * 0.5);
	ALBEDO = alb;
	ROUGHNESS = rough;
	METALLIC = 0.0;
	SPECULAR = 0.5;
	AO = arm.r * mix(1.0, 0.6, joint);
	AO_LIGHT_AFFECT = 0.25;

	// рельеф набора; фаска на верхней кромке стенки — нормаль к небу
	float ns = normal_strength * mix(1.0, 0.35, far);
	vec2 slope = nxy * ns;
	float nz = sqrt(max(1.0 - dot(nxy, nxy), 0.04));
	vec3 nw = normalize(ft * slope.x + fu * slope.y + n * max(nz, 0.2));
	if (!top) {
		float bevel = 1.0 - smoothstep(bevel_w * 0.5, bevel_w + px, h_top);
		nw = normalize(mix(nw, normalize(n + vec3(0.0, 1.2, 0.0)), bevel * (1.0 - far)));
	}
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
