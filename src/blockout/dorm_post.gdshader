shader_type canvas_item;
// Только пробный стенд: слабое зерно и виньетка, под интерфейсом.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float grain = 0.005;
uniform float vignette = 0.08;
void fragment() {
    vec3 c = texture(screen_tex, SCREEN_UV).rgb;
    vec2 d = SCREEN_UV - 0.5;
    float edge = smoothstep(0.2,0.7,length(d));
    c *= 1.0 - edge*vignette;
    float noise = fract(sin(dot(floor(SCREEN_UV/SCREEN_PIXEL_SIZE)+floor(TIME*12.0),vec2(12.9898,78.233)))*43758.5453)-0.5;
    COLOR = vec4(max(c+noise*grain,vec3(0.0)),1.0);
}
