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
	draw_rect(r, Color(0.05, 0.055, 0.06, 0.9))
	var border := Color(1, 1, 1, 0.15)
	if _hover == 1:
		border = Color(0.3, 0.9, 0.4, 0.8)
	elif _hover == -1:
		border = Color(0.95, 0.3, 0.25, 0.8)
	draw_rect(r, border, false, 1.5)
	draw_string(_font, Vector2(6, 15), String(Inventory.SLOT_NAMES.get(slot, slot)), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.65, 0.68, 0.7))
	if entry.is_empty():
		return
	var cat := String(ItemDb.item(String(entry.id)).get("cat", "misc"))
	var inner := r.grow(-6)
	inner.position.y += 14
	inner.size.y -= 14
	draw_rect(inner, GridView.CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3)))
	draw_string(_font, inner.position + Vector2(5, 16), ItemDb.label(entry), HORIZONTAL_ALIGNMENT_LEFT, inner.size.x - 8, 13, Color(0.95, 0.93, 0.88))


func _get_tooltip(_at: Vector2) -> String:
	if entry.is_empty():
		return String(Inventory.SLOT_NAMES.get(slot, slot))
	return "%s\n%s ₽" % [ItemDb.label(entry), InventoryUI.money(ItemDb.entry_value(entry))]


func _fits(id: String) -> bool:
	return String(ItemDb.equip(id).get("slot", "")) == slot


func _gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT and mb.double_click and not entry.is_empty():
		unequip_requested.emit()
		accept_event()
	elif mb and mb.pressed and mb.button_index == MOUSE_BUTTON_RIGHT and not entry.is_empty():
		context.emit(mb.global_position)
		accept_event()


## Обвес подходит к оружию в этом слоте.
func _mod_fits(id: String) -> bool:
	return not entry.is_empty() and ItemDb.mod_fits(id, String(entry.id))


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
	var id := String((data as Dictionary).id)
	var ok := _fits(id) or _mod_fits(id)
	_hover = 1 if ok else -1
	queue_redraw()
	return ok


func _drop_data(_at: Vector2, data: Variant) -> void:
	_hover = 0
	queue_redraw()
	var d: Dictionary = data
	if _mod_fits(String(d.id)):
		mod_from.emit(d.view, int(d.idx))
	else:
		equip_from.emit(d.view, int(d.idx))


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_DRAG_END:
		_hover = 0
		queue_redraw()
