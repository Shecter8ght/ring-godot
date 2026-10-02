extends Node
## Общий сюжет группы, хост (в паре с coop_quest_client): друг берёт задание у Сергея — у хоста
## оно активно; в рейде друг осматривает место — цель засчитана группе; хост эвакуируется —
## сделанное сохранено в профиле хоста (и у друга — в кампании хоста).
## godot --headless --path . res://tools/coop_quest_host.tscn  (клиент — через 3 с)

const Q := "missing_anton"

var _fails: int = 0


func _ready() -> void:
	if name == "CoopQuestHostRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "CoopQuestHostRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	Profile.use_file("user://profile_coopq_host.json", true)
	Profile.ensure()
	_check("сервер поднят", Net.host("Хост") == "", "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2, 40.0)
	# друг берёт задание у Сергея — разговор у него, засчитывает хост
	await _until(func() -> bool: return Quests.state(Q) == "ACTIVE", 20.0)
	_check("друг взял задание — у хоста оно активно (общее)", Quests.state(Q) == "ACTIVE", Quests.state(Q))
	_check("начало задания записано в профиль хоста", Profile.quests.has(Q), str(Profile.quests.keys()))
	await get_tree().create_timer(1.0).timeout
	# сколько целей пройдено до рейда (разговор с Сергеем — уже первая)
	var obj0 := int((Profile.quests.get(Q, {}) as Dictionary).get("obj", 0))
	Net.start_level.rpc(Floors.scene(Profile.floor), Profile.next_conditions)
	await _until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and get_tree().get_nodes_in_group("players").size() == 2, 40.0)
	Raid.current.local_player().health.hp = 1e9
	_check("рейд: место квеста стоит и у хоста", get_tree().current_scene.find_child("Quest_anton_backpack", true, false) != null, "")
	# друг осматривает рюкзак — ждём, пока цель продвинется
	await _until(func() -> bool: return String(Quests.objective(Q).get("id", "")) != "backpack", 60.0)
	_check("осмотр друга засчитан группе — у хоста цель дальше", String(Quests.objective(Q).get("id", "")) != "backpack", String(Quests.objective(Q).get("id", "")))
	_check("до эвакуации в профиль хоста не записано", int((Profile.quests.get(Q, {}) as Dictionary).get("obj", 0)) == obj0, str(Profile.quests.get(Q)))
	# хост уходит — вынос засчитан всем
	var me := Raid.current.local_player()
	var ext := get_tree().get_nodes_in_group("extractions")[0] as ExtractionPoint
	Raid.current._extract(me, ext)
	await get_tree().create_timer(0.5).timeout
	_check("хост эвакуировался — сделанное в профиле хоста", int((Profile.quests.get(Q, {}) as Dictionary).get("obj", 0)) > obj0, str(Profile.quests.get(Q)))
	# клиенту дать проверить свою копию
	await get_tree().create_timer(10.0).timeout
	print("coop_quest_host: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _until(cond: Callable, sec: float) -> void:
	var t := 0.0
	while not bool(cond.call()) and t < sec:
		await get_tree().create_timer(0.2).timeout
		t += 0.2


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
