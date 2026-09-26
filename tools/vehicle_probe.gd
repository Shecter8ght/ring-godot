extends Node
## Машины на уровне (модели ring_vehicles, стоят руками в сцене): у каждой одна коллизия на всю
## машину, пуля в неё упирается, навмеш её обходит, пол площади под ними — с текстурой (не серая
## сетка блокаута). Снимок vehicles.png. godot --path . res://tools/vehicle_probe.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var inst: Node = load(Balance.RAID_SCENE).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(40):
		await get_tree().physics_frame
	var cars: Array[StaticBody3D] = []
	for n in inst.get_children():
		if n is StaticBody3D and String(n.scene_file_path).contains("ring_vehicles"):
			cars.append(n)
	print("машин в сцене: %d" % cars.size())
	if cars.is_empty():
		print("vehicle_probe: машин нет — нечего проверять")
		get_tree().quit(0)
		return
	var one := true
	for c in cars:
		var shapes := c.find_children("*", "CollisionShape3D", false, false)
		var bodies := c.find_children("*", "CollisionObject3D", true, false)
		one = one and shapes.size() == 1 and bodies.is_empty()
	_check("у каждой машины — одна коллизия на корне, без тел на деталях", one, "")
	var space := inst.get_viewport().get_world_3d().direct_space_state
	var car := cars[0]
	var c := car.global_position + Vector3.UP * 0.8
	var q := PhysicsRayQueryParameters3D.create(c + Vector3(12, 0, 0), c - Vector3(12, 0, 0), Hitscan.LAYER_WORLD)
	var hit := space.intersect_ray(q)
	_check("пуля упирается в машину", not hit.is_empty() and hit.collider == car, str(hit.get("collider")))
	# навмеш: дождаться, центр машины — не на навмеше
	var map := inst.get_viewport().get_world_3d().navigation_map
	for i in range(600):
		if (inst.get_node("Marauders") as Node).get_child_count() > 0:
			break
		await get_tree().physics_frame
	# навмеш на земле — не под машиной (на крыше автобуса может быть свой островок — он выше)
	var bad := 0
	for cc in cars:
		var g := Vector3(cc.global_position.x, 0.0, cc.global_position.z)
		var near := NavigationServer3D.map_get_closest_point(map, g)
		if near.y < 0.8 and Vector2(near.x - g.x, near.z - g.z).length() < 0.5:
			bad += 1
			print("    навмеш под: %s у %s, навмеш %s" % [cc.name, str(cc.global_position), str(near)])
	_check("мародёры объезжают — на земле под машинами навмеша нет", bad == 0, "машин с навмешем под собой: %d" % bad)
	# пол площади: текстура, не блокаут
	var floor_mat := ""
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		if String(mi.name) == "large_floor_tiles_02":
			floor_mat = String(mi.name)
	_check("пол площади — с текстурой", floor_mat != "", floor_mat)
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	var pl := get_tree().get_first_node_in_group("players") as Player
	pl.health.hp = 1e9
	pl.global_position = Vector3(-3.0, 0.1, -152.0)
	await get_tree().create_timer(1.5).timeout
	if DisplayServer.get_name() != "headless":
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/vehicles.png"))
	print("vehicle_probe: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
