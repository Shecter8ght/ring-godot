extends Node
## Окно снаряжения v2: силуэт со слотами, крепления шлема, места брони половинками, подсумки по видам и сброс —
## окно тайника в убежище и окно рюкзака в рейде. Снимки docs/screens/doll_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/rig_shots.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://rig_shots.json", true)
	Profile.money = 900000
	Profile.trust = 49
	for id: String in ["wpn_ar_09", "wpn_hg_02", "armor_top", "helmet_mid", "bp_tourist", "nvg"]:
		Profile.buy(id, 1, "stash", true)
	# подсумки — на места брони половинками (equip_doll_v2): два пистолетных делят место 1, автоматный — место 2,
	# большой — 3+4, автоматный — 5
	for pair: Array in [["pouch_pistol", 1], ["pouch_pistol", 2], ["pouch_rifle", 3], ["pouch_big", 5], ["pouch_rifle", 9]]:
		Profile.buy(String(pair[0]), 1, "stash", false)
		Profile.equip_from("stash", _find_stash(String(pair[0])), "pouch:%d" % int(pair[1]))
	_check("пять подсумков висят на броне по местам", ItemDb.pouch_list(Profile.equipment.armor).size() == 5, str(ItemDb.pouch_list(Profile.equipment.armor)))
	_check("колонки подсумков: пист, пист, авт, большой, авт", Profile.grid_of("rig").x == 6, str(ItemDb.rig_column_groups(Profile.equipment)))
	for i: int in range(5):
		Profile.buy("mag_556_30_gran", 1, "backpack", false)
	Profile.buy("mag_919_17", 1, "backpack", false)
	Profile.buy("ammo_556_std", 60, "backpack", false)
	Profile.buy("bandage", 3, "backpack", false)
	# автоматные — в автоматный и большой, пистолетный — в пистолетный, один пустой — в сумку сброса
	var moved := 0
	for x: int in [2, 3, 4]:
		var i2 := _find("mag_556_30_gran")
		(Profile.backpack[i2] as Dictionary)["rounds"] = 30
		(Profile.backpack[i2] as Dictionary)["ammo"] = "ammo_556_std"
		if Profile.transfer("backpack", i2, "rig", x, 0, false):
			moved += 1
	_check("магазины легли в подсумки", moved == 3 and Profile.list_of("rig").size() == 3, str(moved))
	_check("автоматный в пистолетный подсумок не кладётся", not Profile.transfer("backpack", _find("mag_556_30_gran"), "rig", 0, 0, false))
	_check("пистолетный — в пистолетный", Profile.transfer("backpack", _find("mag_919_17"), "rig", 0, 0, false))
	_check("в подсумки не кладётся бинт", not Profile.transfer("backpack", _find("bandage"), "rig", 5, 0, false))
	_check("пустой магазин — в сумку сброса", Profile.transfer("backpack", _find("mag_556_30_gran"), "dump", 0, 0, false))
	Profile.save()
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	for i in range(200):
		await get_tree().process_frame
	var level := get_tree().current_scene
	var ui := level.get("_ui") as HideoutUI
	for st in get_tree().get_nodes_in_group("interactables"):
		if st is HideoutStation and (st as HideoutStation).kind == HideoutStation.Kind.STASH:
			level.call("open_station", st)
			break
	for i in range(40):
		await get_tree().process_frame
	var doll: EquipDoll = null
	for n in ui._cols.find_children("*", "", true, false):
		if n is EquipDoll:
			doll = n
	_check("в тайнике — ростовая фигура со слотами", doll != null and doll.views.size() == Inventory.SLOTS.size())
	_check("в окне есть сетки подсумков и сброса", ui._stash_views.size() >= 4, str(ui._stash_views.size()))
	_save("doll_stash")
	# рейд со снаряжением: окно рюкзака
	Profile.pending_raid = true
	RaidEvents.enabled = false
	get_tree().change_scene_to_file("res://scenes/levels/mall_map.tscn")
	for i in range(240):
		await get_tree().process_frame
	var me: Player = Raid.current.local_player() if Raid.current else null
	_check("в рейде разгрузка надета, магазины в подсумках", me != null and me.inventory.list_of("rig").size() == 4, str(me.inventory.list_of("rig").size()) if me else "")
	if me:
		for m: Node in get_tree().get_nodes_in_group("marauders"):
			m.set_physics_process(false)
		Input.action_press("inventory")
		await get_tree().process_frame
		await get_tree().process_frame
		Input.action_release("inventory")
		for i in range(30):
			await get_tree().process_frame
		_save("doll_raid")
	print("rig_shots: провалов %d" % _fails)
	get_tree().quit(_fails)


func _find(id: String) -> int:
	for i: int in range(Profile.backpack.size()):
		if String(Profile.backpack[i].id) == id:
			return i
	return -1


func _find_stash(id: String) -> int:
	for i: int in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _save(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _check(what: String, ok: bool, info: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
