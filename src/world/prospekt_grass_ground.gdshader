shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;
// Земля газона «Проспекта»: фотоскан с двумя выборками против повтора, крупные пятна тона
// и второй грунт в естественных проплешинах. Только для тестового газона и его стенда.

global uniform float rain_wet;

uniform bool use_maps = true;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D height_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform bool has_height = false;
uniform bool use_soil = false;
uniform sampler2D soil_albedo_tex : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D soil_normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D soil_arm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float tile_m = 2.0;
uniform float soil_tile_m = 2.5;
uniform float soil_amount : hint_range(0.0, 1.0) = 0.0;
uniform vec3 tint : source_color = vec3(1.0);
uniform float saturation : hint_range(0.0, 1.5) = 0.8;
uniform float macro_var : hint_range(0.0, 0.5) = 0.12;
uniform float normal_strength : hint_range(0.0, 2.0) = 0.85;
// Глубина рельефа по карте высот, м; с дальностью параллакс плавно выключается.
uniform float parallax_scale : hint_range(0.0, 0.1) = 0.035;
uniform float parallax_start = 3.0;
uniform float parallax_end = 8.0;
uniform vec3 base_color : source_color = vec3(0.19, 0.22, 0.13);

varying vec3 wpos;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x),
		mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0)), f.x), f.y);
}

float fbm(vec2 p) {
	mat2 rot = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	float value = 0.0;
	float amplitude = 0.55;
	for (int i = 0; i < 4; i++) {
		value += amplitude * vnoise(p);
		p = rot * p * 2.03 + 11.7;
		amplitude *= 0.47;
	}
	return value / 0.93;
}

vec2 relief_offset(vec2 uv, vec3 view_dir, float depth_scale) {
	float steps = mix(5.0, 16.0, 1.0 - clamp(view_dir.y, 0.0, 1.0));
	float step_depth = 1.0 / steps;
	vec2 delta = view_dir.xz / max(view_dir.y, 0.35) * depth_scale / tile_m / steps;
	vec2 current_uv = uv;
	float layer = 0.0;
	float depth = 1.0 - textureLod(height_tex, current_uv, 0.0).r;
	for (int i = 0; i < 16; i++) {
		if (float(i) >= steps || layer >= depth) {
			break;
		}
		current_uv -= delta;
		layer += step_depth;
		depth = 1.0 - textureLod(height_tex, current_uv, 0.0).r;
	}
	return current_uv - uv;
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 xz = wpos.xz;
	vec2 uv = xz / tile_m;
	mat2 rot = mat2(vec2(0.62, 0.78), vec2(-0.78, 0.62));
	float dist = distance(wpos, INV_VIEW_MATRIX[3].xyz);
	vec2 relief = vec2(0.0);
	if (use_maps && has_height && parallax_scale > 0.0 && dist < parallax_end) {
		vec3 view_dir = normalize(INV_VIEW_MATRIX[3].xyz - wpos);
		float fade = 1.0 - smoothstep(parallax_start, parallax_end, dist);
		relief = relief_offset(uv, view_dir, parallax_scale * fade);
		uv += relief;
	}
	vec2 sample_xz = xz + relief * tile_m;
	vec2 uv2 = rot * uv * 0.73 + vec2(0.37, 0.71);
	float mixk = smoothstep(0.3, 0.7, fbm(xz * 0.17 + 5.0));
	float far_k = smoothstep(12.0, 45.0, dist);
	vec3 alb = base_color;
	vec3 arm = vec3(0.85, 0.92, 0.0);
	vec2 nxy = vec2(0.0);
	float height_value = 0.5;
	if (use_maps) {
		alb = mix(texture(albedo_tex, uv).rgb, texture(albedo_tex, uv2).rgb, mixk);
		arm = mix(texture(arm_tex, uv).rgb, texture(arm_tex, uv2).rgb, mixk);
		vec2 n1 = texture(normal_tex, uv).rg * 2.0 - 1.0;
		vec2 n2 = texture(normal_tex, uv2).rg * 2.0 - 1.0;
		n1.y = -n1.y;
		n2.y = -n2.y;
		nxy = mix(n1, transpose(rot) * n2, mixk);
		if (has_height) {
			height_value = mix(texture(height_tex, uv).r, texture(height_tex, uv2).r, mixk);
		}
	} else {
		float grain = vnoise(xz * 27.0) * 0.6 + vnoise(xz * 61.0) * 0.4;
		alb *= 0.8 + grain * 0.4;
		nxy = vec2(vnoise(xz * 23.0 + 0.5) - vnoise(xz * 23.0 - 0.5),
			vnoise(xz * 23.0 + 3.5) - vnoise(xz * 23.0 + 2.5)) * 0.3;
	}
	float lum = dot(alb, vec3(0.3, 0.59, 0.11));
	alb = mix(vec3(lum), alb, saturation) * tint;
	if (use_soil && use_maps && soil_amount > 0.001) {
		vec2 suv = sample_xz / soil_tile_m;
		vec2 suv2 = rot * suv * 0.67 + vec2(0.13, 0.83);
		vec3 soil_alb = mix(texture(soil_albedo_tex, suv).rgb, texture(soil_albedo_tex, suv2).rgb, mixk);
		vec3 soil_arm = mix(texture(soil_arm_tex, suv).rgb, texture(soil_arm_tex, suv2).rgb, mixk);
		vec2 sn1 = texture(soil_normal_tex, suv).rg * 2.0 - 1.0;
		vec2 sn2 = texture(soil_normal_tex, suv2).rg * 2.0 - 1.0;
		sn1.y = -sn1.y;
		sn2.y = -sn2.y;
		vec2 soil_n = mix(sn1, transpose(rot) * sn2, mixk);
		float patch = fbm(xz * 0.1 + 29.0) * 0.72 + fbm(xz * 0.43 + 7.0) * 0.28;
		float threshold = mix(1.1, 0.43, soil_amount);
		float bare = smoothstep(threshold, threshold + 0.11, patch);
		bare *= mix(0.55, 1.0, 1.0 - smoothstep(0.35, 0.7, height_value));
		soil_alb *= tint * 0.82;
		alb = mix(alb, soil_alb, bare);
		arm = mix(arm, soil_arm, bare);
		nxy = mix(nxy, soil_n, bare);
	}
	float macro = fbm(xz * 0.065 + 3.1);
	alb *= 1.0 + (macro - 0.5) * 2.0 * macro_var;
	alb *= 1.0 - 0.2 * rain_wet;
	ALBEDO = alb;
	ROUGHNESS = mix(clamp(arm.g, 0.35, 1.0), 0.42, rain_wet * 0.55);
	METALLIC = 0.0;
	SPECULAR = mix(0.25, 0.4, rain_wet);
	AO = arm.r;
	AO_LIGHT_AFFECT = 0.25;
	vec2 slope = nxy * normal_strength * mix(1.0, 0.3, far_k);
	vec3 nw = normalize(vec3(slope.x, 1.0, slope.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
