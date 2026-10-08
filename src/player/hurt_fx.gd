class_name HurtFx
extends CanvasLayer
## Словил пулю (осколок, удар): по краям кадра — тёмно-красная виньетка, картинка на миг блёкнет и
## чуть плывёт; сила — по урону, гаснет за Balance.HURT_FX.fade_sec. Без направления: откуда
## стреляли — слышно (звук выстрела), не видно. Создаёт CameraRig, вызывает Player (своё попадание).

var _rect: ColorRect
var _mat: ShaderMaterial
var _k: float = 0.0

const SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float amount = 0.0;
void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 c = uv - 0.5;
	c.x *= 1.6;
	// края темнеют и краснеют, середина почти чистая
	float v = smoothstep(0.22, 0.9, length(c));
	vec3 col = textureLod(screen_tex, uv, amount * 1.6).rgb;
	float g = dot(col, vec3(0.3, 0.59, 0.11));
	col = mix(col, vec3(g), amount * 0.45);
	col *= 1.0 - amount * 0.2;
	col = mix(col, vec3(0.32, 0.015, 0.01), clamp(v * amount * 1.1, 0.0, 0.9));
	COLOR = vec4(col, 1.0);
}
"""


func _ready() -> void:
	layer = 7
	_rect = ColorRect.new()
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = SHADER
	_mat = ShaderMaterial.new()
	_mat.shader = sh
	_rect.material = _mat
	_rect.visible = false
	add_child(_rect)


## Попадание на amount урона.
func hit(amount: float) -> void:
	var f: Dictionary = Balance.HURT_FX
	_k = clampf(maxf(_k, float(f.min)) + amount * float(f.per_dmg), 0.0, float(f.max))


func _process(delta: float) -> void:
	if _k <= 0.0 and not _rect.visible:
		return
	_k = maxf(0.0, _k - delta / float(Balance.HURT_FX.fade_sec))
	_rect.visible = _k > 0.001
	_mat.set_shader_parameter("amount", _k * _k * (3.0 - 2.0 * _k))
