shader_type spatial;
// Стены, откосы и потолки общежития v03: mode 0 — стена (до 2/3 высоты этажа облупленная масляная краска, выше
// побелка по штукатурке, отвал до кирпича, полоса-«филёнка», грязь у пола), 1 — откос (побелка), 2 — потолок
// (побелка по бетону плиты, протечки сильнее). Снаружи корпуса — серый фасад, как в черновике.

#include "res://src/blockout/dorm_v3/common.gdshaderinc"
#include "res://src/blockout/dorm_v3/floors.gdshaderinc"
#include "res://src/blockout/dorm_v3/paint.gdshaderinc"
#include "res://src/blockout/dorm_v3/wash.gdshaderinc"

uniform int mode = 0;
uniform float paint_wear_base = 0.08;
uniform float wash_wear_base = 0.05;
uniform float loss_wear_base = 0.0;

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
	vec2 uv = surface_uv(p, t, b, 0.5);
	vec4 nz = noise_at(p);
	float var_k = nz.r * 1.4 - 0.55;
	float base, height;
	floor_at(p.y, base, height);
	float rel = p.y - base;
	float line_h = height * paint_fraction;
	vec2 w = wear_attr(rel, nz, line_h);
	vec3 color;
	float rough;
	vec3 nrm;
	if (!inside_building(p) && mode == 0) {
		color = vec3(0.396, 0.418, 0.434);
		rough = 0.95;
		nrm = world_normal;
	} else if (mode == 2) {
		float wash = clamp(0.12 + var_k * 0.3, 0.0, 1.0);
		float loss = clamp(loss_wear_base + var_k * 0.06, 0.0, 1.0);
		wash_layer(p, inc, uv, wash, loss, t, b, n, true, 1.5, 1.0, color, rough, nrm);
	} else {
		float zz = rel + (nz.g - 0.5) * 0.12;
		bool lower = mode == 0 && zz < line_h;
		if (lower) {
			float paint_wear = clamp(paint_wear_base + w.x * 0.45 + var_k * 0.4, 0.0, 1.0);
			paint_layer(uv, paint_wear, t, b, n, color, rough, nrm);
		} else {
			float wash = clamp(wash_wear_base + w.x * 0.35 + var_k * 0.25, 0.0, 1.0);
			float loss = clamp(loss_wear_base + w.y * 0.5 + var_k * 0.1, 0.0, 1.0);
			wash_layer(p, inc, uv, wash, loss, t, b, n, false, 1.0, 1.0, color, rough, nrm);
		}
		if (mode == 0) {
			// полоса-«филёнка» по границе краски и грязь у пола
			float line = 1.0 - smoothstep(0.006, 0.009, abs(zz - (line_h + 0.006)));
			color = mix(color, rgb(47.0, 58.0, 44.0), line);
			float dirt = (max(1.0 - rel / 0.35, 0.0) + max(1.0 - rel * 4.0, 0.0)) * smoothstep(0.35, 0.7, nz.b);
			color = mix(color, color * rgb(59.0, 52.0, 40.0), min(dirt * 0.8, 1.0));
		}
	}
	ALBEDO = color;
	ROUGHNESS = clamp(rough, 0.02, 1.0);
	NORMAL = normalize((VIEW_MATRIX * vec4(nrm, 0.0)).xyz);
}
