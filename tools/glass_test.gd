extends Node
## Витрины: пуля пробивает стекло и летит дальше, панель трескается, треснувшая осыпается сама,
## дробь выбивает сразу; выбитая — проём: стекла и подоконника нет, путь ИИ идёт сквозь проём,
## игрок проходит. С окном — снимки glass_*.png. godot --path . res://tools/glass_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_glass_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	var gp := get_tree().get_first_node_in_group("glass_panes") as GlassPanes
	_check("витрины — отдельные панели", gp != null and gp.panes.size() > 20, str(gp.panes.size() if gp else 0))
	# целая панель поближе к улице магазинов
	var pick := -1
	var best := INF
	var probe := SectorBuilder.polar(-100.0, 79.0)
	for i in range(gp.panes.size()):
		var p: Dictionary = gp.panes[i]
		var d := (p.xf as Transform3D).origin.distance_to(probe)
		if not bool(p.broken) and d < best:
			best = d
			pick = i
	var pane: Dictionary = gp.panes[pick]
	var xf: Transform3D = pane.xf
	var nrm := xf.basis.z.normalized()
	var world := me.get_world_3d()
	for i in range(8):
		await get_tree().physics_frame
	var from := xf.origin + nrm * 3.0
	var rng := RandomNumberGenerator.new()
	var hit := Hitscan.fire(world, from, -nrm, 0.0, 12.0, Hitscan.LAYER_WORLD, 30.0, [] as Array[RID], rng)
	var end: Vector3 = hit.get("position", hit.get("end", from))
	_check("пуля прошла сквозь стекло", end.distance_to(from) > 3.3, "долетела на %.1f м" % end.distance_to(from))
	await get_tree().process_frame
	_check("панель треснула", float(gp.panes[pick].hp) < GlassPanes.HP and not bool(gp.panes[pick].broken), "прочность %.0f" % float(gp.panes[pick].hp))
	if DisplayServer.get_name() != "headless":
		await _shot(me, xf.origin + nrm * 2.2, xf.origin, "glass_cracked")
	Hitscan.fire(world, from, -nrm, 0.0, 12.0, Hitscan.LAYER_WORLD, 30.0, [] as Array[RID], rng)
	await get_tree().create_timer(float(Balance.GLASS.collapse_sec[1]) + 0.5).timeout
	_check("треснувшая осыпалась сама", bool(gp.panes[pick].broken), "прочность %.0f" % float(gp.panes[pick].hp))
	await get_tree().physics_frame
	await get_tree().physics_frame
	var q := PhysicsRayQueryParameters3D.create(xf.origin + nrm * 1.0 + Vector3.DOWN * (float(pane.size.y) * 0.5 + 0.2), xf.origin - nrm * 1.0 + Vector3.DOWN * (float(pane.size.y) * 0.5 + 0.2), Hitscan.LAYER_WORLD | Hitscan.LAYER_GLASS)
	_check("проём: ни стекла, ни подоконника", world.direct_space_state.intersect_ray(q).is_empty(), "")
	var a := Vector3(xf.origin.x, 0.0, xf.origin.z) + nrm * 2.0
	var b := Vector3(xf.origin.x, 0.0, xf.origin.z) - nrm * 2.0
	await get_tree().create_timer(0.3).timeout
	var path := NavigationServer3D.map_get_path(world.navigation_map, a, b, true)
	var plen := 0.0
	for i in range(1, path.size()):
		plen += path[i - 1].distance_to(path[i])
	_check("путь ИИ — сквозь проём", path.size() > 1 and plen < 6.5, "длина пути %.1f м" % plen)
	# игрок проходит
	me.global_position = a + Vector3.UP * 0.1
	await get_tree().physics_frame
	for i in range(60):
		me.velocity = -nrm * 3.0
		me.move_and_slide()
		await get_tree().physics_frame
	var crossed := (me.global_position - Vector3(xf.origin.x, me.global_position.y, xf.origin.z)).dot(nrm) < -0.5
	_check("игрок прошёл в проём", crossed, "")
	# дробь выбивает сразу
	var pick2 := -1
	for i in range(gp.panes.size()):
		if i != pick and not bool(gp.panes[i].broken) and (gp.panes[i].xf as Transform3D).origin.distance_to(probe) < 30.0:
			pick2 = i
			break
	var xf2: Transform3D = gp.panes[pick2].xf
	var n2 := xf2.basis.z.normalized()
	for k in range(8):
		Hitscan.fire(world, xf2.origin + n2 * 3.0, -n2, 2.0, 12.0, Hitscan.LAYER_WORLD, float(Balance.WEAPONS.shotgun.damage) if Balance.get("WEAPONS") else 12.0, [] as Array[RID], rng)
	await get_tree().process_frame
	_check("дробь выбила сразу", bool(gp.panes[pick2].broken), "прочность %.0f" % float(gp.panes[pick2].hp))
	if DisplayServer.get_name() != "headless":
		await _shot(me, xf2.origin + n2 * 2.5, xf2.origin, "glass_broken")
	print("glass_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _shot(me: Player, at: Vector3, look: Vector3, n: String) -> void:
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	me.global_position = Vector3(at.x, 0.1, at.z)
	CameraRig.first_person_mode = true
	for i in range(12):
		await get_tree().process_frame
	var d := look - me.eye_position()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = 0.0
	for i in range(40):
		await get_tree().process_frame
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	CameraRig.first_person_mode = false


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
