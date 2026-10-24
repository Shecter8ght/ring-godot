extends Node
## Контракты терминала (Contracts): доска у каждого заказчика, заказ из шаблона детерминирован,
## взять → места в рейде → цели → сдать через терминал → деньги и репутация, заказ уходит с доски
## и выставляется новый; «Под заказ» — сдача найденного в рейде из тайника; отказ от взятого —
## репутация вниз; лимит взятых; невзятые заказы стареют за рейды; окно терминала строится.
## tools/godot.cmd --headless res://tools/contracts_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://contracts_test.json", true)
	Contracts.sync()
	var board: Array = Contracts.board()
	_check("доска: у каждого из 5 заказчиков по 2 заказа", board.size() == 5 * Contracts.OFFERS_PER_GIVER)
	var e: Dictionary = board[0]
	_check("заказ из шаблона одинаков при повторной сборке", JSON.stringify(Contracts.build(e)) == JSON.stringify(Contracts.build(e)))
	_check("заказ — квест-экземпляр, доступен", Quests.state(String(e.id)) == "AVAILABLE")
	# заказ с местами в рейде
	var site_e: Dictionary = _find(func(x: Dictionary) -> bool: return String(x.tpl) in ["beacons", "no_trace", "quiet"])
	_check("есть заказ с местами", not site_e.is_empty())
	var qid := String(site_e.id)
	var money0 := Profile.money
	var gid := String(site_e.giver)
	var rep0 := Contracts.rep_points(gid)
	_check("взять заказ", Contracts.take(qid) == "" and Quests.state(qid) == "ACTIVE")
	var sites: Array = Quests.sites_for("f1_ring").filter(func(s: Dictionary) -> bool: return String(s.quest) == qid)
	_check("места заказа на карте ТЦ", not sites.is_empty())
	_check("сдать нельзя, пока цели не выполнены", not Contracts.can_turn_in(qid))
	var guard := 0
	while String(Quests.objective(qid).get("type", "")) != "talk" and guard < 10:
		Quests.dev_complete_objective(qid)
		guard += 1
	_check("дошло до «отчитаться через терминал»", Contracts.can_turn_in(qid))
	_check("сдача", Contracts.turn_in(qid) == "")
	await get_tree().process_frame
	await get_tree().process_frame
	var reward: Dictionary = Contracts.build(site_e).reward
	_check("оплата пришла", Profile.money == money0 + int(reward.money))
	_check("репутация у заказчика выросла", Contracts.rep_points(gid) == rep0 + int((reward.rep as Dictionary)[gid]))
	_check("выполненный ушёл с доски, выставлен новый", _find(func(x: Dictionary) -> bool: return String(x.id) == qid).is_empty() and Contracts.board().size() == 5 * Contracts.OFFERS_PER_GIVER)
	_check("состояние выполненного убрано из профиля", not Profile.quests.has(qid))
	# «Под заказ»: сдать найденное в рейде
	var order_e := _force_offer("order", "sborshik")
	var oq := String(order_e.id)
	var o: Dictionary = (Contracts.build(order_e).stages[0].objectives as Array)[0]
	Contracts.take(oq)
	_check("«Под заказ»: без вещей сдать нельзя", not Contracts.can_turn_in(oq))
	var item := ItemDb.make(String(o.item), int(o.n))
	item["fir"] = true
	ItemDb.add_to(Profile.stash, item, Profile.stash_grid())
	var m1 := Profile.money
	_check("«Под заказ»: найденное в рейде — сдать можно", Contracts.can_turn_in(oq))
	Contracts.turn_in(oq)
	await get_tree().process_frame
	await get_tree().process_frame
	_check("«Под заказ»: вещи ушли, оплата пришла", Profile.stash_count(String(o.item), true) == 0 and Profile.money > m1)
	# лимит взятых и отказ
	var taken := 0
	for x: Dictionary in Contracts.board().duplicate():
		if Contracts.take(String(x.id)) == "":
			taken += 1
	_check("взять можно не больше %d" % Contracts.active_limit(), Contracts.active_count() == Contracts.active_limit())
	var act: Dictionary = _find(func(x: Dictionary) -> bool: return Quests.state(String(x.id)) == "ACTIVE")
	var g2 := String(act.giver)
	Profile.contracts.rep[g2] = 10
	Contracts.decline(String(act.id))
	_check("отказ от взятого: репутация на ступень вниз", Contracts.rep_points(g2) == 10 - Contracts.REP_STEP)
	_check("отказ: заказ снят", Quests.state(String(act.id)) != "ACTIVE" and _find(func(x: Dictionary) -> bool: return String(x.id) == String(act.id)).is_empty())
	# старение: невзятые заказы уходят через три рейда
	var fresh: Array = Contracts.board().filter(func(x: Dictionary) -> bool: return Quests.state(String(x.id)) == "AVAILABLE").map(func(x: Dictionary) -> String: return String(x.id))
	for i: int in range(Contracts.OFFER_RAIDS):
		Contracts.on_raid_end()
	var still := Contracts.board().filter(func(x: Dictionary) -> bool: return String(x.id) in fresh)
	_check("невзятые заказы устарели за %d рейда" % Contracts.OFFER_RAIDS, still.is_empty())
	_check("взятые остались", Contracts.active_count() == Contracts.active_limit() - 1)
	# окно терминала
	var ui := TerminalUI.new()
	add_child(ui)
	ui.open()
	await get_tree().process_frame
	await get_tree().process_frame
	_check("окно терминала открылось и построилось", ui.is_open() and ui.find_children("*", "Button", true, false).size() >= 7)
	ui.close_ui()
	# рейд: места взятого заказа встают на карте ТЦ (у всех заказов с местами)
	var beacons := _force_offer("beacons", "kotelnaya")
	Contracts.decline(String(_find(func(x: Dictionary) -> bool: return Quests.state(String(x.id)) == "ACTIVE").id))
	_check("взять «Маяки» для рейда", Contracts.take(String(beacons.id)) == "")
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	for i: int in range(300):
		await get_tree().process_frame
		if level.get_node("Marauders").get_child_count() > 0:
			break
	await get_tree().process_frame
	var placed := 0
	for sid: String in (Contracts.build(beacons).sites as Dictionary):
		if level.find_child("Quest_" + sid, true, false) != null:
			placed += 1
	_check("рейд: маяки заказа стоят на карте (%d из 3)" % placed, placed == 3)
	print("contracts_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _find(pred: Callable) -> Dictionary:
	for x: Dictionary in Contracts.board():
		if pred.call(x):
			return x
	return {}


## Заказ нужного шаблона у заказчика — прямо на доску (как выставил бы sync).
func _force_offer(tpl: String, gid: String) -> Dictionary:
	var st: Dictionary = Profile.contracts
	st.seq = int(st.get("seq", 0)) + 1
	var e := {"id": "ct_%d" % int(st.seq), "tpl": tpl, "giver": gid, "seed": 12345, "born": int(st.get("raids", 0))}
	(st.board as Array).append(e)
	Contracts.sync()
	return e


func _check(what: String, ok: bool) -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what)
	if not ok:
		_fails += 1
