class_name SlotView
extends Control
## Ячейка снаряжения (основное, пистолет, броня, шлем): в неё тащат подходящий предмет из сетки,
## из неё — обратно в сетку (снять). Двойной клик — снять. Решает окно (сигналы).

signal equip_from(src: GridView, idx: int)
signal unequip_requested
## Обвес бросили на оружие в слоте (поставить), правая кнопка по слоту (меню обвесов).
signal mod_from(src: GridView, idx: int)
signal context(screen_pos: Vector2)

var slot: String = ""
var entry: Dictionary = {}
var _font: Font
var _hover: int = 0   # 1 — подходит, -1 — нет


func _init(p_slot: String = "") -> void:
	slot = p_slot
	custom_minimum_size = Vector2(4.0 * GridView.CELL, 2.0 * GridView.CELL)
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = " "
	_font = ThemeDB.fallback_font


func set_entry(e: Dictionary) -> void:
	entry = e
	queue_redraw()


func _draw() -> void:
	var r := Rect2(Vector2.ZERO, size)
	var slot_name := String(Inventory.SLOT_NAMES.get(slot, slot))
	draw_rect(r, Color(0.085, 0.087, 0.092, 0.86))
	var border := Color(1, 1, 1, 0.1)
	if _hover == 1:
		border = Color(0.3, 0.9, 0.4, 0.8)
	elif _hover == -1:
		border = Color(0.95, 0.3, 0.25, 0.8)
	if entry.is_empty():
		# пустой слот: только название по центру, приглушённо — не плита с рамкой
		draw_rect(r, border, false, 1.0)
		draw_string(_font, Vector2(0, size.y * 0.5 + 4.0), slot_name, HORIZONTAL_ALIGNMENT_CENTER, size.x, 12, Color(0.46, 0.48, 0.5))
		return
	var cat := String(ItemDb.item(String(entry.id)).get("cat", "misc"))
	var col: Color = GridView.CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3))
	var has_icon := ItemIcons.get_icon(String(entry.id)) != null
	draw_rect(r, ItemIcons.backdrop(col) if has_icon else col)
	# предмет — во весь слот; подписи поверх: чей слот (мелко, сверху) и что надето (снизу)
	var art := r.grow(-3.0)
	art.size.y -= 12.0
	ItemIcons.draw_entry(self, entry, art, false)
	draw_rect(r, border if _hover != 0 else Color(1.0, 0.86, 0.6, 0.28), false, 1.0)
	draw_string(_font, Vector2(5, 12), slot_name, HORIZONTAL_ALIGNMENT_LEFT, size.x - 8, 10, Color(1, 1, 1, 0.5))
	var fs := 11 if size.x < 150.0 else 13
	var label := ItemDb.label(entry)
	var at := Vector2(4, size.y - 5.0)
	draw_rect(Rect2(0, size.y - float(fs) - 7.0, size.x, float(fs) + 7.0), Color(0, 0, 0, 0.45))
	draw_string(_font, at, label, HORIZONTAL_ALIGNMENT_LEFT, size.x - 8, fs, Color(0.95, 0.93, 0.88))


func _get_tooltip(_at: Vector2) -> String:
	if entry.is_empty():
		return String(Inventory.SLOT_NAMES.get(slot, slot))
	return "%s\nПродать: %s ₽" % [ItemDb.label(entry), InventoryUI.money(Profile.sell_price(entry))]


func _fits(id: String) -> bool:
	return ItemDb.slot_ok(id, slot)


func _gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT and mb.double_click and not entry.is_empty():
		unequip_requested.emit()
		accept_event()
	elif mb and mb.pressed and mb.button_index == MOUSE_BUTTON_RIGHT and not entry.is_empty():
		context.emit(mb.global_position)
		accept_event()


## Предмет встаёт в то, что в этом слоте: обвес на оружие, магазин в оружие, плита в плитоносец.
func _mod_fits(id: String) -> bool:
	if entry.is_empty():
		return false
	var eid := String(entry.id)
	if WeaponDb.is_weapon(eid):
		return ItemDb.mod_fits(id, entry) or WeaponDb.mag_fits(eid, id)
	return not WeaponDb.plate(id).is_empty() and entry.has("plates")


func _get_drag_data(_at: Vector2) -> Variant:
	if entry.is_empty():
		return null
	GridView.drag_rot = false
	var s := ItemDb.size(String(entry.id))
	var p := ColorRect.new()
	p.color = Color(0.9, 0.8, 0.5, 0.35)
	p.size = Vector2(s) * GridView.CELL
	p.position = -Vector2(GridView.CELL, GridView.CELL) * 0.5
	var holder := Control.new()
	holder.add_child(p)
	set_drag_preview(holder)
	return {"slot": slot, "id": String(entry.id), "idx": -1, "base_r": false, "grab": Vector2i.ZERO}


func _can_drop_data(_at: Vector2, data: Variant) -> bool:
	if not (data is Dictionary) or not (data as Dictionary).has("view"):
		return false
	var source: GridView = GridView.drag_source(data)
	if source == null or source.drag_index(data) < 0:
		_hover = 0
		queue_redraw()
		return false
	var id := String((data as Dictionary).id)
	var ok := _fits(id) or _mod_fits(id)
	_hover = 1 if ok else -1
	queue_redraw()
	return ok


func _drop_data(_at: Vector2, data: Variant) -> void:
	_hover = 0
	queue_redraw()
	if not (data is Dictionary):
		return
	var d: Dictionary = data
	var source: GridView = GridView.drag_source(d)
	if source == null:
		return
	var index: int = source.drag_index(d)
	if index < 0 or not (_fits(String(d.id)) or _mod_fits(String(d.id))):
		return
	if _mod_fits(String(d.id)):
		mod_from.emit(source, index)
	else:
		equip_from.emit(source, index)


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_DRAG_END:
		_hover = 0
		queue_redraw()
