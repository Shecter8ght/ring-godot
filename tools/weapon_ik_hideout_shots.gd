extends Node
## Снимки и короткий проход к настоящей стене убежища, отдельный профиль.

func _ready() -> void:
	Engine.max_fps = 60
	Profile.use_file("user://weapon_ik_hideout_shots_test.json", true)
	RaidEvents.enabled = false
	var level: Node3D = (load(Balance.HIDEOUT_SCENE) as PackedScene).instantiate() as Node3D
	get_tree().root.add_child.call_deferred(level)
	await get_tree().process_frame
	await get_tree().create_timer(1.5).timeout
	var player: Player = level.get("_player") as Player
	var camera: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	camera.set_process_unhandled_input(false)
	player.loadout_mode = false
	var slot: String = String(WeaponDb.sandbox()[0])
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	player.sandbox_weapons[slot] = WeaponDb.make_weapon("PM_BASE", rng, [100, 100])
	player._ws.erase(slot)
	player.weapon_slot = ""
	player._switch(slot, false)
	CameraRig.first_person_mode = true
	await get_tree().create_timer(.4).timeout
	var start: Vector3 = player.global_position
	var eye: Vector3 = player.eye_position()
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(eye, eye + Vector3.LEFT * 8, WeaponClearance.MASK, [player.get_rid()])
	var hit: Dictionary = level.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		push_error("IK hideout: no wall to the left of spawn")
		get_tree().quit(1)
		return
	var end: Vector3 = (hit.position as Vector3) + (hit.normal as Vector3) * .38
	end.y = start.y
	camera._look_yaw = -PI * .5
	camera._look_pitch = 0.0
	var output: String = "res://docs/screens/weapon_ik/hideout/"
	DirAccess.make_dir_recursive_absolute(output)
	var frame: int = 0
	for stage: int in range(3):
		for step: int in range(30):
			var t: float = smoothstep(0.0, 1.0, float(step) / 29.0)
			player.global_position = start.lerp(end, t) if stage == 0 else (end if stage == 1 else end.lerp(start, t))
			player.velocity = Vector3.ZERO
			camera._look_yaw = -PI * .5
			await get_tree().create_timer(.05).timeout
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(output + "frame_%03d.png" % frame)
			frame += 1
		print("IK_HIDEOUT stage=", stage, " obstruction=", player.weapon_obstruction, " visible=", camera._viewmodel.visible)
	print("IK_HIDEOUT_SHOTS DONE frames=", frame)
	get_tree().quit()
