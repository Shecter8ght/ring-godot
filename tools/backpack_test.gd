extends Node
## Рюкзак: слот, сетки 20 / 30 / 45 / 60, смена рюкзака перекладывает вещи (лишнее — в тайник),
## старый профиль получает обычный рюкзак, спринт с рюкзаком дороже.

const TEST_PROFILE := "user://backpack_test_profile.json"
var _fails := 0


func _check(name: String, ok: bool, info: String = "") -> void:
	print(("  [ok] " if ok else "  [FAIL] ") + name + "  " + info)
	if not ok:
		_fails += 1


func _idx(id: String) -> int:
	for i in Profile.stash.size():
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _ready() -> void:
	Profile.use_file(TEST_PROFILE, true)
	_check("новый профиль: обычный рюкзак надет, 30 ячеек", Profile.equipment.has("backpack") and Profile.backpack_capacity() == 30, str(Profile.grid_of("backpack")))
	for k in [["bp_daypack", 30], ["bp_tourist", 45], ["bp_raid", 60]]:
		var g := ItemDb.bag_grid({"backpack": ItemDb.make(String(k[0]), 1)})
		_check("рюкзак %s — %d ячеек" % [k[0], k[1]], g.x * g.y == int(k[1]), str(g))
	var g0 := ItemDb.bag_grid({})
	_check("без рюкзака — 20 ячеек", g0.x * g0.y == 20, str(g0))
	# набить рюкзак на 30, снять — 20 в карманах, лишнее — в тайник, ничего не теряется
	Profile.backpack = []
	# аптечки 2×1 без стопок: 15 штук — все 30 ячеек
	var kits0 := Profile.stash_count("medkit")
	for i in range(15):
		ItemDb.add_to(Profile.backpack, ItemDb.make("medkit", 1), Profile.grid_of("backpack"))
	_check("рюкзак на 30 забит", ItemDb.cells_of(Profile.backpack) == 30, "%d" % ItemDb.cells_of(Profile.backpack))
	Profile.unequip("backpack")
	_check("снял рюкзак: в карманах ≤ 20 ячеек", ItemDb.cells_of(Profile.backpack) <= 20 and ItemDb.grid_ok(Profile.backpack, Profile.grid_of("backpack")), "%d" % ItemDb.cells_of(Profile.backpack))
	var kits := Profile.stash_count("medkit") - kits0
	for e in Profile.backpack:
		if String(e.id) == "medkit":
			kits += int(e.n)
	_check("лишнее — в тайнике, ничего не пропало", kits == 15, "%d" % kits)
	_check("рюкзак — в тайнике", _idx("bp_daypack") >= 0)
	# купить большой рюкзак: слот свободен — сразу надет
	Profile.money = 1000000
	_check("купил рейдовый — сразу надет", Profile.buy("bp_raid", 1, "stash") and String(Profile.equipment.get("backpack", {}).get("id", "")) == "bp_raid")
	_check("рейдовый — 60 ячеек", Profile.backpack_capacity() == 60)
	# любое оружие в любой слот
	Profile.equipment.erase("primary")
	Profile.equipment.erase("secondary")
	ItemDb.add_to(Profile.stash, ItemDb.make("wpn_hg_01", 1), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("wpn_hg_02", 1), Profile.stash_grid())
	Profile.equip_from("stash", _idx("wpn_hg_01"))
	Profile.equip_from("stash", _idx("wpn_hg_02"))
	_check("два пистолета — в оба слота оружия", Profile.equipment.has("primary") and Profile.equipment.has("secondary"), str(Profile.equipment.keys()))
	_check("спринт с рейдовым дороже", ItemDb.bag_sprint_k(Profile.equipment) > 1.2)
	print("backpack_test: провалено %d" % _fails)
	Profile.use_file(TEST_PROFILE, false)
	get_tree().quit(1 if _fails > 0 else 0)
