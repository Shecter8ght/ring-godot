extends Node3D
## Пистолет крупно: справа, слева, сверху, 3/4 и с обвесами — docs/screens/pistol_*.png.
## godot --path . res://tools/pistol_shots.tscn

func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.1, 0.105, 0.11)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.6, 0.62, 0.66)
	e.ambient_light_energy = 0.55
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.ssao_enabled = true
	e.ssao_radius = 0.02
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-40, 60, 0)
	key.light_energy = 2.4
	key.shadow_enabled = true
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-25, -120, 0)
	rim.light_color = Color(0.7, 0.8, 1.0)
	rim.light_energy = 1.4
	add_child(rim)
	var cam := Camera3D.new()
	cam.near = 0.005
	cam.fov = 28.0
	add_child(cam)
	cam.current = true
	var mid := Vector3(0, 0.02, 0.06)
	var views := {"right": Vector3(0.62, 0.0, 0.0), "left": Vector3(-0.62, 0.0, 0.0), "top": Vector3(0.001, 0.6, 0.0),
		"34": Vector3(0.38, 0.22, 0.38), "back": Vector3(0.18, 0.12, -0.45)}
	for kit in [{}, WeaponDb.preset("HG_03_TAC").get("mods", {})]:
		var w := WeaponModels.build("wpn_hg_03", kit)
		add_child(w)
		for v in views:
			if not kit.is_empty() and v != "right" and v != "34":
				continue
			var off: Vector3 = views[v]
			cam.position = mid + off * (1.6 if not kit.is_empty() else 1.0)
			cam.look_at(mid + (Vector3(0, 0, 0.06) if not kit.is_empty() else Vector3.ZERO), Vector3.UP if v != "top" else Vector3.FORWARD)
			for i in range(5):
				await get_tree().process_frame
			var n := "pistol_%s%s" % [v, "_mods" if not kit.is_empty() else ""]
			get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
			print("pistol_shots: ", n)
		w.queue_free()
		await get_tree().process_frame
	get_tree().quit(0)
