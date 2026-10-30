extends Node
## Окно Михалыча, вкладка «Купить»: закреплённая шапка (поиск, разделы, подгруппы, порядок по цене),
## группы оружия по классам, количество патронов шагом 30 и числом руками, находки из рейда только с
## читом «лут в продаже», четыре готовых комплекта справа (собираются целиком), выбор своего оружия
## одним кликом во вкладке «Обвес оружия». С окном — снимки docs/screens/trader_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/trader_ui_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://trader_ui_test.json", true)
	Settings.unlock_all = false
	Settings.all_weapons = false
	Settings.shop_loot = false
	Profile.money = Profile.buy_price("supply_signal") + 400000

	# --- данные: что продаётся, как делится на группы
	_check("головка станка и сигнал самолёта — только из рейда", ItemDb.loot_only("laser_head") and ItemDb.loot_only("supply_signal") and not ItemDb.loot_only("wpn_hg_01") and not ItemDb.loot_only("bandage"), "")
	_check("без чита находку не купить", not Profile.buy("supply_signal", 1, "stash", false), "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(200)
	var level := get_tree().current_scene
	var ui := level.get("_ui") as HideoutUI
	for st in get_tree().get_nodes_in_group("interactables"):
		if st is HideoutStation and (st as HideoutStation).kind == HideoutStation.Kind.TRADER:
			level.call("open_station", st)
			break
	ui._trader_tab = "buy"
	await _frames(20)
	_check("группы оружия: ПМ — пистолеты, ВЕРАС — автоматы", String(ui._subgroup("wpn_hg_01")[1]) == "Пистолеты" and String(ui._subgroup("wpn_ar_01")[1]) == "Автоматы и карабины", "")
	_check("патроны и магазины — по калибру", String(ui._subgroup("ammo_545_std")[1]) == String(ui._subgroup("mag_545_30")[1]), String(ui._subgroup("ammo_545_std")[1]))
	var stock: Array = ui._trader_stock()
	_check("без читов находок в продаже нет", not "laser_head" in stock and not "supply_signal" in stock, "%d поз." % stock.size())
	# шапка разделов стоит над прокруткой (светлое окно «Б1»: разделы и поиск — не в списке)
	var scroll := ui._shop_list.get_parent() as ScrollContainer
	_check("шапка закреплена над списком", scroll != null and ui._shop_head != null and not scroll.is_ancestor_of(ui._shop_head), "")
	_check("выбран первый в списке, витрина и подробности есть", ui._sel != "" and ui._shop_center.get_child_count() > 0 and ui._shop_detail.get_child_count() > 0, ui._sel)
	_save("trader_buy")

	# --- количество: «+» у патронов — по 30, руками — любое
	_check("патроны по умолчанию — 30", ui._qty_of("ammo_918_pst") == 30, str(ui._qty_of("ammo_918_pst")))
	ui._step_qty("ammo_918_pst", 1)
	_check("«+» — ещё 30", ui._qty_of("ammo_918_pst") == 60, str(ui._qty_of("ammo_918_pst")))
	ui._select("ammo_918_pst")
	await _frames(4)
	var field := _find_field(ui, "ammo_918_pst")
	_check("поле количества есть в подробностях", field != null, "")
	if field:
		field.text = "45"
		field.text_changed.emit("45")
		_check("число руками принято", ui._qty_of("ammo_918_pst") == 45, str(ui._qty_of("ammo_918_pst")))
		ui._step_qty("ammo_918_pst", 1)
		_check("«+» от 45 — до 60", ui._qty_of("ammo_918_pst") == 60, str(ui._qty_of("ammo_918_pst")))
		ui._step_qty("ammo_918_pst", -1)
		ui._step_qty("ammo_918_pst", -1)
		_check("«−» не уходит ниже шага", ui._qty_of("ammo_918_pst") == 30, str(ui._qty_of("ammo_918_pst")))
	ui._qty.clear()

	# --- ГРАНЬ-15 с открытыми каталогами: к нему подходит свой магазин, покупка в рюкзак
	Settings.set_unlock_all(true)
	ui._cat_tab = "weapon"
	await _frames(20)
	ui._select("wpn_ar_09")
	await _frames(4)
	_check("ГРАНЬ-15: к нему подходит магазин «ГРАНЬ»", "mag_556_30_gran" in ui._fits_of("wpn_ar_09"), str(ui._fits_of("wpn_ar_09")))
	_check("магазин «ГРАНЬ»: подходит к ГРАНЬ-15", "wpn_ar_09" in ui._fits_of("mag_556_30_gran"), str(ui._fits_of("mag_556_30_gran")))
	var gran_before: int = Profile.money
	ui._buy("wpn_ar_09", "backpack")
	_check("ГРАНЬ-15 куплен (деньги списаны)", Profile.money == gran_before - Profile.buy_price("wpn_ar_09"), "%d → %d" % [gran_before, Profile.money])
	await _frames(20)
	_save("trader_gran15")
	Settings.set_unlock_all(false)
	Profile.money = Profile.buy_price("supply_signal") + 400000
	ui._cat_tab = "all"
	await _frames(20)

	# --- раздел «Оружие» и подгруппа
	ui._cat_tab = "weapon"
	await _frames(20)
	_save("trader_weapons")
	ui._sub_tab = "Пистолеты"
	await _frames(20)
	_check("подгруппа «Пистолеты»: в списке только они", _cards(ui) > 0 and _only(ui, "PISTOL"), "%d карточек" % _cards(ui))
	ui._sub_tab = ""

	# --- поиск по названию
	ui._cat_tab = "all"
	ui._shop_search = "глуш"
	await _frames(20)
	ui._fill_shop()
	await _frames(4)
	_check("поиск «глуш»: нашлись глушители, остальное скрыто", _cards(ui) > 0 and _cards(ui) < 20, "%d карточек" % _cards(ui))
	_save("trader_search")
	ui._shop_search = ""

	# --- чит «лут в продаже»
	Settings.set_shop_loot(true)
	await _frames(20)
	stock = ui._trader_stock()
	_check("с читом находки продаются", "laser_head" in stock and "supply_signal" in stock and Profile.buy("supply_signal", 1, "stash", false), "%d поз." % stock.size())
	ui._cat_tab = "misc"
	await _frames(20)
	_save("trader_loot_cheat")
	Settings.set_shop_loot(false)
	ui._cat_tab = "all"

	# --- готовые комплекты: с открытыми каталогами и деньгами собираются целиком
	_check("комплектов четыре", Balance.TRADER_KITS.size() == 4, "")
	Settings.set_unlock_all(true)
	for kit: Dictionary in Balance.TRADER_KITS:
		Profile.use_file("user://trader_ui_test.json", true)
		Profile.money = 5000000
		var p := LoadoutTemplates.plan(kit)
		var fails := LoadoutTemplates.apply(kit)
		var worn := true
		for slot: String in (kit.slots as Dictionary):
			var rec: Dictionary = kit.slots[slot]
			var e: Dictionary = Profile.equipment.get(slot, {})
			if String(e.get("id", "")) != String(rec.id):
				worn = false
			for m: String in (rec.get("mods", {}) as Dictionary):
				if WeaponDb.mod_id((e.get("mods", {}) as Dictionary).get(m, "")) != String(rec.mods[m]):
					worn = false
			for side: String in (rec.get("plates", {}) as Dictionary):
				if String(((e.get("plates", {}) as Dictionary).get(side, {}) as Dictionary).get("id", "")) != String(rec.plates[side]):
					worn = false
		_check("комплект «%s» собран целиком" % String(kit.name), int(p.missing) == 0 and fails.is_empty() and worn, "%s ₽ %s" % [InventoryUI.money(int(p.cost)), ", ".join(fails)])
	Settings.set_unlock_all(false)
	Profile.use_file("user://trader_ui_test.json", true)
	Profile.money = 400000
	ui._trader_tab = "kits"
	await _frames(30)
	_check("вкладка «Комплекты»: карточки комплектов", ui._cols.find_children("*", "GridContainer", true, false).size() > 0, "")
	_save("trader_kits")
	await _frames(20)

	# --- обвес оружия: своё оружие выбирается кликом по карточке
	Profile.buy("wpn_hg_01", 1, "stash", false)
	Profile.buy("wpn_sg_03", 1, "stash", false)
	ui._trader_tab = "mods"
	await _frames(30)
	var card: ItemCard = null
	for n in ui._cols.find_children("*", "", true, false):
		if n is ItemCard and (n as ItemCard).mouse_default_cursor_shape == Control.CURSOR_POINTING_HAND:
			card = n
			break
	_check("карточка своего оружия — кликабельна", card != null, "")
	if card:
		var before := ui._tb_where + ui._tb_uid
		var ev := InputEventMouseButton.new()
		ev.button_index = MOUSE_BUTTON_LEFT
		ev.pressed = true
		card.gui_input.emit(ev)
		_check("клик по карточке выбрал оружие", ui._tb_where + ui._tb_uid != before, ui._tb_where)
	await _frames(20)
	_save("trader_mods")

	print("trader_ui_test: провалов %d" % _fails)
	get_tree().quit(_fails)


func _cards(ui: HideoutUI) -> int:
	var n := 0
	for c in ui._shop_list.find_children("*", "", true, false):
		if c is ItemCard:
			n += 1
	return n


## Все карточки списка — оружие класса cls (по иконке карточки).
func _only(ui: HideoutUI, cls: String) -> bool:
	for c in ui._shop_list.find_children("*", "", true, false):
		if c is ItemCard.IconBox:
			var w := WeaponDb.weapon((c as ItemCard.IconBox).id)
			if w.is_empty() or String(w["class"]) != cls:
				return false
	return true


## Поле количества в карточке товара id.
## Поле количества в подробностях выбранного предмета id.
func _find_field(ui: HideoutUI, id: String) -> LineEdit:
	if ui._sel != id:
		return null
	var fields := ui._shop_detail.find_children("*", "LineEdit", true, false)
	return fields[0] if not fields.is_empty() else null


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
