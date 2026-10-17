extends Node
## Шаги заказа «Вернуть машину» на общих механиках Quests (без карт заказа — места в убежище):
## точки съёмки (photo), ранняя находка (early) — засчитывается сама и пропускает лишний шаг
## (skip_if_facts), отчёт с вариантом по найденному (variants) платит оба этапа, лишняя подсказка
## пропускается (skip_if_flags); сдача груза (install / deliver) — сразу, без эвакуации: погиб,
## никто не вышел — деталь осталась, шаг засчитан; без детали — «Нужно: …»; груз no_pocket
## в защищённый карман не кладётся. tools/godot.cmd --headless res://tools/quest_steps_test.tscn

const Q := "tst_steps"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	Profile.use_file("user://quest_steps_test.json", true)
	Profile.ensure()
	Quests.dev_add_def(Q, _def())
	await get_tree().process_frame
	_level = (load("res://scenes/levels/hideout.tscn") as PackedScene).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	for i in range(30):
		await get_tree().physics_frame
	var me := get_tree().get_first_node_in_group("players") as Player
	_check("убежище загружено, свой игрок есть", me != null and Quests.world != null)
	var start := Quests.terminal_action(Q)
	Quests.finish_talk(Q, String(start.npc), String(start.dialogue))
	await _frames(4)
	_check("заказ принят: стоянка и раннее место на карте, место сдачи ждёт груз",
		_site("st_park") != null and _site("st_lead") != null and _site("st_car") != null and _site("st_lead").active)
	# рейд 1: сначала скупка (раннее место), стоянку не осматриваем
	Quests.begin_raid()
	_use("st_lead")
	await _frames(2)
	_check("ранняя находка: осмотр стоянки больше не нужен — ждём отчёта",
		String(Quests.objective(Q).id) == "report_park" and "st_lead" in Quests.facts(Q))
	Quests.on_extracted({"items": [], "npcs": [], "cargo": []})
	Quests.end_raid()
	var act := Quests.terminal_action(Q)
	_check("отчёт — вариант «нашёл на скупке»", String(act.get("dialogue", "")) == "report_lead_first")
	var m0 := Profile.money
	Quests.finish_talk(Q, String(act.npc), String(act.dialogue))
	await _frames(2)
	_check("подсказка и второй рейд пропущены — сразу ставить колесо", String(Quests.objective(Q).id) == "wheel", _obj())
	_check("оплачены оба этапа", Profile.money == m0 + 1000 + 2000, "%d" % (Profile.money - m0))
	# сдача: без детали — сказать, что нужно
	Quests.begin_raid()
	me.inventory.items = []
	me.global_position = _site("st_car").global_position + Vector3(0.6, 0.0, 0.0)
	await _frames(2)
	_use("st_car")
	await _frames(2)
	_check("без детали — шаг не засчитан", String(Quests.objective(Q).id) == "wheel" and Quests.durable(Q).is_empty())
	me.inventory.add("battery", 1)
	me.inventory.add("lighter", 1)
	_use("st_car")
	await _frames(2)
	_check("сдано обе детали — дальше разговор", String(Quests.objective(Q).id) == "final" and Quests.durable(Q).size() == 2, _obj())
	_check("детали ушли из рюкзака", me.inventory.count("battery") == 0 and me.inventory.count("lighter") == 0)
	_check("сдача сразу в профиле", (Profile.quests[Q].get("durable", []) as Array).size() == 2)
	# погибли все, никто не вышел — детали остались, шаг засчитан и дома
	Quests.end_raid()
	_check("никто не вышел — детали в машине, цель засчитана", String(Quests.objective(Q).id) == "final" and Quests.durable(Q).size() == 2, _obj())
	Quests.begin_raid()
	_check("новый рейд — сдавать ничего не надо", Quests.pending_handover(Q, "st_car").is_empty())
	Quests.end_raid()
	# груз no_pocket — не в защищённый карман
	var pocket_item := {"id": "car_wheel", "n": 1}
	if ItemDb.exists("car_wheel"):
		_check("колесо в защищённый карман нельзя, в рюкзак можно",
			not ItemDb.grid_accepts("pocket", pocket_item) and ItemDb.grid_accepts("backpack", pocket_item))
	print("quest_steps_test: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _def() -> Dictionary:
	return {
		"id": Q, "title": "Проверка шагов", "via": "terminal", "giver": "ilya", "requires": {},
		"contacts": {"ilya": {"nick": "Илья"}},
		"dialogues": {
			"order": [["ilya", "Проверьте стоянку."], ["player", "Посмотрю."]],
			"report_park": [["player", "Машины нет."], ["ilya", "Плачу за проверку."]],
			"report_lead_first": [["player", "Номер вашей машины на скупке."], ["ilya", "Плачу за проверку и находку."]],
			"hint": [["perevalka", "Загляни в бокс у заправки."], ["player", "Понял."]],
			"report_lead": [["player", "Номер на скупке."], ["ilya", "Плачу за находку."]],
			"final": [["player", "Всё у машины."], ["ilya", "Забираем."]]},
		"sites": {
			"st_park": {"level": "hideout", "anchor": {"pos": [0.0, 0.1, 7.0]}, "prompt": "Снять стоянку", "photo": true},
			"st_lead": {"level": "hideout", "anchor": {"pos": [2.0, 0.1, 7.0]}, "prompt": "Снять номер", "photo": true, "early": true},
			"st_car": {"level": "hideout", "anchor": {"pos": [4.0, 0.1, 7.0]}, "prompt": "Поставить детали", "early": true}},
		"stages": [
			{"id": "s1", "title": "Пустое место", "objectives": [
				{"id": "order", "type": "talk", "npc": "ilya", "dialogue": "order", "text": "Принять заказ"},
				{"id": "park", "type": "photo", "site": "st_park", "text": "Снять стоянку", "skip_if_facts": ["st_lead"]},
				{"id": "report_park", "type": "talk", "npc": "ilya", "dialogue": "report_park", "text": "Отчёт Илье",
					"reward": {"money": 1000},
					"variants": [{"facts": ["st_lead"], "dialogue": "report_lead_first", "set_flags": {"tst_lead_reported": true}}]}]},
			{"id": "s2", "title": "Наводка", "objectives": [
				{"id": "hint", "type": "talk", "npc": "perevalka", "dialogue": "hint", "text": "Ответ Нины",
					"skip_if_flags": {"tst_lead_reported": true}}]},
			{"id": "s3", "title": "Скупка", "objectives": [
				{"id": "lead", "type": "photo", "site": "st_lead", "text": "Снять номер"},
				{"id": "report_lead", "type": "talk", "npc": "ilya", "dialogue": "report_lead", "text": "Отчёт о скупке",
					"reward": {"money": 2000}, "skip_if_flags": {"tst_lead_reported": true}}]},
			{"id": "s4", "title": "Детали", "objectives": [
				{"id": "wheel", "type": "install", "site": "st_car", "item": "battery", "text": "Поставить колесо"},
				{"id": "kit", "type": "deliver", "site": "st_car", "item": "lighter", "text": "Положить радиатор"},
				{"id": "final", "type": "talk", "npc": "ilya", "dialogue": "final", "text": "Финальный отчёт"}]}]}


func _use(sid: String) -> void:
	var s := _site(sid)
	if s == null:
		_check("место %s на карте" % sid, false)
		return
	var me := get_tree().get_first_node_in_group("players") as Player
	me.global_position = s.global_position + Vector3(0.6, 0.0, 0.0)
	s.request_use()


func _site(sid: String) -> QuestSite:
	return _level.find_child("Quest_" + sid, true, false) as QuestSite if _level else null


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _obj() -> String:
	return "%s: этап %d, цель %s" % [Quests.state(Q), int(Quests.qstate(Q).get("stage", 0)) + 1, String(Quests.objective(Q).get("id", "-"))]


func _check(what: String, ok: bool, info: String = "") -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what + ("" if ok or info == "" else "  — " + info))
	if not ok:
		_fails += 1
