shader_type spatial;
// Искра попадания: раскалённая полоса ярче сцены (цвет остывания — COLOR из impact_particles).
// Свечение днём выключено (Balance.DAY_GLOW) — яркость даёт сам цвет выше единицы.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

#include "res://src/combat/impact_streak.gdshaderinc"

uniform float energy = 8.0;

void fragment() {
	float shape = streak_shape(UV);
	// сердцевина белее краёв
	float core = smoothstep(0.55, 1.0, 1.0 - abs(UV.x * 2.0 - 1.0));
	vec3 hot = mix(COLOR.rgb, vec3(1.0, 0.95, 0.85), core * 0.6);
	ALBEDO = hot * energy * COLOR.a * shape * v_thin;
}
