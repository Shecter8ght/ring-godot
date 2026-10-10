class_name EngraverPanel
extends HBoxContainer
## Отдельная операция с проверкой текста на модели до необратимого нанесения.

var _weapons: Array[Dictionary] = []
var _heads: Array[Dictionary] = []
var _weapon: OptionButton
var _head: OptionButton
var _site: OptionButton
var _positions: Array[Dictionary] = []
var _text: LineEdit
var _status: Label
var _detail: Label
var _preview_button: Button
var _apply_button: Button
var _view: BuilderView
var _preview: Dictionary = {}
var _inventory_sig: String = ""
var _scale: OptionButton
## Головка: что стоит в станке (общая для группы) и кнопки «вставить» / «вынуть».
var _head_state: Label
var _head_insert: Button
var _head_eject: Button


func _ready() -> void:
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_theme_constant_override("separation", 24)
	var left: VBoxContainer = VBoxContainer.new()
	left.custom_minimum_size.x = 360
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(left)
	_label(left, "ЛАЗЕРНАЯ ГРАВИРОВКА", 22)
	_label(left, "Надпись остаётся на оружии навсегда.\nДата и номер добавляются автоматически.", 16)
	_label(left, "Ваше оружие", 16)
	_weapon = OptionButton.new()
	left.add_child(_weapon)
	_weapon.item_selected.connect(func(_idx: int) -> void: _invalidate(); _show_weapon())
	_label(left, "Место нанесения", 16)
	_site = OptionButton.new()
	left.add_child(_site)
	# выбрал место — сразу крупный план этого места на оружии
	_site.item_selected.connect(func(_idx: int) -> void: _invalidate(); _show_weapon(); _zoom_to_mark())
	_label(left, "Размер надписи", 16)
	_scale = OptionButton.new()
	for row: Array in WeaponMark.SCALES:
		_scale.add_item(String(row[1]))
	_scale.select(1)
	left.add_child(_scale)
	_scale.item_selected.connect(func(_idx: int) -> void: _invalidate(); _show_weapon(); _zoom_to_mark())
	# головка работает только вставленной в станок: она общая для группы и видна на станке всем
	_label(left, "Лазерная головка в станке", 16)
	_head_state = _label(left, "", 16)
	_head = OptionButton.new()
	left.add_child(_head)
	var head_row: HBoxContainer = HBoxContainer.new()
	head_row.add_theme_constant_override("separation", 8)
	left.add_child(head_row)
	_head_insert = Button.new()
	_head_insert.text = "Вставить в станок"
	head_row.add_child(_head_insert)
	_head_insert.pressed.connect(func() -> void:
		if _head.selected < 0 or _head.selected >= _heads.size():
			return
		var row: Dictionary = _heads[_head.selected]
		var why: String = Engraver.insert(String(row.where), int(row.idx), String(row.entry.uid))
		_status.text = why if why != "" else "Головка вставлена в станок."
		_refresh())
	_head_eject = Button.new()
	_head_eject.text = "Вынуть в тайник"
	head_row.add_child(_head_eject)
	_head_eject.pressed.connect(func() -> void:
		var why: String = Engraver.eject()
		_status.text = why if why != "" else "Головка вынута — лежит в тайнике."
		_refresh())
	_label(left, "Надпись · до %d символов" % int(Balance.ENGRAVING.max_text), 16)
	_text = LineEdit.new()
	_text.max_length = int(Balance.ENGRAVING.max_text)
	_text.placeholder_text = "Имя или короткая надпись"
	left.add_child(_text)
	_text.text_changed.connect(func(_value: String) -> void: _invalidate(); _show_weapon())
	_preview_button = Button.new()
	_preview_button.text = "Проверить надпись на оружии"
	left.add_child(_preview_button)
	_preview_button.pressed.connect(_make_preview)
	_detail = _label(left, "", 16)
	_apply_button = Button.new()
	_apply_button.text = "Нанести навсегда · 1 использование"
	_apply_button.disabled = true
	left.add_child(_apply_button)
	_apply_button.pressed.connect(_apply)
	_status = _label(left, "", 16)
	_status.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_label(left, "Головка рассчитана на три надписи и работает только в станке.\nПредпросмотр не расходует ресурс.", 14)
	var right: VBoxContainer = VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_child(right)
	_view = BuilderView.new()
	_view.custom_minimum_size = Vector2(440, 320)
	_view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.add_child(_view)
	var sides: HBoxContainer = HBoxContainer.new()
	right.add_child(sides)
	for title: String in ["Сбоку", "Общий вид", "Надпись крупно"]:
		var button: Button = Button.new()
		button.text = title
		button.pressed.connect(func() -> void:
			if title == "Надпись крупно":
				_view.focus_mark()
			elif title == "Сбоку":
				_view.set_view("mark_left" if _site.selected >= 0 and int(_positions[_site.selected].side) > 0 else "mark")
			else:
				_view.set_view("quarter"))
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
	return str(Profile.equipment) + str(Profile.stash) + str(Profile.backpack) + str(Profile.pocket) + Engraver.block() + str(Engraver.installed())


func _process(_delta: float) -> void:
	if _inventory_sig != _signature():
		_refresh()


func _refresh() -> void:
	var selected_uid: String = String(_entry().get("uid", ""))
	var selected_head: String = String(_heads[_head.selected].entry.get("uid", "")) if _head.selected >= 0 and _head.selected < _heads.size() else ""
	_inventory_sig = _signature()
	_weapons = Engraver.weapons()
	_heads = Engraver.heads()
	_weapon.clear()
	_head.clear()
	for row: Dictionary in _weapons:
		var marked: bool = not (row.entry.get("engraving", {}) as Dictionary).is_empty()
		_weapon.add_item(ItemDb.item_name(String(row.entry.id)) + " · " + _place(String(row.where)) + (" · уже подписано" if marked else ""))
		if String(row.entry.get("uid", "")) == selected_uid:
			_weapon.select(_weapon.item_count - 1)
	for row: Dictionary in _heads:
		_head.add_item("Головка · %d / %d · %s" % [int(row.entry.charges), int(Balance.ENGRAVING.charges), _place(String(row.where))])
		if String(row.entry.get("uid", "")) == selected_head:
			_head.select(_head.item_count - 1)
	# что в станке: заряды и кто может вставить / вынуть
	var inst: Dictionary = Engraver.installed()
	if inst.is_empty():
		_head_state.text = "Пусто — вставьте головку из своих вещей." if not _heads.is_empty() else "Пусто. Головки находят в рейдах."
	else:
		_head_state.text = "Стоит головка: осталось %d из %d надписей." % [int(inst.get("charges", 0)), int(Balance.ENGRAVING.charges)]
	_head.visible = inst.is_empty() and not _heads.is_empty()
	_head_insert.visible = inst.is_empty() and not _heads.is_empty()
	_head_eject.visible = not inst.is_empty()
	_invalidate()
	_show_weapon()


## Крупный план места нанесения: метка рисуется несколько кадров — приближаем, когда появилась.
func _zoom_to_mark() -> void:
	for frame: int in range(10):
		await get_tree().process_frame
		if not is_inside_tree():
			return
	_view.focus_mark()


func _place(role: String) -> String:
	return "снаряжение" if role.begins_with("equip:") else {"stash": "тайник", "backpack": "рюкзак", "pocket": "карман"}.get(role, role)


func _invalidate() -> void:
	_preview = {}
	_apply_button.disabled = true
	_detail.text = ""
	var reason: String = Engraver.block()
	if reason == "" and _weapons.is_empty():
		reason = "Нужно собственное оружие."
	if reason == "" and Engraver.installed().is_empty():
		reason = "Вставьте лазерную головку в станок." if not _heads.is_empty() else "Найдите в рейде лазерную головку и вставьте её в станок."
	if reason == "" and int(Engraver.installed().get("charges", 0)) <= 0:
		reason = "Головка в станке исчерпана — выньте её."
	if reason == "" and not (_entry().get("engraving", {}) as Dictionary).is_empty():
		reason = "На этом оружии уже есть постоянная надпись."
	_status.text = reason
	_preview_button.disabled = reason != ""
	_text.editable = reason == ""


func _entry() -> Dictionary:
	return _weapons[_weapon.selected].entry if _weapon.selected >= 0 and _weapon.selected < _weapons.size() else {}


func _show_weapon() -> void:
	var entry: Dictionary = _entry()
	_view.visible = not entry.is_empty()
	if entry.is_empty():
		_site.clear()
		return
	var positions: Array[Dictionary] = WeaponMark.positions(String(entry.id))
	if _positions != positions:
		_positions = positions
		_site.clear()
		for row: Dictionary in _positions:
			_site.add_item(String(row.name))
		# по умолчанию — левая сторона: её видно у себя в руках от первого лица
		for index: int in range(_positions.size()):
			if int(_positions[index].side) > 0:
				_site.select(index)
				break
	var mark: Dictionary = entry.get("engraving", {}) if _preview.is_empty() else _preview
	if not mark.is_empty():
		for index: int in range(_positions.size()):
			if String(_positions[index].id) == String(mark.get("site", "right_1")):
				_site.select(index)
	elif _site.selected >= 0 and _site.selected < _positions.size():
		# надписи ещё нет — образец на выбранном месте и в выбранном размере: видно, куда и как ляжет
		var sample: String = WeaponMark.clean_text(_text.text)
		mark = WeaponMark.make(entry, sample if sample != "" else "ОБРАЗЕЦ", String(_positions[_site.selected].id))
		mark["scale"] = _scale_value()
	_site.disabled = not (entry.get("engraving", {}) as Dictionary).is_empty()
	_view.show_build(String(entry.id), entry.get("mods", {}), WeaponCondition.percent(entry), WeaponMods.mag_state(entry), str(entry) + WeaponMark.key(mark), mark)
	_view.set_view("mark_left" if _site.selected >= 0 and int(_positions[_site.selected].side) > 0 else "mark")
	if not mark.is_empty():
		_detail.text = "«%s»\n%s · № %s" % [String(mark.text), String(mark.date), String(mark.serial)]


func _make_preview() -> void:
	var clean: String = WeaponMark.clean_text(_text.text)
	if clean == "":
		_status.text = "Введите надпись."
		return
	if _site.selected < 0 or _site.selected >= _positions.size():
		_status.text = "Выберите место нанесения."
		return
	_preview = WeaponMark.make(_entry(), clean, String(_positions[_site.selected].id))
	_preview["scale"] = _scale_value()
	_status.text = "Проверьте написание. После нанесения изменить его нельзя."
	_apply_button.disabled = false
	_show_weapon()


func _scale_value() -> float:
	return float(WeaponMark.SCALES[clampi(_scale.selected, 0, WeaponMark.SCALES.size() - 1)][0])


func _apply() -> void:
	if _preview.is_empty() or _weapon.selected < 0:
		return
	var row: Dictionary = _weapons[_weapon.selected]
	var reason: String = Engraver.apply_installed(String(row.where), int(row.idx), String(row.entry.uid), _text.text, _preview)
	if reason != "":
		_status.text = reason
		return
	_refresh()
	_status.text = "Гравировка нанесена. Оружие можно узнать по надписи и номеру."
	Audio.play_ui("workbench")
