extends Node
## Обмен вещами в убежище, два реальных ENet peer (порт 17793): хост предлагает обмен — окно у обоих;
## каждый кладёт вещь в свою половину буфера, оба жмут «Передать» — вещи меняются хозяевами и не
## двоятся; отменённый обмен возвращает вещь владельцу.
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
	Profile.equipment = {"backpack": ItemDb.make("bp_tourist", 1)}
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
