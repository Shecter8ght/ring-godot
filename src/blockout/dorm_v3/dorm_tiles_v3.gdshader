shader_type spatial;
// Плитка общежития v03: mode 0 — стена умывальни / душевой (белая глазурь до 2/3 высоты этажа, выше побелка v03),
// 1 — пол мокрых помещений (тёмная метлахская, окрашена насквозь).

#include "res://src/blockout/dorm_v3/common.gdshaderinc"
#include "res://src/blockout/dorm_v3/floors.gdshaderinc"
#include "res://src/blockout/dorm_v3/wash.gdshaderinc"
#include "res://src/blockout/dorm_v3/tiles.gdshaderinc"

uniform int mode = 0;
uniform vec3 glaze_color : source_color = vec3(0.812, 0.804, 0.761);
uniform vec3 body_color : source_color = vec3(0.733, 0.655, 0.549);
uniform vec3 floor_glaze_color : source_color = vec3(0.49, 0.373, 0.298);
uniform vec3 floor_body_color : source_color = vec3(0.416, 0.31, 0.247);

varying vec3 world_at;
varying vec3 world_normal;

void vertex() {
	world_at = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(mat3(MODEL_MATRIX) * NORMAL);
}

void fragment() {
	vec3 p = world_at;
	vec3 inc = normalize(CAMERA_POSITION_WORLD - p);
	vec3 t, b, n;
	surface_frame(world_normal, false, t, b, n);
	float base, height;
	floor_at(p.y, base, height);
	float rel = p.y - base;
	vec4 nz = noise_at(p);
	vec3 color;
	float rough;
	vec3 nrm;
	if (mode == 1) {
		tile_layer(p, inc, t, b, n, floor_glaze_color, floor_body_color, 1.0, 0.0, color, rough, nrm);
	} else if (rel > height * paint_fraction) {
		vec2 w = wear_attr(rel, nz, height * paint_fraction);
		float wash = clamp(0.2 + w.x * 0.35, 0.0, 1.0);
		wash_layer(p, inc, surface_uv(p, t, b, 0.5), wash, 0.0, t, b, n, false, 1.0, 1.6, color, rough, nrm);
	} else {
		float low = 1.0 - smoothstep(0.05, 0.6, rel);
		tile_layer(p, inc, t, b, n, glaze_color, body_color, 0.0, low, color, rough, nrm);
	}
	ALBEDO = color;
	ROUGHNESS = clamp(rough, 0.02, 1.0);
	NORMAL = normalize((VIEW_MATRIX * vec4(nrm, 0.0)).xyz);
}
