extends Node
## Реальные сцены, UI, свет, частицы, лучи и состояния мародёра; отдельный файл настроек.

var _lab: DevelopmentLab
var _checks: int = 0
var _fails: int = 0
var _out: String = ""


func _ready() -> void:
	Engine.max_fps = 90
	Profile.use_file("user://development_labs_profile_test.json", true)
	LabTuning.storage_path = "user://development_labs_test.cfg"
	DirAccess.remove_absolute(LabTuning.storage_path)
	LabTuning.reload()
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("out="):
			_out = argument.substr(4)
	if not _out.is_empty():
		DirAccess.make_dir_recursive_absolute(_out)
	_check("defaults preserve lighting", is_equal_approx(Balance.lab_number("atmosphere", "sun"), 1.0))
	var invalid: Dictionary = LabTuning.sanitize("perception", {"view": INF, "half_angle": 900.0})
	_check("invalid settings bounded", is_equal_approx(float(invalid.view), 1.0) and is_equal_approx(float(invalid.half_angle), 175.0))
	var values: Dictionary = LabTuning.defaults("perception")
	values.view = 1.5
	_check("named preset save", LabTuning.save("perception", "Проверка А", values, false) == OK)
	values.view = 2.0
	LabTuning.save("perception", "Проверка Б", values, true)
	LabTuning.reload()
	_check("named presets survive reload", LabTuning.names("perception").size() == 2 and is_equal_approx(Balance.lab_number("perception", "view"), 2.0))
	LabTuning.save("perception", "Проверка Б", LabTuning.defaults("perception"), false)
	await _frames(1)
	await _open("atmosphere")
	var atmosphere: AtmosphereLab = _lab as AtmosphereLab
	_check("atmosphere uses real day cycle", DayCycle.current != null and RaidWeather.current != null)
	_check("panel blocks player controls", atmosphere.player.ui_blocked() and not atmosphere.player.is_physics_processing())
	var sun: DirectionalLight3D = atmosphere.get_node("Sun") as DirectionalLight3D
	if DisplayServer.get_name() != "headless" and DayCycle.current and DayCycle.current._calc:
		for attempt: int in range(120):
			if AtmosphereSky._noise_ready():
				break
			await _frames(2)
	atmosphere._settings_changed()
	var original: float = sun.light_energy
	(atmosphere.panel.fields.sun as SpinBox).value = 2.0
	_check("UI changes real sunlight", absf(sun.light_energy - original * 2.0) < 0.001)
	var doubled: float = sun.light_energy
	atmosphere._settings_changed()
	_check("lighting does not accumulate", absf(sun.light_energy - doubled) < 0.001)
	atmosphere.panel.compare.button_pressed = true
	_check("light comparison restores default", absf(sun.light_energy - original) < 0.001)
	atmosphere.panel.compare.button_pressed = false
	atmosphere.set_weather(3)
	await _frames(8)
	var fog: float = atmosphere.world_environment.environment.fog_density
	(atmosphere.panel.fields.fog as SpinBox).value = 2.0
	await _frames(5)
	_check("UI changes real weather fog", atmosphere.world_environment.environment.fog_density > fog * 1.8)
	atmosphere.set_weather(0)
	await _shot("atmosphere_day")
	atmosphere.panel.tabs.current_tab = 1
	await _frames(3)
	await _shot("atmosphere_parameters")
	atmosphere.set_hour(1.0)
	await _frames(30)
	_check("night scenario changes actual sun phase", DayCycle.current.sun_elev < 0.0 and String(RaidConditions.current.time) == "night")
	await _shot("atmosphere_night")
	atmosphere.panel.preset_name.text = "Тестовый свет"
	atmosphere.panel.use_in_game.button_pressed = false
	_check("atmosphere UI saves preset", atmosphere._save())
	await _key(KEY_F8)
	_check("overview camera works", atmosphere.overview and get_viewport().get_camera_3d() == atmosphere.observer)
	await _key(KEY_F8)
	await _key(KEY_F6)
	_check("F6 restores normal movement", atmosphere.player.is_physics_processing() and not atmosphere.player.ui_blocked())
	await _key(KEY_F6)
	await _open("impact")
	var impact: ImpactLab = _lab as ImpactLab
	_check("previous scene preview removed", is_equal_approx(Balance.lab_number("atmosphere", "sun"), 1.0))
	(impact.panel.fields.debris_count as SpinBox).value = 2.0
	var config: Dictionary = Balance.lab_impact("concrete")
	_check("UI changes actual effect profile", (config.debris.count as Vector2i).x == (Balance.IMPACT_SURFACES.concrete.debris.count as Vector2i).x * 2)
	impact.hit()
	await _frames(6)
	var burst: ImpactBurst = _find_burst(impact)
	_check("test hit creates real ImpactBurst", burst != null)
	if burst:
		_check("particle counts follow profile", burst.debris.amount >= int((config.debris.count as Vector2i).x))
	await _shot("impact_concrete")
	impact.select_surface(1)
	await _frames(5)
	(impact.panel.fields.sparks_count as SpinBox).value = 0.0
	impact.hit()
	await _frames(5)
	burst = _find_burst(impact)
	_check("sparks can be disabled", not Balance.lab_impact("metal").has("sparks") and burst != null and not burst.sparks.emitting)
	(impact.panel.fields.sparks_count as SpinBox).value = 2.0
	impact.clear_effects()
	await _frames(5)
	impact.hit()
	await _frames(3)
	await _shot("impact_metal")
	impact.panel.tabs.current_tab = 1
	await _frames(3)
	await _shot("impact_parameters")
	impact.select_surface(0)
	_check("material draft survives switching", is_equal_approx((impact.panel.fields.debris_count as SpinBox).value, 2.0))
	impact.select_surface(3)
	await _frames(5)
	impact.hit()
	await _frames(8)
	_check("glass uses real damage and cracks", int(impact.glass.panes[0].hits) > 0)
	await _shot("impact_glass")
	impact.clear_effects()
	await _frames(5)
	_check("clear restores intact glass", int(impact.glass.panes[0].hits) == 0)
	impact.select_surface(0)
	await _frames(5)
	(impact.panel.fields.decal_life as SpinBox).value = 1.0
	impact.hit()
	await _frames(5)
	var decal: Decal = null
	for node: Node in get_tree().get_nodes_in_group("impact_effects"):
		if node is Decal and impact.is_ancestor_of(node):
			decal = node as Decal
	_check("hit creates decal", decal != null)
	await get_tree().create_timer(1.2).timeout
	_check("decal duration applied", not is_instance_valid(decal))
	await _open("perception")
	var perception: PerceptionLab = _lab as PerceptionLab
	await _frames(100)
	_check("real AI acquires visible player", perception.enemy._seen_now and perception.enemy.state == Marauder.State.COMBAT)
	_check("telemetry agrees with vision", bool(perception.diagnose().visible))
	await _shot("perception_visible")
	perception._set_barrier(true)
	await _frames(8)
	perception.reset_observer()
	await _frames(60)
	_check("wall blocks real vision", not bool(perception.diagnose().visible) and not perception.enemy._seen_now)
	await _shot("perception_blocked")
	perception.reset_observer()
	perception.emit_noise("step", 7.0)
	await _frames(4)
	_check("quiet event outside hearing radius ignored", perception.enemy.state == Marauder.State.PATROL)
	(perception.panel.fields.hearing as SpinBox).value = 2.0
	perception.emit_noise("step", 7.0)
	await _frames(4)
	_check("hearing multiplier changes real response", perception.enemy.state == Marauder.State.INVESTIGATE and perception.enemy.last_known.distance_to(perception.player.position) < 0.1)
	await _shot("perception_hearing")
	var noise: Dictionary = {}
	var listener: Callable = func(_position: Vector3, radius: float, kind: String) -> void:
		if kind == "shot":
			noise["radius"] = radius
	NoiseBus.noise.connect(listener)
	perception.emit_shot_noise()
	NoiseBus.noise.disconnect(listener)
	_check("shot test uses actual weapon noise", noise.has("radius") and is_equal_approx(float(noise.radius), float(perception.player.spec().noise_m)))
	perception._set_barrier(false)
	perception.target_angle_control.value = 150.0
	await _frames(60)
	_check("outside cone not detected", not bool(perception.diagnose().visible))
	(perception.panel.fields.half_angle as SpinBox).value = 175.0
	await _frames(90)
	_check("cone slider changes actual AI visibility", bool(perception.diagnose().visible) and perception.enemy._seen_now)
	await _key(KEY_F8)
	await _shot("perception_overview")
	_check("AI overview active", perception.overview)
	await _key(KEY_F7)
	await _frames(5)
	_check("comparison restores original AI cone", is_equal_approx(Balance.lab_number("perception", "half_angle"), Balance.AI_VIEW_HALF_ANGLE_DEG))
	_lab.queue_free()
	await _frames(5)
	_check("AI draft removed on exit", is_equal_approx(Balance.lab_number("perception", "hearing"), 1.0))
	await _menu_routes()
	DirAccess.remove_absolute(LabTuning.storage_path)
	DirAccess.remove_absolute("user://development_labs_profile_test.json")
	print("DEVELOPMENT_LABS_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _menu_routes() -> void:
	for title: String in ["Свет и атмосфера", "Попадания и эффекты", "Зрение и слух противников"]:
		var menu: Control = (load("res://scenes/ui/main_menu.tscn") as PackedScene).instantiate() as Control
		get_tree().root.add_child(menu)
		get_tree().current_scene = menu
		menu.call("_show_labs")
		var side: VBoxContainer = menu.get("_side") as VBoxContainer
		var found: bool = false
		for child: Node in side.get_children():
			if child is Button and (child as Button).text == title:
				(child as Button).pressed.emit()
				found = true
				break
		for frame: int in range(1200):
			await get_tree().process_frame
			if get_tree().current_scene is DevelopmentLab and not Loading.active:
				break
		_check("main menu opens " + title, found and get_tree().current_scene is DevelopmentLab
			and String((get_tree().current_scene as DevelopmentLab).lab_title) == title)
		if get_tree().current_scene:
			get_tree().current_scene.queue_free()
		await _frames(6)


func _open(name: String) -> void:
	if is_instance_valid(_lab):
		_lab.queue_free()
		await _frames(6)
	_lab = (load("res://scenes/debug/%s_lab.tscn" % name) as PackedScene).instantiate() as DevelopmentLab
	get_tree().root.add_child(_lab)
	get_tree().current_scene = _lab
	await _frames(45)


func _find_burst(parent: Node) -> ImpactBurst:
	for node: Node in get_tree().get_nodes_in_group("impact_effects"):
		if node is ImpactBurst and parent.is_ancestor_of(node):
			return node as ImpactBurst
	return null


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame


func _key(code: Key) -> void:
	var event: InputEventKey = InputEventKey.new()
	event.keycode = code
	event.pressed = true
	Input.parse_input_event(event)
	await _frames(2)
	event = InputEventKey.new()
	event.keycode = code
	Input.parse_input_event(event)
	await _frames(2)


func _shot(name: String) -> void:
	if _out.is_empty() or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	_check("screenshot " + name, get_viewport().get_texture().get_image().save_png(_out.path_join(name + ".png")) == OK)


func _check(label: String, condition: bool) -> void:
	_checks += 1
	if not condition:
		_fails += 1
	print("PASS " if condition else "FAIL ", label)
