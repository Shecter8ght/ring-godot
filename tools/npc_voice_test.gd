extends Node3D

var checked: int = 0
var failed: int = 0
var heard: Array[String] = []


func check(ok: bool, label: String) -> void:
	checked += 1
	if not ok:
		failed += 1
		push_error(label)


func _ready() -> void:
	var camera := Camera3D.new()
	add_child(camera)
	camera.current = true
	get_tree().current_scene = self
	Audio.event_played.connect(func(id: String, _hook: String, _pos: Vector3) -> void: heard.append(id))
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/npc_voice_map.json"))
	check(raw is Dictionary, "карта реплик читается")
	var lines: Array = (raw as Dictionary).get("lines", [])
	check(lines.size() == 612, "612 активных реплик")
	var missing_events: int = 0
	var missing_files: int = 0
	for value: Variant in lines:
		var row: Dictionary = value as Dictionary
		var id := String(row.event)
		if not Audio._events.has(id) or (Audio._samples.get(id, []) as Array).is_empty():
			missing_events += 1
		for file: Variant in Audio._events.get(id, {}).get("files", []):
			if not FileAccess.file_exists("res://assets/audio/" + String(file)):
				missing_files += 1
	check(missing_events == 0, "у каждой строки есть загруженное назначение")
	check(missing_files == 0, "все назначенные файлы существуют")
	check(Audio.play_voice_line("", "Контакт!", Vector3(1.0, 1.0, 0.0)), "точная реплика мародёра запускается")
	check(not heard.is_empty() and heard.back() == "ai_spot", "мародёр играет «Контакт»")
	check(Audio.play_voice_line("Михалыч", "Тише по стеклу.", Vector3.INF, true), "реплика Михалыча запускается")
	check(not Audio._ui_voice_players.is_empty() and Audio._ui_voice_players.back().bus == Settings.RADIO_VOICE_BUS,
		"голос по рации идёт через радиофильтр")
	check(Audio.play_voice_line("player", "Понял."), "реплика игрока запускается")
	check(not Audio.play_voice_line("player", "Несуществующая фраза"), "неизвестный текст молчит")
	check(not Audio.play_voice_line("Антон", "…Ты от Сергея?"), "отложенный Антон остаётся без назначения")
	var marauder := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	add_child(marauder)
	marauder._show_say("Перезаряжаюсь!")
	check(not heard.is_empty() and heard.back() == "ai_reload", "настоящий Marauder использует точную запись")
	marauder.queue_free()
	var hud := QuestHud.new()
	add_child(hud)
	hud._sub_queue.append(["Михалыч", "Тише по стеклу."])
	hud._next_sub()
	check(not heard.is_empty() and heard.back() == Audio.voice_event_for("Михалыч", "Тише по стеклу."), "субтитры играют голос своей строки")
	var voice_sec := Audio.voice_line_duration("Михалыч", "Тише по стеклу.")
	check(voice_sec > 0.0 and hud._sub_t >= voice_sec + float(Balance.VOICE_UI.queue_gap_sec),
		"следующая реплика ждёт окончания записи")
	hud.start_dialogue([["player", "Понял."]], Callable())
	check(not heard.is_empty() and heard.back() == Audio.voice_event_for("player", "Понял."), "разговор играет голос игрока")
	check(Audio._ui_voice_players.size() == 1, "новая реплика разговора выключает предыдущую")
	hud.clear_subtitles()
	check(Audio._ui_voice_players.is_empty(), "перезапуск эпизода выключает прежний голос")
	hud.queue_free()
	var rivals := RivalRaids.new()
	add_child(rivals)
	rivals._rpc_radio("Рация: В ТЦ зашла ещё одна группа — «Барсук».")
	check(not heard.is_empty() and heard.back() == Audio.voice_event_for("rival_radio", "В ТЦ зашла ещё одна группа — «Барсук»."), "рация находит запись по полному тексту")
	rivals.queue_free()
	print("NPC_VOICE_TEST checked=%d failed=%d" % [checked, failed])
	get_tree().quit(1 if failed else 0)
