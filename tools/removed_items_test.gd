extends Node
## Предметы, убранные решением владельца 2026-11-13 (docs/design/loot_matrix_v2.md §6): их нет в ItemDb, таблицы лута
## и каталоги Михалыча их не содержат, а старое сохранение с ними загружается без ошибок — вещи уходят, деньги
## возвращаются по прежней цене (Balance.REMOVED_ITEMS), старые разгрузки превращаются в подсумки (Balance.LEGACY_RIGS).
## godot --headless res://tools/removed_items_test.tscn

const REMOVED: Array[String] = ["rig_belt", "rig_chest", "rig_assault", "rig_heavy", "pack_57_ap", "key_jewelry",
	"keycard_security", "work_gloves", "clipboard", "measuring_tape", "wall_clock", "food_tomatoes", "food_beans",
	"food_sardines", "food_milk", "freeze_dried_meals", "protein_pack", "ration_emergency",
	"headset_passive", "headset_active", "headset_tactical", "headset_perimeter"]
const PROFILE := "user://removed_items_test.json"

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	# (а) ItemDb: записей нет; у pack_57_ap остаётся псевдоним старых сохранений на пачку 9×21 (weapons.json → aliases)
	for id in REMOVED:
		if id == "pack_57_ap":
			_check("pack_57_ap — только псевдоним на нынешнюю пачку", WeaponDb.canonical(id) == "pack_921_ap" and ItemDb.exists("pack_921_ap"), WeaponDb.canonical(id))
		else:
			_check("%s: ItemDb не знает" % id, not ItemDb.exists(id), "")
	var with_rig := 0
	for id: String in ItemDb.all_ids():
		if ItemDb.item(id).has("rig") or bool(ItemDb.item(id).get("legacy", false)):
			with_rig += 1
	_check("в данных не осталось записей-разгрузок", with_rig == 0, str(with_rig))
	# (б) таблицы лута: 2000 бросков каждой, ни одного удалённого id
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261113
	var tables: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string("res://data/loot.json")) as Dictionary).tables
	var bad := 0
	var unknown := 0
	var empty := {}
	for table: String in tables:
		var empties := 0
		for i in range(2000):
			var got: Array = ItemDb.roll(table, rng)
			if got.is_empty():
				empties += 1
			for e: Dictionary in got:
				var id := String(e.id)
				if id in REMOVED and id != "pack_57_ap":
					bad += 1
				if not ItemDb.exists(id):
					unknown += 1
		empty[table] = empties
	_check("2000 бросков × %d таблиц: удалённых id нет" % tables.size(), bad == 0, str(bad))
	_check("все выпавшие id известны ItemDb", unknown == 0, str(unknown))
	print("доля пустых бросков, %: ", _pct(empty))
	# (г) каталоги Михалыча и готовые комплекты
	var cat: Dictionary = TraderStock.data().get("catalog", {})
	var stock_ids: Array = TraderStock.stock()
	for id in REMOVED:
		_check("каталог торговца без %s" % id, not cat.has(id) and not stock_ids.has(id), "")
		_check("цена покупки без %s" % id, not Balance.TRADER_BUY_PRICES.has(id) and not Balance.TRADER_SELL_PRICES.has(id), "")
	var text := JSON.stringify(Balance.TRADER_KITS)
	for id in REMOVED:
		_check("комплекты без %s" % id, not text.contains("\"%s\"" % id), "")
	for pair: Array in Balance.RESCUE_KIT:
		_check("набор выручки: %s известен" % String(pair[0]), ItemDb.exists(String(pair[0])), "")
	for id: String in WeaponDb.loadouts():
		_check("у бойцов нет гарнитур: %s" % id, not WeaponDb.loadout(id).has("headset"), "")
	_check("слота «Уши» нет", "ears" not in Inventory.SLOTS, "")
	# (в) старое сохранение
	_old_save()
	_check("(в) загрузка старого сохранения без ошибок", Profile.money > 0, str(Profile.money))
	_finish()


func _old_save() -> void:
	var armor := {"id": "armor_mid", "n": 1}
	var d := {
		"money": 1000,
		"stash": [{"id": "work_gloves", "n": 3}, {"id": "food_beans", "n": 2}, {"id": "bandage", "n": 4}, {"id": "rig_belt", "n": 1, "mags": [], "dump": []},
			{"id": "pack_57_ap", "n": 1}, {"id": "key_jewelry", "n": 1}, {"id": "headset_passive", "n": 2}],
		"backpack": [{"id": "wall_clock", "n": 1}, {"id": "keycard_security", "n": 1}, {"id": "water", "n": 2}, {"id": "rig_heavy", "n": 1, "mags": [], "dump": []},
			{"id": "headset_active", "n": 1}],
		"pocket": [{"id": "clipboard", "n": 1}, {"id": "ration_emergency", "n": 2}],
		"equipment": {"armor": armor, "rig": {"id": "rig_assault", "n": 1, "mags": [], "dump": []}, "ears": {"id": "headset_perimeter", "n": 1}},
		"trade_hold": [{"id": "headset_tactical", "n": 1}],
		"unlocked_stock": ["headset_tactical"],
		"loadout_templates": [{"name": "Старый", "slots": {"rig": {"id": "rig_chest"}, "ears": {"id": "headset_active"}},
			"backpack": [["protein_pack", 2], ["bandage", 3], ["freeze_dried_meals", 1], ["headset_passive", 2]]}],
	}
	var f := FileAccess.open(PROFILE, FileAccess.WRITE)
	f.store_string(JSON.stringify(d))
	f.close()
	Profile.use_file(PROFILE, false)
	var paid := 3 * 275 + 2 * 990 + 2750 + 990 + 5500 + 330 + 2 * 2860 + 2 * 1650 + 7700 + 14300 + 26400
	_check("деньги вернулись по прежней цене", Profile.money == 1000 + paid, "%d, ждали %d" % [Profile.money, 1000 + paid])
	for l: Array in [Profile.stash, Profile.backpack, Profile.pocket]:
		for e: Dictionary in l:
			_check("в сетках нет %s" % String(e.id), not (String(e.id) in REMOVED) or String(e.id) == "pack_57_ap", "")
	_check("pack_57_ap в сохранении стал пачкой 9×21 (псевдоним)", _count(Profile.stash, "pack_921_ap") == 1, str(Profile.stash))
	_check("обычное осталось: бинты 4, вода 2", _count(Profile.stash, "bandage") == 4 and _count(Profile.backpack, "water") == 2, "")
	_check("слот разгрузки пуст", not Profile.equipment.has("rig"), "")
	_check("надетая гарнитура и запись о ней в магазине убраны", not Profile.equipment.has("ears") and "headset_tactical" not in Profile.unlocked_stock, "")
	# подсумки: надетая rig_assault — 6 автоматных, rig_belt (2) и rig_heavy (8) из сеток — подсумками в тайник
	var pouches := 0
	for e: Dictionary in (ItemDb.pouch_list(Profile.equipment.armor) if Profile.equipment.has("armor") else []):
		if String(e.id) == "pouch_rifle":
			pouches += 1
	var loose := _count(Profile.stash, "pouch_rifle")
	_check("разгрузки стали подсумками: 6 + 2 + 8 штук всего", pouches + loose == 16, "на броне %d, в тайнике %d" % [pouches, loose])
	var t: Dictionary = Profile.loadout_templates[0]
	_check("слот гарнитуры убран из шаблона", not (t.slots as Dictionary).has("ears"), "")
	_check("шаблон: слот rig переведён, убранное из рюкзака шаблона ушло", not (t.slots as Dictionary).has("rig") and (t.backpack as Array).size() == 1 and String(t.backpack[0][0]) == "bandage", str(t))
	# повторная загрузка того, что сохранили, — тоже чисто
	Profile.use_file(PROFILE, false)
	var again := 0
	for l: Array in [Profile.stash, Profile.backpack, Profile.pocket]:
		for e: Dictionary in l:
			if String(e.id) in REMOVED and String(e.id) != "pack_57_ap":
				again += 1
	_check("повторная загрузка: удалённых нет", again == 0, str(again))
	_check("возврат за гарнитуры начислен один раз", Profile.money == 1000 + paid, str(Profile.money))


func _count(list: Array, id: String) -> int:
	var n := 0
	for e: Dictionary in list:
		if String(e.id) == id:
			n += int(e.get("n", 1))
	return n


func _pct(empty: Dictionary) -> String:
	var parts: Array[String] = []
	for k: String in empty:
		if int(empty[k]) > 0:
			parts.append("%s %.1f" % [k, float(empty[k]) / 20.0])
	return ", ".join(parts)


func _check(label: String, ok: bool, detail: String) -> void:
	if not ok:
		_fails += 1
	print("%s: %s %s" % ["OK  " if ok else "FAIL", label, "" if ok else detail])


func _finish() -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(PROFILE))
	print("removed_items_test: %s" % ("всё верно" if _fails == 0 else "ПРОВАЛ (%d)" % _fails))
	get_tree().quit(1 if _fails > 0 else 0)
