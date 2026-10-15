extends Node3D
## Проверяет реальные Player/CameraRig, расход и физику. С окном сохраняет три рабочих кадра.

var _fails: int = 0
var _checks: int = 0
var _me: Player
var _camera: CameraRig


func _ready() -> void:
	Engine.max_fps = 60
	get_tree().create_timer(50.0).timeout.connect(func() -> void: get_tree().quit(99))
	Profile.use_file("user://profile_grenade_hand_test.json", true)
	Profile.ensure()
	Profile.pending_raid = false
	RaidEvents.enabled = false
	_build_stage()
	_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(_camera)
	_me = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	_me.name = "Player_1"
	_me.position = Vector3(0, 0.02, 0)
	add_child(_me)
	_me.health.invulnerable = true
	_me.set_physics_process(false)
	_camera.set_target(_me)
	_me.ads = true
	_me.look_yaw = PI
	_camera._look_yaw = PI
	_me._switch(String(_me.weapon_keys()[0]), false)
	await _frames(8)
	var gun: String = _me.weapon_id
	var rounds: int = _me.ammo
	var count: int = _me.grenade_count()
	await _tap("grenade")
	_check("4 выбирает гранату, слоты и патроны оружия сохранены", _me.grenade_equipped and _me.weapon_id == "" and _me.ammo == rounds)
	_check("руки с гранатой заняты", not _me.hands_free())
	await _frames(5)
	_check("CameraRig действительно показывает гранату и существующие руки", _camera._viewmodel is GrenadeModel and _camera._viewmodel.visible and _camera._arms.visible)
	var model: GrenadeModel = _camera._viewmodel as GrenadeModel
	_check("загружен игровой ассет, не запасная модель", bool(model.get_meta("asset_loaded", false)))
	_check("семь деталей и морф сжатия концов чеки импортированы", model.find_children("*", "MeshInstance3D", true, false).size() == 7 and model._pin_mesh.mesh.get_blend_shape_count() == 1)
	var home: Vector3 = model._pin.position
	model.prepare(1.0)
	_check("чека с кольцом извлекается на 52 мм, скоба остаётся прижата", absf(model._pin.position.distance_to(home) - 0.052) < 0.0001 and model._lever.rotation == model._lever_home)
	model.prepare(0.0)
	await _shot("grenade_hand_idle")
	_me._combat(0.5)
	await _frames(1)
	Input.action_press("fire")
	_me._combat(0.02)
	_me._combat(0.15)
	_check("пока ЛКМ зажата, граната не расходуется и не создаётся", _me.grenade_count() == count and _grenades().is_empty())
	PauseMenu.shown = true
	_me._combat(0.1)
	PauseMenu.shown = false
	Input.action_release("fire")
	_check("меню отменяет подготовку без расхода", _me.grenade_pin == 0.0 and _me.grenade_count() == count)
	await _frames(1)
	_me._combat(0.1)
	Input.action_press("fire")
	_me._combat(0.01)
	Input.action_release("fire")
	_me._combat(0.01)
	_check("быстрый клик ждёт извлечения чеки", _grenades().is_empty())
	_me._combat(0.3)
	_check("отпускание ЛКМ — один верхний бросок и одна граната из запаса", _grenades().size() == 1 and _me.grenade_count() == count - 1)
	var weak_speed: float = (_grenades()[0] as Grenade).linear_velocity.length()
	_clear_grenades()
	await get_tree().create_timer(0.7).timeout
	_me._combat(1.0)
	_me._combat(0.01)
	await _frames(1)
	Input.action_press("fire")
	_me._combat(0.01)
	_me._combat(1.3)
	_check("длительное удержание достигло предельной силы", is_equal_approx(_me.grenade_charge, 1.0))
	await _shot("grenade_hand_over")
	Input.action_release("fire")
	_me._combat(0.01)
	_check("сильный верхний бросок быстрее короткого", _grenades().size() == 1 and (_grenades()[0] as Grenade).linear_velocity.length() > weak_speed + 3.0)
	if _grenades().is_empty():
		get_tree().quit(1)
		return
	var over_velocity: Vector3 = (_grenades()[0] as Grenade).linear_velocity
	var over_height: float = (_grenades()[0] as Grenade).position.y
	_clear_grenades()
	await get_tree().create_timer(0.7).timeout
	_me._combat(1.0)
	_me._combat(0.01)
	await _frames(1)
	Input.action_press("aim")
	_me._combat(0.01)
	_me._combat(1.3)
	_check("ПКМ готовит подброс, не включает прицел оружия", _me.grenade_underhand and not _me.aiming)
	await _shot("grenade_hand_under")
	Input.action_release("aim")
	_me._combat(0.01)
	_check("подброс снизу ниже и слабее верхнего", _grenades().size() == 1 and (_grenades()[0] as Grenade).linear_velocity.length() < over_velocity.length() and (_grenades()[0] as Grenade).position.y < over_height - 0.3)
	_check("последняя граната возвращает прежнее оружие с прежними патронами", _me.grenade_count() == 0 and not _me.grenade_equipped and _me.weapon_id == gun and _me.ammo == rounds)
	_clear_grenades()
	await _frames(2)
	_me._equip_grenade()
	_check("пустой запас не убирает оружие", not _me.grenade_equipped and _me.weapon_id == gun)
	_me.grenades = 2
	Input.action_press("fire")
	_me._equip_grenade()
	_me._combat(0.5)
	_check("зажатый до выбора спуск не готовит гранату", _me.grenade_pin == 0.0 and _me.grenade_count() == 2)
	Input.action_release("fire")
	_me._combat(0.01)
	await _frames(1)
	Input.action_press("fire")
	_me._combat(0.2)
	_me._switch(String(_me.weapon_keys()[1]), false)
	Input.action_release("fire")
	_me._combat(0.1)
	_check("смена оружия с зажатой ЛКМ отменяет бросок", _grenades().is_empty() and _me.grenade_count() == 2 and not _me.grenade_equipped)
	_check("подсказки траектории и радиуса не создаются", _me.find_child("GrenadeAim", true, false) == null)
	# Реальный полёт до первого касания: одинаковый взгляд, разная сила/тип броска.
	var short_range: float = await _flight(0.0, false)
	var long_range: float = await _flight(1.0, false)
	var under_range: float = await _flight(1.0, true)
	_check("удержание увеличивает реальную дальность, снизу — короткая дуга", long_range > short_range + 5.0 and under_range < long_range * 0.6, "%.2f / %.2f / %.2f м" % [short_range, long_range, under_range])
	var wall: StaticBody3D = StaticBody3D.new()
	var wall_collision: CollisionShape3D = CollisionShape3D.new()
	var wall_shape: BoxShape3D = BoxShape3D.new()
	wall_shape.size = Vector3(2.0, 4.0, 0.04)
	wall_collision.shape = wall_shape
	wall.add_child(wall_collision)
	wall.position = Vector3(0, 1.5, -0.16)
	add_child(wall)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var blocked_launch: Array = _me._grenade_launch(1.0, false, Vector3.FORWARD)
	_check("у стены граната появляется перед преградой", (blocked_launch[0] as Vector3).z > -0.14)
	wall.queue_free()
	await _frames(2)
	# Расход снаряжения проходит через Inventory, а не через песочничный счётчик.
	_me.loadout_mode = true
	_me.inventory.items = [ItemDb.make("grenade", 1)]
	_me.inventory.loadout_ready = true
	_me._equip_grenade()
	_me._grenade_host_ms = -10000
	_me._grenade_seq += 1
	_me._server_grenade_throw(_me._grenade_seq, 0.5, false, Vector3.FORWARD)
	_me._server_grenade_throw(_me._grenade_seq, 0.5, false, Vector3.FORWARD)
	_check("повтор операции хоста не размножает гранату и списывает один предмет", _me.inventory.count("grenade") == 0 and _grenades().size() == 1)
	_clear_grenades()
	print("grenade_hand_test: проверок %d, провалено %d" % [_checks, _fails])
	await _cleanup()
	get_tree().quit(1 if _fails else 0)


func _flight(power: float, under: bool) -> float:
	var launch: Array = _me._grenade_launch(power, under, Vector3.FORWARD)
	var grenade: Grenade = Grenade.throw(self, launch[0], launch[1], _me.get_rid(), false)
	grenade._fuse = 100.0
	var start: Vector3 = grenade.global_position
	var travel: float = 0.0
	for frame: int in range(240):
		await get_tree().physics_frame
		travel = Vector2(grenade.global_position.x - start.x, grenade.global_position.z - start.z).length()
		if grenade.get_contact_count() > 0:
			break
	grenade.queue_free()
	await _frames(2)
	return travel


func _tap(action: String) -> void:
	Input.action_press(action)
	_me._combat(0.01)
	await _frames(1)
	Input.action_release(action)
	_me._combat(0.4)
	await _frames(1)


func _grenades() -> Array[Node]:
	return get_tree().get_nodes_in_group("thrown_grenades")


func _clear_grenades() -> void:
	for grenade: Node in _grenades():
		grenade.queue_free()


func _check(label: String, ok: bool, note: String = "") -> void:
	_checks += 1
	if not ok:
		_fails += 1
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", label, note])


func _frames(count: int) -> void:
	for frame: int in range(count):
		await get_tree().process_frame


func _shot(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await _frames(3)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/" + label + ".png")


func _build_stage() -> void:
	var body: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(100, 0.2, 100)
	collision.shape = shape
	collision.position.y = -0.1
	body.add_child(collision)
	add_child(body)
	var floor_mesh: MeshInstance3D = MeshInstance3D.new()
	var plane: PlaneMesh = PlaneMesh.new()
	plane.size = Vector2(100, 100)
	floor_mesh.mesh = plane
	body.add_child(floor_mesh)
	var environment_node: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.18, 0.22, 0.28)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_energy = 0.65
	environment.ambient_light_color = Color(0.75, 0.83, 1.0)
	environment_node.environment = environment
	add_child(environment_node)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -30, 0)
	light.light_energy = 1.8
	add_child(light)


func _cleanup() -> void:
	Input.action_release("fire")
	Input.action_release("aim")
	PauseMenu.shown = false
	for child: Node in get_children():
		child.queue_free()
	await _frames(4)
