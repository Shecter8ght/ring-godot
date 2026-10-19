extends Node
## Детали заказа «Вернуть машину» на настоящей карте («Пригород», автобаза с ангаром № 8): заказ на этапе «комплект» —
## в кладовой стоят радиатор и колесо с биркой (cargo у мест-источников); затем колесо и радиатор сданы — в кладовой
## пусто, колесо на машине, радиатор в комплекте (placed). Снимки docs/screens/car_parts_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/car_parts_shots.tscn

const Q := "car_recovery"


func _ready() -> void:
	if name != "CarPartsShotsRunner":
		var runner: Node = Node.new()
		runner.name = "CarPartsShotsRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	Profile.use_file("user://car_parts_shots.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Quests.dev_start(Q)
	Quests.dev_stage(Q, 6)
	get_tree().change_scene_to_file("res://scenes/levels/zone01_mall.tscn")
	for frame: int in range(40):
		await get_tree().process_frame
	var level: Node3D = get_tree().current_scene as Node3D
	while not bool(level.get("_nav_baked")):
		await get_tree().create_timer(0.1).timeout
	var player: Player = Raid.current.local_player()
	player.set_physics_process(false)
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
	var rig: Node = level.get_node("CameraRig")
	rig.set_process(false)
	rig.set_physics_process(false)
	var cam: Camera3D = get_viewport().get_camera_3d()
	var radiator: Node3D = _site("car_belt_parts_radiator")
	var wheel: Node3D = _site("car_belt_parts_wheel")
	var kit: Node3D = _site("car_belt_delivery")
	print("car_parts_shots: места — кладовая ", radiator != null, " ", wheel != null, ", комплект ", kit != null)
	if radiator == null or wheel == null or kit == null:
		get_tree().quit(1)
		return
	var mid: Vector3 = (radiator.global_position + wheel.global_position) * 0.5
	# перёд радиатора у якоря — по +Z якоря: смотрим с той стороны и сбоку, на высоте глаз
	var front: Vector3 = radiator.global_transform.basis.z.normalized()
	await _shot(cam, player, mid + front * 2.2 + Vector3.UP * 1.6, mid + Vector3.UP * 0.25, "store")
	await _shot(cam, player, mid + front * 1.0 + Vector3(0.0, 1.2, 1.4), wheel.global_position + Vector3.UP * 0.15, "store_close")
	# сдано: в кладовой пусто, колесо на машине, радиатор в комплекте у машины
	Quests._durable_add(Q, "wheel")
	Quests._durable_add(Q, "radiator")
	Quests._auto_all()
	await _shot(cam, player, mid + front * 2.2 + Vector3.UP * 1.6, mid + Vector3.UP * 0.25, "store_empty")
	var kf: Vector3 = kit.global_transform.basis.z.normalized()
	await _shot(cam, player, kit.global_position + kf * 2.0 + Vector3(0.6, 1.5, 0.0), kit.global_position + Vector3.UP * 0.3, "kit")
	get_tree().quit(0)


func _site(sid: String) -> Node3D:
	return get_tree().current_scene.find_child("Quest_" + sid, true, false) as Node3D


func _shot(cam: Camera3D, player: Player, eye: Vector3, at: Vector3, tag: String) -> void:
	player.global_position = eye - Vector3.UP * 1.5
	cam.global_position = eye
	cam.look_at(at)
	for frame: int in range(12):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/car_parts_%s.png" % tag
	get_viewport().get_texture().get_image().save_png(path)
	print("car_parts_shots: ", path)
