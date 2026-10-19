shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_burley, specular_schlick_ggx;
// Материал оружия с жировыми следами рук. Вид один (решение владельца 2026-10-19): модель при любой прочности
// показывает карты, принятые в Blender; износ по виду (маски _wear, ручные карты 60/20) отменён и удалён.
// Основа — те же карты и правила, что у StandardMaterial3D модели (цвет, нормали, шероховатость, металл,
// AO на непрямой свет); WeaponCondition.wear_material переносит их сюда из материала GLB. Сверху — жировые
// следы, свечение по карте и намокание в дождь.

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

// насколько оружие намокает в дождь (глобальный rain_wet от RainFx)
uniform float wet_k = 0.7;

global uniform float rain_wet;

void vertex() {
	UV = UV * uv1_scale.xy + uv1_offset.xy;
}

void fragment() {
	vec3 col = (texture(albedo_tex, UV) * albedo_color).rgb;
	float rough = dot(texture(roughness_tex, UV), roughness_channel) * roughness;
	float metal = dot(texture(metallic_tex, UV), metallic_channel) * metallic;
	float ao = dot(texture(ao_tex, UV), ao_channel);
	float film = texture(coat_tex, UV).r * coat_weight;
	// пористое (фенопласт, пластик) темнеет от воды, металл — только блестит
	float porous = 1.0 - metal;
	// жировой след сглаживает поверхность (не грубее film_roughness), карта нормалей остаётся
	rough = mix(rough, min(rough, film_roughness), clamp(film, 0.0, 1.0));
	// дождь: вода сглаживает отражение, пористое темнеет
	float wet = clamp(rain_wet * wet_k, 0.0, 1.0);
	col *= 1.0 - 0.3 * wet * porous;
	rough = mix(rough, min(rough, 0.16), wet * 0.8);
	ALBEDO = col;
	ROUGHNESS = clamp(rough, 0.04, 1.0);
	METALLIC = clamp(metal, 0.0, 1.0);
	SPECULAR = specular;
	NORMAL_MAP = texture(normal_tex, UV).rgb;
	NORMAL_MAP_DEPTH = normal_scale;
	AO = ao;
	AO_LIGHT_AFFECT = ao_light_affect;
	EMISSION = texture(emission_tex, UV).rgb * emission_color * emission_energy;
}
