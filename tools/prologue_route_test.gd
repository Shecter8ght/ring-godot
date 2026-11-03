extends Node
## Эвакуация с пропущенной зоной, восстановление сохранения и настоящий запуск выбранной карты.

const Q: String = "prologue"
var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	# Стенд остаётся в дереве при переходе на выбранную карту.
	get_tree().current_scene = null
	# Отдельный прогон копии настоящего сохранения: исходный файл игры не открывается на запись.
	var copy_path: String = OS.get_environment("PROLOGUE_REPAIR_COPY")
	if copy_path != "":
		var before: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(copy_path)) as Dictionary
		Profile.use_file(copy_path, false)
		_check("реальное сохранение: пролог закрыт, Продолжить ведёт в убежище", Quests.state(Q) == "COMPLETED"
			and not Saves.prologue_pending(copy_path) and Profile.flags.get("prologue_done") == true)
		var after: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(copy_path)) as Dictionary
		_check("реальное сохранение: вещи и заказ машины сохранены", after.get("stash", []) == before.get("stash", [])
			and after.get("backpack", []) == before.get("backpack", []) and after.get("equipment", {}) == before.get("equipment", {})
			and (after.get("quests", {}) as Dictionary).get("car_recovery", {}) == (before.get("quests", {}) as Dictionary).get("car_recovery", {}))
		print("prologue_route_test: провалено %d" % _fails)
		get_tree().quit(_fails)
		return
	Profile.use_file("user://prologue_route_test.json", true)
	# Сравниваем обычное загруженное сохранение: стартовый набор тоже проходит старые миграции вещей.
	Profile.use_file(Profile.path, false)
	var stash_before: String = JSON.stringify(Profile.stash)
	Profile.quests = {Q: _unfinished(), "car_recovery": {"state": "ACTIVE", "stage": 0, "obj": 1}}
	Profile.flags = {"new_game": true, "prologue": true, "packet_delivered": true, "bp_slot": true}
	Profile.save()
	_check("Продолжить не отправляет прошедшего пролог обратно", not Saves.prologue_pending(Profile.path))
	Profile.use_file(Profile.path, false)
	_check("зависший пролог восстановлен и сохранён", Quests.state(Q) == "COMPLETED" and Profile.flags.get("prologue_done") == true
		and not Saves.prologue_pending(Profile.path))
	_check("вещи и активный заказ машины сохранены", JSON.stringify(Profile.stash) == stash_before
		and Quests.state("car_recovery") == "ACTIVE" and int(Profile.quests.car_recovery.obj) == 1)
	var home: Node = (load("res://src/hideout/hideout_level.gd") as Script).new() as Node
	_check("убежище больше не подменяет маршрут прологом", not bool(home.call("_prologue_pending")))
	Profile.quests = {Q: _unfinished()}
	Profile.flags = {"new_game": true, "prologue": true, "bp_slot": true}
	Profile.save()
	_check("незавершённый первый рейд по-прежнему запускает пролог", Saves.prologue_pending(Profile.path)
		and bool(home.call("_prologue_pending")))
	var world: QuestWorld = QuestWorld.new()
	world.level = "prospekt"
	Quests.world = world
	Quests.begin_raid()
	Quests.end_raid()
	_check("смерть без выхода не завершает пролог", Quests.state(Q) == "ACTIVE")
	world.level = "mall_map"
	Quests.begin_raid()
	Quests.on_extracted({"items": [], "npcs": []})
	Quests.end_raid()
	_check("выход с другой карты не закрывает пролог", Quests.state(Q) == "ACTIVE")
	world.level = "prospekt"
	Quests.begin_raid()
	Quests.dev_add_def("route_guard", {"title": "Проверка обычного заказа", "stages": [
		{"objectives": [{"id": "inspect", "type": "inspect", "site": "route_guard_site"}]}]})
	Quests.dev_start("route_guard")
	Quests.on_extracted({"items": [], "npcs": []})
	Quests.end_raid()
	_check("успешный выход закрывает пролог без промежуточной зоны и без пакета", Quests.state(Q) == "COMPLETED"
		and Quests.flag("prologue_done") == true and Quests.flag("packet_delivered") != true)
	_check("обычный заказ не закрывается одной эвакуацией", Quests.state("route_guard") == "ACTIVE")
	_check("обучение в убежище открывается после выхода", Quests.state("tutorial_basics") == "AVAILABLE")
	_check("после выхода новый рейд не подменяется прологом", not bool(home.call("_prologue_pending")))
	Quests.world = null
	world.free()
	_check("выбрана территория ТЦ", Floors.select("mall") and Floors.scene(Profile.floor) == "res://scenes/levels/mall_map.tscn")
	var reached: Array[String] = []
	Net.scene_transition_finished.connect(func(path: String) -> void: reached.append(path))
	var launched: bool = bool(home.call("_launch_raid"))
	home.free()
	var deadline: int = Time.get_ticks_msec() + 180000
	while reached.is_empty() and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	_check("выход из убежища действительно загрузил территорию ТЦ", launched and reached.has("res://scenes/levels/mall_map.tscn")
		and get_tree().current_scene != null and get_tree().current_scene.scene_file_path == "res://scenes/levels/mall_map.tscn"
		and Prologue.current == null)
	print("prologue_route_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _unfinished() -> Dictionary:
	return {"state": "ACTIVE", "stage": 2, "obj": 1, "count": 0, "clues": []}


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("%s %s" % ["OK" if ok else "FAIL", label])
