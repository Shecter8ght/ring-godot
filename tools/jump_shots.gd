extends Node
## Реальный прыжок в убежище: боковой ракурс в воздухе, тестовый профиль.

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://jump_shots_test.json",true)
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	for i: int in range(160):await get_tree().process_frame
	var level: Node = get_tree().current_scene
	var player: Player = level.get("_player") as Player
	player.global_position = Vector3(0,.03,4)
	player.velocity = Vector3.ZERO
	for i: int in range(12):await get_tree().physics_frame
	var rig: CameraRig = level.get_node("CameraRig") as CameraRig
	rig.set_process(false)
	for layer: Node in level.find_children("*","CanvasLayer",true,false):
		(layer as CanvasLayer).visible = false
	var camera: Camera3D = Camera3D.new()
	camera.fov = 55
	level.add_child(camera)
	camera.global_position = player.global_position+Vector3(-2.6,1.9,-2.8)
	camera.look_at(player.global_position+Vector3(0,1.15,0))
	camera.make_current()
	SectorMaterials.set_cutaway_distance(0,.001)
	player.cursor_ground = player.global_position+Vector3(0,0,-3)
	player._try_jump()
	for i: int in range(17):await get_tree().physics_frame
	player.set_physics_process(false)
	await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png("res://docs/shelter/validation/jump.png")
	get_tree().quit()
