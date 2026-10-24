extends Node
## Снимки сюжета «Не вернулся»: разговор в убежище, места этапов в рейде (рюкзак на парковке,
## лагерь у разгрузки, встреча на П-3, ворота и Антон), несёшь Антона, Антон в убежище.
## godot --path . res://tools/quest_shots.tscn → docs/screens/quest_*.png (тестовый профиль)

const Q := "missing_anton"

var _level: Node


func _ready() -> void:
	Profile.use_file("user://profile_quest_shots.json", true)
	Profile.ensure()
	await get_tree().process_frame
	# убежище: разговор с Сергеем
	await _load("res://scenes/levels/hideout.tscn")
	var opts := Quests.talk_options("trader")
	var o: Dictionary = opts[0]
	Quests.hud.start_dialogue(Quests.dialogue(Q, String(o.dialogue)), func() -> void: Quests.finish_talk(Q, "trader", String(o.dialogue)))
	await _frames(20)
	_save("quest_hideout_talk")
	Quests.hud._advance()
	for i in range(10):
		if Quests.hud._dlg.visible:
			Quests.hud._advance()
	await _frames(10)
	_save("quest_tracker_hideout")
	# места этапов в рейде — камера сверху у места
	for st in [[1, "anton_backpack", "quest_backpack"], [2, "unloading_camp", "quest_unloading"], [3, "p3_meeting", "quest_p3"], [5, "red_gate", "quest_red_gate"]]:
		Quests.dev_stage(Q, int(st[0]))
		await _load("res://scenes/levels/mall_map.tscn")
		for m in get_tree().get_nodes_in_group("marauders"):
			(m as Node).queue_free()
		var s := _level.find_child("Quest_" + String(st[1]), true, false) as Node3D
		var me := Raid.current.local_player()
		me.health.hp = 1e9
		if s:
			me.global_position = s.global_position + Vector3(2.5, 0.2, 2.5)
		await _frames(40)
		_save(String(st[2]))
	# несёт Антона
	var a := _level.find_child("Quest_anton", true, false) as QuestSite
	if a:
		var me := Raid.current.local_player()
		me.global_position = a.global_position + Vector3(1.0, 0.2, 0.0)
		await _frames(5)
		a.request_use()
		await _frames(5)
		a.request_use()
		me.global_position += Vector3(3.0, 0.0, 3.0)
		await _frames(30)
		_save("quest_carry")
	print("quest_shots: готово")
	get_tree().quit(0)


func _load(path: String) -> void:
	if _level:
		_level.queue_free()
		await get_tree().process_frame
	_level = load(path).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	await _frames(30)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("quest_shots: ", n)
