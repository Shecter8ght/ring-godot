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
	_site.item_selected.connect(func(_idx: int) -> void: _invalidate(); _show_weapon())
	_label(left, "Лазерная головка", 16)
	_head = OptionButton.new()
	left.add_child(_head)
	_head.item_selected.connect(func(_idx: int) -> void: _invalidate())
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
	_label(left, "Головка рассчитана на три надписи.\nПредпросмотр не расходует ресурс.", 14)
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
	return str(Profile.equipment) + str(Profile.stash) + str(Profile.backpack) + str(Profile.pocket) + Engraver.block()


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
	_invalidate()
	_show_weapon()


func _place(role: String) -> String:
	return "снаряжение" if role.begins_with("equip:") else {"stash": "тайник", "backpack": "рюкзак", "pocket": "карман"}.get(role, role)


func _invalidate() -> void:
	_preview = {}
	_apply_button.disabled = true
	_detail.text = ""
	var reason: String = Engraver.block()
	if reason == "" and _weapons.is_empty():
		reason = "Нужно собственное оружие."
	if reason == "" and _heads.is_empty():
		reason = "Найдите в рейде лазерную головку с оставшимся ресурсом."
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
	var mark: Dictionary = entry.get("engraving", {}) if _preview.is_empty() else _preview
	if not mark.is_empty():
		for index: int in range(_positions.size()):
			if String(_positions[index].id) == String(mark.get("site", "right_1")):
				_site.select(index)
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
	_status.text = "Проверьте написание. После нанесения изменить его нельзя."
	_apply_button.disabled = false
	_show_weapon()


func _apply() -> void:
	if _preview.is_empty() or _weapon.selected < 0 or _head.selected < 0:
		return
	var row: Dictionary = _weapons[_weapon.selected]
	var head: Dictionary = _heads[_head.selected]
	var reason: String = Engraver.apply(String(row.where), int(row.idx), String(row.entry.uid), String(head.where), int(head.idx), String(head.entry.uid), _text.text, _preview)
	if reason != "":
		_status.text = reason
		return
	_refresh()
	_status.text = "Гравировка нанесена. Оружие можно узнать по надписи и номеру."
	Audio.play_ui("workbench")
