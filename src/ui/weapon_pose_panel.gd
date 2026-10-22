class_name WeaponPosePanel
extends PanelContainer
## Интерфейс стенда: сантиметры для переноса, градусы для поворота; сигналы не меняют игрока.

signal weapon_selected(index: int)
signal pose_selected(index: int)
signal stance_selected(index: int)
signal values_changed(position: Vector3, rotation: Vector3)
signal comparison_changed(original: bool)
signal save_requested
signal restore_requested
signal reset_requested
signal play_requested
signal back_requested
signal copy_requested

var weapons: OptionButton
var poses: OptionButton
var stances: OptionButton
var compare: CheckButton
var use_in_game: CheckButton
var status: Label
var _position: Array[SpinBox] = []
var _rotation: Array[SpinBox] = []
var _sliders: Array[HSlider] = []


func _ready() -> void:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.035, 0.042, 0.05, 0.96)
	style.border_color = Color(0.7, 0.63, 0.46, 0.55)
	style.set_border_width_all(1)
	style.set_content_margin_all(18)
	add_theme_stylebox_override("panel", style)
	var frame: VBoxContainer = VBoxContainer.new()
	frame.add_theme_constant_override("separation", 10)
	add_child(frame)
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	frame.add_child(scroll)
	var body: VBoxContainer = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 8)
	scroll.add_child(body)
	_label(body, "Положение оружия", 28)
	_label(body, "Выбери оружие и позу. Изменения видны сразу.", 16)
	weapons = _options(body, "Оружие")
	weapons.item_selected.connect(func(index: int) -> void: weapon_selected.emit(index))
	poses = _options(body, "Настраиваемая поза")
	for title: String in ["От бедра", "Прицеливание", "Опущенное оружие"]:
		poses.add_item(title)
	poses.item_selected.connect(func(index: int) -> void: pose_selected.emit(index))
	stances = _options(body, "Стойка игрока")
	for title: String in ["Стоя", "Сидя", "Лёжа"]:
		stances.add_item(title)
	stances.item_selected.connect(func(index: int) -> void: stance_selected.emit(index))
	_label(body, "Смещение от исходной позы · см", 19)
	for axis: int in range(3):
		var title: String = ["Влево (−) / вправо (+)", "Ниже (−) / выше (+)", "Дальше (−) / ближе к глазам (+)"][axis]
		_position.append(_axis(body, title, WeaponPoseProfiles.POSITION_LIMIT[axis] * 100.0, 0.1, " см"))
	_label(body, "Поворот оружия · градусы", 19)
	for title: String in ["Наклон вверх / вниз", "Поворот в стороны", "Завал в стороны"]:
		_rotation.append(_axis(body, title, WeaponPoseProfiles.ROTATION_LIMIT, 0.5, "°"))
	compare = CheckButton.new()
	compare.text = "Исходная поза для сравнения · F7"
	compare.focus_mode = Control.FOCUS_NONE
	body.add_child(compare)
	compare.toggled.connect(func(original: bool) -> void: comparison_changed.emit(original))
	use_in_game = CheckButton.new()
	use_in_game.text = "Использовать сохранённые позы в игре"
	use_in_game.focus_mode = Control.FOCUS_NONE
	body.add_child(use_in_game)
	use_in_game.toggled.connect(func(_on: bool) -> void: set_status("Есть несохранённые изменения"))
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	body.add_child(row)
	_button(row, "Сбросить эту позу", func() -> void: reset_requested.emit())
	_button(row, "Загрузить сохранённое", func() -> void: restore_requested.emit())
	_button(body, "Скопировать значения этой позы", func() -> void: copy_requested.emit())
	_button(body, "В главное меню", func() -> void: back_requested.emit())
	_label(body, "Сохранение — для этого компьютера.\nИсходная поза: 0 см и 0°. У стены оружие отводится автоматически.", 14)
	_button(frame, "Сохранить все настройки · Ctrl+S", func() -> void: save_requested.emit())
	_button(frame, "Проверить в движении · F6", func() -> void: play_requested.emit())
	status = _label(frame, "", 15)
	status.add_theme_color_override("font_color", Color(1.0, 0.82, 0.5))


func _label(parent: Node, text: String, font_size: int) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	parent.add_child(label)
	return label


func _options(parent: Node, title: String) -> OptionButton:
	_label(parent, title, 15)
	var options: OptionButton = OptionButton.new()
	options.custom_minimum_size.y = 34
	options.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	options.focus_mode = Control.FOCUS_NONE
	options.add_theme_font_size_override("font_size", 17)
	parent.add_child(options)
	return options


func _button(parent: Node, text: String, action: Callable) -> Button:
	var button: Button = Button.new()
	button.text = text
	button.custom_minimum_size.y = 36
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 15)
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _axis(parent: Node, title: String, limit: float, step_size: float, suffix: String) -> SpinBox:
	_label(parent, title, 15)
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	parent.add_child(row)
	var slider: HSlider = HSlider.new()
	slider.min_value = -limit
	slider.max_value = limit
	slider.step = step_size
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	slider.focus_mode = Control.FOCUS_NONE
	row.add_child(slider)
	_sliders.append(slider)
	var spin: SpinBox = SpinBox.new()
	spin.min_value = -limit
	spin.max_value = limit
	spin.step = step_size
	spin.suffix = suffix
	spin.custom_minimum_size = Vector2(128, 32)
	spin.add_theme_font_size_override("font_size", 16)
	spin.update_on_text_changed = true
	row.add_child(spin)
	slider.value_changed.connect(func(value: float) -> void:
		spin.set_value_no_signal(value)
		_emit_values())
	spin.value_changed.connect(func(value: float) -> void:
		slider.set_value_no_signal(value)
		_emit_values())
	return spin


func _emit_values() -> void:
	if _position.size() != 3 or _rotation.size() != 3:
		return
	compare.set_pressed_no_signal(false)
	values_changed.emit(Vector3(_position[0].value, _position[1].value, _position[2].value) / 100.0,
		Vector3(_rotation[0].value, _rotation[1].value, _rotation[2].value))


func show_values(value: Dictionary) -> void:
	var position: Vector3 = value.position as Vector3
	var rotation: Vector3 = value.rotation as Vector3
	for axis: int in range(3):
		_position[axis].set_value_no_signal(position[axis] * 100.0)
		_rotation[axis].set_value_no_signal(rotation[axis])
		_sliders[axis].set_value_no_signal(position[axis] * 100.0)
		_sliders[axis + 3].set_value_no_signal(rotation[axis])


func set_status(text: String) -> void:
	status.text = text
