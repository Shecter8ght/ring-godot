extends Node
## Проба: в убежище ходьба и бег — замер скорости. godot --path . res://tools/hideout_move_probe.tscn

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://profile_probe.json", true)
	for id in ["wpn_ar_03", "wpn_hg_03", "armor_mid", "helmet_simple"]:
		for i in range(Profile.stash.size()):
			if String(Profile.stash[i].id) == id:
				Profile.equip_from_stash(i)
				break
	CameraRig.first_person_mode = OS.get_environment("PROBE_FP") == "1"
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	for i in range(60):
		await get_tree().physics_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	print("probe: player ", pl, " stamina ", pl.stamina if pl else -1.0)
	for sprint in [false, true]:
		var p0 := pl.global_position
		Input.action_press("move_forward")
		if sprint:
			Input.action_press("sprint")
		for i in range(40):
			await get_tree().physics_frame
		var v := Vector2(pl.velocity.x, pl.velocity.z).length()
		Input.action_release("move_forward")
		Input.action_release("sprint")
		print("probe: бег %s — скорость %.2f, прошёл %.2f, stamina %.0f, winded %s, aiming %s, over %.2f" % [sprint, v, pl.global_position.distance_to(p0), pl.stamina, pl._winded, pl.aiming, pl.carry_speed_k()])
		for i in range(20):
			await get_tree().physics_frame
	get_tree().quit(0)
