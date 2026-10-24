extends Node
## Снимок экономики для обсуждения баланса: настоящие цены и стопки из ItemDb/Profile.
## Профиль и настройки не меняет; броски лута изолированы фиксированным зерном.

## Снимок до v0 (economy_current.json) сохраняем для сравнения; новый аудит пишет отдельно.
const OUTPUT := "res://docs/design/economy_live.json"
const SAMPLES := 10000


func _ready() -> void:
	# Автозагрузки контрактов тоже обращаются к Profile: им нужен отдельный тестовый файл.
	Profile.use_file("user://economy_audit_test.json", true)
	var ids: Array = ItemDb.all_ids().duplicate()
	ids.sort()
	var items: Array[Dictionary] = []
	for raw: Variant in ids:
		var id: String = String(raw)
		# Алиасы старых сохранений — один и тот же товар, а не дополнительные позиции.
		if id != WeaponDb.canonical(id):
			continue
		var definition: Dictionary = ItemDb.item(id).duplicate(true)
		var entry: Dictionary = ItemDb.make(id, 1)
		if WeaponDb.is_weapon(id) and entry.get("mag") is Dictionary:
			(entry.mag as Dictionary)["rounds"] = WeaponDb.capacity(entry)
		var cat: String = String(definition.get("cat", "misc"))
		var catalog: int = TraderStock.catalog_of(id)
		var shop: bool = catalog > 0 or (cat not in ["key", "intel"] and ItemDb.value(id) > 0)
		items.append({"id": id, "definition": definition, "catalog": catalog,
			"shop": shop, "loot_only": ItemDb.loot_only(id), "buy": Profile.buy_price(id),
			"sell_new": Profile.sell_price(entry), "stack": ItemDb.stack(id),
			"cells": ItemDb.cells(id), "weight": ItemDb.weight(id)})
	var kits: Array[Dictionary] = []
	for kit: Dictionary in Balance.TRADER_KITS:
		var cost: int = 0
		var lines: Array[Dictionary] = []
		for slot: String in kit.slots:
			var spec: Dictionary = kit.slots[slot]
			cost += _line(lines, String(spec.id), 1)
			for mount: String in spec.get("mods", {}):
				cost += _line(lines, WeaponDb.mod_id(spec.mods[mount]), 1)
			for place: String in spec.get("plates", {}):
				cost += _line(lines, String(spec.plates[place]), 1)
			for pid: Variant in spec.get("pouches", []):
				cost += _line(lines, String(pid), 1)
		for pair: Array in kit.backpack:
			cost += _line(lines, String(pair[0]), int(pair[1]))
		kits.append({"name": kit.name, "buy_from_empty": cost, "lines": lines})
	var loot: Dictionary = {}
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 20261011
	var tables: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string(ItemDb.LOOT_PATH)) as Dictionary).get("tables", {})
	for table: String in tables:
		var values: Array[int] = []
		var loose_values: Array[int] = []
		var total: int = 0
		var loose_total: int = 0
		for sample: int in range(SAMPLES):
			var value: int = 0
			for entry: Dictionary in ItemDb.roll(table, rng):
				value += Profile.sell_price(entry)
			values.append(value)
			total += value
			var loose: String = ItemDb.loose_item(table, rng)
			var loose_value: int = Profile.sell_price(ItemDb.make(loose, 1)) if loose != "" else 0
			loose_values.append(loose_value)
			loose_total += loose_value
		values.sort()
		loose_values.sort()
		loot[table] = {"samples": SAMPLES, "container_mean_sell": float(total) / SAMPLES,
			"container_p50": values[SAMPLES / 2], "container_p90": values[int(SAMPLES * 0.9)],
			"loose_mean_sell": float(loose_total) / SAMPLES, "loose_p50": loose_values[SAMPLES / 2]}
	var supplies: Array[int] = []
	var supply_total: int = 0
	var raid: Raid = Raid.new()
	for sample: int in range(1000):
		var supply_value: int = 0
		for entry: Dictionary in raid._supply_loot():
			supply_value += Profile.sell_price(entry)
		supplies.append(supply_value)
		supply_total += supply_value
	raid.free()
	supplies.sort()
	var data: Dictionary = {"date": "2026-10-11", "note": "Current code snapshot; loot rolls are not player raid income. No carry/time/combat/survival model. Container samples have a fixed seed; plane samples use the live generator's random seed.",
		"items": items, "kits": kits, "loot": loot, "catalogs": TraderStock.catalogs(),
		"start_money": Balance.START_MONEY, "start_stash": Balance.START_STASH,
		"rescue_kit": Balance.RESCUE_KIT, "sell_mult": Balance.TRADER_SELL_MULT,
		"condition": Balance.CONDITION, "supply_signal": Balance.SUPPLY_SIGNAL,
		"supply_loot": Balance.SUPPLY_LOOT, "loot_packs": Balance.LOOT_PACKS,
		"plane_drop": {"samples": supplies.size(), "mean_sell": float(supply_total) / supplies.size(), "p50": supplies[supplies.size() / 2], "p90": supplies[int(supplies.size() * 0.9)]},
		"modules": {"modules": Upgrades.all()},
		"floors": {"floors": Floors.all()},
		"missions": JSON.parse_string(FileAccess.get_file_as_string("res://data/missions.json"))}
	var file: FileAccess = FileAccess.open(OUTPUT, FileAccess.WRITE)
	if file == null:
		push_error("Не удалось записать аудит экономики: %s" % OUTPUT)
		get_tree().quit(1)
		return
	file.store_string(JSON.stringify(data, "\t") + "\n")
	file.close()
	print("ECONOMY_AUDIT: %d предметов, %d комплектов, %d таблиц лута → %s" % [items.size(), kits.size(), loot.size(), OUTPUT])
	get_tree().quit()


func _line(lines: Array[Dictionary], id: String, count: int) -> int:
	var cost: int = Profile.buy_price(id) * count
	lines.append({"id": id, "count": count, "cost": cost})
	return cost
