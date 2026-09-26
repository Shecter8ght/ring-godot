class_name RaidStoryGenerator
extends RefCounted
## Хроника рейда, шаг 4: абзацы рассказа. Стиль — случайный, но не тот, что в прошлый раз. Абзац 1 —
## вступление и первое событие; дальше события по два, иногда со связкой («Слушай дальше.»);
## последний — события конца и концовка по исходу (эвакуация / чем убит). Фразы — из
## data/raid_story.json: пул стиля вперемешку с общим («*»), недавно звучавшие — в последнюю очередь.
## Переменные фраз ({kills_ppl}, {killer}…) — только из фактов RaidSummary.

var s: RaidSummary
var data: Dictionary
var rng: RandomNumberGenerator
var style: String = ""
## Подстановки для фраз — все сразу (каждое событие берёт свои).
var vars: Dictionary = {}
var _said: Dictionary = {}


func _init(summary: RaidSummary, d: Dictionary, r: RandomNumberGenerator) -> void:
	s = summary
	data = d
	rng = r
	vars = _vars()


## Стиль по весам data.styles, кроме avoid (прошлого).
func pick_style(avoid: String) -> String:
	var styles: Dictionary = data.get("styles", {})
	var total := 0.0
	for k in styles:
		if String(k) != avoid or styles.size() == 1:
			total += float(styles[k])
	var roll := rng.randf() * total
	style = ""
	for k in styles:
		if String(k) == avoid and styles.size() > 1:
			continue
		style = String(k)
		roll -= float(styles[k])
		if roll <= 0.0:
			break
	return style


## Фраза из пула {стиль: [...], "*": [...]}.
func line(pool: Dictionary, extra: Dictionary = {}) -> String:
	var lines: Array = []
	lines.append_array(pool.get(style, []))
	lines.append_array(pool.get("*", []))
	return pick(lines, extra)


## Одна из фраз: не звучавшая в этом рассказе и недавно (RaidHistory), если такая есть.
func pick(lines: Array, extra: Dictionary = {}) -> String:
	if lines.is_empty():
		return ""
	var fresh := lines.filter(func(l: Variant) -> bool: return not _said.has(l) and not RaidHistory.used(String(l)))
	if fresh.is_empty():
		fresh = lines.filter(func(l: Variant) -> bool: return not _said.has(l))
	if fresh.is_empty():
		fresh = lines
	var l := String(fresh[rng.randi() % fresh.size()])
	_said[l] = true
	RaidHistory.remember(l)
	var v := vars.duplicate()
	v.merge(extra, true)
	return RaidStoryText.prepositions(RaidStoryText.fill(l, v))


## 2–5 абзацев по отобранному (RaidStoryEventSelector.select).
func paragraphs(sel: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var intros: Dictionary = data.get("intro", {})
	var mid: Array = (sel.get("mid", []) as Array).duplicate()
	var first: Array[String] = [line(intros.get(String(sel.get("intro", "*")), intros.get("*", {})))]
	if not mid.is_empty():
		first.append(event(mid.pop_front()))
	out.append(" ".join(first))
	while not mid.is_empty():
		var p: Array[String] = []
		if rng.randf() < float(Balance.RAID_STORY.transition_chance):
			p.append(line(data.get("transitions", {})))
		p.append(event(mid.pop_front()))
		if not mid.is_empty():
			p.append(event(mid.pop_front()))
		out.append(" ".join(p))
	var last: Array[String] = []
	for t in sel.get("end", []):
		last.append(event(t))
	last.append(ending())
	out.append(" ".join(last))
	return out


func event(t: Dictionary) -> String:
	return line((data.get("events", {}) as Dictionary).get(String(t.tag), {}))


## Концовка: вышел (сам / вынесли раненым) или погиб — от чего.
func ending() -> String:
	var endings: Dictionary = data.get("endings", {})
	if s.outcome == "extract":
		var ex: Dictionary = endings.get("extract", {})
		return line(ex.get("carried" if s.carried else "*", ex.get("*", {})))
	var death: Dictionary = endings.get("death", {})
	var key := s.death_cause
	# от ИИ: иногда — с тем, из чего стрелял
	if key == "ai" and String(s.death.get("weapon", "")) != "" and rng.randf() < 0.5:
		key = "ai_weapon"
	return line(death.get(key, death.get("*", {})))


# ---------------------------------------------------------------- подстановки

func _vars() -> Dictionary:
	var T := RaidStoryText
	var v := {}
	_weapon_vars(v, "start_w", String(s.start_weapons[0]) if not s.start_weapons.is_empty() else "")
	_weapon_vars(v, "found_w", s.found_weapon)
	v.kit = T.money(s.start_kit_value)
	var k := s.start_kit_value / 1000
	v.kit_k = T.words(k) if k < 1000 else str(k)
	v.kills = str(s.kill_count)
	_count_vars(v, "kills_ppl", s.kill_count, ["человек", "человека", "человек"], "m")
	_count_vars(v, "kills_foes", s.kill_count, ["противник", "противника", "противников"], "m")
	_count_vars(v, "kills_bodies", s.kill_count, ["тело", "тела", "тел"], "n")
	v.streak = str(s.best_streak)
	_count_vars(v, "streak_ppl", s.best_streak, ["человек", "человека", "человек"], "m")
	v.nade = str(s.grenade_kills)
	_count_vars(v, "nade_ppl", s.grenade_kills, ["человек", "человека", "человек"], "m")
	v.weak = str(s.weak_kills)
	_count_vars(v, "weak_ppl", s.weak_kills, ["человек", "человека", "человек"], "m")
	_count_vars(v, "n_times", s.weapon_switches, ["раз", "раза", "раз"], "m")
	v.pct = str(int(round(s.accuracy * 100.0)))
	_count_vars(v, "misses", s.shots - s.hits, ["выстрел", "выстрела", "выстрелов"], "m")
	_count_vars(v, "shots_n", s.shots, ["выстрел", "выстрела", "выстрелов"], "m")
	_count_vars(v, "downs_times", s.downs, ["раз", "раза", "раз"], "m")
	_count_vars(v, "crit_times", s.critical, ["раз", "раза", "раз"], "m")
	_count_vars(v, "heals_times", s.heals, ["раз", "раза", "раз"], "m")
	_count_vars(v, "ff_times", s.friendly_hits, ["раз", "раза", "раз"], "m")
	var item := ItemDb.item_name(String(s.best_find.get("id", ""))) if not s.best_find.is_empty() else ""
	# «Золотая цепочка» посреди фразы — со строчной (аббревиатуры не трогаем)
	if item.length() > 1 and item.substr(1, 1) == item.substr(1, 1).to_lower():
		item = item.substr(0, 1).to_lower() + item.substr(1)
	v.find_item = item
	v.find_item_cap = T.cap(item)
	v.find_value = T.money(int(s.best_find.get("value", 0)))
	v.loot = T.money(s.loot_value)
	_count_vars(v, "missions", s.missions_done.size(), ["задание", "задания", "заданий"], "n")
	v.missions_n = str(s.missions_done.size())
	v.time = T.duration(s.duration)
	v.time_cap = T.cap(v.time)
	v.near_time = T.duration(s.near_extract_sec)
	v.near_time_cap = T.cap(v.near_time)
	v.exit = s.exit_display
	v.exit_m = "%d м" % int(s.death_extract_dist) if s.death_extract_dist < INF else ""
	v.exit_m_cap = v.exit_m
	var arch: Dictionary = data.get("arch", {})
	var who: Dictionary = arch.get(s.death_killer if s.death_killer != "" else "*", arch.get("*", {}))
	v.killer = String(who.get("nom", ""))
	v.killer_cap = T.cap(v.killer)
	v.killer_ins = String(who.get("ins", ""))
	var kw := forms(String(s.death.get("weapon", "")))
	v.killer_w = String(kw.get("nom", ""))
	v.killer_w_ins = String(kw.get("ins", ""))
	return v


## Формы слова оружия по классу (пистолет / пистолетом…); пусто — «голые руки».
func forms(weapon_id: String) -> Dictionary:
	var classes: Dictionary = data.get("weapon_class", {})
	if weapon_id == "":
		return classes.get("", {})
	var cls := String(WeaponDb.weapon(weapon_id).get("class", ""))
	return classes.get(cls, classes.get("SPECIAL", {}))


func _weapon_vars(v: Dictionary, key: String, weapon_id: String) -> void:
	var f := forms(weapon_id)
	v[key] = String(f.get("nom", ""))
	for c in ["ins", "acc", "gen"]:
		v["%s_%s" % [key, c]] = String(f.get(c, ""))


## «три человека» и «Три человека».
func _count_vars(v: Dictionary, key: String, n: int, words: Array, gender: String) -> void:
	v[key] = RaidStoryText.count(n, String(words[0]), String(words[1]), String(words[2]), gender)
	v[key + "_cap"] = RaidStoryText.cap(String(v[key]))
