extends Node
## Настройки: шины громкости, качество графики (низко — без SDFGI/SSIL/SSAO/тумана, рендер 77 %;
## высоко — как в сцене), чувствительность, поле зрения (пересчёт, прицелы, руки). В инструментах
## ничего не сохраняется.
## godot --path . res://tools/settings_test.tscn (можно --headless)

var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://settings_test.json", true)
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	await get_tree().process_frame
	await get_tree().process_frame
	var ok_bus := true
	for b in Settings.BUSES:
		ok_bus = ok_bus and AudioServer.get_bus_index(String(b)) >= 0
	_check("шины звука есть", ok_bus and Settings.bus_for("shot_rifle") == &"Shots" and Settings.bus_for("step_stone") == &"Steps", "")
	Settings.set_volume("Shots", 0.5)
	_check("громкость выстрелов 50 % — −6 дБ", absf(AudioServer.get_bus_volume_db(AudioServer.get_bus_index("Shots")) + 6.02) < 0.1, "%.1f дБ" % AudioServer.get_bus_volume_db(AudioServer.get_bus_index("Shots")))
	Settings.set_volume("Shots", 1.0)
	var env := (inst.find_children("*", "WorldEnvironment", true, false)[0] as WorldEnvironment).environment
	var sdfgi0 := env.sdfgi_enabled
	# тень солнца по качеству (Balance.SHADOW_QUALITY): на ТЦ в сцене — 260 м и 4 каскада
	var sun := inst.find_children("*", "DirectionalLight3D", true, false)[0] as DirectionalLight3D
	var sun_m0: float = (sun.get_meta("orig_sun_shadow", {}) as Dictionary).get("max_m", sun.directional_shadow_max_distance)
	Settings.set_quality("low")
	_check("низко: без SDFGI, SSIL, SSAO, тумана; рендер 77 %", not env.sdfgi_enabled and not env.ssil_enabled and not env.ssao_enabled and not env.volumetric_fog_enabled \
		and is_equal_approx(get_viewport().scaling_3d_scale, 0.77), "")
	_check("низко: тень солнца до 100 м, 2 каскада", is_equal_approx(sun.directional_shadow_max_distance, minf(sun_m0, 100.0))
		and sun.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS, "%.0f м, режим %d" % [sun.directional_shadow_max_distance, sun.directional_shadow_mode])
	Settings.set_quality("medium")
	# SSAO и объёмный туман на «средне» — как в сцене (туман есть не на каждом свете: у прежнего света «Проспекта»
	# объёмного тумана не было, у света Road to Vostok — дымка); SDFGI — только «высоко»
	var orig: Dictionary = env.get_meta("orig", {})
	_check("средне: SSAO и туман как в сцене, SDFGI нет", env.ssao_enabled == bool(orig.get("ssao", true)) and env.ssao_enabled
		and env.volumetric_fog_enabled == bool(orig.get("fog", false)) and not env.sdfgi_enabled,
		"SSAO %s, туман %s (в сцене %s)" % [env.ssao_enabled, env.volumetric_fog_enabled, orig.get("fog")])
	_check("средне: тень солнца до 160 м, 4 каскада", is_equal_approx(sun.directional_shadow_max_distance, minf(sun_m0, 160.0))
		and sun.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS, "%.0f м, режим %d" % [sun.directional_shadow_max_distance, sun.directional_shadow_mode])
	Settings.set_quality("high")
	_check("высоко — как в сцене", env.sdfgi_enabled == sdfgi0 and is_equal_approx(get_viewport().scaling_3d_scale, 1.0), "")
	_check("высоко: тень солнца как в сцене (%.0f м, 4 каскада)" % sun_m0, is_equal_approx(sun.directional_shadow_max_distance, sun_m0)
		and sun.directional_shadow_mode == DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS, "%.0f м" % sun.directional_shadow_max_distance)
	Settings.set_sens(2.0, 0.5)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_check("хит-маркер по умолчанию включён", Settings.hitmarker, "")
	# маркер горит Balance.HITMARKER_SEC (0,14 с): первые кадры после загрузки карты длиннее — ждём, пока уровень догрузится
	await _settle()
	rig.show_hitmarker(false)
	await get_tree().process_frame
	await get_tree().process_frame
	_check("попадание показывает маркер", rig._hitmarker.visible, "")
	Pause.open_menu()
	Settings.set_hitmarker(false)
	_check("отключение на паузе действует сразу", not rig._hitmarker.visible and rig._hitmarker_t <= 0.0, "")
	Pause.close_menu()
	await get_tree().process_frame
	await get_tree().process_frame
	_check("отключение убирает текущий маркер", not rig._hitmarker.visible and rig._hitmarker_t <= 0.0, "")
	rig.show_hitmarker(true)
	_check("убийство при выключенном маркере не запускает таймер", rig._hitmarker_t <= 0.0, "")
	Settings.set_hitmarker(true)
	await get_tree().process_frame
	_check("после включения старое попадание не возвращается", not rig._hitmarker.visible, "")
	rig.show_hitmarker(true)
	_check("новое убийство снова показывает красный маркер", rig._hitmarker_t > 0.0 and rig._hitmarker.modulate.r > rig._hitmarker.modulate.g, "")
	_check("чувствительность мыши — множитель", is_equal_approx(Settings.sens_fps, 2.0) and rig != null, "")
	Settings.set_sens(0.05, 10.0)
	_check("чувствительность: от ×0.05 до ×10", is_equal_approx(Settings.sens_fps, 0.05) and is_equal_approx(Settings.sens_iso, 10.0), "%.2f / %.2f" % [Settings.sens_fps, Settings.sens_iso])
	var pl := get_tree().get_first_node_in_group("players") as Player
	if pl and rig:
		Settings.set_sens(1.0, 1.0)
		pl.aiming = true
		var aim1 := rig.ads_sens()
		Settings.set_sens_ads(2.5)
		_check("в прицеле — свой множитель", is_equal_approx(rig.ads_sens(), aim1 * 2.5), "%.5f → %.5f" % [aim1, rig.ads_sens()])
		pl.aiming = false
		_check("не целится — множитель прицела не действует", is_equal_approx(rig.ads_sens(), aim1), "%.5f" % rig.ads_sens())
		Settings.set_sens_ads(1.0)
	# Поле зрения мира по горизонтали на 16:9; ADS сохраняет его, оружие имеет своё.
	# По умолчанию 80° (решение владельца 2026-10-24, стенд масштаба; было 90°).
	_check("поле зрения по умолчанию 80°", is_equal_approx(Settings.fov_h, Settings.FOV_H_DEFAULT) and is_equal_approx(Settings.FOV_H_DEFAULT, 80.0), "%.1f" % Settings.fov_h)
	Settings.set_fov_h(10.0)
	var lo := Settings.fov_h
	Settings.set_fov_h(200.0)
	_check("поле зрения: от 50° до 120°", is_equal_approx(lo, 50.0) and is_equal_approx(Settings.fov_h, 120.0), "%.1f / %.1f" % [lo, Settings.fov_h])
	Settings.set_fov_h(90.0)
	_check("90° по горизонтали — 58.72° по вертикали", absf(Settings.fps_fov_v() - 58.72) < 0.01, "%.3f" % Settings.fps_fov_v())
	var h74 := rad_to_deg(2.0 * atan(tan(deg_to_rad(Balance.FPS_FOV) * 0.5) * 16.0 / 9.0))
	_check("%.2f° по горизонтали — опорные 74° по вертикали" % h74, absf(Settings.fov_v_from_h(h74) - 74.0) < 0.001, "%.3f" % Settings.fov_v_from_h(h74))
	var vm_ok := is_equal_approx(CameraRig.viewmodel_scale(Balance.FPS_VIEWMODEL_FOV), 1.0)
	for cam_v in [40.0, 58.72, 74.0, 100.0]:
		var vk := CameraRig.viewmodel_scale(cam_v)
		# точка (x, y, z) в осях камеры под масштабом (k, k, 1): на экране — как у камеры с полем зрения модели
		var p := Vector3(0.09, -0.12, -0.35)
		var ndc_cam := vk * p.y / -p.z / tan(deg_to_rad(cam_v) * 0.5)
		var ndc_vm := p.y / -p.z / tan(deg_to_rad(Balance.FPS_VIEWMODEL_FOV) * 0.5)
		vm_ok = vm_ok and absf(ndc_cam - ndc_vm) < 1e-5
	_check("руки и оружие — со своим полем зрения (масштаб k)", vm_ok, "k(58.72)=%.4f" % CameraRig.viewmodel_scale(58.72))
	if pl and rig:
		pl.aiming = false
		rig._ads_cam.fov = Settings.fps_fov_v()
		var s90 := rig.ads_sens()
		Settings.set_fov_h(120.0)
		rig._ads_cam.fov = Settings.fps_fov_v()
		var s120 := rig.ads_sens()
		Settings.set_fov_h(90.0)
		rig._ads_cam.fov = Settings.fps_fov_v()
		_check("у бедра мышь та же при любом поле зрения", is_equal_approx(s90, s120) and is_equal_approx(s90, Balance.ADS_SENS * Balance.FPS_FOV / 62.0), "%.5f / %.5f" % [s90, s120])
	# «Покачивание камеры»: по умолчанию полное, от 0 до 100 %, ползунок в меню
	_check("покачивание камеры по умолчанию 100 %", is_equal_approx(Settings.camera_motion, 1.0), "%.2f" % Settings.camera_motion)
	Settings.set_camera_motion(-1.0)
	var cm_lo := Settings.camera_motion
	Settings.set_camera_motion(3.0)
	_check("покачивание камеры: от 0 до 100 %", is_equal_approx(cm_lo, 0.0) and is_equal_approx(Settings.camera_motion, 1.0), "%.2f / %.2f" % [cm_lo, Settings.camera_motion])
	Settings.set_camera_motion(1.0)
	_check("в настройках есть ползунок «Покачивание камеры»", get_node("/root/Pause").find_child("CameraMotionSlider", true, false) != null, "")
	# клавиши: F → E у «взаимодействия»; E уже у поворота камеры — видно; сброс — снова F
	var e := InputEventKey.new()
	e.physical_keycode = KEY_E
	Settings.set_key("interact", e)
	_check("клавиша сменилась", PauseMenu.key_name("interact") == "E", PauseMenu.key_name("interact"))
	_check("занятая клавиша — конфликт виден", "camera_right" in Settings.key_conflicts("interact"), str(Settings.key_conflicts("interact")))
	Settings.reset_keys()
	_check("по умолчанию — снова F", PauseMenu.key_name("interact") == "F" and Settings.keys.is_empty(), PauseMenu.key_name("interact"))
	Settings.set_invert_y(true)
	_check("инверсия по вертикали", Settings.invert_y, "")
	Settings.set_invert_y(false)
	Settings.set_sens(1.0, 1.0)
	_check("в инструментах настройки не сохраняются", Settings._tool_run, "")
	print("settings_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Ждать, пока кадры станут короткими (карта догрузилась, навигация и шейдеры собраны): до 20 с.
func _settle() -> void:
	var calm := 0
	var t0 := Time.get_ticks_msec()
	while calm < 5 and Time.get_ticks_msec() - t0 < 20000:
		await get_tree().process_frame
		calm = calm + 1 if get_process_delta_time() < Balance.HITMARKER_SEC * 0.25 else 0


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
