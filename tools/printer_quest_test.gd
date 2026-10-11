extends Node
## Задание Михалыча «Фирменный знак» (принтер наклеек): закрыто до «Своей метки»; четыре этапа — корпус,
## плата, головка (груз вынесен из рейда — этап закрыт), расходники из тайника разговором; после задания
## принтер печатает наклейки (плёнка и краска тратятся, первая — бесплатно), Михалыч продаёт плёнку.
## tools/godot.cmd --headless res://tools/printer_quest_test.tscn

const Q := "brand_seal"

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://printer_quest_test.json", true)
	Profile.ensure()
	Profile.trust = 20
	Profile.stash.clear()
	_check("задание есть в списке", not Quests.def(Q).is_empty())
	_check("до «Своей метки» задание закрыто", Quests.state(Q) == "LOCKED", Quests.state(Q))
	_check("без принтера печатать нельзя, плёнки в продаже нет", not Stickers.printer_ready() and Stickers.print_block("sticker_skull") != "" and ItemDb.loot_only("sticker_film"))
	# «Своя метка» пройдена
	Profile.quests["own_mark"] = {"state": "COMPLETED", "stage": 3, "obj": 0, "clues": [], "count": 0, "rewarded": true}
	_check("после «Своей метки» задание доступно у Михалыча", Quests.state(Q) == "AVAILABLE" and _option() != "", Quests.state(Q))
	_talk()
	_check("взято: цель — вынести корпус", Quests.state(Q) == "ACTIVE" and String(Quests.objective(Q).get("item", "")) == "printer_body", str(Quests.objective(Q).get("id", "")))
	# три груза: вынесен — этап закрыт, отчёт Михалычу
	for step: Array in [["printer_body", "printer_body"], ["printer_board", "printer_board"], ["printer_head", "printer_head"]]:
		_check("цель — груз %s" % step[1], String(Quests.objective(Q).get("item", "")) == String(step[1]), str(Quests.objective(Q)))
		Quests.event("extracted", {"cargo": [String(step[0])], "items": [], "npcs": []})
		_check("%s вынесен — нужно отчитаться Михалычу" % step[1], String(Quests.objective(Q).get("type", "")) == "talk", str(Quests.objective(Q).get("id", "")))
		_talk()
	_check("после головки принтер установлен (модуль убежища)", Quests.flag("printer_installed") == true and Upgrades.level("sticker_printer") == 1)
	_check("последний этап — расходники", String(Quests.objective(Q).get("id", "")) == "supplies", str(Quests.objective(Q).get("id", "")))
	# расходников нет — разговор другой, этап не закрывается
	_check("без расходников Михалыч говорит, что нужно", _option() == "supplies", _option())
	_talk()
	_check("без расходников этап не закрыт", Quests.state(Q) == "ACTIVE" and not Stickers.printer_ready())
	ItemDb.add_to(Profile.stash, ItemDb.make("sticker_film", 5), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("ink_set", 2), Profile.stash_grid())
	_check("расходники в тайнике — обычный разговор", _option() == "ready", _option())
	var money: int = Profile.money
	_talk()
	_check("расходники забраны: плёнки 2, картриджей 1", Profile.stash_count("sticker_film") == 2 and Profile.stash_count("ink_set") == 1,
		"%d / %d" % [Profile.stash_count("sticker_film"), Profile.stash_count("ink_set")])
	_check("задание выполнено, принтер отдан, награда выдана", Quests.state(Q) == "COMPLETED" and Stickers.printer_ready() and Profile.money > money, Quests.state(Q))
	# печать
	_check("плёнка теперь в продаже у Михалыча", not ItemDb.loot_only("sticker_film"))
	_check("эмблему ЧВК принтер не печатает", Stickers.print_block("sticker_perimeter") != "")
	_check("первая наклейка — за счёт Михалыча: плёнка и краска целы", Stickers.print_sticker("sticker_skull") == ""
		and Profile.stash_count("sticker_skull") == 1 and Profile.stash_count("sticker_film") == 2 and Profile.stash_count("ink_set") == 1)
	_check("вторая — лист плёнки и новый комплект картриджей", Stickers.print_sticker("sticker_shark") == ""
		and Profile.stash_count("sticker_shark") == 1 and Profile.stash_count("sticker_film") == 1 and Profile.stash_count("ink_set") == 0
		and Stickers.ink_left() == int(Balance.STICKERS.ink_sheets) - 1, "плёнки %d, картриджей %d, краски %d" % [Profile.stash_count("sticker_film"), Profile.stash_count("ink_set"), Stickers.ink_left()])
	_check("третья — только плёнка, комплект тот же", Stickers.print_sticker("sticker_tally") == "" and Profile.stash_count("sticker_film") == 0 and Stickers.ink_left() == int(Balance.STICKERS.ink_sheets) - 2)
	_check("плёнка кончилась — печать не идёт, причина названа", Stickers.print_sticker("sticker_skull") != "" and Profile.stash_count("sticker_skull") == 1)
	# окно: страница «Наклейки» с принтером
	var ui: HideoutUI = HideoutUI.new()
	add_child(ui)
	ui._wb_mode = "stickers"
	ui.open(HideoutStation.Kind.WORKBENCH)
	for i: int in range(30):
		await get_tree().process_frame
	var button: Button = ui.find_child("StickerPrint", true, false) as Button
	_check("на странице «Наклейки» есть принтер; без плёнки кнопка выключена", button != null and button.disabled)
	if DisplayServer.get_name() != "headless":
		ItemDb.add_to(Profile.stash, ItemDb.make("sticker_film", 3), Profile.stash_grid())
		for i: int in range(30):
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/stickers_printer.png"))
	print("printer_quest_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Какой разговор по заданию сейчас предлагает Михалыч ("" — никакого).
func _option() -> String:
	for o: Dictionary in Quests.talk_options("trader"):
		if String(o.quest) == Q:
			return String(o.dialogue)
	return ""


func _talk() -> void:
	for o: Dictionary in Quests.talk_options("trader"):
		if String(o.quest) == Q:
			Quests.finish_talk(Q, "trader", String(o.dialogue))
			return
	_check("есть о чём поговорить с Михалычем", false, str(Quests.objective(Q)))


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1
