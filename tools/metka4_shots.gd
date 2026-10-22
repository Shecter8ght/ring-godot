extends Node3D
## Проверочные кадры принятой модели в Forward+: предмет, крепления и игровой конструктор.

func _ready() -> void:
	Engine.max_fps = 60
	Profile.use_file("user://metka4_shots.json", true)
	var world: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.23, 0.245, 0.26)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.75, 0.8, 0.88)
	environment.ambient_light_energy = 0.65
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.ssao_enabled = true
	environment.ssao_radius = 0.025
	world.environment = environment
	add_child(world)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-45, -35, 0)
	key.light_energy = 2.4
	add_child(key)
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, 145, 0)
	fill.light_energy = 0.8
	fill.light_color = Color(0.78, 0.85, 1.0)
	add_child(fill)
	var camera: Camera3D = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.near = 0.002
	camera.far = 10
	add_child(camera)
	camera.current = true
	var item: Node3D = ItemModels.build(Metka4Model.ID)
	add_child(item)
	var box: AABB = ItemModels.bounds(item)
	var center: Vector3 = box.get_center()
	camera.size = 0.165
	camera.look_at_from_position(center + Vector3(-0.12, 0.17, 0.16), center)
	await _shot("item")
	item.free()
	var entry: Dictionary = ItemDb.make("wpn_ar_01", 1)
	var fitted: Array = WeaponBuild.insert(entry, "top_front", ItemDb.make(Metka4Model.ID, 1), 3)
	entry = fitted[0]
	var options: Array[Dictionary] = AttachmentRemote.options(String(entry.id), entry.mods, "top_front")
	for choice: Dictionary in options:
		if String(choice.point) == "side_left":
			entry.mods.top_front.remote = {"point": "side_left", "slot": int(choice.slot), "reverse": bool(choice.reverse)}
			break
	var weapon: Node3D = WeaponModels.build(String(entry.id), entry.mods)
	add_child(weapon)
	camera.size = 0.24
	center = Vector3(0, 0.095, 0.32)
	camera.look_at_from_position(center + Vector3(0.25, 0.19, 0.17), center)
	await _shot("mounted")
	camera.look_at_from_position(center + Vector3(-0.19, 0.04, -0.15), center)
	await _shot("cable")
	weapon.free()
	var bracket: Dictionary = WeaponBuild.insert(ItemDb.make("wpn_ar_01", 1), "optic_primary", ItemDb.make("mount_offset45_01", 1), 4)[0]
	var angled: Dictionary = Gear.fit(bracket, ItemDb.make("optic_holo_01", 1), "optic_primary/rail")[0]
	var lumar_gun: Node3D = WeaponModels.build("wpn_ar_01", angled.mods, -1)
	add_child(lumar_gun)
	center = Vector3(-0.01, 0.135, 0.09)
	camera.size = 0.17
	camera.look_at_from_position(center + Vector3(-0.18, 0.12, -0.16), center)
	await _shot("lumar45")
	lumar_gun.free()
	Profile.equipment = {"primary": entry}
	Profile.modules["workbench"] = 2
	Profile.money = 100000
	var builder: WeaponBuilder = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await get_tree().process_frame
	builder._sel = "top_front"
	builder._refresh()
	await _shot("builder")
	builder._draft["optic_primary"] = {"id": "optic_holo_01", "src": {"from": "shop"}}
	builder._refresh()
	await _shot("warning")
	builder.queue_free()
	await get_tree().process_frame
	get_tree().quit()


func _shot(label: String) -> void:
	for i: int in range(8):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/metka4_%s.png" % label
	var error: Error = get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	print("METKA4_SHOT ", label, " ", error)
