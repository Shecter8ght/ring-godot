extends Node
## «Проспект»: сколько бойцов даёт население по слоям при 1 / 2 / 3 игроках (среднее по POP_TRIALS расстановок).
## Расстановка — настоящая (AIPopulation: _spawn_posts / _spawn_routes / _spawn_nests), после каждой бойцов убираем;
## подход считается по расписанию (групп × arrive_group). Выход — печать; код 0.
##   tools/godot.cmd --headless res://tools/prospekt_pop_stats.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"  # POP_LEVEL — другая сцена (сравнение до / после)


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_pop_stats.json", true)
	await get_tree().process_frame
	var level: Node = load(OS.get_environment("POP_LEVEL") if OS.get_environment("POP_LEVEL") != "" else LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	var pop := level.get_node("Population") as AIPopulation
	var me := get_tree().get_first_node_in_group("players") as Player
	if me:
		me.set_physics_process(false)
	var trials: int = int(OS.get_environment("POP_TRIALS")) if OS.get_environment("POP_TRIALS") != "" else 20
	print("постов на карте %d, маршрутов %d, гнёзд %d, точек подхода %d" % [
		get_tree().get_nodes_in_group("ai_posts").size(), get_tree().get_nodes_in_group("ai_routes").size(),
		get_tree().get_nodes_in_group("ai_nests").size(), get_tree().get_nodes_in_group("ai_arrivals").size()])
	for party in [1, 2, 3]:
		AIPopulation.party_override = party
		var sum := {"posts": 0.0, "routes": 0.0, "nests": 0.0, "arrivals": 0.0}
		var groups := {"posts": 0.0, "routes": 0.0, "nests": 0.0}
		var mn := 9999
		var mx := 0
		var used := {}
		for i in range(trials):
			await _clear()
			var c := pop.cfg()
			var want := {"posts": pop.group_count("posts"), "routes": pop.group_count("routes"),
				"nests": pop.group_count("nests"), "arrivals": pop.group_count("arrivals")}
			pop.placed = {"posts": [], "routes": [], "nests": [], "arrivals": [], "marauders": 0, "party": party, "want": want}
			var a: int = pop._spawn_posts(int(want.posts))
			var b: int = pop._spawn_routes(int(want.routes))
			var n: int = pop._spawn_nests(int(want.nests))
			var arr: int = int(want.arrivals) * int((c.arrive_group as Array)[0])
			sum.posts += a
			sum.routes += b
			sum.nests += n
			sum.arrivals += arr
			groups.posts += (pop.placed.posts as Array).size()
			groups.routes += (pop.placed.routes as Array).size()
			groups.nests += (pop.placed.nests as Array).size()
			for p in pop.placed.posts:
				used[p] = int(used.get(p, 0)) + 1
			var tot: int = a + b + n + arr
			mn = mini(mn, tot)
			mx = maxi(mx, tot)
		var k := float(trials)
		print("игроков %d: посты %.1f бойцов (%.1f групп), патрули %.1f (%.1f), гнёзда %.1f (%.1f), подход %.1f; всего %.1f, от %d до %d" % [
			party, sum.posts / k, groups.posts / k, sum.routes / k, groups.routes / k, sum.nests / k, groups.nests / k,
			sum.arrivals / k, (sum.posts + sum.routes + sum.nests + sum.arrivals) / k, mn, mx])
		var keys: Array = used.keys()
		keys.sort_custom(func(x: Variant, y: Variant) -> bool: return int(used[x]) > int(used[y]))
		print("  посты по частоте: ", ", ".join(keys.map(func(x: Variant) -> String: return "%s %d" % [x, used[x]])))
	AIPopulation.party_override = 0
	await _clear()
	get_tree().quit(0)


func _clear() -> void:
	for m in get_tree().get_nodes_in_group("marauders"):
		m.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame
