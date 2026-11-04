extends Node3D
## Permanent equipment, death/extraction, and an actual dual-viewport FPS camera.
var failures: int = 0
var me: Player
var rig: CameraRig

func check(ok: bool, title: String) -> void:
	print("PHONE ", "PASS " if ok else "FAIL ", title)
	if not ok: failures += 1

func count_phone(list: Array) -> int:
	return list.filter(func(e: Dictionary) -> bool: return PhoneGear.personal(e)).size()

func frames(n: int) -> void:
	for i: int in range(n): await get_tree().process_frame

func authored_pose(title: String) -> void:
	check(not Phone._authored_pose.is_empty(), title + " uses Blender pose")
	var sk := Phone.arms.skeleton
	var frame := Phone.model.global_transform.affine_inverse() * sk.global_transform
	var worst_position: float = 0.0
	var worst_basis: float = 0.0
	for entry: Dictionary in Phone._authored_pose.get("runtime_bones", []):
		var actual := frame * sk.get_bone_global_pose(int(entry.bone))
		var expected: Transform3D = entry.transform
		worst_position = maxf(worst_position, actual.origin.distance_to(expected.origin))
		for axis: int in range(3): worst_basis = maxf(worst_basis, actual.basis[axis].distance_to(expected.basis[axis]))
	check(worst_position < 0.00001 and worst_basis < 0.00001, title + " preserves owner bone transforms")
	var hand := sk.find_bone("mixamorig_RightHand")
	var scale := sk.get_bone_global_pose(hand).basis.get_scale()
	check(scale.distance_to(Vector3.ONE * 0.8) < 0.00001, title + " keeps 80 percent hands without double scaling")

func _ready() -> void:
	Profile.use_file("user://personal_phone_test.json", true)
	Profile.ensure()
	Profile.flags[PhoneGear.FLAG] = true
	PhoneGear.ensure_profile()
	check(count_phone(Profile.backpack) == 1, "one phone after unlock")
	PhoneGear.ensure_profile()
	check(count_phone(Profile.backpack) == 1, "repeated grants do not duplicate")
	var idx: int = -1
	for i: int in Profile.backpack.size():
		if PhoneGear.personal(Profile.backpack[i]): idx = i
	check(not Profile.sell(idx, 1, "backpack"), "cannot sell personal phone")
	check(not Profile.discard("backpack", idx), "cannot discard personal phone")
	check(not Profile.backpack_to_stash(idx, 1), "phone stays with its owner")
	var lo := Profile.take_loadout()
	check(count_phone(lo.backpack) == 1 and count_phone(Profile.backpack) == 1, "raid loadout and retained profile equipment")
	var inv := Inventory.new()
	add_child(inv)
	inv.items = (lo.backpack as Array).duplicate(true)
	check(inv.remove(PhoneGear.ID, 1) == 0, "cannot remove by item id")
	check(inv.take_entry("backpack", 0).is_empty(), "cannot drop phone entry")
	var corpse := inv.take_all()
	check(count_phone(corpse) == 0, "corpse contains no duplicate phone")
	check(count_phone(Profile.backpack) == 1, "phone survives death without accepting quest again")
	Profile.return_loadout({}, lo.backpack)
	check(count_phone(Profile.backpack) == 1, "extraction returns exactly one phone")
	check(ItemDb.size(PhoneGear.ID) == Vector2i(1, 2), "inventory footprint 1x2")
	Profile.backpack = []; Profile.stash = []; Profile.equipment = {}
	var capacity := Profile.grid_of("backpack").x * Profile.grid_of("backpack").y
	for i: int in capacity: ItemDb.add_to(Profile.backpack, ItemDb.make("phone", 1), Profile.grid_of("backpack"))
	PhoneGear.ensure_profile()
	var retained_loot: int = 0
	for entry: Dictionary in Profile.backpack + Profile.stash:
		if String(entry.id) == "phone": retained_loot += int(entry.n)
	check(retained_loot == capacity and count_phone(Profile.backpack) == 1, "full old loadout migrates without losing loot")
	if DisplayServer.get_name() == "headless":
		print("PHONE GEAR failures ", failures)
		get_tree().quit(1 if failures else 0)
		return
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR; env.background_color = Color(0.16, 0.21, 0.28)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.75, 0.82, 0.95); env.ambient_light_energy = 0.7
	environment.environment = env; add_child(environment)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-45, -35, 0); add_child(sun)
	var floor_body := StaticBody3D.new()
	floor_body.collision_layer = 1
	var floor_shape := CollisionShape3D.new(); var shape := BoxShape3D.new(); shape.size = Vector3(30, 0.2, 30)
	floor_shape.shape = shape; floor_shape.position.y = -0.1; floor_body.add_child(floor_shape); add_child(floor_body)
	for i: int in 7:
		var mesh := MeshInstance3D.new(); var box := BoxMesh.new(); box.size = Vector3(0.7, 1.5 + i * 0.1, 0.7)
		mesh.mesh = box; mesh.position = Vector3((i - 3) * 1.1, 0.75, 4 + (i % 2) * 0.8)
		var material := StandardMaterial3D.new(); material.albedo_color = Color.from_hsv(float(i) / 7, 0.65, 0.8)
		mesh.material_override = material; add_child(mesh)
	rig = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(rig)
	me = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(me); me.position = Vector3(0, 0.15, 0); me.health.invulnerable = true
	me.inventory.items = (lo.backpack as Array).duplicate(true)
	rig.set_target(me); rig.first_person_mode = true
	await frames(90)
	Phone.set_active(true)
	await frames(60)
	check(Phone.active, "V device can be equipped")
	check(Phone.blocks_combat(me), "phone blocks weapon input")
	check(Phone.finder.world_3d == rig._ads_cam.get_world_3d(), "viewfinder shares actual world")
	check((Phone.lens.cull_mask & 2) == 0, "capture excludes phone and arms")
	check(Phone.model.screen.material_override.albedo_texture == Phone.screen_viewport.get_texture(), "physical screen uses independent UI viewport")
	check(Phone.arms.visible and Phone.arms.max_grip_error < 0.01, "right hand is present at device")
	authored_pose("held")
	await shot("camera")
	var shot_before := me.last_shot_ms
	Input.action_press("fire"); await frames(5); Input.action_release("fire")
	check(me.last_shot_ms == shot_before, "shutter never shoots weapon")
	var before: int = Phone._photos.size()
	await Phone.capture()
	await frames(4)
	check(Phone._photos.size() == before + 1, "real viewfinder capture saved")
	authored_pose("after shutter")
	Phone._set_zoom(2.0)
	check(Phone.lens.fov < 35, "2x changes capture lens FOV")
	# Use an actual projected mouse click on the physical display's gallery tab.
	var toggle := InputEventMouseButton.new(); toggle.button_index = MOUSE_BUTTON_MIDDLE; toggle.pressed = true
	Input.parse_input_event(toggle)
	await frames(2)
	check(Phone.pointer, "middle button enters display control")
	toggle = toggle.duplicate(); toggle.pressed = false; Input.parse_input_event(toggle)
	await frames(30)
	authored_pose("reading")
	var display: MeshInstance3D = Phone.model.screen
	var box := display.get_aabb()
	var point := Vector3(box.position.x + box.size.x * 0.375, box.end.y - box.size.y * 0.95, box.position.z)
	var click := InputEventMouseButton.new(); click.button_index = MOUSE_BUTTON_LEFT; click.pressed = true
	click.position = rig._ads_cam.unproject_position(display.to_global(point))
	Input.parse_input_event(click)
	await frames(2)
	click = click.duplicate(); click.pressed = false; Input.parse_input_event(click)
	await frames(3)
	check(Phone.screen_ui.app == "Снимки", "projected click opens gallery on device")
	var stamp := Time.get_ticks_usec()
	await frames(60)
	print("PHONE FRAME average ms with device: ", float(Time.get_ticks_usec() - stamp) / 60000.0)
	for app: String in ["Снимки", "Заказы", "Связь"]:
		Phone.screen_ui.select(app); Phone.pointer = true; await frames(30)
		await shot({"Снимки":"gallery", "Заказы":"orders", "Связь":"messages"}[app])
	Phone.close(); await frames(4)
	check(not Phone.active and not is_instance_valid(Phone.holder), "stow frees extra viewport/model")
	Phone.set_active(true); await frames(6)
	check(Phone._photos.size() == before + 1, "gallery survives stow/reopen")
	authored_pose("re-equipped")
	Phone.close()
	print("PHONE FUNCTIONAL failures ", failures)
	get_tree().quit(1 if failures else 0)

func shot(tag: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/quest_phone_fps_%s.png" % tag)
