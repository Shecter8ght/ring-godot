extends RefCounted
## Снимки 203 в Forward+ с игровыми руками. Положения и экспозиция постоянны.

const PISTOL := "wpn_hg_02"
const VIEWS := [
	["01_door_tv", 0, Vector3(.88, 1.65, 5.81), 30.0, -3.4],
	["02_board_morning", 0, Vector3(-2.38, 1.57, 6.40), 291.0, -2.4],
	["03_cabinet_door", 0, Vector3(-2.74, 1.53, 1.93), 45.0, -2.0],
	["04_entry_noon", 1, Vector3(-1.54, 1.64, 1.30), 124.0, -4.7],
	["05_table_side", 1, Vector3(-2.29, 1.27, 4.76), 66.0, -4.0],
	["06_seat", 1, Vector3(-1.38, 1.14, 5.50), 84.0, -64.0],
	["07_wall_tv", 1, Vector3(4.21, 1.68, 5.26), 77.0, -1.0],
	["08_table_board", 1, Vector3(2.55, 1.55, 4.22), 260.0, -9.5],
]
const DETAILS := [
	["09_carpet", 1, Vector3(-2.6, 1.12, 6.8), Vector3(-2.2, 0, 6.02), 47.0],
	["10_backrest", 1, Vector3(-2.12, 1.16, 3.24), Vector3(-1.08, .72, 3.55), 43.0],
	["11_wood", 1, Vector3(-2.22, 1.35, 4.21), Vector3(-.72, .78, 4.63), 41.0],
	["12_carafe", 1, Vector3(.67, 1.22, 4.75), Vector3(.12, .92, 4.13), 40.0],
	["13_ceiling", 1, Vector3(-2.64, 1.66, 1.64), Vector3(.78, 3.15, 5.99), 50.0],
	["14_glazing", 1, Vector3(-1.30, 1.70, 6.15), Vector3(1.48, 1.83, 7.77), 49.0],
	["16_night_lantern", 6, Vector3(-1.36, 1.53, 3.20), Vector3(.58, .91, 4.86), 43.0],
	["17_window_morning", 0, Vector3(-3.46, 1.58, .80), Vector3(.04, 1.33, 4.49), 49.0],
	["18_window_noon", 1, Vector3(-3.46, 1.58, .80), Vector3(.04, 1.33, 4.49), 49.0],
	["19_window_sunset", 3, Vector3(-3.46, 1.58, .80), Vector3(.04, 1.33, 4.49), 49.0],
	["20_blinds_noon", 1, Vector3(3.75, 1.65, 3.07), Vector3(2.9, .08, 4.65), 43.0],
]
const TOWARD_WINDOWS := ["15_fps_windows", 1, Vector3(-2.22, 1.64, 5.52), 173.0, -7.0]
const MOTION_START := Vector3(-1.54, .018, 1.3)
const MOTION_END := Vector3(-3.18, .018, 2.70)
const SWITCH_CYCLES := 3

var _scene: Node3D
var _rig: CameraRig
var _player: Player
var _light: Node3D
var _viewport: Viewport
var _path: String
var _report := {}
var _error := false


func run(scene: Node3D, rig: CameraRig, player: Player, path: String, args: PackedStringArray) -> void:
	_scene = scene
	_rig = rig
	_player = player
	_light = scene.get_node("Daylight")
	_viewport = scene.get_viewport()
	_path = path
	_light.running = false
	_light.camera_attributes.auto_exposure_enabled = false
	_light.camera_attributes.exposure_multiplier = .60
	Settings.fov_h = 105.0
	scene.get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	scene.get_window().size = Vector2i(1920, 1080)
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	Engine.max_fps = 60
	var viewport_rid := _viewport.get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(viewport_rid, true)
	_report["gpu"] = RenderingServer.get_video_adapter_name()
	_report["renderer"] = RenderingServer.get_current_rendering_method()
	_report["frame_limit"] = Engine.max_fps
	_report["exposure"] = _light.camera_attributes.exposure_multiplier
	_report["fov"] = Settings.fps_fov_v()
	_report["quality"] = Settings.quality
	_equip()
	_scene.get_node("OfficeDoor203").toggle(Vector3(0.0, 0.0, -1.0))
	await _wait(1.3)
	_report["environment"] = _render_state()
	if args.has("--quality-ab"):
		await _compare_passes()
	elif args.has("--quality-views"):
		await _capture_views()
	elif args.has("--quality-details"):
		await _capture_details()
	else:
		await _capture_views()
		await _capture_details()
		await _capture_weather()
	var report_name := "details.json" if args.has("--quality-details") else "quality.json"
	var file := FileAccess.open(path.path_join(report_name), FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(_report, "  "))
	scene.get_tree().quit(1 if _error or file == null else 0)


func _equip() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 203
	var entry := WeaponDb.bare_weapon(PISTOL, rng, [100, 100])
	_player.loadout_mode = true
	_player.cancel_weapon_action()
	_player.inventory.equipment = {"sidearm": entry}
	_player.weapon_slot = ""
	_player._ws.clear()
	_player._switch("sidearm", false)
	_player.carry_low = false
	_player.raise_weapon()


func _wait(seconds: float) -> void:
	await _scene.get_tree().create_timer(seconds).timeout


func _pose(view: Array) -> void:
	var eye: Vector3 = view[2]
	_rig.set_process(true)
	_player.global_position = Vector3(eye.x, .018, eye.z)
	_player.velocity = Vector3.ZERO
	_player.reset_physics_interpolation()
	_rig._look_yaw = PI - deg_to_rad(view[3])
	_rig._look_pitch = deg_to_rad(view[4])


func _lock_camera(view: Array) -> void:
	await RenderingServer.frame_post_draw
	var camera := _viewport.get_camera_3d()
	_rig.set_process(false)
	camera.global_transform = Transform3D(
		Basis.from_euler(Vector3(deg_to_rad(view[4]), -deg_to_rad(view[3]), 0.0)), view[2])


func _set_preset(index: int) -> void:
	_light.set_preset(index)


func _save(id: String) -> void:
	await RenderingServer.frame_post_draw
	var image := _viewport.get_texture().get_image()
	var correct_size := image.get_size() == Vector2i(1920, 1080)
	var result := image.save_png(_path.path_join(id + ".png"))
	_error = _error or not correct_size or result != OK
	print("203 quality ", id, " ", image.get_size(), " save=", result)


func _render_state() -> Dictionary:
	var environment: Environment = _light.environment
	return {"sdfgi": environment.sdfgi_enabled, "bounce_feedback": environment.sdfgi_bounce_feedback,
		"ssr": environment.ssr_enabled, "ssil": environment.ssil_enabled, "ssao": environment.ssao_enabled,
		"taa": _viewport.use_taa, "msaa": _viewport.msaa_3d,
		"viewmodel_fill": _rig.get_node("AdsCamera/ViewmodelFill").visible}


func _memory() -> Dictionary:
	const MIB := 1024.0 * 1024.0
	return {
		"static_mib": snappedf(Performance.get_monitor(Performance.MEMORY_STATIC) / MIB, .1),
		"video_mib": snappedf(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / MIB, .1),
		"texture_mib": snappedf(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED) / MIB, .1),
		"resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
		"nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
	}


func _measure() -> Dictionary:
	var frames := PackedFloat32Array()
	var gpu := PackedFloat32Array()
	var cpu := PackedFloat32Array()
	var rid := _viewport.get_viewport_rid()
	var previous := Time.get_ticks_usec()
	for frame in range(72):
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		frames.append((now - previous) / 1000.0)
		previous = now
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(rid))
		cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(rid))
	frames.sort()
	gpu.sort()
	cpu.sort()
	return {"fps": snappedf(1000.0 / frames[36], .1), "frame_p50_ms": snappedf(frames[36], .01),
		"frame_p95_ms": snappedf(frames[68], .01), "gpu_p50_ms": snappedf(gpu[36], .01),
		"gpu_p95_ms": snappedf(gpu[68], .01), "cpu_p95_ms": snappedf(cpu[68], .01),
		"memory": _memory()}


func _capture_views() -> void:
	var photos := {}
	var requested := OS.get_environment("BC5_MEETING_ONLY").split(",", false)
	for view: Array in VIEWS + [TOWARD_WINDOWS]:
		if not requested.is_empty() and not requested.has(view[0]):
			continue
		_pose(view)
		_set_preset(view[1])
		await _wait(.4)
		await _lock_camera(view)
		await _wait(1.2)
		await _save(view[0])
		var camera := _viewport.get_camera_3d()
		photos[view[0]] = {"position": str(camera.global_position), "basis": str(camera.global_basis),
			"fov": camera.fov, "sun": _light.sun.light_energy}
	_report["cameras"] = photos


func _capture_details() -> void:
	var gameplay_camera := _viewport.get_camera_3d()
	var requested := OS.get_environment("BC5_MEETING_ONLY").split(",", false)
	var detail_camera := Camera3D.new()
	detail_camera.near = .032
	detail_camera.attributes = _light.camera_attributes
	detail_camera.cull_mask = gameplay_camera.cull_mask & ~2
	_scene.add_child(detail_camera)
	_rig.set_process(false)
	_set_preset(1)
	for detail: Array in DETAILS:
		if not requested.is_empty() and not requested.has(detail[0]):
			continue
		_set_preset(detail[1])
		detail_camera.global_position = detail[2]
		detail_camera.look_at(detail[3])
		detail_camera.fov = detail[4]
		detail_camera.make_current()
		await _wait(.5)
		await _save(detail[0])
	gameplay_camera.make_current()
	_rig.set_process(true)
	detail_camera.queue_free()


func _capture_weather() -> void:
	var conditions := []
	_pose(VIEWS[3])
	await _wait(.4)
	await _lock_camera(VIEWS[3])
	for i in _light.PRESETS.size():
		var preset: Array = _light.PRESETS[i]
		_set_preset(i)
		await _wait(2.6)
		var frame := await _measure()
		frame["id"] = preset[0]
		frame["sun"] = _light.sun.light_energy
		frame["sun_basis"] = str(_light.sun.global_basis.z)
		frame["lantern_energy"] = _light.lantern_light.light_energy
		conditions.append(frame)
		await _save("weather_" + preset[0])
	_report["weather"] = conditions
	var resources := []
	for cycle in SWITCH_CYCLES:
		for i in _light.PRESETS.size():
			_set_preset(i)
			await _wait(.14)
		await _wait(.8)
		resources.append(_memory())
	_report["cycles"] = resources
	# Изменение положения и курса на одном отрезке даёт замер с обновлением видимой области.
	_set_preset(1)
	_pose(VIEWS[3])
	await _wait(1.8)
	var elapsed := PackedFloat32Array()
	var gpu := PackedFloat32Array()
	var rid := _viewport.get_viewport_rid()
	var previous := Time.get_ticks_usec()
	for frame in range(150):
		var k := float(frame) / 149.0
		_player.global_position = MOTION_START.lerp(MOTION_END, k)
		_rig._look_yaw = PI - deg_to_rad(lerpf(124.0, 45.0, k))
		await RenderingServer.frame_post_draw
		var now := Time.get_ticks_usec()
		elapsed.append((now - previous) / 1000.0)
		previous = now
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(rid))
		if frame == 50 or frame == 100:
			await _save("motion_%03d" % frame)
			previous = Time.get_ticks_usec()
	elapsed.sort()
	gpu.sort()
	_report["motion"] = {"frame_p95_ms": snappedf(elapsed[142], .01), "gpu_p95_ms": snappedf(gpu[142], .01)}


func _compare_passes() -> void:
	var env: Environment = _light.environment
	var apertures: Array[AreaLight3D] = _light.sky_apertures
	var aperture: AreaLight3D = apertures[0]
	var sun: DirectionalLight3D = _light.sun
	var room_probe: ReflectionProbe = _light.reflections[0]
	var original := _render_state()
	var floor_size := aperture.light_size
	var original_intensity: float = room_probe.intensity
	var original_cull: int = room_probe.cull_mask
	var original_fill: DirectionalLight3D = _rig.get_node("AdsCamera/ViewmodelFill")
	var original_blur := aperture.shadow_blur
	var gi_energy := env.sdfgi_energy
	var gi_occlusion := env.sdfgi_use_occlusion
	var snapshots := []
	var requested := OS.get_environment("BC5_MEETING_ONLY").split(",", false)
	var composition := VIEWS[3] if OS.get_environment("BC5_MEETING_AB_VIEW") == "room" else VIEWS[2]
	for id: String in ["base", "no_ssao", "no_ssil", "no_sdfgi", "low_feedback", "no_ssr", "no_room_probe",
		"world_probe", "no_fill", "no_aperture_softness", "no_aperture_shadows", "no_aperture", "no_sun_softness", "flat_wall",
		"aperture_003", "aperture_012", "aperture_035", "filtered_aperture", "taa", "moving_day",
		"gi_boost", "ambient_boost", "gi_no_occ"]:
		if not requested.is_empty() and not requested.has(id):
			continue
		_set_preset(composition[1])
		_pose(composition)
		env.ssao_enabled = bool(original.ssao) and id != "no_ssao"
		env.ssil_enabled = bool(original.ssil) and id != "no_ssil"
		env.sdfgi_enabled = bool(original.sdfgi) and id != "no_sdfgi"
		env.sdfgi_bounce_feedback = .36 if id == "low_feedback" else float(original.bounce_feedback)
		env.sdfgi_energy = 1.85 if id == "gi_boost" else gi_energy
		env.sdfgi_use_occlusion = gi_occlusion and id != "gi_no_occ"
		env.ssr_enabled = bool(original.ssr) and id != "no_ssr"
		room_probe.intensity = 0.0 if id == "no_room_probe" else original_intensity
		room_probe.cull_mask = 1 if id == "world_probe" else original_cull
		if id == "ambient_boost":
			room_probe.ambient_color_energy = .45
		original_fill.visible = bool(original.get("viewmodel_fill", true)) and id != "no_fill"
		var sizes := {"no_aperture_softness": 0.0, "filtered_aperture": 0.0,
			"aperture_003": .03, "aperture_012": .12, "aperture_035": .35}
		for section in apertures:
			section.light_size = float(sizes.get(id, floor_size))
			section.shadow_blur = 2.8 if id == "filtered_aperture" else original_blur
			section.shadow_enabled = id != "no_aperture_shadows"
			section.visible = id != "no_aperture"
		_viewport.use_taa = id == "taa" or bool(original.taa)
		if id == "no_sun_softness":
			sun.light_angular_distance = 0.0
		for mesh: MeshInstance3D in _scene.get_node("Room203").find_children("*", "MeshInstance3D", true, false):
			var mat := mesh.get_active_material(0) as BaseMaterial3D
			if mat and mat.resource_name == "BC5_203_Walls":
				mat.normal_enabled = id != "flat_wall"
		if id == "moving_day":
			_light.running = true
			await _wait(17.0)
			_light.running = false
		else:
			await _wait(.4)
		await _lock_camera(composition)
		await _wait(2.0)
		await _save("ab_" + id)
		var frame := await _measure()
		frame["id"] = id
		snapshots.append(frame)
	_report["ab"] = snapshots
