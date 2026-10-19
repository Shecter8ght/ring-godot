extends Node
## Тридцать секунд реального игрового цикла: ходьба, присед, лёжа, снова ходьба.


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
		enemy.visible = false
	var player: Player = get_tree().get_first_node_in_group("players") as Player
	player.global_position = Vector3(100.0, 0.1, -5.0)
	await get_tree().physics_frame
	var camera: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if camera:
		camera.set_distance(Balance.CAMERA_ZOOM_MIN)
	player.health.hp = 100000.0
	var interval: float = 1.0 if OS.get_environment("PERSONA_QUICK") == "1" else 7.5
	await _phase(player, "walk", Player.Stance.STAND, true, interval)
	await _phase(player, "crouch", Player.Stance.CROUCH, false, interval)
	await _phase(player, "prone", Player.Stance.PRONE, false, interval)
	await _phase(player, "walk_again", Player.Stance.STAND, true, interval)
	get_tree().quit()


func _phase(player: Player, label: String, next_stance: int, moving: bool, duration: float) -> void:
	var origin: Vector3 = player.global_position
	player.stance = next_stance
	player._apply_stance()
	if moving:
		Input.action_press("move_forward")
	await get_tree().create_timer(duration * 0.5).timeout
	var skeleton: Skeleton3D = player.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	var left_foot: int = skeleton.find_bone("mixamorig_LeftFoot")
	var right_foot: int = skeleton.find_bone("mixamorig_RightFoot")
	var minimum: float = INF
	var min_bone: String = ""
	for i in range(skeleton.get_bone_count()):
		var y: float = (skeleton.global_transform * skeleton.get_bone_global_pose(i)).origin.y
		if y < minimum:
			minimum = y
			min_bone = skeleton.get_bone_name(i)
	var animator: CharacterAnimator = player.get_node("CharacterAnimator") as CharacterAnimator
	print("PLAYTEST ", label, " moved=", player.global_position.distance_to(origin), " feet_y=", (skeleton.global_transform * skeleton.get_bone_global_pose(left_foot)).origin.y, ",", (skeleton.global_transform * skeleton.get_bone_global_pose(right_foot)).origin.y, " min=", minimum, " bone=", min_bone, " hips=", (skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("mixamorig_Hips"))).origin.y, " body_scale=", player.get_node("Body").scale.y, " model_pos=", player.get_node("Body/Persona").position.y, " clip=", animator._current, " shot=", animator._one_shot)
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/persona_playtest_" + label + ".png"))
	await get_tree().create_timer(duration * 0.5).timeout
	if moving:
		Input.action_release("move_forward")
