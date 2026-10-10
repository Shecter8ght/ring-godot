extends Node
## Снимки убежища на тестовом профиле: общий вид, окно тайника, торговца, выхода —
## docs/screens/hideout_*.png. godot --path . res://tools/hideout_shots.tscn
## HIDEOUT_ONLY=sell — только вкладка «Продать»: сетки рядом, отметка нескольких предметов, продажа разом.

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
	Profile.trust = 9  # ступень 10 — второй каталог, верстак 2, маршрут на 2F
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
	if OS.get_environment("HIDEOUT_ONLY") == "sell":
		await _sell_only()
		return
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
	# продажа: выбран ствол — подсвечены его магазины и патроны
	for ln in ["stash", "backpack"]:
		var list := Profile.list_of(ln)
		for i in range(list.size()):
			if WeaponDb.is_weapon(String(list[i].id)) and ui._sell_sel.is_empty():
				ui._sell_sel = [ln, i]
	ui._sell_picks = [ui._sell_sel.duplicate()] if not ui._sell_sel.is_empty() else []
	ui._trader_tab = "sell"
	await _frames(30)
	_save("hideout_trader_sell_focus")
	ui._sell_sel = []
	ui._sell_picks = []
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


## Вкладка «Продать»: тайник и рюкзак рядом; отмечено несколько предметов — список и общая цена;
## «Продать выбранное» — деньги пришли, предметов нет.
func _sell_only() -> void:
	var level := get_tree().current_scene
	var ui := level.get("_ui") as HideoutUI
	for st in get_tree().get_nodes_in_group("interactables"):
		if st is HideoutStation and (st as HideoutStation).kind == HideoutStation.Kind.TRADER:
			level.call("open_station", st)
			break
	ui._trader_tab = "sell"
	await _frames(30)
	_save("hideout_trader_sell")
	for ln in ["stash", "backpack"]:
		var list := Profile.list_of(ln)
		for i in range(list.size()):
			if WeaponDb.is_weapon(String(list[i].id)) and ui._sell_sel.is_empty():
				ui._sell_sel = [ln, i]
	ui._sell_picks = [ui._sell_sel.duplicate()]
	await _frames(30)
	_save("hideout_trader_sell_focus")
	# несколько: три из тайника и всё из рюкзака
	ui._sell_picks = [["stash", 0], ["stash", 2], ["stash", 3]]
	for i in range(Profile.backpack.size()):
		ui._sell_picks.append(["backpack", i])
	ui._sell_sel = ["stash", 3]
	await _frames(30)
	_save("hideout_trader_sell_multi")
	var want := 0
	for p in ui._sell_picks:
		want += Profile.sell_price(Profile.list_of(String(p[0]))[int(p[1])])
	var money := Profile.money
	var stash_n := Profile.stash.size()
	var buttons := ui.find_children("*", "Button", true, false).filter(func(b: Node) -> bool: return (b as Button).text.begins_with("Продать выбранное"))
	var fails := 0
	if buttons.size() != 1:
		fails += 1
		print("[FAIL] кнопка «Продать выбранное» одна: ", buttons.size())
	else:
		(buttons[0] as Button).pressed.emit()
	await _frames(30)
	for check in [["деньги пришли: +%d" % want, Profile.money == money + want], ["из тайника ушли три записи", Profile.stash.size() == stash_n - 3],
			["рюкзак пуст", Profile.backpack.is_empty()], ["отметки сняты", ui._sell_picks.is_empty()]]:
		if not bool(check[1]):
			fails += 1
		print("%s %s" % ["[ok]  " if bool(check[1]) else "[FAIL]", String(check[0])])
	_save("hideout_trader_sell_done")
	print("hideout_shots (sell): провалено %d" % fails)
	get_tree().quit(1 if fails else 0)


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
