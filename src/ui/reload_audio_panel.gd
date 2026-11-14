extends VBoxContainer
## Предпросмотр и сохранение меток из звукового стенда.

const ReloadAudio := preload("res://src/audio/reload_audio.gd")
const AnimationPreview := preload("res://src/ui/reload_animation_preview.gd")
const ROLE_NAMES := ["Обычная", "С пустым магазином", "Быстрая", "Быстрая с пустым магазином"]
const SLOT_NAMES := {"mag_out": "Вынуть магазин", "mag_in": "Вставить магазин", "charge": "Затвор",
	"breech_open": "Открыть", "round_insert": "Вложить патрон", "breech_close": "Закрыть"}
const ROW_COLORS := [Color("#79c5d6"), Color("#a2c884"), Color("#e2ae6c")]
const PREVIEW_SPEEDS := [1.0, 0.5, 0.25]
const RULER_HEIGHT := 28.0

var _preview: AnimationPreview
var _weapons: OptionButton
var _modes: OptionButton
var _copy_sounds: Button
var _speed: OptionButton
var _transport: Button
var _time_text: Label
var _lanes: VBoxContainer
var _wave: Control
var _status: Label
var _action: Label
var _save_button: Button
var _restore_button: Button
var _fit_button: Button
var _end_button: Button
var _clear_recording: Button
var _enabled: CheckBox
var _picker: FileDialog
var _picker_slot: String = ""
var _track_style: StyleBoxFlat
var _selected_style: StyleBoxFlat
var _weapon: String = ""
var _role: String = "reload"
var _marks: Dictionary = {}
var _slots: Array[String] = []
var _tracks: Dictionary = {}
var _selection: String = ""
var _duration: float = 1.0
var _time: float = 0.0
var _playing: bool = false
var _drag_slot: String = ""
var _drag_edge: String = ""
var _players: Array[AudioStreamPlayer] = []
var _settings_dirty: bool = false


func _ready() -> void:
	add_theme_constant_override("separation", 8)
	var options := HBoxContainer.new()
	options.add_theme_constant_override("separation", 12)
	add_child(options)
	options.add_child(_label("Оружие"))
	_weapons = OptionButton.new()
	_weapons.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	options.add_child(_weapons)
	options.add_child(_label("Вариант"))
	_modes = OptionButton.new()
	options.add_child(_modes)
	_copy_sounds = _button(options, "Взять WAV из обычной", _copy_from_normal)
	_copy_sounds.tooltip_text = "Подставить сохранённые WAV из обычной перезарядки в пустые строки. Метки текущего варианта сохраняются."
	_weapons.item_selected.connect(_select_weapon)
	_modes.item_selected.connect(_select_mode)
	_speed = OptionButton.new()
	_speed.tooltip_text = "Скорость просмотра"
	for caption: String in ["1×", "½×", "¼×"]:
		_speed.add_item(caption)
	options.add_child(_speed)
	_speed.item_selected.connect(func(_index: int) -> void: stop())
	var frame := AspectRatioContainer.new()
	frame.ratio = 16.0 / 9.0
	frame.stretch_mode = AspectRatioContainer.STRETCH_FIT
	frame.size_flags_vertical = Control.SIZE_EXPAND_FILL
	frame.custom_minimum_size.y = 224.0
	add_child(frame)
	_preview = AnimationPreview.new()
	frame.add_child(_preview)
	var wide := CheckBox.new()
	wide.text = "Шире кадр"
	wide.toggled.connect(_preview.set_wide)
	options.add_child(wide)
	var transport := HBoxContainer.new()
	add_child(transport)
	_transport = _button(transport, "▶ Вся перезарядка", _play_all)
	_transport.tooltip_text = "Проиграть клип с начала со всеми назначенными звуками"
	_button(transport, "▶ С курсора", _play_from_cursor).tooltip_text = "Начать прослушивание с кадра под курсором"
	_button(transport, "‹ Кадр", _step.bind(-1))
	_button(transport, "Кадр ›", _step.bind(1))
	_time_text = _label("")
	transport.add_child(_time_text)
	var timeline := HBoxContainer.new()
	timeline.add_theme_constant_override("separation", 0)
	add_child(timeline)
	_lanes = VBoxContainer.new()
	_lanes.add_theme_constant_override("separation", 0)
	timeline.add_child(_lanes)
	_wave = Control.new()
	_wave.clip_contents = true
	_wave.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_wave.resized.connect(_wave.queue_redraw)
	_wave.draw.connect(_draw_wave)
	_wave.gui_input.connect(_timeline_input)
	timeline.add_child(_wave)
	_track_style = StyleBoxFlat.new()
	_track_style.bg_color = Color("#1d252e")
	_track_style.content_margin_left = 12
	_track_style.content_margin_right = 12
	_track_style.content_margin_top = 4
	_track_style.content_margin_bottom = 4
	_selected_style = _track_style.duplicate()
	_selected_style.bg_color = Color("#293e4b")
	var adjust := HBoxContainer.new()
	adjust.add_theme_constant_override("separation", 10)
	add_child(adjust)
	_action = _label("")
	adjust.add_child(_action)
	_button(adjust, "Начало на курсор", _mark_cursor).tooltip_text = "Запустить звук на кадре под курсором"
	_end_button = _button(adjust, "Конец на курсор", _mark_end)
	_fit_button = _button(adjust, "Подогнать затвор", _fit_charge)
	_fit_button.tooltip_text = "Подгоняет запись между двумя метками. Высота сохраняется."
	_enabled = CheckBox.new()
	_enabled.text = "Звук включён"
	_enabled.toggled.connect(_enable_slot)
	adjust.add_child(_enabled)
	_clear_recording = _button(adjust, "Убрать свой WAV", _clear_local_recording)
	_clear_recording.tooltip_text = "Использовать назначение Sonora для этого действия"
	var timeline_hint: Label = _label("Перетащи метку на шкале.")
	timeline_hint.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	timeline_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	timeline_hint.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	adjust.add_child(timeline_hint)
	var save_row := HBoxContainer.new()
	save_row.add_theme_constant_override("separation", 10)
	add_child(save_row)
	_status = _label("")
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	save_row.add_child(_status)
	_restore_button = _button(save_row, "Вернуть сохранённое", _load_mode)
	_save_button = _button(save_row, "Сохранить для игры", _save)
	_save_button.tooltip_text = "Сохранить звуки и метки выбранного варианта на этом компьютере"
	_picker = FileDialog.new()
	_picker.transient = true
	_picker.exclusive = true
	_picker.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	_picker.access = FileDialog.ACCESS_FILESYSTEM
	_picker.filters = PackedStringArray(["*.wav ; WAV"])
	_picker.file_selected.connect(_choose_wav)
	add_child(_picker)
	for id: String in WeaponDb.weapon_ids():
		var weapon: Dictionary = WeaponDb.weapon(id)
		if not ViewmodelClips.available(id) and (weapon.get("rig", {}) as Dictionary).is_empty():
			continue
		_weapons.add_item(ItemDb.item_name(id))
		_weapons.set_item_metadata(_weapons.item_count - 1, id)
	if _weapons.item_count > 0:
		_select_weapon(0)


func _label(caption: String) -> Label:
	var label := Label.new()
	label.text = caption
	label.add_theme_font_size_override("font_size", 18)
	return label


func _button(parent: Container, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
	button.custom_minimum_size.y = 34
	button.add_theme_font_size_override("font_size", 18)
	button.pressed.connect(action)
	parent.add_child(button)
	return button


func _select_weapon(index: int) -> void:
	if not _confirm_switch():
		_select_metadata(_weapons, _weapon)
		return
	_weapon = String(_weapons.get_item_metadata(index))
	_preview.select_weapon(_weapon)
	_modes.clear()
	var clips: Dictionary = (WeaponDb.weapon(_weapon).get("viewmodel", {}) as Dictionary).get("clips", {})
	for i: int in ReloadAudio.CLIP_ROLES.size():
		var role: String = ReloadAudio.CLIP_ROLES[i]
		if not clips.is_empty() and not clips.has(role):
			continue
		if clips.is_empty() and i >= 2:
			continue
		_modes.add_item(ROLE_NAMES[i] if _weapon != "signal_launcher" else ["Заряженная", "Пустая"][i])
		_modes.set_item_metadata(_modes.item_count - 1, role)
	_modes.select(0)
	_role = String(_modes.get_item_metadata(0))
	_load_mode()


func _select_mode(index: int) -> void:
	if not _confirm_switch():
		_select_metadata(_modes, _role)
		return
	_role = String(_modes.get_item_metadata(index))
	_load_mode()


func _select_metadata(list: OptionButton, value: String) -> void:
	for i: int in list.item_count:
		if list.get_item_metadata(i) == value:
			list.select(i)
			return


func _confirm_switch() -> bool:
	if _settings_dirty:
		_status.text = "Сохрани изменения для игры или нажми «Вернуть сохранённое»."
	return not _settings_dirty


func _load_mode() -> void:
	stop()
	var spec: Dictionary = WeaponStats.compute({"id": _weapon, "mods": {}, "mag": {"id": WeaponDb.default_mag(_weapon)}})
	_duration = maxf(float(spec.reload_empty if _role.ends_with("empty") else spec.reload), 0.1)
	if _role.begins_with("reload_fast"):
		_duration *= float(Balance.RELOAD_FAST.time_k)
	_marks = ReloadAudio.defaults(_weapon, _role)
	var saved: Dictionary = ReloadAudio.saved(_weapon, _role)
	for slot: String in saved:
		var mark: Dictionary = _marks.get(slot, {})
		if saved[slot] is Dictionary:
			mark.merge(saved[slot], true)
		if mark.has("at"):
			_marks[slot] = mark
	_slots.assign(_marks.keys())
	_tracks.clear()
	for child: Node in _lanes.get_children():
		_lanes.remove_child(child)
		child.queue_free()
	var header: Label = _label("Действие и запись")
	header.custom_minimum_size.y = RULER_HEIGHT
	_lanes.add_child(header)
	for slot: String in _slots:
		_build_track(slot)
		_refresh_track(slot)
	_select_slot(_slots[0])
	_set_dirty(false)
	_update_copy_button()
	_status.text = "Загрузи WAV в нужной строке и прослушай всю перезарядку." if saved.is_empty() else "Настройки этого варианта сохранены для игры."
	_seek(0.0)


func _event_id(slot: String) -> String:
	return Audio.resolve_event(WeaponDb.weapon_sound_kind(_weapon, slot))


func _slot_name(slot: String) -> String:
	return String(SLOT_NAMES.get(slot, Audio._events.get(_event_id(slot), {}).get("name", slot)))


func _build_track(slot: String) -> void:
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 560
	card.resized.connect(_wave.queue_redraw)
	_lanes.add_child(card)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 0)
	card.add_child(column)
	var heading := HBoxContainer.new()
	column.add_child(heading)
	var title := Button.new()
	title.text = _slot_name(slot)
	title.alignment = HORIZONTAL_ALIGNMENT_LEFT
	title.flat = true
	title.add_theme_font_size_override("font_size", 18)
	title.tooltip_text = "Показать кадр начала этого звука"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.pressed.connect(_go_to_mark.bind(slot))
	heading.add_child(title)
	var timing: Label = _label("")
	timing.modulate = ROW_COLORS[(_lanes.get_child_count() - 2) % ROW_COLORS.size()]
	heading.add_child(timing)
	var source_row := HBoxContainer.new()
	source_row.add_theme_constant_override("separation", 8)
	column.add_child(source_row)
	var filename: Label = _label("")
	filename.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filename.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	source_row.add_child(filename)
	var variants := OptionButton.new()
	variants.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	variants.fit_to_longest_item = false
	variants.item_selected.connect(_select_variant.bind(slot))
	source_row.add_child(variants)
	var listen: Button = _button(source_row, "Прослушать", _listen_to_slot.bind(slot))
	listen.tooltip_text = "Проиграть только эту запись"
	var upload: Button = _button(source_row, "Заменить WAV", _open_picker.bind(slot))
	upload.custom_minimum_size.x = upload.get_minimum_size().x
	upload.add_theme_color_override("font_color", Color("#e4f6ff"))
	_tracks[slot] = {"card": card, "timing": timing, "filename": filename, "variants": variants,
		"listen": listen, "upload": upload}


func _go_to_mark(slot: String) -> void:
	stop()
	_select_slot(slot)
	_seek(float(_marks[slot].at) * _duration)


func _select_slot(slot: String) -> void:
	_selection = slot
	for key: String in _slots:
		(_tracks[key].card as PanelContainer).add_theme_stylebox_override("panel", _selected_style if key == slot else _track_style)
	var mark: Dictionary = _marks[slot]
	_action.text = "Метка · %s" % _slot_name(slot)
	_enabled.set_pressed_no_signal(bool(mark.get("enabled", true)))
	_clear_recording.visible = mark.has("file")
	_end_button.visible = mark.has("end")
	_fit_button.visible = mark.has("end")
	_fit_button.disabled = String(_tracks[slot].source.get("path", "")).get_extension().to_lower() != "wav"
	_wave.queue_redraw()


func _select_variant(index: int, slot: String) -> void:
	stop()
	_set_source(slot, index)
	_select_slot(slot)


func _refresh_track(slot: String) -> void:
	var track: Dictionary = _tracks[slot]
	var mark: Dictionary = _marks[slot]
	var sources: Array[Dictionary] = []
	var local_stream: AudioStream = ReloadAudio.recording(mark)
	if local_stream:
		var path: String = String(mark.file)
		var filename: String = String(mark.get("name", ""))
		var caption: String = "Свой WAV" if filename == "" else "Свой WAV · " + filename
		sources.append({"stream": local_stream, "path": path, "caption": caption})
	for stream: AudioStream in Audio._samples.get(_event_id(slot), []):
		var file: String = String(Audio._stream_files.get(stream.get_instance_id(), ""))
		sources.append({"stream": stream, "path": "res://assets/audio/" + file, "caption": "Sonora · " + file.get_file()})
	var variants: OptionButton = track.variants
	variants.clear()
	for source: Dictionary in sources:
		variants.add_item(source.caption)
		variants.get_popup().set_item_tooltip(variants.item_count - 1, source.caption)
	variants.visible = sources.size() > 1
	track.filename.visible = sources.size() <= 1
	track.listen.disabled = sources.is_empty()
	track.upload.text = "Заменить WAV" if local_stream else "Загрузить WAV"
	track.upload.tooltip_text = "Выбрать WAV для «%s»" % _slot_name(slot)
	track.sources = sources
	_set_source(slot, 0)
	_update_timing(slot)


func _set_source(slot: String, index: int) -> void:
	var track: Dictionary = _tracks[slot]
	var sources: Array[Dictionary] = track.sources
	var source: Dictionary = sources[index] if not sources.is_empty() else {}
	track.source = source
	var no_recording: String = "WAV не найден" if _marks[slot].has("file") else "Нет записи"
	var caption: String = String(source.get("caption", no_recording))
	track.filename.text = caption
	track.filename.tooltip_text = String(source.get("path", _marks[slot].get("file", caption)))
	track.filename.modulate = Color.WHITE if not sources.is_empty() else Color("#a6b5c3")
	if not sources.is_empty():
		track.variants.select(index)
	track.variants.tooltip_text = caption + "\nВарианты для прослушивания. В игре звучит свой WAV или набор Sonora."
	track.waveform = _read_wave(String(source.get("path", "")))


func _sounds_to_copy() -> Dictionary:
	var sounds: Dictionary = {}
	if _role == "reload":
		return sounds
	var normal: Dictionary = ReloadAudio.saved(_weapon, "reload")
	for slot: String in _slots:
		if _marks[slot].has("file") or not _tracks[slot].sources.is_empty():
			continue
		var mark: Dictionary = normal.get(slot, {})
		if ReloadAudio.recording(mark):
			sounds[slot] = mark
	return sounds


func _update_copy_button() -> void:
	_copy_sounds.visible = not _sounds_to_copy().is_empty()


func _copy_from_normal() -> void:
	stop()
	var sounds: Dictionary = _sounds_to_copy()
	if sounds.is_empty():
		return
	for slot: String in sounds:
		_marks[slot].file = sounds[slot].file
		_marks[slot].name = sounds[slot].get("name", "")
		_marks[slot].enabled = true
		_refresh_track(slot)
	_select_slot(_selection)
	_set_dirty(true)
	_update_copy_button()
	_status.text = "WAV из обычной перезарядки подставлены. Изменения не сохранены."


func _update_timing(slot: String) -> void:
	var mark: Dictionary = _marks[slot]
	var seconds: String = ("%.2f" % (float(mark.at) * _duration)).replace(".", ",")
	_tracks[slot].timing.text = seconds + " с" if bool(mark.get("enabled", true)) else "Выключен"


func _read_wave(path: String) -> PackedFloat32Array:
	var wave := PackedFloat32Array()
	if path.get_extension().to_lower() != "wav":
		return wave
	var wav: AudioStreamWAV = AudioStreamWAV.load_from_file(path)
	if wav == null or wav.format not in [AudioStreamWAV.FORMAT_8_BITS, AudioStreamWAV.FORMAT_16_BITS]:
		return wave
	var data: PackedByteArray = wav.data
	var stride: int = 2 if wav.format == AudioStreamWAV.FORMAT_16_BITS else 1
	var samples: int = data.size() / stride
	var columns: int = mini(768, samples)
	for column: int in columns:
		var peak: float = 0.0
		var first: int = column * samples / columns
		var last: int = (column + 1) * samples / columns
		for sample: int in range(first, last):
			var index: int = sample * stride
			var value: float = float(data.decode_s16(index)) / 32768.0 if stride == 2 else float(data.decode_s8(index)) / 128.0
			peak = maxf(peak, absf(value))
		wave.append(peak)
	return wave


func _draw_wave() -> void:
	var width: float = maxf(1.0, _wave.size.x - 16.0)
	var ruler_height: float = (_lanes.get_child(0) as Control).size.y if not _slots.is_empty() else RULER_HEIGHT
	var font: Font = ThemeDB.fallback_font
	_wave.draw_rect(Rect2(Vector2.ZERO, _wave.size), Color("#141a21"))
	for i: int in range(11):
		var x: float = 8.0 + width * float(i) / 10.0
		_wave.draw_line(Vector2(x, ruler_height), Vector2(x, _wave.size.y), Color("#34424e"))
		if i < 10:
			_wave.draw_string(font, Vector2(x + 3, 19), "%.2f" % (_duration * i / 10.0), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("#b4c3ce"))
	for i: int in _slots.size():
		var slot: String = _slots[i]
		var mark: Dictionary = _marks[slot]
		var lane: Rect2 = (_tracks[slot].card as Control).get_rect()
		var center: float = lane.get_center().y
		var color: Color = ROW_COLORS[i % ROW_COLORS.size()]
		if not bool(mark.get("enabled", true)):
			color = color.darkened(0.6)
		if slot == _selection:
			_wave.draw_rect(Rect2(0, lane.position.y, _wave.size.x, lane.size.y), Color(0.35, 0.55, 0.66, 0.16))
		_wave.draw_line(Vector2(0, lane.position.y), Vector2(_wave.size.x, lane.position.y), Color("#34424e"))
		var start: float = 8.0 + width * float(mark.at)
		var source: Dictionary = _tracks[slot].source
		var stream: AudioStream = source.get("stream") as AudioStream
		var wave: PackedFloat32Array = _tracks[slot].waveform
		if stream:
			var span: float = stream.get_length() * width / _duration
			_wave.draw_rect(Rect2(start, center - 20, span, 40), Color(color, 0.14))
			for column: int in wave.size():
				var x: float = start + span * column / wave.size()
				if x > _wave.size.x:
					break
				var amplitude: float = wave[column] * 20.0
				_wave.draw_line(Vector2(x, center - amplitude), Vector2(x, center + amplitude), color)
		if mark.has("end"):
			var finish: float = 8.0 + width * float(mark.end)
			_wave.draw_line(Vector2(start, center + 22), Vector2(finish, center + 22), color, 2)
			_wave.draw_line(Vector2(finish, center - 22), Vector2(finish, center + 22), color, 2)
		_wave.draw_line(Vector2(start, center - 22), Vector2(start, center + 22), color, 2)
		_wave.draw_colored_polygon(PackedVector2Array([Vector2(start - 6, center - 22), Vector2(start + 6, center - 22), Vector2(start, center - 13)]), color)
	var cursor: float = 8.0 + width * _time / _duration
	_wave.draw_line(Vector2(cursor, ruler_height - 5), Vector2(cursor, _wave.size.y), Color("#f7edc6"), 1.5)


func _timeline_input(event: InputEvent) -> void:
	var width: float = maxf(1.0, _wave.size.x - 16.0)
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if not event.pressed:
			_drag_slot = ""
			return
		stop()
		var point: Vector2 = event.position
		for slot: String in _slots:
			var lane: Rect2 = (_tracks[slot].card as Control).get_rect()
			if point.y < lane.position.y or point.y >= lane.end.y:
				continue
			_select_slot(slot)
			var mark: Dictionary = _marks[slot]
			var at: float = 8.0 + width * float(mark.at)
			var end: float = 8.0 + width * float(mark.get("end", -1.0))
			var near_start: bool = absf(point.x - at) <= 8.0
			var near_end: bool = mark.has("end") and absf(point.x - end) <= 8.0
			if near_start or near_end:
				_drag_slot = slot
				_drag_edge = "end" if near_end and (not near_start or point.y >= lane.get_center().y) else "at"
			break
		_seek(clampf((point.x - 8.0) / width, 0.0, 1.0) * _duration)
	elif event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_LEFT:
		var fraction: float = clampf((event.position.x - 8.0) / width, 0.0, 1.0)
		if _drag_slot != "":
			_set_mark(_drag_slot, _drag_edge, fraction)
		_seek(fraction * _duration)


func _set_mark(slot: String, edge: String, fraction: float) -> void:
	var mark: Dictionary = _marks[slot]
	mark[edge] = maxf(float(mark.at), fraction) if edge == "end" else fraction
	if edge == "at" and mark.has("end"):
		mark.end = maxf(float(mark.end), fraction)
	_update_timing(slot)
	_set_dirty(true)
	_status.text = "«%s» · метка %.3f с. Изменения не сохранены." % [_slot_name(slot), float(mark[edge]) * _duration]
	_wave.queue_redraw()


func _mark_cursor() -> void:
	stop()
	_set_mark(_selection, "at", _time / _duration)


func _mark_end() -> void:
	stop()
	_set_mark(_selection, "end", _time / _duration)


func _enable_slot(enabled: bool) -> void:
	stop()
	_marks[_selection].enabled = enabled
	_update_timing(_selection)
	_set_dirty(true)
	_status.text = "Изменения не сохранены."
	_wave.queue_redraw()


func _set_dirty(dirty: bool) -> void:
	_settings_dirty = dirty
	_save_button.disabled = not dirty
	_restore_button.disabled = not dirty


func _step(frames: int) -> void:
	stop()
	var count: int = _preview.frame_count(_role, _duration)
	var frame: int = roundi(_time / _duration * count)
	_seek(float(frame + frames) / count * _duration)


func _seek(seconds: float) -> void:
	_time = clampf(seconds, 0.0, _duration)
	_preview.seek_reload(_role, _time / _duration)
	var count: int = _preview.frame_count(_role, _duration)
	_time_text.text = "%.3f / %.3f с  ·  кадр %d / %d" % [_time, _duration, roundi(_time / _duration * count), count]
	_wave.queue_redraw()


func _play_all() -> void:
	if _playing:
		stop()
		return
	_seek(0.0)
	_play_from_cursor()


func _play_from_cursor() -> void:
	stop()
	if is_equal_approx(_time, _duration):
		_seek(0.0)
	_playing = true
	_transport.text = "Ⅱ Пауза"
	for slot: String in _slots:
		var at: float = float(_marks[slot].at) * _duration
		if at <= _time:
			_play_recording(slot, _time - at)


func _process(delta: float) -> void:
	if not _playing:
		return
	var previous: float = _time
	var speed: float = PREVIEW_SPEEDS[_speed.selected]
	_seek(_time + delta * speed)
	_play_between(previous, _time)
	if is_equal_approx(_time, _duration):
		_playing = false
		_transport.text = "▶ Вся перезарядка"


func _play_between(from: float, to: float) -> void:
	for slot: String in _slots:
		var at: float = float(_marks[slot].at) * _duration
		if at > from and at <= to:
			_play_recording(slot, to - at)


func _play_recording(slot: String, offset: float) -> void:
	if not bool(_marks[slot].get("enabled", true)):
		return
	_play_track(slot, offset, PREVIEW_SPEEDS[_speed.selected])


func _listen_to_slot(slot: String) -> void:
	stop()
	_select_slot(slot)
	_play_track(slot, 0.0, 1.0)


func _play_track(slot: String, offset: float, speed: float) -> void:
	var stream: AudioStream = _tracks[slot].source.get("stream") as AudioStream
	if stream == null or offset >= stream.get_length():
		return
	var id: String = _event_id(slot)
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = Audio._bus_for(id)
	player.pitch_scale = speed
	var gain: float = ReloadAudio.gain(slot)
	if not (WeaponDb.weapon(_weapon).get("rig", {}) as Dictionary).is_empty():
		gain = float(Balance.PM_ACTION.sound_db)
	Audio._tag_mix(player, id, stream, float(Audio._kind_spec(id).db) + gain)
	player.finished.connect(player.queue_free)
	add_child(player)
	_players = _players.filter(func(node: AudioStreamPlayer) -> bool: return is_instance_valid(node))
	_players.append(player)
	player.play(maxf(0.0, offset))


func stop() -> void:
	_playing = false
	if _transport:
		_transport.text = "▶ Вся перезарядка"
	for player: AudioStreamPlayer in _players:
		if is_instance_valid(player):
			player.stop()
			player.queue_free()
	_players.clear()


func can_close() -> bool:
	return _confirm_switch()


func refresh() -> void:
	if _weapon == "":
		return
	stop()
	for slot: String in _slots:
		_refresh_track(slot)
	_select_slot(_selection)
	_update_copy_button()


func _recording_path(slot: String) -> String:
	var folder: String = ProjectSettings.globalize_path(ReloadAudio.RECORDINGS)
	if DirAccess.make_dir_recursive_absolute(folder) != OK:
		return ""
	return "%s/%s_%s_%s_%d_%d.wav" % [ReloadAudio.RECORDINGS, _weapon, _role, slot,
		int(Time.get_unix_time_from_system()), randi()]


func _open_picker(slot: String) -> void:
	stop()
	_select_slot(slot)
	_picker_slot = slot
	_picker.title = "WAV для «%s»" % _slot_name(slot)
	_picker.current_file = ""
	_picker.popup_centered_ratio(0.7)


func _choose_wav(path: String) -> void:
	stop()
	var slot: String = _picker_slot
	_picker_slot = ""
	if not _marks.has(slot):
		return
	var wav: AudioStreamWAV = AudioStreamWAV.load_from_file(path)
	if wav == null or wav.get_length() <= 0.0:
		_status.text = "Не удалось открыть WAV для «%s»." % _slot_name(slot)
		return
	var target: String = _recording_path(slot)
	if target == "" or DirAccess.copy_absolute(path, ProjectSettings.globalize_path(target)) != OK:
		_status.text = "Не удалось скопировать запись."
		return
	_marks[slot].enabled = true
	_assign_recording(slot, target, path.get_file())


func _assign_recording(slot: String, path: String, caption: String) -> void:
	_marks[slot].file = path
	_marks[slot].name = caption
	_refresh_track(slot)
	_go_to_mark(slot)
	_set_dirty(true)
	_update_copy_button()
	_status.text = "«%s» · WAV загружен. Изменения не сохранены." % _slot_name(slot)


func _clear_local_recording() -> void:
	stop()
	var mark: Dictionary = _marks[_selection]
	mark.erase("file")
	mark.erase("name")
	_refresh_track(_selection)
	_select_slot(_selection)
	_set_dirty(true)
	_update_copy_button()
	_status.text = "«%s» · свой WAV убран. Изменения не сохранены." % _slot_name(_selection)


func _fit_charge() -> void:
	stop()
	var mark: Dictionary = _marks[_selection]
	var span: float = (float(mark.end) - float(mark.at)) * _duration
	if span < 0.03:
		_status.text = "Разведи начало и конец движения затвора на шкале."
		return
	var source: Dictionary = _tracks[_selection].source
	var stream: AudioStream = source.stream
	var speed: float = stream.get_length() / span
	if speed < 0.5 or speed > 2.0:
		_status.text = "Для этого отрезка нужна скорость вне 0,5–2×. Обрежь запись до самого движения."
		return
	var ffmpeg: String = ProjectSettings.globalize_path("res://tools/sonora_studio/vendor/ffmpeg.exe")
	if not FileAccess.file_exists(ffmpeg):
		ffmpeg = "D:/ПРОГРАММЫ/Sonora Studio/resources/bin/ffmpeg.exe"
	if not FileAccess.file_exists(ffmpeg):
		_status.text = "Для подгонки нужен FFmpeg из Sonora."
		return
	var target: String = _recording_path(_selection)
	if target == "":
		_status.text = "Не удалось создать папку записи."
		return
	var output: Array = []
	var args := PackedStringArray(["-v", "error", "-nostdin", "-i", ProjectSettings.globalize_path(String(source.path)),
		"-af", "atempo=%.6f,apad" % speed, "-t", "%.6f" % span, "-c:a", "pcm_s16le", ProjectSettings.globalize_path(target)])
	if OS.execute(ffmpeg, args, output, true) != 0 or ReloadAudio.recording({"file": target}) == null:
		_status.text = "FFmpeg не смог подогнать запись."
		return
	_assign_recording(_selection, target, String(source.path).get_file())


func _save() -> void:
	var error: Error = ReloadAudio.save(_weapon, _role, _marks)
	_set_dirty(error != OK)
	_status.text = "Звуки варианта «%s» сохранены для игры." % _modes.text if error == OK else "Не удалось сохранить. " + error_string(error)
