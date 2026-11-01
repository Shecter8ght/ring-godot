extends Node
## Наклейки на оружии: клеятся на верстаке (предмет тратится), не больше трёх и не на занятое место,
## снятая пропадает, «Счёт» получает зарубку за эвакуацию (до предела), всё это едет в модель ствола.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/stickers_test.tscn → docs/screens/stickers_panel.png

var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://stickers_test.json", true)
	var rifle: Dictionary = ItemDb.make("wpn_ar_09", 1)
	WeaponMark.identify(rifle)
	Profile.equipment = {"primary": rifle}
	Profile.stash.clear()
	Profile.backpack.clear()
	for pair: Array in [["sticker_skull", 3], ["sticker_tally", 2], ["sticker_shark", 1], ["sticker_perimeter", 1]]:
		ItemDb.add_to(Profile.stash, ItemDb.make(String(pair[0]), int(pair[1])), Profile.stash_grid())
	var uid: String = String(rifle.uid)
	var sites: Array[Dictionary] = WeaponMark.positions("wpn_ar_09")
	_check("наклейки найдены у игрока", Stickers.owned().size() == 4, str(Stickers.owned().size()))
	_check("наклеена «Счёт»", _stick("sticker_tally", String(sites[5].id), 1.0) == "")
	_check("предмет потрачен: осталась одна «Счёт»", _count("sticker_tally") == 1, str(_count("sticker_tally")))
	_check("на занятое место — отказ", _stick("sticker_skull", String(sites[5].id), 1.0) != "")
	_check("вторая и третья наклеены", _stick("sticker_skull", String(sites[6].id), 1.5) == "" and _stick("sticker_perimeter", String(sites[0].id), 1.0) == "")
	_check("четвёртая — отказ, предмет цел", _stick("sticker_shark", String(sites[1].id), 1.0) != "" and _count("sticker_shark") == 1)
	_check("на стволе три наклейки", Stickers.of(Profile.equipment.primary).size() == 3)
	# зарубки за эвакуацию
	var key_before: String = WeaponMark.key(WeaponMark.marks(Profile.equipment.primary))
	Profile.return_loadout(Profile.equipment, [])
	_check("эвакуация — зарубка на «Счёте»", int(Stickers.of(Profile.equipment.primary)[0].n) == 1, str(Stickers.of(Profile.equipment.primary)[0]))
	_check("зарубка меняет вид ствола (ключ модели)", WeaponMark.key(WeaponMark.marks(Profile.equipment.primary)) != key_before)
	for i: int in range(40):
		Profile.return_loadout(Profile.equipment, [])
	_check("зарубок не больше предела", int(Stickers.of(Profile.equipment.primary)[0].n) == int(Balance.STICKERS.tally_max), str(Stickers.of(Profile.equipment.primary)[0].n))
	# снятая пропадает
	var skulls: int = _count("sticker_skull")
	_check("снятая наклейка пропадает", Stickers.remove("equip:primary", -1, uid, 1) == "" and Stickers.of(Profile.equipment.primary).size() == 2 and _count("sticker_skull") == skulls)
	_check("после снятия место свободно", _stick("sticker_shark", String(sites[6].id), 0.7) == "")
	# модель: наклейки — узлы на стволе, с окном — и сами проекции
	var model: Node3D = WeaponModels.build("wpn_ar_09", {}, 0, 100.0, "*", WeaponMark.marks(Profile.equipment.primary))
	add_child(model)
	_check("в модели ствола три узла наклеек", model.find_children("Sticker*", "Node3D", true, false).size() == 3, str(model.find_children("Sticker*", "Node3D", true, false).size()))
	if DisplayServer.get_name() != "headless":
		await _frames(12)
		_check("наклейки спроецированы на ствол", model.find_children("StickerMark*", "Decal", true, false).size() == 3, str(model.find_children("StickerMark*", "Decal", true, false).size()))
	model.queue_free()
	# окно верстака
	var ui: HideoutUI = HideoutUI.new()
	add_child(ui)
	ui._wb_mode = "stickers"
	ui.open(HideoutStation.Kind.WORKBENCH)
	await _frames(40)
	var panel: StickerPanel = ui.find_children("*", "StickerPanel", true, false)[0] as StickerPanel if not ui.find_children("*", "StickerPanel", true, false).is_empty() else null
	_check("на верстаке открыта страница наклеек", panel != null)
	if panel:
		_check("ствол полон — кнопка «Наклеить» выключена, причина названа", panel._apply_button.disabled and panel._status.text != "", panel._status.text)
		await _shot("stickers_panel")
	print("stickers_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _stick(id: String, site: String, scale: float) -> String:
	for row: Dictionary in Stickers.owned():
		if String(row.entry.id) == id:
			return Stickers.apply("equip:primary", -1, String(Profile.equipment.primary.uid), String(row.where), int(row.idx), id, site, scale)
	return "нет предмета"


func _count(id: String) -> int:
	var n: int = 0
	for row: Dictionary in Stickers.owned():
		if String(row.entry.id) == id:
			n += int(row.entry.get("n", 1))
	return n


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _shot(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
