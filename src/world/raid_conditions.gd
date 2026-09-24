class_name RaidConditions
extends RefCounted
## Условия рейда: время (день / закат / ночь), погода (ясно / дождь / туман / жара), электричество
## в ТЦ (есть / нет / аварийное). Игрок выбирает их у лестницы в убежище (Profile.next_conditions)
## — тяжелее условия, больше риск: лучше лут и доплата Михалыча. В коопе условия хоста приходят
## всем при старте уровня (Net.start_level). Значения и риск — Balance.RAID_TIME / _WEATHER / _POWER.
## Применяет их на уровне RaidAtmosphere.

const DEFAULT := {"time": "dusk", "weather": "clear", "power": "on"}

## Условия идущего рейда (выставляет уровень при загрузке).
static var current: Dictionary = DEFAULT.duplicate()
## Пришли от хоста вместе с командой «на уровень» — главнее своих.
static var from_host: Dictionary = {}


## Условия для рейда, который сейчас начнётся: от хоста / из убежища / по умолчанию (тесты).
static func for_new_raid() -> Dictionary:
	if not from_host.is_empty():
		return normalized(from_host)
	if Profile.pending_raid:
		return normalized(Profile.next_conditions)
	return DEFAULT.duplicate()


static func normalized(c: Dictionary) -> Dictionary:
	var out := DEFAULT.duplicate()
	for k in out:
		var v := String(c.get(k, out[k]))
		if (_table(k) as Dictionary).has(v):
			out[k] = v
	return out


static func _table(axis: String) -> Dictionary:
	match axis:
		"time":
			return Balance.RAID_TIME
		"weather":
			return Balance.RAID_WEATHER
	return Balance.RAID_POWER


static func spec(axis: String, c: Dictionary = current) -> Dictionary:
	return _table(axis).get(String(c.get(axis, DEFAULT[axis])), {})


static func risk(c: Dictionary = current) -> int:
	var r := 0
	for axis in ["time", "weather", "power"]:
		r += int(spec(axis, c).get("risk", 0))
	return r


## Шанс лишнего броска в контейнере (лучше лут за риск).
static func loot_bonus(c: Dictionary = current) -> float:
	return minf(0.8, float(risk(c)) * Balance.RISK_LOOT_BONUS)


## Доплата Михалыча за риск: доля ценности вынесенного.
static func pay_bonus(c: Dictionary = current) -> float:
	return float(risk(c)) * Balance.RISK_PAY_BONUS


## Одной строкой: «Ночь · Дождь · Электричества нет».
static func title(c: Dictionary = current) -> String:
	return "%s · %s · %s" % [String(spec("time", c).name), String(spec("weather", c).name), String(spec("power", c).name)]


## Что это значит для игрока (подсказки к сборам).
static func hints(c: Dictionary = current) -> Array[String]:
	var out: Array[String] = []
	var dark := String(c.time) == "night" or String(c.power) != "on"
	if dark:
		out.append("Темно: фонарь на оружии или ПНВ. Фонарь выдаёт тебя издалека.")
	if String(c.power) == "emergency":
		out.append("Аварийное освещение: коридоры видно, магазины — в темноте.")
	if String(c.power) == "off":
		out.append("Нет питания: ворота и двери на электричестве закрыты.")
	match String(c.weather):
		"rain":
			out.append("Дождь: слышно хуже — и тебя, и их. Может начаться прямо в рейде.")
		"fog":
			out.append("Туман: видно недалеко всем. Снайперы без дела.")
		"heat":
			out.append("Жара: на улице пересвечено — очки от солнца; устаёшь быстрее.")
	return out


static func random(rng: RandomNumberGenerator) -> Dictionary:
	var out := {}
	for axis in ["time", "weather", "power"]:
		var keys: Array = _table(axis).keys()
		out[axis] = String(keys[rng.randi_range(0, keys.size() - 1)])
	return out
