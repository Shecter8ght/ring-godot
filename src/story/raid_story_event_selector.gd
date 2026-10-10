class_name RaidStoryEventSelector
extends RefCounted
## Хроника рейда, шаг 3: что из тегов RaidSummary попадёт в рассказ. Вступление — самый интересный
## тег начала (с чем пришёл), для которого есть фразы; события — 3–6 самых интересных из середины и
## конца (с небольшой случайной прибавкой к интересности, чтобы похожие рейды звучали по-разному),
## в естественном порядке рассказа. Теги без фраз (серии рейдов, повторы) идут только в вердикт.

## Порядок в рассказе: чем вооружился → бой → мир → здоровье → добыча → уход.
const ORDER := ["weapon_upgrade", "weapon_switches", "some_kills", "zero_kills", "high_kill_count", "kill_streak",
	"grenade_kills", "weak_weapon_kills", "pmc_kill", "rival_kill", "sniper_kill", "leader_kill", "enemy_self_grenade",
	"enemy_ally_grenade", "high_accuracy", "low_accuracy", "trigger_happy", "friendly_fire", "player_low_hp",
	"survived_downed", "many_heals", "no_damage", "big_find", "valuable_loot", "empty_handed", "missions_done",
	"long_raid", "camped_exit", "fast_death", "killed_by_weak", "near_extract_death"]


## {intro: тег вступления или «*», mid: [теги], end: [теги]} — теги как в RaidSummary.tags.
static func select(tags: Array, data: Dictionary, rng: RandomNumberGenerator) -> Dictionary:
	var cfg: Dictionary = Balance.RAID_STORY
	var intros: Dictionary = data.get("intro", {})
	var events: Dictionary = data.get("events", {})
	var intro := "*"
	var intro_score := -1.0
	var pool: Array = []
	var interesting := 0
	for t in tags:
		var tag := String(t.tag)
		if String(t.phase) == "start":
			if intros.has(tag) and float(t.score) > intro_score:
				intro = tag
				intro_score = float(t.score)
			continue
		if not events.has(tag):
			continue
		var c: Dictionary = (t as Dictionary).duplicate()
		c["weight"] = float(t.score) + rng.randf() * float(cfg.pick_jitter)
		pool.append(c)
		if float(t.score) >= float(cfg.interesting):
			interesting += 1
	pool.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.weight) > float(b.weight))
	var n := clampi(interesting + rng.randi_range(0, 1), int(cfg.events_min), int(cfg.events_max))
	var picked := pool.slice(0, mini(n, pool.size()))
	picked.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return ORDER.find(String(a.tag)) < ORDER.find(String(b.tag)))
	var mid: Array = []
	var end: Array = []
	for t in picked:
		(end if String(t.phase) == "end" else mid).append(t)
	return {"intro": intro, "mid": mid, "end": end}
