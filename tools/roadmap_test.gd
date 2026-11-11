extends Node
## Дорожная карта до демоверсии (RoadmapData, RoadmapWindow, data/roadmap.json): файл списка читается
## без ошибок (id не повторяются, статусы и этапы известны, «сначала» ссылается на существующие пункты),
## счёт «сделано / всего» сходится, отметка сохраняется между открытиями и не ломает ручные правки
## файла, в сборке отметки ложатся отдельно; окно: счёт, щелчок по отметке, фильтр «только не
## сделанное», порядок работ по этапам, «отложено», Esc. Настоящий файл проекта проверка не меняет —
## работает на копии в user://.
## tools/godot.cmd --headless res://tools/roadmap_test.tscn
## С окном (--windowed --resolution 1600x900) — снимки docs/screens/roadmap_*.png

const COPY: String = "user://roadmap_test.json"
const MARKS: String = "user://roadmap_test_marks.json"

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var before: String = FileAccess.get_md5(RoadmapData.PATH)

	# --- настоящий список
	var real: RoadmapData = RoadmapData.new(RoadmapData.PATH, MARKS + ".none")
	_check("файл списка читается без ошибок", real.problems.is_empty(), " | ".join(PackedStringArray(real.problems)))
	var total: Vector2i = real.count()
	_check("в списке есть пункты", total.y > 0, "%d из %d" % [total.x, total.y])
	_check("есть разделы и этапы", real.sections().size() >= 3 and real.stages().size() >= 2,
		"разделов %d, этапов %d" % [real.sections().size(), real.stages().size()])
	var by_sections: int = 0
	for sec: Dictionary in real.sections():
		by_sections += real.count(String(sec.get("id", ""))).y
	var by_stages: int = 0
	for st: Variant in real.stages():
		by_stages += real.count(String((st as Dictionary).get("id", ""))).y
	_check("счёт по разделам и по этапам сходится с общим", by_sections == total.y and by_stages == total.y,
		"разделы %d, этапы %d, всего %d" % [by_sections, by_stages, total.y])
	var empty: int = 0
	for it: Dictionary in real.items():
		if String(it.get("title", "")) == "" or String(it.get("done_when", "")) == "":
			empty += 1
	_check("у каждого пункта есть название и «готово, когда»", empty == 0, "пустых %d" % empty)
	_check("пункт не ждёт сам себя и готовый не ждёт неготового", _order_ok(real))

	# --- отметка сохраняется в файл списка (копия)
	_copy(RoadmapData.PATH, COPY)
	DirAccess.remove_absolute(ProjectSettings.globalize_path(MARKS))
	var data: RoadmapData = RoadmapData.new(COPY)
	var first: Dictionary = _first_with(data, "todo")
	var id: String = String(first.get("id", ""))
	_check("есть несделанный пункт для пробы", id != "")
	var done_before: int = data.count().x
	_check("отметка «готово» ставится", data.set_status(id, "done") and data.status(id) == "done")
	var again: RoadmapData = RoadmapData.new(COPY)
	_check("после нового открытия отметка на месте", again.status(id) == "done" and again.count().x == done_before + 1,
		"сделано %d → %d" % [done_before, again.count().x])
	var text: String = FileAccess.get_file_as_string(COPY)
	_check("порядок полей в файле не перемешан", text.find("\"title\"") < text.find("\"sections\"")
		and text.find("\"id\"", text.find("\"items\"")) < text.find("\"done_when\"", text.find("\"items\"")))
	_check("числа в файле не появились (1 → 1.0)", not text.contains(".0,") and not text.contains(".0\n"))
	# файл поправили руками, пока «игра открыта» — отметка из игры правку не затирает
	var edited: Variant = JSON.parse_string(text)
	(edited as Dictionary)["demo"] = "ПРАВКА РУКАМИ"
	var f: FileAccess = FileAccess.open(COPY, FileAccess.WRITE)
	f.store_string(JSON.stringify(edited, " ", false))
	f.close()
	again.set_status(id, "doing")
	var third: RoadmapData = RoadmapData.new(COPY)
	_check("ручная правка файла не потеряна при отметке из игры", third.summary() == "ПРАВКА РУКАМИ" and third.status(id) == "doing")
	_check("статусы идут по кругу", RoadmapData.next_status("todo") == "doing" and RoadmapData.next_status("doing") == "done"
		and RoadmapData.next_status("done") == "todo")
	_check("неизвестный статус и неизвестный пункт не принимаются", not third.set_status(id, "maybe") and not third.set_status("нет_такого", "done"))

	# --- сборка для друзей: отметки отдельно, файл списка не трогается
	_copy(RoadmapData.PATH, COPY)
	var sum: String = FileAccess.get_md5(COPY)
	var sealed: RoadmapData = RoadmapData.new(COPY, MARKS)
	sealed.set_status(id, "done")
	var sealed_again: RoadmapData = RoadmapData.new(COPY, MARKS)
	_check("отметки отдельно: файл списка тот же, отметка есть", FileAccess.get_md5(COPY) == sum and sealed_again.status(id) == "done")

	# --- испорченный файл не роняет игру
	f = FileAccess.open(COPY, FileAccess.WRITE)
	f.store_string("{ это не список")
	f.close()
	var broken: RoadmapData = RoadmapData.new(COPY)
	_check("испорченный файл: сообщение вместо падения", not broken.problems.is_empty() and broken.count() == Vector2i.ZERO)

	# --- окно
	_copy(RoadmapData.PATH, COPY)
	data = RoadmapData.new(COPY)
	var w: RoadmapWindow = RoadmapWindow.open_in(get_tree(), data)
	await _frames(3)
	_check("окно открыто и держит клавиши у себя", w.is_open() and w.is_in_group("esc_windows"))
	if DisplayServer.get_name() != "headless":
		await _shot("roadmap_sections")
		w.set_mode("stages")
		w.set_group("s1")
		await _shot("roadmap_stage1")
		w.set_mode("sections")
	_check("второе открытие возвращает то же окно", RoadmapWindow.open_in(get_tree()) == w)
	var all: Vector2i = data.count()
	var total_label: Label = w.find_child("Total", true, false) as Label
	_check("в шапке общий счёт", total_label.text == "Сделано %d из %d · осталось %d" % [all.x, all.y, all.y - all.x], total_label.text)
	_check("слева — разделы со счётом", w.find_child("Group_all", true, false) != null
		and _count_nodes(w, "Group_") == real.sections().size() + 1 + (1 if not real.later().is_empty() else 0),
		"кнопок %d" % _count_nodes(w, "Group_"))
	_check("в списке все пункты", _count_nodes(w, "Item_") == all.y, "%d" % _count_nodes(w, "Item_"))
	id = String(_first_with(data, "todo").get("id", ""))
	var mark: Button = w.find_child("Item_" + id.replace(".", "_"), true, false).find_child("Mark", true, false) as Button
	_check("у пункта отметка «не начато»", mark.text == "не начато", mark.text)
	mark.pressed.emit()
	await _frames(2)
	_check("щелчок: «в работе», счёт тот же", data.status(id) == "doing" and data.count().x == all.x)
	w.cycle(id)
	await _frames(2)
	_check("ещё щелчок: «готово», счёт вырос и в шапке", data.status(id) == "done"
		and total_label.text == "Сделано %d из %d · осталось %d" % [all.x + 1, all.y, all.y - all.x - 1], total_label.text)
	_check("отметка из окна — в файле", RoadmapData.new(COPY).status(id) == "done")
	w.cycle(id, -1)
	await _frames(2)
	_check("правый щелчок — назад: «в работе»", data.status(id) == "doing")
	w.cycle(id)
	var only: CheckButton = w.find_child("OnlyOpen", true, false) as CheckButton
	only.button_pressed = true
	await _frames(2)
	_check("«только не сделанное» прячет готовые", _count_nodes(w, "Item_") == all.y - data.count().x
		and w.find_child("Item_" + id.replace(".", "_"), true, false) == null, "%d" % _count_nodes(w, "Item_"))
	only.button_pressed = false
	w.set_mode("stages")
	await _frames(2)
	_check("по порядку работ: слева этапы, пункты те же", _count_nodes(w, "Group_") == real.stages().size() + 1 + (1 if not real.later().is_empty() else 0)
		and _count_nodes(w, "Item_") == all.y, "кнопок %d, пунктов %d" % [_count_nodes(w, "Group_"), _count_nodes(w, "Item_")])
	var stage_id: String = String((real.stages()[0] as Dictionary).get("id", ""))
	w.set_group(stage_id)
	await _frames(2)
	_check("выбран этап — только его пункты", _count_nodes(w, "Item_") == data.count(stage_id).y, "%d" % _count_nodes(w, "Item_"))
	if not real.later().is_empty():
		w.set_group("later")
		await _frames(2)
		_check("«отложено» — без отметок", _count_nodes(w, "Item_") == 0 and w.find_child("Mark", true, false) == null)
	var esc: InputEventAction = InputEventAction.new()
	esc.action = "pause"
	esc.pressed = true
	Input.parse_input_event(esc)
	await _frames(4)
	_check("Esc закрывает окно, меню паузы не открылось", not is_instance_valid(w) and not PauseMenu.shown)

	# --- вход из меню по Esc
	Pause.open_menu()
	Pause.open_roadmap()
	await _frames(3)
	var from_menu: Array[Node] = get_tree().get_nodes_in_group("roadmap_window")
	_check("кнопка «Дорожная карта» в меню открывает окно", from_menu.size() == 1)
	for n: Node in from_menu:
		(n as RoadmapWindow).close_ui()
	await _frames(3)
	_check("закрыли окно — меню паузы осталось", PauseMenu.shown)
	Pause.close_menu()

	_check("настоящий файл проекта проверка не изменила", FileAccess.get_md5(RoadmapData.PATH) == before)
	for p: String in [COPY, MARKS]:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(p))
	print("roadmap_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Готовый пункт не должен ждать неготовый, и никто не ждёт сам себя.
func _order_ok(data: RoadmapData) -> bool:
	for it: Dictionary in data.items():
		var id: String = String(it.get("id", ""))
		if id in (it.get("needs", []) as Array):
			print("   ждёт сам себя: ", id)
			return false
		if data.status(id) == "done" and not data.blockers(id).is_empty():
			print("   готов раньше того, чего ждёт: ", id)
			return false
	return true


func _first_with(data: RoadmapData, st: String) -> Dictionary:
	for it: Dictionary in data.items():
		if data.status(String(it.get("id", ""))) == st:
			return it
	return {}


## С окном — снимок в docs/screens (как выглядит окно).
func _shot(shot_name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % shot_name))


func _count_nodes(root: Node, prefix: String) -> int:
	var n: int = 0
	for c: Node in root.find_children(prefix + "*", "", true, false):
		if not c.is_queued_for_deletion():
			n += 1
	return n


func _copy(from: String, to: String) -> void:
	var f: FileAccess = FileAccess.open(to, FileAccess.WRITE)
	f.store_string(FileAccess.get_file_as_string(from))
	f.close()


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
