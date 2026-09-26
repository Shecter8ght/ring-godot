extends Node
## Хроника рейда: рассказ и вердикт из фактов. Своя граната → вердикт про гранату; снова так же —
## про повтор; третий дорогой комплект подряд — про серию; с пистолетом много убийств и вышел —
## «не ствол делает рейдера»; один рейд пять раз — стиль не повторяется подряд, тексты разные;
## 400 случайных рейдов — 2–5 абзацев, 3–6 событий, все {переменные} подставлены. В уровне: убил
## мародёра, стрелял, ранили, погиб от снайпера — факты дошли, на экране итога хроника и вердикт
## (с окном — снимок docs/screens/story_summary.png).
## godot --headless res://tools/story_test.tscn

var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://story_test.json", true)
	await get_tree().process_frame
	_check_pools()
	_check_self_grenade()
	_check_pistol_hero()
	_check_variety()
	_check_fuzz()
	await _check_in_level()
	print("story_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Рейд из фактов: базовый — 10 минут, автомат, комплект на 90 тысяч; поверх — overrides.
func _raid(outcome: String, overrides: Dictionary = {}) -> RaidAnalytics:
	var a := RaidAnalytics.new()
	a.started_ms = 0
	a.ended_ms = 600000
	a.loadout = true
	a.start_weapons = ["wpn_ar_03"]
	a.start_kit_value = 90000
	a.outcome = outcome
	a.extract_name = "Грузовой шлюз" if outcome == "extract" else ""
	a.end_value = 120000 if outcome == "extract" else 0
	if outcome == "death":
		a.death = {"cause": "ai", "arch": "gunner", "faction": "marauder", "weapon": "wpn_ar_03"}
		a.death_extract_dist = 140.0
	for k in overrides:
		var v: Variant = overrides[k]
		# типизированные массивы (Array[String]) через set() из простого массива не принимаются
		if a.get(k) is Array and v is Array:
			(a.get(k) as Array).assign(v)
		else:
			a.set(k, v)
	return a


func _rng(seed_v: int) -> RandomNumberGenerator:
	var r := RandomNumberGenerator.new()
	r.seed = seed_v
	return r


func _text(st: RaidStory) -> String:
	return "\n\n".join(st.paragraphs) + "\n" + st.verdict


## Все фразы пулов — строки, вердиктов на каждый случай хватает.
func _check_pools() -> void:
	var d := RaidStory.data()
	_check("data/raid_story.json читается", not d.is_empty() and d.has("events") and d.has("verdicts"), "")
	var small: Array = []
	for k in d.verdicts:
		var p: Variant = d.verdicts[k]
		if p is Array and (p as Array).size() < 2:
			small.append(k)
	_check("вердиктов — хотя бы по две фразы", small.is_empty(), str(small))


func _check_self_grenade() -> void:
	Profile.raid_history = []
	var a := _raid("death", {"ended_ms": 70000, "start_kit_value": 200000,
		"death": {"cause": "self_grenade", "attacker": 1}, "kills": []})
	var st := RaidStory.make(a, true, _rng(1))
	var pool: Array = RaidStory.data().verdicts.self_grenade
	var fast_exp: Array = RaidStory.data().verdicts.fast_expensive
	_check("своя граната — вердикт про гранату", _in_pool(st.verdict, pool), st.verdict)
	_check("рассказ кончается гранатой", _in_pool(_last_sentences(st), (RaidStory.data().endings.death.self_grenade as Dictionary).values().reduce(func(acc: Array, x: Array) -> Array: return acc + x, [])), st.paragraphs[-1])
	print("    ", _text(st).replace("\n", "\n    "))
	# снова своя граната — повтор важнее
	var b := _raid("death", {"ended_ms": 300000, "death": {"cause": "self_grenade", "attacker": 1}})
	var st2 := RaidStory.make(b, true, _rng(2))
	_check("снова своя граната — вердикт про повтор", _in_pool(st2.verdict, RaidStory.data().verdicts.repeated.self_grenade), st2.verdict)
	# дорогой комплект третий раз подряд
	Profile.raid_history = []
	for i in range(2):
		RaidStory.make(_raid("death", {"start_kit_value": 180000, "death": {"cause": "bleed"} if i == 0 else {"cause": "grenade"}}), true, _rng(10 + i))
	var c := _raid("death", {"start_kit_value": 210000, "death": {"cause": "ai", "arch": "scout", "faction": "marauder", "weapon": "wpn_hg_03"}})
	var st3 := RaidStory.make(c, true, _rng(3))
	_check("третий дорогой комплект подряд — вердикт про серию", _in_pool(st3.verdict, RaidStory.data().verdicts.loss_streak), st3.verdict)
	_check("история: три рейда, новее первым", Profile.raid_history.size() == 3 and int(Profile.raid_history[0].kit) == 210000, str(Profile.raid_history.size()))


func _check_pistol_hero() -> void:
	Profile.raid_history = []
	var kills: Array = []
	for i in range(5):
		kills.append({"t": 60.0 + i * 5.0, "arch": "gunner", "faction": "marauder", "weapon": "wpn_hg_03", "grenade": false, "leader": false})
	var a := _raid("extract", {"start_weapons": ["wpn_hg_03"], "start_kit_value": 20000, "kills": kills, "shots": 30, "hits": 20})
	var st := RaidStory.make(a, true, _rng(4))
	_check("с пистолетом пять убийств и вышел — вердикт «не ствол делает рейдера»", _in_pool(st.verdict, RaidStory.data().verdicts.pistol_hero), st.verdict)
	var tags := st.tags.map(func(t: Dictionary) -> String: return String(t.tag))
	_check("теги: пистолет, серия, слабым оружием, меткость", "pistol_start" in tags and "kill_streak" in tags and "weak_weapon_kills" in tags and "high_accuracy" in tags, str(tags))
	print("    ", _text(st).replace("\n", "\n    "))


## Один и тот же рейд подряд: стиль меняется, тексты разные.
func _check_variety() -> void:
	Profile.raid_history = []
	var prev_style := ""
	var same_style := 0
	var texts := {}
	for i in range(6):
		var st := RaidStory.make(_raid("extract", {"kills": [{"t": 50.0, "arch": "scout", "faction": "marauder", "weapon": "wpn_ar_03", "grenade": false}]}), true, _rng(100 + i))
		if st.style == prev_style:
			same_style += 1
		prev_style = st.style
		texts[_text(st)] = true
	_check("стиль не повторяется подряд", same_style == 0, "")
	_check("шесть одинаковых рейдов — шесть разных текстов", texts.size() == 6, str(texts.size()))


## Случайные рейды: форма рассказа и подстановки.
func _check_fuzz() -> void:
	var r := _rng(7)
	var bad: Array = []
	for i in range(400):
		Profile.raid_history = [] if r.randf() < 0.3 else Profile.raid_history
		var died := r.randf() < 0.5
		var kills: Array = []
		for k in range(r.randi_range(0, 14)):
			kills.append({"t": r.randf_range(0, 900), "arch": ["scout", "gunner", "heavy", "sniper"][r.randi() % 4],
				"faction": ["marauder", "pmc", "resident"][r.randi() % 3], "weapon": ["wpn_hg_03", "wpn_ar_03", "", "wpn_sg_02"][r.randi() % 4],
				"grenade": r.randf() < 0.1, "leader": r.randf() < 0.1})
		kills.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return float(x.t) < float(y.t))
		var causes := ["ai", "grenade", "self_grenade", "friendly", "bleed", "give_up"]
		var shots := r.randi_range(0, 300)
		var a := _raid("death" if died else "extract", {
			"ended_ms": r.randi_range(20, 2400) * 1000, "start_weapons": [["wpn_hg_03"], ["wpn_ar_03"], [], ["wpn_sg_02", "wpn_hg_03"]][r.randi() % 4],
			"weapons_used": ["wpn_sr_01"] if r.randf() < 0.3 else [], "start_kit_value": r.randi_range(0, 400000), "kills": kills,
			"shots": shots, "hits": r.randi_range(0, shots), "damage_taken": r.randf_range(0, 300) if r.randf() < 0.8 else 0.0,
			"friendly_hits": r.randi_range(0, 2), "downs": r.randi_range(0, 2), "low_hp_moments": r.randi_range(0, 3),
			"heals": ["medkit", "bandage", "medkit"] if r.randf() < 0.3 else [], "enemy_self_grenades": int(r.randf() < 0.1),
			"enemy_ally_grenades": int(r.randf() < 0.1), "near_extract_sec": r.randf_range(0, 200),
			"end_value": r.randi_range(0, 500000), "found_value": r.randi_range(0, 90000), "found_items": r.randi_range(0, 20),
			"best_find": {"id": "gold_chain", "value": 45000} if r.randf() < 0.3 else {},
			"extract_name": "Парковка" + (Raid.CARRIED_SUFFIX if r.randf() < 0.2 else "") if not died else "",
			"death": {"cause": causes[r.randi() % causes.size()], "arch": ["scout", "sniper", "pmc", ""][r.randi() % 4],
				"faction": ["marauder", "pmc", "resident"][r.randi() % 3], "weapon": ["wpn_ar_03", ""][r.randi() % 2]} if died else {},
			"death_extract_dist": r.randf_range(0, 200) if died else INF})
		var st := RaidStory.make(a, true, r)
		var t := _text(st)
		if st.paragraphs.size() < 2 or st.paragraphs.size() > 5:
			bad.append("абзацев %d" % st.paragraphs.size())
		if t.contains("{") or t.contains("}") or t.contains("  ") or st.verdict.strip_edges() == "":
			bad.append(t)
		for p in st.paragraphs:
			if p.strip_edges() == "":
				bad.append("пустой абзац")
		if bad.size() > 5:
			break
		if i < 3:
			print("    [%s] %s" % [st.style, t.replace("\n", "\n    ")])
	_check("400 случайных рейдов: 2–5 абзацев, всё подставлено", bad.is_empty(), str(bad.slice(0, 3)))


## В уровне: факты от хоста, причина смерти, экран итога.
func _check_in_level() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() < 2:
		await get_tree().process_frame
	var ms := level.get_node("Marauders").get_children()
	for i in range(1, ms.size()):
		ms[i].queue_free()
	var m := ms[0] as Marauder
	var me := Raid.current.local_player()
	await get_tree().create_timer(0.5).timeout
	var an := Raid.current.analytics
	_check("в уровне: хроника началась", an.started_ms >= 0, "")
	m.global_position = me.global_position + Vector3(0, 0, -6)
	# в шлеме и бронежилете с одного раза не падает — добиваем
	var mh := m.get_node("Health") as Health
	for i in range(12):
		if not mh.alive:
			break
		mh.apply_or_request_damage(400.0, me.global_position, "thorax", -1, Vector3.INF, {"src": {"kind": "player"}})
		await get_tree().process_frame
	_check("убил мародёра — в хронике, урон нанесён", an.kills.size() == 1 and an.damage_dealt > 0.0, "убийств %d, урон %.0f" % [an.kills.size(), an.damage_dealt])
	# по игроку стреляет снайпер: ранен, добит
	var src := {"kind": "ai", "faction": "marauder", "arch": "sniper", "weapon": "wpn_sr_01"}
	me.health.apply_or_request_damage(30.0, me.global_position + Vector3(20, 0, 0), "thorax", 0, Vector3.INF, {"src": src})
	_check("попали — в хронике", an.hits_taken == 1 and an.damage_taken > 0.0 and an.friendly_hits == 0, "%d, %.0f" % [an.hits_taken, an.damage_taken])
	for i in range(8):
		if not me.health.alive:
			break
		me.health.apply_or_request_damage(500.0, me.global_position + Vector3(20, 0, 0), "head", 0, Vector3.INF, {"src": src})
		await get_tree().process_frame
	await get_tree().create_timer(0.3).timeout
	_check("погиб — причина от хоста: снайпер", an.outcome == "death" and String(an.death.get("cause", "")) == "ai" and String(an.death.get("arch", "")) == "sniper", str(an.death))
	var ch := Raid.current.chronicle
	_check("экран итога: хроника, вердикт, статистика", ch != null and Raid.current._story_panel.visible and Raid.current._story_text.text.length() > 80 and Raid.current._story_verdict.text != "", "")
	if ch:
		var stats := {}
		for row in ch.stats:
			stats[String(row[0])] = String(row[1])
		_check("статистика: убийства 1, причина — снайпер", stats.get("Убийства", "") == "1" and String(stats.get("Итог", "")).contains("снайпер"), str(stats))
		print("    ", _text(ch).replace("\n", "\n    "))
		print("    ", stats)
	# с окном — снимок экрана итога
	if DisplayServer.get_name() != "headless":
		await get_tree().create_timer(0.5).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/story_summary.png")


func _in_pool(line: String, pool: Array) -> bool:
	for p in pool:
		# {переменная} — любая подстановка
		var re := RegEx.new()
		re.compile("^" + _escape_vars(String(p)) + "$")
		if re.search(line) != null:
			return true
	return false


func _escape_vars(p: String) -> String:
	var out := ""
	var i := 0
	while i < p.length():
		var c := p.substr(i, 1)
		if c == "{":
			var j := p.find("}", i)
			out += ".+?"
			i = j + 1
			continue
		out += _escape(c)
		i += 1
	return out


func _escape(s: String) -> String:
	var out := ""
	for c in s:
		out += ("\\" + c) if c in ".^$*+?()[]{}|\\" else c
	return out


## Последняя фраза рассказа (концовка).
func _last_sentences(st: RaidStory) -> String:
	var last: String = st.paragraphs[-1]
	var pool: Array = []
	for style in (RaidStory.data().endings.death.self_grenade as Dictionary):
		pool.append_array(RaidStory.data().endings.death.self_grenade[style])
	for p in pool:
		var re := RegEx.new()
		re.compile(_escape_vars(String(p)) + "$")
		var m := re.search(last)
		if m:
			return m.get_string()
	return last


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
