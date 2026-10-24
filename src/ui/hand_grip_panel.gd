class_name HandGripPanel
extends VBoxContainer
## Сантиметры и градусы: обе кисти и каждый из трёх суставов пяти пальцев.

signal values_changed(value: Dictionary)
signal side_selected(index: int)
signal view_selected(index: int)
signal reset_requested
signal grip_copy_requested(sides: Array[String])
signal grip_paste_requested

var sides: OptionButton
var views: OptionButton
var fingers: OptionButton
var use_in_game: CheckButton
var context: Label
var transfer_scope: OptionButton
var copy_grip: Button
var paste_grip: Button
var transfer_info: Label
var _position: Array[SpinBox] = []
var _rotation: Array[SpinBox] = []
var _bend: Array[SpinBox] = []
var _spread: SpinBox
var _twist: SpinBox
var _sliders: Array[HSlider] = []
var _value: Dictionary = HandGripProfiles.sanitize({})
var _body: VBoxContainer
var tabs: TabContainer


func _ready() -> void:
	add_theme_constant_override("separation", 6)
	_body = self
	var selectors: HBoxContainer = HBoxContainer.new()
	selectors.add_theme_constant_override("separation", 10)
	add_child(selectors)
	var side_body: VBoxContainer = VBoxContainer.new()
	side_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selectors.add_child(side_body)
	var view_body: VBoxContainer = VBoxContainer.new()
	view_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selectors.add_child(view_body)
	_body = side_body
	sides = _options("Кисть", ["Левая", "Правая"])
	sides.item_selected.connect(func(index: int) -> void: side_selected.emit(index))
	_body = view_body
	views = _options("Камера · F8", ["Из глаз", "Осмотр кисти", "Обе руки"])
	views.select(1)
	views.item_selected.connect(func(index: int) -> void: view_selected.emit(index))
	_body = self
	context = _label("", 14)
	tabs = TabContainer.new()
	add_child(tabs)
	var palm: VBoxContainer = VBoxContainer.new()
	palm.name = "Положение"
	palm.add_theme_constant_override("separation", 6)
	tabs.add_child(palm)
	var turn: VBoxContainer = VBoxContainer.new()
	turn.name = "Поворот"
	turn.add_theme_constant_override("separation", 6)
	tabs.add_child(turn)
	var digit: VBoxContainer = VBoxContainer.new()
	digit.name = "Пальцы"
	digit.add_theme_constant_override("separation", 6)
	tabs.add_child(digit)
	var transfer: VBoxContainer = VBoxContainer.new()
	transfer.name = "Перенос"
	transfer.add_theme_constant_override("separation", 8)
	tabs.add_child(transfer)
	_body = palm
	_label("Положение кисти на оружии · см", 19)
	for title: String in ["К правому (−) / левому (+) боку", "Ниже (−) / выше (+)", "К прикладу (−) / к дулу (+)"]:
		_position.append(_axis(title, HandGripProfiles.POSITION_LIMIT * 100.0, 0.1, " см"))
	_body = turn
	_label("Поворот кисти · градусы", 19)
	for title: String in ["Вверх / вниз · X", "В стороны · Y", "Вокруг ствола · Z"]:
		_rotation.append(_axis(title, HandGripProfiles.ROTATION_LIMIT, 0.5, "°"))
	_body = digit
	fingers = _options("Палец", ["Указательный", "Средний", "Безымянный", "Мизинец", "Большой"])
	fingers.item_selected.connect(func(_index: int) -> void: _show_finger())
	_label("Сгиб от исходного хвата · + сжать / − разжать", 15)
	for title: String in ["Сустав у ладони", "Средний сустав", "Кончик пальца"]:
		_bend.append(_axis(title, HandGripProfiles.BEND_LIMIT, 1.0, "°"))
	_spread = _axis("Разведение пальца", HandGripProfiles.SPREAD_LIMIT, 1.0, "°")
	_twist = _axis("Поворот пальца вокруг своей оси", HandGripProfiles.TWIST_LIMIT, 1.0, "°")
	_body = transfer
	_label("Настрой хват, скопируй его, выбери другое оружие и нажми «Вставить хват».", 16)
	transfer_scope = _options("Что скопировать", ["Обе кисти", "Левую кисть", "Правую кисть"])
	copy_grip = _transfer_button("Скопировать хват", _request_grip_copy)
	paste_grip = _transfer_button("Вставить хват", func() -> void: grip_paste_requested.emit())
	transfer_info = _label("", 14)
	_label("Переносятся положение и поворот кистей и все настройки пальцев. После вставки можно поправить хват и сохранить · Ctrl+S.", 14)
	show_grip_buffer("", [])
	_body = self
	use_in_game = CheckButton.new()
	use_in_game.text = "Использовать сохранённый хват в игре"
	use_in_game.focus_mode = Control.FOCUS_NONE
	add_child(use_in_game)
	var reset: Button = Button.new()
	reset.text = "Сбросить эту кисть и её пальцы"
	reset.custom_minimum_size.y = 36
	reset.focus_mode = Control.FOCUS_NONE
	reset.pressed.connect(func() -> void: reset_requested.emit())
	add_child(reset)
	_label("Нули возвращают исходный хват. В перезарядке руки следуют анимации; поправка возвращается в стойке.", 14)
	show_values(_value)


func _transfer_button(text: String, action: Callable) -> Button:
	var button: Button = Button.new()
	button.text = text
	button.custom_minimum_size.y = 36
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(action)
	_body.add_child(button)
	return button


func _request_grip_copy() -> void:
	var selected: Array[String] = []
	if transfer_scope.selected == 0:
		selected.assign(HandGripProfiles.SIDES)
	else:
		selected.append(HandGripProfiles.SIDES[transfer_scope.selected - 1])
	grip_copy_requested.emit(selected)


func show_grip_buffer(source: String, sides: Array[String]) -> void:
	paste_grip.disabled = source.is_empty() or sides.is_empty()
	if paste_grip.disabled:
		transfer_info.text = "Хват ещё не скопирован."
		return
	var scope: String = "обе кисти" if sides.size() == 2 else ("левая кисть" if sides[0] == "Left" else "правая кисть")
	transfer_info.text = "Скопировано: %s · %s.\nВыбери другое оружие и вставь хват. Его можно вставлять несколько раз до закрытия стенда." % [source, scope]


func _label(text: String, font_size: int) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	_body.add_child(label)
	return label


func _options(title: String, entries: Array[String]) -> OptionButton:
	_label(title, 15)
	var options: OptionButton = OptionButton.new()
	options.fit_to_longest_item = false
	options.clip_text = true
	options.custom_minimum_size.y = 32
	options.focus_mode = Control.FOCUS_NONE
	options.add_theme_font_size_override("font_size", 16)
	for entry: String in entries:
		options.add_item(entry)
	_body.add_child(options)
	return options


func _axis(title: String, limit: float, step_size: float, suffix: String) -> SpinBox:
	_label(title, 14)
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	_body.add_child(row)
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
	spin.custom_minimum_size = Vector2(122, 30)
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
	if _twist == null:
		return
	_value.position = Vector3(_position[0].value, _position[1].value, _position[2].value) / 100.0
	_value.rotation = Vector3(_rotation[0].value, _rotation[1].value, _rotation[2].value)
	var finger: String = HandGripProfiles.FINGERS[fingers.selected]
	_value.fingers[finger] = {"bend": Vector3(_bend[0].value, _bend[1].value, _bend[2].value), "spread": _spread.value, "twist": _twist.value}
	values_changed.emit(_value.duplicate(true))


func show_values(value: Dictionary) -> void:
	_value = HandGripProfiles.sanitize(value)
	for axis: int in range(3):
		_position[axis].set_value_no_signal((_value.position as Vector3)[axis] * 100.0)
		_rotation[axis].set_value_no_signal((_value.rotation as Vector3)[axis])
		_sliders[axis].set_value_no_signal(_position[axis].value)
		_sliders[axis + 3].set_value_no_signal(_rotation[axis].value)
	_show_finger()


func _show_finger() -> void:
	var finger: Dictionary = _value.fingers[HandGripProfiles.FINGERS[fingers.selected]]
	for joint: int in range(3):
		_bend[joint].set_value_no_signal((finger.bend as Vector3)[joint])
		_sliders[joint + 6].set_value_no_signal(_bend[joint].value)
	_spread.set_value_no_signal(float(finger.spread))
	_twist.set_value_no_signal(float(finger.twist))
	_sliders[9].set_value_no_signal(_spread.value)
	_sliders[10].set_value_no_signal(_twist.value)
