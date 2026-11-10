extends DevelopmentLab
## Дорожка переходов и две площадки для сравнения одного покрытия. Запись выбирается по полу под ногами.

const STEP_FILES: String = "user://surface_audio_lab.cfg"
const FORMATS: PackedStringArray = ["*.wav,*.ogg,*.mp3 ; Звуковые файлы"]
const SURFACES: Array[Array] = [
	["Асфальт", "asphalt", Color("#454b50")],
	["Плитка", "tile", Color("#a59073")],
	["Дерево", "wood", Color("#8d6447")],
	["Ковёр", "carpet", Color("#844e51")],
	["Гравий", "gravel", Color("#706658")],
	["Трава", "grass", Color("#566745")],
	["Песок", "sand", Color("#b19a74")],
	["Вода", "water", Color("#38596d")],
	["Стекло", "glass", Color("#668f92")],
	["Грунт", "dirt", Color("#765744")],
	["Бетон", "concrete", Color("#8d8d83")],
	["Листья", "leaves", Color("#82673a")],
	["Щебень", "rubble", Color("#77746e")],
	["Грязь", "mud", Color("#514033")],
	["Мокрый асфальт", "asphalt_wet", Color("#343f4b")],
	["Ткань", "fabric", Color("#8b7e70")],
	["Снег", "snow", Color("#c9d8de")],
	["Лужи", "puddle", Color("#4d666d")],
	["Картон", "cardboard", Color("#ac8760")],
	["Мусор", "trash", Color("#605943")],
	["Пластик", "plastic", Color("#74806e")],
	["Мусорные пакеты", "trash_bags", Color("#3f4542")],
	["Металл", "metal", Color("#607783")],
]
const OUTSIDE: Vector3 = Vector3(0, 0.08, -6)
const INSIDE: Vector3 = Vector3(0, 0.08, 9)
const ROUTE: Vector3 = Vector3(13, 0.08, -6)
const ROUTE_TILE_M: float = 3.0
const ROUTE_WIDTH_M: float = 5.0
const LAYER_START: Vector3 = Vector3(0, 0.08, 20)
const StepLayerPatch := preload("res://src/audio/step_layer_patch.gd")
const MapSamples := preload("res://src/debug/map_surface_samples.gd")
const MapReadout := preload("res://src/debug/surface_map_readout.gd")
const FootstepAudit := preload("res://src/debug/footstep_audit.gd")
const TIMING_DOMAIN: String = "step_timing"
const REVIEW_NOTES: String = "user://footsteps_review.cfg"
const REVIEW_REPORT: String = "user://footsteps_report.md"

var _floors: Array[StaticBody3D] = []
var _surface_index: int = 0
var _tracks: Dictionary = {}
var _names: Dictionary = {}
var _wet_recordings: Array[AudioStream] = []
var _files: ConfigFile = ConfigFile.new()
var _step_labels: Dictionary = {}
var _map_picker: OptionButton
var _map_paths: Array[String] = []
var _map_note: Label
var _map_play: AudioStreamPlayer
var _map_playing: bool = false
var _layer_mix: Dictionary = {}
var _layer_labels: Dictionary = {}
var _map_samples: Array[Dictionary] = []
var _surface_picker: OptionButton
var _timing: Dictionary = {}
var _timing_page: VBoxContainer
var _footsteps: Footsteps
var _last_count: int = 0
var _walking_clock: float = 0.0
var _last_beat: float = -1.0
var _last_interval: float = 0.0
var _review_page: VBoxContainer
var _review_notes: ConfigFile = ConfigFile.new()
var _review_slots: Array[Dictionary] = []
var _review_picker: OptionButton
var _review_note: LineEdit
var _review_summary: Label
var _review_text: TextEdit
var step_files_path: String = STEP_FILES
var review_notes_path: String = REVIEW_NOTES
var review_report_path: String = REVIEW_REPORT


func _ready() -> void:
	leave_overview_to_play = true
	super._ready()
	player.combat_enabled = false
	player.clear_range_weapon()
	_build_track()
	_build_route()
	_build_layer_floor()
	_build_map_samples()
	_files.load(step_files_path)
	_load_tracks()
	panel.tabs.set_tab_hidden(1, true)
	panel.tabs.set_tab_hidden(2, true)
	panel.tabs.set_tab_title(0, "Шаги")
	panel.tabs.add_theme_font_size_override("font_size", 15)
	panel.save_button.hide()
	panel.play_button.text = "Взять управление · F6"
	panel.label(panel.context, "Выбери покрытие и добавь WAV, OGG или MP3. Игра берёт записи с выбранного места на диске.")
	panel.action("Пройти все покрытия →", func() -> void: _move_to(ROUTE + Vector3.RIGHT * 0.4, PI * 0.5, true))
	var labels: Array[String] = []
	for entry: Array in SURFACES:
		labels.append(String(entry[0]))
	_surface_picker = panel.option("Покрытие для одиночной пробы", labels, select_surface)
	panel.action("Загрузить шаги для улицы и комнаты…", func() -> void:
		_audio_dialog(true, _assign_steps.bind(["outdoor", "room"])))
	_add_step_controls("Улица", "outdoor", OUTSIDE)
	_add_step_controls("Комната", "room", INSIDE)
	_build_map_controls()
	_build_layer_controls()
	_build_timing_controls()
	_build_review_controls()
	_build_samples_controls()
	panel.offset_right = 560.0
	($Interface/Hint as Control).offset_left = 580.0
	panel.action("В главное меню", _back)
	($Interface/Hint/Label as Label).text = "F6 — панель / прогулка   ·   F7 — штатные шаги   ·   F8 — обзор\nИди по полосам и смотри, какой тип пола и набор шагов определила игра"
	var readout: PanelContainer = $Interface/Telemetry
	readout.anchor_left = 1.0
	readout.offset_left = -485
	readout.offset_bottom = 201
	select_surface(0)
	if not _map_samples.is_empty():
		_go_to_sample(0, false)


func _build_track() -> void:
	var samples: Node3D = $Samples
	_floors.append(box(samples, "Street", Vector3(0, -0.03, -7), Vector3(10, 0.16, 18), Color.WHITE))
	_floors.append(box(samples, "RoomFloor", Vector3(0, -0.03, 8), Vector3(10, 0.16, 12), Color.WHITE))
	var walls: Color = Color("#555b60")
	box(samples, "Roof", Vector3(0, 3.15, 8), Vector3(10.3, 0.3, 12.3), walls)
	box(samples, "BackWall", Vector3(0, 1.5, 14), Vector3(10.3, 3, 0.25), walls)
	for sign_x: float in [-1.0, 1.0]:
		box(samples, "SideWall", Vector3(5.0 * sign_x, 1.5, 8), Vector3(0.25, 3, 12), walls)
		box(samples, "DoorSide", Vector3(3.0 * sign_x, 1.5, 2), Vector3(4.0, 3, 0.25), walls)
	box(samples, "DoorLintel", Vector3(0, 2.75, 2), Vector3(2, 0.5, 0.25), walls)
	box(samples, "StreetEnd", Vector3(0, 0.3, -16), Vector3(10, 0.6, 0.25), walls)
	var lamp: OmniLight3D = OmniLight3D.new()
	lamp.position = Vector3(0, 2.8, 8)
	lamp.omni_range = 11.0
	lamp.light_energy = 1.4
	lamp.light_color = Color("#ffdcad")
	samples.add_child(lamp)
	text_3d(samples, "КОМНАТА", Vector3(0, 2.7, 1.7))
	text_3d(samples, "УЛИЦА", Vector3(0, 2.1, -13))


func _build_route() -> void:
	var course: Node3D = Node3D.new()
	course.name = "SurfaceRoute"
	add_child(course)
	var center: Vector3 = ROUTE + Vector3.RIGHT * ROUTE_TILE_M * SURFACES.size() * 0.5
	for index: int in range(SURFACES.size()):
		var entry: Array = SURFACES[index]
		var surface: String = String(entry[1])
		var pad: Vector3 = ROUTE + Vector3.RIGHT * ROUTE_TILE_M * (float(index) + 0.5)
		var floor: StaticBody3D = box(course, "Pad_" + surface, Vector3(pad.x, -0.03, pad.z),
			Vector3(ROUTE_TILE_M, 0.16, ROUTE_WIDTH_M), entry[2] as Color, surface)
		if surface in ["water", "puddle", "asphalt_wet", "glass"]:
			var mesh: BoxMesh = (floor.get_child(0) as MeshInstance3D).mesh as BoxMesh
			(mesh.material as StandardMaterial3D).roughness = 0.28
		var sign: Vector3 = pad + Vector3(0, 0.95, 2.15)
		var nameplate: Label3D = text_3d(course, "%02d · %s" % [index + 1, entry[0]], sign)
		nameplate.pixel_size = 0.005
		nameplate.visibility_range_end = 18.0
	var end: Vector3 = ROUTE + Vector3.RIGHT * ROUTE_TILE_M * SURFACES.size()
	box(course, "LadderLanding", end + Vector3(1.5, -0.11, 0), Vector3(3, 0.32, ROUTE_WIDTH_M), Color("#636965"), "metal")
	box(course, "LadderPlatform", end + Vector3(4, 3.03, 0), Vector3(2.8, 0.24, 2.4), Color("#636965"), "metal")
	var ladder: Ladder = (preload("res://scenes/world/ladder.tscn") as PackedScene).instantiate() as Ladder
	ladder.height = 3.1
	ladder.position = end + Vector3(2.55, 0.05, 0)
	ladder.rotation.y = -PI * 0.5
	course.add_child(ladder)
	text_3d(course, "Лестница\n%s — взяться" % PauseMenu.key_name("vault"), end + Vector3(2.65, 2.3, 1.8))
	observer.position = center + Vector3(0, 39, -26)
	observer.look_at(center)


func _build_layer_floor() -> void:
	var floor: StaticBody3D = box($Samples, "LayerTestFloor", LAYER_START + Vector3(0, -0.11, 6),
		Vector3(6, 0.16, 12), Color.WHITE, "tile")
	(floor.get_child(0) as MeshInstance3D).material_override = SectorMaterials.get_material("large_floor_tiles_02")
	for id: String in Balance.STEP_LAYERS:
		var patch: StepLayerPatch = StepLayerPatch.new()
		patch.name = "Layer_" + id
		patch.layer = id
		patch.position = LAYER_START + Vector3(0, -0.03, 8)
		patch.size = Vector2(6, 8)
		$Samples.add_child(patch)
	var glass: GlassPanes = GlassPanes.new()
	$Samples.add_child(glass)
	glass._pile(Transform3D(Basis.IDENTITY, LAYER_START + Vector3.FORWARD * -8.0), Vector2(5.0, 1.0), 0.054, false)
	text_3d($Samples, "ПЛИТКА", LAYER_START + Vector3(1.9, 1.15, 2))
	text_3d($Samples, "ПЛИТКА + СЛОИ", LAYER_START + Vector3(1.9, 1.15, 5.4))


func _build_map_samples() -> void:
	var rows: Dictionary = MapSamples.rows()
	var gallery: Node3D = Node3D.new()
	gallery.name = "MapSamples"
	add_child(gallery)
	var row_index: int = 0
	for map_name: String in rows:
		var index: int = 0
		for entry: Dictionary in rows[map_name]:
			var pos: Vector3 = Vector3(14.0 + float(index) * 4.0, 0.05, 10.0 + float(row_index) * 6.0)
			var surface: String = String(entry.kind)
			var body: StaticBody3D = box(gallery, "Sample_%d" % _map_samples.size(), pos - Vector3.UP * 0.08,
				Vector3(4.0, 0.16, 5.0), Color("#696960"), surface)
			var label: String = "%s · %s" % [map_name, entry.name]
			body.set_meta("sample", label)
			# Уличный шейдер читает размеры отрезка в CUSTOM0. Собираем так же, как на «Проспекте».
			var material: Material = entry.material as Material
			var visual: MeshInstance3D = body.get_child(0) as MeshInstance3D
			visual.material_override = material
			if material is ShaderMaterial and (material as ShaderMaterial).shader.resource_path == "res://src/world/street_paving.gdshader":
				var street: Script = load("res://src/world/street_paving.gd") as Script
				visual.mesh = street.call("surface_mesh", Rect2(-2.0, -2.5, 4.0, 5.0), 0.08, Color(0, 0, 0, 0))
			var sign: Label3D = text_3d(gallery, "%s\n%s" % [entry.name, Audio.step_surface_name(surface)],
				pos + Vector3(0, 0.9, 1.85))
			sign.pixel_size = 0.004
			sign.visibility_range_begin = 2.5
			sign.visibility_range_end = 15.0
			_map_samples.append({"label": label, "kind": surface, "at": pos + Vector3(-1.5, 0.05, 0)})
			index += 1
		row_index += 1


func _build_samples_controls() -> void:
	var page: VBoxContainer = panel._page("Покрытия карт")
	panel.tabs.move_child(page.get_parent(), 0)
	panel.tabs.current_tab = 0
	panel.label(page, "Материалы с карт уложены полосами. Подпись под названием показывает, каким типом пола игра считает образец.")
	var labels: Array[String] = []
	for entry: Dictionary in _map_samples:
		labels.append(String(entry.label))
	var picker: OptionButton = panel.option("Образец", labels, func(index: int) -> void: _go_to_sample(index, false), page)
	picker.fit_to_longest_item = false
	picker.clip_text = true
	panel.action("Встать на образец и пройтись", func() -> void: _go_to_sample(picker.selected, true), page)
	panel.action("Открыть настройки шагов этого типа", func() -> void: _edit_sample_kind(picker.selected), page)
	panel.label(page, "На самой карте можно проверить любое место. F6 вернёт на стенд.")
	for map: Dictionary in Floors.all():
		var path: String = String(map.get("scene", ""))
		if path.is_empty() or not ResourceLoader.exists(path, "PackedScene"):
			continue
		var title: String = String(map.name)
		panel.action("Пройти по карте · " + title, MapReadout.open.bind(path, title), page)
	panel.action("В главное меню", _back, page)


func _go_to_sample(index: int, play: bool) -> void:
	if index >= 0 and index < _map_samples.size():
		_move_to(_map_samples[index].at, PI * 0.5, play)
		rig._look_pitch = -0.25


func _edit_sample_kind(sample: int) -> void:
	if sample < 0 or sample >= _map_samples.size():
		return
	var kind: String = String(_map_samples[sample].kind)
	for index: int in range(SURFACES.size()):
		if String(SURFACES[index][1]) == kind:
			_surface_picker.select(index)
			select_surface(index)
			panel.tabs.current_tab = _surface_picker.get_parent().get_parent().get_index()
			return


func _move_to(destination: Vector3, yaw: float, play: bool) -> void:
	player.position = destination
	player.reset_physics_interpolation()
	player.velocity = Vector3.ZERO
	player._eye_tick_ready = false
	player.face(yaw)
	rig._look_yaw = yaw
	rig._look_pitch = 0.0
	if play:
		if overview:
			toggle_overview()
		set_editing(false)


func _add_step_controls(title: String, place: String, destination: Vector3) -> void:
	panel.label(panel.context, title, 18)
	_step_labels[place] = panel.label(panel.context, "", 14)
	panel.action("Загрузить записи · " + title.to_lower(), func() -> void:
		_audio_dialog(true, _assign_steps.bind([place])))
	panel.action("Штатные записи · " + title.to_lower(), func() -> void: _assign_steps(PackedStringArray(), [place]))
	panel.action("Перейти · " + title.to_lower(), func() -> void:
		_move_to(destination, 0.0 if place == "outdoor" else PI, true))


func _load_tracks() -> void:
	var wet_paths: PackedStringArray = ["res://assets/audio/sonora/step_asphalt_wet_01.wav", "res://assets/audio/sonora/step_asphalt_wet_02.wav"]
	for index: int in range(1, 17):
		wet_paths.append("res://assets/audio/steps/asphalt_wet_%02d.ogg" % index)
	_wet_recordings = _read_steps(wet_paths)
	for entry: Array in SURFACES:
		var surface: String = String(entry[1])
		_names[surface] = String(entry[0])
		var sets: Dictionary = {}
		for place: String in ["outdoor", "room"]:
			var paths: PackedStringArray = _files.get_value(surface, place, PackedStringArray())
			sets[place] = _read_steps(paths) if not paths.is_empty() else _default_steps(surface)
		if surface == "asphalt_wet":
			sets["hook"] = Audio.step_hook("puddle")
		_tracks[surface] = sets
	for id: String in Balance.STEP_LAYERS:
		var key: String = "layer_" + id
		var sets: Dictionary = {}
		for place: String in ["outdoor", "room"]:
			sets[place] = _read_steps(_files.get_value(key, place, PackedStringArray()))
		_tracks[key] = sets


func _default_steps(surface: String) -> Array[AudioStream]:
	if surface == "asphalt_wet":
		return _wet_recordings
	return []


func select_surface(index: int) -> void:
	_surface_index = index
	var surface: String = String(SURFACES[index][1])
	for floor: StaticBody3D in _floors:
		floor.set_meta("surface", surface)
		var mesh: BoxMesh = (floor.get_child(0) as MeshInstance3D).mesh as BoxMesh
		(mesh.material as StandardMaterial3D).albedo_color = SURFACES[index][2] as Color
	for place: String in ["outdoor", "room"]:
		var paths: PackedStringArray = _files.get_value(surface, place, PackedStringArray())
		_step_status(surface, place, (_tracks[surface][place] as Array).size(), paths.size())
	_refresh_preview()


func _read_steps(paths: PackedStringArray) -> Array[AudioStream]:
	var takes: Array[AudioStream] = []
	for path: String in paths:
		var stream: AudioStream = Audio.load_audio_file(path)
		if stream != null:
			takes.append(stream)
	return takes


func _assign_steps(paths: PackedStringArray, places: Array, override: String = "") -> void:
	var takes: Array[AudioStream] = _read_steps(paths)
	if takes.size() != paths.size():
		panel.status.text = "Часть записей не открылась. Выбери исправные WAV, OGG или MP3."
		return
	var next: ConfigFile = ConfigFile.new()
	next.parse(_files.encode_to_text())
	var surface: String = override if override != "" else String(SURFACES[_surface_index][1])
	for place: String in places:
		next.set_value(surface, place, paths)
	var result: Error = next.save(step_files_path)
	if result != OK:
		panel.status.text = "Шаги не сохранены · " + error_string(result)
		return
	_files = next
	for place: String in places:
		_tracks[surface][place] = takes if not paths.is_empty() else _default_steps(surface)
		if override == "":
			_step_status(surface, place, (_tracks[surface][place] as Array).size(), paths.size())
	if override != "":
		_layer_status(override.trim_prefix("layer_"))
	panel.compare.set_pressed_no_signal(false)
	_refresh_preview()


func _step_status(surface: String, place: String, loaded: int, total: int) -> void:
	var label: Label = _step_labels[place]
	label.text = "%d из %d записей загружено" % [loaded, total] if total > 0 else _recording_label(surface, loaded)


func _recording_label(surface: String, count: int) -> String:
	if count > 0:
		return "Загруженные записи · %d" % count
	var hook: String = Audio.step_hook("puddle" if surface == "asphalt_wet" else surface)
	return "Штатные записи игры" if Audio.has_sound(hook) else "Для покрытия пока нет записей"


func _refresh_preview() -> void:
	Audio.set_step_preview({"asphalt_wet": {"hook": Audio.step_hook("puddle")}} if panel.compare.button_pressed else _tracks)
	if not _layer_mix.is_empty():
		LabTuning.preview("step_layers", {} if panel.compare.button_pressed else _layer_mix)
	if not _timing.is_empty():
		LabTuning.preview(TIMING_DOMAIN, {} if panel.compare.button_pressed else _timing)
	panel.status.text = "Штатные шаги · F7" if panel.compare.button_pressed else "Прослушивание на игровых шагах · F6"


func _save() -> bool:
	# Назначения сохраняются сразу после выбора файла.
	return true


func _build_timing_controls() -> void:
	_timing = LabTuning.preset(TIMING_DOMAIN)
	_footsteps = player.get_node("Footsteps") as Footsteps
	_timing_page = panel._page("Темп")
	panel.label(_timing_page, "Интервал задаётся для обычной скорости. При замедлении, в приседе и на разгоне темп следует за движением.")
	panel.action("Проверить шаг и бег на улице", func() -> void: _move_to(OUTSIDE, 0.0, true), _timing_page)
	panel.action("Применять этот темп и панораму в игре", _save_timing, _timing_page)
	var rules: Dictionary = Balance.lab_rules(TIMING_DOMAIN)
	for key: String in ["walk_sec", "run_sec", "start_custom", "start_sec", "pan_pct"]:
		var rule: Array = rules[key]
		if key == "start_custom":
			var toggle: CheckButton = panel.toggle(String(rule[0]), float(_timing[key]) >= 0.5,
				func(enabled: bool) -> void: _change_timing(key, 1.0 if enabled else 0.0), _timing_page)
			toggle.name = key
		else:
			var field: SpinBox = panel.number(String(rule[0]), float(_timing[key]), float(rule[2]), float(rule[3]), float(rule[4]),
				func(value: float) -> void: _change_timing(key, value), _timing_page)
			field.name = key
	panel.label(_timing_page, "0 % — общий источник под игроком. 100 % — 12 см влево или вправо от центра. Для шагов подходят монофайлы без записанного увода в сторону.", 14)
	panel.label(_timing_page, "Подсказка справа показывает интервал по скорости и последний измеренный интервал. F7 сравнивает со штатными настройками.", 14)
	panel.action("В главное меню", _back, _timing_page)


func _change_timing(key: String, value: float) -> void:
	_timing[key] = value
	_last_interval = 0.0
	panel.compare.set_pressed_no_signal(false)
	_refresh_preview()


func _save_timing() -> void:
	var result: Error = LabTuning.save(TIMING_DOMAIN, "Темп и панорама", _timing, true)
	panel.status.text = "Темп и панорама своих шагов сохранены для игры." if result == OK else "Темп не сохранён · " + error_string(result)


func _build_review_controls() -> void:
	_review_notes.load(review_notes_path)
	_review_page = panel._page("Ведомость")
	_review_summary = panel.label(_review_page, "", 16)
	panel.action("Перечитать игровой каталог", func() -> void:
		Audio.reload_events()
		_refresh_review(), _review_page)
	_review_picker = panel.option("Набор для заметки", [], func(_index: int) -> void: _load_review_note(), _review_page)
	_review_note = LineEdit.new()
	_review_note.placeholder_text = "Что нужно записать или заменить"
	_review_note.max_length = 220
	_review_page.add_child(_review_note)
	_review_note.text_submitted.connect(func(_value: String) -> void: _save_review_note())
	panel.action("Сохранить заметку", _save_review_note, _review_page)
	panel.action("Записать отчёт .md", _export_review, _review_page)
	panel.action("Открыть папку отчёта", func() -> void:
		OS.shell_open(ProjectSettings.globalize_path("user://")), _review_page)
	_review_text = TextEdit.new()
	_review_text.editable = false
	_review_text.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	_review_text.custom_minimum_size.y = 360
	_review_text.add_theme_font_size_override("font_size", 14)
	_review_text.add_theme_color_override("font_readonly_color", Color("#dedbd4"))
	_review_page.add_child(_review_text)
	panel.action("В главное меню", _back, _review_page)
	panel.tabs.tab_changed.connect(func(index: int) -> void:
		if index == _review_page.get_parent().get_index() and _review_slots.is_empty():
			_refresh_review())


func _refresh_review() -> void:
	var selected: int = maxi(_review_picker.selected, 0)
	_review_slots = Audio.step_catalog()
	_review_picker.clear()
	for slot: Dictionary in _review_slots:
		_review_picker.add_item(String(slot.name))
	_review_picker.select(mini(selected, _review_slots.size() - 1))
	_load_review_note()
	_render_review()


func _load_review_note() -> void:
	var index: int = _review_picker.selected
	if index >= 0:
		_review_note.text = String(_review_notes.get_value("notes", String(_review_slots[index].hook), ""))


func _save_review_note() -> void:
	var index: int = _review_picker.selected
	if index < 0:
		return
	var next: ConfigFile = ConfigFile.new()
	next.parse(_review_notes.encode_to_text())
	next.set_value("notes", String(_review_slots[index].hook), _review_note.text)
	var result: Error = next.save(review_notes_path)
	if result != OK:
		panel.status.text = "Заметка не сохранена · " + error_string(result)
		return
	_review_notes = next
	_render_review()
	panel.status.text = "Заметка сохранена."


func _render_review() -> void:
	var report: Dictionary = FootstepAudit.scan(_review_slots, _review_notes)
	_review_summary.text = "Игровой каталог · пропусков %d · групп дублей %d" % [report.gaps, report.duplicates]
	_review_text.text = String(report.text)


func _export_review() -> void:
	var file: FileAccess = FileAccess.open(review_report_path, FileAccess.WRITE)
	if file == null:
		panel.status.text = "Отчёт не записан · " + error_string(FileAccess.get_open_error())
		return
	file.store_string(_review_text.text)
	var result: Error = file.get_error()
	file.close()
	panel.status.text = "Записан %s. Его можно открыть из папки отчёта." % review_report_path.get_file() if result == OK else "Ошибка записи отчёта."


func _build_map_controls() -> void:
	var page: VBoxContainer = panel._page("Фон")
	panel.label(page, "Выбери карту и назначь зацикленный фон. Он прозвучит здесь и при входе на карту.", 16)
	var names: Array[String] = ["Убежище"]
	_map_paths.append(Balance.HIDEOUT_SCENE)
	for floor: Dictionary in Floors.all():
		var path: String = String(floor.get("scene", ""))
		if not path.is_empty() and not path in _map_paths and ResourceLoader.exists(path, "PackedScene"):
			names.append(String(floor.get("name", path)))
			_map_paths.append(path)
	for path: String in Audio.local_map_scenes():
		if not path in _map_paths and ResourceLoader.exists(path, "PackedScene"):
			names.append(path.get_file().get_basename())
			_map_paths.append(path)
	_map_picker = panel.option("Карта", names, _select_map, page)
	_map_note = panel.label(page, "", 14)
	panel.action("Выбрать другую сцену карты…", _choose_map_scene, page)
	panel.action("Загрузить фон…", func() -> void: _audio_dialog(false, _assign_map), page)
	panel.action("Слушать фон", func() -> void: _set_map_playing(true), page)
	panel.action("Остановить фон", func() -> void: _set_map_playing(false), page)
	panel.action("Вернуть штатный фон карты", func() -> void: _assign_map(""), page)
	panel.action("В главное меню", _back, page)
	_select_map(0)


func _build_layer_controls() -> void:
	_layer_mix = LabTuning.preset("step_layers")
	var page: VBoxContainer = panel._page("Слои")
	panel.label(page, "Основной шаг всегда звучит по полу. На второй половине дорожки поверх плитки подмешиваются включённые слои.")
	panel.action("Пройти от чистой плитки к смеси →", func() -> void: _move_to(LAYER_START + Vector3.FORWARD * -0.5, 0.0, true), page)
	panel.action("Применять этот микс в игре", _save_layers, page)
	for id: String in Balance.STEP_LAYERS:
		var title: String = String(Balance.STEP_LAYERS[id])
		var key: String = "layer_" + id
		panel.toggle(title, float(_layer_mix[id + "_on"]) > 0.5,
			func(value: bool) -> void: _change_layer(id + "_on", 1.0 if value else 0.0), page)
		panel.number("Громкость слоя, дБ", float(_layer_mix[id + "_db"]), -36.0, 0.0, 1.0,
			func(value: float) -> void: _change_layer(id + "_db", value), page)
		_layer_labels[id] = panel.label(page, "", 14)
		_layer_status(id)
		panel.action("Загрузить записи слоя…", func() -> void:
			_audio_dialog(true, _assign_steps.bind(["outdoor", "room"], key)), page)
		panel.action("Вернуть записи каталога", func() -> void: _assign_steps(PackedStringArray(), ["outdoor", "room"], key), page)
	panel.label(page, "Применение сохраняет включение, громкость и выбранные записи слоёв для игры на этом компьютере.", 14)
	panel.action("В главное меню", _back, page)


func _change_layer(key: String, value: float) -> void:
	_layer_mix[key] = value
	panel.compare.set_pressed_no_signal(false)
	_refresh_preview()


func _save_layers() -> void:
	for id: String in Balance.STEP_LAYERS:
		_layer_mix[id + "_files"] = _files.get_value("layer_" + id, "outdoor", PackedStringArray())
	var result: Error = LabTuning.save("step_layers", "Микс слоёв", _layer_mix, true)
	panel.status.text = "Микс слоёв сохранён для игры." if result == OK else "Микс не сохранён · " + error_string(result)


func _layer_status(id: String) -> void:
	var label: Label = _layer_labels[id]
	var takes: Array = _tracks["layer_" + id].outdoor
	label.text = "Своих записей · %d" % takes.size() if not takes.is_empty() else (
		"Записи каталога" if Audio.has_sound(Audio.step_hook(id)) else "Пока нет записи слоя")


func _select_map(index: int) -> void:
	var path: String = _map_paths[index]
	var source: String = Audio.local_map_ambience(path)
	var assignment: String = "Штатное назначение карты"
	if source != "":
		assignment = "Назначен файл «%s»" % source.get_file() if FileAccess.file_exists(source) else "Файл не найден · " + source.get_file()
	_map_note.text = path + "\n" + assignment
	_set_map_playing(_map_playing)


func _choose_map_scene() -> void:
	var dialog: FileDialog = FileDialog.new()
	dialog.title = "Выбери сцену карты"
	dialog.access = FileDialog.ACCESS_RESOURCES
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dialog.filters = ["*.tscn,*.scn ; Сцены Godot"]
	_open_dialog(dialog)
	dialog.current_dir = "res://scenes/levels"
	dialog.file_selected.connect(func(path: String) -> void:
		var index: int = _map_paths.find(path)
		if index == -1:
			index = _map_paths.size()
			_map_paths.append(path)
			_map_picker.add_item(path.get_file().get_basename())
		_map_picker.select(index)
		_select_map(index))


func _assign_map(path: String) -> void:
	var result: Error = Audio.set_map_ambience(_map_paths[_map_picker.selected], path)
	if result == OK:
		_select_map(_map_picker.selected)
		panel.status.text = "Назначение фона сохранено на этом компьютере."
	else:
		panel.status.text = "Фон не сохранён · " + error_string(result)


func _set_map_playing(enabled: bool) -> void:
	if is_instance_valid(_map_play):
		_map_play.stop()
		_map_play.queue_free()
	_map_playing = enabled
	if enabled:
		_map_play = Audio.play_map_ambience(_map_paths[_map_picker.selected], self)
		panel.status.text = "Фон карты играет." if _map_play else "Для этой карты пока нет доступной записи."


func _audio_dialog(multiple: bool, callback: Callable) -> void:
	var dialog: FileDialog = FileDialog.new()
	dialog.title = "Выбери звуковые файлы" if multiple else "Выбери звуковой файл"
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILES if multiple else FileDialog.FILE_MODE_OPEN_FILE
	dialog.filters = FORMATS
	if multiple:
		dialog.files_selected.connect(callback)
	else:
		dialog.file_selected.connect(callback)
	_open_dialog(dialog)


func _open_dialog(dialog: FileDialog) -> void:
	dialog.file_selected.connect(func(_path: String) -> void: dialog.queue_free())
	dialog.files_selected.connect(func(_paths: PackedStringArray) -> void: dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered_clamped(Vector2i(860, 620))


func _lab_tick(delta: float) -> void:
	_measure_timing(delta)
	if player.on_ladder:
		telemetry.text = "Вертикальная лестница\n" + ("Штатные записи игры" if Audio.has_sound("ladder_step") else "Для лестницы пока нет записей")
		return
	var outdoor: bool = Audio.place_at(player.global_position + Vector3.UP) == "outdoor"
	var hit: Dictionary = Audio.ground_hit(player.global_position)
	var surface: String = Surfaces.kind_at(hit)
	var sets: Dictionary = _tracks.get(surface, {})
	var tracks: Array = sets.get("outdoor" if outdoor else "room", [])
	var place: String = "Маршрут" if player.global_position.x >= ROUTE.x else ("Улица" if outdoor else "Комната")
	var body: Node = hit.get("collider") as Node
	var sample: String = String(body.get_meta("sample", "")) if body else ""
	var loaded: int = 0 if panel.compare.button_pressed else tracks.size()
	if sample == "":
		telemetry.text = "%s   ·   %s\n%s" % [place, String(_names.get(surface, surface)), _recording_label(surface, loaded)]
	else:
		var running: bool = Vector2(player.velocity.x, player.velocity.z).length() > Balance.STEP_RUN_SPEED
		var kind: String = Audio.step_kind_at(player.global_position, surface, running)
		telemetry.text = "%s\nТип · %s\n%s" % [sample, Audio.step_surface_name(surface),
			_recording_label(surface, loaded) if loaded > 0 else Audio.step_event_name(kind)]
	var layers: PackedStringArray = PackedStringArray()
	for node: Node in Audio.step_layers_at(player.global_position):
		var id: String = (node as StepLayerPatch).layer
		if Balance.STEP_LAYERS.has(id) and Balance.lab_number("step_layers", id + "_on") >= 0.5:
			layers.append(String(Balance.STEP_LAYERS[id]))
	if not layers.is_empty():
		telemetry.text += "\nСлои · " + " + ".join(layers)
	if _timing_page and panel.tabs.current_tab == _timing_page.get_parent().get_index():
		if _footsteps.walking():
			var interval: float = _footsteps.interval()
			telemetry.text += "\nТемп · %.2f с / %.1f шага в секунду" % [interval, 1.0 / interval]
		if _last_interval > 0.0:
			telemetry.text += "\nПоследний интервал · %.2f с" % _last_interval


func _measure_timing(delta: float) -> void:
	if not _footsteps:
		return
	if not _footsteps.walking():
		_walking_clock = 0.0
		_last_beat = -1.0
		_last_count = _footsteps.steps_taken
		return
	_walking_clock += delta
	if _footsteps.steps_taken != _last_count:
		if _last_beat >= 0.0:
			_last_interval = _walking_clock - _last_beat
		_last_beat = _walking_clock
		_last_count = _footsteps.steps_taken


func _exit_tree() -> void:
	Audio.set_step_preview({})
	LabTuning.end_preview("step_layers")
	LabTuning.end_preview(TIMING_DOMAIN)
	super._exit_tree()
