extends Node
## Эвакуация группой: встал в открытую зону — общий отсчёт (EXTRACT_GROUP_SEC), напарника ждут;
## из зоны ушли все — сброс; все в зоне (раненый напарник рядом — его выносят) — короткий отсчёт
## точки; отсчёт кончился — кто в зоне, ушёл со всем, живой не в зоне — «не успел»: из мира
## пропал, в хронике — «группа ушла без него», рейд окончен.
## godot --headless res://tools/evac_test.tscn

var _fails: int = 0
var _raid: Raid
var _me: Player
var _mate: Player
var _ext: ExtractionPoint


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_raid = Raid.current
	_me = _raid.local_player()
	_me.health.invulnerable = true
	await get_tree().create_timer(0.3).timeout
	for e in get_tree().get_nodes_in_group("extractions"):
		if _raid.extraction_block_reason(e as ExtractionPoint) == "":
			_ext = e
			break
	_check("есть открытая точка", _ext != null, "")
	_mate = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	_mate.name = "Player_2"
	_mate.peer_id = 2
	level.get_node("Players").add_child(_mate)
	_raid.register(2, "Напарник")
	await get_tree().physics_frame
	var far := _ext.global_position + Vector3(60, 0, 0)
	_put(_mate, far)

	# 1. встал в зону — общий отсчёт, напарника ждут, короткого нет
	await _move_me(_ext.global_position)
	await _wait(1.0)
	var ch: Array = _raid.channel.get(1, [])
	_check("встал в зону — общий отсчёт 3 мин, ждём напарника",
		_raid.evac_left > Balance.EXTRACT_GROUP_SEC - 3.0 and _raid.evac_left < Balance.EXTRACT_GROUP_SEC and _raid.evac_wait == [2] and ch.size() == 2 and float(ch[1]) == 0.0,
		"осталось %.1f, ждём %s, %s" % [_raid.evac_left, str(_raid.evac_wait), str(ch)])
	_check("в зоне — подсказка «ждём»", _raid._progress_label.visible and _raid._progress_label.text.contains("ждём"), _raid._progress_label.text)
	# у напарника (не в зоне) — «группа у выхода»; проверяем подсказку за него: он локальный на миг
	# 2. вышел — сброс
	await _move_me(far + Vector3(0, 0, 30))
	await _wait(0.4)
	_check("из зоны ушли все — сброс", _raid.evac_left < 0.0 and _raid.channel.is_empty() and _raid.evac_wait.is_empty(), "%.1f" % _raid.evac_left)
	# 3. все в зоне (раненый напарник лежит рядом) — короткий отсчёт, выносят обоих
	_mate.health.take_damage(150.0, Vector3.ZERO, "body")
	_put(_mate, _ext.global_position + Vector3(0.8, 0, 0))
	await _move_me(_ext.global_position)
	await _wait(1.0)
	_check("все в зоне — короткий отсчёт точки", _raid.evac_wait.is_empty() and float((_raid.channel.get(1, [0, 0.0]) as Array)[1]) > 0.5, str(_raid.channel))
	await _wait(_ext.channel_s + 0.5)
	_check("ушли оба, раненого вынесли", _raid.is_extracted(1) and String(_raid.extracted.get(2, "")).ends_with(Raid.CARRIED_SUFFIX), str(_raid.extracted))
	await _restore()

	# 4. напарник не пришёл — отсчёт кончился: я ушёл, он не успел
	_mate.health.revive(1.0)
	_put(_mate, far)
	await _move_me(_ext.global_position)
	await _wait(0.5)
	_raid.evac_left = 1.0
	await _wait(1.5)
	_check("отсчёт кончился — кто в зоне, ушёл", _raid.is_extracted(1), str(_raid.extracted))
	_check("живой не в зоне — не успел, пропал из мира", _raid.stranded.has(2) and not _raid.is_extracted(2) and not _mate.is_in_group("players"), str(_raid.stranded))
	_check("рейд окончен", _raid.over, "")
	await _restore()

	# 5. не успел я: хроника — «группа ушла без него», вердикт — из пула «не успел»
	_mate.health.revive(1.0)
	_put(_mate, _ext.global_position)
	await _move_me(far)
	await _wait(0.5)
	_check("я не в зоне — «группа у выхода, успей»", _raid._progress_label.visible and _raid._progress_label.text.contains("ГРУППА У ВЫХОДА"), _raid._progress_label.text)
	_raid.evac_left = 1.0
	await _wait(1.8)
	_check("я не успел — ушёл из мира, рейд окончен", _raid.stranded.has(1) and not _me.is_in_group("players") and _raid.is_extracted(2) and _raid.over, str(_raid.stranded))
	var ch2 := _raid.chronicle
	_check("хроника: исход «не успел»", ch2 != null and _raid.analytics.outcome == "stranded" and _in_pool(ch2.verdict, RaidStory.data().verdicts.stranded), ch2.verdict if ch2 else "")
	if ch2:
		print("    ", "\n\n".join(ch2.paragraphs).replace("\n", "\n    "), "\n    ", ch2.verdict)
		_check("итог: не успел, через какую точку ушла группа", String(ch2.stats[-1][1]).contains("не успел") and String(ch2.stats[-1][1]).contains(_ext.display_name), String(ch2.stats[-1][1]))
	_check("экран итога: не успел", _raid._story_panel.visible and _raid._story_footer.text.contains("НЕ УСПЕЛ"), _raid._story_footer.text)
	print("evac_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _put(pl: Player, p: Vector3) -> void:
	pl.global_position = p + Vector3(0, 0.1, 0)


func _move_me(p: Vector3) -> void:
	_me.global_position = p + Vector3(0, 0.3, 0)
	_me.velocity = Vector3.ZERO
	await get_tree().physics_frame
	await get_tree().physics_frame


## Вернуть рейд как был: никто не ушёл, оба в мире, хроника заново.
func _restore() -> void:
	_raid.extracted = {}
	_raid.stranded = {}
	_raid.loot_value = {}
	_raid.drags = {}
	_raid.over = false
	for pl in [_me, _mate]:
		pl.add_to_group("players")
		pl.visible = true
		pl.set_physics_process(true)
		pl.collision_layer = 2
		pl.collision_mask = 13
	_raid.analytics.queue_free()
	var a := RaidAnalytics.new()
	a.name = "Analytics_%d" % Time.get_ticks_msec()
	_raid.add_child(a)
	_raid.analytics = a
	_raid.chronicle = null
	_raid._chronicle_wait = 0.0
	await get_tree().physics_frame


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _in_pool(line: String, pool: Array) -> bool:
	for p in pool:
		var re := RegEx.new()
		var pat := ""
		var i := 0
		var s := String(p)
		while i < s.length():
			var c := s.substr(i, 1)
			if c == "{":
				pat += ".+?"
				i = s.find("}", i) + 1
				continue
			pat += ("\\" + c) if c in ".^$*+?()[]|\\" else c
			i += 1
		re.compile("^" + pat + "$")
		if re.search(line) != null:
			return true
	return false


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
