shader_type spatial;
// Свечение самого фонаря (LampGlow): яркая точка и ореол, всегда лицом к камере; ярче, когда луч
// смотрит на камеру, сзади не виден (свой фонарь в руках). Вдали — крупнее (иначе точка тоньше пикселя, а
// фонарь ночью виден за сотни метров), в оптике — как есть.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform vec3 color : source_color = vec3(1.0, 0.95, 0.86);
uniform float energy = 5.0;
uniform float grow_from = 15.0;
uniform float grow_max = 5.0;

varying float v_face;

void vertex() {
	float dist = distance(CAMERA_POSITION_WORLD, NODE_POSITION_WORLD);
	float s = clamp(dist / grow_from, 1.0, grow_max);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * s, INV_VIEW_MATRIX[1] * s, INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	// луч — вдоль −Z узла света
	vec3 fwd = normalize(-MODEL_MATRIX[2].xyz);
	v_face = dot(fwd, normalize(CAMERA_POSITION_WORLD - NODE_POSITION_WORLD));
}

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r2 = dot(p, p);
	float face = smoothstep(-0.3, 0.95, v_face);
	float core = exp(-r2 * 60.0);
	float halo = exp(-r2 * 7.0) * 0.3 * face;
	ALBEDO = color * energy;
	ALPHA = clamp((core + halo) * face, 0.0, 1.0);
}
