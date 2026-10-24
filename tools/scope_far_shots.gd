extends Node
## Сильная оптика на дальней планке (над цевьём) и на заднем краю верхней планки: в прицеле в окуляре
## картинка оптики, а не заглушка линзы; у бедра линза — тёмное стекло. Снимки docs/screens/scope_far_*.png.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/scope_far_shots.tscn

var _player: Player
var _rig: CameraRig
var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(60):
		await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.health.hp = 1e9
	for m: Node in get_tree().get_nodes_in_group("marauders"):
		m.set_physics_process(false)
	var cases: Array = [["front8", {"top_front": "optic_8x_01"}], ["front12", {"top_front": "optic_12x_01"}], ["front4", {"top_front": "optic_4x_01"}],
		["rear8", {"optic_primary": "optic_8x_01"}]]
	for c: Array in cases:
		_player.set_sandbox_mods(String(_player.weapon_keys()[0]), c[1])
		await _tap("weapon_2")
		await get_tree().create_timer(0.3).timeout
		await _tap("weapon_1")
		await get_tree().create_timer(0.5).timeout
		_save("scope_far_%s_hip" % String(c[0]))
		Input.action_press("aim")
		await get_tree().create_timer(1.0).timeout
		await _frames(10)
		print("  [%s] %s: в прицеле работает картинка оптики  (%s)" % ["ok" if _rig.scope_active else "FAIL", String(c[0]), str(c[1])])
		if not _rig.scope_active:
			_fails += 1
		_save("scope_far_%s_ads" % String(c[0]))
		Input.action_release("aim")
		await _frames(20)
	print("scope_far_shots: провалов %d" % _fails)
	get_tree().quit(_fails)


func _tap(action: String) -> void:
	Input.action_press(action)
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(action)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
