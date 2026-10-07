extends Node
## Контракты в группе (хост + гость, в убежище): гость видит доску хоста, берёт заказ — у хоста он
## взят; хост доводит цели до «отчитаться»; гость сдаёт через свой терминал — заказ выполнен у
## хоста, оплата и репутация — и хосту, и гостю (своему профилю, по разу).
## tools/godot.cmd --headless res://tools/contracts_net_test.tscn -- host
## tools/godot.cmd --headless res://tools/contracts_net_test.tscn -- client   (через 3 с)

var _fails: int = 0
var _mode: String = ""


func _ready() -> void:
	if name == "ContractsNetRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "ContractsNetRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	_mode = OS.get_cmdline_user_args()[0]
	Profile.use_file("user://contracts_net_%s.json" % _mode, true)
	Profile.ensure()
	if _mode == "host":
		await _host()
	else:
		await _client()
	print("contracts_net_%s: провалено %d" % [_mode, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _host() -> void:
	_check("сервер поднят", Net.host("Хост") == "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2, 40.0)
	Contracts.sync()
	# гость берёт заказ «Маяки» / «Без следа» / «Тихий район» — у хоста он станет активным
	await _until(func() -> bool: return Contracts.active_count() == 1, 20.0)
	_check("гость взял заказ — у хоста он взят", Contracts.active_count() == 1)
	var qid := ""
	for e: Dictionary in Contracts.board():
		if Quests.state(String(e.id)) == "ACTIVE":
			qid = String(e.id)
	var money0 := Profile.money
	var guard := 0
	while String(Quests.objective(qid).get("type", "")) != "talk" and guard < 10:
		Quests.dev_complete_objective(qid)
		guard += 1
	_check("хост: цели пройдены до сдачи", Contracts.can_turn_in(qid))
	# гость сдаёт через свой терминал
	await _until(func() -> bool: return not Profile.quests.has(qid), 20.0)
	_check("гость сдал — у хоста заказ выполнен и снят с доски", not Profile.quests.has(qid))
	_check("хосту оплата пришла", Profile.money > money0)
	await get_tree().create_timer(4.0).timeout


func _client() -> void:
	await get_tree().create_timer(3.0).timeout
	_check("подключение", Net.join("127.0.0.1", "Гость") == "")
	await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _until(func() -> bool: return Contracts.board().size() >= 10, 30.0)
	_check("гость видит доску хоста", Contracts.board().size() >= 10)
	var own_board: Array = Profile.contracts.get("board", [])
	_check("своя доска гостя не смешана с хостовой", own_board.is_empty() or JSON.stringify(own_board) != JSON.stringify(Contracts.board()))
	var e: Dictionary = {}
	for x: Dictionary in Contracts.board():
		if String(x.tpl) in ["beacons", "no_trace", "quiet"]:
			e = x
			break
	var qid := String(e.id)
	var gid := String(e.giver)
	var money0 := Profile.money
	var rep0 := Contracts.rep_points(gid)
	_check("взять заказ с терминала гостя", Contracts.take(qid) == "")
	await _until(func() -> bool: return Quests.state(qid) == "ACTIVE", 10.0)
	_check("заказ взят и у гостя (снимок хоста)", Quests.state(qid) == "ACTIVE")
	await _until(func() -> bool: return Contracts.can_turn_in(qid), 20.0)
	_check("гость видит: можно сдавать", Contracts.can_turn_in(qid))
	var reward: Dictionary = Contracts.build(e).reward
	_check("гость сдаёт", Contracts.turn_in(qid) == "")
	await _until(func() -> bool: return Profile.money > money0, 15.0)
	_check("гостю оплата пришла", Profile.money == money0 + int(reward.money))
	_check("гостю репутация у заказчика", Contracts.rep_points(gid) == rep0 + int((reward.rep as Dictionary)[gid]))
	await get_tree().create_timer(2.0).timeout


func _until(cond: Callable, sec: float) -> void:
	var t := 0.0
	while not bool(cond.call()) and t < sec:
		await get_tree().create_timer(0.2).timeout
		t += 0.2


func _check(what: String, ok: bool) -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + "%s: %s" % [_mode, what])
	if not ok:
		_fails += 1
