class_name Floors
extends RefCounted
## Этажи ТЦ, зоны и маршруты заброски (data/floors.json). Этаж = отдельная карта; внутри здания этажи
## отрезаны друг от друга, поэтому у каждого — свой путь снаружи, и выбор этажа в убежище — это
## выбор маршрута. Маршрут открывает торговец: нужно его доверие (Profile.trust, растёт за удачные
## эвакуации) и разовая плата за наводку. Что открыто и что выбрано — в профиле; общедоступные
## маршруты помечены available_by_default в данных, поэтому не требуют миграции сохранений.

const PATH := "res://data/floors.json"

static var _floors: Array = []


static func all() -> Array:
	if _floors.is_empty():
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
		if d is Dictionary:
			_floors = (d as Dictionary).get("floors", [])
			for route: Dictionary in _floors:
				var prices: Dictionary = Balance.FLOOR_PRICES.get(String(route.id), {})
				route["price"] = int(prices.get("price", 0))
				route["fee"] = int(prices.get("fee", 0))
	return _floors


static func find(id: String) -> Dictionary:
	for f in all():
		if String(f.id) == id:
			return f
	return {}


## Сцена этажа; этаж не собран или не найден — первый этаж.
static func scene(id: String) -> String:
	var s := String(find(id).get("scene", ""))
	return s if s != "" else String(find("f1").get("scene", Balance.RAID_SCENE))


static func built(id: String) -> bool:
	return String(find(id).get("scene", "")) != ""


## Маршрут сцены, которую передал хост; тестовые сцены могут не быть в списке.
static func id_for_scene(scene_path: String) -> String:
	if scene_path == "":
		return ""
	for f: Dictionary in all():
		if String(f.get("scene", "")) == scene_path:
			return String(f.id)
	return ""


static func is_open(id: String) -> bool:
	var f: Dictionary = find(id)
	return not f.is_empty() and (bool(f.get("available_by_default", false)) or id in Profile.floors_open)


## Явный выбор игрока сохраняем в существующем формате: Profile при загрузке проверяет floors_open.
static func select(id: String) -> bool:
	Profile.ensure()
	if not is_open(id):
		return false
	Profile.floor = id
	if not id in Profile.floors_open:
		Profile.floors_open.append(id)
	Profile.save()
	return true


## Почему маршрут пока нельзя открыть ("" — можно).
static func unlock_block(id: String) -> String:
	var f := find(id)
	if f.is_empty() or is_open(id):
		return ""
	if Profile.trust_step() < int(f.trust):
		return "доверие Михалыча: ступень %d из %d" % [Profile.trust_step(), int(f.trust)]
	if Profile.money < int(f.price):
		return "не хватает денег"
	return ""


## Открыть маршрут: доверие хватает — платим за наводку, маршрут в профиле навсегда.
static func unlock(id: String) -> bool:
	var f := find(id)
	if f.is_empty() or is_open(id) or unlock_block(id) != "":
		return false
	Profile.money -= int(f.price)
	Profile.floors_open.append(id)
	Profile.save()
	return true


## Выход по маршруту: этаж открыт, собран и хватает на плату за вылет (если она есть).
static func start_block(id: String) -> String:
	var f := find(id)
	if not is_open(id):
		return "маршрут закрыт"
	if not built(id):
		return "этаж ещё не собран"
	if Profile.money < int(f.get("fee", 0)):
		return "не хватает на вылет"
	return ""


## Списать плату за выход (вертолёт) — перед сменой сцены.
static func pay_fee(id: String) -> void:
	var fee := int(find(id).get("fee", 0))
	if fee > 0:
		Profile.money -= fee
		Profile.save()
