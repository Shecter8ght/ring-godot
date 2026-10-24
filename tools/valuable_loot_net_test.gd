extends Node
## Два реальных ENet peer: общая модель, полный рюкзак, повторный запрос, вынос и продажа.
const PORT: int = 17789
var role: String = "host"
var fails: int = 0
var phase: int = 0
var ack: int = 0
var result: int = -1
var client_ready: bool = false
var target: NodePath


func _ready() -> void:
	if name != "ValuableNetRunner":
		var runner: Node = Node.new()
		runner.name = "ValuableNetRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://valuable_net_%s.json" % role, true)
	Profile.backpack = []
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.from_hideout = true
	Profile.save()
	RaidEvents.enabled = false
	check("ENet", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2)
	if role == "host":
		Net.start_level.rpc("res://scenes/levels/mall_map.tscn", {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2 and Raid.current.local_player().inventory.loadout_ready)
	var me: Player = Raid.current.local_player()
	if role == "client":
		me.set_physics_process(false)
		_ready_client.rpc_id(1)
		await until(func() -> bool: return phase >= 1 and me.inventory.has("pack_939_sp6"))
		Raid.current.request_unpack(0, "pack_939_sp6")
		Raid.current.request_unpack(0, "pack_939_sp6")
		await until(func() -> bool: return not me.inventory.has("pack_939_sp6") and me.inventory.has("ammo_939_sp6"))
		check("повторное вскрытие не копирует патроны", me.inventory.count("ammo_939_sp6") == 30)
		_ack.rpc_id(1, 1)
		await until(func() -> bool: return phase >= 2)
		me.global_position = Vector3(500, 0.1, 500)
		Raid.current.request_supply_signal()
		Raid.current.request_supply_signal()
		await until(func() -> bool: return not Raid.current.supply_state.is_empty() and me.inventory.count("supply_signal") == 1)
		check("клиент видит один вызов и многоразовый пистолет", me.inventory.count("signal_launcher") == 1)
		_ack.rpc_id(1, 2)
		await until(func() -> bool: return phase >= 3 and bool(Raid.current.supply_state.get("dropped", false)) and not _crates().is_empty())
		var crate: LootContainer = _crates()[0] as LootContainer
		check("один общий груз на клиенте", _crates().size() == 1 and crate.items.size() >= 4)
		await until(func() -> bool: return crate.global_position.y < 0.2)
		me.global_position = crate.global_position + Vector3(0.3, 0.1, 0)
		var id: String = String(crate.items[0].id)
		Raid.current.request_take_idx(crate, 0)
		await until(func() -> bool: return me.inventory.has(id))
		check("клиент забирает настоящую редкую находку", me.inventory.count(id) == 1)
		_ack.rpc_id(1, 3)
		await until(func() -> bool: return phase >= 4 and not Raid.current._exit_receipt.is_empty() and count_item(Profile.backpack, id) == 1)
		Profile._loaded = false
		Profile.ensure()
		var sell_idx: int = -1
		for i: int in range(Profile.backpack.size()):
			if String(Profile.backpack[i].id) == id:
				sell_idx = i
		var before: int = Profile.money
		check("вынос, сохранение и продажа редкого груза", sell_idx >= 0 and Profile.sell(sell_idx, 1, "backpack") and Profile.money - before == Profile.sell_price(ItemDb.make(id, 1)))
		_result.rpc_id(1, fails)
		print("valuable_net_client: failures=", fails)
		await get_tree().create_timer(0.5).timeout
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return client_ready)
	var friend: Player = Raid.current.player_of(multiplayer.get_peers()[0])
	friend.inventory.items = [ItemDb.make("pack_939_sp6", 1), ItemDb.make("signal_launcher", 1), ItemDb.make("supply_signal", 2)]
	_set_phase.rpc(1)
	await until(func() -> bool: return ack >= 1)
	check("хост выдал ровно 30 патронов", friend.inventory.count("ammo_939_sp6") == 30)
	var floor_body: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = Vector3(20, 0.2, 20)
	collision.shape = shape
	floor_body.add_child(collision)
	get_tree().current_scene.add_child(floor_body)
	floor_body.global_position = Vector3(500, -0.1, 500)
	friend.global_position = Vector3(500, 0.1, 500)
	await get_tree().physics_frame
	await get_tree().physics_frame
	_set_phase.rpc(2)
	await until(func() -> bool: return ack >= 2)
	check("хост расходовал один патрон", friend.inventory.count("supply_signal") == 1)
	Raid.current.supply_state.elapsed = float(Balance.SUPPLY_SIGNAL.delay) - 0.01
	Raid.current._tick_supply(0.02)
	_set_phase.rpc(3)
	await until(func() -> bool: return not _crates().is_empty() and (_crates()[0] as LootContainer).global_position.y < 0.2)
	friend.global_position = Raid.current.supply_state.pos
	await until(func() -> bool: return ack >= 3)
	check("один груз на хосте", _crates().size() == 1)
	var ext: ExtractionPoint = ExtractionPoint.new()
	get_tree().current_scene.add_child(ext)
	Raid.current._extract(friend, ext)
	_set_phase.rpc(4)
	await until(func() -> bool: return result >= 0)
	print("valuable_net_host: failures=", fails + maxi(result, 0))
	await get_tree().create_timer(0.6).timeout
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


func _crates() -> Array:
	return Raid.current._drops.get_children().filter(func(n: Node) -> bool: return n is LootContainer and n.display_name == Raid.SUPPLY_DROP_NAME)


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


func until(condition: Callable) -> void:
	var end: int = Time.get_ticks_msec() + 40000
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
