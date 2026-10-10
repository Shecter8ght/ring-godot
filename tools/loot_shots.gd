extends Node
## Реальные точки лута двора зоны 1: вид от первого лица и вещь в рюкзаке.


func _ready() -> void:
	if name != "LootShotsRunner":
		var runner: Node = Node.new()
		runner.name = "LootShotsRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	Profile.use_file("user://loot_shots.json", true)
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
	var item: Dictionary = ItemDb.make("thermos", 1)
	item["fir"] = true
	point.items = [item]
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
	await shot("loot_world")
	point.request_use()
	await shot("loot_picked")
	Raid.current.ui._backpack_open = true
	Raid.current.ui._refresh_visibility()
	await shot("loot_backpack")
	get_tree().quit(0)


func shot(id: String) -> void:
	for frame: int in range(10):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/%s.png" % id)
