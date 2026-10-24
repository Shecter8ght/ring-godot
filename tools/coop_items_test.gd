extends Node
## Кооп, вещи гостя в рейде (два реальных ENet peer, порт 17791): гость со снаряжением из профиля
## снаряжает магазин, сортирует рюкзак, меняет ствол в слоте, переключает оружие клавишей — и видит
## результат у себя (рюкзак считает хост и шлёт обратно). Уровень — вторым аргументом (умалчиваемый —
## зона 1 с ТЦ, где это ломалось): tools/godot.cmd --headless res://tools/coop_items_test.tscn -- host [сцена]
## и через 3 с то же с «-- client».
const PORT: int = 17791
var role: String = "host"
var fails: int = 0
var result: int = -1
var results: int = 0
var clients_ready: int = 0
## Сколько игроков в проверке (COOP_ITEMS_PEERS, умалчиваемо двое: хост и гость).
var _want: int = 2


func _ready() -> void:
	if name != "CoopItemsRunner":
		var runner: Node = Node.new()
		runner.name = "CoopItemsRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	role = String(args[0])
	if OS.get_environment("COOP_ITEMS_PEERS") != "":
		_want = int(OS.get_environment("COOP_ITEMS_PEERS"))
	var level: String = String(args[1]) if args.size() > 1 else "res://scenes/levels/zone01_mall.tscn"
	Profile.use_file("user://coop_items_%s_%d.json" % [role, OS.get_process_id() % 1000], true)
	_setup_profile()
	RaidEvents.enabled = false
	check("ENet подключение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == _want, 120)
	# третий аргумент «two»: сначала короткий рейд на маленькой карте и возврат в убежище — как в живой
	# игре, где второй рейд за вечер идёт по тем же сетевым путям, что и первый
	if args.size() > 2 and String(args[2]) == "two":
		if role == "host":
			Net.start_level.rpc("res://scenes/levels/mall_map.tscn", {"time": "day", "weather": "clear", "power": "on"})
		await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == _want and Raid.current.local_player().inventory.loadout_ready, 240)
		print("coop_items_%s: первый рейд идёт" % role)
		await get_tree().create_timer(4.0).timeout
		if role == "host":
			Raid.current.go_hideout()
		await until(func() -> bool: return Raid.current == null and get_tree().current_scene != null and Net.scene_of(get_tree().current_scene) == "hideout" and get_tree().get_nodes_in_group("players").size() == _want, 120)
		print("coop_items_%s: снова в убежище" % role)
		# ушли через меню — снаряжение осталось в рейде; собрать то же заново
		_setup_profile()
		await get_tree().create_timer(2.0).timeout
	if role == "host":
		Net.start_level.rpc(level, {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == _want and Raid.current.local_player().inventory.loadout_ready, 240)
	var me: Player = Raid.current.local_player()
	print("coop_items_%s: в рейде, вещей %d, надето %s" % [role, me.inventory.items.size(), str(me.inventory.equipment.keys())])
	if role == "client":
		_ready_client.rpc_id(1)
		await _items_pass(me)
		_result.rpc_id(1, fails)
		await get_tree().create_timer(0.5).timeout
		print("coop_items_client: failures=", fails)
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return clients_ready >= _want - 1, 240)
	if OS.get_environment("COOP_ITEMS_PERF") != "":
		await _perf("до действий")
	# хост делает то же со своим рюкзаком — и видит рюкзак гостя после его действий
	await _items_pass(me)
	await until(func() -> bool: return results >= _want - 1, 120)
	check("все гости отчитались", results >= _want - 1)
	# размеры сетевого состояния: узел рейда шлётся целиком (предел пакета ~1350 байт), рюкзак — изменениями
	var raid_bytes: int = 0
	for prop: String in ["participants", "switches", "extracted", "loot_value", "dead", "over", "channel", "drags", "evac_left", "evac_wait", "stranded", "supply_state", "gone"]:
		raid_bytes += var_to_bytes(Raid.current.get(prop)).size()
	print("coop_items_host: состояние рейда %d байт (переключателей %d), рюкзак %d байт, снаряжение %d байт" % [raid_bytes, Raid.current.switches.size(),
		var_to_bytes(me.inventory.items).size(), var_to_bytes(me.inventory.equipment).size()])
	check("состояние рейда помещается в пакет синхронизации", raid_bytes < 1200)
	for peer: int in multiplayer.get_peers():
		var friend: Player = Raid.current.player_of(peer)
		var loaded: bool = false
		for e: Dictionary in friend.inventory.items:
			if String(e.id) == "mag_545_30":
				loaded = true
		check("хост видит магазин гостя и его новый ствол", loaded and String((friend.inventory.equipment.get("primary", {}) as Dictionary).get("id", "")) == "wpn_smg_04")
	# гости вышли из игры посреди рейда: хост их больше не ждёт, вещи — мешком, рейд заканчивается
	var left: Array = Array(multiplayer.get_peers())
	await until(func() -> bool: return Raid.current.gone.size() >= left.size(), 60)
	check("вышедшие гости отмечены пропавшими", Raid.current.gone.size() >= left.size())
	var bags: int = 0
	for n: Node in Raid.current._drops.get_children():
		if n is LootContainer and (n as LootContainer).display_name.begins_with("Вещи: "):
			bags += 1
	check("их вещи остались мешками", bags == left.size())
	var ext: ExtractionPoint = ExtractionPoint.new()
	ext.display_name = "Проверка выхода"
	get_tree().current_scene.add_child(ext)
	Raid.current._extract(me, ext)
	check("хост вышел — рейд окончен, никого не ждём", Raid.current.over)
	print("coop_items_host: failures=", fails + maxi(result, 0))
	await get_tree().create_timer(0.6).timeout
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


## Нагрузка хоста (COOP_ITEMS_PERF=1, запускать с окном и --disable-vsync): кадры, время кадра и физики.
func _perf(label: String) -> void:
	await get_tree().create_timer(3.0).timeout
	var frames: int = 0
	var proc: float = 0.0
	var phys: float = 0.0
	var began: int = Time.get_ticks_msec()
	while Time.get_ticks_msec() - began < 5000:
		await get_tree().process_frame
		frames += 1
		proc += Performance.get_monitor(Performance.TIME_PROCESS)
		phys += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
	print("coop_items_host: нагрузка (%s, игроков %d): %.0f к/с, кадр %.2f мс, физика %.2f мс, вызовов отрисовки %d, узлов %d, мародёров %d" % [label, _want, frames / 5.0,
		proc / frames * 1000.0, phys / frames * 1000.0, int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
		int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)), get_tree().get_nodes_in_group("marauders").size()])


## Снаряжение и рюкзак из профиля: два ствола, запасной ствол, магазин, патроны — вразброс.
func _setup_profile() -> void:
	var rifle: Dictionary = ItemDb.make("wpn_ar_01", 1)
	(rifle.mag as Dictionary)["rounds"] = 30
	Profile.equipment = {"primary": rifle, "sidearm": ItemDb.make("wpn_hg_02", 1), "backpack": ItemDb.make("bp_tourist", 1)}
	Profile.backpack = []
	var grid: Vector2i = ItemDb.bag_grid(Profile.equipment)
	# вещи вразброс — сортировке есть что двигать
	ItemDb.put_at(Profile.backpack, ItemDb.make("bandage", 2), grid, grid.x - 1, grid.y - 1, false)
	ItemDb.put_at(Profile.backpack, ItemDb.make("mag_545_30", 1), grid, 2, 3, false)
	ItemDb.put_at(Profile.backpack, ItemDb.make("ammo_545_std", 60), grid, grid.x - 1, 0, false)
	ItemDb.add_to(Profile.backpack, ItemDb.make("wpn_smg_04", 1), grid)
	Profile.from_hideout = true
	Profile.save()


## Снарядить магазин, отсортировать, сменить ствол в слоте, переключить оружие — у своего игрока.
func _items_pass(me: Player) -> void:
	var inv: Inventory = me.inventory
	# магазины снаряжаются сами на входе в рейд — сначала разрядить, потом снарядить руками
	var rounds: Callable = func() -> int:
		var i: int = _find(inv, "mag_545_30")
		return int(inv.items[i].get("rounds", 0)) if i >= 0 else -1
	var full: int = int(rounds.call())
	Raid.current.request_item_op("unload", "backpack", _find(inv, "mag_545_30"))
	await until(func() -> bool: return int(rounds.call()) >= 0 and int(rounds.call()) <= full - 3, 30)
	check("магазин разряжается", int(rounds.call()) >= 0 and int(rounds.call()) <= full - 3)
	Raid.current.request_cancel_op()
	await get_tree().create_timer(0.5).timeout
	var low: int = int(rounds.call())
	Raid.current.request_item_op("load", "backpack", _find(inv, "mag_545_30"))
	await until(func() -> bool: return int(rounds.call()) >= low + 2, 30)
	check("магазин снаряжается", int(rounds.call()) >= low + 2)
	Raid.current.request_cancel_op()
	await get_tree().create_timer(0.4).timeout
	var before: String = _layout(inv)
	Raid.current.request_sort("backpack")
	await until(func() -> bool: return _layout(inv) != before, 15)
	check("рюкзак сортируется", _layout(inv) != before)
	var gun_idx: int = _find(inv, "wpn_smg_04")
	Raid.current.request_equip_from("backpack", gun_idx, null, "primary")
	await until(func() -> bool: return String((inv.equipment.get("primary", {}) as Dictionary).get("id", "")) == "wpn_smg_04", 15)
	check("ствол в слоте меняется, прежний — в рюкзаке", String((inv.equipment.get("primary", {}) as Dictionary).get("id", "")) == "wpn_smg_04" and _find(inv, "wpn_ar_01") >= 0)
	# клавиши 1 / 3 — оружие в руках (3 — пистолет)
	for pair: Array in [["weapon_3", "sidearm"], ["weapon_1", "primary"]]:
		Input.action_press(String(pair[0]))
		await get_tree().create_timer(0.15).timeout
		Input.action_release(String(pair[0]))
		await until(func() -> bool: return me.weapon_slot == String(pair[1]), 10)
		check("клавиша «%s» берёт %s" % [String(pair[0]), String(pair[1])], me.weapon_slot == String(pair[1]))
		await get_tree().create_timer(1.2).timeout
	check("в руках — новый ствол слота", me.weapon_id == "wpn_smg_04")


func _find(inv: Inventory, id: String) -> int:
	for i: int in range(inv.items.size()):
		if String(inv.items[i].id) == id:
			return i
	return -1


func _layout(inv: Inventory) -> String:
	var out: String = ""
	for e: Dictionary in inv.items:
		out += "%s@%d,%d " % [String(e.id), int(e.get("x", -1)), int(e.get("y", -1))]
	return out


@rpc("any_peer", "call_remote", "reliable")
func _ready_client() -> void:
	clients_ready += 1


@rpc("any_peer", "call_remote", "reliable")
func _result(value: int) -> void:
	result = maxi(result, value)
	results += 1


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
