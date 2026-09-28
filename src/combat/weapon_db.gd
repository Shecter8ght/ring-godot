@tool
class_name WeaponDb
extends RefCounted
## Реестр арсенала (data/weapons.json, data/armor.json, data/loadouts.json; см.
## docs/design/weapons.md). Определения — здесь (шаблоны), состояние — в записи предмета:
##   оружие  {id, n, dur, mods: {точка: {id[, light, laser]}}, mag: {id, ammo, rounds}, sight}
##   магазин {id, n, ammo, rounds}
##   жилет   {id, n, dur (мягкая часть), plates: {front: {id, dur}, back: {...}}}
##   шлем / плита — {id, n, dur}
## Совместимость — только через интерфейсы (точка оружия → интерфейс, обвес → fits), без списков
## конкретного оружия: новое оружие с тем же интерфейсом сразу принимает весь подходящий обвес.

const WEAPONS_PATH := "res://data/weapons.json"
const ARMOR_PATH := "res://data/armor.json"
const LOADOUTS_PATH := "res://data/loadouts.json"
const WEAPON_SOUND_SLOTS_PATH := "res://data/weapon_sound_slots.json"

## Точки крепления в порядке показа.
const MOUNTS := ["optic_primary", "optic_offset", "muzzle", "underbarrel", "side_left", "side_right", "stock"]
const MOUNT_NAMES := {"optic_primary": "Прицел основной", "optic_offset": "Прицел угловой", "muzzle": "Дульное", "underbarrel": "Под цевьё",
	"side_left": "Сбоку слева", "side_right": "Сбоку справа", "stock": "Приклад"}
const CLASS_NAMES := {"PISTOL": "Пистолет", "SMG": "Пистолет-пулемёт", "PDW": "PDW", "SHOTGUN": "Ружьё", "ASSAULT_RIFLE": "Автомат", "CARBINE": "Карабин",
	"BATTLE_RIFLE": "Боевая винтовка", "DMR": "Марксманская", "SNIPER": "Снайперская", "SPECIAL": "Специальное", "LMG": "Пулемёт"}

static var _w: Dictionary = {}
static var _a: Dictionary = {}
static var _l: Dictionary = {}
static var _sound_slots: Array[Dictionary] = []
## Все предметы арсенала (id → словарь предмета) — их подмешивает ItemDb.
static var _items: Dictionary = {}
## id → вид предмета (weapon, ammo, mag, mod, vest, plate, helmet, headset) — для выборки лута.
static var _kind: Dictionary = {}
const _KIND := {"weapons": "weapon", "ammo": "ammo", "magazines": "mag", "attachments": "mod",
	"vests": "vest", "plates": "plate", "helmets": "helmet", "headsets": "headset"}


static func _ensure() -> void:
	if not _w.is_empty():
		return
	_w = JSON.parse_string(FileAccess.get_file_as_string(WEAPONS_PATH)) as Dictionary
	_a = JSON.parse_string(FileAccess.get_file_as_string(ARMOR_PATH)) as Dictionary
	_l = JSON.parse_string(FileAccess.get_file_as_string(LOADOUTS_PATH)) as Dictionary
	var sound_data: Variant = JSON.parse_string(FileAccess.get_file_as_string(WEAPON_SOUND_SLOTS_PATH))
	if sound_data is Dictionary:
		for raw in (sound_data as Dictionary).get("slots", []):
			if raw is Dictionary:
				_sound_slots.append(raw as Dictionary)
	for sec in ["weapons", "ammo", "magazines", "attachments"]:
		_items.merge(_w.get(sec, {}))
		for id in _w.get(sec, {}):
			_kind[id] = _KIND[sec]
	for sec in ["vests", "plates", "helmets", "headsets"]:
		_items.merge(_a.get(sec, {}))
		for id in _a.get(sec, {}):
			_kind[id] = _KIND[sec]


static func items() -> Dictionary:
	_ensure()
	return _items


## Старый id → новый (сохранения до арсенала).
static func canonical(id: String) -> String:
	_ensure()
	return String((_w.get("aliases", {}) as Dictionary).get(id, id))


static func aliases() -> Dictionary:
	_ensure()
	return _w.get("aliases", {})


# ---------------------------------------------------------------- определения

static func weapon(id: String) -> Dictionary:
	_ensure()
	return ((_w.weapons as Dictionary).get(canonical(id), {}) as Dictionary).get("weapon", {})


static func is_weapon(id: String) -> bool:
	return not weapon(id).is_empty()


## Все модели оружия в порядке данных. Стенд строит по этому списку карточки и автоматически
## подхватывает новые модели, когда у них появляется запись в weapons.json и иконка.
static func weapon_ids() -> Array[String]:
	_ensure()
	var out: Array[String] = []
	for id in _w.weapons:
		out.append(String(id))
	return out


## Собственные события одной модели. Пока у события нет своих записей, Audio идёт по fallback к
## прежнему общему набору — поэтому переход на помодельный звук не ломает существующее звучание.
static func weapon_sound_events(id: String = "") -> Array[Dictionary]:
	_ensure()
	var ids: Array[String] = weapon_ids()
	if id != "":
		ids.clear()
		ids.append(canonical(id))
	var out: Array[Dictionary] = []
	for wid in ids:
		var item: Dictionary = (_w.weapons as Dictionary).get(wid, {})
		var w: Dictionary = item.get("weapon", {})
		if w.is_empty():
			continue
		for raw in _sound_slots:
			if not _sound_slot_applies(raw, w):
				continue
			var slot := String(raw.id)
			var base_kind := "%s_%s" % [wid, "shot" if slot == "shot_far" else slot]
			var event := raw.duplicate(true)
			event.id = "%s_%s" % [wid, slot]
			event.kind = (base_kind + "@far") if slot == "shot_far" and bool(raw.wired) else (base_kind if bool(raw.wired) else "")
			event.file = "guns/%s_%s_" % [wid.trim_prefix("wpn_"), String(raw.file)]
			event.fallback = _weapon_sound_fallback(w, String(raw.fallback))
			event.weapon = wid
			event.slot = slot
			event.cat = "Оружие по моделям"
			event.name = "%s — %s" % [String(item.get("name", wid)), String(raw.name)]
			event.now = "свой набор модели; пока общий запасной"
			out.append(event)
	return out


## Вид Audio для слота; пусто означает, что у этой конструкции такого действия нет или оно пока
## только предусмотрено в стенде, но не вызывается механикой.
static func weapon_sound_kind(id: String, slot: String) -> String:
	for event in weapon_sound_events(id):
		if String(event.slot) == slot:
			return String(event.kind).trim_suffix("@far")
	return ""


static func weapon_sound_map(id: String) -> Dictionary:
	var out: Dictionary = {}
	for event in weapon_sound_events(id):
		var kind := String(event.kind)
		if kind != "" and not kind.ends_with("@far"):
			out[String(event.slot)] = kind
	return out


static func _sound_slot_applies(slot: Dictionary, w: Dictionary) -> bool:
	var condition := String(slot.get("condition", "all"))
	var internal := w.has("internal_mag")
	var action := String(w.get("action", ""))
	match condition:
		"suppressible":
			return bool((w.get("integral", {}) as Dictionary).get("suppressed", false)) or (w.get("mounts", {}) as Dictionary).has("muzzle")
		"detachable_mag":
			return not internal
		"internal_mag":
			return internal
		"manual_cycle":
			return String(w.get("cycle_sound", "")) != ""
		"break_action":
			return action == "break"
		"not_break_action":
			return action != "break"
		"automatic":
			return bool((w.get("stats", {}) as Dictionary).get("auto", false))
	return true


static func _weapon_sound_fallback(w: Dictionary, fallback: String) -> String:
	match fallback:
		"$shot":
			return String(w.get("sound", ""))
		"$shot_far":
			var shot := String(w.get("sound", ""))
			if shot.begins_with("shot_hg_") or shot == "shot_pistol":
				return "shot_pistol@far"
			if shot == "shot_smg":
				return "shot_smg@far"
			if shot == "shot_ak762":
				return "shot_ak762@far"
			if shot == "shot_shotgun":
				return "shot_shotgun@far"
			if shot == "shot_bolt":
				return "shot_bolt@far"
			return "shot_rifle@far"
		"$suppressed":
			if String(w.get("caliber", "")) == "9x39":
				return "shot_sup939"
			return "shot_pistol_sup" if String(w.get("class", "")) == "PISTOL" else "shot_rifle_sup"
		"$mechanism":
			return "mech_pistol" if String(w.get("class", "")) == "PISTOL" else "mech_rifle"
		"$reload":
			return String(w.get("reload_sound", "reload_rifle"))
		"$cycle":
			return String(w.get("cycle_sound", "bolt"))
	return fallback


static func ammo(id: String) -> Dictionary:
	_ensure()
	return ((_w.ammo as Dictionary).get(canonical(id), {}) as Dictionary).get("ammo", {})


static func magazine(id: String) -> Dictionary:
	_ensure()
	return ((_w.magazines as Dictionary).get(canonical(id), {}) as Dictionary).get("mag", {})


static func attachment(id: String) -> Dictionary:
	_ensure()
	return ((_w.attachments as Dictionary).get(canonical(id), {}) as Dictionary).get("attach", {})


static func caliber_name(cal: String) -> String:
	_ensure()
	return String(((_w.calibers as Dictionary).get(cal, {}) as Dictionary).get("name", cal))


static func model(key: String) -> Dictionary:
	_ensure()
	return (_w.models as Dictionary).get(key, {})


static func preset(id: String) -> Dictionary:
	_ensure()
	return (_w.presets as Dictionary).get(id, {})


static func presets() -> Dictionary:
	_ensure()
	return _w.presets


static func sandbox() -> Array:
	_ensure()
	return _w.get("sandbox", [])


static func vest(id: String) -> Dictionary:
	_ensure()
	return ((_a.vests as Dictionary).get(canonical(id), {}) as Dictionary).get("armor", {})


static func plate(id: String) -> Dictionary:
	_ensure()
	return ((_a.plates as Dictionary).get(canonical(id), {}) as Dictionary).get("plate", {})


static func helmet(id: String) -> Dictionary:
	_ensure()
	return ((_a.helmets as Dictionary).get(canonical(id), {}) as Dictionary).get("helmet", {})


static func headset(id: String) -> Dictionary:
	_ensure()
	return ((_a.headsets as Dictionary).get(canonical(id), {}) as Dictionary).get("headset", {})


static func loadout(id: String) -> Dictionary:
	_ensure()
	return (_l.loadouts as Dictionary).get(id, {})


static func loadouts() -> Dictionary:
	_ensure()
	return _l.loadouts


static func pmc_squad() -> Array:
	_ensure()
	return _l.get("pmc_squad", [])


## Все id раздела (weapons / ammo / magazines / attachments; vests / plates / helmets / headsets).
## Случайный предмет арсенала по фильтру — для таблиц лута ("pick:…"). Фильтр:
## "kind=ammo|mag; tags=POLICE|SCAV; tier=2; min_tier=1" — вид (weapon, ammo, mag, mod, vest,
## plate, helmet, headset; preset — готовая сборка оружия, вернёт "preset:<id>"), хотя бы один
## тег, тир не выше tier и не ниже min_tier. Вес — по редкости (Balance.LOOT_RARITY_W). "" — нет.
static func pick(query: String, rng: RandomNumberGenerator) -> String:
	var pool := matching(query)
	var total := 0.0
	for p in pool:
		total += float(p[1])
	var r := rng.randf() * total
	for p in pool:
		r -= float(p[1])
		if r <= 0.0:
			return String(p[0])
	return ""


## Всё, что проходит фильтр pick: [[id, вес], …].
static func matching(query: String) -> Array:
	_ensure()
	var q := {}
	for part in query.split(";", false):
		var kv := part.split("=", false, 1)
		if kv.size() == 2:
			q[kv[0].strip_edges()] = kv[1].strip_edges()
	var kinds := String(q.get("kind", "")).split("|", false)
	var tags := String(q.get("tags", "")).split("|", false)
	var tmax := int(q.get("tier", 9))
	var tmin := int(q.get("min_tier", 0))
	var presets := "preset" in kinds
	var src := {}
	if presets:
		for p in _w.get("presets", {}):
			src["preset:" + String(p)] = String((_w.presets[p] as Dictionary).weapon)
	else:
		for id in _items:
			src[id] = id
	var out: Array = []
	for key in src:
		var id := String(src[key])
		var it: Dictionary = _items.get(id, {})
		if it.is_empty() or (not presets and not kinds.is_empty() and not String(_kind.get(id, "")) in kinds):
			continue
		var t := int(it.get("tier", 1))
		if t > tmax or t < tmin:
			continue
		if not tags.is_empty():
			var hit := false
			for tg in it.get("tags", []):
				if String(tg) in tags:
					hit = true
					break
			if not hit:
				continue
		out.append([String(key), float(Balance.LOOT_RARITY_W.get(String(it.get("rarity", "common")), 1.0))])
	return out


static func ids(section: String) -> Array:
	_ensure()
	if _w.has(section):
		return (_w[section] as Dictionary).keys()
	return (_a.get(section, {}) as Dictionary).keys()


# ---------------------------------------------------------------- совместимость

## Точки крепления оружия: имя → интерфейс.
static func mounts_of(weapon_id: String) -> Dictionary:
	return weapon(weapon_id).get("mounts", {})


## Почему обвес att нельзя поставить в точку mount оружия entry ("" — можно). Проверки: точка
## есть, интерфейс подходит, точка не занята (кроме замены того же), не закрыта другим обвесом,
## и сам обвес не закрывает занятую точку.
static func attach_block(entry: Dictionary, mount: String, att: String) -> String:
	var a := attachment(att)
	if a.is_empty():
		return "это не обвес"
	var m := mounts_of(String(entry.id))
	if not m.has(mount):
		return "на этом оружии нет такой точки"
	if not String(m[mount]) in a.get("fits", []):
		return "не подходит крепление (%s)" % String(m[mount])
	var mods: Dictionary = entry.get("mods", {})
	for other in mods:
		if String(other) == mount:
			continue
		var oa := attachment(mod_id(mods[other]))
		if mount in oa.get("blocks", []):
			return "мешает: " + ItemDb.item_name(mod_id(mods[other]))
		if String(other) in a.get("blocks", []):
			return "закроет: " + ItemDb.item_name(mod_id(mods[other]))
	return ""


## Первая свободная точка, куда встаёт обвес ("" — некуда).
static func free_mount_for(entry: Dictionary, att: String) -> String:
	var mods: Dictionary = entry.get("mods", {})
	for mount in MOUNTS:
		if not mods.has(mount) and attach_block(entry, mount, att) == "":
			return mount
	return ""


## Все точки, куда обвес вообще встаёт (занятые тоже — для замены).
static func mounts_for(entry: Dictionary, att: String) -> Array:
	var out: Array = []
	var a := attachment(att)
	var m := mounts_of(String(entry.id))
	for mount in MOUNTS:
		if m.has(mount) and String(m[mount]) in a.get("fits", []):
			out.append(mount)
	return out


## id обвеса из значения точки (у старых записей — строка, у новых — словарь).
static func mod_id(v: Variant) -> String:
	if v is Dictionary:
		return canonical(String((v as Dictionary).get("id", "")))
	return canonical(String(v))


## Магазин подходит к оружию (интерфейс горловины).
static func mag_fits(weapon_id: String, mag_id: String) -> bool:
	var w := weapon(weapon_id)
	return w.has("mag_if") and String(magazine(mag_id).get("if", "-")) == String(w.mag_if)


## Патрон подходит к оружию / магазину (калибр).
static func ammo_fits(weapon_id: String, ammo_id: String) -> bool:
	return String(ammo(ammo_id).get("caliber", "-")) == String(weapon(weapon_id).get("caliber", "?"))


static func mag_caliber(mag_id: String) -> String:
	var iface := String(magazine(mag_id).get("if", ""))
	for wid in ids("weapons"):
		var w := weapon(String(wid))
		if String(w.get("mag_if", "")) == iface:
			return String(w.caliber)
	return ""


## Штатный магазин оружия; явный default_mag нужен платформам с общим интерфейсом и разной базовой ёмкостью.
static func default_mag(weapon_id: String) -> String:
	var w := weapon(weapon_id)
	if not w.has("mag_if"):
		return ""
	var preferred := canonical(String(w.get("default_mag", "")))
	if preferred != "" and mag_fits(weapon_id, preferred):
		return preferred
	for mid in ids("magazines"):
		if String(magazine(String(mid)).get("if", "")) == String(w.mag_if):
			return String(mid)
	return ""


## Вместимость магазина оружия: вставленного (или встроенного).
static func capacity(entry: Dictionary) -> int:
	var w := weapon(String(entry.id))
	if w.has("internal_mag"):
		return int(w.internal_mag)
	var mag: Dictionary = entry.get("mag", {})
	if mag.is_empty():
		return 0
	return int(magazine(String(mag.id)).get("capacity", 0))


## Патрон по умолчанию для калибра (первый обычный в данных).
static func default_ammo(caliber: String) -> String:
	for aid in ids("ammo"):
		if String(ammo(String(aid)).caliber) == caliber:
			return String(aid)
	return ""


# ---------------------------------------------------------------- экземпляры

## Оружие из пресета: обвес, магазин с патронами, износ, выбранный прицел.
static func make_weapon(preset_id: String, rng: RandomNumberGenerator, dur_range: Array = []) -> Dictionary:
	var p := preset(preset_id)
	if p.is_empty():
		return {}
	var wid := String(p.weapon)
	var e := {"id": wid, "n": 1}
	var dr: Array = dur_range if not dur_range.is_empty() else p.get("dur", [80, 100])
	e["dur"] = roundf(rng.randf_range(float(dr[0]), float(dr[1])))
	var mods := {}
	for mount in p.get("mods", {}):
		mods[String(mount)] = {"id": String(p.mods[mount])}
	e["mods"] = mods
	var ammo_id := pick_ammo(p.get("ammo", []), rng, String(weapon(wid).caliber))
	var cap := 0
	if weapon(wid).has("internal_mag"):
		cap = int(weapon(wid).internal_mag)
		e["mag"] = {"id": "", "ammo": ammo_id, "rounds": cap}
	else:
		var mid := String(p.get("mag", default_mag(wid)))
		cap = int(magazine(mid).get("capacity", 0))
		e["mag"] = {"id": mid, "ammo": ammo_id, "rounds": cap}
	e["sight"] = String(p.get("sight", "primary"))
	return e


## Патрон из смеси пресета [[id, доля], …]; пусто — штатный калибра.
static func pick_ammo(mix: Array, rng: RandomNumberGenerator, caliber: String) -> String:
	if mix.is_empty():
		return default_ammo(caliber)
	var total := 0.0
	for m in mix:
		total += float(m[1])
	var r := rng.randf() * total
	for m in mix:
		r -= float(m[1])
		if r <= 0.0:
			return String(m[0])
	return String(mix[0][0])


## Отдельный магазин (в рюкзак): снаряжён ammo_id на rounds патронов.
static func make_mag(mag_id: String, ammo_id: String, rounds: int) -> Dictionary:
	return {"id": mag_id, "n": 1, "ammo": ammo_id, "rounds": rounds}


## Жилет / плитоносец: мягкая часть с полной прочностью, плиты — по списку {гнездо: id}.
static func make_vest(id: String, plates: Dictionary = {}, wear: float = 1.0) -> Dictionary:
	var v := vest(id)
	var e := {"id": canonical(id), "n": 1}
	if v.get("soft") != null:
		e["dur"] = roundf(float((v.soft as Dictionary).durability) * wear)
	var ps := {}
	for slot in plates:
		var pid := String(plates[slot])
		if pid != "" and String(slot) in v.get("plates", []):
			ps[String(slot)] = {"id": pid, "dur": roundf(float(plate(pid).durability) * wear)}
	if not (v.get("plates", []) as Array).is_empty():
		e["plates"] = ps
	return e


# ---------------------------------------------------------------- миграция

## Запись из старого сохранения — к новому формату (id по алиасам, обвес по точкам, магазин,
## прочность оружия). Возвращает [запись, выпавшее] — что не встало (в тайник).
static func migrate(e: Dictionary) -> Array:
	var out: Dictionary = e.duplicate(true)
	var spill: Array = []
	out.id = canonical(String(out.id))
	var id := String(out.id)
	if is_weapon(id):
		if not out.has("dur"):
			out["dur"] = 100.0
		var old: Dictionary = out.get("mods", {})
		var mods := {}
		var old_mag := ""
		for k in old:
			var mid := mod_id(old[k])
			if String(k) in MOUNTS:
				mods[String(k)] = old[k] if old[k] is Dictionary else {"id": mid}
				continue
			# старые слоты: mag — магазин; остальное — в первую подходящую точку
			if not magazine(mid).is_empty():
				old_mag = mid
				continue
			var probe := out.duplicate(true)
			probe["mods"] = mods
			var mount := free_mount_for(probe, mid)
			if mount != "":
				mods[mount] = {"id": mid}
			else:
				spill.append({"id": mid, "n": 1})
		out["mods"] = mods
		if not out.has("mag") or not (out.mag is Dictionary):
			var w := weapon(id)
			var mg := old_mag if old_mag != "" and mag_fits(id, old_mag) else default_mag(id)
			if w.has("internal_mag"):
				mg = ""
			if old_mag != "" and mg != old_mag:
				spill.append({"id": old_mag, "n": 1})
			out["mag"] = {"id": mg, "ammo": default_ammo(String(w.caliber)), "rounds": 0}
		if not out.has("sight"):
			out["sight"] = "primary"
	elif not magazine(id).is_empty():
		if not out.has("rounds"):
			out["rounds"] = 0
			out["ammo"] = default_ammo(mag_caliber(id))
	elif not vest(id).is_empty():
		var v := vest(id)
		if v.get("soft") != null:
			var mx := float((v.soft as Dictionary).durability)
			out["dur"] = clampf(float(out.get("dur", mx)), 0.0, mx)
		elif out.has("dur"):
			out.erase("dur")
		if not (v.get("plates", []) as Array).is_empty() and not out.has("plates"):
			out["plates"] = {}
	elif not helmet(id).is_empty():
		var mx := float(helmet(id).durability)
		out["dur"] = clampf(float(out.get("dur", mx)), 0.0, mx)
	elif not plate(id).is_empty():
		if not out.has("dur"):
			out["dur"] = float(plate(id).durability)
	return [out, spill]
