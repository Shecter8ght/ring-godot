extends Node
## Два реальных ENet peer: общая модель, полный рюкзак, повторный запрос, вынос и продажа.
const PORT: int = 17788
var role: String = "host"
var fails: int = 0
var phase: int = 0
var ack: int = 0
var result: int = -1
var client_ready: bool = false
var target: NodePath
var result_confirmed: bool = false


func _ready() -> void:
	if name != "LootNetRunner":
		var runner: Node = Node.new()
		runner.name = "LootNetRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://loot_net_%s.json" % role, true)
	Profile.backpack = []
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.from_hideout = true
	Profile.save()
	RaidEvents.enabled = false
	check("ENet подключение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2)
	if role == "host":
		var level_path: String = OS.get_environment("LOOT_NET_LEVEL")
		if level_path == "":
			level_path = "res://scenes/levels/f1_market.tscn"
		Net.start_level.rpc(level_path, {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2 and Raid.current.local_player().inventory.loadout_ready)
	var me: Player = Raid.current.local_player()
	# Поздний спавн отрядов после готовности навмеша не должен вмешиваться в проверку вещей.
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
	if role == "client":
		_ready_client.rpc_id(1)
		await until(func() -> bool: return phase >= 1)
		var found: LooseLoot = Raid.current.get_node(target) as LooseLoot
		await until(func() -> bool: return not found.items.is_empty() and me.inventory.items.size() > 2)
		check("клиент видит модель хоста", found._vis.get_child_count() == 1 and String(found.items[0].id) == "multimeter")
		me.global_position = found.global_position + Vector3(0.5, 0.1, 0)
		await get_tree().create_timer(0.8).timeout
		found.request_use()
		await get_tree().create_timer(0.7).timeout
		check("полный рюкзак не удалил находку", found.items.size() == 1 and not me.inventory.has("multimeter"))
		_ack.rpc_id(1, 1)
		await until(func() -> bool: return phase >= 2 and me.inventory.items.is_empty())
		found.request_use()
		found.request_use()
		await until(func() -> bool: return found.items.is_empty() and me.inventory.has("multimeter"))
		check("повторный сетевой запрос даёт ровно одну вещь", me.inventory.count("multimeter") == 1)
		check("модель и подсказка исчезли на клиенте", found._vis.get_child_count() == 0 and not found.can_use())
		_ack.rpc_id(1, 2)
		await until(func() -> bool: return phase >= 3 and not Raid.current._exit_receipt.is_empty())
		check("надёжное подтверждение выноса содержит вещь", count_item(Raid.current._exit_receipt.items, "multimeter") == 1)
		# Надёжное подтверждение и обычная репликация статуса эвакуации могут прийти в разные кадры.
		await until(func() -> bool: return count_item(Profile.backpack, "multimeter") == 1)
		Profile._loaded = false
		Profile.ensure()
		var before: int = Profile.money
		check("клиент сохранил и продал вынесенную вещь", Profile.sell(0, 1, "backpack") and Profile.money - before == Profile.sell_price(ItemDb.make("multimeter", 1)))
		_result.rpc_id(1, fails)
		await until(func() -> bool: return result_confirmed)
		await get_tree().create_timer(0.5).timeout
		print("loot_net_client: failures=", fails)
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return client_ready)
	var points: Array[Node] = get_tree().get_nodes_in_group("loose_loot")
	check("на карте есть точки вне ящиков", not points.is_empty())
	if points.is_empty():
		get_tree().quit(1)
		return
	var found: LooseLoot = points[0] as LooseLoot
	var entry: Dictionary = ItemDb.make("multimeter", 1)
	entry["fir"] = true
	found.items = [entry]
	found.rolled = true
	var friend: Player = Raid.current.player_of(multiplayer.get_peers()[0])
	var grid: Vector2i = friend.inventory.backpack_grid()
	var full: Array = []
	for y: int in range(grid.y):
		for x: int in range(grid.x):
			full.append({"id": "watch", "n": ItemDb.stack("watch"), "x": x, "y": y})
	friend.inventory.items = full
	_set_target.rpc(Raid.current.get_path_to(found))
	_set_phase.rpc(1)
	await until(func() -> bool: return ack >= 1)
	check("хост сохранил вещь после отказа", found.items.size() == 1)
	friend.inventory.items = []
	_set_phase.rpc(2)
	await until(func() -> bool: return ack >= 2)
	check("хост видит тот же единственный экземпляр", friend.inventory.count("multimeter") == 1 and found.items.is_empty() and found._vis.get_child_count() == 0)
	var ext: ExtractionPoint = ExtractionPoint.new()
	ext.display_name = "Проверка выноса"
	get_tree().current_scene.add_child(ext)
	Raid.current._extract(friend, ext)
	_set_phase.rpc(3)
	await until(func() -> bool: return result >= 0)
	if not multiplayer.get_peers().is_empty():
		_confirm_result.rpc_id(int(multiplayer.get_peers()[0]))
	print("loot_net_host: failures=", fails + maxi(result, 0))
	await get_tree().create_timer(0.6).timeout
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


@rpc("any_peer", "call_remote", "reliable")
func _ready_client() -> void:
	client_ready = true


@rpc("authority", "call_local", "reliable")
func _set_target(path: NodePath) -> void:
	target = path


@rpc("authority", "call_local", "reliable")
func _set_phase(value: int) -> void:
	phase = value


@rpc("any_peer", "call_remote", "reliable")
func _ack(value: int) -> void:
	ack = value


@rpc("any_peer", "call_remote", "reliable")
func _result(value: int) -> void:
	result = value


@rpc("authority", "call_remote", "reliable")
func _confirm_result() -> void:
	result_confirmed = true


func until(condition: Callable) -> void:
	var wait_ms: int = 120000 if OS.get_environment("LOOT_NET_LEVEL") != "" else 40000
	var end: int = Time.get_ticks_msec() + wait_ms
	while not condition.call() and Time.get_ticks_msec() < end:
		await get_tree().create_timer(0.1).timeout
	if not condition.call():
		check("истекло ожидание", false)
		get_tree().quit(1)


func count_item(list: Array, id: String) -> int:
	var n: int = 0
	for entry: Dictionary in list:
		if String(entry.id) == id:
			n += int(entry.n)
	return n


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
