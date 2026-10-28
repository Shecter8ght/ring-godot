shader_type spatial;
// Предварительная краска и плиточная сетка для оценки геометрии, без внешних текстур.
uniform int finish_mode = 0;
uniform vec4 green : source_color = vec4(0.349, 0.396, 0.298, 1.0);
uniform vec4 white : source_color = vec4(0.875, 0.882, 0.851, 1.0);
uniform vec4 tile_color : source_color = vec4(0.73, 0.78, 0.74, 1.0);
uniform vec4 floors = vec4(0.48, 4.42, 7.36, 10.30);
uniform float fifth_floor = 13.24;
uniform vec4 heights = vec4(3.7, 2.7, 2.7, 2.7);
uniform float tile_size = 0.2;
uniform vec4 main_bounds = vec4(0.0, -9.98, 43.41, 9.98);
uniform vec4 annex_bounds = vec4(33.9, -39.0, 43.41, -10.62);
varying vec3 world_at;
varying vec3 world_normal;

void vertex() {
    world_at = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    world_normal = normalize(mat3(MODEL_MATRIX) * NORMAL);
}

void fragment() {
    float base = floors.x;
    float height = heights.x;
    if (world_at.y >= floors.y - 0.001) { base = floors.y; height = heights.y; }
    if (world_at.y >= floors.z - 0.001) { base = floors.z; height = heights.z; }
    if (world_at.y >= floors.w - 0.001) { base = floors.w; height = heights.w; }
    if (world_at.y >= fifth_floor - 0.001) { base = fifth_floor; height = heights.w; }
    float upper = step(height * 0.6666667, world_at.y - base);
    ALBEDO = mix(green.rgb, white.rgb, upper);
    ROUGHNESS = mix(0.48, 0.88, upper);
    bool in_main = world_at.x >= main_bounds.x - 0.001 && world_at.x <= main_bounds.z + 0.001 && world_at.z >= main_bounds.y - 0.001 && world_at.z <= main_bounds.w + 0.001;
    bool in_annex = world_at.x >= annex_bounds.x - 0.001 && world_at.x <= annex_bounds.z + 0.001 && world_at.z >= annex_bounds.y - 0.001 && world_at.z <= annex_bounds.w + 0.001;
    if (!in_main && !in_annex) {
        ALBEDO = vec3(0.396, 0.418, 0.434);
        ROUGHNESS = 0.95;
    }
    if (finish_mode > 0) {
        vec3 n = abs(normalize(world_normal));
        vec2 uv = n.y > 0.6 ? world_at.xz : (n.x > n.z ? world_at.zy : world_at.xy);
        vec2 scaled = uv / tile_size;
        vec2 cell = floor(scaled);
        vec2 distance_edge = abs(fract(scaled) - 0.5);
        vec2 aa = max(fwidth(scaled), vec2(0.0001));
        vec2 lines = smoothstep(vec2(0.49) - aa, vec2(0.49) + aa, distance_edge);
        float grout = max(lines.x, lines.y);
        float variation = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);
        vec3 tile = tile_color.rgb * (0.96 + variation * 0.06);
        ALBEDO = mix(tile, vec3(0.29, 0.32, 0.29), grout);
        ROUGHNESS = mix(0.3, 0.9, grout);
    }
}
