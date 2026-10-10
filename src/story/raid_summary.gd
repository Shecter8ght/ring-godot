class_name RaidSummary
extends RefCounted
## Хроника рейда, шаг 2: итог по фактам RaidAnalytics и теги событий — что в этом рейде было
## необычного. Тег: {tag, score (насколько интересно), phase ("start"/"mid"/"end" — где в рассказе),
## и данные для текста}. Пороги — Balance.RAID_STORY. История прошлых рейдов (RaidHistory) даёт
## теги повторов: снова та же смерть, третий дорогой комплект подряд, серия выходов.

var duration: float = 0.0
var outcome: String = ""
var extract_name: String = ""
## Точка без приписки; вынесли раненым (дотащил напарник).
var exit_display: String = ""
var carried: bool = false
var start_weapons: Array[String] = []
var start_kit_value: int = 0
var kills: Array = []
var kill_count: int = 0
var best_streak: int = 0
var grenade_kills: int = 0
var weak_kills: int = 0
var kills_by_arch: Dictionary = {}
var shots: int = 0
var hits: int = 0
var accuracy: float = 0.0
var damage_taken: float = 0.0
var damage_dealt: float = 0.0
var friendly_hits: int = 0
var downs: int = 0
var critical: int = 0
var min_hp_frac: float = 1.0
var heals: int = 0
var loot_value: int = 0
var found_value: int = 0
var best_find: Dictionary = {}
var found_weapon: String = ""
var weapon_switches: int = 0
var enemy_self_grenades: int = 0
var enemy_ally_grenades: int = 0
var near_extract_sec: float = 0.0
var death: Dictionary = {}
var death_cause: String = ""
## Кто убил: ключ формы в raid_story.json (arch: scout…, pmc, resident, player, «*»).
var death_killer: String = ""
## Найдено в рейде: предметов с меткой «из рейда».
var found_items: int = 0
var death_extract_dist: float = INF
var missions_done: Array[String] = []
var missions_left: Array[String] = []
var lost_value: int = 0


static func from(a: RaidAnalytics) -> RaidSummary:
	var s := RaidSummary.new()
	var cfg: Dictionary = Balance.RAID_STORY
	s.duration = float(maxi(a.ended_ms, a.started_ms) - a.started_ms) / 1000.0
	s.outcome = a.outcome
	s.extract_name = a.extract_name
	s.carried = a.extract_name.ends_with(Raid.CARRIED_SUFFIX)
	s.exit_display = a.extract_name.trim_suffix(Raid.CARRIED_SUFFIX)
	s.start_weapons = a.start_weapons
	s.start_kit_value = a.start_kit_value
	s.kills = a.kills
	s.kill_count = a.kills.size()
	s.shots = a.shots
	s.hits = a.hits
	s.accuracy = float(a.hits) / float(a.shots) if a.shots > 0 else 0.0
	s.damage_taken = a.damage_taken
	s.damage_dealt = a.damage_dealt
	s.found_items = a.found_items
	s.friendly_hits = a.friendly_hits
	s.downs = a.downs
	s.critical = a.low_hp_moments
	s.min_hp_frac = a.min_hp_frac
	s.heals = a.heals.size()
	s.found_value = a.found_value
	s.best_find = a.best_find
	s.weapon_switches = a.weapon_switches
	s.enemy_self_grenades = a.enemy_self_grenades
	s.enemy_ally_grenades = a.enemy_ally_grenades
	s.near_extract_sec = a.near_extract_sec
	s.death = a.death
	s.death_extract_dist = a.death_extract_dist
	s.missions_done = a.missions_done
	s.missions_left = a.missions_left
	s.loot_value = maxi(0, a.end_value - a.start_kit_value) if a.outcome == "extract" else 0
	s.lost_value = a.start_kit_value if a.outcome == "death" or a.outcome == "stranded" else 0
	# убийства: подряд (окно streak_sec), гранатой, «слабым» оружием, по типам
	for i in range(a.kills.size()):
		var k: Dictionary = a.kills[i]
		var n := 1
		for j in range(i + 1, a.kills.size()):
			if float(a.kills[j].t) - float(k.t) <= float(cfg.streak_sec):
				n += 1
		s.best_streak = maxi(s.best_streak, n)
		if bool(k.grenade):
			s.grenade_kills += 1
		elif _weak(String(k.weapon)):
			s.weak_kills += 1
		var key := String(k.faction) if String(k.faction) in ["pmc", "resident", "rival"] else String(k.arch)
		s.kills_by_arch[key] = int(s.kills_by_arch.get(key, 0)) + 1
		if bool(k.get("leader", false)):
			s.kills_by_arch["leader"] = int(s.kills_by_arch.get("leader", 0)) + 1
	# нашёл оружие получше того, с чем пришёл, и держал в руках (в песочнице стволы все сразу — не в счёт)
	for w in (a.weapons_used if a.loadout else []):
		if not w in a.start_weapons and _tier(w) > _best_tier(a.start_weapons):
			s.found_weapon = w
	s.death_cause = _cause(a.death)
	s.death_killer = killer_key(a.death)
	return s


## Кто убил — ключ форм слова: ЧВК и жильцы — по фракции, мародёры — по типу, свой — «player».
static func killer_key(d: Dictionary) -> String:
	if d.is_empty():
		return ""
	match String(d.get("cause", "")):
		"friendly":
			return "player"
		"self_grenade":
			return "self"
	var faction := String(d.get("faction", ""))
	if faction == "pmc" or faction == "resident" or faction == "rival":
		return faction
	var arch := String(d.get("arch", ""))
	return arch if arch != "" else "*"


## Чем кончилось: self_grenade, grenade, friendly, bleed, give_up, ai.
static func _cause(d: Dictionary) -> String:
	if d.is_empty():
		return ""
	return String(d.get("cause", "ai"))


static func _tier(w: String) -> int:
	var cls := String(WeaponDb.weapon(w).get("class", ""))
	return int(Balance.RAID_STORY.class_rank.get(cls, 1))


static func _best_tier(list: Array[String]) -> int:
	var t := 0
	for w in list:
		t = maxi(t, _tier(w))
	return t


## «Слабое» оружие: пистолет или совсем простое (класс с рангом ≤ 1).
static func _weak(w: String) -> bool:
	return w != "" and _tier(w) <= 1


## Теги событий этого рейда — с учётом истории прошлых (history — последние рейды, новее первым).
func tags(history: Array) -> Array:
	var cfg: Dictionary = Balance.RAID_STORY
	var out: Array = []
	var died := outcome == "death"
	# вход: с чем пришёл
	if start_weapons.is_empty():
		out.append(_t("no_weapon_start", 0.7, "start"))
	elif _best_tier(start_weapons) <= 1:
		out.append(_t("pistol_start", 0.6, "start"))
	if start_kit_value >= int(cfg.expensive_kit):
		out.append(_t("expensive_loadout", 0.55, "start"))
	elif start_kit_value > 0 and start_kit_value <= int(cfg.cheap_kit):
		out.append(_t("cheap_loadout", 0.5, "start"))
	# мир
	if enemy_self_grenades > 0:
		out.append(_t("enemy_self_grenade", 0.95, "mid", {"n": enemy_self_grenades}))
	if enemy_ally_grenades > 0:
		out.append(_t("enemy_ally_grenade", 0.9, "mid", {"n": enemy_ally_grenades}))
	# бой
	if kill_count == 0:
		out.append(_t("zero_kills", 0.45 if not died else 0.35, "mid"))
	elif kill_count >= int(cfg.high_kills):
		out.append(_t("high_kill_count", 0.9, "mid", {"n": kill_count}))
	else:
		out.append(_t("some_kills", 0.4, "mid", {"n": kill_count}))
	if best_streak >= int(cfg.streak_n):
		out.append(_t("kill_streak", 0.8, "mid", {"n": best_streak}))
	if grenade_kills > 0:
		out.append(_t("grenade_kills", 0.75, "mid", {"n": grenade_kills}))
	if weak_kills >= int(cfg.weak_kills):
		out.append(_t("weak_weapon_kills", 0.7, "mid", {"n": weak_kills}))
	if kills_by_arch.has("pmc"):
		out.append(_t("pmc_kill", 0.85, "mid", {"n": int(kills_by_arch.pmc)}))
	if kills_by_arch.has("rival"):
		out.append(_t("rival_kill", 0.8, "mid", {"n": int(kills_by_arch.rival)}))
	if kills_by_arch.has("sniper"):
		out.append(_t("sniper_kill", 0.65, "mid"))
	if kills_by_arch.has("leader"):
		out.append(_t("leader_kill", 0.6, "mid"))
	if found_weapon != "":
		out.append(_t("weapon_upgrade", 0.8, "mid", {"weapon": found_weapon}))
	if weapon_switches >= int(cfg.many_switches):
		out.append(_t("weapon_switches", 0.3, "mid", {"n": weapon_switches}))
	if shots >= int(cfg.accuracy_min_shots):
		if accuracy >= float(cfg.accurate):
			out.append(_t("high_accuracy", 0.6, "mid", {"pct": int(round(accuracy * 100.0))}))
		elif accuracy <= float(cfg.inaccurate):
			out.append(_t("low_accuracy", 0.55, "mid", {"pct": int(round(accuracy * 100.0)), "misses": shots - hits}))
	if shots >= int(cfg.trigger_happy):
		out.append(_t("trigger_happy", 0.5, "mid", {"n": shots}))
	# здоровье
	if downs > 0 and not died:
		out.append(_t("survived_downed", 0.85, "mid", {"n": downs}))
	elif critical > 0 and not died:
		out.append(_t("player_low_hp", 0.6, "mid"))
	if heals >= int(cfg.many_heals):
		out.append(_t("many_heals", 0.45, "mid", {"n": heals}))
	if damage_taken <= 0.0 and duration >= float(cfg.no_damage_min_sec) and not died:
		out.append(_t("no_damage", 0.7, "mid"))
	if friendly_hits > 0:
		out.append(_t("friendly_fire", 0.8, "mid", {"n": friendly_hits}))
	# добыча и задания
	if best_find.get("value", 0) >= int(cfg.big_find):
		out.append(_t("big_find", 0.65, "mid", {"item": String(best_find.id), "value": int(best_find.value)}))
	if outcome == "extract":
		if loot_value >= int(cfg.valuable_loot):
			out.append(_t("valuable_loot", 0.75, "end", {"value": loot_value}))
		elif loot_value < int(cfg.empty_handed):
			out.append(_t("empty_handed", 0.5, "end"))
	if not missions_done.is_empty():
		out.append(_t("missions_done", 0.55, "end", {"n": missions_done.size()}))
	# время
	if duration >= float(cfg.long_raid_sec):
		out.append(_t("long_raid", 0.35, "end"))
	if near_extract_sec >= float(cfg.camped_exit_sec) and not died:
		out.append(_t("camped_exit", 0.5, "end", {"sec": int(near_extract_sec)}))
	# конец
	if died:
		if duration <= float(cfg.fast_death_sec):
			out.append(_t("fast_death", 0.95, "end"))
		if death_extract_dist <= float(cfg.near_exit_m):
			out.append(_t("near_extract_death", 0.95, "end", {"m": int(death_extract_dist)}))
		match death_cause:
			"self_grenade":
				out.append(_t("player_self_grenade", 1.0, "end"))
			"grenade":
				out.append(_t("grenade_death", 0.8, "end"))
			"friendly":
				out.append(_t("friendly_fire_death", 1.0, "end"))
			"bleed":
				out.append(_t("bleed_out", 0.7, "end"))
			"give_up":
				out.append(_t("gave_up", 0.6, "end"))
		if kill_count >= int(cfg.high_kills) and death_cause == "ai" and death_killer in ["scout", "resident"]:
			out.append(_t("killed_by_weak", 0.9, "end"))
	elif outcome == "extract":
		out.append(_t("successful_extract", 0.2, "end"))
	# история
	if not history.is_empty():
		var prev: Dictionary = history[0]
		# та же смерть: причина та же, а от ИИ — ещё и тот же тип противника (иначе это не повтор)
		var same_death := died and String(prev.get("outcome", "")) == "death" and String(prev.get("cause", "")) == death_cause and death_cause != ""
		if same_death and death_cause == "ai":
			same_death = death_killer != "*" and String(prev.get("killer", "")) == death_killer
		if same_death:
			out.append(_t("repeated_death_reason", 0.9, "end", {"cause": death_cause}))
		# дорогой комплект потерян (погиб или не успел к эвакуации) — который раз подряд
		var lost := 1 if outcome != "extract" and start_kit_value >= int(cfg.expensive_kit) else 0
		for h in history:
			if String(h.get("outcome", "")) != "extract" and int(h.get("kit", 0)) >= int(cfg.expensive_kit) and lost > 0:
				lost += 1
			else:
				break
		if lost >= 2:
			out.append(_t("expensive_loss_streak", 0.9, "end", {"n": lost}))
		var same := 1
		for h in history:
			if String(h.get("outcome", "")) == outcome:
				same += 1
			else:
				break
		if same >= int(cfg.streak_raids) and outcome != "stranded":
			out.append(_t("extract_streak" if not died else "death_streak", 0.7, "end", {"n": same}))
	return out


static func _t(tag: String, score: float, phase: String, data: Dictionary = {}) -> Dictionary:
	var d := data.duplicate()
	d["tag"] = tag
	d["score"] = score
	d["phase"] = phase
	return d
