shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, world_vertex_coords;
// Густой ярус травы (GrassBlades → DistrictGrass): травинки-ленты без прозрачности. Цвет — от тёмного
// корня к зелени и сухой соломенной верхушке (сухость — пятнами по полю и у каждой травинки своя),
// нормали скруглены поперёк ленты и наклонены к небу — поле освещено как пушистый объём, а не
// плоские полосы. Против низкого солнца травинки просвечивают. Дальше fade_start..fade_end травинки
// уходят в землю (не «выскакивают» у края покрова). Ветер и примятие — grass_wind.gdshaderinc.

#include "res://src/world/grass_wind.gdshaderinc"

global uniform float rain_wet;

uniform vec3 root_color : source_color = vec3(0.16, 0.17, 0.08);
uniform vec3 green_color : source_color = vec3(0.3, 0.41, 0.14);
uniform vec3 dry_color : source_color = vec3(0.6, 0.53, 0.31);
uniform vec3 tip_color : source_color = vec3(0.68, 0.62, 0.41);
uniform vec3 translucency : source_color = vec3(0.3, 0.3, 0.1);
uniform float dryness = 0.45;
uniform float fade_start = 18.0;
uniform float fade_end = 22.0;
// скругление поперёк ленты и наклон нормали к небу
uniform float round_k = 0.75;
uniform float sky_k = 0.45;

varying float v_f;
varying vec3 v_col;
varying float v_ao;
varying float v_flat;

void vertex() {
	vec3 root = (MODEL_MATRIX * vec4(UV2.x, 0.0, UV2.y, 1.0)).xyz;
	vec3 cam = INV_VIEW_MATRIX[3].xyz;
	float d = distance(root.xz, cam.xz);
	float shrink = 1.0 - smoothstep(fade_start, fade_end, d);
	float sy = length(MODEL_MATRIX[1].xyz);
	float h = COLOR.g * sy * shrink;
	float f = UV.y;
	VERTEX = root + (VERTEX - root) * shrink;
	float flat_k;
	vec2 bend = grass_total_bend(root, h, COLOR.b, TIME, flat_k);
	VERTEX += grass_bend_offset(bend, h, f);
	// примятая — легла почти плашмя
	VERTEX.y = root.y + (VERTEX.y - root.y) * grass_squash(flat_k);
	// скруглённая лента, обращённая к небу; примятая — смотрит вверх
	vec3 n = normalize(NORMAL + TANGENT * (UV.x * 2.0 - 1.0) * round_k);
	NORMAL = normalize(mix(n, vec3(0.0, 1.0, 0.0), clamp(sky_k + flat_k * 0.4, 0.0, 1.0)));
	// сухость: пятнами по полю (шум) + своя у куртины (цвет экземпляра) + своя у травинки
	float patch_dry = texture(wind_noise, root.xz * 0.013 + vec2(0.37, 0.11)).g;
	float dry = clamp(dryness + (patch_dry - 0.5) * 1.1 + (INSTANCE_CUSTOM.g - 0.5) * 0.5 + (COLOR.a - 0.5) * 0.6, 0.0, 1.0);
	vec3 body = mix(green_color, dry_color, dry);
	vec3 tip = mix(body, tip_color, 0.35 + 0.65 * dry);
	v_col = mix(body, tip, smoothstep(0.35, 1.0, f)) * (0.82 + 0.36 * COLOR.r) * INSTANCE_CUSTOM.r;
	v_f = f;
	v_ao = mix(0.32, 1.0, smoothstep(0.0, 0.7, f));
	v_flat = flat_k;
}

void fragment() {
	vec3 c = mix(root_color, v_col, smoothstep(0.0, 0.4, v_f));
	// примятая трава темнее (видна изнанка и тень соседних травинок) и чуть блестит, лёжа
	ALBEDO = c * (1.0 - 0.22 * rain_wet) * mix(1.0, 0.72, v_flat);
	AO = mix(v_ao, v_ao * 0.7, v_flat);
	AO_LIGHT_AFFECT = 0.35;
	ROUGHNESS = mix(mix(0.68, 0.5, v_flat), 0.32, rain_wet);
	SPECULAR = mix(0.28, 0.5, rain_wet);
	BACKLIGHT = translucency * (0.25 + 0.75 * v_f);
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
