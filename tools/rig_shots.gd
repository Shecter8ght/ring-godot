extends Node
## Ростовая фигура со слотами и разгрузка: окно тайника в убежище (фигура, подсумки, сумка сброса) и
## окно рюкзака в рейде. Снимки docs/screens/doll_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/rig_shots.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://rig_shots.json", true)
	Profile.money = 900000
	Profile.trust = 49
	for id: String in ["wpn_ar_02", "wpn_hg_02", "armor_top", "helmet_mid", "headset_tactical", "bp_tourist", "nvg"]:
		Profile.buy(id, 1, "stash", true)
	# подсумки — на надетую броню (вместо прежней разгрузки): три автоматных
	for k in range(3):
		Profile.buy("pouch_rifle", 1, "stash", false)
		Profile.equip_from("stash", _find_stash("pouch_rifle"))
	_check("три подсумка висят на броне", (Profile.equipment.armor.get("pouches", []) as Array).size() == 3, str(Profile.equipment.armor.get("pouches", [])))
	for i: int in range(5):
		Profile.buy("mag_556_30", 1, "backpack", false)
	Profile.buy("mag_919_17", 1, "backpack", false)
	Profile.buy("ammo_556_std", 60, "backpack", false)
	Profile.buy("bandage", 3, "backpack", false)
	# три магазина — в подсумки, один пустой — в сумку сброса
	var moved := 0
	var i2 := 0
	while i2 < Profile.backpack.size() and moved < 3:
		if String(Profile.backpack[i2].id) == "mag_556_30":
			(Profile.backpack[i2] as Dictionary)["rounds"] = 30
			(Profile.backpack[i2] as Dictionary)["ammo"] = "ammo_556_std"
			if Profile.transfer("backpack", i2, "rig", moved, 0, false):
				moved += 1
				continue
		i2 += 1
	_check("магазины легли в подсумки", moved == 3 and Profile.list_of("rig").size() == 3, str(moved))
	_check("в подсумки не кладётся бинт", not Profile.transfer("backpack", _find("bandage"), "rig", 4, 0, false))
	_check("пустой магазин — в сумку сброса", Profile.transfer("backpack", _find("mag_556_30"), "dump", 0, 0, false))
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
	get_tree().change_scene_to_file("res://scenes/levels/f1_market.tscn")
	for i in range(240):
		await get_tree().process_frame
	var me: Player = Raid.current.local_player() if Raid.current else null
	_check("в рейде разгрузка надета, магазины в подсумках", me != null and me.inventory.list_of("rig").size() == 3, str(me.inventory.list_of("rig").size()) if me else "")
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
