extends Node3D
## Быстрая проверка запечённой модели и трёх поз крупным планом.


func _ready() -> void:
	var scene: PackedScene = load("res://assets/models/characters/persona_animated.glb") as PackedScene
	var clips: AnimationLibrary = load("res://assets/models/characters/persona_clips.res") as AnimationLibrary
	var poses: Array[String] = ["pistol_walk_f", "unarmed_crouch_idle", "prone_move_b"]
	for i in range(poses.size()):
		var model: Node3D = scene.instantiate() as Node3D
		model.position.x = (i - 1.0) * 1.7
		add_child(model)
		var anim := AnimationPlayer.new()
		anim.name = "AnimationPlayer"
		anim.root_node = NodePath("..")
		model.add_child(anim)
		anim.add_animation_library("", clips)
		anim.play(poses[i])
		anim.seek(float(Balance.CHARACTER_ANIM.prone_hold_sec) if i == 2 else 0.25, true)
	var floor := MeshInstance3D.new()
	var floor_mesh := PlaneMesh.new()
	floor_mesh.size = Vector2(12.0, 5.0)
	floor.mesh = floor_mesh
	add_child(floor)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45.0, 30.0, 0.0)
	light.light_energy = 2.0
	add_child(light)
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.16, 0.18, 0.2)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.75, 0.8, 0.85)
	env.ambient_light_energy = 1.0
	environment.environment = env
	add_child(environment)
	var camera := Camera3D.new()
	camera.position = Vector3(0.0, 2.0, 7.0)
	add_child(camera)
	camera.look_at(Vector3(0.0, 1.0, 0.0))
	camera.current = true
	await get_tree().create_timer(1.0).timeout
	get_viewport().get_texture().get_image().save_png("res://docs/screens/persona_gallery.png")
	camera.position = Vector3(-1.7, 1.55, 0.9)
	camera.look_at(Vector3(-1.7, 1.55, 0.0))
	await get_tree().create_timer(0.2).timeout
	get_viewport().get_texture().get_image().save_png("res://docs/screens/persona_face.png")
	get_tree().quit()
