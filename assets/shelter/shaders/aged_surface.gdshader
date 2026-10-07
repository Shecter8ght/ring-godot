shader_type spatial;
// Старая поверхность котельной (стены, пол, потолок): обычный PBR из текстур плюс старение в мировых
// координатах — крупные пятна ломают повтор плитки, низ стен грязный и сырой, сверху вниз — подтёки,
// к потолку копоть (тёплый воздух котельной). Ориентация по нормали: стена, пол или потолок.
// Материалы собирает tools/author_shelter_scene.gd; маски — tools/shelter_grime_textures.py.

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_albedo = true;
uniform bool has_normal = false;
uniform bool has_orm = false;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float normal_scale = 0.35;
uniform float specular = 0.35;
uniform float roughness = 1.0;

// R — крупные пятна (метры), G — мелкие разводы
uniform sampler2D macro_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float macro_scale = 0.22;
uniform float macro_amount = 0.2;
// низ стен: высота пола, высота полосы, сила, цвет грязи
uniform float floor_y = 0.0;
uniform float base_height = 0.5;
uniform float base_grime = 0.45;
uniform vec3 grime_color : source_color = vec3(0.2, 0.17, 0.13);
// подтёки сверху вниз
uniform sampler2D streak_tex : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform float streaks = 0.3;
// копоть: от какой высоты, на сколько метров нарастает, сила; потолок — soot_ceiling
uniform float soot_from = 2.4;
uniform float soot_range = 4.5;
uniform float soot = 0.3;
uniform float soot_ceiling = 0.25;
uniform vec3 soot_color : source_color = vec3(0.07, 0.065, 0.06);
// пол: вытертое и засаленное — пятна чуть глаже и темнее
uniform float floor_wear = 0.25;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize(mat3(MODEL_MATRIX) * NORMAL);
}

void fragment() {
	vec4 base = has_albedo ? texture(albedo_tex, UV) : vec4(1.0);
	base *= albedo_color;
	vec3 orm = has_orm ? texture(orm_tex, UV).rgb : vec3(1.0, 1.0, 0.0);
	float rough = orm.g * roughness;
	float up = wnrm.y;
	float wall = 1.0 - smoothstep(0.45, 0.75, abs(up));
	float floor_k = smoothstep(0.5, 0.8, up);
	float ceil_k = smoothstep(0.5, 0.8, -up);
	// координаты вдоль поверхности, м: у стены — по горизонтали и высоте, у пола/потолка — план
	vec2 along = abs(wnrm.x) > abs(wnrm.z) ? vec2(wpos.z, wpos.y) : vec2(wpos.x, wpos.y);
	vec2 wp = abs(up) > 0.6 ? wpos.xz : along;
	vec2 mac = vec2(texture(macro_tex, wp * macro_scale).r, texture(macro_tex, wp * macro_scale * 3.3 + 0.37).g);
	vec3 col = base.rgb * mix(1.0 - macro_amount, 1.0 + macro_amount * 0.4, mac.x) * mix(0.93, 1.04, mac.y);
	float h = wpos.y - floor_y;
	// низ стены: грязь и сырость с рваным краем
	float band = base_height * (0.55 + 0.9 * mac.y);
	float bg = (1.0 - smoothstep(0.0, band, h)) * wall * base_grime * (0.6 + 0.4 * mac.x);
	col = mix(col, col * grime_color * 2.4, bg);
	rough = mix(rough, rough * 0.78, bg * 0.6);
	// подтёки
	float st = texture(streak_tex, vec2(wp.x * 0.33, -wp.y * 0.12)).r;
	float sk = st * streaks * wall * smoothstep(0.6, 2.2, h) * (0.4 + 0.8 * mac.x);
	col *= 1.0 - sk * 0.7;
	rough = mix(rough, 0.5, sk * 0.5);
	// копоть
	float so = (smoothstep(soot_from, soot_from + soot_range, h) * soot * wall + ceil_k * soot_ceiling) * (0.55 + 0.6 * mac.x);
	col = mix(col, soot_color, clamp(so, 0.0, 0.9));
	// пол: вытертые и засаленные места
	float fw = floor_k * floor_wear * smoothstep(0.45, 0.8, mac.y);
	col *= 1.0 - fw * 0.25;
	rough = mix(rough, rough * 0.6, fw);
	ALBEDO = col;
	ROUGHNESS = clamp(rough, 0.04, 1.0);
	METALLIC = has_orm ? orm.b : 0.0;
	AO = orm.r;
	SPECULAR = specular;
	if (has_normal) {
		NORMAL_MAP = texture(normal_tex, UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
}
