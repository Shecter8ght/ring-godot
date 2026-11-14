extends Node
## Окно снаряжения v2 без окна (docs/design/equip_doll_v2.md): места брони на половинках (пистолетный — половина,
## автоматный — с левой половины места, большой — только на пару из armor.pairs_big, на пояс — нет), перевод
## старого списка подсумков, магазины по виду подсумка, снять / переставить подсумок, правило ПНВ и шлема без
## площадки, кукла: силуэт, крепления шлема, полоска мест; пистолетный на теле бота — на половине места.

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://equip_doll_test.json", true)
	_places()
	_migration()
	_mag_kinds()
	_detach()
	_nvg()
	_profile_ops()
	_doll()
	_outfit()
	print("equip_doll_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String = "") -> void:
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
	if not ok:
		_fails += 1


func _armor(id: String) -> Dictionary:
	return ItemDb.make(id, 1)


func _places() -> void:
	var mid := _armor("armor_mid")
	_check("автоматный — на целое место, с левой половины", ItemDb.pouch_fits(mid, "pouch_rifle", 1) and not ItemDb.pouch_fits(mid, "pouch_rifle", 2))
	_check("пистолетный — на любую половину", ItemDb.pouch_fits(mid, "pouch_pistol", 2) and ItemDb.pouch_fits(mid, "pouch_pistol", 10))
	_check("большой — на пару 1+2 и 2+3, не 3+4", ItemDb.pouch_fits(mid, "pouch_big", 1) and ItemDb.pouch_fits(mid, "pouch_big", 3) and not ItemDb.pouch_fits(mid, "pouch_big", 5))
	_check("за пределами мест — нет", not ItemDb.pouch_fits(mid, "pouch_rifle", 11) and not ItemDb.pouch_fits(mid, "pouch_pistol", 11))
	_check("на пояс большой не встаёт", not ItemDb.pouch_fits(_armor("belt_pouches"), "pouch_big", 1))
	ItemDb.attach_pouch(mid, "pouch_rifle", 1)
	_check("занятое место — нет", not ItemDb.pouch_fits(mid, "pouch_pistol", 2) and not ItemDb.pouch_fits(mid, "pouch_big", 1))
	_check("два пистолетных делят место", ItemDb.attach_pouch(mid, "pouch_pistol", 3) and ItemDb.attach_pouch(mid, "pouch_pistol", 4))
	_check("большой на 2+3 уже не встаёт (место 2 занято)", not ItemDb.pouch_fits(mid, "pouch_big", 3))
	_check("свободно мест 3", is_equal_approx(ItemDb.places_free(mid), 3.0), str(ItemDb.places_free(mid)))
	_check("первое свободное для автоматного — место 3", ItemDb.pouch_free_at(mid, "pouch_rifle") == 5, str(ItemDb.pouch_free_at(mid, "pouch_rifle")))


func _migration() -> void:
	var e := _armor("armor_mid")
	e["pouches"] = ["pouch_pistol", "pouch_rifle", "pouch_pistol", "pouch_big"]
	var list := ItemDb.pouch_list(e)
	var at: Array = []
	for p: Dictionary in list:
		at.append([String(p.id), int(p.at)])
	_check("старый список — в полуслоты по правилам", str(at) == str([["pouch_pistol", 1], ["pouch_pistol", 2], ["pouch_rifle", 3], ["pouch_big", 5]]), str(at))
	var e2 := _armor("armor_mid")
	e2["pouches"] = ["pouch_rifle", "pouch_rifle", "pouch_big"]
	var ids := ItemDb.pouch_ids(e2)
	_check("большой не на свою пару — всё равно на месте, не пропал", ids.size() == 3 and ids.has("pouch_big"), str(ItemDb.pouch_list(e2)))


func _rig_eq() -> Dictionary:
	var a := _armor("armor_top")
	ItemDb.attach_pouch(a, "pouch_pistol", 1)
	ItemDb.attach_pouch(a, "pouch_rifle", 3)
	ItemDb.attach_pouch(a, "pouch_big", 5)
	return {"armor": a}


func _mag_kinds() -> void:
	var eq := _rig_eq()
	_check("сетка подсумков: пист 1 + авт 1 + большой 2", ItemDb.rig_grid(eq, "rig") == Vector2i(4, int(Balance.RIG.rows)), str(ItemDb.rig_grid(eq, "rig")))
	var pm := ItemDb.make("mag_918_8", 1)
	var ak := ItemDb.make("mag_545_30", 1)
	var big := ItemDb.make("mag_545_60", 1)
	var wide := ItemDb.make("mag_pkm_100", 1)
	_check("пистолетный — пистолетный магазин, не автоматный", ItemDb.rig_accepts_at(eq, pm, 0, 0, false) and not ItemDb.rig_accepts_at(eq, ak, 0, 0, false))
	_check("автоматный — обычный, не крупный", ItemDb.rig_accepts_at(eq, ak, 1, 0, false) and not ItemDb.rig_accepts_at(eq, big, 1, 0, false))
	_check("большой — крупный и обычный", ItemDb.rig_accepts_at(eq, big, 2, 0, false) and ItemDb.rig_accepts_at(eq, ak, 3, 0, false))
	_check("широкий магазин — только на две колонки большого", ItemDb.rig_accepts_at(eq, wide, 2, 0, false) and not ItemDb.rig_accepts_at(eq, wide, 1, 0, false))
	_check("подписи колонок", str(ItemDb.rig_column_groups(eq)) == str([[0, 1, "пист"], [1, 1, "авт"], [2, 2, "большой"]]), str(ItemDb.rig_column_groups(eq)))
	var placed: Array = []
	for m: Dictionary in [ItemDb.make("mag_545_60", 1), ItemDb.make("mag_918_8", 1), ItemDb.make("mag_545_30", 1)]:
		placed.append(ItemDb.add_to_rig(eq, m))
	var xs: Array = []
	for m: Dictionary in ItemDb.rig_list(eq, "rig"):
		xs.append([String(m.id), int(m.x)])
	_check("сами раскладываются по видам", placed == [1, 1, 1] and xs.has(["mag_918_8", 0]) and xs.has(["mag_545_60", 2]), str(xs))
	var inv := Inventory.new()
	inv.equipment = eq
	_check("инвентарь не кладёт автоматный в пистолетный", inv.put_at(ItemDb.make("mag_545_30", 1), 0, 1, false, "rig") == 0)
	_check("инвентарь кладёт пистолетный в пистолетный", inv.put_at(ItemDb.make("mag_919_17", 1), 0, 1, false, "rig") == 1)
	inv.free()


func _detach() -> void:
	var eq := _rig_eq()
	ItemDb.add_to_rig(eq, ItemDb.make("mag_545_30", 1))
	ItemDb.add_to_rig(eq, ItemDb.make("mag_545_30", 1))
	ItemDb.add_to_rig(eq, ItemDb.make("mag_918_8", 1))
	var i := ItemDb.pouch_index_at(eq.armor, 3)
	var out := ItemDb.detach_pouch(eq, i)
	var ids: Array = []
	for m: Dictionary in out:
		ids.append(String(m.id))
	var left := ItemDb.rig_list(eq, "rig").size()
	_check("сняли автоматный — сам подсумок наружу, магазины переехали в большой", ids.has("pouch_rifle") and left + out.size() - 1 == 3, "наружу %s, в подсумках %d" % [str(ids), left])
	var a := eq.armor as Dictionary
	var mv := ItemDb.move_pouch(eq, 1, 4)
	_check("переставить пистолетный на половину места 2", bool(mv[0]) and ItemDb.pouch_index_at(a, 4) >= 0 and ItemDb.pouch_index_at(a, 1) < 0)
	_check("на занятое — нет", not bool(ItemDb.move_pouch(eq, 4, 5)[0]))


func _nvg() -> void:
	var simple := {"helmet": ItemDb.make("helmet_simple", 1)}
	var mid := {"helmet": ItemDb.make("helmet_mid", 1)}
	_check("ПНВ без шлема — можно", ItemDb.pick_slot("nvg", {}) == "eyes")
	_check("ПНВ под шлем без площадки — нет", ItemDb.pick_slot("nvg", simple) == "" and ItemDb.slot_block("nvg", "eyes", simple) != "")
	_check("ПНВ под шлем с площадкой — можно", ItemDb.pick_slot("nvg", mid) == "eyes")
	_check("очки под любой шлем", ItemDb.pick_slot("sunglasses", simple) == "eyes")
	var with_nvg := {"eyes": ItemDb.make("nvg", 1)}
	_check("шлем без площадки поверх ПНВ — нет", ItemDb.pick_slot("helmet_simple", with_nvg) == "")
	_check("шлем с площадкой поверх ПНВ — можно", ItemDb.pick_slot("helmet_top", with_nvg) == "helmet")
	_check("крепления тяжёлого шлема", ItemDb.helmet_mounts({"helmet": ItemDb.make("helmet_top", 1)}) == ["NVG", "LIGHT", "VISOR"])


func _stash_index(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _profile_ops() -> void:
	Profile.equipment = {"armor": ItemDb.make("armor_mid", 1), "helmet": ItemDb.make("helmet_simple", 1)}
	Profile.stash = []
	Profile.backpack = []
	for id: String in ["pouch_rifle", "pouch_pistol", "pouch_big", "nvg"]:
		ItemDb.add_to(Profile.stash, ItemDb.make(id, 1), Profile.stash_grid())
	var a: Dictionary = Profile.equipment.armor
	_check("подсумок из тайника — на полуслот 3", Profile.equip_from("stash", _stash_index("pouch_rifle"), "pouch:3") and ItemDb.pouch_index_at(a, 3) >= 0)
	_check("пистолетный — на половину 2", Profile.equip_from("stash", _stash_index("pouch_pistol"), "pouch:2") and ItemDb.pouch_index_at(a, 2) >= 0)
	_check("большой на 1+2 — занято, не встал", not Profile.equip_from("stash", _stash_index("pouch_big"), "pouch:1") and _stash_index("pouch_big") >= 0)
	_check("ПНВ под простой шлем — не надеть", not Profile.equip_from("stash", _stash_index("nvg")) and not Profile.equipment.has("eyes"))
	_check("переставить автоматный на место 3", Profile.move_pouch(3, 5) and ItemDb.pouch_index_at(a, 5) >= 0)
	_check("снять пистолетный — в тайник", Profile.unequip("pouch:2") and _stash_index("pouch_pistol") >= 0 and ItemDb.pouch_index_at(a, 2) < 0)
	_check("снять в рюкзак перетаскиванием", Profile.unequip_to("pouch:5", "backpack", 0, 0, false) and ItemDb.pouch_list(a).is_empty() and not Profile.backpack.is_empty())


func _doll() -> void:
	var doll := EquipDoll.new()
	add_child(doll)
	var top := ItemDb.make("armor_top", 1)
	ItemDb.attach_pouch(top, "pouch_big", 1)
	doll.set_equipment({"armor": top, "helmet": ItemDb.make("helmet_top", 1), "eyes": ItemDb.make("nvg", 1)})
	var chips := 0
	for c: Node in doll.get_children():
		if c is EquipDoll.MountChip:
			chips += 1
	_check("тяжёлый шлем — 3 крепления, ПНВ горит", chips == 3)
	_check("полоска — 8 мест", doll.places.places() == 8)
	_check("3D-модели в окне нет", doll.find_children("*", "SubViewport", true, false).is_empty())
	doll.set_equipment({"helmet": ItemDb.make("helmet_simple", 1)})
	_check("под простым шлемом подпись у глаз", (doll.views.eyes as SlotView).note != "")
	_check("простой шлем — креплений нет", doll.get_children().filter(func(c: Node) -> bool: return c is EquipDoll.MountChip and not c.is_queued_for_deletion()).is_empty())
	doll.queue_free()


func _outfit() -> void:
	var a := ItemDb.make("armor_mid", 1)
	ItemDb.attach_pouch(a, "pouch_pistol", 1)
	ItemDb.attach_pouch(a, "pouch_pistol", 2)
	ItemDb.attach_pouch(a, "pouch_rifle", 3)
	var d: Dictionary = JSON.parse_string(NpcOutfit.describe({"armor": a}, false))
	# числа из JSON — дробные: сравнить целыми
	var got: Array = []
	for rec: Variant in d.get("pouches", []):
		got.append([int((rec as Array)[0]), String((rec as Array)[1]), int((rec as Array)[2])])
	_check("на теле: два пистолетных на месте 1 по половинам, автоматный — место 2", str(got) == str([[1, "pouch_pistol", -1], [1, "pouch_pistol", 1], [2, "pouch_rifle", 0]]), str(got))
	_check("шаг мест брони по данным", NpcGear.place_pitch("mid", 1) > 0.05, str(NpcGear.place_pitch("mid", 1)))
