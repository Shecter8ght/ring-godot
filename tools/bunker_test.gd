extends Node
## Спуски в убежище на f1_ring: игрок появляется внизу у гермодвери (не на улице), над приямком
## земли нет (вырез), рядом — есть; по лестнице можно подняться на улицу; мародёров рядом нет.
## С окном — снимки docs/screens/bunker_*.png (изометрия, из глаз вверх по лестнице, ночь).
## godot --path . res://tools/bunker_test.tscn

var _player: Player
var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": String(OS.get_environment("BUNKER_TIME")) if OS.get_environment("BUNKER_TIME") != "" else "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var inst: Node = load(Balance.RAID_SCENE).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(30):
		await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_player.health.hp = 1e9
	var ents := get_tree().get_nodes_in_group("ground_holes")
	_check("спуски на месте", ents.size() >= 3, "%d" % ents.size())
	var ent := _nearest(ents, _player.global_position)
	var loc := ent.global_transform.affine_inverse() * _player.global_position
	_check("появился внизу, у двери убежища", absf(loc.y + ent.depth) < 0.4 and loc.z > ent.stair_len - 0.5 and loc.z < ent.total_len(),
		"%s в %s" % [str(loc), ent.display_name])
	# земля: над приямком — пусто до дна, рядом — асфальт
	var space := _player.get_world_3d().direct_space_state
	# плоскость земли (бесконечная, для столкновений) лучи останавливает — смотрим, что под ней
	var gp := get_tree().get_first_node_in_group("ground_plane") as CollisionObject3D
	var over := _ray_y(space, ent.global_transform * Vector3(0.0, 5.0, ent.stair_len * 0.5), [gp.get_rid()])
	_check("над лестницей — ступени, не пол", over < -0.5, "луч упал на %.2f" % over)
	var mesh_hole := true
	for mi in get_tree().current_scene.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if "asphalt" in String(m.name) and m.mesh:
			var faces := m.mesh.get_faces()
			var c := ent.global_transform * Vector3(0.0, 0.0, ent.total_len() * 0.5)
			for i in range(0, faces.size(), 3):
				if Geometry2D.is_point_in_polygon(Vector2(c.x, c.z), PackedVector2Array([Vector2(faces[i].x, faces[i].z), Vector2(faces[i + 1].x, faces[i + 1].z), Vector2(faces[i + 2].x, faces[i + 2].z)])):
					mesh_hole = false
	_check("в асфальте над приямком — проём", mesh_hole, "")
	var side := _ray_y(space, ent.global_transform * Vector3(ent.width * 0.5 + 2.0, 5.0, 3.0))
	_check("рядом с приямком — асфальт", absf(side) < 0.2, "%.2f" % side)
	# мародёры: не рядом
	while (inst.get_node("Marauders") as Node).get_child_count() == 0:
		await get_tree().physics_frame
	var near := INF
	for m in get_tree().get_nodes_in_group("marauders"):
		near = minf(near, (m as Node3D).global_position.distance_to(_player.global_position))
	_check("мародёры не рядом со спуском", near >= Balance.MARAUDER_SPAWN_MIN_DIST - 1.0, "ближайший %.0f м" % near)
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	await _wait(1.0)
	_save("bunker_iso")
	# из глаз: вверх по лестнице
	CameraRig.set_first_person_mode(true)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	await _wait(0.6)
	_save("bunker_fp")
	CameraRig.set_first_person_mode(false)
	await _wait(0.4)
	# подняться: «вперёд» — к верху лестницы (−Z спуска)
	var z := ent.global_basis.z
	rig.rotation.y = atan2(z.x, z.z)
	Input.action_press("move_forward")
	var t := 0.0
	while t < 7.0:
		rig.rotation.y = atan2(z.x, z.z)
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
	Input.action_release("move_forward")
	await _wait(0.5)
	loc = ent.global_transform.affine_inverse() * _player.global_position
	_check("поднялся по лестнице на улицу", loc.z < 0.2 and absf(_player.global_position.y) < 0.3, "%s" % str(loc))
	_save("bunker_top")
	print("bunker_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _nearest(list: Array, p: Vector3) -> HideoutEntrance:
	var best: HideoutEntrance = null
	var bd := INF
	for n in list:
		var e := n as HideoutEntrance
		if e and e.global_position.distance_to(p) < bd:
			bd = e.global_position.distance_to(p)
			best = e
	return best


func _ray_y(space: PhysicsDirectSpaceState3D, from: Vector3, exclude: Array[RID] = []) -> float:
	var q := PhysicsRayQueryParameters3D.create(from, from + Vector3.DOWN * 20.0, 0xFFFFFFFF, exclude)
	var hit := space.intersect_ray(q)
	return float((hit.position as Vector3).y) if not hit.is_empty() else -99.0


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _save(n: String) -> void:
	if DisplayServer.get_name() != "headless":
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
