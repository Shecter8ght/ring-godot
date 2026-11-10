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
var step_files_path: String = STEP_FILES


func _ready() -> void:
	leave_overview_to_play = true
	super._ready()
	player.combat_enabled = false
	player.clear_range_weapon()
	_build_track()
	_build_route()
	_files.load(step_files_path)
	_load_tracks()
	panel.tabs.set_tab_hidden(1, true)
	panel.tabs.set_tab_hidden(2, true)
	panel.tabs.set_tab_title(0, "Шаги")
	panel.save_button.hide()
	panel.play_button.text = "Взять управление · F6"
	panel.label(panel.context, "Выбери покрытие и добавь WAV, OGG или MP3. Игра берёт записи с выбранного места на диске.")
	panel.action("Пройти все покрытия →", func() -> void: _move_to(ROUTE + Vector3.RIGHT * 0.4, PI * 0.5, true))
	var labels: Array[String] = []
	for entry: Array in SURFACES:
		labels.append(String(entry[0]))
	panel.option("Покрытие для одиночной пробы", labels, select_surface)
	panel.action("Загрузить шаги для улицы и комнаты…", func() -> void:
		_audio_dialog(true, _assign_steps.bind(["outdoor", "room"])))
	_add_step_controls("Улица", "outdoor", OUTSIDE)
	_add_step_controls("Комната", "room", INSIDE)
	_build_map_controls()
	panel.action("В главное меню", _back)
	($Interface/Hint/Label as Label).text = "F6 — панель / прогулка   ·   F7 — штатные шаги   ·   F8 — обзор\nНа маршруте иди вперёд по полосам   ·   Shift — бег"
	var readout: PanelContainer = $Interface/Telemetry
	readout.anchor_left = 1.0
	readout.offset_left = -380
	readout.offset_bottom = 165
	select_surface(0)
	_move_to(ROUTE + Vector3.RIGHT * 0.4, PI * 0.5, false)


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


func _assign_steps(paths: PackedStringArray, places: Array) -> void:
	var takes: Array[AudioStream] = _read_steps(paths)
	if takes.size() != paths.size():
		panel.status.text = "Часть записей не открылась. Выбери исправные WAV, OGG или MP3."
		return
	var next: ConfigFile = ConfigFile.new()
	next.parse(_files.encode_to_text())
	var surface: String = String(SURFACES[_surface_index][1])
	for place: String in places:
		next.set_value(surface, place, paths)
	var result: Error = next.save(step_files_path)
	if result != OK:
		panel.status.text = "Шаги не сохранены · " + error_string(result)
		return
	_files = next
	for place: String in places:
		_tracks[surface][place] = takes if not paths.is_empty() else _default_steps(surface)
		_step_status(surface, place, (_tracks[surface][place] as Array).size(), paths.size())
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
	panel.status.text = "Штатные шаги · F7" if panel.compare.button_pressed else "Прослушивание на игровых шагах · F6"


func _save() -> bool:
	# Назначения сохраняются сразу после выбора файла.
	return true


func _build_map_controls() -> void:
	var page: VBoxContainer = panel._page("Фон карты")
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


func _lab_tick(_delta: float) -> void:
	if player.on_ladder:
		telemetry.text = "Вертикальная лестница\n" + ("Штатные записи игры" if Audio.has_sound("ladder_step") else "Для лестницы пока нет записей")
		return
	var outdoor: bool = Audio.place_at(player.global_position + Vector3.UP) == "outdoor"
	var surface: String = Audio._surface_under(player.global_position)
	var sets: Dictionary = _tracks.get(surface, {})
	var tracks: Array = sets.get("outdoor" if outdoor else "room", [])
	var place: String = "Маршрут" if player.global_position.x >= ROUTE.x else ("Улица" if outdoor else "Комната")
	telemetry.text = "%s   ·   %s\n%s" % [place, String(_names.get(surface, surface)),
		_recording_label(surface, 0 if panel.compare.button_pressed else tracks.size())]


func _exit_tree() -> void:
	Audio.set_step_preview({})
	super._exit_tree()
