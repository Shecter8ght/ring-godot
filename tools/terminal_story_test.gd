extends Node
## Переписка в терминале (Quests, via: "terminal"): заказ без видимого NPC — письмо заказчика,
## «Принять заказ» в окне терминала, история сообщений, отчёт после рейда, оплата этапа один раз,
## собеседник из Contracts (Нина «Перевалка»), задание ждёт несобранную карту (requires.scenes),
## гость получает оплату этапа из снимка хоста один раз.
## tools/godot.cmd --headless res://tools/terminal_story_test.tscn

const Q := "tst_terminal"
const LOCKED := "tst_terminal_nomap"

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://terminal_story_test.json", true)
	Quests.dev_add_def(Q, _def())
	var locked := _def()
	locked["requires"] = {"scenes": ["res://scenes/levels/__нет_такой_карты.tscn"]}
	Quests.dev_add_def(LOCKED, locked)
	_check("карта не собрана — задание закрыто и в переписке его нет",
		Quests.state(LOCKED) == "LOCKED" and not LOCKED in Quests.terminal_threads())
	_check("заказ по переписке доступен в терминале", Quests.state(Q) == "AVAILABLE" and Q in Quests.terminal_threads())
	_check("у Михалыча этот заказ не предлагается", Quests.talk_options("trader").filter(func(o: Dictionary) -> bool: return String(o.quest) == Q).is_empty())
	var act := Quests.terminal_action(Q)
	_check("действие — принять заказ Ильи", String(act.get("kind", "")) == "accept" and String(act.get("npc", "")) == "ilya")
	_check("подпись собеседника из contacts", String(Quests.speaker(Q, "ilya").name) == "Илья")
	_check("собеседник из Contracts — Нина «Перевалка»", String(Quests.speaker(Q, "perevalka").name) == "Перевалка")
	# окно терминала: переписка открывается сама, кнопка «Принять заказ»
	var ui := TerminalUI.new()
	add_child(ui)
	ui.open()
	await get_tree().process_frame
	await get_tree().process_frame
	var accept := _button(ui, "[ ПРИНЯТЬ ЗАКАЗ ]")
	_check("окно открыто на переписке, письмо и кнопка «Принять»", ui.is_open() and accept != null and _has_text(ui, "Был у поста"))
	if accept != null:
		accept.pressed.emit()
	await get_tree().process_frame
	_check("заказ принят из окна, цель — осмотр места", Quests.state(Q) == "ACTIVE" and String(Quests.objective(Q).id) == "parking")
	var lg := Quests.thread_log(Q)
	_check("в истории письмо Ильи и ответ игрока", lg.size() == 2 and String((lg[1] as Array)[0]) == "player")
	_check("пока цель в рейде — отправлять нечего", Quests.terminal_action(Q).is_empty())
	Quests.dev_complete_objective(Q)
	act = Quests.terminal_action(Q)
	_check("после находки — отправить отчёт Илье", String(act.get("kind", "")) == "send" and bool(act.ready))
	var m0 := Profile.money
	await get_tree().process_frame
	await get_tree().process_frame
	var send := _button(ui, "[ ОТПРАВИТЬ: Отправить снимки Илье ]")
	_check("входящего до ответа нет — сразу кнопка (письмо Ильи начинается с игрока)", not _has_text(ui, "Вывоз я не заказывал"))
	_check("кнопка отправки в окне", send != null and not send.disabled)
	if send != null:
		send.pressed.emit()
	await get_tree().process_frame
	_check("оплата этапа пришла", Profile.money == m0 + 15000)
	_check("ответ в истории, следующая цель — Нина", Quests.thread_log(Q).size() == 4 and String(Quests.objective(Q).get("npc", "")) == "perevalka")
	Quests._reward_completed(Profile.quests)
	_check("повторная фиксация не платит второй раз", Profile.money == m0 + 15000)
	var nina := Quests.terminal_action(Q)
	Quests.finish_talk(Q, String(nina.npc), String(nina.dialogue))
	_check("заказ закрыт, расчёт по итогу", Quests.state(Q) == "COMPLETED" and Profile.money == m0 + 15000 + 40000)
	_check("закрытый заказ: действий нет, история осталась", Quests.terminal_action(Q).is_empty() and Quests.thread_log(Q).size() == 6)
	ui.close_ui()
	# гость: оплата этапа из снимка хоста — один раз
	var g0 := Profile.money
	var snap := {"campaign": "host_test", "quests": {Q: {"state": "ACTIVE", "stage": 1, "obj": 0, "paid": ["report"]}}, "flags": {}}
	Quests._commit_guest(snap)
	Quests._commit_guest(snap)
	_check("гость: оплата этапа один раз", Profile.money == g0 + 15000)
	print("terminal_story_test: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _def() -> Dictionary:
	return {
		"id": Q, "title": "Проверка переписки", "via": "terminal", "giver": "ilya", "offer": "принять заказ",
		"summary": "Тестовый заказ по переписке.",
		"contacts": {"ilya": {"nick": "Илья", "name": "Илья Савельев", "color": [0.9, 0.8, 0.5]}},
		"requires": {}, "reward": {"money": 40000},
		"dialogues": {
			"order": [["ilya", "Был у поста по генератору. Проверьте, стоит ли машина."], ["player", "Посмотрю."]],
			"report": [["player", "Машины нет, снимки приложил."], ["ilya", "Вывоз я не заказывал. Оплатил проверку."]],
			"hint": [["perevalka", "В боксе у заправки принимали детали."], ["player", "Понял."]]},
		"sites": {"parking": {"level": "f1_ring", "anchor": {"polar": [-60, 100]}, "prompt": "Осмотреть"}},
		"stages": [
			{"id": "s1", "title": "Пустое место", "objectives": [
				{"id": "order", "type": "talk", "npc": "ilya", "dialogue": "order", "text": "Принять заказ"},
				{"id": "parking", "type": "find_clue", "site": "parking", "text": "Осмотреть стоянку"},
				{"id": "report", "type": "talk", "npc": "ilya", "dialogue": "report", "text": "Отправить снимки Илье",
					"reward": {"money": 15000}}]},
			{"id": "s2", "title": "Наводка", "objectives": [
				{"id": "hint", "type": "talk", "npc": "perevalka", "dialogue": "hint", "text": "Прочитать ответ Нины"}]}]}


func _button(root: Node, text: String) -> Button:
	for b: Node in root.find_children("*", "Button", true, false):
		if (b as Button).text == text:
			return b as Button
	return null


func _has_text(root: Node, part: String) -> bool:
	for l: Node in root.find_children("*", "Label", true, false):
		if (l as Label).text.contains(part):
			return true
	return false


func _check(what: String, ok: bool) -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + what)
	if not ok:
		_fails += 1
