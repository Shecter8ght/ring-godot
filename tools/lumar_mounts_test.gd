extends Node3D
## Угловой ЛУМАР, запасное крепление на цевье и переключение реальным событием СКМ.
## --headless: проверки; LUMAR_CAPTURE=1 с окном: дополнительно снимки VERAS из глаза.

var _fails: int = 0
var _checks: int = 0
var _player: Player
var _camera: CameraRig


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("%s: %s %s" % ["PASS" if ok else "FAIL", label, detail])
	if not ok:
		_fails += 1


func _ready() -> void:
	Engine.max_fps = 60
	Profile.use_file("user://lumar_mounts_test.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_data_checks()
	_build_world()
	await _mount_gallery()
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	_player.name = "Player"
	add_child(_player)
	_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	_camera.target_path = NodePath("../Player")
	add_child(_camera)
	await _equip({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}, "optic_offset": {"id": "optic_holo_01", "dur": 100.0}})
	Input.action_press("aim")
	await get_tree().create_timer(1.2).timeout
	_check("VERAS смотрит через основной LPVO", _camera.scope_active and String(_player.spec().sight) == "primary")
	await _capture("veras_lumar_primary")
	await _middle()
	var angled: String = String(_player.spec().sight)
	_check("СКМ выбирает угловой на кронштейне и сохраняет ПКМ", WeaponBuild.depth(angled) > 0 and _player.aiming and not _camera.scope_active, angled)
	_check_line(angled)
	await _capture("veras_lumar_offset")
	await _middle()
	_check("повторная СКМ возвращает основной", String(_player.spec().sight) == "primary" and _camera.scope_active)
	for mount: String in ["side_right", "side_left"]:
		await _equip({"optic_primary": {"id": "optic_lpvo_01", "dur": 100.0}, mount: {"id": "optic_holo_01", "dur": 100.0}})
		await _middle()
		_check("СКМ выбирает " + mount, String(_player.spec().sight) == mount and _player.aiming and not _camera.scope_active)
		_check_line(mount)
		await _capture("veras_lumar_" + mount)
		var worn_mods: Dictionary = _player.weapon_mods.duplicate(true)
		worn_mods[mount].dur = 0.0
		WeaponMods.update_condition(_camera._viewmodel, worn_mods)
		var part: Node = _camera._viewmodel.find_child("Attachment_" + mount, true, false)
		var reticle: MeshInstance3D = part.find_child("Reticle", true, false) as MeshInstance3D
		_check("сломанный боковой ЛУМАР гаснет " + mount, not reticle.visible)
	Input.action_release("aim")
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
		elif sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
	print("lumar_mounts_test: проверок %d, ошибок %d" % [_checks, _fails])
	get_tree().quit(_fails)


func _data_checks() -> void:
	var base: Dictionary = ItemDb.make("wpn_ar_01", 1)
	for mount: String in ["optic_primary", "side_left", "side_right"]:
		_check("VERAS принимает ЛУМАР: " + mount, WeaponDb.attach_block(base, mount, "optic_holo_01") == "", WeaponDb.attach_block(base, mount, "optic_holo_01"))
	var bracketed: Dictionary = Gear.fit(base, ItemDb.make("mount_offset45_01", 1), "")[0]
	_check("VERAS принимает ЛУМАР на кронштейн 45°", WeaponDb.attach_block(bracketed, "optic_primary/rail", "optic_holo_01") == "")
	var weapon: Dictionary = Gear.fit(base, ItemDb.make("optic_lpvo_01", 1), "optic_primary")[0]
	weapon = Gear.fit(weapon, {"id": "optic_holo_01", "n": 1, "dur": 20.0}, "side_right")[0]
	_check("боковая установка сохраняет износ", float(weapon.mods.side_right.dur) == 20.0)
	_check("боковой коллиматор добавляется к прицелам", WeaponStats.sights_of(weapon) == ["primary", "side_right"])
	var primary: Dictionary = WeaponStats.compute(weapon)
	weapon.sight = "side_right"
	var side: Dictionary = WeaponStats.compute(weapon)
	_check("боковой прицел без кратности LPVO", primary.scoped and not side.scoped and float(side.zoom) == 0.0)
	var stripped: Array = Gear.strip(weapon, "mod:side_right")
	_check("снятие бокового прицела сохраняет ресурс", float(stripped[1].dur) == 20.0 and WeaponStats.active_sight(stripped[0]) == "primary")
	var flashlight: Dictionary = Gear.fit(base, ItemDb.make("tac_flashlight_01", 1), "side_left")[0]
	_check("фонарь не становится прицелом", WeaponStats.sights_of(flashlight) == ["primary"])
	var alone: Dictionary = Gear.fit(base, ItemDb.make("optic_holo_01", 1), "side_left")[0]
	_check("один боковой прицел автоматически активен", WeaponStats.active_sight(alone) == "side_left")
	var inventory: Inventory = Inventory.new()
	add_child(inventory)
	inventory.equipment = {"primary": weapon}
	inventory.apply_weapon_state("primary", {"id": weapon.id, "rev": weapon.rev, "sight": "side_right"})
	_check("хост сохраняет выбранную боковую точку", String(inventory.equipment.primary.sight) == "side_right")
	inventory.apply_weapon_state("primary", {"id": weapon.id, "rev": weapon.rev, "sight": "nonexistent"})
	_check("хост отбрасывает несуществующий прицел", String(inventory.equipment.primary.sight) == "primary")
	Profile.equipment = {"primary": weapon}
	Profile.save()
	Profile._loaded = false
	Profile.ensure()
	_check("выбор и ресурс проходят сохранение", String(Profile.equipment.primary.sight) == "side_right" and float(Profile.equipment.primary.mods.side_right.dur) == 20.0)
	var pair_entry: Dictionary = _legacy_pair("wpn_ar_01", {"optic_primary": {"id": "optic_lpvo_01"}})
	var pair: Node3D = WeaponModels.build("wpn_ar_01", pair_entry.mods)
	var lpvo: Node3D = pair.find_child("Attachment_optic_primary", true, false) as Node3D
	var lumar: Node3D = pair.find_child("Attachment_" + WeaponBuild.node_name(_bracket_sight(pair_entry)), true, false) as Node3D
	var optic: Node3D = lumar.find_child("LUMAR_H1", true, false) as Node3D
	var primary_box: AABB = _bounds(lpvo, pair)
	var lumar_box: AABB = _bounds(optic, pair)
	_check("крупный ЛУМАР не пересекает основную оптику", not primary_box.intersects(lumar_box), str(primary_box) + " / " + str(lumar_box))
	pair.free()
	for wid: String in WeaponDb.weapon_ids():
		for mount: String in ["offset", "side_left", "side_right"]:
			var mods: Dictionary = {mount: {"id": "optic_holo_01", "dur": 20.0}}
			if mount == "offset":
				# угловой — теперь кронштейн на верхней планке с ЛУМАР на нём
				var bracket_entry: Dictionary = _legacy_pair(wid, {})
				if _bracket_sight(bracket_entry) == "":
					continue
				mods = bracket_entry.mods
				(mods[_bracket_sight(bracket_entry)] as Dictionary).dur = 20.0
			elif WeaponDb.attach_block({"id": wid, "mods": {}}, mount, "optic_holo_01") != "":
				continue
			var key: String = _bracket_sight({"mods": mods}) if mount == "offset" else mount
			var model: Node3D = WeaponModels.build(wid, mods, 1)
			var part: Node = model.find_child("Attachment_" + WeaponBuild.node_name(key), true, false)
			var lens: MeshInstance3D = part.find_child("Lens", true, false) as MeshInstance3D if part else null
			_check("геометрия и вид " + wid + ":" + mount, (model.get_meta("sights", {}) as Dictionary).has(key) and lens != null and lens.material_override is ShaderMaterial)
			model.free()
	var probe: CameraRig = CameraRig.new()
	var model: Node3D = WeaponModels.build("wpn_ar_01", {"optic_primary": {"id": "optic_lpvo_01"}, "side_right": {"id": "optic_holo_01"}})
	var start: Vector3 = probe._aim_line(model, "primary", 0.0)
	var halfway: Vector3 = probe._aim_line(model, "side_right", float(Balance.SIGHT_SWITCH_SEC) * 0.5)
	var reversed: Vector3 = probe._aim_line(model, "primary", 0.0)
	_check("переход плавный, повторное нажатие не скачет", halfway.distance_to(start) > 0.01 and reversed.is_equal_approx(halfway))
	probe.free()
	model.free()


## Старая сборка «основной + угловой» → кронштейн на планке с ЛУМАР (как WeaponBuild.upgrade).
func _legacy_pair(wid: String, mods: Dictionary) -> Dictionary:
	var legacy: Dictionary = mods.duplicate(true)
	legacy["optic_offset"] = {"id": "optic_holo_01", "dur": 100.0}
	return WeaponBuild.upgrade({"id": wid, "n": 1, "mods": legacy, "sight": "primary"})[0]


## Прицел на кронштейне в сборке ("" — нет).
func _bracket_sight(entry: Dictionary) -> String:
	for k: Variant in entry.get("mods", {}):
		if WeaponBuild.depth(String(k)) > 0:
			return String(k)
	return ""


func _equip(mods: Dictionary) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	var entry: Dictionary = WeaponBuild.upgrade({"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": mods, "sight": "primary"})[0]
	_player.sandbox_weapons[slot] = {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": entry.mods,
		"mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}, "sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.7).timeout


func _middle() -> void:
	var button: InputEventMouseButton = InputEventMouseButton.new()
	button.button_index = MOUSE_BUTTON_MIDDLE
	button.pressed = true
	Input.parse_input_event(button)
	await get_tree().process_frame
	button = button.duplicate() as InputEventMouseButton
	button.pressed = false
	Input.parse_input_event(button)
	await get_tree().create_timer(0.7).timeout


func _check_line(sight: String) -> void:
	var part: Node = _camera._viewmodel.find_child("Attachment_" + WeaponBuild.node_name(WeaponStats.sight_mount(sight)), true, false)
	var axis: Node3D = part.find_child("SightAxis", true, false) as Node3D
	var point: Vector3 = _camera._vm_space.global_transform.affine_inverse() * axis.global_position
	var direction: Vector3 = (_camera._vm_space.global_basis.inverse() * axis.global_basis.z).normalized()
	_check("окно на оси взгляда " + sight, Vector2(point.x, point.y).length() < 0.003 and direction.dot(Vector3.FORWARD) > 0.999, str(point))


func _build_world() -> void:
	var world: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.18, 0.21, 0.24)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_energy = 0.8
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	world.environment = env
	add_child(world)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -30, 0)
	light.light_energy = 2.0
	add_child(light)
	var body: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(30, 0.3, 30)
	collision.shape = shape
	collision.position.y = -0.15
	body.add_child(collision)
	add_child(body)
	var target: MeshInstance3D = MeshInstance3D.new()
	var quad: QuadMesh = QuadMesh.new()
	quad.size = Vector2(6.0, 6.0)
	target.mesh = quad
	target.position = Vector3(0, 1.6, 12)
	target.rotation.y = PI
	var checker: Shader = Shader.new()
	checker.code = "shader_type spatial; render_mode unshaded, cull_disabled; void fragment() { float c = mod(floor(UV.x*12.0)+floor(UV.y*12.0), 2.0); ALBEDO = mix(vec3(0.12), vec3(0.8,0.75,0.65), c); }"
	var target_material: ShaderMaterial = ShaderMaterial.new()
	target_material.shader = checker
	target.material_override = target_material
	add_child(target)


func _bounds(part: Node3D, root: Node3D) -> AABB:
	var box: AABB = AABB()
	var first: bool = true
	for raw: Node in part.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		if not mesh.visible:
			continue
		var relative: Transform3D = mesh.transform
		var parent: Node = mesh.get_parent()
		while parent != null and parent != root:
			if parent is Node3D:
				relative = (parent as Node3D).transform * relative
			parent = parent.get_parent()
		var bounds: AABB = relative * mesh.get_aabb()
		box = bounds if first else box.merge(bounds)
		first = false
	return box


func _mount_gallery() -> void:
	if OS.get_environment("LUMAR_CAPTURE") != "1":
		return
	var camera: Camera3D = Camera3D.new()
	camera.fov = 32.0
	camera.near = 0.005
	add_child(camera)
	camera.current = true
	for mount: String in ["optic_offset", "side_right"]:
		var model: Node3D = WeaponModels.build("wpn_ar_01", {"optic_primary": {"id": "optic_lpvo_01"}, mount: {"id": "optic_holo_01"}})
		add_child(model)
		model.position = Vector3(0, 0.8, 0)
		camera.look_at_from_position(Vector3(-0.7, 1.24, -0.35), Vector3(0, 0.88, 0.18))
		await get_tree().create_timer(0.3).timeout
		await _capture("veras_lumar_mount_" + mount)
		model.queue_free()
		await get_tree().process_frame
	camera.queue_free()
	await get_tree().process_frame


func _capture(label: String) -> void:
	if OS.get_environment("LUMAR_CAPTURE") != "1":
		return
	if is_instance_valid(_camera):
		_camera._look_yaw = 0.0
		_camera._look_pitch = 0.0
		await get_tree().process_frame
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/" + label + ".png"))
