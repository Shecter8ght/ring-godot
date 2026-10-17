extends Node
## Обучение новой игры (data/quests/tutorial_basics.json) в настоящем убежище: начинается само
## только у новой игры; пакет на ящиках, полка на стеллаже; открыл рюкзак раньше подсказки — шаг
## засчитан сам; взять пакет → положить на полку → открыть терминал → сообщение в «Переписке»;
## задание «после обучения» ждёт его и не мешает старым сохранениям.
## tools/godot.cmd --headless res://tools/tutorial_test.tscn

const Q := "tutorial_basics"
const AFTER := "tst_after_tutorial"

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	Profile.use_file("user://tutorial_test.json", true)
	Profile.flags["new_game"] = true
	Profile.save()
	Quests.dev_add_def(AFTER, {"id": AFTER, "title": "После обучения", "via": "terminal", "giver": "ilya",
		"requires": {"after": [Q]}, "stages": [{"id": "s", "objectives": [{"id": "o", "type": "talk", "npc": "ilya", "dialogue": "x"}]}],
		"dialogues": {"x": [["ilya", "Заказ."]]}})
	await get_tree().process_frame
	_level = (load("res://scenes/levels/hideout.tscn") as PackedScene).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	for i in range(30):
		await get_tree().physics_frame
	var me := get_tree().get_first_node_in_group("players") as Player
	_check("новая игра — обучение началось само и отслеживается", Quests.state(Q) == "ACTIVE" and Quests.tracked() == Q, Quests.state(Q))
	_check("заказ «после обучения» пока закрыт", Quests.state(AFTER) == "LOCKED")
	_check("тест: всплыла инструкция первого шага", not Balance.QUEST_TEST_HINTS or (Quests.hud._test_t > 0.0 and Quests.hud._test_text.text.contains("штабелю ящиков")), Quests.hud._test_text.text)
	var box := _site("tut_box")
	var shelf := _site("tut_shelf")
	_check("пакет лежит на ящиках, полка — на стеллаже",
		box != null and shelf != null and absf(box.global_position.y - 0.68) < 0.08 and absf(shelf.global_position.y - 1.125) < 0.02,
		"%s / %s" % [box.global_position if box else "нет", shelf.global_position if shelf else "нет"])
	# рюкзак открыли раньше подсказки
	Quests.ui_seen("inventory")
	_check("рюкзак до подсказки — цель пока «взять пакет»", String(Quests.objective(Q).id) == "box")
	me.global_position = box.global_position + Vector3(0.7, -box.global_position.y, 0.0)
	await _frames(2)
	box.request_use()
	await _frames(3)
	_check("пакет в рюкзаке и в профиле", me.inventory.count("tutorial_packet") == 1 and _in_backpack("tutorial_packet"))
	_check("«открыть рюкзак» засчитано заранее — сразу полка", String(Quests.objective(Q).id) == "shelf", String(Quests.objective(Q).get("id", "")))
	me.global_position = shelf.global_position + Vector3(0.8, -shelf.global_position.y, 0.0)
	await _frames(2)
	shelf.request_use()
	await _frames(3)
	_check("пакет на полке, из рюкзака ушёл", me.inventory.count("tutorial_packet") == 0 and not _in_backpack("tutorial_packet") and String(Quests.objective(Q).id) == "terminal")
	var placed := shelf.get_node_or_null("Visual/QuestPlaced") as Node3D
	if placed == null:
		for n: Node in shelf.find_children("QuestPlaced", "", true, false):
			placed = n as Node3D
	_check("на полке видно пакет", placed != null and placed.visible)
	var ui := TerminalUI.new()
	add_child(ui)
	ui.open()
	await _frames(3)
	_check("терминал — обучение завершено, сообщение в переписке", Quests.state(Q) == "COMPLETED" and Quests.thread_log(Q).size() == 1 and _has_text(ui, "Знакомство с убежищем завершено"))
	_check("после обучения заказ доступен", Quests.state(AFTER) == "AVAILABLE")
	ui.close_ui()
	_level.queue_free()
	await _frames(3)
	# старое сохранение: обучения нет, заказ не ждёт
	Profile.use_file("user://tutorial_test_old.json", true)
	_check("старое сохранение — обучения нет, заказ доступен", Quests.state(Q) == "LOCKED" and Quests.state(AFTER) == "AVAILABLE")
	print("tutorial_test: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _in_backpack(id: String) -> bool:
	for e: Dictionary in Profile.backpack:
		if String(e.get("id", "")) == id:
			return true
	return false


func _site(sid: String) -> QuestSite:
	return _level.find_child("Quest_" + sid, true, false) as QuestSite if _level else null


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _has_text(root: Node, part: String) -> bool:
	for l: Node in root.find_children("*", "Label", true, false):
		if (l as Label).text.contains(part):
			return true
	return false


func _check(what: String, ok: bool, info: String = "") -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what + ("" if ok or info == "" else "  — " + info))
	if not ok:
		_fails += 1
