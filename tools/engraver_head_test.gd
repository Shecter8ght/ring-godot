extends Node
## Головка гравировщика в станке: вставить из вещей (из тайника уходит), нанести надпись выбранного
## размера на левую сторону (заряд тратится в станке), вынуть обратно в тайник с остатком; занятый
## станок вторую головку не берёт. С окном — снимки окна станка docs/screens/engraver_head_*.png.
## tools/godot.cmd --headless res://tools/engraver_head_test.tscn   (с окном: --windowed --resolution 1600x900)

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://engraver_head_test.json", true)
	Profile.modules["generator"] = 1
	Profile.flags["engraver_installed"] = true
	Profile.stash = []
	ItemDb.add_to(Profile.stash, ItemDb.make("wpn_ar_01", 1), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("laser_head", 1), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("laser_head", 1), Profile.stash_grid())
	Profile.save()
	_check("станок готов", Engraver.block() == "", Engraver.block())
	_check("в станке пусто, головки — в вещах", Engraver.installed().is_empty() and Engraver.heads().size() == 2)
	var gun: Dictionary = Profile.stash[0]
	var mark: Dictionary = WeaponMark.make(gun, "Михалыч", "left_1")
	mark["scale"] = 1.5
	_check("без головки в станке не нанести", Engraver.apply_installed("stash", 0, String(gun.uid), "Михалыч", mark) != "")
	var head: Dictionary = Engraver.heads()[0]
	_check("головка вставлена", Engraver.insert(String(head.where), int(head.idx), String(head.entry.uid)) == "")
	_check("из вещей она ушла — лежит в станке", Engraver.heads().size() == 1 and int(Engraver.installed().get("charges", 0)) == 3, str(Engraver.installed()))
	var second: Dictionary = Engraver.heads()[0]
	_check("занятый станок вторую головку не берёт", Engraver.insert(String(second.where), int(second.idx), String(second.entry.uid)) != "" and Engraver.heads().size() == 1)
	_check("надпись нанесена головкой из станка", Engraver.apply_installed("stash", 0, String(gun.uid), "Михалыч", mark) == "")
	var done: Dictionary = (Profile.stash[0] as Dictionary).get("engraving", {})
	_check("на стволе надпись слева, крупная", String(done.get("text", "")) == "Михалыч" and String(done.get("site", "")) == "left_1" and is_equal_approx(float(done.get("scale", 1.0)), 1.5), str(done))
	_check("заряд потрачен в станке", int(Engraver.installed().get("charges", 0)) == 2, str(Engraver.installed()))
	_check("размер входит в ключ модели (метка перерисуется)", WeaponMark.key(done) != WeaponMark.key(WeaponMark.make(gun, "Михалыч", "left_1")))
	if DisplayServer.get_name() != "headless":
		await _shots()
	_check("головка вынута", Engraver.eject() == "")
	var back: Array[Dictionary] = Engraver.heads()
	var charges: Array = []
	for row: Dictionary in back:
		charges.append(int(row.entry.charges))
	charges.sort()
	_check("вынутая головка в тайнике с остатком 2, в станке пусто", Engraver.installed().is_empty() and charges == [2, 3], str(charges))
	print("engraver_head_test: провалов %d" % _fails)
	get_tree().quit(_fails)


func _shots() -> void:
	var hideout: Node = load("res://scenes/levels/hideout.tscn").instantiate()
	get_tree().root.add_child(hideout)
	get_tree().current_scene = hideout
	for frame: int in range(40):
		await get_tree().process_frame
	var ui: HideoutUI = hideout._ui
	ui.open(HideoutStation.Kind.ENGRAVER)
	for frame: int in range(12):
		await get_tree().process_frame
	var panel: EngraverPanel = null
	for child: Node in ui._cols.get_children():
		if child is EngraverPanel:
			panel = child
	_check("окно станка открыто", panel != null)
	if panel == null:
		return
	# второй ствол без надписи: выбрано место слева, образец виден крупно
	ItemDb.add_to(Profile.stash, ItemDb.make("wpn_ar_02", 1), Profile.stash_grid())
	panel._refresh()
	for idx: int in range(panel._weapons.size()):
		if (panel._weapons[idx].entry.get("engraving", {}) as Dictionary).is_empty():
			panel._weapon.select(idx)
	panel._invalidate()
	panel._show_weapon()
	panel._scale.select(2)
	panel._show_weapon()
	await panel._zoom_to_mark()
	for frame: int in range(40):
		await get_tree().process_frame
	_check("по умолчанию — место слева (видно от первого лица)", panel._site.selected >= 0 and int(panel._positions[panel._site.selected].side) > 0)
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/engraver_head_panel.png"))
	ui.close_ui()


func _check(what: String, ok: bool, info: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
