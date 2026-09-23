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
	_press("pause")
	await _frames(4)
	print("ui_shots: меню закрыто — пауза снята: ", not get_tree().paused)
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
