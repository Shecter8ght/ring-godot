class_name RaidHistory
extends RefCounted
## Хроника рейда: короткая история последних рейдов в профиле (Profile.raid_history, новее первым,
## не больше Balance.RAID_STORY.history_n) — повторы и серии для рассказа и вердикта; и какие
## фразы уже звучали (Profile.story_recent) — чтобы два похожих рейда не звучали одинаково.


static func recent() -> Array:
	return Profile.raid_history


## Рейд окончен: запомнить главное.
static func record(s: RaidSummary, style: String) -> void:
	var weapon := String(s.start_weapons[0]) if not s.start_weapons.is_empty() else ""
	Profile.raid_history.push_front({"outcome": s.outcome, "cause": s.death_cause, "killer": s.death_killer, "kit": s.start_kit_value,
		"kills": s.kill_count, "sec": int(s.duration), "loot": s.loot_value, "lost": s.lost_value,
		"weapon": String(WeaponDb.weapon(weapon).get("class", "")), "style": style})
	while Profile.raid_history.size() > int(Balance.RAID_STORY.history_n):
		Profile.raid_history.pop_back()


static func last_style() -> String:
	return String((Profile.raid_history[0] as Dictionary).get("style", "")) if not Profile.raid_history.is_empty() else ""


## Эта фраза недавно звучала?
static func used(line: String) -> bool:
	return line.hash() in Profile.story_recent


static func remember(line: String) -> void:
	Profile.story_recent.push_front(line.hash())
	while Profile.story_recent.size() > int(Balance.RAID_STORY.recent_lines):
		Profile.story_recent.pop_back()
