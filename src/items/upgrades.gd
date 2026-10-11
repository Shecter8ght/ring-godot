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
			for module: Dictionary in _mods:
				var prices: Dictionary = Balance.HIDEOUT_MODULE_PRICES.get(String(module.id), {})
				var levels: Array = module.get("levels", [])
				for i: int in range(levels.size()):
					(levels[i] as Dictionary)["money"] = int(prices.get(i + 1, 0))
	return _mods


static func find(id: String) -> Dictionary:
	for m in all():
		if String(m.id) == id:
			return m
	return {}


static func level(id: String) -> int:
	# чит «открыть всё»: модуль считается построенным до предела, сохранение не меняется
	if Settings.unlocked():
		return max_level(id)
	var flag: String = String(find(id).get("world_flag", ""))
	if flag != "":
		return 1 if Quests.flag(flag) == true else 0
	return int(Profile.modules.get(id, int(find(id).get("start", 0))))


static func max_level(id: String) -> int:
	return (find(id).get("levels", []) as Array).size()


## Все модули на пределе: id -> уровень (чит «открыть всё»).
static func max_levels() -> Dictionary:
	var out: Dictionary = {}
	for m in all():
		out[String(m.id)] = max_level(String(m.id))
	return out


## Что нужно для следующего уровня ({} — уже максимум).
static func next_cost(id: String) -> Dictionary:
	var lv := level(id)
	var levels: Array = find(id).get("levels", [])
	return levels[lv] if lv < levels.size() else {}


## Почему следующий уровень пока нельзя построить ("" — можно).
static func block(id: String) -> String:
	if String(find(id).get("world_flag", "")) != "":
		return "восстановление по заданию Михалыча «Своя метка»"
	var c := next_cost(id)
	if c.is_empty():
		return "максимальный уровень"
	if Profile.trust_level() < int(c.get("trust", 1)):
		return "нужна ступень доверия Михалыча %d" % TraderStock.step_of(int(c.get("trust", 1)))
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
	Quests.modules_changed()
	Audio.play_ui("upgrade")
	return true
