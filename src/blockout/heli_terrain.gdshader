shader_type spatial;
// Земля серого стенда «Вертолёт» (heli_terrain.gd): те же слои зоны 1, что у district_terrain, но на крутых склонах
// камень кладётся с трёх сторон — на отвесных стенах ущелья в 250 м текстура по горизонтали тянулась полосами.
// Без карт нормалей и «травы издали»: это проба геометрии и производительности, не готовая земля.

uniform sampler2DArray albedo_array : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray normal_array : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2DArray arm_array : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D splat : filter_linear, repeat_disable;
uniform sampler2D noise : filter_linear_mipmap, repeat_enable;
uniform vec2 splat_origin = vec2(0.0);
uniform vec2 splat_size = vec2(1.0);
uniform float layer_tile[6];
uniform vec3 grass_tint : source_color = vec3(0.5, 0.56, 0.38);
uniform vec3 rock_tint : source_color = vec3(0.68, 0.66, 0.62);
// камень скал — крупнее, чем галька под ногами: стена видна целиком с сотен метров
uniform float cliff_tile = 16.0;
uniform float rock_slope_start = 0.8;
uniform float rock_slope_end = 0.58;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 planar(int layer, vec2 uv) {
	return texture(albedo_array, vec3(uv / layer_tile[layer], float(layer))).rgb;
}

vec3 cliff(vec3 p, vec3 n) {
	vec3 w = pow(abs(n), vec3(6.0));
	w /= (w.x + w.y + w.z);
	vec3 x = texture(albedo_array, vec3(p.zy / cliff_tile, 4.0)).rgb;
	vec3 y = texture(albedo_array, vec3(p.xz / cliff_tile, 4.0)).rgb;
	vec3 z = texture(albedo_array, vec3(p.xy / cliff_tile, 4.0)).rgb;
	return x * w.x + y * w.y + z * w.z;
}

void fragment() {
	vec4 m = texture(splat, (wpos.xz - splat_origin) / splat_size);
	float up = clamp(wnrm.y, 0.0, 1.0);
	float steep = 1.0 - smoothstep(rock_slope_end, rock_slope_start, up);
	float macro = texture(noise, wpos.xz / 700.0).r;
	float spots = texture(noise, wpos.xz / 90.0).g;
	vec3 col = planar(0, wpos.xz) * grass_tint;
	col = mix(col, planar(1, wpos.xz) * grass_tint, smoothstep(0.45, 0.75, macro) * 0.8);
	col = mix(col, planar(2, wpos.xz), clamp(m.a, 0.0, 1.0));
	col = mix(col, planar(3, wpos.xz), clamp(m.r, 0.0, 1.0));
	col = mix(col, planar(5, wpos.xz), clamp(m.b, 0.0, 1.0));
	float rock = max(m.g, steep);
	if (rock > 0.01) {
		col = mix(col, cliff(wpos, wnrm) * rock_tint, rock);
	}
	col *= mix(0.86, 1.08, spots);
	ALBEDO = col;
	ROUGHNESS = 0.92;
	SPECULAR = 0.3;
}
