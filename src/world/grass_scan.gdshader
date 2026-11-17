shader_type spatial;
render_mode cull_disabled, diffuse_lambert_wrap, world_vertex_coords;
// Пучки-сканы травы и сорняков (Poly Haven) над густым ярусом: те же ветер и примятие, что у
// травинок (grass_wind.gdshaderinc); пучок гнётся от корня (начало координат экземпляра), верх —
// сильнее. Нормали наклонены к небу — пучок освещён как часть луга, а не чёрные стебли сбоку.

#include "res://src/world/grass_wind.gdshaderinc"

global uniform float rain_wet;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec3 tint : source_color = vec3(0.8, 0.76, 0.66);
uniform float alpha_cut = 0.4;
uniform bool dynamic_alpha = false;
uniform float far_alpha_cut = 0.04;
uniform float clip_distance = 24.0;
// высота пучка в осях модели (по рамке сетки) — доля высоты вершины для изгиба
uniform float mesh_height = 0.3;
uniform vec3 translucency : source_color = vec3(0.22, 0.2, 0.08);
uniform float fade_start = 28.0;
uniform float fade_end = 32.0;

varying float v_f;
varying float v_camera_distance;
varying vec3 v_var;
varying float v_flat;

void vertex() {
	vec3 root = MODEL_MATRIX[3].xyz;
	vec3 cam = INV_VIEW_MATRIX[3].xyz;
	v_camera_distance = distance(root, cam);
	float shrink = 1.0 - smoothstep(fade_start, fade_end, distance(root.xz, cam.xz));
	float sy = length(MODEL_MATRIX[1].xyz);
	float h = max(mesh_height * sy, 0.01);
	float f = clamp((VERTEX.y - root.y) / h, 0.0, 1.0);
	VERTEX = root + (VERTEX - root) * shrink;
	h *= shrink;
	float phase = fract(dot(root.xz, vec2(0.173, 0.291)));
	float flat_k;
	vec2 bend = grass_total_bend(root, h, phase, TIME, flat_k);
	VERTEX += grass_bend_offset(bend, h, f);
	VERTEX.y = root.y + (VERTEX.y - root.y) * grass_squash(flat_k);
	NORMAL = normalize(NORMAL * 0.25 + vec3(0.0, 1.0, 0.0));
	v_f = f;
	v_flat = flat_k;
	v_var = vec3(INSTANCE_CUSTOM.r) * mix(vec3(1.0), vec3(0.92, 0.8, 0.55), INSTANCE_CUSTOM.g);
}

void fragment() {
	vec4 a = texture(albedo_tex, UV);
	ALPHA = a.a;
	float cut = dynamic_alpha ? mix(alpha_cut, far_alpha_cut, clamp(v_camera_distance / clip_distance, 0.0, 1.0)) : alpha_cut;
	ALPHA_SCISSOR_THRESHOLD = cut;
	ALBEDO = a.rgb * tint * v_var * (1.0 - 0.2 * rain_wet) * mix(0.55, 1.0, smoothstep(0.0, 0.5, v_f)) * mix(1.0, 0.75, v_flat);
	ROUGHNESS = mix(1.0, 0.45, rain_wet);
	SPECULAR = mix(0.12, 0.45, rain_wet);
	BACKLIGHT = translucency * (0.3 + 0.7 * v_f);
	if (!FRONT_FACING) {
		NORMAL = -NORMAL;
	}
}
