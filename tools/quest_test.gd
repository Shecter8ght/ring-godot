extends Node
## Сюжетный квест «Не вернулся» целиком, без рук: разговор с Сергеем → улика только на своём
## этапе → «эвакуируйся» → смерть не засчитывает → эвакуация сохраняет (и в файл) → разговор
## открывает следующий этап → … → Антон появляется только на финале, его надо донести до
## эвакуации (смерть по дороге — этап заново) → Антон в убежище → квест выполнен, флаги, награда.
## И второй квест из одних данных — ядро не трогаем. godot --path . res://tools/quest_test.tscn (--headless)

const TEST_PROFILE := "user://profile_quest_test.json"
const Q := "missing_anton"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.use_file(TEST_PROFILE, true)
	Profile.ensure()
	await get_tree().process_frame
	# 1. Сергей: квест доступен, разговор начинает
	_check("квест доступен у Сергея", Quests.state(Q) == "AVAILABLE" and not Quests.talk_options("trader").is_empty(), Quests.state(Q))
	var opt: Dictionary = Quests.talk_options("trader")[0]
	# окно разговора показывает и кто говорит, и текст реплики
	if Quests.hud:
		Quests.hud.start_dialogue(Quests.dialogue(String(opt.quest), String(opt.dialogue)), func() -> void: pass)
		_check("разговор: видно, кто говорит, и текст", Quests.hud._dlg_who.text != "" and Quests.hud._dlg_text.text != "", Quests.hud._dlg_text.text)
		Quests.hud._dlg.visible = false
	Quests.finish_talk(String(opt.quest), "trader", String(opt.dialogue))
	_check("разговор — квест начат, цель: следы Антона", Quests.state(Q) == "ACTIVE" and String(Quests.objective(Q).id) == "backpack", _obj())
	# 2. рейд: только место текущего этапа, Антона нет
	await _raid()
	_check("в рейде — рюкзак есть, чужих этапов нет, Антона нет", _site("anton_backpack") != null and _site("unloading_camp") == null and _site("anton") == null, _sites())
	_site("anton_backpack").request_use()
	await get_tree().process_frame
	_check("улика найдена — надо эвакуироваться", Quests.status(Q) == "WAITING_FOR_EXTRACTION" and int(Profile.quests[Q].obj) == 1, "%s, в профиле цель %d" % [Quests.status(Q), int(Profile.quests[Q].obj)])
	# погиб — не засчитано
	_raid_node().quest_world.on_local_lost()
	_check("погиб — улика не засчитана, повторить", String(Quests.objective(Q).id) == "backpack" and not Quests.in_raid(), _obj())
	await _raid()
	_check("новый рейд — рюкзак снова на месте", _site("anton_backpack") != null, _sites())
	_site("anton_backpack").request_use()
	await _extract()
	_check("эвакуировался — «поговорите с Сергеем», сохранено", Quests.status(Q) == "RETURN_TO_NPC" and _file_obj() == "report1", "в файле: " + _file_obj())
	# повторно та же улика — ничего не меняет
	Quests.event("site", {"site": "anton_backpack"})
	_check("старая улика повторно не срабатывает", String(Quests.objective(Q).id) == "report1", _obj())
	_talk()
	_check("разговор открыл этап 2", int(Quests.qstate(Q).stage) == 1 and String(Quests.objective(Q).id) == "camp", _obj())
	# 3. этап 2: обыск места, записка
	await _raid()
	_check("этап 2: лагерь и записка есть, рюкзака нет", _site("unloading_camp") != null and _site("unloading_note") != null and _site("anton_backpack") == null, _sites())
	_check("записку не прочитать раньше лагеря", not _site("unloading_note").can_use(), "")
	_site("unloading_camp")._done()
	_site("unloading_note").request_use()
	await _extract()
	_talk()
	_check("этап 3 — П-3", String(Quests.stage(Q).id) == "p3", _obj())
	# 4. этап 3: вошёл в зону на П-3 (третий уровень паркинга), записка, тайник
	await _raid()
	var meet := _site("p3_meeting")
	_check("место встречи — на третьем уровне паркинга", meet != null and meet.global_position.y > 5.5, str(meet.global_position if meet else Vector3.ZERO))
	var me := _raid_node().local_player()
	me.global_position = meet.global_position + Vector3(1.0, 0.2, 0.0)
	for i in range(5):
		await get_tree().physics_frame
	_check("вошёл в зону встречи", String(Quests.objective(Q).id) == "p3note", _obj())
	_site("p3_note").request_use()
	_site("p3_ammo").request_use()
	await _extract()
	_talk()
	# 5. этап 4: схрон, записи
	await _raid()
	_site("anton_stash")._done()
	_site("dossier").request_use()
	await _extract()
	_check("улик в журнале — 5", Quests.clues(Q).size() == 5, str(Quests.clues(Q).size()))
	_talk()
	_check("этап 5 — финал", String(Quests.stage(Q).id) == "rescue", _obj())
	# 6. финал: ворота, охрана, Антон
	await _raid()
	_check("Антон и ворота — только сейчас", _site("anton") != null and _site("red_gate") != null, _sites())
	var guards := 0
	for t in range(60):
		guards = 0
		for m in get_tree().get_nodes_in_group("marauders"):
			if String((m as Node).name).begins_with("Guard"):
				guards += 1
		if guards > 0:
			break
		await get_tree().create_timer(0.5).timeout
	_check("у ворот — охрана", guards >= 3, str(guards))
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	me = _raid_node().local_player()
	me.global_position = _site("red_gate").global_position + Vector3(0, 0.3, -2.0)
	for i in range(5):
		await get_tree().physics_frame
	_site("anton").request_use()
	await get_tree().process_frame
	_check("нашёл Антона — надо вынести", String(Quests.objective(Q).type) == "extract_with_npc" and _site("anton").can_carry, _obj())
	_site("anton").request_use()
	await get_tree().process_frame
	_check("несёт Антона — медленно, только пистолет", me.carrying and me.allowed_weapons().size() <= 1 and me._stance_speed() <= Balance.CARRY_SPEED + 0.01, "")
	# погиб с Антоном — финал заново
	_raid_node().quest_world.on_local_lost()
	_check("погиб по дороге — Антон не спасён, этап заново", String(Quests.objective(Q).id) == "gate" and Quests.flag("anton_rescued") == null, _obj())
	await _raid()
	me = _raid_node().local_player()
	me.global_position = _site("red_gate").global_position + Vector3(0, 0.3, -2.0)
	for i in range(5):
		await get_tree().physics_frame
	_site("anton").request_use()
	await get_tree().process_frame
	# без Антона эвакуация не спасает
	var a := _site("anton")
	a.request_use()
	await get_tree().process_frame
	_raid_node().quest_world.put_down()
	me.global_position += Vector3(40, 0, 0)
	await _extract()
	# что нашёл — засчитано (знаешь, где он), а спасён — только если донёс
	_check("ушёл без Антона — не спасён, в следующий раз — донести", Quests.flag("anton_rescued") == null and String(Quests.objective(Q).id) == "carry", _obj())
	await _raid()
	me = _raid_node().local_player()
	me.global_position = _site("red_gate").global_position + Vector3(0, 0.3, -2.0)
	for i in range(5):
		await get_tree().physics_frame
	_check("в новом рейде Антон на месте — поднять", _site("anton") != null and _site("anton").can_carry, _sites())
	_site("anton").request_use()
	await get_tree().process_frame
	await _extract()
	_check("вынес Антона — «поговорите», флаг anton_rescued", Quests.flag("anton_rescued") == true and String(Quests.objective(Q).id) == "finale", _obj())
	# 7. убежище: Антон на койке, финальный разговор
	_free_level()
	var h: Node = load("res://scenes/levels/hideout.tscn").instantiate()
	get_tree().root.add_child(h)
	get_tree().current_scene = h
	_level = h
	for i in range(8):
		await get_tree().physics_frame
	_check("Антон в убежище", h.find_child("Quest_anton_hideout", true, false) != null, "")
	var money0 := Profile.money
	_talk()
	_check("квест выполнен, награда, флаги", Quests.state(Q) == "COMPLETED" and Profile.money == money0 + 40000 and Profile.flags.get("sergey_secret_revealed") == true \
		and "vest_heavy" in Profile.unlocked_stock, "%s, +%d ₽" % [Quests.state(Q), Profile.money - money0])
	# сохранено в файл
	Profile.use_file(TEST_PROFILE, false)
	Profile.ensure()
	_check("после перезапуска — выполнен, флаги на месте", Quests.state(Q) == "COMPLETED" and Profile.flags.get("anton_rescued") == true, "")
	# 8. второй квест — только данными
	Quests._defs["test_hunt"] = {"id": "test_hunt", "title": "ТЕСТ", "giver": "trader", "requires": {"quests": [Q]},
		"stages": [{"id": "s1", "objectives": [
			{"id": "k", "type": "kill_targets", "n": 2, "arch": "heavy", "text": "Убейте двух тяжёлых"},
			{"id": "p", "type": "pickup_item", "item": "gold_chain", "text": "Найдите цепочку"},
			{"id": "x", "type": "extract_with_item", "item": "gold_chain", "text": "Вынесите"}]}],
		"reward": {"money": 1}}
	Quests._order.append("test_hunt")
	Quests.start("test_hunt")
	Quests.event("kill", {"arch": "scout"})
	Quests.event("kill", {"arch": "heavy"})
	Quests.event("kill", {"arch": "heavy"})
	Quests.event("have_item", {"item": "gold_chain"})
	Quests.begin_raid()
	Quests.end_raid(true, {"items": ["gold_chain"], "npcs": []})
	_check("второй квест из данных: убить, найти, вынести", Quests.state("test_hunt") == "COMPLETED", Quests.dev_describe())
	Quests._defs.erase("test_hunt")
	Quests._order.erase("test_hunt")
	print("quest_test: провалено %d" % _fails)
	get_tree().quit(_fails)


# ---------------------------------------------------------------- помощники

func _raid() -> void:
	_free_level()
	await get_tree().process_frame
	_level = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	for i in range(10):
		await get_tree().physics_frame
	var me := _raid_node().local_player()
	me.health.hp = 1e9
	# мародёры бродят и стреляют — в голову было бы насмерть; тест не про бой
	me.health.head_protected = func() -> bool: return true


func _free_level() -> void:
	if _level and is_instance_valid(_level):
		_level.queue_free()
		_level = null


func _raid_node() -> Raid:
	return Raid.current


## Эвакуация своего игрока (как делает Raid по каналу в зоне).
func _extract() -> void:
	var r := _raid_node()
	var me := r.local_player()
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	r._extract(me, ext)
	await get_tree().process_frame
	await get_tree().process_frame


func _talk() -> void:
	var opts := Quests.talk_options("trader")
	if opts.is_empty():
		_check("есть о чём поговорить с Сергеем", false, _obj())
		return
	var o: Dictionary = opts[0]
	Quests.finish_talk(String(o.quest), "trader", String(o.dialogue))


func _site(sid: String) -> QuestSite:
	if _level == null:
		return null
	var n := _level.find_child("Quest_" + sid, true, false)
	return n as QuestSite


func _sites() -> String:
	var out: Array[String] = []
	for n in get_tree().root.find_children("Quest_*", "", true, false):
		out.append(String(n.name))
	return str(out)


func _obj() -> String:
	return "%s этап %d, цель %s (%s)" % [Quests.state(Q), int(Quests.qstate(Q).get("stage", 0)) + 1, String(Quests.objective(Q).get("id", "-")), Quests.status(Q)]


func _file_obj() -> String:
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(TEST_PROFILE))
	var q: Dictionary = (d as Dictionary).get("quests", {}).get(Q, {})
	var st: Array = Quests.def(Q).stages
	var s: Dictionary = st[int(q.get("stage", 0))]
	return String(s.objectives[int(q.get("obj", 0))].id)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
