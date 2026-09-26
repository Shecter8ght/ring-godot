extends Node
## Настройки: шины громкости, качество графики (низко — без SDFGI/SSIL/SSAO/тумана, рендер 77 %;
## высоко — как в сцене), чувствительность. В инструментах ничего не сохраняется.
## godot --path . res://tools/settings_test.tscn (можно --headless)

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
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
	Settings.set_quality("low")
	_check("низко: без SDFGI, SSIL, SSAO, тумана; рендер 77 %", not env.sdfgi_enabled and not env.ssil_enabled and not env.ssao_enabled and not env.volumetric_fog_enabled \
		and is_equal_approx(get_viewport().scaling_3d_scale, 0.77), "")
	Settings.set_quality("medium")
	_check("средне: SSAO и туман есть, SDFGI нет", env.ssao_enabled and env.volumetric_fog_enabled and not env.sdfgi_enabled, "")
	Settings.set_quality("high")
	_check("высоко — как в сцене", env.sdfgi_enabled == sdfgi0 and is_equal_approx(get_viewport().scaling_3d_scale, 1.0), "")
	Settings.set_sens(2.0, 0.5)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
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


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
