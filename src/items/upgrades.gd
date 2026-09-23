class_name Upgrades
extends RefCounted
## Модули убежища (data/hideout.json): верстак, генератор, защищённый карман, тайник, рация.
## Уровень строится за деньги и детали из тайника, нужен уровень доверия Михалыча и иногда другой
## модуль (генератор). Уровни — в профиле (Profile.modules). Эффекты читают другие системы:
## верстак — Profile.install_mod, карман — рейд, тайник — Profile.stash_grid, рация — Missions.

const PATH := "res://data/hideout.json"

static var _mods: Array = []


static func all() -> Array:
	if _mods.is_empty():
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
		if d is Dictionary:
			_mods = (d as Dictionary).get("modules", [])
	return _mods


static func find(id: String) -> Dictionary:
	for m in all():
		if String(m.id) == id:
			return m
	return {}


static func level(id: String) -> int:
	return int(Profile.modules.get(id, int(find(id).get("start", 0))))


static func max_level(id: String) -> int:
	return (find(id).get("levels", []) as Array).size()


## Что нужно для следующего уровня ({} — уже максимум).
static func next_cost(id: String) -> Dictionary:
	var lv := level(id)
	var levels: Array = find(id).get("levels", [])
	return levels[lv] if lv < levels.size() else {}


## Почему следующий уровень пока нельзя построить ("" — можно).
static func block(id: String) -> String:
	var c := next_cost(id)
	if c.is_empty():
		return "максимальный уровень"
	if Profile.trust_level() < int(c.get("trust", 1)):
		return "нужно доверие Михалыча %d" % int(c.get("trust", 1))
	for need in c.get("needs", {}):
		if level(String(need)) < int(c.needs[need]):
			return "сначала: %s %d" % [String(find(String(need)).get("name", need)), int(c.needs[need])]
	if Profile.money < int(c.get("money", 0)):
		return "не хватает денег"
	for pair in c.get("items", []):
		if Profile.stash_count(String(pair[0])) < int(pair[1]):
			return "нет в тайнике: %s × %d" % [ItemDb.item_name(String(pair[0])), int(pair[1])]
	return ""


## Построить следующий уровень: деньги и детали из тайника уходят.
static func build(id: String) -> bool:
	if block(id) != "":
		return false
	var c := next_cost(id)
	Profile.money -= int(c.get("money", 0))
	for pair in c.get("items", []):
		Profile.take_from_stash(String(pair[0]), int(pair[1]))
	Profile.modules[id] = level(id) + 1
	Profile.save()
	return true
