class_name Missions
extends RefCounted
## Задания Михалыча (data/missions.json): взять (слотов — Balance.MISSION_SLOTS, с рацией больше),
## выполнить в рейдах, сдать — деньги и доверие. Прогресс — в профиле (Profile.missions_active:
## id -> счётчик), сданные — Profile.missions_done. Счётчики двигает рейд: убийства, посещённые
## помещения, выход через точку, выживание подряд; «сдать предметы» — из тайника у торговца.

const PATH := "res://data/missions.json"

static var _list: Array = []


static func all() -> Array:
	if _list.is_empty():
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
		if d is Dictionary:
			_list = (d as Dictionary).get("missions", [])
	return _list


static func find(id: String) -> Dictionary:
	for m in all():
		if String(m.id) == id:
			return m
	return {}


static func slots() -> int:
	return int(Balance.MISSION_SLOTS[1 if Upgrades.level("radio") > 0 else 0])


## Что Михалыч сейчас предлагает: не взятые, не сданные, по уровню доверия.
static func offered() -> Array:
	var out: Array = []
	for m in all():
		var id := String(m.id)
		if Profile.missions_active.has(id) or id in Profile.missions_done:
			continue
		if Profile.trust_level() >= int(m.get("trust_level", 1)):
			out.append(m)
	return out


static func take(id: String) -> bool:
	if Profile.missions_active.size() >= slots() or find(id).is_empty():
		return false
	Profile.missions_active[id] = 0
	Profile.save()
	Audio.play_ui("quest")
	return true


## Нужно / сделано (для строки прогресса).
static func goal(m: Dictionary) -> int:
	match String(m.type):
		"visit", "extract_via":
			return 1
	return int(m.get("n", 1))


static func progress(id: String) -> int:
	var m := find(id)
	if String(m.get("type", "")) == "hand_in":
		# только найденное в рейде — купленное у Михалыча ему же не сдать
		return mini(Profile.stash_count(String(m.item), true), goal(m))
	return int(Profile.missions_active.get(id, 0))


static func done(id: String) -> bool:
	return Profile.missions_active.has(id) and progress(id) >= goal(find(id))


## Сдать: предметы (hand_in) уходят из тайника, награда — деньги и доверие.
static func turn_in(id: String) -> bool:
	if not done(id):
		return false
	var m := find(id)
	if String(m.type) == "hand_in":
		Profile.take_from_stash(String(m.item), goal(m), true)
	Profile.missions_active.erase(id)
	Profile.missions_done.append(id)
	Profile.money += int(m.reward.get("money", 0))
	Profile.trust += int(m.reward.get("trust", 0))
	Profile.save()
	Audio.play_ui("quest")
	return true


static func _bump(type: String, match_key: String, match_value: String, by: int) -> void:
	var changed := false
	for id in Profile.missions_active.keys():
		var m := find(String(id))
		if String(m.get("type", "")) != type:
			continue
		if match_key != "" and String(m.get(match_key, "")) != match_value:
			continue
		var cur := int(Profile.missions_active[id])
		var nxt := mini(cur + by, goal(m))
		if nxt != cur:
			Profile.missions_active[id] = nxt
			changed = true
	if changed:
		Profile.save()


# ---------------------------------------------------------------- события рейда (свой игрок)

static func on_kill() -> void:
	_bump("kill", "", "", 1)


static func on_visit(room_id: String) -> void:
	_bump("visit", "room", room_id, 1)


static func on_extract(exit_node: String) -> void:
	_bump("extract_via", "exit", exit_node, 1)
	_bump("survive", "", "", 1)


## Погиб — «выжить подряд» начинается заново.
static func on_death() -> void:
	for id in Profile.missions_active.keys():
		if String(find(String(id)).get("type", "")) == "survive":
			Profile.missions_active[id] = 0
	Profile.save()


## Строка для окна: «Расчистка — 2 / 3».
static func line(id: String) -> String:
	var m := find(id)
	return "%s — %d / %d" % [String(m.get("name", id)), progress(id), goal(m)]
