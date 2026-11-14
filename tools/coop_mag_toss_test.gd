extends Node
## Кооп, быстрая перезарядка (два реальных ENet peer, порт 17799): старый магазин вылетает настоящим телом
## (TossedItem). Сначала двойное R делает гость, потом хост; оба видят полёт (у хоста тело считает физика, у
## того, кто смотрит, оно едет за хостом), слышат удар и находят лежащий магазин в одном и том же месте, с теми
## же патронами; гость подбирает свой — у хоста находка пустеет.
## tools/godot.cmd --headless res://tools/coop_mag_toss_test.tscn -- host   и через 3 с то же с «-- client».
const PORT: int = 17799
const LEVEL: String = "res://scenes/levels/mall_map.tscn"
var role: String = "host"
var fails: int = 0
var result: int = -1
var clients_ready: int = 0
## Что гость увидел у себя: метка события ("guest" — его перезарядка, "host" — перезарядка хоста) → {pos, rounds, flew, hits, sim}.
var seen_by_guest: Dictionary = {}
## Хост закончил свою перезарядку и сверку — гостю можно выходить.
var host_done: bool = false
var go_host: bool = false


func _ready() -> void:
	if name != "CoopMagTossRunner":
		var runner: Node = Node.new()
		runner.name = "CoopMagTossRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://coop_mag_toss_%s_%d.json" % [role, OS.get_process_id() % 1000], true)
	_setup_profile()
	RaidEvents.enabled = false
	check("ENet подключение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2, 120)
	if role == "host":
		Net.start_level.rpc(LEVEL, {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2 and Raid.current.local_player().inventory.loadout_ready, 240)
	var me: Player = Raid.current.local_player()
	print("coop_mag_toss_%s: в рейде" % role)
	await get_tree().create_timer(2.0).timeout
	if role == "client":
		_ready_client.rpc_id(1)
		# --- гость перезаряжается сам: тело считает хост, гость видит его полёт и лежащий магазин
		var mine: Dictionary = await _fast_reload(me)
		check("гость: его магазин вылетел телом и лёг (патронов %d)" % int(mine.get("rounds", -1)), not mine.is_empty())
		if not mine.is_empty():
			check("гость: тело у него не считается физикой, а едет за хостом (сдвинулось %.2f м)" % float(mine.flew), not bool(mine.sim) and float(mine.flew) > 0.3)
			check("гость: руки перестали рисовать магазин, когда тело пришло", me.mag_body_seen)
			check("гость: удар о поверхность слышен и у него", int(mine.hits) >= 1)
			_report.rpc_id(1, "guest", mine.pos, int(mine.rounds), float(mine.flew), int(mine.hits))
			# подобрать — магазин с теми же патронами снова в рюкзаке
			var lying: LooseLoot = mine.node
			var had: int = _mags(me, int(mine.rounds))
			lying.request_use()
			await until(func() -> bool: return _mags(me, int(mine.rounds)) == had + 1, 10)
			check("гость: подобрал — магазин с теми же патронами в рюкзаке", _mags(me, int(mine.rounds)) == had + 1)
		_go_host.rpc_id(1)
		# --- перезаряжается хост: гость видит его магазин
		var theirs: Dictionary = await _watch(1, 40.0)
		check("гость: видит полёт магазина хоста и лежащий магазин", not theirs.is_empty() and float(theirs.get("flew", 0.0)) > 0.3)
		if not theirs.is_empty():
			_report.rpc_id(1, "host", theirs.pos, int(theirs.rounds), float(theirs.flew), int(theirs.hits))
		await until(func() -> bool: return host_done, 30)
		_result.rpc_id(1, fails)
		await get_tree().create_timer(0.5).timeout
		print("coop_mag_toss_client: failures=", fails)
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return clients_ready >= 1, 240)
	var guest_id: int = multiplayer.get_peers()[0]
	# --- хост следит за магазином гостя
	var from_guest: Dictionary = await _watch(guest_id, 60.0)
	check("хост: магазин гостя вылетел телом (считает хост) и лёг", not from_guest.is_empty() and bool(from_guest.get("sim", false)))
	await until(func() -> bool: return seen_by_guest.has("guest"), 20)
	if not from_guest.is_empty() and seen_by_guest.has("guest"):
		var g: Dictionary = seen_by_guest.guest
		var apart: float = (g.pos as Vector3).distance_to(from_guest.pos)
		check("магазин гостя лежит у хоста и у гостя в одном месте (расхождение %.0f мм), патронов поровну (%d)" % [apart * 1000.0, int(g.rounds)],
			apart < 0.02 and int(g.rounds) == int(from_guest.rounds))
		var lying: LooseLoot = from_guest.node
		await until(func() -> bool: return go_host, 20)
		check("гость подобрал — у хоста находка пуста", not is_instance_valid(lying) or lying.items.is_empty())
	await until(func() -> bool: return go_host, 20)
	# --- хост перезаряжается сам
	var mine_host: Dictionary = await _fast_reload(me)
	check("хост: его магазин вылетел телом и лёг (патронов %d)" % int(mine_host.get("rounds", -1)), not mine_host.is_empty())
	await until(func() -> bool: return seen_by_guest.has("host"), 20)
	if not mine_host.is_empty() and seen_by_guest.has("host"):
		var h: Dictionary = seen_by_guest.host
		var apart_h: float = (h.pos as Vector3).distance_to(mine_host.pos)
		check("магазин хоста лежит у обоих в одном месте (расхождение %.0f мм), гость слышал удар" % (apart_h * 1000.0),
			apart_h < 0.02 and int(h.rounds) == int(mine_host.rounds) and int(h.hits) >= 1)
	else:
		check("гость отчитался о магазине хоста", false)
	_host_done.rpc()
	await until(func() -> bool: return result >= 0, 30)
	check("гость отчитался", result >= 0)
	print("coop_mag_toss_host: failures=", fails + maxi(result, 0))
	await get_tree().create_timer(0.6).timeout
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


## Двойное R у своего игрока и слежка за своим магазином.
func _fast_reload(me: Player) -> Dictionary:
	# с полным магазином перезарядка не начинается (на входе в рейд магазины снаряжаются) — отстрелять несколько
	var full: int = me.ammo
	Input.action_press("fire")
	await until(func() -> bool: return me.ammo < full - 2, 5)
	Input.action_release("fire")
	await get_tree().create_timer(0.8).timeout
	print("coop_mag_toss_%s: патронов %d из %d, в руках %s" % [role, me.ammo, full, me.weapon_id])
	for i: int in range(2):
		Input.action_press("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_release("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
	check("%s: двойное R — быстрая перезарядка" % role, me._reload_fast and me.reload_timer > 0.0)
	return await _watch(me.peer_id, 30.0)


## Дождаться тела магазина игрока peer и лежащей после него находки. {pos, rounds, flew — на сколько тело
## сдвинулось на глазах этого peer, hits — сколько ударов прозвучало, sim — считает ли его физика этого peer, node}.
func _watch(peer: int, seconds: float) -> Dictionary:
	var body: TossedItem = null
	var end: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while body == null and Time.get_ticks_msec() < end:
		await get_tree().process_frame
		for n: Node in get_tree().get_nodes_in_group("tossed_items"):
			if (n as TossedItem).owner_peer == peer:
				body = n as TossedItem
	if body == null:
		return {}
	var out: Dictionary = {"sim": not body.freeze, "flew": 0.0, "hits": 0, "rounds": int(body.entry.get("rounds", -1))}
	var from: Vector3 = body.global_position
	var last: Vector3 = from
	while is_instance_valid(body) and not body.is_queued_for_deletion():
		last = body.global_position
		out["hits"] = body.hit_count
		await get_tree().process_frame
	out["flew"] = from.distance_to(last)
	# находка появляется вместо тела (у гостя — на кадр-другой позже)
	var lying: LooseLoot = null
	end = Time.get_ticks_msec() + 5000
	while lying == null and Time.get_ticks_msec() < end:
		await get_tree().process_frame
		for n: Node in get_tree().get_nodes_in_group("loot_containers"):
			var c := n as LooseLoot
			if c != null and c.dropped and c.posed and not c.items.is_empty() and c.global_position.distance_to(last) < 0.6:
				lying = c
	if lying == null:
		return {}
	var holder: Node3D = lying._vis.get_node_or_null("Laid") as Node3D
	out["pos"] = holder.global_position if holder else lying.global_position
	out["rounds"] = int((lying.items[0] as Dictionary).get("rounds", -1))
	out["node"] = lying
	check("%s: магазин лежит там, где остановилось тело (%.0f мм)" % [role, (out.pos as Vector3).distance_to(last) * 1000.0], (out.pos as Vector3).distance_to(last) < 0.05)
	return out


## Сколько в рюкзаке магазинов с rounds патронами.
func _mags(me: Player, rounds: int) -> int:
	var n: int = 0
	for e: Dictionary in me.inventory.items:
		if e.has("rounds") and int(e.rounds) == rounds:
			n += 1
	return n


## ВЕРАС-54 с неполным магазином и два запасных в рюкзаке.
func _setup_profile() -> void:
	var rifle: Dictionary = ItemDb.make("wpn_ar_01", 1)
	(rifle.mag as Dictionary)["rounds"] = 12
	Profile.equipment = {"primary": rifle, "backpack": ItemDb.make("bp_tourist", 1)}
	Profile.backpack = []
	var grid: Vector2i = ItemDb.bag_grid(Profile.equipment)
	for i: int in range(2):
		ItemDb.add_to(Profile.backpack, WeaponDb.make_mag(WeaponDb.default_mag("wpn_ar_01"), WeaponDb.default_ammo("545x39"), 30), grid)
	Profile.from_hideout = true
	Profile.save()


@rpc("any_peer", "call_remote", "reliable")
func _ready_client() -> void:
	clients_ready += 1


@rpc("any_peer", "call_remote", "reliable")
func _report(tag: String, pos: Vector3, rounds: int, flew: float, hits: int) -> void:
	seen_by_guest[tag] = {"pos": pos, "rounds": rounds, "flew": flew, "hits": hits}


@rpc("any_peer", "call_remote", "reliable")
func _go_host() -> void:
	go_host = true


@rpc("authority", "call_remote", "reliable")
func _host_done() -> void:
	host_done = true


@rpc("any_peer", "call_remote", "reliable")
func _result(value: int) -> void:
	result = maxi(result, value)


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
	for node: Node in get_tree().get_nodes_in_group("marauders"):
		node.set_physics_process(false)
	if not Net.is_networked() or multiplayer.is_server():
		for node: Node in get_tree().get_nodes_in_group("players"):
			(node as Player).health.hp = 1e9
