class_name RaidStory
extends RefCounted
## Хроника рейда целиком: RaidAnalytics → RaidSummary (факты и теги) → RaidStoryEventSelector (что
## рассказать) → RaidStoryGenerator (абзацы в одном из стилей) → RaidVerdictGenerator (одна фраза) →
## RaidHistory (запомнить рейд — для повторов и серий). Всё локально, без сети и без LLM: фразы —
## data/raid_story.json, рассказ — только о том, что было. Показывает Raid на экране итога.

const DATA_PATH := "res://data/raid_story.json"

static var _data: Dictionary = {}

var style: String = ""
var paragraphs: Array[String] = []
var verdict: String = ""
## Статистика под рассказом: [[подпись, значение], …].
var stats: Array = []
var tags: Array = []
var summary: RaidSummary


static func data() -> Dictionary:
	if _data.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
		if parsed is Dictionary:
			_data = parsed
	return _data


## Рассказ о рейде своего игрока. record — записать рейд в историю профиля (рейд из убежища;
## сохранить профиль — забота вызывающего). rng — для тестов (одинаковый рассказ).
static func make(a: RaidAnalytics, record: bool, rng: RandomNumberGenerator = null) -> RaidStory:
	if rng == null:
		rng = RandomNumberGenerator.new()
		rng.randomize()
	var st := RaidStory.new()
	var history := RaidHistory.recent()
	st.summary = RaidSummary.from(a)
	st.tags = st.summary.tags(history)
	var gen := RaidStoryGenerator.new(st.summary, data(), rng)
	st.style = gen.pick_style(RaidHistory.last_style())
	st.paragraphs = gen.paragraphs(RaidStoryEventSelector.select(st.tags, data(), rng))
	st.verdict = RaidVerdictGenerator.verdict(st.summary, st.tags, history, gen)
	st.stats = stats_of(st.summary, gen)
	if record:
		RaidHistory.record(st.summary, st.style)
	return st


## Цифры под рассказом.
static func stats_of(s: RaidSummary, gen: RaidStoryGenerator) -> Array:
	var T := RaidStoryText
	var out: Array = []
	var sec := int(round(s.duration))
	out.append(["Время в рейде", "%d мин %02d с" % [sec / 60, sec % 60] if sec >= 60 else "%d с" % sec])
	out.append(["Убийства", str(s.kill_count)])
	out.append(["Точность", "%d%% (%d из %d)" % [int(round(s.accuracy * 100.0)), s.hits, s.shots] if s.shots > 0 else "не стрелял"])
	out.append(["Урон", "нанёс %d · получил %d" % [int(round(s.damage_dealt)), int(round(s.damage_taken))]])
	out.append(["Найдено", "%d %s" % [s.found_items, T.plural(s.found_items, "предмет", "предмета", "предметов")]])
	if s.outcome == "extract":
		out.append(["Стоимость добычи", T.money(s.loot_value)])
	else:
		var gone := "осталось в рейде" if s.outcome == "death" else "пропало"
		out.append(["Стоимость добычи", "%s — %s" % [T.money(s.found_value), gone] if s.found_value > 0 else "—"])
		out.append(["Потеряно", T.money(s.lost_value)])
	var names: Array[String] = []
	for id in s.missions_done:
		names.append("«%s»" % String(Missions.find(id).get("name", id)))
	out.append(["Задания", ", ".join(names) if not names.is_empty() else "—"])
	if s.outcome == "extract":
		out.append(["Итог", "эвакуация: %s%s" % [s.exit_display, " (вынесли раненым)" if s.carried else ""]])
	elif s.outcome == "stranded":
		out.append(["Итог", "не успел к эвакуации (группа ушла через «%s»)" % s.exit_display])
	else:
		out.append(["Итог", "погиб: " + cause_text(s, gen)])
	return out


## Причина смерти коротко: «мародёр-штурмовик (автомат)», «своя граната».
static func cause_text(s: RaidSummary, gen: RaidStoryGenerator) -> String:
	match s.death_cause:
		"self_grenade":
			return "своя граната"
		"grenade":
			return "граната противника"
		"friendly":
			return "огонь своих"
		"bleed":
			return "кровопотеря (%s)" % String(gen.vars.killer) if s.death_killer not in ["", "*"] else "кровопотеря"
		"give_up":
			return "сдался раненым"
	var w := String(gen.vars.killer_w)
	return String(gen.vars.killer) + (" (%s)" % w if w != "" else "")
