extends CanvasLayer
## Подтверждённое обнаружение своим врагом: глаз, надпись и направление относительно взгляда.
## Получает только снимки настоящего зрения от хоста; после потери контакта источник не отслеживается.

var camera_basis: Basis = Basis.IDENTITY
var _contacts: Dictionary = {}
var _enabled: bool = true

@onready var _screen: Control = $Screen
@onready var _label: Label = $Screen/Status


func _ready() -> void:
	_screen.visible = false
	_screen.draw.connect(_draw_indicator)
	_label.add_theme_color_override("font_color", Balance.DETECTION_INDICATOR.color)
	_label.add_theme_constant_override("outline_size", int(Balance.DETECTION_INDICATOR.text_outline))


func set_enabled(on: bool) -> void:
	_enabled = on
	if not on:
		_contacts.clear()
		_screen.visible = false


func contact(observer: int, from: Vector3, origin: Vector3) -> void:
	if not _enabled or not from.is_finite() or not origin.is_finite():
		return
	var direction: Vector3 = from - origin
	direction.y = 0.0
	if not _contacts.has(observer) and _contacts.size() >= int(Balance.DETECTION_INDICATOR.max_sources):
		var oldest: int = int(_contacts.keys()[0])
		for key: int in _contacts:
			if float(_contacts[key].age) > float(_contacts[oldest].age):
				oldest = key
		_contacts.erase(oldest)
	_contacts[observer] = {"direction": direction.normalized(), "age": 0.0}


func direction_on_screen(direction: Vector3) -> Vector2:
	var forward: Vector3 = -camera_basis.z
	forward.y = 0.0
	if forward.is_zero_approx():
		forward = Vector3.UP.cross(camera_basis.x)
	forward = forward.normalized()
	return Vector2(direction.dot(forward.cross(Vector3.UP)), -direction.dot(forward)).normalized()


func _alpha(age: float) -> float:
	var d: Dictionary = Balance.DETECTION_INDICATOR
	return 1.0 - smoothstep(float(d.hold_sec), float(d.hold_sec) + float(d.fade_sec), age)


func _process(delta: float) -> void:
	var d: Dictionary = Balance.DETECTION_INDICATOR
	var alpha: float = 0.0
	for key: int in _contacts.keys():
		_contacts[key].age = float(_contacts[key].age) + delta
		var age: float = float(_contacts[key].age)
		if age >= float(d.hold_sec) + float(d.fade_sec):
			_contacts.erase(key)
		else:
			alpha = maxf(alpha, _alpha(age))
	_screen.visible = not _contacts.is_empty()
	if not _screen.visible:
		return
	var short_side: float = minf(_screen.size.x, _screen.size.y)
	_label.add_theme_font_size_override("font_size", clampi(roundi(short_side * float(d.font_size)), int(d.font_min), int(d.font_max)))
	_label.size = _label.get_minimum_size()
	_label.position = _screen.size * 0.5 - Vector2(_label.size.x * 0.5, short_side * float(d.status_offset))
	_label.modulate.a = alpha
	_screen.queue_redraw()


func _draw_indicator() -> void:
	var d: Dictionary = Balance.DETECTION_INDICATOR
	var center: Vector2 = _screen.size * 0.5
	var short_side: float = minf(_screen.size.x, _screen.size.y)
	var line_width: float = short_side * float(d.line_width)
	var outline_width: float = short_side * float(d.outline_width)
	var shown: Array[Vector2] = []
	# Сначала свежие наблюдатели: близкие направления объединяются только при отрисовке.
	var contacts: Array = _contacts.values()
	contacts.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.age) < float(b.age))
	for entry: Dictionary in contacts:
		var direction: Vector2 = direction_on_screen(entry.direction)
		if direction.is_zero_approx():
			continue
		var duplicate: bool = false
		for other: Vector2 in shown:
			if direction.dot(other) >= cos(deg_to_rad(float(d.merge_deg))):
				duplicate = true
				break
		if duplicate:
			continue
		shown.append(direction)
		var tip: Vector2 = center + direction * short_side * float(d.radius)
		var back: Vector2 = tip - direction * short_side * float(d.arrow_depth)
		var side: Vector2 = Vector2(-direction.y, direction.x) * short_side * float(d.arrow_half_width)
		var points: PackedVector2Array = PackedVector2Array([back + side, tip, back - side])
		var color: Color = d.color
		var outline: Color = d.outline_color
		color.a = _alpha(float(entry.age))
		outline.a = color.a
		_screen.draw_polyline(points, outline, outline_width, true)
		_screen.draw_polyline(points, color, line_width, true)
	# Глаз слева от текста; обводка сохраняет читаемость на светлом фоне и под эффектами ранения.
	var eye: Vector2 = _label.position + Vector2(-short_side * (float(d.eye_width) + float(d.eye_gap)), _label.size.y * 0.5)
	var contour: PackedVector2Array = PackedVector2Array()
	var segments: int = int(d.eye_segments)
	for i: int in range(segments + 1):
		var phase: float = TAU * i / segments
		contour.append(eye + Vector2(cos(phase) * float(d.eye_width), sin(phase) * float(d.eye_height)) * short_side)
	var eye_color: Color = d.color
	var eye_outline: Color = d.outline_color
	eye_color.a = _label.modulate.a
	eye_outline.a = eye_color.a
	_screen.draw_polyline(contour, eye_outline, outline_width, true)
	_screen.draw_polyline(contour, eye_color, line_width, true)
	_screen.draw_circle(eye, short_side * float(d.pupil), eye_color, true, -1.0, true)
