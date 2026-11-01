extends Node
## Верстак, ремонт: всё изношенное из снаряжения, тайника и рюкзака — плашками в своей колонке, сразу
## целиком; чинится по одной и всё разом; не хватает денег — кнопки выключены.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/workbench_repair_test.tscn → docs/screens/workbench_repair.png

var _fails: int = 0
var _ui: HideoutUI


func _ready() -> void:
	Profile.use_file("user://workbench_repair_test.json", true)
	var rifle: Dictionary = ItemDb.make("wpn_ar_09", 1)
	rifle.dur = 20.0
	rifle.mods = {"optic_primary": {"id": "optic_holo_01", "dur": 0.0}, "muzzle": {"id": "muzzle_supp_gran_01", "dur": 55.0}}
	Profile.equipment = {"primary": rifle}
	Profile.stash.clear()
	Profile.backpack.clear()
	var ids: Array[String] = WeaponDb.weapon_ids()
	# в тайнике и рюкзаке — по несколько стволов разной изношенности и один целый
	for i: int in range(6):
		var e: Dictionary = ItemDb.make(String(ids[i * 3 % ids.size()]), 1)
		e.dur = [0.0, 12.0, 35.0, 58.0, 80.0, 100.0][i]
		(Profile.backpack if i == 4 else Profile.stash).append(e)
	var loose: Dictionary = ItemDb.make("optic_rd_01", 1)
	loose.dur = 40.0
	Profile.stash.append(loose)
	Profile.money = 5000000
	_ui = HideoutUI.new()
	add_child(_ui)
	_ui.open(HideoutStation.Kind.WORKBENCH)
	await _frames(6)
	var want: int = _ui._repair_jobs().size()
	_check("изношенное найдено: надетое, его обвесы, тайник, рюкзак", want == 9, str(want))
	_check("плашек столько же, сколько предметов к ремонту", _plates().size() == want, "%d / %d" % [_plates().size(), want])
	var list: Control = _plates()[0].get_parent() as Control
	var scroll: ScrollContainer = list.get_parent() as ScrollContainer
	_check("все плашки видны без прокрутки", list.size.y <= scroll.size.y + 1.0, "%.0f / %.0f" % [list.size.y, scroll.size.y])
	_check("окно не распирает за экран", _ui._cols.size.x <= get_viewport().get_visible_rect().size.x, str(_ui._cols.size.x))
	var caption: Label = _plates()[0].find_children("*", "Label", true, false)[0] as Label
	_check("подпись на плашке видна", caption.size.y >= 16.0 and caption.size.x >= 120.0, str(caption.size))
	await _shot("workbench_repair")
	# одна плашка
	var before: int = Profile.money
	var job: Dictionary = _plates()[1].get_meta("repair_job")
	_button(_plates()[1]).pressed.emit()
	await _frames(6)
	_check("плашка обвеса: починен, деньги списаны, плашка ушла",
		float(WeaponCondition.mod_entry(Profile.equipment.primary.mods[String(job.mount)]).dur) >= 100.0
		and Profile.money == before - int(job.cost) and _plates().size() == want - 1, "%d" % _plates().size())
	# денег мало: дорогое выключено, «всё» — тоже
	var rich: int = Profile.money
	Profile.money = 60
	await _frames(6)
	var all: Button = _ui.find_child("RepairAll", true, false) as Button
	_check("не хватает денег — «Починить всё» выключена", all != null and all.disabled)
	Profile.money = rich
	await _frames(6)
	all = _ui.find_child("RepairAll", true, false) as Button
	var total: int = 0
	for j: Dictionary in _ui._repair_jobs():
		total += int(j.cost)
	all.pressed.emit()
	await _frames(6)
	_check("«Починить всё»: чинить больше нечего, списана сумма", _ui._repair_jobs().is_empty() and _plates().is_empty() and Profile.money == rich - total, str(Profile.money))
	await _shot("workbench_repair_done")
	print("workbench_repair_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _plates() -> Array[Node]:
	var out: Array[Node] = []
	var list: Node = _ui.find_child("Plates", true, false)
	if list:
		for c: Node in list.get_children():
			if not c.is_queued_for_deletion():
				out.append(c)
	return out


func _button(plate: Node) -> Button:
	return plate.find_children("*", "Button", true, false)[0] as Button


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
