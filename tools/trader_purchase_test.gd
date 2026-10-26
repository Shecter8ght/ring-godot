extends Node
## Покупки: свободные слоты, занятая/несовместимая экипировка, тайник и атомарный отказ.
## tools/godot.cmd --headless res://tools/trader_purchase_test.tscn

var _checks: int = 0
var _fails: int = 0


func _enter_tree() -> void:
	Profile.use_file("user://trader_purchase_test.json", true)


func _ready() -> void:
	Settings.unlock_all = false
	Settings.all_weapons = false
	Settings.shop_loot = false
	_catalog()
	_wearables()
	_storage()
	_migration()
	print("trader_purchase_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _reset() -> void:
	Profile.equipment = {}
	Profile.stash = []
	Profile.backpack = []
	Profile.pocket = []
	Profile.modules = {}
	Profile.money = 10000000
	Profile.trust = 9


func _check(label: String, ok: bool) -> void:
	_checks += 1
	if not ok:
		_fails += 1
	print("%s: %s" % ["PASS" if ok else "FAIL", label])


func _catalog() -> void:
	_reset()
	for id: String in ["optic_rmr_01", "optic_offset_rd_01"]:
		_check(id + " убран из определений и витрины", not id in WeaponDb.ids("attachments") and not id in TraderStock.stock())
		_check(id + " из старого сохранения заменяется на ЗОРИН", WeaponDb.canonical(id) == "optic_zorin_k1")
	for id: String in ["optic_zorin_k1", "mount_pm_k1"]:
		_check(id + " в открытом втором каталоге и имеет цену", id in TraderStock.stock() and TraderStock.catalog_of(id) == 2 and Profile.trust_level() >= 2 and Profile.buy_price(id) > 0)
		var money_before: int = Profile.money
		_check(id + " покупается без читов в рюкзак", Profile.buy(id, 1, "backpack") and _count(Profile.backpack, id) == 1 and Profile.money == money_before - Profile.buy_price(id))
	_check("в актуальных пресетах нет убранных прицелов", not JSON.stringify(WeaponDb.presets()).contains("optic_rmr_01") and not JSON.stringify(WeaponDb.presets()).contains("optic_offset_rd_01"))


func _wearables() -> void:
	for id: String in ["wpn_ar_01", "wpn_hg_01", "signal_launcher", "armor_poor", "helmet_simple", "sunglasses", "headset_passive", "bp_daypack", "nvg"]:
		_reset()
		# Ракетница помечена raid_only; здесь проверяем её слот при разрешённой покупке.
		Settings.shop_loot = id == "signal_launcher"
		_fill(Profile.backpack, Profile.grid_of("backpack"))
		_fill(Profile.stash, Profile.stash_grid())
		var slot: String = ItemDb.pick_slot(id, Profile.equipment)
		_check(id + " надевается даже при полных сетках", Profile.buy(id, 1, "backpack") and String((Profile.equipment.get(slot, {}) as Dictionary).get("id", "")) == id)
	Settings.shop_loot = false
	_reset()
	Profile.equipment.primary = {}
	_check("пустая запись слота считается свободной", Profile.buy("wpn_ar_01", 1, "backpack") and String(Profile.equipment.primary.id) == "wpn_ar_01" and not Profile.equipment.has("secondary"))
	_reset()
	Profile.equipment = {"helmet": {}, "eyes": {}}
	_check("пустая запись шлема не мешает надеть ПНВ", Profile.buy("nvg", 1, "backpack") and String(Profile.equipment.eyes.id) == "nvg")
	_reset()
	Profile.equipment.eyes = ItemDb.make("nvg", 1)
	_check("несовместимый шлем не надевается поверх ПНВ", Profile.buy("helmet_simple", 1, "backpack") and not Profile.equipment.has("helmet") and _count(Profile.backpack, "helmet_simple") == 1)
	_reset()
	Profile.equipment.primary = ItemDb.make("wpn_ar_01", 1)
	var original: String = JSON.stringify(Profile.equipment.primary)
	_check("другое длинное оружие занимает второй свободный слот", Profile.buy("wpn_sg_03", 1, "backpack") and String(Profile.equipment.secondary.id) == "wpn_sg_03" and JSON.stringify(Profile.equipment.primary) == original)
	_reset()
	Profile.equipment.helmet = ItemDb.make("helmet_simple", 1)
	_check("занятый шлем не заменяется", Profile.buy("helmet_mid", 1, "backpack") and String(Profile.equipment.helmet.id) == "helmet_simple" and _count(Profile.backpack, "helmet_mid") == 1)
	_check("ПНВ не надевается на несовместимый шлем", Profile.buy("nvg", 1, "backpack") and not Profile.equipment.has("eyes") and _count(Profile.backpack, "nvg") == 1)
	_reset()
	Profile.equipment.armor = ItemDb.make("armor_mid", 1)
	_check("подсумок сразу крепится к свободному месту брони", Profile.buy("pouch_rifle", 1, "backpack") and not (Profile.equipment.armor.get("pouches", []) as Array).is_empty() and _count(Profile.backpack, "pouch_rifle") == 0)
	_reset()
	_check("две купленные винтовки занимают два слота", Profile.buy("wpn_ar_01", 2, "backpack") and Profile.equipment.has("primary") and Profile.equipment.has("secondary") and Profile.backpack.is_empty())
	_check("каждая купленная винтовка имеет собственный номер и полный магазин", String(Profile.equipment.primary.get("uid", "")) != String(Profile.equipment.secondary.get("uid", "")) and int(Profile.equipment.primary.mag.rounds) == WeaponDb.capacity(Profile.equipment.primary) and int(Profile.equipment.secondary.mag.rounds) == WeaponDb.capacity(Profile.equipment.secondary))
	_reset()
	_check("сборщик шаблона может отключить автонадевание", Profile.buy("helmet_mid", 1, "stash", false) and Profile.equipment.is_empty() and Profile.stash_count("helmet_mid") == 1)


func _storage() -> void:
	_reset()
	_check("обычная покупка остаётся в рюкзаке", Profile.buy("bandage", 3, "backpack") and _count(Profile.backpack, "bandage") == 3 and Profile.stash.is_empty())
	_reset()
	_fill(Profile.backpack, Profile.grid_of("backpack"))
	_check("полный рюкзак отправляет покупку в тайник", Profile.buy("optic_zorin_k1", 1, "backpack") and Profile.stash_count("optic_zorin_k1") == 1 and _count(Profile.backpack, "optic_zorin_k1") == 0)
	_reset()
	_fill(Profile.backpack, Profile.grid_of("backpack"))
	Profile.backpack.pop_back()
	var qty: int = ItemDb.stack("ammo_918_pst") * 2
	_check("непоместившаяся партия уходит в тайник целиком", Profile.buy("ammo_918_pst", qty, "backpack") and Profile.stash_count("ammo_918_pst") == qty and _count(Profile.backpack, "ammo_918_pst") == 0)
	_reset()
	_fill(Profile.backpack, Profile.grid_of("backpack"))
	_fill(Profile.stash, Profile.stash_grid())
	var before: String = _snapshot()
	_check("обе сетки полны — отказ без списания и частичной выдачи", not Profile.buy("optic_zorin_k1", 1, "backpack") and _snapshot() == before)
	_check("партия оружия не надевается частично при отказе", not Profile.buy("wpn_ar_01", 3, "backpack") and _snapshot() == before)
	_reset()
	Profile.money = Profile.buy_price("helmet_mid") - 1
	before = _snapshot()
	_check("не хватает денег — экипировка и сетки не меняются", not Profile.buy("helmet_mid", 1, "backpack") and _snapshot() == before)


func _migration() -> void:
	_reset()
	Profile.stash = [{"id": "optic_rmr_01", "n": 1, "dur": 67.0},
		{"id": "optic_offset_rd_01", "n": 1, "dur": 53.0},
		{"id": "mount_offset45_01", "n": 1, "dur": 81.0, "mods": {"rail": {"id": "optic_rmr_01", "dur": 37.0}}}]
	Profile.equipment.sidearm = ItemDb.make("wpn_hg_02", 1)
	Profile.equipment.sidearm.mods = {"optic_primary": {"id": "optic_rmr_01", "dur": 42.0}}
	Profile.save()
	Profile.use_file("user://trader_purchase_test.json", false)
	_check("несовместимый прицел снят с затвора", (Profile.equipment.sidearm.mods as Dictionary).is_empty())
	_check("все четыре прежних прицела сохранены как ЗОРИН", Profile.stash_count("optic_zorin_k1") == 4)
	var conditions: Array[float] = []
	for item: Dictionary in Profile.stash:
		if String(item.id) == "optic_zorin_k1":
			conditions.append(float(item.dur))
	conditions.sort()
	_check("прочность каждого прицела сохранена", conditions == ([37.0, 42.0, 53.0, 67.0] as Array[float]))
	Profile.use_file("user://trader_purchase_test.json", false)
	_check("повторная загрузка не дублирует прицелы", Profile.stash_count("optic_zorin_k1") == 4)


func _fill(items: Array, grid: Vector2i) -> void:
	items.clear()
	for y: int in range(grid.y):
		for x: int in range(grid.x):
			items.append({"id": "bandage", "n": ItemDb.stack("bandage"), "x": x, "y": y, "r": false})


func _snapshot() -> String:
	return JSON.stringify([Profile.money, Profile.equipment, Profile.stash, Profile.backpack])


func _count(items: Array, id: String) -> int:
	var total: int = 0
	for entry: Dictionary in items:
		if String(entry.id) == id:
			total += int(entry.n)
	return total
