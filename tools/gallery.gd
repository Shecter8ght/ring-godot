extends Node3D
## Витрина оружия: все модели на тёмном сукне под студийным светом + крупные планы.
## godot --path . res://tools/gallery.tscn → docs/screens/weapons*.png

func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.06, 0.065, 0.07)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.5, 0.52, 0.55)
	e.ambient_light_energy = 0.35
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.ssao_enabled = true
	e.ssao_radius = 0.05
	e.glow_enabled = true
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-50, -35, 0)
	key.light_energy = 2.2
	key.shadow_enabled = true
	key.directional_shadow_max_distance = 5.0
	add_child(key)
	var rim := OmniLight3D.new()
	rim.position = Vector3(-0.6, 0.5, 1.2)
	rim.light_color = Color(0.7, 0.8, 1.0)
	rim.light_energy = 1.5
	rim.omni_range = 3.0
	add_child(rim)
	var cloth := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(4, 4)
	cloth.mesh = pm
	var cm := StandardMaterial3D.new()
	cm.albedo_color = Color(0.16, 0.17, 0.15)
	cm.roughness = 1.0
	cloth.material_override = cm
	add_child(cloth)
	# раскладка: оружие лежит на боку (правой стороной вверх), дулом вправо
	var layout := {"bolt": Vector3(-0.35, 0, -0.42), "rifle": Vector3(-0.3, 0, -0.14), "shotgun": Vector3(-0.3, 0, 0.12), "pistol": Vector3(-0.35, 0, 0.36), "grenade": Vector3(0.05, 0, 0.38)}
	for id in layout:
		var w := WeaponModels.build(id)
		add_child(w)
		w.position = layout[id] + Vector3(0, 0.025, 0)
		if id != "grenade":
			# дулом вправо, правой стороной вверх
			w.basis = Basis(Vector3.RIGHT, -PI * 0.5) * Basis(Vector3.UP, PI * 0.5)
		else:
			w.position.y = 0.032
	var cam := Camera3D.new()
	cam.fov = 38
	add_child(cam)
	cam.position = Vector3(0.05, 1.25, 0.95)
	cam.look_at(Vector3(0.0, 0, -0.02))
	cam.current = true
	for i in range(30):
		await get_tree().process_frame
	_save("weapons")
	var shots := {"rifle": [Vector3(0.0, 0.14, 0.2), Vector3(0.02, 0.0, -0.14)], "bolt": [Vector3(-0.12, 0.2, -0.2), Vector3(0.0, 0.02, -0.42)], "pistol": [Vector3(-0.35, 0.12, 0.52), Vector3(-0.35, 0.02, 0.36)], "grenade": [Vector3(0.12, 0.09, 0.47), Vector3(0.05, 0.035, 0.38)]}
	for id in shots:
		cam.position = shots[id][0]
		cam.look_at(shots[id][1])
		for i in range(8):
			await get_tree().process_frame
		_save("weapons_" + id)
	get_tree().quit(0)


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("gallery: ", n)
