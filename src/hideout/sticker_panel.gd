class_name StickerPanel
extends HBoxContainer
## Наклейки на оружие — страница верстака: выбрать ствол, наклейку из своих вещей, место и размер;
## образец сразу виден на модели крупным планом. Наклеил — предмет потрачен; снял — наклейка пропала.
## На стволе не больше Balance.STICKERS.max. Правила — Stickers.

var _weapons: Array[Dictionary] = []
var _owned: Array[Dictionary] = []
var _positions: Array[Dictionary] = []
var _weapon: OptionButton
var _sticker: OptionButton
var _site: OptionButton
var _scale: OptionButton
var _on_weapon: VBoxContainer
var _apply_button: Button
var _status: Label
var _view: BuilderView
var _inventory_sig: String = ""
var _print_pick: OptionButton
var _print_button: Button
var _print_state: Label


func _ready() -> void:
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 24)
	var left: VBoxContainer = VBoxContainer.new()
	left.custom_minimum_size.x = 400
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 6)
	add_child(left)
	_label(left, "НАКЛЕЙКИ", 22)
	_label(left, "До %d на стволе. Наклейка тратится; снятая — пропадает.\nНа характеристики и цену не влияют." % int(Balance.STICKERS.max), 15)
	_label(left, "Ваше оружие", 16)
	_weapon = OptionButton.new()
	left.add_child(_weapon)
	_weapon.item_selected.connect(func(_idx: int) -> void: _positions = []; _show_weapon())
	_label(left, "Уже на стволе", 16)
	_on_weapon = VBoxContainer.new()
	_on_weapon.add_theme_constant_override("separation", 4)
	left.add_child(_on_weapon)
	_label(left, "Наклейка из ваших вещей", 16)
	_sticker = OptionButton.new()
	left.add_child(_sticker)
	_sticker.item_selected.connect(func(_idx: int) -> void: _show_weapon(); _zoom())
	_label(left, "Место", 16)
	_site = OptionButton.new()
	left.add_child(_site)
	_site.item_selected.connect(func(_idx: int) -> void: _show_weapon(); _zoom())
	_label(left, "Размер", 16)
	_scale = OptionButton.new()
	for row: Array in WeaponMark.SCALES:
		_scale.add_item(String(row[1]))
	_scale.select(1)
	left.add_child(_scale)
	_scale.item_selected.connect(func(_idx: int) -> void: _show_weapon(); _zoom())
	_apply_button = Button.new()
	_apply_button.name = "StickerApply"
	_apply_button.text = "Наклеить"
	_apply_button.custom_minimum_size.y = 40
	_apply_button.add_theme_stylebox_override("normal", UiTheme.face(Color(0.5, 0.36, 0.14), Color(1.0, 0.8, 0.45), 2))
	_apply_button.add_theme_stylebox_override("hover", UiTheme.face(Color(0.62, 0.45, 0.18), Color(1.0, 0.9, 0.65), 2))
	_apply_button.add_theme_stylebox_override("pressed", UiTheme.face(Color(0.4, 0.28, 0.1), Color(1.0, 0.8, 0.45), 0))
	left.add_child(_apply_button)
	_apply_button.pressed.connect(_apply)
	_status = _label(left, "", 16)
	_status.size_flags_vertical = Control.SIZE_EXPAND_FILL
	# принтер: печать наклейки из набора рисунков — лист плёнки и краска из тайника
	left.add_child(HSeparator.new())
	_label(left, "Принтер наклеек", 16)
	var print_row: HBoxContainer = HBoxContainer.new()
	print_row.add_theme_constant_override("separation", 8)
	left.add_child(print_row)
	_print_pick = OptionButton.new()
	_print_pick.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for id: String in Balance.STICKERS.printable:
		_print_pick.add_item(ItemDb.item_name(id))
	print_row.add_child(_print_pick)
	_print_pick.item_selected.connect(func(_idx: int) -> void: _refresh_printer())
	_print_button = Button.new()
	_print_button.name = "StickerPrint"
	_print_button.text = "Напечатать"
	print_row.add_child(_print_button)
	_print_button.pressed.connect(_print)
	_print_state = _label(left, "", 14)
	_label(left, "Наклейки находят в рейдах: киоски, офисы, тела мародёров и бойцов ЧВК.\n«Счёт» сам получает зарубку за каждую эвакуацию с этим стволом.", 14)
	var right: VBoxContainer = VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.size_flags_stretch_ratio = 1.6
	add_child(right)
	_view = BuilderView.new()
	_view.custom_minimum_size = Vector2(440, 320)
	_view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(_view)
	var sides: HBoxContainer = HBoxContainer.new()
	right.add_child(sides)
	for title: String in ["Справа", "Слева", "Общий вид", "Образец крупно"]:
		var button: Button = Button.new()
		button.text = title
		button.pressed.connect(func() -> void:
			if title == "Справа":
				_view.set_view("mark")
			elif title == "Слева":
				_view.set_view("mark_left")
			elif title == "Общий вид":
				_view.set_view("quarter")
			else:
				_view.focus_mark("StickerPreview"))
		sides.add_child(button)
	_label(right, "ЛКМ — поворот · колесо — приближение", 14)
	_refresh()


func _label(parent: Node, text: String, font_size: int) -> Label:
	var label: Label = Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.add_theme_font_size_override("font_size", font_size)
	parent.add_child(label)
	return label


func _signature() -> String:
	return str(Profile.equipment) + str(Profile.stash) + str(Profile.backpack) + str(Profile.pocket) + str(Stickers.printer_ready()) + str(Stickers.ink_left())


func _print_id() -> String:
	var list: Array = Balance.STICKERS.printable
	return String(list[clampi(_print_pick.selected, 0, list.size() - 1)])


func _refresh_printer() -> void:
	var why: String = Stickers.print_block(_print_id())
	_print_button.disabled = why != ""
	_print_pick.disabled = not Stickers.printer_ready()
	if not Stickers.printer_ready():
		_print_state.text = why
		return
	var line: String = "Плёнки в тайнике: %d · краски хватит на листов: %d (+ комплектов: %d)" % [Profile.stash_count(String(Balance.STICKERS.film)),
		Stickers.ink_left(), Profile.stash_count(String(Balance.STICKERS.ink))]
	_print_state.text = line if why == "" else line + "\n" + why


func _print() -> void:
	var why: String = Stickers.print_sticker(_print_id())
	_refresh()
	_status.text = why if why != "" else "Напечатано: %s — лежит в тайнике." % ItemDb.item_name(_print_id())
	if why == "":
		Audio.play_ui("workbench")


func _process(_delta: float) -> void:
	if _inventory_sig != _signature():
		_refresh()


func _refresh() -> void:
	var chosen_uid: String = String(_entry().get("uid", ""))
	var chosen_sticker: String = _sticker_id()
	_inventory_sig = _signature()
	_weapons = Engraver.weapons()
	_owned = Stickers.owned()
	_weapon.clear()
	for row: Dictionary in _weapons:
		var have: int = Stickers.of(row.entry).size()
		_weapon.add_item("%s · %s · наклеек %d / %d" % [ItemDb.item_name(String(row.entry.id)), _place(String(row.where)), have, int(Balance.STICKERS.max)])
		if chosen_uid != "" and String(row.entry.get("uid", "")) == chosen_uid:
			_weapon.select(_weapon.item_count - 1)
	_sticker.clear()
	var pick: int = -1
	for row: Dictionary in _owned:
		_sticker.add_item("%s ×%d · %s" % [ItemDb.item_name(String(row.entry.id)), int(row.entry.get("n", 1)), _place(String(row.where))])
		if pick < 0 and String(row.entry.id) == chosen_sticker:
			pick = _sticker.item_count - 1
	if _sticker.item_count > 0:
		_sticker.select(maxi(pick, 0))
	_refresh_printer()
	_show_weapon()


func _place(role: String) -> String:
	return "снаряжение" if role.begins_with("equip:") else {"stash": "тайник", "backpack": "рюкзак", "pocket": "карман"}.get(role, role)


func _row() -> Dictionary:
	return _weapons[_weapon.selected] if _weapon.selected >= 0 and _weapon.selected < _weapons.size() else {}


func _entry() -> Dictionary:
	return _row().get("entry", {})


func _sticker_id() -> String:
	return String(_owned[_sticker.selected].entry.id) if _sticker != null and _sticker.selected >= 0 and _sticker.selected < _owned.size() else ""


func _site_id() -> String:
	return String(_positions[_site.selected].id) if _site.selected >= 0 and _site.selected < _positions.size() else ""


func _scale_value() -> float:
	return float(WeaponMark.SCALES[clampi(_scale.selected, 0, WeaponMark.SCALES.size() - 1)][0])


## Крупный план образца: наклейка рисуется пару кадров — приближаем, когда появилась.
func _zoom() -> void:
	for frame: int in range(8):
		await get_tree().process_frame
		if not is_inside_tree():
			return
	_view.focus_mark("StickerPreview")


func _show_weapon() -> void:
	var entry: Dictionary = _entry()
	_view.visible = not entry.is_empty()
	for c: Node in _on_weapon.get_children():
		_on_weapon.remove_child(c)
		c.queue_free()
	if entry.is_empty():
		_site.clear()
		_positions = []
		_apply_button.disabled = true
		_status.text = "Нужно собственное оружие."
		return
	var positions: Array[Dictionary] = WeaponMark.positions(String(entry.id))
	if _positions != positions:
		_positions = positions
		_site.clear()
		for pos: Dictionary in _positions:
			_site.add_item(String(pos.name))
		# по умолчанию — левая сторона: её видно у себя в руках от первого лица
		for index: int in range(_positions.size()):
			if int(_positions[index].side) > 0 and Stickers.block(entry, String(_positions[index].id)) == "":
				_site.select(index)
				break
	# что уже наклеено — со снятием
	var stuck: Array = Stickers.of(entry)
	if stuck.is_empty():
		_label(_on_weapon, "Пока ничего.", 14).modulate = Color(1, 1, 1, 0.6)
	for n: int in range(stuck.size()):
		var line: HBoxContainer = HBoxContainer.new()
		line.add_theme_constant_override("separation", 8)
		var pic: TextureRect = TextureRect.new()
		pic.texture = StickerArt.texture(String(stuck[n].get("id", "")), int(stuck[n].get("n", 0)))
		pic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		pic.custom_minimum_size = Vector2(44, 30)
		line.add_child(pic)
		var text: Label = Label.new()
		text.text = Stickers.label(String(entry.id), stuck[n])
		text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		text.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		text.add_theme_font_size_override("font_size", 14)
		line.add_child(text)
		var off: Button = Button.new()
		off.text = "Снять"
		off.tooltip_text = "Снятая наклейка пропадает"
		var which: int = n
		off.pressed.connect(func() -> void: _remove(which))
		line.add_child(off)
		_on_weapon.add_child(line)
	# образец выбранной наклейки на выбранном месте
	var marks: Dictionary = WeaponMark.marks(entry)
	var why: String = ""
	if _sticker_id() == "":
		why = "Наклеек нет — их находят в рейдах."
	elif _site_id() == "":
		why = "Выберите место на оружии."
	else:
		why = Stickers.block(entry, _site_id())
	if why == "":
		var list: Array = (marks.get("stickers", []) as Array).duplicate(true)
		list.append({"id": _sticker_id(), "site": _site_id(), "scale": _scale_value(), "n": 0, "preview": true})
		marks["stickers"] = list
	_apply_button.disabled = why != ""
	_status.text = why
	_view.show_build(String(entry.id), entry.get("mods", {}), WeaponCondition.percent(entry), WeaponMods.mag_state(entry), str(entry) + WeaponMark.key(marks) + str(why == ""), marks)
	var left_side: bool = _site.selected >= 0 and _site.selected < _positions.size() and int(_positions[_site.selected].side) > 0
	_view.set_view("mark_left" if left_side else "mark")


func _apply() -> void:
	var row: Dictionary = _row()
	if row.is_empty() or _sticker.selected < 0 or _sticker.selected >= _owned.size():
		return
	var src: Dictionary = _owned[_sticker.selected]
	WeaponMark.identify(row.entry)
	var why: String = Stickers.apply(String(row.where), int(row.idx), String(row.entry.get("uid", "")), String(src.where), int(src.idx), String(src.entry.id), _site_id(), _scale_value())
	_refresh()
	_status.text = why if why != "" else "Наклеено."
	if why == "":
		Audio.play_ui("workbench")


func _remove(n: int) -> void:
	var row: Dictionary = _row()
	if row.is_empty():
		return
	var why: String = Stickers.remove(String(row.where), int(row.idx), String(row.entry.get("uid", "")), n)
	_refresh()
	_status.text = why if why != "" else "Наклейка снята и выброшена."
