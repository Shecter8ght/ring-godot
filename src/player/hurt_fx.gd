class_name HurtFx
extends CanvasLayer
## Словил пулю (осколок, удар): по краям кадра — тёмно-красная виньетка, картинка на миг блёкнет и
## чуть плывёт; сила — по урону, гаснет за Balance.HURT_FX.fade_sec. Красная дуга указывает сторону
## попадания относительно взгляда. Создаёт CameraRig, вызывает Player (своё попадание).

var _rect: ColorRect
var _mat: ShaderMaterial
var _k: float = 0.0
var _indicator: Control
var _directions: Array[Dictionary] = []
var camera_basis: Basis = Basis.IDENTITY

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
	# Дуга рисуется после экранного эффекта: остаётся читаемой при ранении и в ПНВ.
	_indicator = Control.new()
	_indicator.name = "DamageDirection"
	_indicator.set_anchors_preset(Control.PRESET_FULL_RECT)
	_indicator.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_indicator.draw.connect(_draw_directions)
	add_child(_indicator)


## Попадание на amount урона.
func hit(amount: float, from: Vector3 = Vector3.INF, origin: Vector3 = Vector3.INF) -> void:
	var f: Dictionary = Balance.HURT_FX
	_k = clampf(maxf(_k, float(f.min)) + amount * float(f.per_dmg), 0.0, float(f.max))
	if not from.is_finite() or not origin.is_finite():
		return
	var direction: Vector3 = from - origin
	direction.y = 0.0
	if direction.is_zero_approx():
		return
	direction = direction.normalized()
	var d: Dictionary = Balance.HURT_DIRECTION
	var strength: float = clampf(float(d.min_alpha) + amount * float(d.per_dmg_alpha), 0.0, 1.0)
	for entry: Dictionary in _directions:
		if direction.dot(entry.direction) >= cos(deg_to_rad(float(d.merge_deg))):
			entry.direction = direction
			entry.age = 0.0
			entry.strength = maxf(float(entry.strength), strength)
			return
	if _directions.size() >= int(d.max_hits):
		var oldest: int = 0
		for i: int in range(1, _directions.size()):
			if float(_directions[i].age) > float(_directions[oldest].age):
				oldest = i
		_directions.remove_at(oldest)
	_directions.append({"direction": direction, "age": 0.0, "strength": strength})


## Горизонтальное направление относительно камеры: её наклон вверх/вниз не меняет сторону.
func direction_on_screen(direction: Vector3) -> Vector2:
	var forward: Vector3 = -camera_basis.z
	forward.y = 0.0
	if forward.is_zero_approx():
		forward = Vector3.UP.cross(camera_basis.x)
	forward = forward.normalized()
	var right: Vector3 = forward.cross(Vector3.UP)
	return Vector2(direction.dot(right), -direction.dot(forward)).normalized()


func _draw_directions() -> void:
	var d: Dictionary = Balance.HURT_DIRECTION
	var center: Vector2 = _indicator.size * 0.5
	var short_side: float = minf(_indicator.size.x, _indicator.size.y)
	var radius: float = short_side * float(d.radius)
	var width: float = short_side * float(d.width)
	var half_arc: float = deg_to_rad(float(d.arc_deg)) * 0.5
	for entry: Dictionary in _directions:
		var fade: float = 1.0 - clampf((float(entry.age) - float(d.hold_sec)) / float(d.fade_sec), 0.0, 1.0)
		var alpha: float = float(entry.strength) * smoothstep(0.0, 1.0, fade)
		var angle: float = direction_on_screen(entry.direction).angle()
		var color: Color = d.color
		var outline: Color = d.outline_color
		var highlight: Color = d.highlight_color
		color.a = alpha
		outline.a = alpha
		highlight.a = alpha
		_indicator.draw_arc(center, radius, angle - half_arc, angle + half_arc, int(d.segments), outline, width + short_side * float(d.outline), true)
		_indicator.draw_arc(center, radius, angle - half_arc, angle + half_arc, int(d.segments), color, width, true)
		_indicator.draw_arc(center, radius - width * 0.5, angle - half_arc, angle + half_arc, int(d.segments), highlight, short_side * float(d.highlight), true)


func _process(delta: float) -> void:
	var d: Dictionary = Balance.HURT_DIRECTION
	for i: int in range(_directions.size() - 1, -1, -1):
		_directions[i].age = float(_directions[i].age) + delta
		if float(_directions[i].age) >= float(d.hold_sec) + float(d.fade_sec):
			_directions.remove_at(i)
	if not _directions.is_empty() or _indicator.visible:
		_indicator.visible = not _directions.is_empty()
		_indicator.queue_redraw()
	if _k <= 0.0 and not _rect.visible:
		return
	_k = maxf(0.0, _k - delta / float(Balance.HURT_FX.fade_sec))
	_rect.visible = _k > 0.001
	_mat.set_shader_parameter("amount", _k * _k * (3.0 - 2.0 * _k))
