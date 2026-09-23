class_name GridView
extends Control
## Ячеистая сетка предметов (рюкзак, тайник, лут): предмет — прямоугольник своего размера
## (ItemDb.size), стопка — число в углу, у брони — полоска прочности. Мышью: тащить (R — повернуть
## на лету), двойной клик — действие по умолчанию, правая кнопка — меню действий, наведение —
## подсказка с ценой. Сама ничего не меняет: сообщает сигналами, решает окно (профиль или хост).
##
## auto_layout — список без мест (лут): предметы раскладываются для показа по порядку.

signal dropped(src: GridView, src_idx: int, x: int, y: int, r: bool)
signal slot_dropped(slot: String, x: int, y: int, r: bool)
signal activated(idx: int)
signal context(idx: int, screen_pos: Vector2)
signal quick_move(idx: int)

const CELL := 46.0
const CAT_COLOR := {
	"weapon": Color(0.36, 0.3, 0.24), "ammo": Color(0.42, 0.36, 0.18), "armor": Color(0.26, 0.33, 0.27),
	"med": Color(0.45, 0.22, 0.22), "food": Color(0.33, 0.35, 0.22), "tech": Color(0.22, 0.3, 0.38),
	"value": Color(0.45, 0.38, 0.14), "barter": Color(0.34, 0.3, 0.3), "tools": Color(0.3, 0.3, 0.33),
	"intel": Color(0.3, 0.3, 0.4), "key": Color(0.5, 0.42, 0.12), "mod": Color(0.25, 0.28, 0.33),
	"throw": Color(0.3, 0.35, 0.25),
}
## Поворот того, что сейчас тащат (R во время перетаскивания) — общий на все сетки.
static var drag_rot: bool = false
static var _drag_preview: Control

var grid: Vector2i = Vector2i(6, 5)
var items: Array = []
var auto_layout: bool = false
## Метка для окна: чья это сетка ("stash", "backpack", "loot").
var role: String = ""

var _layout: Array = []   # [x, y, r] на запись (при auto_layout — вычисленные)
var _hover: Vector2i = Vector2i(-1, -1)
var _hover_size: Vector2i = Vector2i.ONE
var _hover_ok: bool = false
var _font: Font


func _init(p_grid: Vector2i = Vector2i(6, 5), p_role: String = "") -> void:
	grid = p_grid
	role = p_role
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = " "
	_font = ThemeDB.fallback_font


func set_items(list: Array) -> void:
	items = list
	_relayout()
	queue_redraw()


func _relayout() -> void:
	_layout.clear()
	if not auto_layout:
		for it in items:
			_layout.append([int(it.get("x", 0)), int(it.get("y", 0)), bool(it.get("r", false))])
		custom_minimum_size = Vector2(grid) * CELL + Vector2.ONE
		return
	# лут: раскладка для показа, сетка растёт вниз
	var rows := grid.y
	var tmp: Array = []
	for it in items:
		var e: Dictionary = {"id": it.id, "n": 1}
		var spot := Vector3i(-1, -1, 0)
		while spot.x < 0 and rows <= 40:
			spot = ItemDb.find_spot(ItemDb.occupancy(tmp, Vector2i(grid.x, rows)), Vector2i(grid.x, rows), String(it.id))
			if spot.x < 0:
				rows += 1
		e.x = spot.x
		e.y = spot.y
		e.r = spot.z == 1
		tmp.append(e)
		_layout.append([spot.x, spot.y, spot.z == 1])
	grid = Vector2i(grid.x, rows)
	custom_minimum_size = Vector2(grid) * CELL + Vector2.ONE


func _size_of(i: int) -> Vector2i:
	var s := ItemDb.size(String(items[i].id))
	return Vector2i(s.y, s.x) if bool(_layout[i][2]) else s


func _rect_of(i: int) -> Rect2:
	var s := _size_of(i)
	return Rect2(Vector2(int(_layout[i][0]), int(_layout[i][1])) * CELL, Vector2(s) * CELL)


func index_at(pos: Vector2) -> int:
	for i in range(items.size()):
		if _rect_of(i).has_point(pos):
			return i
	return -1


# ---------------------------------------------------------------- рисование

func _draw() -> void:
	var bg := Rect2(Vector2.ZERO, Vector2(grid) * CELL)
	draw_rect(bg, Color(0.05, 0.055, 0.06, 0.9))
	for x in range(grid.x + 1):
		draw_line(Vector2(x * CELL, 0), Vector2(x * CELL, grid.y * CELL), Color(1, 1, 1, 0.07))
	for y in range(grid.y + 1):
		draw_line(Vector2(0, y * CELL), Vector2(grid.x * CELL, y * CELL), Color(1, 1, 1, 0.07))
	for i in range(items.size()):
		if int(_layout[i][0]) < 0:
			continue
		var it: Dictionary = items[i]
		var r := _rect_of(i).grow(-1.5)
		var cat := String(ItemDb.item(String(it.id)).get("cat", "misc"))
		draw_rect(r, CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3)))
		draw_rect(r, Color(1, 1, 1, 0.18), false, 1.0)
		# в маленькой клетке — короткая подпись (калибр, «Бинт»), полное имя — в подсказке
		var name := ItemDb.item_name(String(it.id))
		if r.size.x < 60:
			name = String(ItemDb.item(String(it.id)).get("short", name))
		var fs := 12 if r.size.x > 60 else 11
		draw_string(_font, r.position + Vector2(4, fs + 2), name, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 6, fs, Color(0.95, 0.93, 0.88))
		if int(it.n) > 1:
			var t := str(int(it.n))
			var w := _font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
			draw_string(_font, r.end - Vector2(w + 4, 4), t, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1.0, 0.92, 0.6))
		if it.has("dur"):
			var mx := float(ItemDb.equip(String(it.id)).get("durability", 1))
			var k := clampf(float(it.dur) / maxf(1.0, mx), 0.0, 1.0)
			draw_rect(Rect2(r.position + Vector2(3, r.size.y - 6), Vector2((r.size.x - 6) * k, 3)), Color(0.4, 0.85, 0.4).lerp(Color(0.9, 0.3, 0.2), 1.0 - k))
		if it.has("mods") and not (it.mods as Dictionary).is_empty():
			draw_string(_font, r.position + Vector2(4, r.size.y - 5), "+%d" % (it.mods as Dictionary).size(), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.6, 0.85, 1.0))
	if _hover.x >= 0:
		var hr := Rect2(Vector2(_hover) * CELL, Vector2(_hover_size) * CELL)
		draw_rect(hr, Color(0.3, 0.9, 0.4, 0.28) if _hover_ok else Color(0.95, 0.3, 0.25, 0.28))


func _get_tooltip(at: Vector2) -> String:
	var i := index_at(at)
	if i < 0:
		return ""
	var e: Dictionary = items[i]
	var t := ItemDb.label(e)
	if int(e.n) > 1:
		t += "  ×%d" % int(e.n)
	return "%s\n%s ₽" % [t, InventoryUI.money(ItemDb.entry_value(e))]


# ---------------------------------------------------------------- мышь

func _gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb == null or not mb.pressed:
		return
	var i := index_at(mb.position)
	if i < 0:
		return
	if mb.button_index == MOUSE_BUTTON_LEFT and mb.double_click:
		activated.emit(i)
		accept_event()
	elif mb.button_index == MOUSE_BUTTON_LEFT and mb.ctrl_pressed:
		quick_move.emit(i)
		accept_event()
	elif mb.button_index == MOUSE_BUTTON_RIGHT:
		context.emit(i, mb.global_position)
		accept_event()


func _get_drag_data(at: Vector2) -> Variant:
	var i := index_at(at)
	if i < 0:
		return null
	drag_rot = bool(_layout[i][2])
	var s := _size_of(i)
	# за какую ячейку предмета взяли — чтобы при отпускании он встал так же под курсором
	var grab := Vector2i((at - Vector2(int(_layout[i][0]), int(_layout[i][1])) * CELL) / CELL)
	var p := ColorRect.new()
	p.color = Color(0.9, 0.8, 0.5, 0.35)
	p.size = Vector2(s) * CELL
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := Label.new()
	l.text = ItemDb.item_name(String(items[i].id))
	l.add_theme_font_size_override("font_size", 12)
	p.add_child(l)
	var holder := Control.new()
	holder.add_child(p)
	p.position = -Vector2(grab) * CELL - Vector2(CELL, CELL) * 0.5
	_drag_preview = p
	set_drag_preview(holder)
	return {"view": self, "idx": i, "id": String(items[i].id), "base_r": bool(_layout[i][2]), "grab": grab}


## R во время перетаскивания — повернуть.
func _input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k and k.pressed and not k.echo and k.physical_keycode == KEY_R and get_viewport().gui_is_dragging():
		drag_rot = not drag_rot
		if is_instance_valid(_drag_preview):
			_drag_preview.size = Vector2(_drag_preview.size.y, _drag_preview.size.x)
		get_viewport().set_input_as_handled()


func _cell_for(at: Vector2, data: Dictionary) -> Vector2i:
	var grab: Vector2i = data.get("grab", Vector2i.ZERO)
	if drag_rot != bool(data.get("base_r", false)):
		grab = Vector2i(grab.y, grab.x)
	return Vector2i(floori(at.x / CELL), floori(at.y / CELL)) - grab


func _can_drop_data(at: Vector2, data: Variant) -> bool:
	if not (data is Dictionary) or not (data as Dictionary).has("id"):
		return false
	var d: Dictionary = data
	var s := ItemDb.size(String(d.id))
	if drag_rot:
		s = Vector2i(s.y, s.x)
	var c := _cell_for(at, d)
	_hover = c
	_hover_size = s
	if auto_layout:
		_hover_ok = true
	else:
		var skip: int = int(d.idx) if d.get("view") == self else -1
		var occ := ItemDb.occupancy(items, grid, skip)
		_hover_ok = ItemDb.fits_at(occ, grid, c.x, c.y, s)
		# на такую же неполную стопку — тоже можно
		if not _hover_ok:
			var j := index_at(at)
			_hover_ok = j >= 0 and j != skip and String(items[j].id) == String(d.id)
	queue_redraw()
	return true


func _drop_data(at: Vector2, data: Variant) -> void:
	var d: Dictionary = data
	var c := _cell_for(at, d)
	var j := index_at(at)
	# бросили на такую же стопку — целимся в её угол (слияние)
	if j >= 0 and String(items[j].id) == String(d.id) and not (d.get("view") == self and j == int(d.idx)):
		c = Vector2i(int(_layout[j][0]), int(_layout[j][1]))
	_hover = Vector2i(-1, -1)
	queue_redraw()
	if d.has("slot"):
		slot_dropped.emit(String(d.slot), c.x, c.y, drag_rot)
	else:
		dropped.emit(d.view, int(d.idx), c.x, c.y, drag_rot)


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_DRAG_END:
		_hover = Vector2i(-1, -1)
		queue_redraw()
