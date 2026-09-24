extends Node
## Снимки убежища на тестовом профиле: общий вид, окно тайника, торговца, выхода —
## docs/screens/hideout_*.png. godot --path . res://tools/hideout_shots.tscn

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://profile_shots.json", true)
	# немного снаряжения — чтобы окна были не пустыми
	for id in ["wpn_ar_03", "wpn_hg_03", "vest_police"]:
		Profile.equip_from_stash(_idx(id))
	Profile.stash_to_backpack(_idx("ammo_545_std"), 90)
	Profile.stash_to_backpack(_idx("bandage"), 4)
	Profile.money = 400000
	Profile.trust = 3
	# верстак 2 — ставятся и прицелы, и фонари сбоку
	for pair in [["battery", 2], ["wires", 5], ["toolset", 1], ["cigarettes", 5], ["lighter", 2]]:
		ItemDb.add_to(Profile.stash, ItemDb.make(String(pair[0]), int(pair[1])), Profile.stash_grid())
	Upgrades.build("generator")
	Upgrades.build("workbench")
	for id in ["optic_rd_01", "muzzle_supp_545_01", "grip_vertical_01", "stock_tele_ak_01", "tac_flashlight_01", "tac_laser_01",
			"optic_holo_01", "optic_4x_01", "muzzle_comp_545_01", "optic_rmr_01", "mag_545_45", "plate_steel"]:
		Profile.buy(id, 1)
	for id in ["optic_rd_01", "muzzle_supp_545_01", "grip_vertical_01", "stock_tele_ak_01", "tac_flashlight_01"]:
		Profile.install_mod("primary", _idx(id))
	Profile.fit_part("equip:primary", -1, "stash", _idx("mag_545_45"))
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(240)
	_save("hideout")
	var level := get_tree().current_scene
	for kind in [HideoutStation.Kind.STASH, HideoutStation.Kind.TRADER, HideoutStation.Kind.EXIT, HideoutStation.Kind.WORKBENCH, HideoutStation.Kind.UPGRADES]:
		for st in get_tree().get_nodes_in_group("interactables"):
			if st is HideoutStation and (st as HideoutStation).kind == kind:
				level.call("open_station", st)
				break
		await _frames(40)
		_save("hideout_ui_%d" % kind)
		(level.get("_ui") as HideoutUI).close_ui()
		await _frames(2)
	# торговец: вкладки (карточки, схема обвеса с выбором своего оружия, продажа)
	var ui := level.get("_ui") as HideoutUI
	for st in get_tree().get_nodes_in_group("interactables"):
		if st is HideoutStation and (st as HideoutStation).kind == HideoutStation.Kind.TRADER:
			level.call("open_station", st)
			break
	for tab in ["buy", "mods", "sell"]:
		ui._trader_tab = tab
		await _frames(40)
		_save("hideout_trader_%s" % tab)
	# схема: клик по квадратику прицела — список (купить и поставить / своё)
	ui._trader_tab = "mods"
	await _frames(20)
	var boards := ui.find_children("*", "MountBoard", true, false)
	if not boards.is_empty():
		var b := boards[0] as MountBoard
		for slot in b._slots:
			if String(slot) == "optic_primary":
				(b._slots[slot] as Button).pressed.emit()
		await _frames(20)
		_save("hideout_trader_board_popup")
	get_tree().quit(0)


func _idx(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
