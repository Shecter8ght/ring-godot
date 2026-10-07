shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_disabled, shadows_disabled;

// Готовая нарисованная маска; движение хранится в анимации меша.
uniform sampler2D density_texture : source_color, filter_linear_mipmap;
uniform vec4 tint : source_color = vec4(0.68, 0.65, 0.58, 1.0);
uniform float opacity : hint_range(0.0, 1.0) = 0.4;

void fragment() {
	ALBEDO = tint.rgb;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	ALPHA = texture(density_texture, UV).a * opacity;
}
