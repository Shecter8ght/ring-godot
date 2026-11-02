extends SceneTree
## Интерфейс прогулки по стенду общежития: подсказка внизу помещается в окно, F10 / U прячет всё (панель света,
## подсказки, план, подписи в мире) и возвращает обратно. Снимки ui_check_* в docs/screens/dorm/.
##   tools/godot.cmd --windowed --resolution 1600x900 --script res://tools/dorm_ui_check.gd

const OUT: String = "res://docs/screens/dorm/"


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var scene: Node = (load("res://tools/dorm_study.tscn") as PackedScene).instantiate()
	root.add_child(scene)
	for i: int in range(240):
		await process_frame
	var fails: int = 0
	fails += _shot("ui_check_shown")
	var hud: CanvasLayer = scene.get("hud") as CanvasLayer
	for key: Key in [KEY_U, KEY_U, KEY_F10]:
		var ev: InputEventKey = InputEventKey.new()
		ev.physical_keycode = key
		ev.keycode = key
		ev.pressed = true
		Input.parse_input_event(ev)
		for i: int in range(20):
			await process_frame
		var labels_visible: int = 0
		for node: Node in get_nodes_in_group("dorm_study_labels"):
			if (node as Node3D).visible:
				labels_visible += 1
		print("dorm_ui: после %s — интерфейс %s, подписей видно %d" % [OS.get_keycode_string(key), "виден" if hud.visible else "скрыт", labels_visible])
		if key == KEY_U and not hud.visible:
			fails += _shot("ui_check_hidden")
	print("dorm_ui: готово, ошибок ", fails)
	quit(fails)


func _shot(name: String) -> int:
	var img: Image = root.get_viewport().get_texture().get_image()
	return 0 if img.save_png(ProjectSettings.globalize_path(OUT + name + ".png")) == OK else 1
