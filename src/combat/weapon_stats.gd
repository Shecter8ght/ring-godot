class_name WeaponStats
extends RefCounted
## Характеристики ствола с обвесами — одно место расчёта: стрельба игрока, прицел, верстак.
## База — Balance.WEAPONS (+ ADS_SPREAD, ADS_FOV, ergo, zoom), обвесы — data/items.json → mod.fx:
##   kick, shake, spread, ads_spread, hip_spread, noise, damage — множители;
##   ergo — прибавка эргономики (очки 0–100); mag — прибавка магазина;
##   scoped / zoom — оптика (кратность); suppressed / db — глушитель; braced_* — сошки.
## Эргономика — отдельная механика: чем выше, тем быстрее ствол «доходит» в прицеле (aim_time)
## и тем меньше гуляет прицел (sway).

static var _cache: Dictionary = {}


static func compute(weapon_id: String, mods: Dictionary) -> Dictionary:
	var key := weapon_id + str(mods)
	if _cache.has(key):
		return _cache[key]
	var s: Dictionary = (Balance.WEAPONS[weapon_id] as Dictionary).duplicate()
	s.ads_spread = float(Balance.ADS_SPREAD.get(weapon_id, 0.5))
	s.hip_spread = 1.0
	s.ads_fov = float(Balance.ADS_FOV.get(weapon_id, 60.0))
	s.zoom = float(s.get("zoom", 0.0))
	s.scoped = s.zoom > 0.0
	s.suppressed = false
	s.db = 0.0
	s.braced_kick = 1.0
	s.braced_spread = 1.0
	s.ergo = float(s.get("ergo", 50.0))
	for slot in mods:
		var fx: Dictionary = (ItemDb.item(String(mods[slot])).get("mod", {}) as Dictionary).get("fx", {})
		s.kick = float(s.kick) * float(fx.get("kick", 1.0))
		s.kick_h = float(s.get("kick_h", 0.0)) * float(fx.get("kick", 1.0))
		s.shake = float(s.shake) * float(fx.get("shake", 1.0))
		s.spread_deg = float(s.spread_deg) * float(fx.get("spread", 1.0))
		s.ads_spread = float(s.ads_spread) * float(fx.get("ads_spread", 1.0))
		s.hip_spread = float(s.hip_spread) * float(fx.get("hip_spread", 1.0))
		s.noise_m = float(s.noise_m) * float(fx.get("noise", 1.0))
		s.damage = float(s.damage) * float(fx.get("damage", 1.0))
		s.mag = int(s.mag) + int(fx.get("mag", 0))
		s.ergo = float(s.ergo) + float(fx.get("ergo", 0.0))
		s.db = float(s.db) + float(fx.get("db", 0.0))
		s.braced_kick = float(s.braced_kick) * float(fx.get("braced_kick", 1.0))
		s.braced_spread = float(s.braced_spread) * float(fx.get("braced_spread", 1.0))
		if bool(fx.get("suppressed", false)):
			s.suppressed = true
		if bool(fx.get("scoped", false)):
			s.scoped = true
			s.zoom = float(fx.get("zoom", 4.0))
	s.ergo = clampf(float(s.ergo), 5.0, 100.0)
	var e := float(s.ergo) / 100.0
	s.aim_time = lerpf(Balance.AIM_TIME_SLOW, Balance.AIM_TIME_FAST, e)
	s.sway = lerpf(Balance.SWAY_MAX, Balance.SWAY_MIN, e)
	_cache[key] = s
	return s


## Для верстака: [(название, значение, шкала 0–100, больше — лучше?, формат)].
static func rows(s: Dictionary) -> Array:
	var dmg := float(s.damage) * int(s.pellets)
	return [
		["Урон", dmg, clampf(dmg, 0.0, 100.0), true, "%.0f"],
		["Скорострельность", 60.0 / float(s.interval), clampf(60.0 / float(s.interval) / 7.0, 0.0, 100.0), true, "%.0f выстр/мин"],
		["Точность от бедра", _acc(float(s.spread_deg) * float(s.hip_spread)), _acc(float(s.spread_deg) * float(s.hip_spread)), true, "%.0f"],
		["Точность в прицеле", _acc(float(s.spread_deg) * float(s.ads_spread)), _acc(float(s.spread_deg) * float(s.ads_spread)), true, "%.0f"],
		["Отдача", float(s.kick) * 1100.0, clampf(float(s.kick) * 1100.0, 0.0, 100.0), false, "%.0f"],
		["Эргономика", float(s.ergo), float(s.ergo), true, "%.0f"],
		["Шумность", float(s.noise_m), clampf(float(s.noise_m) / 1.3, 0.0, 100.0), false, "%.0f м"],
		["Дальность", float(s.range_m), clampf(float(s.range_m) / 1.7, 0.0, 100.0), true, "%.0f м"],
		["Магазин", float(s.mag), clampf(float(s.mag) * 2.0, 0.0, 100.0), true, "%.0f"],
		["Кратность", float(s.zoom) if s.scoped else 1.0, clampf(float(s.zoom) * 12.0, 0.0, 100.0) if s.scoped else 0.0, true, "%.0f×"],
	]


## Точность 0–100 из разброса в градусах.
static func _acc(spread_deg: float) -> float:
	return clampf(100.0 - spread_deg * 16.0, 0.0, 100.0)
