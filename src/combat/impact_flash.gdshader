shader_type spatial;
// Вспышка в точке удара (металл): круглое пятно к камере на пару кадров, ярче сцены.
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.78, 0.45, 1.0);
uniform float energy = 6.0;
instance uniform float fade = 1.0;

void vertex() {
	mat4 m = mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	m = m * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0), vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0),
		vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0), vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_MATRIX = VIEW_MATRIX * m;
}

void fragment() {
	float r = length(UV * 2.0 - 1.0);
	// яркое ядро и мягкий ореол; лучи — неровность по углу
	float ang = atan(UV.y - 0.5, UV.x - 0.5);
	float rays = 0.75 + 0.25 * sin(ang * 7.0) * sin(ang * 3.0 + 1.3);
	float glow = exp(-r * r * 9.0) + 0.35 * exp(-r * 3.2 / rays);
	ALBEDO = mix(color.rgb, vec3(1.0, 0.97, 0.9), exp(-r * r * 30.0)) * energy * glow * fade * (1.0 - smoothstep(0.85, 1.0, r));
}
