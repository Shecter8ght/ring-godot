extends Node
## Кооп, население рейда слоями на «Пешем маршруте» (реальные ENet peer, порт 17795): хост считает
## группы по числу игроков в рейде, а не по себе; гарнизоны, патрули, снайпер и подход у гостей там же,
## где у хоста, и ходят; подход входит вдали от всех игроков, а не только от хоста; чужие отряды и ЧВК —
## по составу; счётчик стычек засчитывает бой с гостем.
## tools/godot.cmd --headless res://tools/coop_population_test.tscn -- host
## и через 3 с то же с «-- client» (COOP_POP_PEERS=3 — двое гостей: второй «-- client» ещё через 3 с).
const PORT: int = 17795
const LEVEL: String = "res://scenes/levels/zone01_mall.tscn"
## Где стоят игроки на проверке подхода: хост — у северного входа подхода, гости — у южного и восточного.
const PLACES: Array[Vector3] = [Vector3(-130.0, 0.3, -165.0), Vector3(-60.0, 0.3, 240.0), Vector3(380.0, 5.5, -60.0)]
## Сколько раз выбирать вход подхода: если гостя не учитывают, хоть раз выпадет вход у него.
const ARRIVAL_ROLLS: int = 40

var role: String = "host"
var fails: int = 0
var _want: int = 2
var clients_ready: int = 0
## Хост: отчёты гостей по этапам {этап: [прошёл?, …]}; гость: ответ хоста на просьбу о свежих позициях.
var _reports: Dictionary = {}
var _fresh: Dictionary = {}
var _placed_n: int = 0
var _done: bool = false


func _ready() -> void:
	if name != "CoopPopulationRunner":
		var runner: Node = Node.new()
		runner.name = "CoopPopulationRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	role = String(args[0])
	if OS.get_environment("COOP_POP_PEERS") != "":
		_want = int(OS.get_environment("COOP_POP_PEERS"))
	Profile.use_file("user://coop_pop_%s_%d.json" % [role, OS.get_process_id() % 1000], true)
	Profile.from_hideout = false
	RaidEvents.enabled = false
	RivalRaids.forced = true
	check("ENet подключение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == _want, 120)
	if role == "host":
		await get_tree().create_timer(2.0).timeout
		Net.start_level.rpc(LEVEL, {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == _want, 240)
	print("coop_pop_%s: в рейде, игроков %d" % [role, get_tree().get_nodes_in_group("players").size()])
	if role == "client":
		_ready_client.rpc_id(1)
		await until(func() -> bool: return _done, 600)
		print("coop_pop_client: failures=", fails)
		await get_tree().create_timer(0.5).timeout
		get_tree().quit(1 if fails else 0)
		return
	await _host_pass()
	_finish.rpc()
	print("coop_pop_host: failures=", fails)
	await get_tree().create_timer(1.0).timeout
	get_tree().quit(1 if fails else 0)


# ---------------------------------------------------------------- хост

func _host_pass() -> void:
	var level: Node = get_tree().current_scene
	await until(func() -> bool: return int(level.get("_marauders_spawned")) > 0, 240)
	var pop: AIPopulation = level.get_node_or_null("Population") as AIPopulation
	check("население расставлено слоями", pop != null and pop.layered)
	if pop == null or not pop.layered:
		return
	check("групп — по %d игрокам рейда (участников %d, в расстановке %d)" % [_want, Raid.current.participants.size(), int(pop.placed.get("party", 0))],
		AIPopulation.party_size() == _want and int(pop.placed.get("party", 0)) == _want)
	await until(func() -> bool: return clients_ready >= _want - 1, 240)
	# все бойцы старта у гостей — там же
	await _stage("старт", _names(func(_m: Marauder) -> bool: return true))
	# ходят
	_reports.erase("ходят")
	_measure_move.rpc()
	await until(func() -> bool: return (_reports.get("ходят", []) as Array).size() >= _want - 1, 60)
	check("у гостей мародёры ходят", _all_passed("ходят"))
	# чужие отряды — по составу
	var rivals: RivalRaids = RivalRaids.current
	await until(func() -> bool: return rivals != null and rivals._ready_host, 30)
	var planned: int = rivals._queue.size() + rivals.squads.size()
	var span: Array = Balance.RIVALS.squads[_want - 1]
	check("чужих отрядов %d — в пределах %d–%d для %d игроков" % [planned, int(span[0]), int(span[1]), _want],
		planned >= int(span[0]) and planned <= int(span[1]))
	await _arrival(pop)
	await _pmc()
	await _contact()


## Подход: игроки стоят у разных входов; вход выбирается вдали от каждого из них; группы — у гостей.
func _arrival(pop: AIPopulation) -> void:
	var me: Player = Raid.current.local_player()
	_stand(me, PLACES[0])
	var peers: Array = Array(multiplayer.get_peers())
	_placed_n = 0
	for i in range(peers.size()):
		_go_to.rpc_id(int(peers[i]), PLACES[i + 1])
	await until(func() -> bool: return _placed_n >= peers.size(), 30)
	# позиция гостя доходит до хоста синхронизатором
	var guests_there: Callable = func() -> bool:
		for i in range(peers.size()):
			var pl: Player = Raid.current.player_of(int(peers[i]))
			if pl == null or AIPopulation._flat_dist(pl.global_position, PLACES[i + 1]) > 6.0:
				return false
		return true
	await until(guests_there, 20)
	check("хост видит гостей там, где они встали", guests_there.call())
	var players: Array[Player] = []
	for n in get_tree().get_nodes_in_group("players"):
		players.append(n as Player)
	var near: int = 0
	var none: int = 0
	for i in range(ARRIVAL_ROLLS):
		var at: Vector3 = pop._arrival_point()
		if at == Vector3.INF:
			none += 1
			continue
		for pl in players:
			if pl.global_position.distance_to(at) < float(Balance.AI_POPULATION.arrive_min_m):
				near += 1
	check("вход подхода не ближе %d м ни к хосту, ни к гостям (%d выборов, вплотную %d, некуда %d)" % [int(Balance.AI_POPULATION.arrive_min_m), ARRIVAL_ROLLS, near, none],
		near == 0 and none < ARRIVAL_ROLLS)
	var before: Dictionary = _names(func(_m: Marauder) -> bool: return true)
	var came: int = pop.arrive_now() + pop.arrive_now()
	await get_tree().physics_frame
	var fresh: Dictionary = _names(func(m: Marauder) -> bool: return not before.has(String(m.name)))
	check("подход: вошли %d" % came, came > 0 and fresh.size() == came)
	await _stage("подход", fresh)


## ЧВК: приезжают группой по составу, у гостей — тоже.
func _pmc() -> void:
	RaidEvents.current.trigger("pmc")
	await until(func() -> bool: return _names(func(m: Marauder) -> bool: return m.faction == "pmc").size() >= AIPopulation.pmc_size(), 20)
	var pmc: Dictionary = _names(func(m: Marauder) -> bool: return m.faction == "pmc")
	check("ЧВК приехали: %d (по составу %d)" % [pmc.size(), AIPopulation.pmc_size()], pmc.size() == AIPopulation.pmc_size()
		and AIPopulation.pmc_size() == int((Balance.AI_POPULATION.pmc as Array)[_want - 1]))
	await _stage("ЧВК", pmc)


## Мародёр видит гостя — счётчик стычек открывает стычку с ним.
func _contact() -> void:
	var guest: Player = Raid.current.player_of(int(multiplayer.get_peers()[0]))
	var pop: AIPopulation = AIPopulation.current
	var best: Marauder = null
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m.faction == "marauder" and m.state == Marauder.State.PATROL:
			if best == null or m.global_position.distance_to(guest.global_position) < best.global_position.distance_to(guest.global_position):
				best = m
	# место в 8 м от гостя, откуда его видно
	var map: RID = (get_tree().current_scene as Node3D).get_world_3d().navigation_map
	var at: Vector3 = Vector3.INF
	for i in range(8):
		var a: float = TAU * float(i) / 8.0
		var p: Vector3 = NavigationServer3D.map_get_closest_point(map, guest.global_position + Vector3(cos(a), 0.0, sin(a)) * 8.0)
		if p.distance_to(guest.global_position) > 4.0 and pop._visible(p, guest.global_position):
			at = p
			break
	check("рядом с гостем есть место, откуда его видно", at != Vector3.INF and best != null)
	if at == Vector3.INF or best == null:
		return
	best.global_position = at + Vector3.UP * 0.1
	best._set_move_target(at)
	best.pause_timer = 30.0
	var contacts: RaidContacts = RaidContacts.current
	var counted: Callable = func() -> bool:
		# пока не заметил — стоит лицом к гостю
		if best._target_player == null:
			best._facing = atan2(guest.global_position.x - best.global_position.x, guest.global_position.z - best.global_position.z)
		return best._target_player == guest and not contacts._open.is_empty() and (contacts._open.get("enemies", {}) as Dictionary).has(best.get_instance_id())
	await until(counted, 15)
	check("мародёр увидел гостя — стычка засчитана", counted.call())


## Этап сверки: гости ждут у себя эти имена, потом просят свежие позиции и сравнивают.
func _stage(stage: String, names: Dictionary) -> void:
	_reports.erase(stage)
	_expect.rpc(stage, names.keys())
	await until(func() -> bool: return (_reports.get(stage, []) as Array).size() >= _want - 1, 90)
	check("у гостей «%s»: %d бойцов там же, где у хоста" % [stage, names.size()], _all_passed(stage))


func _names(filter: Callable) -> Dictionary:
	var out: Dictionary = {}
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m and not m.is_queued_for_deletion() and filter.call(m):
			out[String(m.name)] = m.global_position
	return out


func _all_passed(stage: String) -> bool:
	var list: Array = _reports.get(stage, [])
	if list.size() < _want - 1:
		return false
	for r in list:
		if not bool(r):
			return false
	return true


@rpc("any_peer", "call_remote", "reliable")
func _ready_client() -> void:
	clients_ready += 1


@rpc("any_peer", "call_remote", "reliable")
func _want_fresh(stage: String, names: Array) -> void:
	var out: Dictionary = {}
	var root: Node = get_tree().current_scene.get_node("Marauders")
	for nm in names:
		var m := root.get_node_or_null(NodePath(String(nm))) as Node3D
		if m:
			out[String(nm)] = m.global_position
	_fresh_positions.rpc_id(multiplayer.get_remote_sender_id(), stage, out)


@rpc("any_peer", "call_remote", "reliable")
func _client_report(stage: String, passed: bool, detail: String) -> void:
	var list: Array = _reports.get(stage, [])
	list.append(passed)
	_reports[stage] = list
	print("coop_pop_host: гость %d, «%s» — %s %s" % [multiplayer.get_remote_sender_id(), stage, "да" if passed else "НЕТ", detail])


@rpc("any_peer", "call_remote", "reliable")
func _placed() -> void:
	_placed_n += 1


# ---------------------------------------------------------------- гость

@rpc("authority", "call_remote", "reliable")
func _expect(stage: String, names: Array) -> void:
	var root: Node = get_tree().current_scene.get_node("Marauders")
	var missing: Callable = func() -> Array:
		return names.filter(func(nm: Variant) -> bool: return root.get_node_or_null(NodePath(String(nm))) == null)
	await until(func() -> bool: return (missing.call() as Array).is_empty(), 60)
	var lost: Array = missing.call()
	_fresh.erase(stage)
	_want_fresh.rpc_id(1, stage, names)
	await until(func() -> bool: return _fresh.has(stage), 20)
	var host_pos: Dictionary = _fresh.get(stage, {})
	var off: Array[String] = []
	for nm in host_pos:
		var m := root.get_node_or_null(NodePath(String(nm))) as Node3D
		if m == null or m.global_position.distance_to(host_pos[nm] as Vector3) > 4.0:
			off.append("%s %.1f м" % [nm, m.global_position.distance_to(host_pos[nm] as Vector3) if m else -1.0])
	var ok: bool = lost.is_empty() and off.is_empty() and host_pos.size() == names.size()
	check("«%s»: у меня все %d, позиции сходятся" % [stage, names.size()], ok)
	_client_report.rpc_id(1, stage, ok, "нет %s, разошлись %s" % [str(lost), str(off)])


@rpc("authority", "call_remote", "reliable")
func _fresh_positions(stage: String, positions: Dictionary) -> void:
	_fresh[stage] = positions


@rpc("authority", "call_remote", "reliable")
func _measure_move() -> void:
	var root: Node = get_tree().current_scene.get_node("Marauders")
	var start: Dictionary = {}
	for m in root.get_children():
		start[m.name] = (m as Node3D).global_position
	await get_tree().create_timer(8.0).timeout
	var moved: int = 0
	for m in root.get_children():
		if start.has(m.name) and (m as Node3D).global_position.distance_to(start[m.name] as Vector3) > 1.0:
			moved += 1
	var ok: bool = moved >= 3
	check("мародёры у меня ходят: сдвинулись %d из %d" % [moved, start.size()], ok)
	_client_report.rpc_id(1, "ходят", ok, "сдвинулись %d" % moved)


@rpc("authority", "call_remote", "reliable")
func _go_to(at: Vector3) -> void:
	_stand(Raid.current.local_player(), at)
	_placed.rpc_id(1)


@rpc("authority", "call_remote", "reliable")
func _finish() -> void:
	_done = true


# ---------------------------------------------------------------- общее

## Поставить своего игрока на землю у точки и не дать ему уйти.
func _stand(me: Player, at: Vector3) -> void:
	var map: RID = (get_tree().current_scene as Node3D).get_world_3d().navigation_map
	me.set_physics_process(false)
	me.velocity = Vector3.ZERO
	me.global_position = NavigationServer3D.map_get_closest_point(map, at) + Vector3.UP * 0.05


func until(condition: Callable, seconds: float = 40.0) -> void:
	var end: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call() and Time.get_ticks_msec() < end:
		await get_tree().create_timer(0.1).timeout


func check(label: String, passed: bool) -> void:
	print("OK " if passed else "FAIL ", label)
	if not passed:
		fails += 1


func _process(_delta: float) -> void:
	if Raid.current == null:
		return
	# игроков не убить: смотрим население, а не бой
	if not Net.is_networked() or multiplayer.is_server():
		for node: Node in get_tree().get_nodes_in_group("players"):
			(node as Player).health.hp = 1e9
