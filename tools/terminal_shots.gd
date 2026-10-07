extends Node
## Терминал связи: стол в хабе и окно доски заказов — docs/screens/terminal_*.png.
## tools/godot.cmd res://tools/terminal_shots.tscn

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://terminal_shots_test.json", true)
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	for i: int in range(150):
		await get_tree().process_frame
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	pl.global_position = Vector3(-5.0, 0.05, -7.6)
	rig._look_yaw = PI
	rig._look_pitch = -0.32
	for i: int in range(90):
		await get_tree().process_frame
	_save("terminal_desk")
	var term: ContractTerminal = level.find_child("ContractTerminal", true, false) as ContractTerminal
	Contracts.sync()
	var board: Array = Contracts.board()
	if not board.is_empty():
		Contracts.take(String(board[0].id))
	term.request_use()
	for i: int in range(20):
		await get_tree().process_frame
	_save("terminal_board")
	get_tree().quit()


func _save(label: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % label))
