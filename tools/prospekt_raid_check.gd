extends Node
## Рейдовая карта «Проспект» (scenes/levels/prospekt.tscn, tools/build_prospekt_raid.py): уровень загружается,
## навигация из кэша, население расставлено слоями — кордон держат ЧВК; точки постов, патрулей, гнёзд и подхода
## стоят на навигации; от каждого захода по навигации дойти до выхода; места лута на месте; приёмы EFT —
## выходы по стороне захода, условные выходы, подстанция, решётка хранилища, замки, схроны, главарь банка.
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
		if mm and mm.archetype == "pmc" and mm.global_position.distance_to(Vector3(-203, 0, -15.65)) < 20.0:
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
	_eft_checks(me, pop)
	_finish()


## Приёмы EFT (docs/design/prospekt_eft_mechanics.md, владелец 2026-10-29: «делай всё»): выходы по стороне захода
## и «не каждый рейд», условные выходы, подстанция, решётка хранилища, замки, схроны, главарь банка.
func _eft_checks(me: Player, pop: AIPopulation) -> void:
	var raid := Raid.current
	var exits: Array[ExtractionPoint] = []
	var by_name := {}
	for n in get_tree().get_nodes_in_group("extractions"):
		if n is ExtractionPoint:
			exits.append(n as ExtractionPoint)
			by_name[(n as ExtractionPoint).display_name] = n
	_check("список выходов рейда объявлен при старте", raid.exits_note.begins_with("Выходы:"), raid.exits_note)
	# у каждого захода закрыты выходы ближе порога, открытых без условий — не меньше двух
	var near_m := float(Balance.EXIT_RULES.near_spawn_m)
	var rng := RandomNumberGenerator.new()
	rng.seed = 29
	var bad: Array[String] = []
	var rows: Array[String] = []
	for node in get_tree().get_nodes_in_group("spawn_points"):
		var sp := node as SpawnPoint
		if sp == null or not sp.entry:
			continue
		raid.roll_exits(sp.global_position, near_m, rng)
		var plain: Array[String] = []
		for e in exits:
			var d := Vector2(e.global_position.x - sp.global_position.x, e.global_position.z - sp.global_position.z).length()
			var shut := raid.closed_exits.has(String(e.name))
			if d < near_m and not shut:
				bad.append("%s: «%s» открыт в %d м" % [sp.display_name, e.display_name, int(d)])
			if not shut and e.required_switch == "" and e.required_key == "" and not e.no_backpack:
				plain.append(e.display_name)
		if plain.size() < 2:
			bad.append("%s: простых выходов %d" % [sp.display_name, plain.size()])
		rows.append("%s → %s" % [sp.display_name, ", ".join(plain)])
	var tracks_open := 0
	var far := Vector3(181.3, 0.0, -135.3)
	var tracks_name := String((by_name["По путям на запад"] as Node).name) if by_name.has("По путям на запад") else ""
	for i in range(200):
		raid.roll_exits(far, near_m, rng)
		if tracks_name != "" and not raid.closed_exits.has(tracks_name):
			tracks_open += 1
	_check("выходы по стороне захода: ближние закрыты, простых открытых не меньше двух", bad.is_empty(),
		str(bad) if not bad.is_empty() else " · ".join(rows))
	_check("«По путям на запад» открыт не каждый рейд (около 60 %)", tracks_open > 95 and tracks_open < 145, "%d из 200" % tracks_open)
	raid.closed_exits = {}
	var hold := me.global_position
	# ворота паркинга: без питания закрыты, рубильник КТП открывает, брелок — и без питания
	var gate := by_name.get("Паркинг −1, выезд в город") as ExtractionPoint
	var sw_node: PowerSwitch = null
	for n in get_tree().get_nodes_in_group("interactables"):
		if n is PowerSwitch and (n as PowerSwitch).switch_id == "prospekt_ktp":
			sw_node = n as PowerSwitch
	var steps: Array[String] = []
	if gate:
		me.global_position = gate.global_position
		steps.append(raid.extraction_block_reason_for(gate, me))
		me.inventory.add("key_parking_fob", 1)
		steps.append(raid.extraction_block_reason_for(gate, me))
		me.inventory.remove("key_parking_fob", 1)
		raid.set_switch("prospekt_ktp", true)
		steps.append(raid.extraction_block_reason_for(gate, me))
		raid.set_switch("prospekt_ktp", false)
	_check("ворота паркинга: питание КТП или брелок", gate != null and sw_node != null and steps.size() == 3
		and steps[0].contains("питания") and steps[1] == "" and steps[2] == "", str(steps))
	# труба: только без рюкзака
	var pipe := by_name.get("Водопропускная труба") as ExtractionPoint
	var pipe_steps: Array[String] = []
	if pipe:
		me.global_position = pipe.global_position
		var eq := me.inventory.equipment.duplicate(true)
		var bare := eq.duplicate(true)
		bare.erase("backpack")
		me.inventory.equipment = bare
		pipe_steps.append(raid.extraction_block_reason_for(pipe, me))
		var packed := bare.duplicate(true)
		packed["backpack"] = ItemDb.make("bp_raid", 1)
		me.inventory.equipment = packed
		pipe_steps.append(raid.extraction_block_reason_for(pipe, me))
		me.inventory.equipment = eq
	_check("труба под насыпью: без рюкзака — да, с рюкзаком — нет", pipe != null and pipe_steps.size() == 2
		and pipe_steps[0] == "" and pipe_steps[1].contains("рюкзак"), str(pipe_steps))
	me.global_position = hold
	# решётка хранилища: электрозамок и ключ-карта
	var grille := _level.get_node_or_null("Gameplay/VaultGrille") as Door
	var g_steps: Array[bool] = []
	if grille:
		g_steps.append(bool(grille.call("_can_open", me)))
		raid.set_switch("prospekt_ktp", true)
		g_steps.append(bool(grille.call("_can_open", me)))
		me.inventory.add("key_bank_vault", 1)
		g_steps.append(bool(grille.call("_can_open", me)))
		me.inventory.remove("key_bank_vault", 1)
		raid.set_switch("prospekt_ktp", false)
	_check("решётка хранилища: без питания и без карты — нет, с обоими — да", g_steps == [false, false, true], str(g_steps))
	# замки на сейфах: без ключа — причина, с ключом — открывается
	var locked: Array[String] = []
	var lock_bad: Array[String] = []
	for n in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null or c.required_key == "":
			continue
		locked.append(c.display_name)
		var without := c.lock_reason(me)
		me.inventory.add(c.required_key, 1)
		var with_key := c.lock_reason(me)
		me.inventory.remove(c.required_key, 1)
		if without == "" or with_key != "":
			lock_bad.append(c.display_name)
	_check("сейфы под ключ («Ярус», ломбард) заперты и открываются ключом", locked.size() >= 2 and lock_bad.is_empty(),
		"%s %s" % [str(locked), str(lock_bad)])
	# схроны: в пуле не меньше десяти, открыто по Balance.STASHES
	var pool := 0
	var active := 0
	for n in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c and c.stash:
			pool += 1
			if not c.stash_off:
				active += 1
	_check("схроны: открыта случайная часть", pool >= 10 and active >= int(Balance.STASHES.active[0])
		and active <= int(Balance.STASHES.active[1]), "открыто %d из %d" % [active, pool])
	# таблицы: главарь всегда несёт ключ-карту, схрон не пустой
	var r2 := RandomNumberGenerator.new()
	r2.seed = 3
	var boss_key := true
	var stash_items := 0
	for i in range(20):
		var got := ItemDb.roll("bank_boss", r2)
		boss_key = boss_key and got.any(func(e: Dictionary) -> bool: return String(e.id) == "key_bank_vault")
		stash_items += ItemDb.roll("stash", r2).size()
	_check("лут: ключ-карта у главаря всегда, схроны не пустые", boss_key and stash_items >= 40, "предметов в 20 схронах %d" % stash_items)
	# главарь банка: пост не каждый рейд, ведёт охрану; если занят — ровно один главарь
	var post := _level.get_node_or_null("Gameplay/Population/Posts/Bank_Boss") as AIPost
	var bosses := 0
	for m in get_tree().get_nodes_in_group("marauders"):
		if (m as Marauder).archetype == "bank_boss":
			bosses += 1
	var placed := (pop.placed.posts as Array).has("Bank_Boss")
	_check("главарь банка: пост 30 %, ведёт охрану", post != null and is_equal_approx(post.chance, 0.3) and post.lead_arch == "bank_boss"
		and not WeaponDb.loadout("bank_boss").is_empty() and bosses == (1 if placed else 0),
		"занят %s, главарей %d" % [str(placed), bosses])


func _check(label: String, ok: bool, details: String) -> void:
	print("prospekt_raid: %s · %s %s" % ["PASS" if ok else "FAIL", label, details])
	if not ok:
		_fails += 1


func _finish() -> void:
	print("prospekt_raid: провалов %d" % _fails)
	get_tree().quit(_fails)
