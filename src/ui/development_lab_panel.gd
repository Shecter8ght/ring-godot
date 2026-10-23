class_name DevelopmentLabPanel
extends PanelContainer
## Общая панель трёх стендов. Основные действия закреплены, длинные настройки прокручиваются.

signal value_changed(key: String, value: Variant)
signal save_requested
signal load_requested(name: String)
signal defaults_requested
signal comparison_changed(original: bool)
signal play_requested
signal overview_requested
signal back_requested

var context: VBoxContainer
var tuning: VBoxContainer
var fields: Dictionary = {}
var presets: OptionButton
var preset_name: LineEdit
var use_in_game: CheckButton
var compare: CheckButton
var status: Label
var tabs: TabContainer
var _title: Label


func _ready() -> void:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.035, 0.042, 0.05, 0.97)
	style.border_color = Color(0.7, 0.63, 0.46, 0.6)
	style.set_border_width_all(1)
	style.set_content_margin_all(16)
	add_theme_stylebox_override("panel", style)
	var frame: VBoxContainer = VBoxContainer.new()
	frame.add_theme_constant_override("separation", 8)
	add_child(frame)
	_title = label(frame, "Стенд", 25)
	tabs = TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.add_theme_font_size_override("font_size", 17)
	frame.add_child(tabs)
	context = _page("Проверка")
	tuning = _page("Параметры")
	var body: VBoxContainer = _page("Варианты")
	label(body, "Сохранённые варианты", 17)
	presets = OptionButton.new()
	presets.focus_mode = Control.FOCUS_NONE
	body.add_child(presets)
	presets.item_selected.connect(func(index: int) -> void: load_requested.emit(presets.get_item_text(index)))
	preset_name = LineEdit.new()
	preset_name.placeholder_text = "Имя варианта"
	preset_name.max_length = 60
	preset_name.custom_minimum_size.y = 34
	body.add_child(preset_name)
	use_in_game = CheckButton.new()
	use_in_game.text = "После сохранения применять в игре"
	use_in_game.focus_mode = Control.FOCUS_NONE
	body.add_child(use_in_game)
	compare = CheckButton.new()
	compare.text = "Исходные значения для сравнения · F7"
	compare.focus_mode = Control.FOCUS_NONE
	body.add_child(compare)
	compare.toggled.connect(func(original: bool) -> void: comparison_changed.emit(original))
	action("Вернуть исходные значения в черновик", func() -> void: defaults_requested.emit(), body)
	action("Камера сверху / из глаз · F8", func() -> void: overview_requested.emit(), body)
	action("В главное меню", func() -> void: back_requested.emit(), body)
	action("Сохранить вариант · Ctrl+S", func() -> void: save_requested.emit(), frame)
	action("Проверить в движении · F6", func() -> void: play_requested.emit(), frame)
	status = label(frame, "", 15)
	status.add_theme_color_override("font_color", Color(1.0, 0.82, 0.5))


func _page(title: String) -> VBoxContainer:
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tabs.add_child(scroll)
	var body: VBoxContainer = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 8)
	scroll.add_child(body)
	return body


func label(parent: Node, text: String, size: int = 16) -> Label:
	var control: Label = Label.new()
	control.text = text
	control.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	control.add_theme_font_size_override("font_size", size)
	parent.add_child(control)
	return control


func action(text: String, callback: Callable, parent: Node = null) -> Button:
	var button: Button = Button.new()
	button.text = text
	button.custom_minimum_size.y = 34
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_font_size_override("font_size", 16)
	button.pressed.connect(callback)
	(parent if parent else context).add_child(button)
	return button


func option(text: String, items: Array, callback: Callable) -> OptionButton:
	label(context, text, 16)
	var control: OptionButton = OptionButton.new()
	control.focus_mode = Control.FOCUS_NONE
	control.custom_minimum_size.y = 34
	control.add_theme_font_size_override("font_size", 16)
	for title: Variant in items:
		control.add_item(String(title))
	context.add_child(control)
	control.item_selected.connect(callback)
	return control


func toggle(text: String, initial: bool, callback: Callable) -> CheckButton:
	var control: CheckButton = CheckButton.new()
	control.text = text
	control.focus_mode = Control.FOCUS_NONE
	control.set_pressed_no_signal(initial)
	context.add_child(control)
	control.toggled.connect(callback)
	return control


func number(text: String, initial: float, minimum: float, maximum: float, step_size: float, callback: Callable) -> SpinBox:
	label(context, text, 16)
	return _numeric(context, initial, minimum, maximum, step_size, callback)


func _numeric(parent: Node, initial: float, minimum: float, maximum: float, step_size: float, callback: Callable) -> SpinBox:
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	var slider: HSlider = HSlider.new()
	slider.min_value = minimum
	slider.max_value = maximum
	slider.step = step_size
	slider.value = initial
	slider.focus_mode = Control.FOCUS_NONE
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)
	var spin: SpinBox = SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.step = step_size
	spin.value = initial
	spin.custom_minimum_size = Vector2(110, 32)
	spin.update_on_text_changed = true
	row.add_child(spin)
	spin.set_meta("slider", slider)
	slider.value_changed.connect(func(value: float) -> void:
		spin.set_value_no_signal(value)
		callback.call(value))
	spin.value_changed.connect(func(value: float) -> void:
		slider.set_value_no_signal(value)
		callback.call(value))
	return spin


func configure(title: String, domain: String, values: Dictionary) -> void:
	_title.text = title
	fields.clear()
	for child: Node in tuning.get_children():
		tuning.remove_child(child)
		child.queue_free()
	for key: String in Balance.lab_rules(domain):
		var rule: Array = Balance.lab_rules(domain)[key]
		label(tuning, String(rule[0]), 15)
		if rule[1] is Color:
			var picker: ColorPickerButton = ColorPickerButton.new()
			picker.color = values[key] as Color
			picker.edit_alpha = false
			picker.custom_minimum_size.y = 32
			tuning.add_child(picker)
			picker.color_changed.connect(func(value: Color) -> void: value_changed.emit(key, value))
			fields[key] = picker
		else:
			fields[key] = _numeric(tuning, float(values[key]), float(rule[2]), float(rule[3]), float(rule[4]),
				func(value: float) -> void: value_changed.emit(key, value))
	presets.clear()
	for name: Variant in LabTuning.names(domain):
		presets.add_item(String(name))
	preset_name.text = LabTuning.active_name(domain)
	use_in_game.set_pressed_no_signal(LabTuning.enabled(domain))
