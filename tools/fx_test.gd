extends Node
## Проверка эффектов попаданий: стреляем по витрине, стене, роллете, мародёру и делаем два снимка —
## в момент частиц и через секунду (декали). godot --path . res://tools/fx_test.tscn

const LEVEL := "res://scenes/levels/f1_market.tscn"


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	while inst.get_node_or_null("Marauders") == null:
		await get_tree().process_frame
	await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 100000.0
	player.global_position = SectorBuilder.polar(-19.0, 29.5) + Vector3(0, 0.05, 0)
	var m := inst.get_node("Marauders").get_child(0) as Marauder
	m.global_position = SectorBuilder.polar(-16.5, 30.0) + Vector3(0, 0.1, 0)
	m.set_physics_process(false)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var cam := get_viewport().get_camera_3d()
	# камера ближе, чтобы разглядеть
	(get_tree().get_first_node_in_group("camera_rig") as CameraRig)._distance = 18.0
	for other in inst.get_node("Marauders").get_children():
		if other != m:
			(other as Marauder).queue_free()
	# цели: стекло витрины, вывеска/стена над ней, ригель, колонна колоннады, мародёр
	var targets := [
		SectorBuilder.polar(-20.5, 33.0) + Vector3(0, 1.4, 0),
		SectorBuilder.polar(-21.5, 33.0) + Vector3(0, 1.0, 0),
		SectorBuilder.polar(-19.0, 33.0) + Vector3(0, 2.0, 0),
		SectorBuilder.polar(-18.0, 33.0) + Vector3(0, 5.0, 0),
		SectorBuilder.polar(-19.0, 25.0) + Vector3(0, 1.2, 0),
		m.global_position + Vector3(0, 1.1, 0),
		m.global_position + Vector3(0, 1.3, 0),
	]
	for t in targets:
		for k in range(3):
			await get_tree().process_frame
		Input.warp_mouse(cam.unproject_position(t))
		await get_tree().process_frame
		await get_tree().process_frame
		player.ammo = 8
		Input.action_press("fire")
		await get_tree().process_frame
		await get_tree().process_frame
		Input.action_release("fire")
		print("  выстрел в %s -> курсор на теле: %s" % [t, player.cursor_body != Vector3.ZERO])
		await get_tree().create_timer(0.12).timeout
	await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/fx_particles.png"))
	await get_tree().create_timer(1.2).timeout
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/fx_decals.png"))
	(get_tree().get_first_node_in_group("camera_rig") as CameraRig)._distance = 28.0
	await get_tree().create_timer(1.0).timeout
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/fx_decals_far.png"))
	var decals := 0
	for c in inst.get_children():
		if c is Decal:
			decals += 1
			print("  декаль %s размер %.2f нормаль %s" % [c.global_position, c.size.x, c.global_basis.y])
	print("fx: снимки сохранены, декалей %d" % decals)
	get_tree().quit(0)
