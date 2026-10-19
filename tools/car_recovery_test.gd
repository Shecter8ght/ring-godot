extends Node
## Заказ «Вернуть машину» (data/quests/car_recovery.json) по данным целиком, без карт: сцены мест обеих карт
## есть (ТЦ — scenes/levels/mall, Пригород — zone01) — заказ предлагается (без сцены — закрыт, общий случай
## проверяет terminal_story_test); обычный путь — стоянка, Нина, скупка, «ЮР / 8», дворы, банда, механик,
## аккумулятор, колесо и радиатор (модель радиатора в кладовой и в комплекте), расчёт; ранняя находка на скупке — без стоянки и подсказки;
## обе находки за один рейд — общий отчёт. Оплаты этапов и итог — один раз.
## tools/godot.cmd --headless res://tools/car_recovery_test.tscn

const Q := "car_recovery"

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	Profile.use_file("user://car_recovery_test.json", true)
	var scenes: Array = (Quests.def(Q).get("requires", {}) as Dictionary).get("scenes", [])
	_check("сцены мест обеих карт есть", scenes.size() == 2 and scenes.all(func(p: Variant) -> bool: return ResourceLoader.exists(String(p))), str(scenes))
	_check("заказ предлагается в терминале", Quests.state(Q) == "AVAILABLE" and Q in Quests.terminal_threads(), Quests.state(Q))
	# обычный путь
	_begin()
	var m0 := Profile.money
	_check("тест: инструкция шага «стоянка» всплыла", not Balance.QUEST_TEST_HINTS or Quests.hud._test_text.text.contains("северо-восточным докам"), Quests.hud._test_text.text)
	_check("у каждого шага есть тестовая инструкция", _all_hinted())
	_site("car_mall_parking_wide")
	_site("car_mall_parking_detail")
	_check("стоянка снята — ждём отчёта", _oid() == "report_park")
	_send("report_park")
	_send("hint")
	_check("после подсказки Нины — скупка", _oid() == "lead_plate")
	_site("car_mall_lead_plate")
	_site("car_mall_lead_invoice")
	_send("report_lead")
	_send("decode")
	_check("«ЮР / 8» расшифрован — дворы, в журнале улика", _oid() == "search" and _has_clue("«ЮР / 8»"))
	_check("на этапе дворов — охрана у ангара", not Quests.guards_for("zone01_mall").is_empty())
	Quests.event("site", {"site": "car_belt_search"})
	_check("банда не убита — снимать машину рано", _oid() == "gang")
	Quests.event("cleared", {"site": "car_belt_hangar"})
	_site("car_belt_car_body")
	_site("car_belt_car_marking")
	_send("report_car")
	var b0 := Profile.stash_count("battery")
	_send("kirill_task")
	_check("механик: аккумулятор оплачен — в тайнике", Profile.stash_count("battery") == b0 + 1 and _oid() == "battery")
	_hand("battery")
	for sid in ["car_belt_photo_engine", "car_belt_photo_radiator", "car_belt_photo_wheel", "car_belt_photo_wiring"]:
		_site(sid)
	_send("report_kirill")
	_check("список механика — колесо и радиатор", _oid() == "wheel" and Quests.pending_items(Q) == ["car_wheel", "car_radiator"], str(Quests.pending_items(Q)))
	_check("источники деталей открыты", _site_on("car_belt_parts_wheel", "zone01_mall") and _site_on("car_mall_supply_wheel", "mall_map"))
	# места заказа узлами, как их ставит QuestWorld: модель радиатора в кладовой и в комплекте
	var parts := _site_node("car_belt_parts_radiator")
	var wheel := _site_node("car_belt_parts_wheel")
	var kit := _site_node("car_belt_delivery")
	await get_tree().process_frame
	_check("кладовая: радиатор и колесо лежат, пока их ждут", _shown(parts, "QuestCargo") and _shown(wheel, "QuestCargo"))
	_check("комплект: радиатора ещё нет", not _shown(kit, "QuestPlaced") and not Quests.handed_over(Q, "car_belt_delivery"))
	_hand("wheel")
	_hand("radiator")
	await get_tree().process_frame
	_check("радиатор сдан: в кладовой его нет, в комплекте лежит", not _shown(parts, "QuestCargo") and _shown(kit, "QuestPlaced")
			and Quests.handed_over(Q, "car_belt_delivery"))
	_check("колесо поставлено: в кладовой его нет", not _shown(wheel, "QuestCargo"))
	wheel.queue_free()
	parts.queue_free()
	kit.queue_free()
	_check("комплект собран — заключительный отчёт", _oid() == "final")
	_send("final")
	_check("заказ закрыт, машина вывезена (флаг)", Quests.state(Q) == "COMPLETED" and Quests.flag("car_recovered") == true)
	_check("оплачено: 15 + 20 + 40 + итог 80 тыс.", Profile.money == m0 + 155000, "%d" % (Profile.money - m0))
	Quests._reward_completed(Profile.quests)
	_check("повторная фиксация не платит", Profile.money == m0 + 155000)
	# ранняя находка: в первом рейде сразу скупка
	Profile.use_file("user://car_recovery_test_early.json", true)
	_begin()
	var e0 := Profile.money
	Quests.begin_raid()
	_check("скупка открыта с принятия заказа", _site_on("car_mall_lead_plate", "mall_map") and _site_on("car_mall_lead_invoice", "mall_map"))
	_site("car_mall_lead_plate")
	_site("car_mall_lead_invoice")
	_check("в рейде: стоянка больше не нужна", _oid() == "report_park")
	Quests.on_extracted({"items": [], "npcs": [], "cargo": []})
	Quests.end_raid()
	_check("отчёт — «нашёл на скупке»", String(Quests.terminal_action(Q).dialogue) == "report_lead_first")
	_send_current()
	_check("подсказка и второй рейд пропущены — сразу расшифровка", _oid() == "decode", _oid())
	_check("оплачены оба этапа", Profile.money == e0 + 35000, "%d" % (Profile.money - e0))
	# обе находки за один рейд
	Profile.use_file("user://car_recovery_test_both.json", true)
	_begin()
	for sid in ["car_mall_parking_wide", "car_mall_parking_detail", "car_mall_lead_plate", "car_mall_lead_invoice"]:
		_site(sid)
	_check("обе находки — общий отчёт", String(Quests.terminal_action(Q).dialogue) == "report_both")
	_send_current()
	_check("и снова сразу расшифровка", _oid() == "decode")
	print("car_recovery_test: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Заказ принят (карт нет — начинаем отладкой и отвечаем на письмо Ильи).
func _begin() -> void:
	Quests.dev_start(Q)
	Quests.finish_talk(Q, "ilya", "order")


func _site(sid: String) -> void:
	Quests.request_site(sid)


## Место заказа без карты (как его ставит QuestWorld): модели груза строятся по данным места.
func _site_node(sid: String) -> QuestSite:
	var s := QuestSite.new()
	s.quest_id = Q
	s.site_id = sid
	s.spec = ((Quests.def(Q).get("sites", {}) as Dictionary).get(sid, {}) as Dictionary).duplicate(true)
	add_child(s)
	return s


func _shown(s: QuestSite, node: String) -> bool:
	var n := s.find_child(node, true, false) as Node3D
	return n != null and n.visible


## Хост засчитал сдачу груза (как QuestWorld.take_item у места): без эвакуации.
func _hand(oid: String) -> void:
	Quests._durable_add(Q, oid)
	Quests._auto_all()


func _send(oid: String) -> void:
	if _oid() != oid:
		_check("текущая цель — %s" % oid, false, _oid())
		return
	_send_current()


func _send_current() -> void:
	var act := Quests.terminal_action(Q)
	Quests.finish_talk(Q, String(act.npc), String(act.dialogue))


func _all_hinted() -> bool:
	for st in Quests.def(Q).get("stages", []):
		for o: Dictionary in (st as Dictionary).get("objectives", []):
			if String(o.get("test_hint", "")) == "":
				return false
	return true


func _oid() -> String:
	return String(Quests.objective(Q).get("id", ""))


func _site_on(sid: String, level: String) -> bool:
	for w: Dictionary in Quests.sites_for(level):
		if String(w.site) == sid and bool(w.active):
			return true
	return false


func _has_clue(title: String) -> bool:
	for c: Dictionary in Quests.clues(Q):
		if String(c.get("title", "")) == title:
			return true
	return false


func _check(what: String, ok: bool, info: String = "") -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what + ("" if ok or info == "" else "  — " + info))
	if not ok:
		_fails += 1
