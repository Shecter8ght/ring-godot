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
	Settings.sky_mode = "calc"
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
	(atmosphere.panel.fields.shadow_angle as SpinBox).value = 0.75
	_check("UI changes actual shadow softness", is_equal_approx(sun.light_angular_distance, 0.75))
	(atmosphere.panel.fields.fog_distance as SpinBox).value = 1.5
	_check("UI changes depth fog distance immediately", is_equal_approx(atmosphere.world_environment.environment.fog_depth_end, 1350.0))
	(atmosphere.panel.fields.adapt_scale as SpinBox).value = 0.42
	_check("UI changes actual player eye exposure", is_equal_approx(atmosphere.rig._look._attr.auto_exposure_scale, 0.42))
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
	await _surface_audio()
	await _enemy_lab()
	await _motion_lab()
	await _menu_routes()
	DirAccess.remove_absolute(LabTuning.storage_path)
	DirAccess.remove_absolute("user://development_labs_profile_test.json")
	print("DEVELOPMENT_LABS_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _menu_routes() -> void:
	for title: String in ["Свет и атмосфера", "Попадания и эффекты", "Зрение и слух противников",
			"Поверхности и звуки карт", "Противник", "Камера и движение оружия"]:
		var menu: Control = (load("res://scenes/ui/main_menu.tscn") as PackedScene).instantiate() as Control
		get_tree().root.add_child(menu)
		get_tree().current_scene = menu
		menu.call("_show_labs")
		var side: VBoxContainer = menu.get("_side") as VBoxContainer
		var found: bool = false
		if title == "Свет и атмосфера":
			await _frames(3)
			await _shot("stands_catalog")
		for child: Node in side.find_children("*", "Button", true, false):
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


func _surface_audio() -> void:
	var scene: PackedScene = load("res://scenes/debug/surface_audio_lab.tscn") as PackedScene
	var lab: DevelopmentLab = scene.instantiate() as DevelopmentLab
	var steps_path: String = "user://lab_steps_test.cfg"
	lab.set("step_files_path", steps_path)
	get_tree().root.add_child(lab)
	get_tree().current_scene = lab
	await _frames(6)
	var outside: Vector3 = Vector3(0, 0.08, -6)
	var inside: Vector3 = Vector3(0, 0.08, 9)
	_check("same physical surface in both lanes", Audio._surface_under(outside) == "asphalt" and Audio._surface_under(inside) == "asphalt")
	_check("physics distinguishes street and room", Audio.place_at(outside + Vector3.UP) == "outdoor" and Audio.place_at(inside + Vector3.UP) == "room")
	var map_samples: Array = lab.get("_map_samples")
	var valid: bool = map_samples.size() >= 15
	for sample: Dictionary in map_samples:
		var hit: Dictionary = Audio.ground_hit(sample.at)
		var shape: StaticBody3D = hit.get("collider") as StaticBody3D
		valid = valid and shape != null and shape.has_meta("sample") and Surfaces.kind_at(hit) == sample.kind \
			and (shape.get_child(0) as MeshInstance3D).material_override != null
	_check("map samples use materials and real collision surface IDs", valid)
	await _shot("map_materials")
	var course: Node3D = lab.get_node("SurfaceRoute") as Node3D
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio_surfaces.json")) as Dictionary
	for entry: Dictionary in catalog.footsteps:
		for surface: String in entry.surfaces:
			if surface == "ladder":
				_check("footstep route includes the real ladder", course.get_node_or_null("Ladder") is Ladder)
				continue
			var pad: Node3D = course.get_node_or_null("Pad_" + surface) as Node3D
			_check("footstep route includes " + surface, pad != null and Audio._surface_under(pad.global_position + Vector3.UP * 0.1) == surface)
	_check("wet asphalt uses the existing uploaded tracks", (lab.get("_wet_recordings") as Array).size() >= 16
		and course.has_node("Pad_asphalt_wet"))
	var files: PackedStringArray = ["user://lab_steps_outdoor.wav", "user://lab_steps_room.wav"]
	var recording: AudioStreamWAV = AudioStreamWAV.new()
	recording.format = AudioStreamWAV.FORMAT_16_BITS
	recording.mix_rate = 48000
	for index: int in range(files.size()):
		var samples: PackedByteArray = PackedByteArray()
		samples.resize(96000 + 2000 * index)
		recording.data = samples
		_check("write fixture WAV", recording.save_to_wav(files[index]) == OK)
	lab.call("_assign_steps", PackedStringArray([files[0]]), ["outdoor", "room"])
	lab.call("_assign_steps", PackedStringArray([files[1]]), ["room"])
	var latest: Array[int] = [0]
	var observe: Callable = func(_id: String, hook: String, _pos: Vector3) -> void:
		if hook != "step_concrete":
			return
		var mixed: Array[Node] = get_tree().get_nodes_in_group("sonora_mixed_players")
		var played: AudioStreamPlayer3D = mixed.back() as AudioStreamPlayer3D
		latest[0] = (played.stream as AudioStreamWAV).data.size()
	Audio.event_played.connect(observe)
	lab.set_editing(false)
	for index: int in range(2):
		lab.player.position = outside if index == 0 else inside
		lab.player.reset_physics_interpolation()
		latest[0] = 0
		Input.action_press("move_forward")
		for frame: int in range(60):
			await get_tree().physics_frame
			if latest[0] != 0:
				break
		Input.action_release("move_forward")
		if latest[0] != 96000 + 2000 * index:
			print("step diagnostic: bytes=", latest[0], " position=", lab.player.position, " velocity=", lab.player.velocity,
				" blocked=", lab.player.keys_blocked())
		_check("walking plays the imported recording in zone %d" % index, latest[0] == 96000 + 2000 * index)
	Audio.event_played.disconnect(observe)
	await _surface_layers(lab, files[0])
	await _surface_transition(lab, course, files[1])
	lab.player.position = outside
	lab.rig._look_yaw = 0.0
	lab.rig._look_pitch = 0.0
	lab.set_editing(true)
	await _frames(3)
	await _shot("surface_audio")
	await _surface_ladder(lab, course, files[0])
	lab.set_editing(true)
	var saved_steps: ConfigFile = ConfigFile.new()
	_check("both step assignments persist", saved_steps.load(steps_path) == OK
		and saved_steps.get_value("asphalt", "outdoor", []) == PackedStringArray([files[0]])
		and saved_steps.get_value("asphalt", "room", []) == PackedStringArray([files[1]]))
	var map_path: String = "res://scenes/levels/dorm_study.tscn"
	var old_storage: String = Audio.map_ambience_save_path
	var old_file: String = Audio.local_map_ambience(map_path)
	Audio.map_ambience_save_path = "user://lab_ambient_test.cfg"
	_check("assign ambience to another map", Audio.set_map_ambience(map_path, files[1]) == OK)
	var preview: AudioStreamPlayer = Audio.play_map_ambience(map_path, lab)
	_check("preview uses game bus and loops", preview != null and preview.bus == &"Ambient"
		and (preview.stream as AudioStreamWAV).loop_mode == AudioStreamWAV.LOOP_FORWARD)
	var map_root: Node3D = Node3D.new()
	map_root.scene_file_path = map_path
	add_child(map_root)
	await _frames(3)
	_check("map receives assigned background", is_instance_valid(Audio._map_ambient) and Audio._map_ambient.get_parent() == map_root)
	_check("restore built-in ambience", Audio.set_map_ambience(map_path, old_file) == OK)
	map_root.queue_free()
	lab.queue_free()
	await _frames(6)
	_check("step previews cleared after leaving", Audio._step_preview.is_empty())
	DirAccess.remove_absolute(steps_path)
	DirAccess.remove_absolute(Audio.map_ambience_save_path)
	Audio.map_ambience_save_path = old_storage
	for path: String in files:
		DirAccess.remove_absolute(path)


func _surface_layers(lab: DevelopmentLab, fixture: String) -> void:
	var previous: Dictionary = Audio._preview
	var track: AudioStream = Audio.load_audio_file(fixture)
	Audio.set_preview(previous.merged({"step_stone": [track], "step_glass": [track], "step_grass": [track], "step_trash": [track]}, true))
	var pos: Vector3 = Vector3(0, 0.08, 27)
	lab.call("_move_to", pos, 0.0, false)
	await _frames(3)
	var heard: Array[String] = []
	var observe: Callable = func(_id: String, hook: String, _pos: Vector3) -> void: heard.append(hook)
	Audio.event_played.connect(observe)
	Audio.step(pos, false, false, 0.0, true)
	_check("one step plays tile and all enabled overlays", heard == ["step_stone", "step_glass", "step_grass", "step_trash"])
	heard.clear()
	lab.call("_change_layer", "leaves_on", 0.0)
	Audio.step(pos, false, false, 0.0, true)
	_check("muting a layer preserves the base and other layers", heard == ["step_stone", "step_glass", "step_trash"])
	_check("overlay does not carry through floors", Audio.step_layers_at(pos + Vector3.UP * 3.0).is_empty())
	var panes: GlassPanes = GlassPanes.new()
	lab.add_child(panes)
	var pile: Vector3 = Vector3(1, 0.05, 22)
	panes._pile(Transform3D(Basis.IDENTITY, pile), Vector2(2, 2), pile.y, false)
	heard.clear()
	Audio.step(pile, false, false, 0.0, true)
	_check("glass pile automatically adds a glass layer over tile", heard == ["step_stone", "step_glass"])
	Audio.event_played.disconnect(observe)
	Audio.set_preview(previous)
	panes.queue_free()
	lab.set_editing(true)
	for tab: int in range(lab.panel.tabs.get_tab_count()):
		if lab.panel.tabs.get_tab_title(tab) == "Слои":
			lab.panel.tabs.current_tab = tab
			break
	await _shot("footstep_layers")
	lab.call("_assign_steps", PackedStringArray([fixture]), ["outdoor", "room"], "layer_glass")
	lab.call("_save_layers")
	LabTuning.reload()
	_check("manual layer mix and recording persist", LabTuning.enabled("step_layers")
		and LabTuning.preset("step_layers").glass_files == PackedStringArray([fixture])
		and is_zero_approx(float(LabTuning.preset("step_layers").leaves_on)))


func _surface_transition(lab: DevelopmentLab, course: Node3D, tile_file: String) -> void:
	lab.call("select_surface", 1)
	lab.call("_assign_steps", PackedStringArray([tile_file]), ["outdoor"])
	lab.call("select_surface", 0)
	var asphalt: Node3D = course.get_node("Pad_asphalt") as Node3D
	var start: Vector3 = asphalt.global_position + Vector3(-1.2, 0.12, 0)
	lab.call("_move_to", start, PI * 0.5, false)
	lab.set_editing(true)
	await _frames(3)
	await _shot("surface_route")
	var heard: Array[String] = []
	var observer: Callable = func(hook: String, surface: String, _pos: Vector3) -> void:
		var next: String = surface + "/" + hook
		if heard.is_empty() or heard.back() != next:
			heard.append(next)
	Audio.stepped.connect(observer)
	lab.set_editing(false)
	Input.action_press("move_forward")
	for frame: int in range(220):
		await get_tree().physics_frame
		if "tile/step_stone" in heard:
			break
	Input.action_release("move_forward")
	Audio.stepped.disconnect(observer)
	_check("steps change from asphalt to tile without stopping", heard.size() >= 2
		and heard[0] == "asphalt/step_concrete" and heard[1] == "tile/step_stone")
	var played: Array[Node] = get_tree().get_nodes_in_group("sonora_mixed_players")
	var sound: AudioStreamPlayer3D = played.back() as AudioStreamPlayer3D if not played.is_empty() else null
	_check("tile keeps its own loaded WAV after switching the sample picker",
		sound != null and sound.stream is AudioStreamWAV and (sound.stream as AudioStreamWAV).data.size() == 98000)


func _surface_ladder(lab: DevelopmentLab, course: Node3D, fixture: String) -> void:
	var ladder: Ladder = course.get_node("Ladder") as Ladder
	lab.call("_move_to", ladder.global_position + Vector3(-0.8, 0.04, 0), PI * 0.5, true)
	for frame: int in range(12):
		await get_tree().physics_frame
	lab.player._try_vault()
	_check("the player can grab the route ladder", lab.player.ladder == ladder)
	var previous: Dictionary = Audio._preview
	if not Audio.has_sound("ladder_step"):
		Audio.set_preview(previous.merged({"ladder_step": [Audio.load_audio_file(fixture)]}))
	var heard: Array[String] = []
	var observe: Callable = func(_id: String, hook: String, _pos: Vector3) -> void:
		if hook == "ladder_step":
			heard.append(hook)
	Audio.event_played.connect(observe)
	Input.action_press("move_forward")
	for frame: int in range(120):
		await get_tree().physics_frame
		if not heard.is_empty():
			break
	Input.action_release("move_forward")
	Audio.event_played.disconnect(observe)
	Audio.set_preview(previous)
	_check("climbing plays the assigned ladder step", not heard.is_empty())


func _enemy_lab() -> void:
	await _open("enemy")
	var enemy: Marauder = _lab.get("enemy") as Marauder
	var animator: CharacterAnimator = _lab.get("animator") as CharacterAnimator
	_check("enemy uses the actual character model", animator.has_model())
	_lab.call("_play_clip")
	var clip: AnimationPlayer = _lab.get("clip_player") as AnimationPlayer
	_check("chosen clip plays on the character", is_instance_valid(clip) and clip.is_playing())
	(_lab.panel.fields.clip_speed as SpinBox).value = 0.5
	_check("clip speed changes in place", is_equal_approx(clip.speed_scale, 0.5))
	(_lab.get("_timeline") as HSlider).value = 0.4
	_check("clip seeks to the requested frame", absf(clip.current_animation_position - 0.4) < 0.02)
	_lab.panel.tabs.current_tab = 1
	await _frames(2)
	await _shot("enemy_animation")
	_lab.call("_stop_clip")
	var rounds: int = enemy._mag
	_lab.set("_one_shot", true)
	await get_tree().physics_frame
	await get_tree().physics_frame
	_check("enemy fires a real round", enemy._mag == rounds - 1)
	(_lab.panel.fields.reload_speed as SpinBox).value = 2.0
	enemy._start_reload()
	_check("reload speed changes the real reload", is_equal_approx(enemy._reload_t, float(enemy._spec.reload) * 0.5))
	(_lab.panel.fields.ragdoll_damp as SpinBox).value = 2.0
	(_lab.panel.fields.ragdoll_joints as SpinBox).value = 0.5
	_lab.call("_play_clip")
	_lab.call("_fall")
	await _frames(10)
	var bodies: Array[Node] = enemy.find_children("*", "PhysicalBone3D", true, false)
	_check("fall from clip uses the real ragdoll", not enemy._health.alive and bodies.size() == 14)
	var chest: PhysicalBone3D = enemy.find_child("PB_Spine2", true, false) as PhysicalBone3D
	_check("ragdoll uses adjusted joints and damping", chest != null
		and is_equal_approx(chest.angular_damp, float(Balance.RAGDOLL_DAMP.angular) * 2.0)
		and is_equal_approx(float(chest.get("joint_constraints/swing_span")), 25.0))
	await _shot("enemy_ragdoll")
	_lab.call("_reset_enemy")
	enemy = _lab.get("enemy") as Marauder
	_check("reset spawns a fresh living enemy", enemy._health.alive)
	_lab.set_editing(false)
	# У бедра пуля идёт по наклонённому стволу. Для проверки попадания целимся по оси взгляда.
	_lab.rig.set_process_input(false)
	Input.action_press("aim")
	for frame: int in range(45):
		var direction: Vector3 = enemy.global_position + Vector3.UP * 1.2 - _lab.player.eye_position()
		_lab.rig._look_yaw = atan2(direction.x, direction.z)
		_lab.rig._look_pitch = atan2(direction.y, Vector2(direction.x, direction.z).length())
		await get_tree().physics_frame
	_check("F6 returns from the orbit camera to the shooter", not _lab.overview and _lab.player.is_physics_processing())
	Input.action_press("fire")
	for frame: int in range(45):
		await get_tree().physics_frame
		if enemy._health.last_zone != "":
			break
	Input.action_release("fire")
	Input.action_release("aim")
	_check("player can shoot the enemy in first person", enemy._health.last_zone != "")
	# Как при переходе с экраном загрузки, даём короткой вспышке выстрела закончиться.
	await get_tree().create_timer(0.15).timeout
	_lab.queue_free()
	await _frames(6)


func _motion_lab() -> void:
	await _open("motion")
	var movement: CameraMotion = _lab.rig._motion
	var settings: Dictionary = _lab.panel.fields
	(settings.idle_amp as SpinBox).value = 0.0
	await _frames(4)
	_check("idle control silences weapon breath", movement.weapon_bob.is_zero_approx() and is_zero_approx(movement.idle_sway_scale()))
	(settings.weapon_speed as SpinBox).value = 2.0
	await _frames(2)
	_check("speed control drives the real weapon oscillator", is_equal_approx(movement.weapon_rate, 2.0))
	movement._amp = 1.0
	movement._sprint = 0.0
	movement._weapon(Balance.CAMERA_MOTION, 0.0, 1.0, 0.27)
	var walk: Vector3 = movement.weapon_bob
	(settings.walk_angle as SpinBox).value = 90.0
	movement._read_tuning()
	movement._weapon(Balance.CAMERA_MOTION, 0.0, 1.0, 0.27)
	_check("walk direction rotates the weapon trajectory", movement.weapon_bob.is_equal_approx(walk.rotated(Vector3.BACK, PI * 0.5)))
	movement._sprint = 1.0
	movement._weapon(Balance.CAMERA_MOTION, 0.0, 1.0, 0.27)
	var run: Vector3 = movement.weapon_bob
	(settings.run_angle as SpinBox).value = -90.0
	movement._read_tuning()
	movement._weapon(Balance.CAMERA_MOTION, 0.0, 1.0, 0.27)
	_check("run has an independent direction", movement.weapon_bob.is_equal_approx(run.rotated(Vector3.BACK, -PI * 0.5)))
	(settings.head as SpinBox).value = 0.0
	_lab.set_editing(false)
	for frame: int in range(12):
		await get_tree().physics_frame
	Input.action_press("move_forward")
	for frame: int in range(24):
		await get_tree().physics_frame
	Input.action_release("move_forward")
	_check("head adjustment preserves weapon bob while walking", movement.offset.is_zero_approx() and movement.weapon_bob.length() > 0.001)
	_lab.player._try_jump()
	for frame: int in range(10):
		await get_tree().physics_frame
	_check("jump movement is independent of head bob", _lab.player.airborne and absf(movement.offset.y) > 0.001)
	(settings.jump as SpinBox).value = 0.0
	await _frames(4)
	_check("jump control cancels the air offset", movement.offset.is_zero_approx())
	_lab.set_editing(true)
	await _shot("motion_parameters")
	_lab.queue_free()
	await _frames(6)
	_check("motion draft clears on exit", is_equal_approx(Balance.lab_number("motion", "head"), 1.0))


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
