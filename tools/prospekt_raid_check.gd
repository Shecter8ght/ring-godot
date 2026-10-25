extends Node
## Рейдовая карта «Проспект» (scenes/levels/prospekt.tscn, tools/build_prospekt_raid.py): уровень загружается,
## навигация из кэша, население расставлено слоями — кордон держат ЧВК; точки постов, патрулей, гнёзд и подхода
## стоят на навигации; от каждого захода по навигации дойти до выхода; места лута на месте.
##   tools/godot.cmd --headless res://tools/prospekt_raid_check.tscn
## Код выхода — число провалов.

const LEVEL := "res://scenes/levels/prospekt.tscn"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_raid_check.json", true)
	await get_tree().process_frame
	_level = load(LEVEL).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	var t0: int = Time.get_ticks_msec()
	while int(_level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	_check("уровень загружен, навигация готова", bool(_level.get("_nav_baked")), "%d мс" % (Time.get_ticks_msec() - t0))
	var pop := _level.get_node_or_null("Population") as AIPopulation
	_check("население расставлено слоями", pop != null and pop.layered, str(pop.placed if pop else {}))
	if pop == null:
		_finish()
		return
	var me := get_tree().get_first_node_in_group("players") as Player
	if me:
		me.health.hp = 1e9
		me.set_physics_process(false)
	# кордон: пост ЧВК занят всегда, бойцы — «pmc»
	var pmc := 0
	for m in get_tree().get_nodes_in_group("marauders"):
		var mm := m as Marauder
		if mm and mm.archetype == "pmc" and mm.global_position.distance_to(Vector3(-203, 0, 0)) < 20.0:
			pmc += 1
	_check("кордон держат ЧВК «Периметр»", (pop.placed.posts as Array).has("Cordon_PMC") and pmc >= 2, "бойцов у кордона %d" % pmc)
	# точки слоёв — на навигации
	var off: Array[String] = []
	for n in get_tree().get_nodes_in_group("ai_posts"):
		if pop._ground((n as Node3D).global_position) == Vector3.INF:
			off.append(String(n.name))
	for n in get_tree().get_nodes_in_group("ai_routes"):
		var pts: PackedVector3Array = (n as AIRoute).points()
		for i in range(pts.size()):
			if pop._ground(pts[i]) == Vector3.INF:
				off.append("%s/P%02d" % [n.name, i + 1])
	for g in ["ai_nests", "ai_arrivals"]:
		for n in get_tree().get_nodes_in_group(g):
			if pop._ground((n as Node3D).global_position) == Vector3.INF:
				off.append(String(n.name))
	_check("посты, патрули, гнёзда и подход стоят на навигации", off.is_empty(), str(off))
	# заходы → выходы по навигации
	var map: RID = (_level as Node3D).get_world_3d().navigation_map
	var exits: Array[Vector3] = []
	var exit_names: Array[String] = []
	var exit_radius: Array[float] = []
	for n in get_tree().get_nodes_in_group("extractions"):
		exits.append((n as Node3D).global_position)
		exit_names.append((n as ExtractionPoint).display_name)
		exit_radius.append((n as ExtractionPoint).radius)
	var entries := 0
	var stuck: Array[String] = []
	for n in get_tree().get_nodes_in_group("spawn_points"):
		var sp := n as SpawnPoint
		if sp == null or not sp.entry:
			continue
		entries += 1
		var reached := 0
		var missed: Array[String] = []
		for i in range(exits.size()):
			var e: Vector3 = exits[i]
			var a := NavigationServer3D.map_get_closest_point(map, sp.global_position)
			var b := NavigationServer3D.map_get_closest_point(map, e)
			# путь через всю карту длиннее предела поиска по умолчанию (4096 многоугольников) — без предела
			var query := NavigationPathQueryParameters3D.new()
			query.map = map
			query.start_position = a
			query.target_position = b
			query.path_search_max_polygons = 0
			var result := NavigationPathQueryResult3D.new()
			NavigationServer3D.query_path(query, result)
			var path: PackedVector3Array = result.path
			# дошёл — конец пути в круге выхода (по горизонтали, ±1 м по высоте)
			var r: float = exit_radius[i]
			var end: Vector3 = path[path.size() - 1] if not path.is_empty() else Vector3.INF
			if not path.is_empty() and Vector2(end.x - e.x, end.z - e.z).length() < r and absf(end.y - e.y) < 1.5:
				reached += 1
			else:
				missed.append("%s (до %s, конец %s)" % [exit_names[i], str(b), str(path[path.size() - 1]) if not path.is_empty() else "—"])
		if reached < exits.size():
			stuck.append("%s: %d/%d, нет: %s" % [sp.display_name, reached, exits.size(), ", ".join(missed)])
	_check("от каждого из %d заходов по навигации дойти до всех %d выходов" % [entries, exits.size()],
		entries >= 4 and stuck.is_empty(), str(stuck))
	var loot := (_level.get_node("Gameplay/Loot") as Node).get_child_count()
	var hall_loot := 0
	for b in get_tree().get_nodes_in_group("mall_study_snap"):
		hall_loot += int(b.get_meta("loot_count", 0))
	_check("места лута: улица и сценки больше 200, залы зданий — свои", loot > 200 and hall_loot > 40,
		"улица %d, залы %d" % [loot, hall_loot])
	_finish()


func _check(label: String, ok: bool, details: String) -> void:
	print("prospekt_raid: %s · %s %s" % ["PASS" if ok else "FAIL", label, details])
	if not ok:
		_fails += 1


func _finish() -> void:
	print("prospekt_raid: провалов %d" % _fails)
	get_tree().quit(_fails)
