extends Node
## Население рейда слоями (AIPopulation, docs/design/enemy_population.md) на «Пешем маршруте»:
## точки карты стоят на навигации и не у входов игроков; для 1, 2, 3 игроков — столько групп в каждом
## слое, рынок занят всегда, никто не появился у точки появления или на виду у неё; подход входит вдали
## от игрока и идёт к недавним выстрелам; на один шум идут не больше двух групп, остальные настороже;
## чужих отрядов и ЧВК — под состав; счётчик стычек считает стычки, врагов и тяжёлые.
## tools/godot.cmd --headless res://tools/ai_population_test.tscn

const LEVEL := "res://scenes/levels/zone01_mall.tscn"

var _fails: int = 0
var _level: Node
var _pop: AIPopulation


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = load(LEVEL).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	var t0: int = Time.get_ticks_msec()
	while int(_level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	_pop = _level.get_node_or_null("Population") as AIPopulation
	_check("уровень расставил население слоями", _pop != null and _pop.layered, "")
	if _pop == null or not _pop.layered:
		_finish()
		return
	# игрок не мешает: под землёй, не видят, не стреляет
	var me: Player = get_tree().get_first_node_in_group("players") as Player
	me.health.hp = 1e9
	me.set_physics_process(false)
	_check_points()
	for party in [1, 2, 3]:
		await _check_party(party)
	await _check_arrival(me)
	await _check_noise(me)
	_check_party_scaling()
	_check_contacts()
	_finish()


## Точки карты: все на навигации; посты не ближе 60 м ко входам игроков; подход — не ближе 40 м ко
## входам и кругам эвакуации.
func _check_points() -> void:
	var bad: Array[String] = []
	var near: Array[String] = []
	var entries: Array[Vector3] = []
	for n in get_tree().get_nodes_in_group("spawn_points"):
		if n is SpawnPoint and (n as SpawnPoint).entry:
			entries.append((n as Node3D).global_position)
	var exits: Array[Vector3] = []
	for n in get_tree().get_nodes_in_group("extractions"):
		exits.append((n as Node3D).global_position)
	var posts := get_tree().get_nodes_in_group("ai_posts")
	for n in posts:
		var p := n as AIPost
		if _pop._ground(p.global_position) == Vector3.INF:
			bad.append(String(p.name))
		for q in p.patrol_points():
			if _pop._ground(q) == Vector3.INF:
				bad.append("%s/точка" % p.name)
		for e in entries:
			if AIPopulation._flat_dist(p.global_position, e) < 60.0:
				near.append("%s у входа" % p.name)
	var routes := get_tree().get_nodes_in_group("ai_routes")
	for n in routes:
		var r := n as AIRoute
		var pts := r.points()
		for i in range(pts.size()):
			if _pop._ground(pts[i]) == Vector3.INF:
				bad.append("%s/P%02d" % [r.name, i + 1])
	var nests := get_tree().get_nodes_in_group("ai_nests")
	for n in nests:
		if _pop._ground((n as Node3D).global_position) == Vector3.INF:
			bad.append(String(n.name))
	var arrivals := get_tree().get_nodes_in_group("ai_arrivals")
	for n in arrivals:
		var at := (n as Node3D).global_position
		if _pop._ground(at) == Vector3.INF:
			bad.append(String(n.name))
		for e in entries + exits:
			if AIPopulation._flat_dist(at, e) < 40.0:
				near.append("%s у входа/выхода" % n.name)
	_check("точки на карте: постов %d, маршрутов %d, гнёзд %d, подходов %d" % [posts.size(), routes.size(), nests.size(), arrivals.size()],
		posts.size() >= 10 and routes.size() >= 3 and nests.size() >= 3 and arrivals.size() >= 6, "")
	_check("все точки стоят на навигации", bad.is_empty(), str(bad))
	_check("посты и подходы не у входов игроков и выходов", near.is_empty(), str(near))


## Расстановка для party игроков: число групп по слоям, рынок, безопасный старт, роли бойцов.
func _check_party(party: int) -> void:
	for m in get_tree().get_nodes_in_group("marauders"):
		m.queue_free()
	await get_tree().process_frame
	AIPopulation.party_override = party
	var count := _pop.spawn_start()
	var want: Dictionary = _pop.placed.want
	var k: float = float((Balance.AI_POPULATION.party_k as Array)[party - 1])
	var posts: Array = _pop.placed.posts
	var tag := "игроков %d" % party
	_check("%s: постов %d (хотели %d, по Balance %d–%d)" % [tag, posts.size(), int(want.posts), roundi(5 * k), roundi(6 * k)],
		posts.size() == int(want.posts) and int(want.posts) >= roundi(float(Balance.AI_POPULATION.posts[0]) * k)
		and int(want.posts) <= roundi(float(Balance.AI_POPULATION.posts[1]) * k), str(posts))
	_check("%s: патрулей %d из %d" % [tag, (_pop.placed.routes as Array).size(), int(want.routes)],
		(_pop.placed.routes as Array).size() == int(want.routes) and int(want.routes) == (1 if party == 1 else 2), str(_pop.placed.routes))
	_check("%s: снайперов %d (не больше одного)" % [tag, (_pop.placed.nests as Array).size()], (_pop.placed.nests as Array).size() <= 1, "")
	var windows: Array = Balance.AI_POPULATION.arrive_at
	var ok_times := _pop._arrive_queue.size() == int(want.arrivals)
	for t in _pop._arrive_queue:
		ok_times = ok_times and t >= float(windows[0][0]) and t <= float(windows[windows.size() - 1][1])
	_check("%s: подход %d групп, в окнах времени %s" % [tag, _pop._arrive_queue.size(), _pop._arrive_queue], ok_times
		and int(want.arrivals) >= roundi(2 * k) and int(want.arrivals) <= roundi(3 * k), "")
	var market_ok := posts.has("Post_market_hangar") and (party < 2 or posts.has("Post_market_rows"))
	_check("%s: рынок занят (ангар%s)" % [tag, "" if party < 2 else " и ряды"], market_ok, str(posts))
	_check("%s: на паркинге не больше одного поста" % tag,
		not (posts.has("Post_parking_ground") and posts.has("Post_parking_mid")), str(posts))
	var spawn: Vector3 = _level.call("spawn_pos")
	var close: Array[String] = []
	var seen: Array[String] = []
	var garrison := 0
	var patrol := 0
	var snipers := 0
	var roles_ok := true
	var alive: Array[Marauder] = []
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m.is_queued_for_deletion():
			continue
		alive.append(m)
		if m.global_position.distance_to(spawn) < Balance.MARAUDER_SPAWN_MIN_DIST:
			close.append(String(m.name))
		if bool(_level.call("sees_spawn", m.global_position)):
			seen.append(String(m.name))
		if m.home != Vector3.INF:
			garrison += 1
			roles_ok = roles_ok and not m.home_points.is_empty()
		elif not m.route.is_empty():
			patrol += 1
			roles_ok = roles_ok and m.no_loot
		elif m.watch_dir != Vector3.ZERO:
			snipers += 1
	_check("%s: бойцов %d — гарнизонов %d, патрульных %d, снайперов %d" % [tag, count, garrison, patrol, snipers],
		alive.size() == count and garrison + patrol + snipers == count and roles_ok, "")
	var lo := roundi(5 * k) * 2 + (1 if party == 1 else 2) * 2
	var hi := roundi(6 * k) * 3 + 4 + 1
	_check("%s: бойцов на старте %d в пределах %d–%d" % [tag, count, lo, hi], count >= lo and count <= hi, "")
	_check("%s: никто не ближе %d м к точке появления" % [tag, int(Balance.MARAUDER_SPAWN_MIN_DIST)], close.is_empty(), str(close))
	_check("%s: никого не видно с точки появления" % tag, seen.is_empty(), str(seen))
	AIPopulation.party_override = 0


## Подход: вход вдали от игрока и не на виду; недавний выстрел — ведущий идёт туда; по расписанию входит сам.
func _check_arrival(me: Player) -> void:
	AIPopulation.party_override = 3
	var arrivals := get_tree().get_nodes_in_group("ai_arrivals")
	# игрок стоит на одном из входов — там не появляются
	var stand := (arrivals[0] as Node3D).global_position
	me.global_position = _pop._ground(stand) + Vector3.UP * 0.1
	await get_tree().physics_frame
	var before := _marauder_names()
	var shot := _pop._ground(Vector3(-150.0, 0.45, 80.0))
	NoiseBus.emit(shot, 120.0, "shot")
	var n := _pop.arrive_now()
	await get_tree().process_frame
	await get_tree().physics_frame
	var fresh: Array[Marauder] = []
	for m in get_tree().get_nodes_in_group("marauders"):
		if not before.has(String(m.name)):
			fresh.append(m as Marauder)
	_check("подход: вошли %d" % n, n >= int(Balance.AI_POPULATION.arrive_group[0]) and fresh.size() == n, "")
	var far := true
	var hidden := true
	for m in fresh:
		far = far and m.global_position.distance_to(me.global_position) >= float(Balance.AI_POPULATION.arrive_min_m)
		hidden = hidden and not _pop._visible(me.global_position, m.global_position)
	_check("подход: не ближе %d м к игроку и не на виду" % int(Balance.AI_POPULATION.arrive_min_m), far and hidden, "")
	var lead: Marauder = fresh[0] if not fresh.is_empty() else null
	_check("подход: ведущий идёт к недавним выстрелам", lead != null and lead.state == Marauder.State.INVESTIGATE
		and lead.last_known.distance_to(shot) < 3.0, "%s" % (Marauder.State.keys()[lead.state] if lead else "нет"))
	# по расписанию: подошло время — вошли сами
	var had := (_pop.placed.arrivals as Array).size()
	_pop._arrive_queue = [_pop._t + 0.3]
	_pop._retry_t = 0.0
	await get_tree().create_timer(1.0).timeout
	_check("подход по расписанию вошёл сам", (_pop.placed.arrivals as Array).size() == had + 1 and _pop._arrive_queue.is_empty(),
		str(_pop.placed.arrivals))
	me.global_position = Vector3(0, -200, 0)
	AIPopulation.party_override = 0


## Шум: одинокий выстрел — идёт ближняя группа, дальние настороже; бой одной группы — подходит ещё
## одна ближайшая, остальные ждут (всего у боя две группы); шум под носом проверяют всегда.
func _check_noise(me: Player) -> void:
	me.global_position = Vector3(0, -200, 0)
	var map := (_level as Node3D).get_world_3d().navigation_map
	var center := NavigationServer3D.map_get_closest_point(map, Vector3(-30.0, 0.3, -130.0))
	# одинокий выстрел
	var squads: Array[Marauder] = await _line_of_squads(center, [20.0, 30.0, 40.0, 50.0])
	NoiseBus.emit(center, 100.0, "shot")
	await get_tree().physics_frame
	_check("одинокий выстрел: идёт ближняя группа, дальние настороже", squads[0].state == Marauder.State.INVESTIGATE
		and not squads[1].is_alert() and squads[2].is_alert() and squads[3].is_alert(), _states(squads))
	# шум под самым носом — проверяет и насторожённый
	NoiseBus.emit(squads[3].global_position + Vector3(5.0, 0.0, 0.0), 100.0, "shot")
	await get_tree().physics_frame
	_check("шум под носом проверяют всегда", squads[3].state == Marauder.State.INVESTIGATE, _states(squads))
	# бой: первая группа стреляет — к ней идёт одна ближайшая, остальные настороже
	squads = await _line_of_squads(center, [0.0, 20.0, 30.0, 40.0])
	var fighter := squads[0]
	fighter.state = Marauder.State.COMBAT
	fighter.last_known = center + Vector3(0.0, 0.0, -70.0)
	fighter.memory_timer = 60.0
	for i in range(3):
		NoiseBus.emit(fighter.global_position + Vector3(float(i) * 2.0, 0.0, 0.0), 100.0, "shot")
		await get_tree().physics_frame
	var going := squads.filter(func(m: Marauder) -> bool: return m != fighter and m.state in [Marauder.State.INVESTIGATE, Marauder.State.SEARCH, Marauder.State.COMBAT]).size()
	_check("бой одной группы: подходит ещё одна, остальные ждут", going == 1 and squads[1].state == Marauder.State.INVESTIGATE
		and squads[2].is_alert() and squads[3].is_alert(), _states(squads))
	for m in squads:
		m.queue_free()


## Одиночные группы на линии от center (расстояния по X), стоят на месте и не грабят.
func _line_of_squads(center: Vector3, dists: Array) -> Array[Marauder]:
	for m in get_tree().get_nodes_in_group("marauders"):
		m.queue_free()
	await get_tree().process_frame
	var map := (_level as Node3D).get_world_3d().navigation_map
	var out: Array[Marauder] = []
	for d in dists:
		var at := NavigationServer3D.map_get_closest_point(map, center + Vector3(float(d), 0.0, 0.0))
		var m: Marauder = _level.call("spawn_marauder", at, "gunner", {}) as Marauder
		var sq := Squad.new()
		sq.add(m)
		m.no_loot = true
		out.append(m)
	await get_tree().physics_frame
	for m in out:
		m.state = Marauder.State.PATROL
		m.pause_timer = 60.0
		m._set_move_target(m.global_position)
	await get_tree().physics_frame
	return out


func _states(list: Array[Marauder]) -> String:
	return str(list.map(func(m: Marauder) -> String: return "насторожен" if m.is_alert() else String(Marauder.State.keys()[m.state])))


## Чужие отряды и ЧВК — под число игроков (решение владельца: у троих 2–3 отряда, соло ЧВК из трёх).
func _check_party_scaling() -> void:
	var want := {1: [[1, 1], 3], 2: [[1, 2], 4], 3: [[2, 3], 4]}
	var ok := true
	for party: int in want:
		AIPopulation.party_override = party
		ok = ok and (Balance.RIVALS.squads[party - 1] as Array) == want[party][0] and AIPopulation.pmc_size() == int(want[party][1])
	AIPopulation.party_override = 0
	_check("чужих отрядов 1 / 1–2 / 2–3, ЧВК 3 / 4 / 4", ok, "")


## Счётчик стычек: открывает, считает врагов, закрывает после затишья, отмечает тяжёлые и паузы.
func _check_contacts() -> void:
	var c := _level.get_node_or_null("Contacts") as RaidContacts
	_check("у уровня есть счётчик стычек", c != null, "")
	if c == null:
		return
	c.contacts.clear()
	c._open = {}
	var map := (_level as Node3D).get_world_3d().navigation_map
	var crew: Array[Marauder] = []
	for i in range(4):
		var at := NavigationServer3D.map_get_closest_point(map, Vector3(-20.0 - 3.0 * i, 0.3, -130.0))
		crew.append(_level.call("spawn_marauder", at, "gunner", {}) as Marauder)
	var now := Time.get_ticks_msec()
	for m in crew:
		m.player_contact_ms = now
	c.tick()
	_check("стычка открылась: врагов %d" % (c._open.get("enemies", {}) as Dictionary).size(), (c._open.get("enemies", {}) as Dictionary).size() == 4, "")
	for m in crew:
		m.player_contact_ms = 1
	c._open.last = Time.get_ticks_msec() - int(float(Balance.RAID_CONTACTS.calm_sec) * 1000.0) - 100
	c.tick()
	_check("затишье — стычка закрылась, тяжёлая (4 врага)", c.contacts.size() == 1 and bool(c.contacts[0].heavy) and int(c.contacts[0].enemies) == 4,
		str(c.contacts))
	crew[0].player_contact_ms = Time.get_ticks_msec()
	crew[1].player_contact_ms = Time.get_ticks_msec()
	c.tick()
	crew[0].player_contact_ms = 1
	crew[1].player_contact_ms = 1
	c._open.last = Time.get_ticks_msec() - int(float(Balance.RAID_CONTACTS.calm_sec) * 1000.0) - 100
	c.tick()
	var s := c.summary()
	_check("вторая стычка — двое, обычная; итог считает паузу", int(s.count) == 2 and int(s.heavy) == 1 and (s.sizes as Array) == [4, 2]
		and (s.gaps as Array).size() == 1, str(s))
	for m in crew:
		m.queue_free()


func _marauder_names() -> Dictionary:
	var out := {}
	for m in get_tree().get_nodes_in_group("marauders"):
		out[String(m.name)] = true
	return out


func _check(what: String, ok: bool, detail: String) -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["OK  " if ok else "FAIL", what, ("  — " + detail) if detail != "" and not ok else ""])


func _finish() -> void:
	print("ai_population_test: %s, провалов %d" % ["всё сходится" if _fails == 0 else "ЕСТЬ ПРОВАЛЫ", _fails])
	get_tree().quit(1 if _fails > 0 else 0)
