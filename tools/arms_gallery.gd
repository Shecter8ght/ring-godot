extends Node3D
## Крупный план хвата для настройки профилей без загрузки уровня.

func _ready() -> void:
	var environment: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.19, 0.22, 0.26)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.WHITE
	env.ambient_light_energy = 0.8
	environment.environment = env
	add_child(environment)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -40, 0)
	light.light_energy = 1.8
	add_child(light)
	var camera: Camera3D = Camera3D.new()
	camera.near = 0.02
	camera.fov = 65
	add_child(camera)
	camera.current = true
	var rig: Node3D = Node3D.new()
	add_child(rig)
	var arms: FirstPersonArms = load("res://scenes/player/first_person_arms.tscn").instantiate() as FirstPersonArms
	rig.add_child(arms)
	for id: String in ["pistol", "rifle", "shotgun", "bolt"]:
		var mods: Dictionary = {}
		var attachment: String = OS.get_environment("ARMS_ATTACHMENT")
		if attachment != "":
			mods["underbarrel"] = {"id": attachment}
		var suffix: String = "_" + attachment if attachment != "" else ""
		var gun: Node3D = WeaponModels.build(id, mods)
		rig.add_child(gun)
		gun.rotation.y = PI
		gun.position = Balance.FPS_HIP_POSE
		arms.bind_weapon(gun)
		arms.update_pose()
		camera.transform = Transform3D.IDENTITY
		await get_tree().create_timer(0.3).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/arms_" + id + suffix + ".png")
		camera.position = Vector3(0.7, 0.1, -0.15)
		camera.look_at(gun.position + Vector3(0, 0, -0.15))
		await get_tree().create_timer(0.2).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/arms_" + id + suffix + "_side.png")
		for side: String in ["Right", "Left"]:
			var marker: Node3D = gun.find_child(side + "Grip", true, false) as Node3D
			camera.position = marker.global_position + Vector3(0.2 if side == "Right" else -0.2, 0.07, 0.13)
			camera.look_at(marker.global_position)
			await get_tree().create_timer(0.2).timeout
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("res://docs/screens/arms_" + id + suffix + "_" + side.to_lower() + "_detail.png")
		gun.free()
	get_tree().quit()
