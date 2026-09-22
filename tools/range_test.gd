extends Node
## Тир без рук: стреляем по мишеням (тело и голова), снимок в момент откидывания.

func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/test_range.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(20):
		await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	var cam := get_viewport().get_camera_3d()
	var hits := [0, 0]
	var targets := get_tree().get_nodes_in_group("shootable")
	for t in targets:
		(t as Target).hit.connect(func(_d: float, head: bool) -> void: hits[1 if head else 0] += 1)
	var order := [[0, 1.0], [0, 1.0], [1, 1.5], [2, 1.0], [2, 1.5], [3, 1.0]]
	for o in order:
		var t := targets[o[0]] as Target
		for k in range(3):
			await get_tree().process_frame
		# Камера уезжает к курсору — доводим курсор на цель, пока камера не успокоится.
		for k in range(25):
			Input.warp_mouse(cam.unproject_position(t.global_position + Vector3(0, o[1], 0)))
			await get_tree().process_frame
		player.ammo = 8
		Input.action_press("fire")
		await get_tree().process_frame
		await get_tree().process_frame
		Input.action_release("fire")
		print("  цель %d h=%.1f: дист %.1f, курсор на теле=%s" % [o[0], o[1], player.global_position.distance_to(t.global_position), player.cursor_body != Vector3.ZERO])
		await get_tree().create_timer(0.1).timeout
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/range.png"))
	print("range: мишеней %d, попаданий в тело %d, в голову %d" % [targets.size(), hits[0], hits[1]])
	get_tree().quit(0)
