// Фотоскан штукатурки (Poly Haven painted_plaster_wall, CC0) — под краской и под побелкой.
#ifndef DORM_V3_SCAN
#define DORM_V3_SCAN
uniform sampler2D plaster_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaster_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaster_rough : filter_linear_mipmap, repeat_enable;
#endif
