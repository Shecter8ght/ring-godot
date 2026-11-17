extends PanelContainer

const Daylight203 := preload("res://tools/bc5_meeting203/daylight.gd")

var daylight: Daylight203
var _height := HSlider.new()
var _azimuth := HSlider.new()
var _height_value := SpinBox.new()
var _azimuth_value := SpinBox.new()


func _ready() -> void:
	add_to_group("esc_windows")
	position = Vector2(24, 64)
	custom_minimum_size.x = 412
	var panel := UiTheme.face(Color(.065, .062, .055, .95), Color(.51, .45, .35), 0)
	panel.set_content_margin_all(12)
	add_theme_stylebox_override("panel", panel)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 8)
	add_child(content)
	var heading := Label.new()
	heading.text = "Положение солнца"
	heading.add_theme_font_size_override("font_size", 18)
	heading.add_theme_color_override("font_color", UiTheme.C_ACCENT)
	content.add_child(heading)
	_add_angle_row(content, "Высота", _height, _height_value, -90.0, 90.0)
	_add_angle_row(content, "Азимут", _azimuth, _azimuth_value, 0.0, 360.0)
	var compass := "0° — север · 90° — восток · 180° — юг · 270° — запад"
	_azimuth.tooltip_text = compass
	_azimuth_value.tooltip_text = compass
	var actions := HBoxContainer.new()
	actions.alignment = BoxContainer.ALIGNMENT_END
	content.add_child(actions)
	var reset := Button.new()
	reset.text = "По времени суток"
	reset.pressed.connect(_reset)
	actions.add_child(reset)
	var done := Button.new()
	done.text = "Закрыть"
	done.pressed.connect(hide)
	actions.add_child(done)


func _add_angle_row(content: VBoxContainer, title: String, slider: HSlider, entry: SpinBox,
		minimum: float, maximum: float) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	content.add_child(row)
	var label := Label.new()
	label.text = title
	label.custom_minimum_size.x = 63
	row.add_child(label)
	slider.name = title + "Slider"
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	slider.mouse_default_cursor_shape = Control.CURSOR_DRAG
	row.add_child(slider)
	entry.name = title + "Value"
	entry.custom_minimum_size.x = 104
	entry.suffix = "°"
	row.add_child(entry)
	for control: Range in [slider, entry]:
		control.min_value = minimum
		control.max_value = maximum
		control.step = .1
	slider.value_changed.connect(entry.set_value_no_signal)
	slider.value_changed.connect(_angles_changed)
	entry.value_changed.connect(func(degrees: float) -> void: slider.value = degrees)


func is_open() -> bool:
	return is_visible_in_tree()


func _input(event: InputEvent) -> void:
	if PauseMenu.shown or not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.physical_keycode != KEY_F8 and not (is_open() and event.is_action_pressed("pause")):
		return
	if is_open():
		hide()
	else:
		sync()
		show()
	get_viewport().set_input_as_handled()


func sync() -> void:
	var angles := daylight.sun_angles()
	_height.set_value_no_signal(angles.x)
	_height_value.set_value_no_signal(angles.x)
	_azimuth.set_value_no_signal(angles.y)
	_azimuth_value.set_value_no_signal(angles.y)


func _angles_changed(_degrees: float) -> void:
	daylight.set_sun_angles(Vector2(_height.value, _azimuth.value))


func _reset() -> void:
	daylight.reset_sun_angles()
	sync()
