extends Node
## Цены v0: всё покрыто, покупка/разбор/продажа не приносит прибыли, общие пути закупки,
## цены улучшений и сохранение старого имущества. Только отдельный тестовый профиль.

var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://economy_prices_test.json", true)
	Settings.shop_loot = true
	Settings.unlock_all = false
	Settings.all_weapons = false
	var snapshot: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://docs/design/economy_current.json"))
	var table: FileAccess = FileAccess.open("res://docs/design/economy_prices_v0.tsv", FileAccess.READ)
	table.get_csv_line("\t")
	var count: int = 0
	var bad: Array[String] = []
	while not table.eof_reached():
		var row: PackedStringArray = table.get_csv_line("\t")
		if row.size() < 9:
			continue
		var id: String = row[0].trim_prefix("\ufeff")
		var purchase: int = int(row[6])
		var sale: int = int(row[8])
		Profile.stash.clear()
		Profile.money = purchase
		var bought: bool = Profile.buy(id, 1, "stash", false)
		if not bought or Profile.money != 0 or Profile.stash.is_empty():
			bad.append(id + ": покупка")
			continue
		var entry: Dictionary = Profile.stash[0]
		var whole: int = Profile.sell_price(entry)
		var parts: int = _parts_sale(entry)
		if Profile.buy_price(id) != purchase or absi(whole - sale) > 1 or whole > purchase or parts > purchase:
			bad.append("%s: купить %d/%d, продать %d/%d, частями %d" % [id, Profile.buy_price(id), purchase, whole, sale, parts])
		if not Profile.sell(0, 1) or Profile.money != whole or not Profile.stash.is_empty():
			bad.append(id + ": продажа")
		count += 1
	_check("все товары куплены и проданы по v0, целиком и частями без прибыли", count == Balance.TRADER_BUY_PRICES.size() and bad.is_empty(), "%d товаров; %s" % [count, str(bad)])
	var missing: Array[String] = []
	for raw: Variant in ItemDb.all_ids():
		var id: String = String(raw)
		if id != WeaponDb.canonical(id):
			continue
		var cat: String = String(ItemDb.item(id).cat)
		if (TraderStock.catalog_of(id) > 0 or (cat not in ["key", "intel"] and ItemDb.value(id) > 0)) and not Balance.TRADER_BUY_PRICES.has(id):
			missing.append(id)
	_check("включены все скрытые товары; новые товары требуют цены", missing.is_empty(), str(missing))
	_check("алиасы старых предметов читают ту же цену", Profile.buy_price("w_rifle") == Profile.buy_price("wpn_ar_01") and Profile.buy_price("ammo_545") == Profile.buy_price("ammo_545_std"), "")
	_check("неизвестную вещь и отрицательное количество не купить", not Profile.buy("unknown_economy_item", 1) and not Profile.buy("bandage", -1), "")
	_check("отсутствующая цена блокирует и шаблон", LoadoutTemplates._buy_block("unknown_economy_item") != "", "")
	var packs_bad: Array[String] = []
	for id: String in Balance.LOOT_PACKS:
		var contents_buy: int = 0
		var contents_sell: int = 0
		for pair: Array in Balance.LOOT_PACKS[id]:
			contents_buy += Profile.buy_price(String(pair[0])) * int(pair[1])
			contents_sell += Profile.sell_price(ItemDb.make(String(pair[0]), int(pair[1])))
		if Profile.buy_price(id) != contents_buy or contents_sell > contents_buy:
			packs_bad.append(id)
	_check("упаковки не обходят цены патронов при распаковке", packs_bad.is_empty(), "%d упаковок; %s" % [Balance.LOOT_PACKS.size(), str(packs_bad)])
	var loaded: Dictionary = WeaponDb.make_mag("mag_545_60", "ammo_545_ap", 0)
	Gear.mag_apply(loaded, [["ammo_545_std", 20], ["ammo_545_ap", 40]])
	_check("переоценённый магазин сохраняет стоимость смешанных патронов", Profile.sell_price(loaded) == Profile.sell_price(ItemDb.make("mag_545_60", 1)) + Profile.sell_price(ItemDb.make("ammo_545_std", 20)) + Profile.sell_price(ItemDb.make("ammo_545_ap", 40)), str(Profile.sell_price(loaded)))
	var facts: String = ItemInfo.facts_line("mag_545_60", loaded)
	_check("описание показывает новую покупку и продажу конкретного экземпляра", facts.contains("купить %s ₽" % InventoryUI.money(5500)) and facts.contains("продать %s ₽" % InventoryUI.money(Profile.sell_price(loaded))), facts)
	var gun: Dictionary = ItemDb.make("wpn_ar_01", 1)
	gun["dur"] = 20.0
	gun["mag"] = Gear.mag_record(loaded)
	gun["mods"] = {"optic_primary": {"id": "optic_holo_01", "dur": 60.0}}
	gun["chamber"] = 1
	gun["chamber_ammo"] = "ammo_545_ap"
	_check("износ тела не удешевляет исправный магазин и патроны; разбор эквивалентен", absi(Profile.sell_price(gun) - _parts_sale(gun)) <= 1, "%d/%d" % [Profile.sell_price(gun), _parts_sale(gun)])
	var rig: Dictionary = ItemDb.make("armor_mid", 1)
	ItemDb.attach_pouch(rig, "pouch_rifle")
	ItemDb.attach_pouch(rig, "pouch_rifle")
	rig["mags"] = [loaded]
	rig["dump"] = [ItemDb.make("mag_545_60", 1)]
	_check("магазины в подсумках на броне и в сбросе переоценены", absi(Profile.sell_price(rig) - _parts_sale(rig)) <= 1, "%d/%d" % [Profile.sell_price(rig), _parts_sale(rig)])
	var old_values: bool = true
	for row: Dictionary in snapshot.items:
		if ItemDb.value(String(row.id)) != int(row.definition.value):
			old_values = false
	_check("оценки находок для ремонта и аналитики сохранены", old_values, "")
	var repair: Dictionary = ItemDb.make("wpn_ar_01", 1)
	repair["dur"] = 50.0
	_check("дорогая покупка не увеличила ремонт", WeaponCondition.repair_price(repair) == ceili(ItemDb.value("wpn_ar_01") * float(Balance.CONDITION.repair_weapon) * 0.5), str(WeaponCondition.repair_price(repair)))
	Profile.stash.clear()
	Profile.money = 2999
	_check("нехватка денег — ничего не списано и не выдано", not Profile.buy("medkit", 1, "stash", false) and Profile.money == 2999 and Profile.stash.is_empty(), "")
	Profile.money = 100000
	var full: Array = []
	for y: int in range(Profile.stash_grid().y):
		for x: int in range(Profile.stash_grid().x):
			full.append({"id": "bandage", "n": ItemDb.stack("bandage"), "x": x, "y": y})
	Profile.stash = full
	_check("тайник полон — деньги не списаны", not Profile.buy("medkit", 1, "stash", false) and Profile.money == 100000, "")
	# Деньги, купленные предметы, модули и правила кармана переживают загрузку по-прежнему.
	Profile.stash.clear()
	ItemDb.add_to(Profile.stash, gun, Profile.stash_grid())
	Profile.money = 1234567
	Profile.modules["pocket"] = 2
	Profile.modules["generator"] = 1
	Profile.pocket = [ItemDb.make("gold_chain", 2)]
	Profile.save()
	Profile.use_file("user://economy_prices_test.json", false)
	Profile.ensure()
	_check("сохранённые деньги, сборка, улучшения и содержимое кармана не обнулены", Profile.money == 1234567 and int(Profile.modules.generator) == 1 and Profile.pocket_grid() == Vector2i(3, 3) and int(Profile.pocket[0].n) == 2 and int(Profile.stash[0].chamber) == 1, "")
	Profile.modules["generator"] = 0
	Profile.modules["workbench"] = 1
	Profile.modules["stash"] = 1
	Profile.modules["pocket"] = 0
	Profile.modules["radio"] = 0
	_check("цены строительства из Balance", int(Upgrades.next_cost("generator").money) == 100000 and int(Upgrades.next_cost("workbench").money) == 180000 and int(Upgrades.next_cost("stash").money) == 120000 and int(Upgrades.next_cost("pocket").money) == 150000 and int(Upgrades.next_cost("radio").money) == 100000, "")
	Profile.trust = 49
	Profile.stash.clear()
	ItemDb.add_to(Profile.stash, ItemDb.make("battery", 2), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("wires", 3), Profile.stash_grid())
	Profile.money = 99999
	_check("не хватает одного рубля на модуль — деньги и детали целы", not Upgrades.build("generator") and Profile.money == 99999 and Profile.stash_count("battery") == 2 and Upgrades.level("generator") == 0, "")
	Profile.money = 100000
	_check("строительство списывает новую цену и детали", Upgrades.build("generator") and Profile.money == 0 and Profile.stash_count("battery") == 0 and Upgrades.level("generator") == 1, "")
	_check("карты доступны бесплатно; наводки 2F/3F/4F подорожали", int(Floors.find("zone01").price) == 0 and int(Floors.find("zone01").fee) == 0 and int(Floors.find("f2").price) == 200000 and int(Floors.find("f3").price) == 450000 and int(Floors.find("f4").price) == 900000, "")
	Profile.floors_open.erase("f2")
	Profile.money = 199999
	_check("не хватает одного рубля на маршрут — ничего не списано", not Floors.unlock("f2") and Profile.money == 199999 and not Floors.is_open("f2"), "")
	Profile.money = 200000
	_check("новая цена маршрута списывается один раз", Floors.unlock("f2") and Profile.money == 0 and Floors.is_open("f2") and not Floors.unlock("f2"), "")
	Settings.shop_loot = false
	_check("рейдовые ценности остаются вне обычной продажи", not Profile.buy("laser_head", 1) and not Profile.buy("supply_signal", 1), "")
	_check("описание рейдового эксклюзива не обещает покупку", not ItemInfo.facts_line("laser_head").contains("купить"), "")
	Settings.unlock_all = true
	# 2026-10-24: три брони и три шлема вместо 8+7, подсумки на броне вместо разгрузок — суммы комплектов пересчитаны
	var expected: Array[int] = [135140, 704680, 2112190, 3797700]
	for i: int in range(Balance.TRADER_KITS.size()):
		Profile.stash.clear()
		Profile.backpack.clear()
		Profile.equipment.clear()
		Profile.money = 10000000
		var kit: Dictionary = Balance.TRADER_KITS[i]
		var plan: Dictionary = LoadoutTemplates.plan(kit)
		var failed: Array[String] = LoadoutTemplates.apply(kit)
		_check("общая цена готового комплекта «%s»" % String(kit.name), int(plan.cost) == expected[i] and failed.is_empty() and Profile.money == 10000000 - expected[i], "%d/%d; %s" % [int(plan.cost), expected[i], str(failed)])
	print("economy_prices_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Независимый контроль: сколько заплатят после разборки на отдельные записи.
func _parts_sale(entry: Dictionary) -> int:
	var body: Dictionary = entry.duplicate(true)
	for key: String in ["mods", "mag", "chamber", "plates", "mags", "dump", "rounds", "layers"]:
		body.erase(key)
	var total: int = Profile.sell_price(body)
	for slot: String in entry.get("mods", {}):
		total += _parts_sale(WeaponCondition.mod_entry(entry.mods[slot]))
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	if not mag.is_empty():
		total += _parts_sale(Gear.mag_item(mag))
	if entry.has("rounds"):
		for layer: Variant in Gear.mag_layers(entry):
			total += Profile.sell_price(ItemDb.make(String(layer[0]), int(layer[1])))
	if int(entry.get("chamber", 0)) > 0:
		total += Profile.sell_price(ItemDb.make(String(entry.get("chamber_ammo", mag.get("ammo", ""))), int(entry.chamber)))
	for side: String in entry.get("plates", {}):
		total += _parts_sale(entry.plates[side])
	for part: String in ["mags", "dump"]:
		for inner: Variant in entry.get(part, []):
			total += _parts_sale(inner)
	return total


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
