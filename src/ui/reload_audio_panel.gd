extends VBoxContainer
## Предпросмотр и сохранение меток из звукового стенда.

const ReloadAudio := preload("res://src/audio/reload_audio.gd")
const AnimationPreview := preload("res://src/ui/reload_animation_preview.gd")
const ROLE_NAMES := ["Обычная", "С пустым магазином", "Быстрая", "Быстрая с пустым магазином"]
const SLOT_NAMES := {"mag_out": "Вынуть магазин", "mag_in": "Вставить магазин", "charge": "Затвор",
	"breech_open": "Открыть", "round_insert": "Вложить патрон", "breech_close": "Закрыть"}
const ROW_COLORS := [Color("#79c5d6"), Color("#a2c884"), Color("#e2ae6c")]
const PREVIEW_SPEEDS := [1.0, 0.5, 0.25]

var _preview: AnimationPreview
var _weapons: OptionButton
var _modes: OptionButton
var _speed: OptionButton
var _transport: Button
var _time_text: Label
var _variants: OptionButton
var _lanes: VBoxContainer
var _wave: Control
var _status: Label
var _fit_button: Button
var _end_button: Button
var _clear_recording: Button
var _enabled: CheckBox
var _picker: FileDialog
var _weapon: String = ""
var _role: String = "reload"
var _marks: Dictionary = {}
var _slots: Array[String] = []
var _sources: Dictionary = {}
var _files: Dictionary = {}
var _waveforms: Dictionary = {}
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
	add_child(options)
	_weapons = OptionButton.new()
	_weapons.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	options.add_child(_weapons)
	_modes = OptionButton.new()
	options.add_child(_modes)
	_weapons.item_selected.connect(_select_weapon)
	_modes.item_selected.connect(_select_mode)
	_speed = OptionButton.new()
	_speed.tooltip_text = "Скорость просмотра"
	for label: String in ["1×", "½×", "¼×"]:
		_speed.add_item(label)
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
	_transport = _button(transport, "▶ Играть", _toggle_playback)
	_button(transport, "■", func() -> void: stop(); _seek(0.0)).tooltip_text = "В начало"
	_button(transport, "‹ Кадр", func() -> void: _step(-1))
	_button(transport, "Кадр ›", func() -> void: _step(1))
	_time_text = Label.new()
	transport.add_child(_time_text)
	var timeline := HBoxContainer.new()
	add_child(timeline)
	_lanes = VBoxContainer.new()
	_lanes.add_theme_constant_override("separation", 0)
	_lanes.custom_minimum_size.x = 190
	timeline.add_child(_lanes)
	_wave = Control.new()
	_wave.custom_minimum_size.y = 130
	_wave.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_wave.draw.connect(_draw_wave)
	_wave.gui_input.connect(_timeline_input)
	timeline.add_child(_wave)
	var source_row := HBoxContainer.new()
	add_child(source_row)
	_variants = OptionButton.new()
	_variants.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_variants.fit_to_longest_item = false
	_variants.item_selected.connect(_select_variant)
	source_row.add_child(_variants)
	_button(source_row, "Выбрать WAV", func() -> void: _picker.popup_centered_ratio(0.7))
	_clear_recording = _button(source_row, "Убрать WAV", _clear_local_recording)
	_clear_recording.tooltip_text = "Вернуться к вариантам записи из Sonora"
	_button(source_row, "Метка на курсор", _mark_cursor)
	_end_button = _button(source_row, "Конец на курсор", _mark_end)
	_fit_button = _button(source_row, "Подогнать затвор", _fit_charge)
	_fit_button.tooltip_text = "Подгоняет запись между двумя метками. Высота сохраняется."
	var save_row := HBoxContainer.new()
	add_child(save_row)
	_enabled = CheckBox.new()
	_enabled.text = "Звук в этом варианте"
	_enabled.toggled.connect(_enable_slot)
	save_row.add_child(_enabled)
	_button(save_row, "Сохранить для игры", _save)
	_button(save_row, "Вернуть сохранённое", func() -> void: _load_mode())
	_status = Label.new()
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	save_row.add_child(_status)
	_picker = FileDialog.new()
	_picker.title = "Запись выбранного действия"
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


func _button(parent: Container, title: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = title
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
		_status.text = "Сохрани изменения или верни сохранённое перед переключением."
	return not _settings_dirty


func _load_mode() -> void:
	stop()
	var spec: Dictionary = WeaponStats.compute({"id": _weapon, "mods": {}, "mag": {"id": WeaponDb.default_mag(_weapon)}})
	_duration = maxf(float(spec.reload_empty if _role.ends_with("empty") else spec.reload), 0.1)
	if _role.begins_with("reload_fast"):
		_duration *= float(Balance.RELOAD_FAST.time_k)
	_marks = ReloadAudio.saved(_weapon, _role)
	if _marks.is_empty():
		_marks = ReloadAudio.defaults(_weapon, _role)
	_slots.assign(_marks.keys())
	_sources.clear()
	_files.clear()
	_waveforms.clear()
	for child: Node in _lanes.get_children():
		_lanes.remove_child(child)
		child.queue_free()
	var header := Label.new()
	header.text = "Действие"
	header.custom_minimum_size.y = 24
	_lanes.add_child(header)
	for slot: String in _slots:
		var event_id: String = _event_id(slot)
		var event: Dictionary = Audio._events.get(event_id, {})
		var title: String = String(event.get("name", slot))
		var lane: Button = _button(_lanes, String(SLOT_NAMES.get(slot, title)), _select_slot.bind(slot))
		lane.custom_minimum_size.y = 35
		lane.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		lane.tooltip_text = title
		lane.clip_text = true
		_set_source(slot, 0)
	_select_slot(_slots[0])
	_settings_dirty = false
	_status.text = "Щелчок по шкале — кадр. Перетащи треугольник, чтобы передвинуть звук."
	_seek(0.0)


func _event_id(slot: String) -> String:
	return Audio.resolve_event(WeaponDb.weapon_sound_kind(_weapon, slot))


func _select_slot(slot: String) -> void:
	_selection = slot
	_variants.clear()
	var id: String = _event_id(slot)
	var event: Dictionary = Audio._events.get(id, {})
	if String((_marks[slot] as Dictionary).get("file", "")) != "":
		_variants.add_item("Локальная запись")
	for file: String in event.get("files", []):
		_variants.add_item(file.get_file())
	if _variants.item_count == 0:
		_variants.add_item("Запись не назначена")
		_variants.disabled = true
	else:
		_variants.disabled = _variants.item_count <= 1
	var selected: int = int((_sources.get(slot, {}) as Dictionary).get("index", 0))
	_variants.select(clampi(selected, 0, _variants.item_count - 1))
	_enabled.set_pressed_no_signal(bool(_marks[slot].get("enabled", true)))
	_clear_recording.visible = (_marks[slot] as Dictionary).has("file")
	_end_button.visible = slot == "charge"
	_fit_button.visible = slot == "charge"
	_fit_button.disabled = slot != "charge" or not _files.has(slot)
	_wave.queue_redraw()


func _select_variant(index: int) -> void:
	stop()
	_set_source(_selection, index)
	_select_slot(_selection)


func _set_source(slot: String, index: int) -> void:
	var mark: Dictionary = _marks[slot]
	var stream: AudioStream = ReloadAudio.recording(mark) if index == 0 else null
	var file: String = String(mark.get("file", "")) if stream else ""
	var id: String = _event_id(slot)
	if not stream:
		var samples: Array = Audio._samples.get(id, [])
		var offset: int = 1 if mark.has("file") else 0
		if not samples.is_empty():
			stream = samples[clampi(index - offset, 0, samples.size() - 1)]
			file = "res://assets/audio/" + String(Audio._stream_files.get(stream.get_instance_id(), ""))
	_sources[slot] = {"stream": stream, "index": index}
	_files.erase(slot)
	if file.get_extension().to_lower() == "wav":
		_files[slot] = file
	_waveforms[slot] = _read_wave(file)


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
	var font: Font = ThemeDB.fallback_font
	_wave.draw_rect(Rect2(Vector2.ZERO, _wave.size), Color("#141a21"))
	for i: int in range(11):
		var x: float = 8.0 + width * float(i) / 10.0
		_wave.draw_line(Vector2(x, 22), Vector2(x, _wave.size.y), Color("#34424e"))
		if i < 10:
			_wave.draw_string(font, Vector2(x + 3, 16), "%.2f" % (_duration * i / 10.0), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("#b4c3ce"))
	for i: int in _slots.size():
		var slot: String = _slots[i]
		var mark: Dictionary = _marks[slot]
		var center: float = 24.0 + (i + 0.5) * 35.0
		var color: Color = ROW_COLORS[i % ROW_COLORS.size()]
		if not bool(mark.get("enabled", true)):
			color = color.darkened(0.6)
		if slot == _selection:
			_wave.draw_rect(Rect2(0, center - 17.5, _wave.size.x, 35.0), Color(0.35, 0.55, 0.66, 0.16))
		var start: float = 8.0 + width * float(mark.at)
		var source: Dictionary = _sources.get(slot, {})
		var stream: AudioStream = source.get("stream") as AudioStream
		var wave: PackedFloat32Array = _waveforms.get(slot, PackedFloat32Array())
		if stream and not wave.is_empty():
			var span: float = stream.get_length() * width / _duration
			for column: int in wave.size():
				var x: float = start + span * column / wave.size()
				if x > _wave.size.x:
					break
				var amplitude: float = wave[column] * 14.0
				_wave.draw_line(Vector2(x, center - amplitude), Vector2(x, center + amplitude), color)
		elif not stream:
			_wave.draw_string(font, Vector2(14, center + 4), "Нет записи", HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color("#8b98a6"))
		if mark.has("end"):
			var finish: float = 8.0 + width * float(mark.end)
			_wave.draw_line(Vector2(start, center + 14), Vector2(finish, center + 14), color, 2)
			_wave.draw_line(Vector2(finish, center - 15), Vector2(finish, center + 15), color, 2)
		_wave.draw_line(Vector2(start, center - 15), Vector2(start, center + 15), color, 2)
		_wave.draw_colored_polygon(PackedVector2Array([Vector2(start - 5, center - 15), Vector2(start + 5, center - 15), Vector2(start, center - 7)]), color)
	var cursor: float = 8.0 + width * _time / _duration
	_wave.draw_line(Vector2(cursor, 20), Vector2(cursor, _wave.size.y), Color("#f7edc6"), 1.5)


func _timeline_input(event: InputEvent) -> void:
	var width: float = maxf(1.0, _wave.size.x - 16.0)
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		if not event.pressed:
			_drag_slot = ""
			return
		stop()
		var point: Vector2 = event.position
		var index: int = floori((point.y - 24.0) / 35.0)
		if index >= 0 and index < _slots.size():
			var slot: String = _slots[index]
			_select_slot(slot)
			var mark: Dictionary = _marks[slot]
			var at: float = 8.0 + width * float(mark.at)
			var end: float = 8.0 + width * float(mark.get("end", -1.0))
			if absf(point.x - at) <= 8.0 or absf(point.x - end) <= 8.0:
				_drag_slot = slot
				_drag_edge = "end" if mark.has("end") and absf(point.x - end) <= 8.0 and (absf(point.x - at) > 8.0 or point.y >= 24.0 + index * 35.0 + 16.0) else "at"
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
	_settings_dirty = true
	_status.text = "Метка %.3f с. Сохрани для игры." % (float(mark[edge]) * _duration)
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
	_settings_dirty = true
	_status.text = "Сохрани для игры."
	_wave.queue_redraw()


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


func _toggle_playback() -> void:
	if _playing:
		stop()
		return
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
		_transport.text = "▶ Играть"


func _play_between(from: float, to: float) -> void:
	for slot: String in _slots:
		var at: float = float(_marks[slot].at) * _duration
		if at > from and at <= to:
			_play_recording(slot, to - at)


func _play_recording(slot: String, offset: float) -> void:
	var stream: AudioStream = _sources[slot].stream
	if not bool(_marks[slot].get("enabled", true)) or stream == null or offset >= stream.get_length():
		return
	var id: String = _event_id(slot)
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.bus = Audio._bus_for(id)
	player.pitch_scale = PREVIEW_SPEEDS[_speed.selected]
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
		_transport.text = "▶ Играть"
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
		_set_source(slot, 0)
	_select_slot(_selection)


func _recording_path() -> String:
	var folder: String = ProjectSettings.globalize_path(ReloadAudio.RECORDINGS)
	if DirAccess.make_dir_recursive_absolute(folder) != OK:
		return ""
	return "%s/%s_%s_%s_%d_%d.wav" % [ReloadAudio.RECORDINGS, _weapon, _role, _selection,
		int(Time.get_unix_time_from_system()), randi()]


func _choose_wav(path: String) -> void:
	stop()
	var wav: AudioStreamWAV = AudioStreamWAV.load_from_file(path)
	if wav == null or wav.get_length() <= 0.0:
		_status.text = "Не удалось открыть WAV."
		return
	var target: String = _recording_path()
	if target == "" or DirAccess.copy_absolute(path, ProjectSettings.globalize_path(target)) != OK:
		_status.text = "Не удалось скопировать запись."
		return
	_assign_recording(target)


func _assign_recording(path: String) -> void:
	_marks[_selection].file = path
	_set_source(_selection, 0)
	_select_slot(_selection)
	_settings_dirty = true
	_status.text = "Запись подставлена. Сохрани для игры."


func _clear_local_recording() -> void:
	stop()
	(_marks[_selection] as Dictionary).erase("file")
	_set_source(_selection, 0)
	_select_slot(_selection)
	_settings_dirty = true
	_status.text = "Выбраны записи из каталога. Сохрани для игры."


func _fit_charge() -> void:
	stop()
	var mark: Dictionary = _marks[_selection]
	var span: float = (float(mark.end) - float(mark.at)) * _duration
	if span < 0.03:
		_status.text = "Разведи начало и конец движения затвора на шкале."
		return
	var stream: AudioStream = _sources[_selection].stream
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
	var target: String = _recording_path()
	if target == "":
		_status.text = "Не удалось создать папку записи."
		return
	var output: Array = []
	var args := PackedStringArray(["-v", "error", "-nostdin", "-i", ProjectSettings.globalize_path(String(_files[_selection])),
		"-af", "atempo=%.6f,apad" % speed, "-t", "%.6f" % span, "-c:a", "pcm_s16le", ProjectSettings.globalize_path(target)])
	if OS.execute(ffmpeg, args, output, true) != 0 or ReloadAudio.recording({"file": target}) == null:
		_status.text = "FFmpeg не смог подогнать запись."
		return
	_assign_recording(target)


func _save() -> void:
	var error: Error = ReloadAudio.save(_weapon, _role, _marks)
	_settings_dirty = error != OK
	_status.text = "Сохранено для рейдов на этом компьютере." if error == OK else "Не удалось сохранить: " + error_string(error)
