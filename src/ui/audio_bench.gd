extends CanvasLayer
## Прослушивание через Audio в текущем мире. Настройки относятся к событию и к исходной записи.

const ReloadPanel := preload("res://src/ui/reload_audio_panel.gd")

var _root: Control
var _reload_tab: VBoxContainer
var _reload_panel: ReloadPanel
var _list: ItemList
var _search: LineEdit
var _category: OptionButton
var _filter: OptionButton
var _variants: OptionButton
var _title: Label
var _details: Label
var _status: Label
var _event_level: SpinBox
var _file_level: SpinBox
var _distance: SpinBox
var _angle: SpinBox
var _loop: CheckBox
var _sound_path: OptionButton
var _spectral: CheckBox
var _play_button: Button
var _save_timer: Timer
var _step_repeat: Timer
var _step_controls: VBoxContainer
var _step_mode: OptionButton
var _step_base_gain: SpinBox
var _id: String = ""
var _updating: bool = false
var _dirty: bool = false
var _players: Array[Node] = []
var _listener: AudioListener3D
var _preview_camera: Camera3D
var _mouse_before: Input.MouseMode


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 80
	add_to_group("esc_windows")
	_mouse_before = Input.mouse_mode
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if not Audio._has_ears():
		# Для 3D-звука из главного меню Godot нужна камера в этом мире.
		_preview_camera = Camera3D.new()
		_preview_camera.current = true
		add_child(_preview_camera)
		_listener = AudioListener3D.new()
		add_child(_listener)
		_listener.make_current()
	_build()
	_refresh()


func is_open() -> bool:
	return true


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause"):
		_close()
		get_viewport().set_input_as_handled()


func _label(text: String, size: int = 16) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.add_theme_font_size_override("font_size", size)
	return label


func _button(text: String, action: Callable) -> Button:
	var button: Button = Button.new()
	button.text = text
	button.custom_minimum_size.y = 40
	button.pressed.connect(action)
	return button


func _build() -> void:
	_root = PanelContainer.new()
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_root)
	var margin: MarginContainer = MarginContainer.new()
	for side: String in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	_root.add_child(margin)
	var column: VBoxContainer = VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	margin.add_child(column)
	var header: HBoxContainer = HBoxContainer.new()
	column.add_child(header)
	var heading: Label = _label("Звуковой стенд RING", 28)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(heading)
	header.add_child(_button("Обновить назначения", _refresh))
	header.add_child(_button("Закрыть · Esc", _close))
	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(tabs)
	var catalog := VBoxContainer.new()
	catalog.name = "Каталог"
	tabs.add_child(catalog)
	_reload_tab = VBoxContainer.new()
	_reload_tab.name = "Перезарядка"
	tabs.add_child(_reload_tab)
	tabs.tab_changed.connect(_show_tab)
	var row: HBoxContainer = HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 24)
	catalog.add_child(row)
	var left: VBoxContainer = VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 1.2
	row.add_child(left)
	_search = LineEdit.new()
	_search.placeholder_text = "Поиск: модель, действие, поверхность, файл…"
	_search.text_changed.connect(func(_text: String) -> void: _fill_list())
	left.add_child(_search)
	var filters: HBoxContainer = HBoxContainer.new()
	left.add_child(filters)
	_category = OptionButton.new()
	_category.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_category.item_selected.connect(func(_index: int) -> void: _fill_list())
	filters.add_child(_category)
	_filter = OptionButton.new()
	for text: String in ["Все", "Назначенные", "Пустые"]:
		_filter.add_item(text)
	_filter.select(1)
	_filter.item_selected.connect(func(_index: int) -> void: _fill_list())
	filters.add_child(_filter)
	_list = ItemList.new()
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.item_selected.connect(func(index: int) -> void: _select(String(_list.get_item_metadata(index))))
	_list.item_activated.connect(func(_index: int) -> void: _play())
	left.add_child(_list)
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	row.add_child(scroll)
	var right: VBoxContainer = VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 12)
	scroll.add_child(right)
	_title = _label("Выберите звук", 22)
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(_title)
	_details = _label("")
	_details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(_details)
	right.add_child(_label("Вариант записи"))
	_variants = OptionButton.new()
	_variants.item_selected.connect(func(_index: int) -> void: _select_variant())
	right.add_child(_variants)
	_event_level = _level_control(right, "Громкость события · дБ", false)
	_file_level = _level_control(right, "Поправка выбранной записи · дБ", true)
	_step_controls = VBoxContainer.new()
	_step_controls.hide()
	right.add_child(_step_controls)
	_step_mode = OptionButton.new()
	for mode: String in ["Основа и покрытие", "Только основа", "Только покрытие"]:
		_step_mode.add_item(mode)
	_step_mode.item_selected.connect(_step_mode_changed)
	_step_controls.add_child(_step_mode)
	_step_base_gain = _gain_control(_step_controls, "Громкость основы шага · дБ", -60.0, 24.0, _change_step_base_gain)
	_step_repeat = Timer.new()
	_step_repeat.wait_time = Balance.STEP_WALK_SEC
	_step_repeat.timeout.connect(_play_step_take)
	add_child(_step_repeat)
	var position_row: HBoxContainer = HBoxContainer.new()
	right.add_child(position_row)
	position_row.add_child(_label("Расстояние, м"))
	_distance = SpinBox.new()
	_distance.min_value = 0.2
	_distance.max_value = 300.0
	_distance.step = 0.2
	_distance.value = 1.0
	position_row.add_child(_distance)
	position_row.add_child(_label("Направление, °"))
	_angle = SpinBox.new()
	_angle.min_value = -180
	_angle.max_value = 180
	_angle.step = 15
	position_row.add_child(_angle)
	var path_row := HBoxContainer.new()
	right.add_child(path_row)
	path_row.add_child(_label("Преграда"))
	_sound_path = OptionButton.new()
	_sound_path.add_item("Как в сцене", Audio.SoundPathPreview.SCENE)
	_sound_path.add_item("Открыто", Audio.SoundPathPreview.OPEN)
	_sound_path.add_item("За стеной", Audio.SoundPathPreview.WALL)
	path_row.add_child(_sound_path)
	_sound_path.item_selected.connect(func(_index: int) -> void:
		if not _players.is_empty():
			_play())
	_spectral = CheckBox.new()
	_spectral.text = "Приглушать высокие частоты"
	_spectral.button_pressed = true
	_spectral.tooltip_text = "Выключи для сравнения на той же дистанции и с тем же ослаблением громкости за стеной."
	_spectral.toggled.connect(_preview_spectral)
	right.add_child(_spectral)
	_loop = CheckBox.new()
	_loop.text = "Повторять до остановки"
	right.add_child(_loop)
	var controls: HBoxContainer = HBoxContainer.new()
	right.add_child(controls)
	_play_button = _button("▶ Прослушать", _play)
	_play_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	controls.add_child(_play_button)
	controls.add_child(_button("■ Стоп", _stop))
	right.add_child(_button("Сбросить уровни события и записи", _reset_levels))
	_status = _label("Настройки сохраняются автоматически.")
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(_status)
	_save_timer = Timer.new()
	_save_timer.one_shot = true
	_save_timer.wait_time = 0.4
	_save_timer.timeout.connect(_save)
	add_child(_save_timer)


func _show_tab(index: int) -> void:
	_stop()
	if index == 1 and not _reload_panel:
		_reload_panel = ReloadPanel.new()
		_reload_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
		_reload_tab.add_child(_reload_panel)
	elif _reload_panel:
		_reload_panel.stop()


func _level_control(parent: VBoxContainer, text: String, file_level: bool) -> SpinBox:
	return _gain_control(parent, text, -60.0, 24.0, _change_level.bind(file_level))


func _gain_control(parent: VBoxContainer, text: String, minimum: float, maximum: float, on_change: Callable) -> SpinBox:
	parent.add_child(_label(text))
	var row: HBoxContainer = HBoxContainer.new()
	parent.add_child(row)
	var slider: HSlider = HSlider.new()
	slider.min_value = minimum
	slider.max_value = maximum
	slider.step = 0.5
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)
	var number: SpinBox = SpinBox.new()
	number.min_value = minimum
	number.max_value = maximum
	number.step = 0.5
	number.suffix = " дБ"
	number.custom_minimum_size.x = 92
	row.add_child(number)
	slider.value_changed.connect(func(value: float) -> void: number.value = value)
	number.value_changed.connect(func(value: float) -> void:
		slider.set_value_no_signal(value)
		if not _updating:
			on_change.call(value))
	return number


func _refresh() -> void:
	_stop()
	Audio.reload_events()
	if _reload_panel:
		_reload_panel.refresh()
	_category.clear()
	_category.add_item("Все категории")
	var categories: Array[String] = []
	for event: Dictionary in Audio._events.values():
		var name: String = _category_name(event)
		if name not in categories:
			categories.append(name)
	categories.sort()
	for name: String in categories:
		_category.add_item(name)
	_fill_list()


func _display_name(event: Dictionary) -> String:
	var weapon: String = String(event.get("weapon", ""))
	return (String((WeaponDb.items().get(weapon, {}) as Dictionary).get("name", weapon)) + " · " if weapon != "" else "") + String(event.get("name", event.id))


func _category_name(event: Dictionary) -> String:
	return "Оружие" if String(event.get("weapon", "")) != "" else String(event.get("category", "Другие события"))


func _weapon_name(event: Dictionary) -> String:
	var id: String = String(event.get("weapon", ""))
	return String((WeaponDb.items().get(id, {}) as Dictionary).get("name", id)) if id != "" else ""


func _event_less(a: String, b: String) -> bool:
	var first: Dictionary = Audio._events[a]
	var second: Dictionary = Audio._events[b]
	for pair: Array in [[_category_name(first), _category_name(second)], [_weapon_name(first), _weapon_name(second)], [String(first.get("name", a)), String(second.get("name", b))]]:
		var order: int = String(pair[0]).naturalnocasecmp_to(String(pair[1]))
		if order != 0:
			return order < 0
	return a.naturalnocasecmp_to(b) < 0


func _group_heading(text: String, model: bool = false) -> void:
	var index: int = _list.add_item(("    " if model else "") + text)
	_list.set_item_metadata(index, "")
	_list.set_item_selectable(index, false)
	_list.set_item_custom_fg_color(index, Color(0.75, 0.8, 0.85) if model else Color(1.0, 0.84, 0.58))
	_list.set_item_custom_bg_color(index, Color(0.12, 0.13, 0.14) if model else Color(0.19, 0.17, 0.13))


func _fill_list() -> void:
	_list.clear()
	var query: String = _search.text.strip_edges().to_lower()
	var ids: Array = Audio._events.keys()
	ids.sort_custom(_event_less)
	var category: String = ""
	var model: String = ""
	var first_index: int = -1
	for id: String in ids:
		var event: Dictionary = Audio._events[id]
		var assigned: bool = not (Audio._samples.get(id, []) as Array).is_empty()
		if (_filter.selected == 1 and not assigned) or (_filter.selected == 2 and assigned):
			continue
		if _category.selected > 0 and _category_name(event) != _category.get_item_text(_category.selected):
			continue
		var name: String = _display_name(event)
		if query != "" and query not in (name + " " + id + " " + " ".join(event.get("files", []))).to_lower():
			continue
		var next_category: String = _category_name(event)
		if next_category != category:
			category = next_category
			model = ""
			_group_heading(category)
		var next_model: String = _weapon_name(event)
		if next_model != "" and next_model != model:
			model = next_model
			_group_heading(model, true)
		var index: int = _list.add_item(("        " if model != "" else "    ") + ("● " if assigned else "○ ") + String(event.get("name", id)))
		_list.set_item_metadata(index, id)
		if first_index < 0:
			first_index = index
		if id == _id:
			_list.select(index)
	if _list.get_selected_items().is_empty() and first_index >= 0:
		_list.select(first_index)
	if not _list.get_selected_items().is_empty():
		_select(String(_list.get_item_metadata(_list.get_selected_items()[0])))
	else:
		_id = ""
		_play_button.disabled = true
		_step_controls.hide()
		_title.text = "Ничего не найдено"
		_details.text = "Измените поиск или вкладку."


func _select(id: String) -> void:
	_stop()
	_id = id
	for index: int in range(_list.item_count):
		if String(_list.get_item_metadata(index)) == id:
			_list.select(index)
			_list.force_update_list_size()
			_list.ensure_current_is_visible.call_deferred()
			break
	var event: Dictionary = Audio._events[id]
	_title.text = _display_name(event)
	var bus: StringName = Audio._bus_for(id)
	var bus_label: String = "Интерфейс" if bus == Settings.INTERFACE_BUS else String(Settings.BUSES.get(String(bus), bus))
	_details.text = "Пустое назначение. Добавьте запись в Sonora." if not Audio.has_sound(id) else "%s · вариантов %d" % [bus_label, (Audio._samples[id] as Array).size()]
	_variants.clear()
	for file: String in event.get("files", []):
		_variants.add_item(file.get_file())
		_variants.set_item_metadata(_variants.item_count - 1, file)
	_play_button.disabled = not Audio.has_sound(id)
	_step_controls.visible = id in Audio.STEP_MATERIALS.values()
	if _step_controls.visible:
		_update_step_play_button()
	_updating = true
	_event_level.value = Audio.mix_gain(id)
	_step_base_gain.value = Audio.mix_gain(Audio.STEP_BASE)
	_updating = false
	_select_variant()


func _file() -> String:
	return String(_variants.get_item_metadata(_variants.selected)) if _variants.item_count > 0 else ""


func _select_variant() -> void:
	_stop()
	_updating = true
	_file_level.editable = _file() != ""
	_file_level.value = Audio.mix_gain(_id, _file()) if _file() != "" else 0.0
	_updating = false


func _change_level(value: float, file_level: bool) -> void:
	if _id == "" or (file_level and _file() == ""):
		return
	Audio.set_mix_gain(_id, value, _file() if file_level else "")
	_queue_save()


func _change_step_base_gain(value: float) -> void:
	Audio.set_mix_gain(Audio.STEP_BASE, value)
	_queue_save()


func _update_step_play_button() -> void:
	var mode: int = _step_mode.selected
	_play_button.disabled = not ((mode != 2 and Audio.has_sound(Audio.STEP_BASE)) or (mode != 1 and Audio.has_sound(_id)))


func _step_mode_changed(_index: int) -> void:
	_update_step_play_button()
	if not _step_repeat.is_stopped():
		_play()


func _queue_save() -> void:
	_dirty = true
	_status.text = "Сохраняем…"
	_save_timer.start()


func _save() -> void:
	if not _dirty:
		return
	var error: Error = Audio.save_mix()
	_dirty = error != OK
	_status.text = "Сохранено. Эти уровни уже используются в игре." if error == OK else "Не удалось сохранить: " + error_string(error)


func _reset_levels() -> void:
	_event_level.value = 0.0
	_file_level.value = 0.0


func _play() -> void:
	_stop()
	if _id == "" or _play_button.disabled:
		return
	if _step_controls.visible:
		_play_step_take()
		if _loop.button_pressed:
			_step_repeat.start()
	else:
		_add_preview(_id, _play_position(), _variants.selected, _loop.button_pressed)
	_status.text = "Играет: " + _title.text


func _play_step_take() -> void:
	_players = _players.filter(func(player: Variant) -> bool: return is_instance_valid(player))
	var position: Vector3 = _play_position()
	var base_count: int = (Audio._samples.get(Audio.STEP_BASE, []) as Array).size()
	if _step_mode.selected != 2 and base_count > 0:
		_add_preview(Audio.STEP_BASE, position, maxi(_variants.selected, 0) % base_count, false)
	if _step_mode.selected != 1:
		_add_preview(_id, position, _variants.selected, false)


func _play_position() -> Vector3:
	var angle: float = deg_to_rad(_angle.value)
	var direction: Vector3 = Vector3(sin(angle), 0, -cos(angle))
	var camera: Camera3D = get_viewport().get_camera_3d()
	if camera != null:
		direction = camera.global_basis * direction
	return Audio._listener_pos() + direction * _distance.value


func _add_preview(id: String, pos: Vector3, variant: int, looped: bool) -> void:
	var player: Node = Audio.preview_event(id, pos, variant, looped,
		_sound_path.get_selected_id(), _spectral.button_pressed)
	if player != null:
		_players.append(player)


func _preview_spectral(enabled: bool) -> void:
	for player: Node in _players:
		if is_instance_valid(player) and player is AudioStreamPlayer3D:
			Audio.set_preview_spectral(player as AudioStreamPlayer3D, enabled)


func _stop() -> void:
	_step_repeat.stop()
	for player: Node in _players:
		if is_instance_valid(player):
			player.call("stop")
			player.queue_free()
	_players.clear()


func _close() -> void:
	if _reload_panel and not _reload_panel.can_close():
		return
	_save()
	if _dirty:
		return
	_stop()
	Input.mouse_mode = _mouse_before
	queue_free()


func _exit_tree() -> void:
	_stop()
