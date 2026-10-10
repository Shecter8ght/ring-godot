extends Node
## Чит «открыть всё» (плейтест): до него — закрытые каталоги, верстак 1, генератора и станка
## гравировки нет; включил — доверие и все модули на пределе, обвес ставится в любую точку, станок
## работает, тайник и карман выросли; выключил — прогресс прежний, тайник и карман остались
## большими; консоль unlock. godot --headless --path . res://tools/unlock_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://profile_unlock_test.json", true)
	Profile.ensure()
	var catalogs: int = TraderStock.catalogs().size()
	_check("без чита: первый каталог, верстак 1, генератора и станка нет",
		Profile.trust_level() == 1 and Upgrades.level("workbench") == 1 and Upgrades.level("generator") == 0 and Upgrades.level("engraver") == 0,
		"каталог %d, верстак %d" % [Profile.trust_level(), Upgrades.level("workbench")])
	_check("без чита: прицел на верстаке 1 не поставить, станок не работает",
		Profile.mod_block("", "optic_primary") != "" and Engraver.block() != "", Profile.mod_block("", "optic_primary"))
	var stash_before: Vector2i = Profile.stash_grid()
	var modules_before: Dictionary = Profile.modules.duplicate()

	Settings.set_unlock_all(true)
	_check("включил: открыты все каталоги Михалыча", Profile.trust_level() == catalogs and Settings.shop_all(), "%d из %d" % [Profile.trust_level(), catalogs])
	var maxed := true
	for m: Dictionary in Upgrades.all():
		var id: String = String(m.id)
		if Upgrades.level(id) != Upgrades.max_level(id) or not Upgrades.next_cost(id).is_empty():
			maxed = false
			print("    не на пределе: ", id)
	_check("все модули убежища на пределе, строить нечего", maxed, "")
	var free_mounts := true
	for mount: String in Balance.WORKBENCH_SLOT_LEVEL:
		if Profile.mod_block("", mount) != "":
			free_mounts = false
	_check("верстак: обвес ставится в любую точку", free_mounts, "")
	_check("станок гравировки стоит и запитан", Engraver.block() == "" and int(Quests.campaign_modules().get("generator", 0)) >= 1, Engraver.block())
	_check("рация: второе задание Михалыча", Missions.slots() == int(Balance.MISSION_SLOTS[1]), str(Missions.slots()))
	_check("тайник и карман выросли до предела",
		Profile.stash_grid().y == int(Balance.STASH_ROWS[Balance.STASH_ROWS.size() - 1]) and Profile.pocket_grid() == Balance.POCKET_GRIDS[Balance.POCKET_GRIDS.size() - 1],
		"%s, карман %s" % [str(Profile.stash_grid()), str(Profile.pocket_grid())])
	_check("сохранение не помнит верстак и генератор — только тайник и карман",
		not Profile.modules.has("workbench") and not Profile.modules.has("generator") and Profile.flags.get("engraver_installed", false) != true,
		str(Profile.modules))
	# всё из игры покупается: ствол последнего каталога и головка для станка
	Profile.money = 10000000
	var top_gun: String = ""
	for id: Variant in TraderStock.stock():
		if WeaponDb.is_weapon(String(id)) and TraderStock.catalog_of(String(id)) == catalogs:
			top_gun = String(id)
			break
	_check("ствол последнего каталога и головка станка покупаются",
		top_gun != "" and LoadoutTemplates._buy_block(top_gun) == "" and Profile.buy(top_gun, 1, "stash", false) and not Profile.buy("laser_head", 1, "stash", false)
		and _buy_loot("laser_head") and Engraver.heads().size() == 1,
		top_gun)

	Settings.set_unlock_all(false)
	_check("выключил: каталог, верстак, генератор, станок — как были",
		Profile.trust_level() == 1 and Upgrades.level("workbench") == int(modules_before.get("workbench", 1)) and Upgrades.level("generator") == 0 and Upgrades.level("engraver") == 0 and Engraver.block() != "",
		"каталог %d, верстак %d" % [Profile.trust_level(), Upgrades.level("workbench")])
	_check("…а тайник остался большим (вещи не пропадут)", Profile.stash_grid().y > stash_before.y and ItemDb.grid_ok(Profile.stash, Profile.stash_grid()), str(Profile.stash_grid()))

	Quests.hud._run("unlock on")
	_check("консоль: unlock on", Settings.unlock_all and Upgrades.level("generator") == Upgrades.max_level("generator"), "")
	Quests.hud._run("unlock")
	_check("консоль: unlock — выключил", not Settings.unlock_all and Upgrades.level("generator") == 0, "")
	print("unlock_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Находимое только в рейде покупается лишь с отдельным читом «лут в продаже».
func _buy_loot(id: String) -> bool:
	Settings.set_shop_loot(true)
	var ok: bool = Profile.buy(id, 1, "stash", false)
	Settings.set_shop_loot(false)
	return ok


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
