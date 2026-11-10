class_name DevelopmentLab
extends Node3D
## Общая песочница: настоящий игрок, камера, изолированные черновики и сохранение вариантов.

@export var lab_domain: String = "atmosphere"
@export var lab_title: String = "Стенд"
@export var sector_path: String = "res://data/sectors/zone01_mall.json"

var draft: Dictionary = {}
var editing: bool = true
var overview: bool = false
var dirty: bool = false
var leave_overview_to_play: bool = false
var _domains: Array[String] = []
var _drafts: Dictionary = {}
var _conditions_before: Dictionary = {}
var atmosphere: RaidAtmosphere
var weather: RaidWeather

@onready var player: Player = $Player
@onready var rig: CameraRig = $CameraRig
@onready var panel: DevelopmentLabPanel = $Interface/Panel
@onready var telemetry: Label = $Interface/Telemetry/Label
@onready var observer: Camera3D = $ObserverCamera
@onready var world_environment: WorldEnvironment = $WorldEnvironment


func _ready() -> void:
	add_to_group("esc_windows")
	Net.enter_scene("lab_" + lab_domain.get_slice(":", 0))
	_conditions_before = RaidConditions.current.duplicate(true)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	# Ресурс окружения у каждой запущенной сцены свой.
	world_environment.environment = world_environment.environment.duplicate(true) as Environment
	player._camera_rig = rig
	player.health.invulnerable = true
	player.set_physics_process(false)
	rig.set_target(player)
	rig._compass.visible = false
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 54
	player.set_range_weapon(WeaponDb.bare_weapon("wpn_ar_01", rng, [100, 100]))
	player.carry_low = false
	panel.value_changed.connect(_change)
	panel.save_requested.connect(_save)
	panel.load_requested.connect(_load)
	panel.defaults_requested.connect(_defaults)
	panel.comparison_changed.connect(func(_original: bool) -> void: _refresh_preview())
	panel.play_requested.connect(func() -> void: set_editing(not editing))
	panel.overview_requested.connect(toggle_overview)
	panel.back_requested.connect(_back)
	panel.use_in_game.toggled.connect(func(_enabled: bool) -> void: dirty = true)
	panel.preset_name.text_changed.connect(func(_text: String) -> void: dirty = true)
	set_domain(lab_domain)
	set_editing(true)
	($Interface/Hint/Label as Label).text = "F6 — панель / движение  ·  F7 — исходный вариант  ·  F8 — камера сверху\nCtrl+S — сохранить вариант  ·  Esc — скрыть панель / меню"


func start_atmosphere(hour: float = 16.0) -> void:
	atmosphere = RaidAtmosphere.new()
	atmosphere.name = "Atmosphere"
	add_child(atmosphere)
	atmosphere.apply()
	weather = RaidWeather.new()
	weather.name = "Weather"
	add_child(weather)
	weather.conditions_changed()
	if DayCycle.current:
		DayCycle.current.set_process(false)
		DayCycle.current.set_hour(hour)


func set_weather(index: int) -> void:
	RaidConditions.current["weather"] = ["clear", "overcast", "rain", "fog", "heat"][index]
	if atmosphere:
		atmosphere.apply()
	if weather:
		weather.conditions_changed()
	if DayCycle.current:
		DayCycle.current.set_process(false)
	_settings_changed()


func set_hour(hour: float) -> void:
	if DayCycle.current:
		DayCycle.current.set_hour(hour)
		DayCycle.current.set_process(false)
	if weather:
		weather.conditions_changed()
	_settings_changed()


func set_domain(domain: String) -> void:
	if not draft.is_empty():
		_drafts[lab_domain] = {"values": draft.duplicate(true), "name": panel.preset_name.text,
			"enabled": panel.use_in_game.button_pressed, "dirty": dirty}
	lab_domain = domain
	if not domain in _domains:
		_domains.append(domain)
	var cached: Dictionary = _drafts.get(domain, {})
	draft = (cached.get("values", LabTuning.preset(domain)) as Dictionary).duplicate(true)
	panel.compare.set_pressed_no_signal(false)
	panel.configure(lab_title, domain, draft)
	if not cached.is_empty():
		panel.preset_name.text = String(cached.name)
		panel.use_in_game.set_pressed_no_signal(bool(cached.enabled))
	dirty = bool(cached.get("dirty", false))
	_refresh_preview()
	panel.status.text = "Черновик. Сохранение — отдельный вариант для этого стенда."


func _change(key: String, value: Variant) -> void:
	draft[key] = value
	draft = LabTuning.sanitize(lab_domain, draft)
	panel.compare.set_pressed_no_signal(false)
	dirty = true
	panel.status.text = "Есть несохранённые изменения · Ctrl+S"
	_refresh_preview()


func _refresh_preview() -> void:
	LabTuning.preview(lab_domain, {} if panel.compare.button_pressed else draft)
	_settings_changed()


func _settings_changed() -> void:
	pass


func _save() -> bool:
	var error: Error = LabTuning.save(lab_domain, panel.preset_name.text, draft, panel.use_in_game.button_pressed)
	if error != OK:
		panel.status.text = "Не сохранено: " + error_string(error)
		return false
	dirty = false
	_drafts.erase(lab_domain)
	var name: String = panel.preset_name.text.strip_edges()
	panel.presets.clear()
	for item: Variant in LabTuning.names(lab_domain):
		panel.presets.add_item(String(item))
		if String(item) == name:
			panel.presets.select(panel.presets.item_count - 1)
	panel.status.text = "Сохранено: «%s». %s" % [name, "Применяется в игре." if panel.use_in_game.button_pressed else "Только вариант стенда."]
	return true


func _load(name: String) -> void:
	draft = LabTuning.preset(lab_domain, name)
	panel.configure(lab_title, lab_domain, draft)
	panel.preset_name.text = name
	panel.compare.set_pressed_no_signal(false)
	dirty = false
	_refresh_preview()
	panel.status.text = "Загружен вариант «%s»." % name


func _defaults() -> void:
	draft = LabTuning.defaults(lab_domain)
	var name: String = panel.preset_name.text
	var enabled: bool = panel.use_in_game.button_pressed
	panel.configure(lab_title, lab_domain, draft)
	panel.preset_name.text = name
	panel.use_in_game.set_pressed_no_signal(enabled)
	panel.compare.set_pressed_no_signal(false)
	dirty = true
	_refresh_preview()
	panel.status.text = "Исходные значения в черновике. Для применения сброса сохрани вариант."


func is_open() -> bool:
	return editing or overview


func set_editing(enabled: bool) -> void:
	if leave_overview_to_play and not enabled and editing and overview:
		overview = false
		rig.set_process(true)
		rig._ads_cam.make_current()
	editing = enabled
	panel.visible = enabled
	player.set_physics_process(not enabled and not overview)
	player.velocity = Vector3.ZERO
	var focus: Control = get_viewport().gui_get_focus_owner()
	if focus:
		focus.release_focus()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if is_open() else Input.MOUSE_MODE_CAPTURED


func toggle_overview() -> void:
	overview = not overview
	rig.set_process(not overview)
	if overview:
		observer.make_current()
	else:
		rig._ads_cam.make_current()
	set_editing(editing)


func weapon_selector() -> void:
	var ids: Array[String] = []
	var labels: Array[String] = []
	for id: String in WeaponDb.items():
		if WeaponDb.is_weapon(id):
			ids.append(id)
			labels.append(String((WeaponDb.items()[id] as Dictionary).get("name", id)))
	var selector: OptionButton = panel.option("Оружие", labels, func(index: int) -> void:
		var rng: RandomNumberGenerator = RandomNumberGenerator.new()
		rng.seed = 54
		player.set_range_weapon(WeaponDb.bare_weapon(ids[index], rng, [100, 100]))
		player.carry_low = false)
	selector.select(maxi(0, ids.find(player.weapon_id)))


func box(parent: Node, name: String, position: Vector3, size: Vector3, color: Color, surface: String = "concrete") -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = name
	body.set_meta("surface", surface)
	var visual: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.3 if surface == "metal" else 0.85
	material.metallic = 0.8 if surface == "metal" else 0.0
	mesh.material = material
	visual.mesh = mesh
	body.add_child(visual)
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)
	parent.add_child(body)
	body.position = position
	return body


func text_3d(parent: Node, title: String, position: Vector3) -> Label3D:
	var label: Label3D = Label3D.new()
	label.text = title
	label.position = position
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 48
	label.pixel_size = 0.007
	label.outline_size = 8
	parent.add_child(label)
	return label


func _process(delta: float) -> void:
	# Часы стенда стоят, но свет пересчитывается: загрузившиеся облака и новое место игрока учитываются.
	if atmosphere and DayCycle.current and not DayCycle.current.is_processing():
		DayCycle.current._tick(delta, false)
	if editing:
		player._tick_stance_eye(delta)
	if player.position.y < -4.0:
		player.position = Vector3(0, 0.03, -6)
		player.velocity = Vector3.ZERO
	_lab_tick(delta)


func _lab_tick(_delta: float) -> void:
	pass


func _input(event: InputEvent) -> void:
	if overview and event is InputEventMouseButton and event.is_pressed():
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			observer.fov = clampf(observer.fov + (-4.0 if mouse.button_index == MOUSE_BUTTON_WHEEL_UP else 4.0), 15.0, 100.0)
			get_viewport().set_input_as_handled()
			return
	if PauseMenu.shown or not event is InputEventKey or not event.is_pressed() or event.is_echo():
		return
	var key: InputEventKey = event as InputEventKey
	if event.is_action_pressed("pause"):
		for control: Node in panel.find_children("*", "Control", true, false):
			if control is ColorPickerButton and (control as ColorPickerButton).get_popup().visible:
				return
			if control is OptionButton and (control as OptionButton).get_popup().visible:
				return
		for child: Node in get_children():
			if child is Window and (child as Window).visible:
				return
	var handled: bool = true
	if key.keycode == KEY_F6:
		set_editing(not editing)
	elif key.keycode == KEY_F7:
		panel.compare.button_pressed = not panel.compare.button_pressed
	elif key.keycode == KEY_F8:
		toggle_overview()
	elif key.ctrl_pressed and key.physical_keycode == KEY_S:
		_save()
	elif event.is_action_pressed("pause") and (editing or (leave_overview_to_play and overview)):
		set_editing(not editing)
	else:
		handled = false
	if handled:
		get_viewport().set_input_as_handled()


func _back() -> void:
	var unsaved: bool = dirty
	for domain: String in _drafts:
		if domain != lab_domain:
			unsaved = unsaved or bool((_drafts[domain] as Dictionary).get("dirty", false))
	if unsaved:
		var dialog: ConfirmationDialog = ConfirmationDialog.new()
		dialog.title = "Несохранённый вариант"
		dialog.dialog_text = "Выйти в меню без сохранения изменений?"
		dialog.ok_button_text = "Выйти без сохранения"
		dialog.cancel_button_text = "Остаться"
		dialog.confirmed.connect(func() -> void: Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню"))
		dialog.canceled.connect(dialog.queue_free)
		add_child(dialog)
		dialog.popup_centered()
	else:
		Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню")


func _exit_tree() -> void:
	for domain: String in _domains:
		LabTuning.end_preview(domain)
	if not _conditions_before.is_empty():
		RaidConditions.current = _conditions_before
