extends Node3D
## Проверка SSR движка: зеркальная плоскость (стандартный материал и мокрый асфальт), куб над ней.
## godot --path . res://tools/ssr_probe.tscn → docs/screens/ssr_probe_*.png

func _ready() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.05, 0.06, 0.08)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.2, 0.2, 0.2)
	env.ssr_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40, 30, 0)
	add_child(sun)
	for i in range(2):
		var pl := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(6, 12)
		pl.mesh = pm
		pl.position = Vector3(-3.2 + 6.4 * i, 0, 0)
		if i == 0:
			var m := StandardMaterial3D.new()
			m.albedo_color = Color(0.1, 0.1, 0.1)
			m.roughness = 0.02
			pl.material_override = m
		else:
			var wm := (load("res://assets/materials/asphalt_02_wet.tres") as ShaderMaterial).duplicate() as ShaderMaterial
			wm.set_shader_parameter("wetness", 1.0)
			wm.set_shader_parameter("puddles", 1.0)
			wm.set_shader_parameter("occ_size", 0.0001)
			pl.material_override = wm
		add_child(pl)
	for x in [-3.0, 3.0]:
		var c := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(1.5, 3.0, 1.5)
		c.mesh = bm
		c.position = Vector3(x, 1.5, -4.0)
		var cm := StandardMaterial3D.new()
		cm.albedo_color = Color(0.9, 0.2, 0.1)
		cm.emission_enabled = true
		cm.emission = Color(0.9, 0.2, 0.1)
		c.material_override = cm
		add_child(c)
	var cam := Camera3D.new()
	cam.position = Vector3(0, 1.6, 5.0)
	cam.rotation_degrees = Vector3(-14, 0, 0)
	add_child(cam)
	cam.current = true
	# настройки SSR: [шагов, fade_in, fade_out, допуск глубины]
	for cfg in [[64, 0.15, 2.0, 0.2], [256, 0.15, 2.0, 0.2], [256, 0.15, 0.4, 0.5], [512, 0.1, 0.25, 1.0]]:
		env.ssr_max_steps = int(cfg[0])
		env.ssr_fade_in = float(cfg[1])
		env.ssr_fade_out = float(cfg[2])
		env.ssr_depth_tolerance = float(cfg[3])
		for i in range(30):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/ssr_probe_%d_%s.png" % [int(cfg[0]), str(cfg[2])]))
	get_tree().quit(0)
