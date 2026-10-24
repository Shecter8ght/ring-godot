extends Node
## Обмен вещами, два реальных ENet peer (порт 17793). Убежище: хост предлагает обмен — окно у обоих;
## каждый кладёт вещь в свою половину буфера, оба жмут «Передать» — вещи меняются хозяевами и не
## двоятся; отменённый обмен возвращает вещь владельцу; слева виден рюкзак напарника. Затем рейд: то же
## через хоста (сетка "trade" рюкзака, Raid.trades) — обмен обратно, и обмен, сорванный расстоянием.
## tools/godot.cmd --headless res://tools/trade_net_test.tscn -- host  и через 3 с то же с «-- client».
const PORT: int = 17793
var role: String = "host"
var fails: int = 0
var result: int = -1
var phase: int = 0


func _ready() -> void:
	if name != "TradeNetRunner":
		var runner: Node = Node.new()
		runner.name = "TradeNetRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	await _run()


func _run() -> void:
	role = String(OS.get_cmdline_user_args()[0])
	Profile.use_file("user://trade_net_%s.json" % role, true)
	# у обоих надет пояс с пистолетным подсумком и магазином в нём — его отдают прямо из подсумка
	var rig: Dictionary = ItemDb.make("belt_pouches", 1)
	ItemDb.attach_pouch(rig, "pouch_pistol")
	rig["mags"] = [WeaponDb.make_mag("mag_919_17", "ammo_919_fmj", 17)]
	((rig.mags as Array)[0] as Dictionary).merge({"x": 0, "y": 0, "r": false})
	Profile.equipment = {"backpack": ItemDb.make("bp_tourist", 1), "armor": rig}
	Profile.backpack = []
	Profile.stash = []
	# хост отдаёт магазин с патронами, гость — бинты
	var mine: Dictionary = WeaponDb.make_mag("mag_545_30", "ammo_545_std", 30) if role == "host" else ItemDb.make("bandage", 3)
	ItemDb.add_to(Profile.backpack, mine, Profile.grid_of("backpack"))
	ItemDb.add_to(Profile.backpack, ItemDb.make("water", 1), Profile.grid_of("backpack"))
	Profile.save()
	check("ENet подключение", (Net.host("Хост", PORT) if role == "host" else Net.join("127.0.0.1", "Друг", PORT)) == "")
	if role == "client":
		await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2 and Net.visible_in(_other(), "hideout"), 120)
	await get_tree().create_timer(1.0).timeout
	# --- отменённый обмен: вещь возвращается
	if role == "host":
		check("обмен доступен рядом с напарником", Trade.can_trade(_other()))
		Trade.request(_other())
	await until(func() -> bool: return Trade.is_open(), 20)
	check("окно обмена открылось у обоих", Trade.is_open() and Trade.partner == _other())
	if role == "host":
		Trade._quick("backpack", _find("mag_545_30"))
		check("вещь ушла из рюкзака в буфер", _find("mag_545_30") < 0 and Trade._offer.size() == 1 and Profile.trade_hold.size() == 1)
		await get_tree().create_timer(0.6).timeout
		Trade.close_ui()
		check("отменил — вещь снова в рюкзаке", _find("mag_545_30") >= 0 and Profile.trade_hold.is_empty())
	else:
		await until(func() -> bool: return Trade._their.size() == 1 or not Trade.is_open(), 20)
	await until(func() -> bool: return not Trade.is_open(), 20)
	check("отмена закрыла окно у обоих", not Trade.is_open() and Trade.partner == 0)
	await get_tree().create_timer(1.0).timeout
	# --- настоящий обмен
	if role == "host":
		Trade.request(_other())
	await until(func() -> bool: return Trade.is_open(), 20)
	var give: String = "mag_545_30" if role == "host" else "bandage"
	var take: String = "bandage" if role == "host" else "mag_545_30"
	Trade._quick("backpack", _find(give))
	await until(func() -> bool: return Trade._their.size() == 1, 20)
	check("вижу, что отдаёт напарник", Trade._their.size() == 1 and String(Trade._their[0].id) == take)
	check("вижу рюкзак напарника (вода осталась в нём)", Trade._their_backpack().size() == 1 and String(Trade._their_backpack()[0].id) == "water", str(Trade._their_backpack()))
	await get_tree().create_timer(0.5 if role == "host" else 1.2).timeout
	if DisplayServer.get_name() != "headless":
		# с окном — снимок окна обмена
		for i in range(20):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/trade_%s.png" % role))
	Trade._set_ready(true)
	await until(func() -> bool: return Trade.partner == 0, 30)
	check("обмен состоялся: окно закрыто", not Trade.is_open())
	check("получил вещь напарника, свою отдал", _find(take) >= 0 and _find(give) < 0, str(Profile.backpack))
	if role == "host":
		check("бинтов пришло три", int(Profile.backpack[_find("bandage")].n) == 3)
	else:
		check("магазин пришёл с патронами", int(Profile.backpack[_find("mag_545_30")].get("rounds", 0)) == 30)
	check("в буфере ничего не осталось", Profile.trade_hold.is_empty())
	await _raid_part(take, give)
	if role == "client":
		_result.rpc_id(1, fails)
		await get_tree().create_timer(0.5).timeout
		print("trade_net_client: failures=", fails)
		get_tree().quit(1 if fails else 0)
		return
	await until(func() -> bool: return result >= 0, 60)
	print("trade_net_host: failures=", fails + maxi(result, 0))
	await get_tree().create_timer(0.6).timeout
	get_tree().quit(1 if fails > 0 or result > 0 else 0)


## Рейд: вещи у хоста. Меняемся обратно (у меня сейчас mine, хочу вернуть back), потом обмен рвётся,
## когда расходимся.
func _raid_part(mine: String, back: String) -> void:
	Profile.from_hideout = true
	RaidEvents.enabled = false
	await get_tree().create_timer(1.0).timeout
	if role == "host":
		Net.start_level.rpc("res://scenes/levels/mall_map.tscn", {"time": "day", "weather": "clear", "power": "on"})
	await until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2 and Raid.current.local_player().inventory.loadout_ready, 240)
	var raid: Raid = Raid.current
	var me: Player = raid.local_player()
	var inv: Inventory = me.inventory
	for m: Node in get_tree().get_nodes_in_group("marauders"):
		m.set_physics_process(false)
	me.health.invulnerable = true
	await get_tree().create_timer(1.5).timeout
	check("в рейде при мне вещь из обмена в убежище", _in(inv.items, mine) >= 0, str(inv.items))
	if role == "host":
		raid.request_trade(_other())
	await until(func() -> bool: return Trade.is_open(), 20)
	check("рейд: окно обмена открылось у обоих", Trade.is_open() and raid.trades.has(multiplayer.get_unique_id()))
	# хост кладёт вещь в буфер первым — гость может увидеть её уже там, а в рюкзаке напарника — только воду
	check("рейд: слева виден рюкзак напарника", _in(Trade._their_backpack(), "water") >= 0 and (_in(Trade._their_backpack(), back) >= 0 or _in(Trade._their_offer(), back) >= 0), str(Trade._their_backpack()))
	Trade._quick("backpack", _in(inv.items, mine))
	await until(func() -> bool: return inv.trade.size() == 1 and Trade._their_offer().size() == 1, 20)
	check("рейд: вещь в моей половине буфера, вижу половину напарника", inv.trade.size() == 1 and _in(inv.items, mine) < 0 and _in(Trade._their_offer(), back) >= 0)
	await get_tree().create_timer(0.5 if role == "host" else 1.2).timeout
	if DisplayServer.get_name() != "headless":
		for i in range(20):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/trade_raid_%s.png" % role))
	Trade._set_ready(true)
	await until(func() -> bool: return not raid.trades.has(multiplayer.get_unique_id()), 30)
	await get_tree().create_timer(0.5).timeout
	check("рейд: обмен состоялся — своя вещь вернулась, чужая ушла", _in(inv.items, back) >= 0 and _in(inv.items, mine) < 0 and inv.trade.is_empty() and not Trade.is_open(), str(inv.items))
	# магазин — прямо из подсумка надетой разгрузки: отдаёт хост, гость ничего не кладёт
	await get_tree().create_timer(1.0).timeout
	if role == "host":
		raid.request_trade(_other())
	await until(func() -> bool: return Trade.is_open(), 20)
	await get_tree().create_timer(0.4).timeout
	check("рейд: в окне видны подсумки — свои и напарника", Trade._grid("rig") != Vector2i.ZERO and Trade._their_rig_grid("rig") != Vector2i.ZERO and Trade._their_rig_list("rig").size() == 1)
	if role == "host":
		Trade._quick("rig", 0)
		await until(func() -> bool: return inv.trade.size() == 1 and inv.list_of("rig").is_empty(), 20)
		check("рейд: магазин из подсумка лёг в буфер", inv.trade.size() == 1 and inv.list_of("rig").is_empty())
	else:
		await until(func() -> bool: return Trade._their_offer().size() == 1, 20)
	await get_tree().create_timer(0.5 if role == "host" else 1.2).timeout
	if DisplayServer.get_name() != "headless":
		for i in range(20):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/trade_raid_rig_%s.png" % role))
	Trade._set_ready(true)
	await until(func() -> bool: return not raid.trades.has(multiplayer.get_unique_id()), 30)
	await get_tree().create_timer(0.5).timeout
	if role == "host":
		check("рейд: магазин ушёл из подсумка насовсем", inv.list_of("rig").is_empty() and _in(inv.items, "mag_919_17") < 0 and inv.trade.is_empty())
	else:
		var got: int = _in(inv.items, "mag_919_17")
		check("рейд: получил магазин напарника с патронами, свой остался в подсумке", got >= 0 and int(inv.items[got].get("rounds", 0)) == 17 and inv.list_of("rig").size() == 1, str(inv.items))
	# второй обмен: положили вещь и разошлись — хост рвёт обмен, вещь снова в рюкзаке
	await get_tree().create_timer(1.0).timeout
	if role == "host":
		raid.request_trade(_other())
	await until(func() -> bool: return Trade.is_open(), 20)
	Trade._quick("backpack", _in(inv.items, back))
	await until(func() -> bool: return inv.trade.size() == 1, 20)
	check("рейд: вещь снова в буфере", inv.trade.size() == 1)
	await get_tree().create_timer(1.0).timeout
	if role == "host":
		me.global_position += Vector3(float(Balance.TRADE.break_m) + 3.0, 0.0, 0.0)
	await until(func() -> bool: return not raid.trades.has(multiplayer.get_unique_id()), 30)
	await get_tree().create_timer(0.5).timeout
	check("рейд: разошлись — обмен отменён, вещь вернулась в рюкзак", _in(inv.items, back) >= 0 and inv.trade.is_empty() and not Trade.is_open(), str(inv.items))


func _in(list: Array, id: String) -> int:
	for i: int in range(list.size()):
		if String(list[i].id) == id:
			return i
	return -1


func _other() -> int:
	var peers: PackedInt32Array = multiplayer.get_peers()
	return int(peers[0]) if not peers.is_empty() else 0


func _find(id: String) -> int:
	for i: int in range(Profile.backpack.size()):
		if String(Profile.backpack[i].id) == id:
			return i
	return -1


@rpc("any_peer", "call_remote", "reliable")
func _result(value: int) -> void:
	result = value


func until(condition: Callable, seconds: float = 40.0) -> void:
	var end: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call() and Time.get_ticks_msec() < end:
		await get_tree().create_timer(0.1).timeout


func check(label: String, passed: bool, info: String = "") -> void:
	print(("OK " if passed else "FAIL ") + label + ("  " + info if not passed and info != "" else ""))
	if not passed:
		fails += 1
