extends Node
## Наклон у стены и свет на свои руки (приёмы Road to Vostok, docs/research/road_to_vostok.md):
## - наклон в стену останавливается — глаз не ближе Balance.LEAN_WALL_RADIUS к стене; без стены — полный;
##   в другую сторону стена не мешает; подошёл к стене в наклоне — глаз отходит вместе с ней;
## - своя вспышка выстрела не светит на свои руки (слой 2), их освещает отдельный короткий свет;
## - отражённый свет фонаря на руки: у стены — почти полная сила, в открытом поле — почти ноль, фонарь выключен — нет.
## tools/godot.cmd --headless res://tools/lean_light_test.tscn

const ID := "wpn_ar_01"

var _fails: int = 0
var _me: Player
var _rig: CameraRig
var _wall: StaticBody3D


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	# своя площадка высоко над картой: вокруг пусто — ни ствол не упирается, ни фонарю отразиться не от чего
	var floor := StaticBody3D.new()
	floor.collision_layer = Hitscan.LAYER_WORLD
	var fs := CollisionShape3D.new()
	var fbox := BoxShape3D.new()
	fbox.size = Vector3(40.0, 1.0, 40.0)
	fs.shape = fbox
	floor.add_child(fs)
	var fmesh := MeshInstance3D.new()
	var fbm := BoxMesh.new()
	fbm.size = fbox.size
	fmesh.mesh = fbm
	floor.add_child(fmesh)
	level.add_child(floor)
	floor.global_position = Vector3(100.0, 299.5, -5.0)
	_me.global_position = Vector3(100.0, 300.05, -5.0)
	_me.velocity = Vector3.ZERO
	CameraRig.first_person_mode = true
	await _arm(false)
	_rig._look_yaw = -PI * 0.5
	_rig._look_pitch = 0.0
	Input.action_press("aim")
	await _wait(1.0)
	_check("от первого лица и в прицеле", _me.ads and _me.aiming, "упор %.2f" % _me.weapon_obstruction)

	await _lean_cases()
	await _flash_cases()
	await _bounce_cases()

	Input.action_release("aim")
	print("lean_light_test: провалено %d" % _fails)
	get_tree().quit(_fails)


# ---------------------------------------------------------------- наклон

func _lean_cases() -> void:
	var right := _right()
	var eye0: Vector3 = _me.global_position + Vector3.UP * (_me._eye_height() + _me._eye_dy)
	# без стены — полный наклон
	var free: float = await _lean_to("camera_right")
	_check("без стены — полный наклон вправо", free > 0.98, "%.2f" % free)
	await _lean_to("")
	# стена справа в 0,4 м от глаза (капсула игрока — 0,35): полный наклон увёл бы глаз на 0,4 м — в стену
	_wall = _make_wall(eye0 + right * (0.40 + 0.05), right)
	await _wait(0.2)
	var blocked: float = await _lean_to("camera_right")
	var gap: float = _gap_to_wall(right)
	_check("стена справа — наклон остановлен", blocked < 0.8 and blocked > 0.4, "%.2f" % blocked)
	_check("глаз не ближе %.2f м к стене" % Balance.LEAN_WALL_RADIUS, gap >= Balance.LEAN_WALL_RADIUS - 0.02, "%.3f м" % gap)
	var other: float = await _lean_to("camera_left")
	_check("влево стена справа не мешает", other < -0.98, "%.2f" % other)
	# стена в 0,6 м — наклон полный; в наклоне стена подъехала до 0,4 м — глаз отходит вместе с ней
	_wall.global_position = eye0 + right * (0.60 + 0.05)
	var far_lean: float = await _lean_to("camera_right")
	_check("стена в 0,6 м — наклон полный", far_lean > 0.98, "%.2f" % far_lean)
	_wall.global_position = eye0 + right * (0.40 + 0.05)
	await _wait(0.3)
	_check("стена подъехала — наклон меньше, глаз не в стене", _me.lean < far_lean - 0.2 and _gap_to_wall(right) >= Balance.LEAN_WALL_RADIUS - 0.02,
		"%.2f → %.2f, зазор %.3f м" % [far_lean, _me.lean, _gap_to_wall(right)])
	await _lean_to("")
	_wall.queue_free()
	_wall = null
	await _wait(0.2)


func _lean_to(action: String) -> float:
	for a: String in ["camera_left", "camera_right"]:
		Input.action_release(a)
	if action != "":
		Input.action_press(action)
	await _wait(0.6)
	return _me.lean


## Расстояние от глаза до плоскости стены (стена — плоскостью с нормалью -side).
func _gap_to_wall(side: Vector3) -> float:
	if _wall == null:
		return INF
	var face: Vector3 = _wall.global_position - side * 0.05
	return (face - _me.eye_position()).dot(side)


func _right() -> Vector3:
	var y: float = _me.body_yaw()
	return Vector3(-cos(y), 0.0, sin(y))


## Стена 0,1 м толщиной, 3 × 3 м, центр в at; тонкая по направлению side (лицо к игроку — at − side × 0,05).
func _make_wall(at: Vector3, side: Vector3) -> StaticBody3D:
	var b := StaticBody3D.new()
	b.collision_layer = Hitscan.LAYER_WORLD
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.1, 3.0, 3.0)
	cs.shape = box
	b.add_child(cs)
	# видимая — для снимков: светлая штукатурка
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = box.size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.62, 0.6, 0.56)
	mat.roughness = 0.9
	bm.material = mat
	mi.mesh = bm
	b.add_child(mi)
	get_tree().current_scene.add_child(b)
	b.global_transform = Transform3D(Basis.looking_at(Vector3.UP.cross(side), Vector3.UP), at)
	return b


# ---------------------------------------------------------------- вспышка

func _flash_cases() -> void:
	await _arm(false)
	await _wait(0.6)
	var muzzle: OmniLight3D = _me._muzzle
	(_me._ws[_me.weapon_slot] as Dictionary)["jam"] = false
	var rounds: int = _me.ammo
	Input.action_press("fire")
	var seen_hands: bool = false
	var world_mask: int = -1
	var t0: int = Time.get_ticks_msec()
	# вспышка горит 0,05 с — ловим каждый кадр, пока не было выстрела и вспышки (до 1,5 с)
	while Time.get_ticks_msec() - t0 < 1500 and not (world_mask >= 0 and seen_hands):
		await get_tree().process_frame
		if muzzle.visible:
			world_mask = muzzle.light_cull_mask
		if _me._hands_flash and _me._hands_flash.visible:
			seen_hands = true
	Input.action_release("fire")
	_check("выстрел был", _me.ammo < rounds, "%d → %d, упор ствола %.2f" % [rounds, _me.ammo, _me.weapon_obstruction])
	_check("своя вспышка в мир не светит на свои руки", world_mask >= 0 and (world_mask & Player.VIEWMODEL_LAYER) == 0,
		"маска %x" % world_mask)
	_check("руки освещает своя вспышка (только слой 2)", seen_hands and _me._hands_flash.light_cull_mask == Player.VIEWMODEL_LAYER)
	await _wait(0.3)
	_check("свет рук от вспышки гаснет", _me._hands_flash and not _me._hands_flash.visible)


# ---------------------------------------------------------------- отражённый свет фонаря

func _bounce_cases() -> void:
	# от бедра: рук в кадре больше, ствол у стены не упирается
	Input.action_release("aim")
	await _arm(true)
	await _wait(0.5)
	if not _me.light_on:
		Input.action_press("flashlight")
		await _wait(0.1)
		Input.action_release("flashlight")
		await _wait(0.3)
	_check("фонарь включён", _me.light_on)
	var cam: Camera3D = get_viewport().get_camera_3d()
	var fwd: Vector3 = -cam.global_basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	await _wait(0.8)
	var open_e: float = _bounce_energy()
	_check("в открытом поле руки почти не освещены", open_e < 0.05, "%.3f" % open_e)
	_wall = _make_wall(cam.global_position + fwd * 1.25, fwd)
	await _wait(0.8)
	var near_e: float = _bounce_energy()
	_check("стена в 1,2 м — отражённый свет на руках", near_e > 0.3, "%.3f" % near_e)
	_check("ствол у стены не упёрся (модель в руках видна)", _rig._viewmodel and _rig._viewmodel.visible, "упор %.2f" % _me.weapon_obstruction)
	_check("свет отражения — только на руки, без теней", _me._hands_bounce.light_cull_mask == Player.VIEWMODEL_LAYER and not _me._hands_bounce.shadow_enabled)
	# снимки (с окном): фонарь у стены — с отражённым светом на руках и без него (как было)
	await _shot("lean_light_torch_after")
	# игрок каждый кадр сам ведёт отражённый свет — «как было» снимаем с пустой маской света
	_me._hands_bounce.light_cull_mask = 0
	await _shot("lean_light_torch_before")
	_me._hands_bounce.light_cull_mask = Player.VIEWMODEL_LAYER
	Input.action_press("flashlight")
	await _wait(0.1)
	Input.action_release("flashlight")
	await _wait(1.0)
	_check("фонарь выключен — отражения нет", not _me.light_on and _bounce_energy() < 0.01, "%.3f" % _bounce_energy())
	await _flash_shots()
	_wall.queue_free()
	_wall = null


## Кадр вспышки (с окном): свет держим, пока снимаем; было — вспышка светит и на руки у дула, стало — мир
## без рук + свой свет рукам.
func _flash_shots() -> void:
	if DisplayServer.get_name() == "headless":
		return
	var m: Vector3 = _me._muzzle_world()
	var f: float = float(_me.spec().flash)
	var world: OmniLight3D = _me._muzzle
	var hands: OmniLight3D = _me._hands_light("flash")
	world.global_position = m
	world.light_energy = 3.0 * f
	world.light_cull_mask = 0xFFFFF
	world.visible = true
	hands.visible = false
	await _shot("lean_light_flash_before", func() -> void: world.visible = true)
	world.light_cull_mask = 0xFFFFF & ~Player.VIEWMODEL_LAYER
	hands.global_position = _me.hands_flash_at(m)
	hands.light_energy = float(Balance.VIEWMODEL_LIGHTS.flash.energy) * f
	hands.visible = true
	await _shot("lean_light_flash_after", func() -> void:
		world.visible = true
		hands.visible = true)
	world.visible = false
	hands.visible = false


## Снимок окна в docs/screens/<name>.png (без окна — ничего); hold — что держать каждый кадр до снимка.
func _shot(name: String, hold: Callable = Callable()) -> void:
	if DisplayServer.get_name() == "headless":
		return
	for i: int in 4:
		if hold.is_valid():
			hold.call()
		await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % name))
	print("снимок ", name)


func _bounce_energy() -> float:
	if _me._hands_bounce == null or not _me._hands_bounce.visible:
		return 0.0
	return _me._hands_bounce.light_energy


# ---------------------------------------------------------------- общее

func _arm(with_light: bool) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	if with_light:
		entry = Gear.fit(entry, ItemDb.make(DozorGear.MOUNT, 1), "side_left")[0]
		entry = Gear.fit(entry, ItemDb.make("tac_flashlight_01", 1), "side_left/light")[0]
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	_me.carry_low = false
	_me.raise_weapon()
	await _wait(0.3)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["OK  " if ok else "FAIL", what, ("  (" + detail + ")") if detail != "" else ""])
