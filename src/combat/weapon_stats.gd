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
	var key := "%s|%s|%s|%s|%.4f|%s|%s" % [entry.id, str(entry.get("mods", {})), String(mag.get("id", "")), aid, dur, active_sight(entry), laser_on(entry)]
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
	s.sound = String((s.sounds as Dictionary).get("shot", ""))
	s.reload_sound = String((s.sounds as Dictionary).get("reload", ""))
	s.cycle_sound = String((s.sounds as Dictionary).get("cycle", ""))
	s.interval = 60.0 / float(b.rpm)
	s.auto = bool(b.auto)
	s.reload = float(b.reload)
	s.reload_empty = float(b.get("reload_empty", b.reload))
	s.range_m = float(b.range)
	s.noise_m = float(b.noise)
	s.spread_deg = float(b.spread)
	s.ads_spread = float(b.ads_spread)
	s.hip_spread = 1.0
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
	s.zoom_min = 0.0
	s.zoom_max = 0.0
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
		s.zoom = zoom_value(integ)
		s.zoom_min = zoom_limits(integ).x
		s.zoom_max = zoom_limits(integ).y
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
		var st: Dictionary = WeaponCondition.mod_entry(mods[mount])
		var effectiveness: float = WeaponCondition.effectiveness(st)
		var fx: Dictionary = (att.get("fx", {}) as Dictionary).duplicate(true)
		for effect: String in ["kick", "kick_h", "shake", "spread", "ads_spread", "hip_spread", "noise", "damage", "flash", "aim", "braced_kick", "braced_spread"]:
			if fx.has(effect):
				fx[effect] = lerpf(1.0, float(fx[effect]), effectiveness)
		fx["db"] = float(fx.get("db", 0.0)) * effectiveness
		if float(fx.get("ergo", 0.0)) > 0.0:
			fx["ergo"] = float(fx.ergo) * effectiveness
		var is_optic: bool = WeaponDb.is_optic(WeaponDb.mod_id(mods[mount]))
		# прицел действует, только когда через него смотрят; эргономика (вес) — всегда
		if is_optic and String(mount) != sight_mount(active, entry):
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
		if bool(fx.get("suppressed", false)) and effectiveness > 0.0:
			s.suppressed = true
		if is_optic and effectiveness > 0.0:
			s.aim_k = float(s.aim_k) * lerpf(1.0, float(att.get("aim_k", 1.0)), effectiveness)
			if float(att.get("zoom", 0.0)) > 0.0:
				s.zoom = zoom_value(att, st)
				s.zoom_min = zoom_limits(att).x
				s.zoom_max = zoom_limits(att).y
				s.scoped = true
			elif active != "primary":
				# угловой коллиматор: основной (оптика) не работает, пока смотришь в угловой
				s.zoom = 0.0
				s.zoom_min = 0.0
				s.zoom_max = 0.0
				s.scoped = false
		if att.has("light") and effectiveness > 0.0:
			s.light = true
		if att.has("laser") and bool(st.get("laser", false)) and effectiveness > 0.0:
			s.laser = true
			s.hip_spread = float(s.hip_spread) * lerpf(1.0, float((att.laser as Dictionary).get("hip_spread", 1.0)), effectiveness)
	# Глушитель использует только своё назначение. Без него — тишина.
	if bool(s.suppressed):
		s.sound = String((s.sounds as Dictionary).get("shot_suppressed", ""))
	# угловой — без кратности, даже если у ствола встроенная оптика
	if active != "primary":
		s.zoom = 0.0
		s.zoom_min = 0.0
		s.zoom_max = 0.0
		s.scoped = false
	# износ: разброс растёт, задержки чаще (на хорошем стволе — редкость)
	var worn := pow(clampf((100.0 - dur) / 100.0, 0.0, 1.0), 2.0)
	s.spread_deg = float(s.spread_deg) * (1.0 + worn * float(Balance.WEAPON_WEAR.spread))
	s.jam = (1.0 - float(b.reliability)) * float(Balance.WEAPON_WEAR.jam_base) * (1.0 + worn * float(Balance.WEAPON_WEAR.jam_worn)) * jam_k
	s.wear = float(b.get("wear", 0.02))
	s.dur = dur
	s.broken = WeaponCondition.broken(entry)
	s.weight = ItemDb.entry_weight(entry)
	s.ergo = clampf(float(s.ergo), 5.0, 100.0)
	var e := float(s.ergo) / 100.0
	s.aim_time = lerpf(Balance.AIM_TIME_SLOW, Balance.AIM_TIME_FAST, e) / maxf(float(s.aim_k), 0.1)
	s.sway = lerpf(Balance.SWAY_MAX, Balance.SWAY_MIN, e)
	# изометрия: оптика — приближение камеры в прицеле, коллиматор — без
	s.iso_zoom = 1.0 + (minf(float(s.zoom), 8.0) * float(Balance.ISO_AIM.zoom_per_x) if bool(s.scoped) else 0.0)
	if _cache.size() >= int(Balance.CONDITION.cache_entries):
		_cache.clear()
	_cache[key] = s
	return s


## Без диапазона кратность фиксированная. zoom — прежнее умолчание для старых экземпляров.
static func zoom_limits(optic: Dictionary) -> Vector2:
	var nominal: float = maxf(0.0, float(optic.get("zoom", 0.0)))
	if nominal <= 0.0:
		return Vector2.ZERO
	var low: float = maxf(1.0, float(optic.get("zoom_min", nominal)))
	return Vector2(low, maxf(low, float(optic.get("zoom_max", nominal))))


static func zoom_value(optic: Dictionary, state: Dictionary = {}) -> float:
	var limits: Vector2 = zoom_limits(optic)
	if limits == Vector2.ZERO:
		return 0.0
	var selected: float = float(state.get("zoom", optic.get("zoom", limits.x)))
	if not is_finite(selected):
		selected = float(optic.get("zoom", limits.x))
	return clampf(selected, limits.x, limits.y)


## Выбор кратности каждого регулируемого прицела хранится на самом обвесе.
static func scope_zooms(entry: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	var mods: Dictionary = entry.get("mods", {})
	for mount: Variant in mods:
		var optic: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods[mount]))
		var limits: Vector2 = zoom_limits(optic)
		if limits.y > limits.x:
			out[mount] = zoom_value(optic, WeaponCondition.mod_entry(mods[mount]))
	return out


## Эхо владельца: только существующие регулируемые прицелы, в пределах их диапазона.
static func apply_scope_zooms(entry: Dictionary, selections: Dictionary) -> void:
	var mods: Dictionary = entry.get("mods", {})
	for mount: Variant in selections:
		if not mods.has(mount) or not (selections[mount] is float or selections[mount] is int):
			continue
		var rec: Dictionary = WeaponCondition.mod_entry(mods[mount])
		var optic: Dictionary = WeaponDb.attachment(String(rec.id))
		var limits: Vector2 = zoom_limits(optic)
		if limits.y > limits.x:
			rec["zoom"] = zoom_value(optic, {"zoom": selections[mount]})
			mods[mount] = rec
	entry["mods"] = mods


## Основной и все дополнительные прицелы сборки (на кронштейнах, боковых планках, второй на
## планке) — порядок и правила в WeaponBuild.sights. Фонарь/ЛЦУ в боковом слоте не прицел.
static func sights_of(entry: Dictionary) -> Array:
	return WeaponBuild.sights(entry)


## Имя режима на экземпляре → путь точки крепления (у основного — его ключ в сборке entry).
static func sight_mount(sight: String, entry: Dictionary = {}) -> String:
	if sight != "primary":
		return sight
	var main: String = WeaponBuild.primary_key(entry.get("mods", {}))
	return main if main != "" else "optic_primary"


## Подпись прицела для подсказок: основной, слева/справа на боковой планке, угловой на кронштейне.
static func sight_name(sight: String, entry: Dictionary = {}) -> String:
	if sight == "primary":
		return "Основной"
	var base: String = WeaponBuild.base_of(sight)
	if WeaponBuild.depth(sight) == 0:
		return String({"side_left": "Слева", "side_right": "Справа", "offset": "Угловой"}.get(base, "Дополнительный"))
	var mods: Dictionary = entry.get("mods", {})
	if mods.is_empty():
		return "Угловой"
	var roll: float = WeaponBuild.point_roll(WeaponBuild.model_of(String(entry.get("id", ""))), mods, sight)
	if is_zero_approx(roll):
		return "Дополнительный"
	return "Угловой " + ("справа" if roll > 0.0 else "слева")


## Выбранный прицел (сохраняется на экземпляре); нет такого — первый из доступных.
static func active_sight(entry: Dictionary) -> String:
	var sights := sights_of(entry)
	var s := String(entry.get("sight", "primary"))
	if s == "offset":
		# старое сохранение: «угловой» — первый прицел на кронштейне с креном
		var model_key: String = WeaponBuild.model_of(String(entry.get("id", "")))
		for k: Variant in sights:
			if WeaponBuild.depth(String(k)) > 0 and not is_zero_approx(WeaponBuild.point_roll(model_key, entry.get("mods", {}), String(k))):
				return String(k)
	return s if s in sights else String(sights[0])


## Включён ли какой-нибудь ЛЦУ.
static func laser_on(entry: Dictionary) -> bool:
	var mods: Dictionary = entry.get("mods", {})
	for m in mods:
		if mods[m] is Dictionary and not WeaponCondition.broken(mods[m]) and bool((mods[m] as Dictionary).get("laser", false)) and WeaponDb.attachment(WeaponDb.mod_id(mods[m])).has("laser"):
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
		["Точность в прицеле", _acc(ads_spread_deg(s)), _acc(ads_spread_deg(s)), true, "%.0f"],
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


## Разброс через прицел, град: одной пулей — доля Balance.ADS_SPREAD_K от прицельного (0 — пуля идёт
## точно по линии прицеливания), дробь — прицельный разброс ствола (как в Player.shot_spread).
static func ads_spread_deg(s: Dictionary) -> float:
	var k: float = Balance.ADS_SPREAD_K if int(s.pellets) <= 1 else 1.0
	return float(s.spread_deg) * float(s.ads_spread) * k


## Точность 0–100 из разброса в градусах.
static func _acc(spread_deg: float) -> float:
	return clampf(100.0 - spread_deg * 16.0, 0.0, 100.0)
