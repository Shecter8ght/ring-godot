extends Node
## Проверка мародёра без рук: шум шагов → расследование → зрение → бой → выстрелы;
## затем игрок стреляет в мародёра. Печатает состояния и здоровье.
## godot --path . res://tools/ai_test.tscn

const LEVEL := "res://scenes/levels/f1_market.tscn"


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	var level := inst
	while level.get_node_or_null("Marauders") == null:
		await get_tree().process_frame
	await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	var m := level.get_node("Marauders").get_child(0) as Marauder
	player.health.hp = 100000.0  # чтобы дожить до проверки своих выстрелов
	(m.get_node("Health") as Health).damaged.connect(func(amount: float, from: Vector3) -> void:
		print("    мародёр получил %.0f урона, источник в %.1f м от игрока, t=%.1f" % [amount, from.distance_to(player.global_position), Time.get_ticks_msec() / 1000.0]))
	print("    старт t=%.1f" % (Time.get_ticks_msec() / 1000.0))
	# Дверь: встать в зону, нажать F, проверить, что открылась.
	var spawn_pos := player.global_position
	var door := level.get_node("f1_market/Doors").get_child(0) as Door
	player.global_position = door.global_position + door.global_basis.x * (door.width * 0.5) + door.global_basis.z * 0.9 + Vector3.UP * 0.05
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_press("interact")
	await get_tree().process_frame
	Input.action_release("interact")
	await _wait(0.5)
	print("[дверь] %s: открыта = %s, угол створки %.0f°" % [door.name, door.is_open, rad_to_deg(door.get_node("Leaf").rotation.y)])
	player.global_position = spawn_pos
	await get_tree().physics_frame
	# Мародёр в 9 м от игрока, спиной к нему — увидеть не может, но услышит бег.
	var away := (player.global_position - Vector3.ZERO).normalized()
	m.global_position = player.global_position + away * 9.0 + Vector3(0, 0.1, 0)
	m._facing = atan2(away.x, away.z)
	m.state = Marauder.State.PATROL
	await get_tree().physics_frame
	print("[0] мародёр %s, дист %.1f, видит-ли (спиной): %s" % [_state(m), m.global_position.distance_to(player.global_position), _sees(m, player)])
	# бег на месте 1.5 с — шум
	Input.action_press("move_forward")
	Input.action_press("sprint")
	await _wait(1.5)
	Input.action_release("move_forward")
	Input.action_release("sprint")
	print("[1] после бега: %s, last_known дист до игрока %.1f" % [_state(m), m.last_known.distance_to(player.global_position)])
	await _wait(4.0)
	print("[2] через 4 с: %s, HP игрока %d, дист %.1f" % [_state(m), int(player.health.hp), m.global_position.distance_to(player.global_position)])
	await _wait(1.2)
	await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/ai_combat.png"))
	await _wait(2.8)
	print("[3] через 8 с: %s, HP игрока %d" % [_state(m), int(player.health.hp)])
	# игрок стреляет: курсор на мародёра
	var cam := get_viewport().get_camera_3d()
	var hp0 := (m.get_node("Health") as Health).hp
	for i in range(6):
		var scr := cam.unproject_position(m.global_position + Vector3.UP * 1.2)
		Input.warp_mouse(scr)
		Input.action_press("fire")
		await _wait(0.3)
		Input.action_release("fire")
		await get_tree().process_frame
	print("    курсор на земле: %.1f м от мародёра; прямой луч в мародёра: %s" % [player.cursor_ground.distance_to(m.global_position), _probe(player, m)])
	print("[4] игрок сделал 6 выстрелов: HP мародёра %d -> %d, патронов %d, состояние %s" % [int(hp0), int((m.get_node("Health") as Health).hp), player.ammo, _state(m)])
	get_tree().quit(0)


func _probe(p: Player, m: Marauder) -> String:
	var from := p.global_position + Vector3.UP * 1.3
	var to := m.global_position + Vector3.UP * 1.2
	var ex: Array[RID] = [p.get_rid()]
	var rng := RandomNumberGenerator.new()
	var hit := Hitscan.fire(p.get_world_3d(), from, (to - from).normalized(), 0.0, 60.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER, 0.0, ex, rng)
	if hit.has("collider"):
		return "попал в %s (%s) на %.1f м" % [hit.collider.name, hit.collider.get_class(), from.distance_to(hit.position)]
	return "промах"


func _sees(m: Marauder, p: Player) -> bool:
	var eye := m.global_position + Vector3.UP * Marauder.EYE_HEIGHT
	var fwd := Vector3(sin(m._facing), 0.0, cos(m._facing))
	var ex: Array[RID] = [m.get_rid()]
	return Perception.can_see(m.get_world_3d(), eye, fwd, p, ex)


func _state(m: Marauder) -> String:
	return Marauder.State.keys()[m.state]


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout
