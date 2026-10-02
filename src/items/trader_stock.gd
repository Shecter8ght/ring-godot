class_name TraderStock
extends RefCounted
## Ассортимент Михалыча (data/trader.json, собирается tools/gen_trader_catalogs.py): пять
## каталогов, каждый открывается на своей ступени доверия (каждые Balance.TRUST_STEPS.catalog_every
## ступеней — новый). Предмет — в одном каталоге; цена растёт с каталогом
## (Balance.TRADER_CATALOG_MULT). Снаряжения ЧВК «Периметр» в каталогах нет — только с тел.

const PATH := "res://data/trader.json"

static var _d: Dictionary = {}


static func data() -> Dictionary:
	if _d.is_empty():
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
		_d = v if v is Dictionary else {}
	return _d


static func stock() -> Array:
	return data().get("stock", [])


## Каталог предмета (1–5); нет в ассортименте — 0.
static func catalog_of(id: String) -> int:
	return int((data().get("catalog", {}) as Dictionary).get(WeaponDb.canonical(id), 0))


static func catalogs() -> Array:
	return data().get("catalogs", [])


## С какой ступени доверия открыт каталог n.
static func step_of(n: int) -> int:
	for c in catalogs():
		if int(c.n) == n:
			return int(c.step)
	return 1 + (n - 1) * int(Balance.TRUST_STEPS.catalog_every)


static func catalog_name(n: int) -> String:
	for c in catalogs():
		if int(c.n) == n:
			return String(c.name)
	return "каталог %d" % n
