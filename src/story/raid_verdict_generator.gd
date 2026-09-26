class_name RaidVerdictGenerator
extends RefCounted
## Хроника рейда, шаг 5: вердикт — одна фраза. Берётся самое конкретное, что было: после смерти —
## повтор той же смерти, своя граната, огонь своих, серия потерянных дорогих комплектов, смерть у
## самого выхода, быстрая смерть в дорогом… и только потом общее «не ваш день»; после эвакуации —
## вынесли раненым, выход после серии смертей, серия выходов, много убийств, ценный лут… Пулы —
## data/raid_story.json (verdicts), после смерти они саркастичные.


## Ключ пула вердиктов (verdicts.<ключ>) по тегам рейда и истории.
static func key(s: RaidSummary, tags: Array, history: Array) -> String:
	var has := {}
	for t in tags:
		has[String(t.tag)] = t
	if s.outcome == "stranded":
		return "stranded"
	if s.outcome == "death":
		for pair in [["repeated_death_reason", "repeated"], ["player_self_grenade", "self_grenade"],
				["friendly_fire_death", "friendly"], ["expensive_loss_streak", "loss_streak"],
				["near_extract_death", "near_exit"]]:
			if has.has(pair[0]):
				return String(pair[1])
		if has.has("fast_death") and has.has("expensive_loadout"):
			return "fast_expensive"
		for pair in [["killed_by_weak", "killed_by_weak"], ["fast_death", "fast"], ["death_streak", "death_streak"],
				["bleed_out", "bleed"], ["gave_up", "give_up"], ["grenade_death", "grenade"],
				["high_kill_count", "many_kills_death"], ["expensive_loadout", "expensive_death"], ["zero_kills", "no_kills_death"]]:
			if has.has(pair[0]):
				return String(pair[1])
		return "death"
	if s.carried:
		return "carried"
	# живым после двух и больше смертей подряд
	var deaths := 0
	for h in history:
		if String(h.get("outcome", "")) != "death":
			break
		deaths += 1
	if deaths >= 2:
		return "comeback"
	if has.has("extract_streak"):
		return "extract_streak"
	if (has.has("pistol_start") or has.has("no_weapon_start")) and (s.kill_count >= 3 or has.has("valuable_loot")):
		return "pistol_hero"
	for pair in [["high_kill_count", "many_kills"], ["valuable_loot", "rich"], ["no_damage", "no_damage"],
			["survived_downed", "survived_downed"], ["empty_handed", "empty"]]:
		if has.has(pair[0]):
			return String(pair[1])
	return "extract"


## Фраза вердикта (gen — тот же генератор, что писал рассказ: стиль, подстановки, память фраз).
static func verdict(s: RaidSummary, tags: Array, history: Array, gen: RaidStoryGenerator) -> String:
	var k := key(s, tags, history)
	var pools: Dictionary = gen.data.get("verdicts", {})
	var pool: Variant = pools.get(k, pools.get("death" if s.outcome == "death" else "extract", []))
	# повтор смерти — пул по причине
	if pool is Dictionary:
		pool = (pool as Dictionary).get(s.death_cause, (pool as Dictionary).get("ai", []))
	# серии: сколько подряд (тег той серии, о которой вердикт)
	var streak_tag := String({"loss_streak": "expensive_loss_streak", "death_streak": "death_streak", "extract_streak": "extract_streak"}.get(k, ""))
	var n := 0
	for t in tags:
		if String(t.tag) == streak_tag:
			n = int(t.get("n", 0))
	var T := RaidStoryText
	var extra := {"n": str(n), "n_ord": T.ordinal(n), "n_ord_cap": T.cap(T.ordinal(n)),
		"n_gifts": T.count(n, "щедрое пожертвование", "щедрых пожертвования", "щедрых пожертвований", "n"),
		"n_deaths_cap": T.cap(T.count(n, "смерть", "смерти", "смертей", "f")),
		"n_exits_cap": T.cap(T.count(n, "выход", "выхода", "выходов")),
		"n_raids": T.count(n, "удачный рейд", "удачных рейда", "удачных рейдов")}
	return gen.pick(pool as Array, extra)
