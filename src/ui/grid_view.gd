class_name GridView
extends Control
## Ячеистая сетка предметов (рюкзак, тайник, лут): предмет — прямоугольник своего размера
## (ItemDb.size), стопка — число в углу, у брони — полоска прочности, у магазина — ПОЛН / ПУСТ (после
## проверки — оценка). Идёт поштучная операция (MagOps: пометка "op") — круг заполненности и счёт.
## Мышью: тащить (R — повернуть на лету), двойной клик — действие по умолчанию, правая кнопка — меню
## действий, наведение — подсказка с ценой. Патроны на подходящий магазин, плиту на жилет со
## свободным гнездом — dropped_on. Сама ничего не меняет: сообщает сигналами, решает окно.
##
## auto_layout — список без мест (лут): предметы раскладываются для показа по порядку.

signal dropped(src: GridView, src_idx: int, x: int, y: int, r: bool)
signal slot_dropped(slot: String, x: int, y: int, r: bool)
signal activated(idx: int)
signal context(idx: int, screen_pos: Vector2)
signal quick_move(idx: int)
## Патроны бросили на подходящий магазин, плиту — на жилет со свободным гнездом (решает окно).
signal dropped_on(src: GridView, src_idx: int, dst_idx: int)

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
	# своя копия списка (записи — те же): в убежище список профиля меняется на месте, а раскладка
	# считается здесь — до перестройки окна сетка рисует то, что ей дали
	items = list.duplicate()
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
		var col: Color = CAT_COLOR.get(cat, Color(0.3, 0.3, 0.3))
		# с иконкой — тёмная подложка цвета категории, без неё — плашка ярче
		var has_icon := ItemIcons.get_icon(String(it.id)) != null
		draw_rect(r, ItemIcons.backdrop(col) if has_icon else col)
		ItemIcons.draw(self, String(it.id), r.grow(-3.0), bool(_layout[i][2]))
		draw_rect(r, Color(1, 1, 1, 0.18), false, 1.0)
		# в маленькой клетке — короткая подпись (калибр, «Бинт»), полное имя — в подсказке
		var name := ItemDb.item_name(String(it.id))
		if r.size.x < 60:
			name = String(ItemDb.item(String(it.id)).get("short", name))
		var fs := 11 if has_icon else (12 if r.size.x > 60 else 11)
		draw_string_outline(_font, r.position + Vector2(4, fs + 2), name, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 6, fs, 3, Color(0, 0, 0, 0.7))
		draw_string(_font, r.position + Vector2(4, fs + 2), name, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 6, fs, Color(0.95, 0.93, 0.88))
		if int(it.n) > 1:
			var t := str(int(it.n))
			var w := _font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
			draw_string_outline(_font, r.end - Vector2(w + 4, 4), t, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, 3, Color(0, 0, 0, 0.8))
			draw_string(_font, r.end - Vector2(w + 4, 4), t, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1.0, 0.92, 0.6))
		if it.has("dur"):
			var mx := float(ItemDb.equip(String(it.id)).get("durability", 1))
			var k := clampf(float(it.dur) / maxf(1.0, mx), 0.0, 1.0)
			draw_rect(Rect2(r.position + Vector2(3, r.size.y - 6), Vector2((r.size.x - 6) * k, 3)), Color(0.4, 0.85, 0.4).lerp(Color(0.9, 0.3, 0.2), 1.0 - k))
		if it.has("mods") and not (it.mods as Dictionary).is_empty():
			draw_string(_font, r.position + Vector2(4, r.size.y - 5), "+%d" % (it.mods as Dictionary).size(), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.6, 0.85, 1.0))
		if it.get("op") is Dictionary:
			_draw_op(r, it, it.op as Dictionary)
		elif it.has("rounds"):
			# сколько внутри — не видно: полный / пустой, после проверки — оценка
			var tag := Gear.mag_tag(it)
			if tag != "":
				var tc := Color(0.55, 0.9, 0.55) if tag == "ПОЛН" else (Color(0.62, 0.62, 0.6) if tag == "ПУСТ" else Color(1.0, 0.82, 0.45))
				draw_string_outline(_font, r.position + Vector2(4, r.size.y - 5), tag, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 6, 11, 3, Color(0, 0, 0, 0.8))
				draw_string(_font, r.position + Vector2(4, r.size.y - 5), tag, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 6, 11, tc)
	if _hover.x >= 0:
		var hr := Rect2(Vector2(_hover) * CELL, Vector2(_hover_size) * CELL)
		draw_rect(hr, Color(0.3, 0.9, 0.4, 0.28) if _hover_ok else Color(0.95, 0.3, 0.25, 0.28))


## Идёт поштучная операция: круг — заполненность магазина (или сколько плит осталось), в центре —
## счёт: снаряжают заведомо пустой — сколько уже внутри; иначе — сколько добавили / вынули.
func _draw_op(r: Rect2, it: Dictionary, op: Dictionary) -> void:
	var c := r.get_center()
	var rad := minf(r.size.x, r.size.y) * 0.36
	draw_circle(c, rad + 4.0, Color(0, 0, 0, 0.6))
	var frac := 0.0
	var label := ""
	if it.has("rounds"):
		var n := int(it.rounds)
		frac = float(n) / float(maxi(1, MagOps.capacity(it)))
		var s := int(op.get("s", 0))
		if String(op.get("k", "")) == "load":
			label = str(n) if bool(op.get("known", false)) else "+%d" % (n - s)
		else:
			label = "−%d" % (s - n)
	else:
		var left := (it.get("plates", {}) as Dictionary).size()
		frac = float(left) / float(maxi(1, int(op.get("s", 1))))
		label = str(left)
	draw_arc(c, rad, 0.0, TAU, 48, Color(1, 1, 1, 0.16), 3.0, true)
	if frac > 0.0:
		draw_arc(c, rad, -PI * 0.5, -PI * 0.5 + TAU * frac, 48, Color(1.0, 0.8, 0.38), 3.5, true)
	var w := _font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
	draw_string(_font, c + Vector2(-w * 0.5, 5.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1.0, 0.95, 0.8))


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
	var tex := ItemIcons.get_icon(String(items[i].id))
	if tex:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.set_anchors_preset(Control.PRESET_FULL_RECT)
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		p.add_child(tr)
	else:
		var l := Label.new()
		l.text = ItemDb.item_name(String(items[i].id))
		l.add_theme_font_size_override("font_size", 12)
		p.add_child(l)
	var holder := Control.new()
	holder.add_child(p)
	p.position = -Vector2(grab) * CELL - Vector2(CELL, CELL) * 0.5
	_drag_preview = p
	set_drag_preview(holder)
	return {"view": self, "idx": i, "id": String(items[i].id), "origin": Vector2i(_layout[i][0], _layout[i][1]), "base_r": bool(_layout[i][2]), "grab": grab}


## Сетка могла исчезнуть при закрытии окна. Освобождённый Object нельзя приводить к GridView.
static func drag_source(data: Dictionary) -> GridView:
	var source: Variant = data.get("view")
	if not is_instance_valid(source):
		return null
	if not (source is GridView):
		return null
	if source.is_queued_for_deletion():
		return null
	return source as GridView


## Поштучная зарядка убирает пустые стопки и сдвигает индексы. Ищем взятый предмет по ячейке.
func drag_index(data: Dictionary) -> int:
	var id: String = String(data.get("id", ""))
	if data.has("origin"):
		var origin: Vector2i = data.origin
		for index: int in range(items.size()):
			if String(items[index].id) == id and Vector2i(_layout[index][0], _layout[index][1]) == origin:
				return index
		return -1
	var index: int = int(data.get("idx", -1))
	return index if index >= 0 and index < items.size() and String(items[index].id) == id else -1


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
	var d: Dictionary = data.duplicate()
	var source: GridView = drag_source(d)
	if not d.has("slot"):
		if source == null or source.drag_index(d) < 0:
			_hover = Vector2i(-1, -1)
			queue_redraw()
			return false
		d.idx = source.drag_index(d)
	var s := ItemDb.size(String(d.id))
	if drag_rot:
		s = Vector2i(s.y, s.x)
	var c := _cell_for(at, d)
	_hover = c
	_hover_size = s
	if auto_layout:
		_hover_ok = true
	else:
		var skip: int = int(d.idx) if source == self else -1
		var occ := ItemDb.occupancy(items, grid, skip)
		_hover_ok = ItemDb.fits_at(occ, grid, c.x, c.y, s)
		# на такую же неполную стопку — тоже можно; патроны — на магазин (снарядить)
		if not _hover_ok:
			var j := index_at(at)
			_hover_ok = j >= 0 and j != skip and (String(items[j].id) == String(d.id) or _fits_into(d, j))
	queue_redraw()
	return true


func _drop_data(at: Vector2, data: Variant) -> void:
	if not (data is Dictionary) or not data.has("id"):
		return
	var d: Dictionary = data.duplicate()
	var source: GridView = drag_source(d)
	if not d.has("slot"):
		if source == null or source.drag_index(d) < 0:
			return
		d.idx = source.drag_index(d)
	var c := _cell_for(at, d)
	var j := index_at(at)
	# бросили на такую же стопку — целимся в её угол (слияние)
	if j >= 0 and String(items[j].id) == String(d.id) and not (source == self and j == int(d.idx)):
		c = Vector2i(int(_layout[j][0]), int(_layout[j][1]))
	_hover = Vector2i(-1, -1)
	queue_redraw()
	if j >= 0 and not d.has("slot") and _fits_into(d, j) and not (source == self and j == int(d.idx)):
		dropped_on.emit(source, int(d.idx), j)
		return
	if d.has("slot"):
		slot_dropped.emit(String(d.slot), c.x, c.y, drag_rot)
	else:
		dropped.emit(source, int(d.idx), c.x, c.y, drag_rot)


## Тащат патроны, а под курсором — подходящий неполный магазин; плиту — жилет со свободным гнездом.
func _fits_into(d: Dictionary, j: int) -> bool:
	if drag_source(d) == null or j < 0 or j >= items.size():
		return false
	var t: Dictionary = items[j]
	var id := String(d.id)
	if not WeaponDb.ammo(id).is_empty() and t.has("rounds"):
		return MagOps.ammo_fits(t, id) and int(t.rounds) < MagOps.capacity(t)
	if not WeaponDb.plate(id).is_empty() and t.has("plates"):
		for s in WeaponDb.vest(String(t.id)).get("plates", []):
			if not (t.plates as Dictionary).has(s):
				return true
	return false


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_DRAG_END:
		_hover = Vector2i(-1, -1)
		queue_redraw()
