extends Node
## Реальные точки лута двора зоны 1: вид от первого лица и вещь в рюкзаке.


func _ready() -> void:
	if name != "ValuableShotsRunner":
		var runner: Node = Node.new()
		runner.name = "ValuableShotsRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	Profile.use_file("user://valuable_shots.json", true)
	Profile.from_hideout = true
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = []
	Profile.pending_raid = true
	Profile.save()
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	get_tree().change_scene_to_file("res://scenes/levels/zone01_mall.tscn")
	for frame: int in range(40):
		await get_tree().process_frame
	var level: Node3D = get_tree().current_scene as Node3D
	while not bool(level.get("_nav_baked")):
		await get_tree().create_timer(0.1).timeout
	var point: LooseLoot = level.find_child("Found_00", true, false) as LooseLoot
	var player: Player = Raid.current.local_player()
	player.health.hp = 100
	player.set_physics_process(false)
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
	var cam: Camera3D = get_viewport().get_camera_3d()
	# Отключить управление камерой: кадр находится на высоте глаз рядом со скамейкой.
	var rig: Node = level.get_node("CameraRig")
	rig.set_process(false)
	rig.set_physics_process(false)
	var eye: Vector3 = point.global_position + Vector3(0.95, 1.15, 1.1)
	player.global_position = eye - Vector3.UP * 1.5
	cam.global_position = eye
	cam.look_at(point.global_position + Vector3.UP * 0.18)
	for id: String in ["smartphone_business", "photo_camera_pro", "gpu_compute"]:
		var entry: Dictionary = ItemDb.make(id, 1)
		entry["fir"] = true
		point.items = [entry]
		await shot("valuable_world_" + id)
	# Найти свободную площадку реальной карты и вызвать доставку штатным действием.
	var pos: Vector3 = Vector3.INF
	for x: int in range(-15, 16, 5):
		for z: int in range(-15, 16, 5):
			var candidate: Vector3 = point.global_position + Vector3(x, 0, z)
			var ground: Dictionary = level.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(candidate + Vector3.UP * 3, candidate - Vector3.UP * 4, Hitscan.LAYER_WORLD))
			if ground.is_empty():
				continue
			player.global_position = ground.position + Vector3.UP * 0.1
			pos = Raid.current._supply_site(player)
			if pos.is_finite():
				break
		if pos.is_finite():
			break
	if not pos.is_finite():
		push_error("На реальной карте не найдена свободная площадка")
		get_tree().quit(1)
		return
	player.inventory.items = [ItemDb.make("signal_launcher", 1), ItemDb.make("supply_signal", 1)]
	var caller: Vector3 = player.global_position
	Raid.current.request_supply_signal()
	Raid.current.supply_state.elapsed = float(Balance.SUPPLY_SIGNAL.delay) - 1.0
	Raid.current._tick_supply(0.0)
	cam.global_position = pos + Vector3(20, 1.65, 20)
	cam.look_at(pos + Vector3(0, float(Balance.SUPPLY_SIGNAL.altitude), 0))
	await shot("valuable_aircraft")
	Raid.current.supply_state.elapsed = float(Balance.SUPPLY_SIGNAL.delay)
	Raid.current._tick_supply(0.0)
	await get_tree().create_timer(float(Balance.SUPPLY_SIGNAL.fall_sec) + 0.2).timeout
	# Камера остаётся на проверенной позиции стрелка, вдали от соседних стен.
	cam.global_position = caller + Vector3.UP * 1.65
	cam.look_at(pos + Vector3.UP * 0.25)
	# Показать содержимое настоящего сброса в обычном окне обыска.
	player.global_position = pos + Vector3.UP * 0.1
	for node: Node in Raid.current._drops.get_children():
		if node is LootContainer and (node as LootContainer).display_name == Raid.SUPPLY_DROP_NAME:
			Raid.current.ui._open_loot(node as LootContainer)
			break
	await shot("valuable_airdrop")
	get_tree().quit(0)


func shot(id: String) -> void:
	for frame: int in range(10):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/%s.png" % id)


func _process(_delta: float) -> void:
	for node: Node in get_tree().get_nodes_in_group("marauders"):
		node.set_physics_process(false)
