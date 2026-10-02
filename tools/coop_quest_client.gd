extends Node
## Общий сюжет группы, клиент (в паре с coop_quest_host): берёт задание у Сергея (засчитывает хост),
## в рейде сам засчитать не может (ни событием, ни издалека), осматривает место рядом — цель
## продвигается у всей группы; хост эвакуировался — результат записан и у клиента: в кампании
## хоста, своя кампания не тронута. godot --headless --path . res://tools/coop_quest_client.tscn

const Q := "missing_anton"

var _fails: int = 0


func _ready() -> void:
	if name == "CoopQuestClientRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "CoopQuestClientRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	Profile.use_file("user://profile_coopq_client.json", true)
	Profile.ensure()
	var own := Profile.own_campaign()
	await get_tree().create_timer(3.0).timeout
	_check("подключение", Net.join("127.0.0.1", "Друг") == "", "")
	await Net.joined
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _until(func() -> bool: return get_tree().get_nodes_in_group("players").size() == 2 and Quests._remote.has("campaign"), 30.0)
	var host_campaign := String(Quests._remote.get("campaign", ""))
	_check("снимок сюжета от хоста — кампания хоста", host_campaign != "" and host_campaign != own, host_campaign)
	var opts := Quests.talk_options("trader")
	_check("у Сергея можно взять задание", not opts.is_empty(), str(opts))
	if not opts.is_empty():
		Quests.finish_talk(String(opts[0].quest), "trader", String(opts[0].dialogue))
	await _until(func() -> bool: return Quests.state(Q) == "ACTIVE", 10.0)
	_check("задание активно и у клиента (снимок от хоста)", Quests.state(Q) == "ACTIVE", Quests.state(Q))
	_check("своя кампания клиента не тронута", not Profile.quests.has(Q), str(Profile.quests.keys()))
	# рейд хоста
	await _until(func() -> bool: return Raid.current != null and Raid.current.local_player() != null, 40.0)
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	var site: QuestSite = null
	for i in range(100):
		site = get_tree().current_scene.find_child("Quest_anton_backpack", true, false) as QuestSite
		if site:
			break
		await get_tree().create_timer(0.2).timeout
	_check("место квеста стоит и у клиента", site != null, "")
	if site == null:
		_finish()
		return
	# сам засчитать нельзя: событие клиента не считается, просьба издалека — отказ
	_check("клиент сам не засчитывает", not Quests.event("site", {"site": "anton_backpack"}), "")
	Quests.request_site("anton_backpack")
	await get_tree().create_timer(1.5).timeout
	_check("издалека — не засчитано", String(Quests.objective(Q).get("id", "")) == "backpack", String(Quests.objective(Q).get("id", "")))
	# подошёл и осмотрел
	me.global_position = site.global_position + Vector3(0.8, 0.3, 0.0)
	await get_tree().create_timer(0.5).timeout
	site.request_use()
	await _until(func() -> bool: return String(Quests.objective(Q).get("id", "")) != "backpack", 10.0)
	_check("осмотр засчитан группе (снимок от хоста)", String(Quests.objective(Q).get("id", "")) != "backpack", String(Quests.objective(Q).get("id", "")))
	# хост эвакуировался — засчитано и у клиента: в кампании хоста
	await _until(func() -> bool: return bool(Quests._remote.get("delivered", false)) or not bool(Quests._remote.get("raid", true)), 30.0)
	await get_tree().create_timer(0.5).timeout
	var store: Dictionary = Profile.guest_campaigns.get(host_campaign, {})
	var obj := int(((store.get("quests", {}) as Dictionary).get(Q, {}) as Dictionary).get("obj", 0))
	_check("хост вынес — у клиента записано в кампании хоста", obj >= 1, str(store))
	_check("…а своя кампания клиента не тронута", not Profile.quests.has(Q), str(Profile.quests.keys()))
	_finish()


func _finish() -> void:
	print("coop_quest_client: провалено %d" % _fails)
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
