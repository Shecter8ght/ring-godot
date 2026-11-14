extends CanvasLayer

signal station_selected(station: int)
signal track_selected(file: String)

var _root: Control
var _station: OptionButton
var _tracks: ItemList
var _status: Label
var _empty: Label
var _play: Button
var _volume: HSlider
var _volume_value: Label


func _ready() -> void:
	layer = 40
	add_to_group("esc_windows")
	_root = Control.new()
	add_child(_root)
	_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_root.hide()
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.45)
	_root.add_child(dim)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var center := CenterContainer.new()
	_root.add_child(center)
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(580, 410)
	var style := UiTheme.face(Color(0.07, 0.065, 0.06, 0.98), Color(UiTheme.C_ACCENT, 0.4), 0)
	style.set_content_margin_all(16)
	panel.add_theme_stylebox_override("panel", style)
	center.add_child(panel)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 10)
	panel.add_child(body)
	var header := HBoxContainer.new()
	body.add_child(header)
	var title := Label.new()
	title.text = "Магнитола"
	title.add_theme_font_size_override("font_size", 24)
	title.add_theme_color_override("font_color", UiTheme.C_ACCENT)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close := Button.new()
	close.text = "Закрыть"
	close.pressed.connect(close_ui)
	header.add_child(close)
	var tuning := HBoxContainer.new()
	body.add_child(tuning)
	var station_label := Label.new()
	station_label.text = "Станция"
	tuning.add_child(station_label)
	_station = OptionButton.new()
	_station.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_station.item_selected.connect(func(index: int) -> void: station_selected.emit(index))
	tuning.add_child(_station)
	var volume_row := HBoxContainer.new()
	volume_row.add_theme_constant_override("separation", 10)
	body.add_child(volume_row)
	var volume_label := Label.new()
	volume_label.text = "Громкость"
	volume_row.add_child(volume_label)
	_volume = HSlider.new()
	_volume.max_value = 1.0
	_volume.step = 0.01
	_volume.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_volume.value_changed.connect(_change_volume)
	volume_row.add_child(_volume)
	_volume_value = Label.new()
	_volume_value.custom_minimum_size.x = 56
	_volume_value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	volume_row.add_child(_volume_value)
	var heading := Label.new()
	heading.text = "Мои треки"
	body.add_child(heading)
	_tracks = ItemList.new()
	_tracks.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tracks.item_selected.connect(func(_index: int) -> void: _play.disabled = false)
	_tracks.item_activated.connect(_play_track)
	body.add_child(_tracks)
	_empty = Label.new()
	_empty.text = "Скопируйте MP3, OGG или WAV в папку radio."
	_empty.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_empty.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	body.add_child(_empty)
	var bottom := HBoxContainer.new()
	body.add_child(bottom)
	_status = Label.new()
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	bottom.add_child(_status)
	_play = Button.new()
	_play.text = "Воспроизвести"
	_play.pressed.connect(func() -> void:
		var selected: PackedInt32Array = _tracks.get_selected_items()
		if not selected.is_empty():
			_play_track(selected[0]))
	bottom.add_child(_play)


func is_open() -> bool:
	return _root.visible


func close_ui() -> void:
	_root.hide()


func open(stations: Array, files: PackedStringArray) -> void:
	_station.clear()
	for station: String in stations:
		_station.add_item(station)
	_tracks.clear()
	for file: String in files:
		_tracks.add_item(file)
	_tracks.visible = not files.is_empty()
	_empty.visible = files.is_empty()
	_play.disabled = true
	_volume.set_value_no_signal(Settings.shelter_radio_volume)
	_volume_value.text = "%d %%" % roundi(_volume.value * 100.0)
	_root.show()
	if _tracks.visible:
		_tracks.grab_focus()


func update_playback(station: int, status: String) -> void:
	_station.select(station)
	_status.text = status if _tracks.item_count > 0 else ""
	_status.tooltip_text = _status.text


func _play_track(index: int) -> void:
	track_selected.emit(_tracks.get_item_text(index))


func _change_volume(level: float) -> void:
	_volume_value.text = "%d %%" % roundi(level * 100.0)
	Settings.set_shelter_radio_volume(level)


func _unhandled_input(event: InputEvent) -> void:
	if is_open() and not event.is_echo() and (event.is_action_pressed("pause") or event.is_action_pressed("ui_cancel")):
		close_ui()
		get_viewport().set_input_as_handled()
