extends Node
## Снимки окон: карта на M (обзор и приближение), меню на Esc с раскладкой управления.
## godot --path . res://tools/ui_shots.tscn → docs/screens/ui_*.png


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(90):
		await get_tree().physics_frame
	_press("map")
	await _frames(6)
	_save("ui_map")
	var map := inst.get_node("Map") as MapView
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_WHEEL_UP
	e.pressed = true
	for i in range(4):
		map.call("_on_gui_input", e)
	await _frames(4)
	_save("ui_map_zoom")
	_press("map")
	await _frames(4)
	_press("pause")
	await _frames(4)
	_save("ui_pause")
	var pause := get_node("/root/Pause") as PauseMenu
	(pause.get("_controls") as Control).visible = true
	await _frames(4)
	_save("ui_controls")
	(pause.get("_controls") as Control).visible = false
	(pause.get("_settings") as Control).visible = true
	await _frames(4)
	_save("ui_settings")
	(pause.get("_settings") as Control).visible = false
	# панель админа хоста: поднять сервер (без клиентов — в списке только хост)
	Net.host("Хост")
	Net.player_names[2] = "Друг"   # для снимка: вторая строка
	pause.open_admin()
	await _frames(4)
	_save("ui_admin")
	Net.disconnect_all()
	_press("pause")
	await _frames(4)
	print("ui_shots: меню закрыто — пауза снята: ", not get_tree().paused)
	# рюкзак и лут в рейде: в рюкзаке — немного вещей, рядом — сейф
	var me := get_tree().get_first_node_in_group("players") as Player
	for pair in [["ammo_545_std", 90], ["bandage", 3], ["medkit", 1], ["wpn_hg_03", 1], ["vest_police", 1], ["mag_545_30", 1], ["gold_chain", 2]]:
		me.inventory.add(String(pair[0]), int(pair[1]))
	var safe := inst.get_node("Interactables/JewelrySafe") as LootContainer
	safe.roll()
	me.global_position = safe.global_position + safe.global_basis.z * -1.0
	await _frames(3)
	Raid.current.ui.call("_open_loot", safe)
	await _frames(6)
	_save("ui_inventory")
	Raid.current.ui.call("close_all")
	# от первого лица: у бедра, в наклоне вправо, в прицеле
	me.global_position = SectorBuilder.polar(-90.0, 100.0) + Vector3(0, 0.1, 0)
	CameraRig.first_person_mode = true
	_press("weapon_1")
	await _frames(20)
	_save("ui_fps_hip")
	Input.action_press("camera_right")
	await _frames(30)
	_save("ui_fps_lean")
	Input.action_release("camera_right")
	Input.action_press("aim")
	await _frames(40)
	_save("ui_fps_ads")
	Input.action_release("aim")
	CameraRig.first_person_mode = false
	# качество графики: тот же вид в изометрии — высоко и низко
	await _frames(20)
	_save("ui_quality_high")
	Settings.set_quality("low")
	await _frames(30)
	_save("ui_quality_low")
	Settings.set_quality("high")
	# тяжёлое ранение: экран и меню «чем помочь себе»
	me.health.hp = 100.0
	me.health.take_damage(150.0, me.global_position + Vector3(0, 1, 5), "body")
	me.inventory.add("medkit", 1)
	me.inventory.add("bandage", 2)
	await _frames(60)
	_save("ui_downed")
	_press("use_med")
	await _frames(6)
	_save("ui_downed_meds")
	get_tree().quit(0)


func _press(action: String) -> void:
	var ev := InputEventAction.new()
	ev.action = action
	ev.pressed = true
	Input.parse_input_event(ev)
	var up := InputEventAction.new()
	up.action = action
	up.pressed = false
	Input.parse_input_event(up)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("ui_shots: ", n)
