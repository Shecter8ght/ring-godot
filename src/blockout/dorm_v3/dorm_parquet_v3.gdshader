shader_type spatial;
// Пол общежития v03 — паркет «ёлочкой» (parquet.gdshaderinc). Грани коробки пола, кроме верхней, — тот же
// материал без ям (их не видно).

#include "res://src/blockout/dorm_v3/common.gdshaderinc"
#include "res://src/blockout/dorm_v3/parquet.gdshaderinc"

varying vec3 world_at;
varying vec3 world_normal;

void vertex() {
	// Бок плиты пола над пустотой лестницы лежит в плоскости стены этажа ниже (она заходит в толщину плиты) —
	// утапливаем боковые грани на 4 мм: где перед ними стена, видна стена, без мерцания.
	if (abs(NORMAL.y) < 0.5) {
		VERTEX -= NORMAL * 0.004;
	}
	world_at = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(mat3(MODEL_MATRIX) * NORMAL);
}

void fragment() {
	vec3 inc = normalize(CAMERA_POSITION_WORLD - world_at);
	vec3 color;
	float rough;
	vec3 nrm;
	if (world_normal.y > 0.5) {
		parquet_layer(world_at, inc, noise_at(world_at).rgb, color, rough, nrm);
	} else {
		color = rgb(60.0, 45.0, 32.0);
		rough = 0.8;
		nrm = world_normal;
	}
	ALBEDO = color;
	ROUGHNESS = clamp(rough, 0.02, 1.0);
	NORMAL = normalize((VIEW_MATRIX * vec4(nrm, 0.0)).xyz);
}
