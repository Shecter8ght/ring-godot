class_name WeaponStats
extends RefCounted
## Итоговые характеристики оружия — одно место расчёта (стрельба игрока, прицел, ИИ, верстак, UI).
## Из экземпляра (запись предмета, см. WeaponDb): определение (data/weapons.json → weapon.stats)
## + магазин (вместимость, скорость перезарядки, эргономика, надёжность) + обвес (attach.fx:
## kick, kick_h, shake, spread, ads_spread, hip_spread, noise, damage, flash, aim — множители;
## ergo — прибавка; db, suppressed, braced_*) + активный прицел (кратность, довод, точность) +
## патрон (урон, пробитие, урон броне, дробь, дальность, кучность) + износ (разброс, задержки).
## Определение не меняется — всё считается заново (кэш по состоянию).
## Эргономика — время «довода» в прицел (aim_time) и раскачка (sway).

static var _cache: Dictionary = {}


## entry — запись оружия; ammo_id — каким патроном стреляем ("" — что в магазине).
static func compute(entry: Dictionary, ammo_id: String = "") -> Dictionary:
	if entry.is_empty() or not WeaponDb.is_weapon(String(entry.id)):
		return {}
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	var aid := ammo_id if ammo_id != "" else String(mag.get("ammo", ""))
	if ammo_id == "" and int(entry.get("chamber", 0)) > 0:
		aid = String(entry.get("chamber_ammo", aid))
	var dur := float(entry.get("dur", 100.0))
	var key := "%s|%s|%s|%s|%d|%s|%s" % [entry.id, str(entry.get("mods", {})), String(mag.get("id", "")), aid, int(dur / 5.0), active_sight(entry), laser_on(entry)]
	if _cache.has(key):
		return _cache[key]
	var wid := WeaponDb.canonical(String(entry.id))
	var w := WeaponDb.weapon(wid)
	var b: Dictionary = w.stats
	var s := {}
	s.sounds = WeaponDb.weapon_sound_map(wid)
	s.name = ItemDb.item_name(wid)
	s["class"] = String(w["class"])
	s.caliber = String(w.caliber)
	s.sound = String((s.sounds as Dictionary).get("shot", String(w.sound)))
	s.reload_sound = String((s.sounds as Dictionary).get("reload", String(w.reload_sound)))
	s.cycle_sound = String((s.sounds as Dictionary).get("cycle", String(w.cycle_sound)))
	s.interval = 60.0 / float(b.rpm)
	s.auto = bool(b.auto)
	s.reload = float(b.reload)
	s.reload_empty = float(b.get("reload_empty", b.reload))
	s.range_m = float(b.range)
	s.noise_m = float(b.noise)
	s.spread_deg = float(b.spread)
	s.ads_spread = float(b.ads_spread)
	s.hip_spread = 1.0
	s.ads_fov = float(b.ads_fov)
	s.kick = float(b.kick)
	s.kick_h = float(b.kick_h)
	s.kick_bias = float(b.kick_bias)
	s.recover = float(b.recover)
	s.shake = float(b.shake)
	s.ergo = float(b.ergo)
	s.suppressed = false
	s.db = 0.0
	s.flash = 1.0
	s.braced_kick = 1.0
	s.braced_spread = 1.0
	s.aim_k = 1.0
	s.zoom = 0.0
	s.scoped = false
	# патрон
	var a := WeaponDb.ammo(aid) if aid != "" else {}
	if a.is_empty():
		aid = WeaponDb.default_ammo(String(w.caliber))
		a = WeaponDb.ammo(aid)
	s.ammo = aid
	s.damage = float(a.get("damage", 20.0))
	s.pen = float(a.get("pen", 10.0))
	s.armor_dmg = float(a.get("armor_dmg", 10.0))
	s.pellets = int(a.get("pellets", 1))
	# дальность и спад урона/пробития — по классу оружия (Balance.BALLISTICS), пуля ружья — своя
	var bal: Dictionary = Balance.BALLISTICS.get(String(w["class"]), {})
	if not bal.is_empty():
		s.range_m = float(bal.range)
		var fo: Dictionary = Balance.SHOTGUN_SLUG if String(w["class"]) == "SHOTGUN" and int(s.pellets) == 1 else bal
		s.falloff = [float(fo.eff), float(fo.dmg_min), float(fo.pen_min)]
	else:
		s.falloff = []
	s.point_blank = [float(Balance.SHOTGUN_POINT_BLANK.pb_m), float(Balance.SHOTGUN_POINT_BLANK.pb_k)] if String(w["class"]) == "SHOTGUN" and int(s.pellets) > 1 else []
	s.range_m = float(s.range_m) * float(a.get("range_k", 1.0))
	if int(s.pellets) == 1:
		s.spread_deg = float(s.spread_deg) * float(a.get("accuracy", 1.0))
	# магазин
	s.mag = WeaponDb.capacity(entry)
	var jam_k := 1.0
	var md := WeaponDb.magazine(String(mag.get("id", "")))
	if not md.is_empty():
		s.reload = float(s.reload) * float(md.get("reload_k", 1.0))
		s.reload_empty = float(s.reload_empty) * float(md.get("reload_k", 1.0))
		s.ergo = float(s.ergo) + float(md.get("ergo", 0.0))
		jam_k *= 1.0 + (1.0 - float(md.get("reliability", 1.0))) * 10.0
	# встроенное: прицел (болтовки), глушитель
	var integ: Dictionary = w.get("integral", {})
	if integ.has("zoom"):
		s.zoom = float(integ.zoom)
		s.scoped = true
	if bool(integ.get("suppressed", false)):
		s.suppressed = true
		s.db = float(integ.get("db", -14.0))
		s.noise_m = float(s.noise_m) * 0.35
		s.flash = 0.0
	# обвес
	var active := active_sight(entry)
	s.sights = sights_of(entry)
	s.sight = active
	s.laser = false
	s.light = false
	var mods: Dictionary = entry.get("mods", {})
	for mount in mods:
		var att := WeaponDb.attachment(WeaponDb.mod_id(mods[mount]))
		if att.is_empty():
			continue
		var fx: Dictionary = att.get("fx", {})
		var is_optic := String(mount).begins_with("optic_")
		# прицел действует, только когда через него смотрят; эргономика (вес) — всегда
		if is_optic and String(mount) != "optic_" + active:
			s.ergo = float(s.ergo) + float(fx.get("ergo", 0.0))
			continue
		s.kick = float(s.kick) * float(fx.get("kick", 1.0))
		s.kick_h = float(s.kick_h) * float(fx.get("kick_h", fx.get("kick", 1.0)))
		s.shake = float(s.shake) * float(fx.get("shake", 1.0))
		s.spread_deg = float(s.spread_deg) * float(fx.get("spread", 1.0))
		s.ads_spread = float(s.ads_spread) * float(fx.get("ads_spread", 1.0))
		s.hip_spread = float(s.hip_spread) * float(fx.get("hip_spread", 1.0))
		s.noise_m = float(s.noise_m) * float(fx.get("noise", 1.0))
		s.damage = float(s.damage) * float(fx.get("damage", 1.0))
		s.ergo = float(s.ergo) + float(fx.get("ergo", 0.0))
		s.db = float(s.db) + float(fx.get("db", 0.0))
		s.flash = float(s.flash) * float(fx.get("flash", 1.0))
		s.aim_k = float(s.aim_k) * float(fx.get("aim", 1.0))
		s.braced_kick = float(s.braced_kick) * float(fx.get("braced_kick", 1.0))
		s.braced_spread = float(s.braced_spread) * float(fx.get("braced_spread", 1.0))
		if bool(fx.get("suppressed", false)):
			s.suppressed = true
		if is_optic:
			s.aim_k = float(s.aim_k) * float(att.get("aim_k", 1.0))
			if float(att.get("zoom", 0.0)) > 0.0:
				s.zoom = float(att.zoom)
				s.scoped = true
			elif String(mount) == "optic_offset":
				# угловой коллиматор: основной (оптика) не работает, пока смотришь в угловой
				s.zoom = 0.0
				s.scoped = false
		if att.has("light"):
			s.light = true
		var st: Dictionary = mods[mount] if mods[mount] is Dictionary else {}
		if att.has("laser") and bool(st.get("laser", false)):
			s.laser = true
			s.hip_spread = float(s.hip_spread) * float((att.laser as Dictionary).get("hip_spread", 1.0))
	# Запись глушителя — не просто прежний выстрел тише. Пока своей записи нет, Audio возьмёт
	# обычный набор как запасной; после одобрения стенд подхватит suppressed-префикс сам.
	if bool(s.suppressed):
		s.sound = String((s.sounds as Dictionary).get("shot_suppressed", s.sound))
	# угловой — без кратности, даже если у ствола встроенная оптика
	if active == "offset":
		s.zoom = 0.0
		s.scoped = false
	# износ: разброс растёт, задержки чаще (на хорошем стволе — редкость)
	var worn := pow(clampf((100.0 - dur) / 100.0, 0.0, 1.0), 2.0)
	s.spread_deg = float(s.spread_deg) * (1.0 + worn * float(Balance.WEAPON_WEAR.spread))
	s.jam = (1.0 - float(b.reliability)) * float(Balance.WEAPON_WEAR.jam_base) * (1.0 + worn * float(Balance.WEAPON_WEAR.jam_worn)) * jam_k
	s.wear = float(b.get("wear", 0.02))
	s.dur = dur
	s.weight = ItemDb.entry_weight(entry)
	s.ergo = clampf(float(s.ergo), 5.0, 100.0)
	var e := float(s.ergo) / 100.0
	s.aim_time = lerpf(Balance.AIM_TIME_SLOW, Balance.AIM_TIME_FAST, e) / maxf(float(s.aim_k), 0.1)
	s.sway = lerpf(Balance.SWAY_MAX, Balance.SWAY_MIN, e)
	if bool(s.scoped):
		s.ads_fov = Balance.SCOPE_MAIN_FOV
	# изометрия: оптика — приближение камеры в прицеле, коллиматор — без
	s.iso_zoom = 1.0 + (minf(float(s.zoom), 8.0) * float(Balance.ISO_AIM.zoom_per_x) if bool(s.scoped) else 0.0)
	_cache[key] = s
	return s


## Какие прицелы есть: "primary" (основной, встроенный или открытый), "offset" (угловой). Основного
## нет, а угловой есть — только угловой.
static func sights_of(entry: Dictionary) -> Array:
	var mods: Dictionary = entry.get("mods", {})
	var w := WeaponDb.weapon(String(entry.id))
	var out: Array = []
	var integral := (w.get("integral", {}) as Dictionary).has("zoom")
	if mods.has("optic_primary") or integral or not mods.has("optic_offset"):
		out.append("primary")
	if mods.has("optic_offset"):
		out.append("offset")
	return out


## Выбранный прицел (сохраняется на экземпляре); нет такого — первый из доступных.
static func active_sight(entry: Dictionary) -> String:
	var sights := sights_of(entry)
	var s := String(entry.get("sight", "primary"))
	return s if s in sights else String(sights[0])


## Включён ли какой-нибудь ЛЦУ.
static func laser_on(entry: Dictionary) -> bool:
	var mods: Dictionary = entry.get("mods", {})
	for m in mods:
		if mods[m] is Dictionary and bool((mods[m] as Dictionary).get("laser", false)) and WeaponDb.attachment(WeaponDb.mod_id(mods[m])).has("laser"):
			return true
	return false


## Для верстака и карточки: [(название, значение, шкала 0–100, больше — лучше?, формат)].
static func rows(s: Dictionary) -> Array:
	var dmg := float(s.damage) * int(s.pellets)
	return [
		["Урон", dmg, clampf(dmg, 0.0, 100.0), true, "%.0f"],
		["Пробитие", float(s.pen), clampf(float(s.pen) * 1.6, 0.0, 100.0), true, "%.0f"],
		["Скорострельность", 60.0 / float(s.interval), clampf(60.0 / float(s.interval) / 9.0, 0.0, 100.0), true, "%.0f выстр/мин"],
		["Точность от бедра", _acc(float(s.spread_deg) * float(s.hip_spread)), _acc(float(s.spread_deg) * float(s.hip_spread)), true, "%.0f"],
		["Точность в прицеле", _acc(float(s.spread_deg) * float(s.ads_spread)), _acc(float(s.spread_deg) * float(s.ads_spread)), true, "%.0f"],
		["Отдача верт.", float(s.kick) * 1100.0, clampf(float(s.kick) * 1100.0, 0.0, 100.0), false, "%.0f"],
		["Отдача гориз.", float(s.kick_h) * 3000.0, clampf(float(s.kick_h) * 3000.0, 0.0, 100.0), false, "%.0f"],
		["Эргономика", float(s.ergo), float(s.ergo), true, "%.0f"],
		["Шумность", float(s.noise_m), clampf(float(s.noise_m) / 1.3, 0.0, 100.0), false, "%.0f м"],
		["Дальность", float(s.range_m), clampf(float(s.range_m) / 1.9, 0.0, 100.0), true, "%.0f м"],
		["Магазин", float(s.mag), clampf(float(s.mag) * 1.6, 0.0, 100.0), true, "%.0f"],
		["Кратность", float(s.zoom) if s.scoped else 1.0, clampf(float(s.zoom) * 8.0, 0.0, 100.0) if s.scoped else 0.0, true, "%.0f×"],
		["Вес", float(s.weight), clampf(float(s.weight) * 14.0, 0.0, 100.0), false, "%.1f кг"],
		["Состояние", float(s.dur), float(s.dur), true, "%.0f%%"],
	]


## Точность 0–100 из разброса в градусах.
static func _acc(spread_deg: float) -> float:
	return clampf(100.0 - spread_deg * 16.0, 0.0, 100.0)
