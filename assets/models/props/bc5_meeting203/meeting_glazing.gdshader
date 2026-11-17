shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, specular_schlick_ggx;

#include "res://src/world/window_transmission.gdshaderinc"

uniform vec3 glass_tint : source_color = vec3(0.88, 0.95, 0.97);
uniform float glass_opacity : hint_range(0.0, 1.0) = 0.08;
uniform float glass_fresnel : hint_range(0.0, 1.0) = 0.68;
uniform float glass_roughness : hint_range(0.0, 1.0) = 0.085;

varying vec2 pane_uv;
varying float thin_edge;

void vertex() {
	// Масштаб каждой секции задан MultiMesh. Боковые грани куба образуют торцы стекла.
	pane_uv = VERTEX.xy + vec2(0.5);
	thin_edge = 1.0 - abs(NORMAL.z);
}

void fragment() {
	vec2 edge_distance = min(pane_uv, 1.0 - pane_uv);
	float border = 1.0 - smoothstep(0.0008, 0.004, min(edge_distance.x, edge_distance.y));
	float edge = max(thin_edge, border * 0.35);
	float facing = clamp(abs(dot(normalize(NORMAL), VIEW)), 0.0, 1.0);
	float grazing = pow(1.0 - facing, 5.0);
	float reflection = glass_opacity + glass_fresnel * grazing;
	vec2 surface = (INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xy;
	float dust = window_dust(surface);
	vec3 behind = transmitted_window(SCREEN_UV, NORMAL, surface, transmission_blur, dust);
	vec3 pane = mix(vec3(0.022, 0.029, 0.032), vec3(0.17, 0.16, 0.145), dust);
	ALBEDO = mix(pane, vec3(0.10, 0.17, 0.19), edge);
	ROUGHNESS = mix(glass_roughness + 0.31 * dust, 0.041, edge);
	SPECULAR = mix(0.76, 0.94, edge);
	EMISSION = behind * mix(vec3(1.0), glass_tint, 0.16) * (1.0 - 0.54 * reflection - 0.18 * edge - 0.18 * dust);
	ALPHA = clamp(0.85 + 0.13 * grazing + 0.11 * edge + 0.14 * dust, 0.0, 1.0);
}
