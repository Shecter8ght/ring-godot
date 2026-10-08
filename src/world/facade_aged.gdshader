shader_type spatial;
// Наружный фасад после многих лет без ремонта и двух лет без людей: PBR из текстур (UV в метрах)
// плюс старение в мировых координатах — пятна против повтора, грязь и сырость у земли (брызги
// дождя), подтёки сверху вниз, тёмная полоса под парапетом (стекает с кровли), мох у цоколя.
// Высота считается от начала координат модели (низ здания), а не от нуля мира: дома на рельефе.

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float uv_scale = 0.5;
// контраст фототекстуры: <1 — спокойнее (крупа панелей не рябит издали)
uniform float contrast = 1.0;
uniform float normal_scale = 0.8;
uniform float roughness = 1.0;
uniform bool use_metal = false;
// матовость сухой поверхности: бетон, кирпич, дерево не дают глянцевого отблеска против солнца
uniform float rough_min = 0.72;
// сырость в дождь (RainFx): темнее, глаже, блестит
global uniform float rain_wet;

uniform sampler2D macro_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D streak_tex : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform float macro_amount = 0.22;
uniform float splash_height = 0.9;
uniform float splash = 0.55;
uniform vec3 grime_color : source_color = vec3(0.24, 0.21, 0.17);
uniform float streaks = 0.45;
// высота верха стены над низом модели: под ней — полоса стока с кровли
uniform float roof_height = 15.0;
uniform float roof_runoff = 0.35;
uniform vec3 moss_color : source_color = vec3(0.2, 0.24, 0.12);
uniform float moss = 0.25;

varying vec3 wpos;
varying vec3 wnrm;
varying float base_y;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize(mat3(MODEL_MATRIX) * NORMAL);
	base_y = MODEL_MATRIX[3].y;
}

void fragment() {
	vec2 uv = UV * uv_scale;
	vec4 base = texture(albedo_tex, uv);
	float lum = dot(base.rgb, vec3(0.333));
	base.rgb = mix(vec3(lum), base.rgb, 0.85);
	base.rgb = mix(vec3(0.45), base.rgb, contrast);
	base *= albedo_color;
	vec3 orm = texture(orm_tex, uv).rgb;
	float rough = orm.g * roughness;
	float wall = 1.0 - smoothstep(0.45, 0.75, abs(wnrm.y));
	vec2 along = abs(wnrm.x) > abs(wnrm.z) ? vec2(wpos.z, wpos.y) : vec2(wpos.x, wpos.y);
	vec2 wp = abs(wnrm.y) > 0.6 ? wpos.xz : along;
	vec2 mac = vec2(texture(macro_tex, wp * 0.09).r, texture(macro_tex, wp * 0.31 + 0.37).g);
	vec3 col = base.rgb * mix(1.0 - macro_amount, 1.0 + macro_amount * 0.4, mac.x) * mix(0.92, 1.05, mac.y);
	float h = wpos.y - base_y;
	// брызги и грязь у земли
	float band = splash_height * (0.5 + mac.y);
	float sp = (1.0 - smoothstep(0.0, band, h)) * wall * splash * (0.5 + 0.5 * mac.x);
	col = mix(col, col * grime_color * 2.3, sp);
	rough = mix(rough, rough * 0.8, sp * 0.5);
	// мох в сырых пятнах низа
	float ms = (1.0 - smoothstep(0.0, band * 0.7, h)) * moss * smoothstep(0.55, 0.8, mac.x) * wall;
	col = mix(col, moss_color, ms);
	// подтёки (из-под отливов, с плит) и сток с кровли
	float st = texture(streak_tex, vec2(wp.x * 0.33, -wp.y * 0.1)).r;
	float sk = st * streaks * wall * (0.35 + 0.8 * mac.x);
	float runoff = smoothstep(roof_height - 3.5, roof_height - 0.2, h) * roof_runoff * wall * (0.5 + 0.7 * st);
	col *= 1.0 - clamp(sk * 0.55 + runoff * 0.6, 0.0, 0.8);
	rough = mix(rough, 0.55, sk * 0.4);
	// стены мокнут пятнами и сверху вниз, низ — сильнее; горизонтальное — ровно
	float wk = rain_wet * mix(0.55 + 0.45 * (st * 0.7 + mac.x * 0.5), 1.0, 1.0 - wall);
	col *= 1.0 - 0.42 * wk;
	rough = mix(rough, 0.22, wk);
	ALBEDO = col;
	ROUGHNESS = clamp(mix(max(rough, use_metal ? 0.35 : rough_min), rough, rain_wet), 0.05, 1.0);
	METALLIC = use_metal ? orm.b : 0.0;
	AO = orm.r;
	NORMAL_MAP = texture(normal_tex, uv).rgb;
	NORMAL_MAP_DEPTH = normal_scale;
}
