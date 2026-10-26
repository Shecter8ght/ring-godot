extends Node
## Шаблоны снаряжения: сохранить надетое и рюкзак; разложить всё в тайник — собрать обратно из
## тайника бесплатно; продать автомат — шаблон докупит его у Михалыча; ствол закрытого каталога и
## обвес не по верстаку — «нет» с причиной. godot --headless --path . res://tools/templates_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://profile_templates_test.json", true)
	Profile.ensure()
	Profile.money = 1000000
	# ступень 10 — второй каталог (АК-12 у Михалыча)
	Profile.trust = 9
	_equip("wpn_ar_01")
	_equip("wpn_hg_02")
	Profile.stash_to_backpack(_idx("ammo_919_fmj"), 40)
	Profile.stash_to_backpack(_idx("bandage"), 2)
	var t := LoadoutTemplates.capture("Штурм")
	_check("шаблон сохранён: слоты и рюкзак", t.slots.has("primary") and t.slots.has("sidearm") and not (t.backpack as Array).is_empty(), str(t))
	# всё обратно в тайник
	for slot in Profile.equipment.keys():
		Profile.unequip(String(slot))
	while not Profile.backpack.is_empty():
		Profile.backpack_to_stash(0, int(Profile.backpack[0].n))
	var p := LoadoutTemplates.plan(t)
	_check("всё в тайнике — собрать бесплатно", int(p.cost) == 0 and int(p.missing) == 0, str(p))
	var m0 := Profile.money
	var fails := LoadoutTemplates.apply(t)
	_check("собрано из тайника: надето, в рюкзаке", fails.is_empty() and String(Profile.equipment.primary.id) == "wpn_ar_01" and _bp("ammo_919_fmj") == 40 and _bp("bandage") == 2 and Profile.money == m0,
		"%s; патроны %d, бинты %d" % [str(fails), _bp("ammo_919_fmj"), _bp("bandage")])
	# автомат продан — докупить у Михалыча
	Profile.unequip("primary")
	Profile.sell(_idx("wpn_ar_01"), 1)
	p = LoadoutTemplates.plan(t)
	var price := Profile.buy_price("wpn_ar_01")
	_check("автомата нет — в плане покупка по цене Михалыча", int(p.cost) == price and int(p.missing) == 0, "%d / %d" % [int(p.cost), price])
	m0 = Profile.money
	fails = LoadoutTemplates.apply(t)
	_check("собрано с покупкой: автомат надет, деньги списаны", fails.is_empty() and String(Profile.equipment.primary.id) == "wpn_ar_01" and Profile.money == m0 - price, str(fails))
	# закрытый каталог и обвес не по верстаку
	var t2 := {"name": "Мечта", "slots": {"primary": {"id": "wpn_sp_02"}, "secondary": {"id": "wpn_ar_01", "mods": {"optic_primary": "optic_zorin_k1"}}}, "backpack": []}
	p = LoadoutTemplates.plan(t2)
	var why: Array = []
	for r in p.rows:
		if String(r.how) == "нет":
			why.append(String(r.why))
	_check("Шорох-9 — нужна ступень доверия, коллиматор — нужен верстак", int(p.missing) == 2 and "ступень" in str(why) and "верстак" in str(why), str(why))
	print("templates_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _equip(id: String) -> void:
	var i := _idx(id)
	if i < 0:
		Profile.buy(id, 1)
		i = _idx(id)
	Profile.equip_from("stash", i)


func _idx(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _bp(id: String) -> int:
	var n := 0
	for e in Profile.backpack:
		if String(e.id) == id:
			n += int(e.n)
	return n


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
