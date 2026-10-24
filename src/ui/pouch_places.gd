class_name PouchPlaces
extends Control
## Полоска мест надетой брони или пояса (docs/design/equip_doll_v2.md, п. 4): место = два полуслота;
## пистолетный подсумок — один полуслот, автоматный — целое место (с левой половины), большой — два соседних
## места из пар брони (armor.pairs_big, отмечены скобкой снизу). Сюда тащат подсумок из сетки (подсветка — встанет
## ли), отсюда — в сетку (снять) или на другое место; двойной клик — снять. Решает окно (сигналы).

signal pouch_from(src: GridView, idx: int, at: int)
signal pouch_moved(from_at: int, to_at: int)
signal pouch_off(at: int)

const HALF_W := 26.0
const H := 36.0

var armor: Dictionary = {}
var _font: Font
var _hover_at: int = -1
var _hover_n: int = 0
var _hover_ok: bool = false


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = " "
	_font = ThemeDB.fallback_font
	custom_minimum_size = Vector2(16.0 * HALF_W, H + 6.0)


func set_armor(e: Dictionary) -> void:
	armor = e
	queue_redraw()


func places() -> int:
	return int(WeaponDb.vest(String(armor.get("id", ""))).get("places", 0)) if not armor.is_empty() else 0


func _half_at(x: float) -> int:
	return clampi(floori(x / HALF_W) + 1, 1, maxi(1, places() * 2))


## Куда встанет подсумок id, если отпустить над полуслотом half: автоматный и большой — с левой половины места.
func _snap(id: String, half: int) -> int:
	if ItemDb.pouch_kind(id) in ["rifle", "big"] and half % 2 == 0:
		return half - 1
	return half


func _draw() -> void:
	var n := places()
	for p in range(n):
		var r := Rect2(float(p) * 2.0 * HALF_W, 0.0, 2.0 * HALF_W, H)
		draw_rect(r.grow(-1.0), Color(0.085, 0.087, 0.092, 0.86))
		draw_rect(r.grow(-1.0), Color(1, 1, 1, 0.12), false, 1.0)
		draw_dashed_line(Vector2(r.get_center().x, 4.0), Vector2(r.get_center().x, H - 4.0), Color(1, 1, 1, 0.1), 1.0, 3.0)
		draw_string(_font, r.position + Vector2(4, 11), str(p + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color(0.5, 0.52, 0.54))
	# пары под большой — скобкой снизу
	for pair: Variant in WeaponDb.vest(String(armor.get("id", ""))).get("pairs_big", []):
		var a := int((pair as Array)[0]) - 1
		var x0 := float(a) * 2.0 * HALF_W + 6.0
		var x1 := float(a + 2) * 2.0 * HALF_W - 6.0
		var y := H + 2.0 + float(a % 2) * 2.0
		draw_line(Vector2(x0, y), Vector2(x1, y), Color(0.95, 0.82, 0.6, 0.3), 1.0)
	for pv: Dictionary in ItemDb.pouch_list(armor):
		var id := String(pv.id)
		var r := Rect2((float(pv.at) - 1.0) * HALF_W, 0.0, float(ItemDb.pouch_half(id)) * HALF_W, H).grow(-3.0)
		var col: Color = GridView.CAT_COLOR.get("armor", Color(0.3, 0.3, 0.3))
		draw_rect(r, col)
		ItemIcons.draw_entry(self, {"id": id, "n": 1}, r.grow(-2.0), false)
		draw_rect(r, Color(1.0, 0.86, 0.6, 0.35), false, 1.0)
		var label: String = {"pistol": "П", "rifle": "авт", "big": "большой"}.get(ItemDb.pouch_kind(id), "")
		draw_string_outline(_font, Vector2(r.position.x + 2, r.end.y - 3), label, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 3, 10, 3, Color(0, 0, 0, 0.75))
		draw_string(_font, Vector2(r.position.x + 2, r.end.y - 3), label, HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 3, 10, Color(0.95, 0.93, 0.88))
	if _hover_at > 0:
		var hr := Rect2((float(_hover_at) - 1.0) * HALF_W, 0.0, float(_hover_n) * HALF_W, H)
		draw_rect(hr, Color(0.3, 0.9, 0.4, 0.3) if _hover_ok else Color(0.95, 0.3, 0.25, 0.3))


func _get_tooltip(at: Vector2) -> String:
	var n := places()
	if n <= 0:
		return "Надень броню или пояс — появятся места под подсумки"
	var half := _half_at(at.x)
	var i := ItemDb.pouch_index_at(armor, half)
	if i >= 0:
		var pid := String((ItemDb.pouch_list(armor)[i] as Dictionary).id)
		return "%s\nПеретащи в сетку — снять, на другое место — переставить; двойной клик — снять" % ItemDb.item_name(pid)
	var pairs: Array[String] = []
	for pair: Variant in WeaponDb.vest(String(armor.get("id", ""))).get("pairs_big", []):
		pairs.append("%d+%d" % [int((pair as Array)[0]), int((pair as Array)[1])])
	return "Место %d, %s половина\nПистолетный — половина места, автоматный — место, большой — два (%s)" % [
		(half + 1) / 2, "левая" if half % 2 == 1 else "правая", ", ".join(pairs) if not pairs.is_empty() else "сюда не встаёт"]


func _gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT and mb.double_click:
		var i := ItemDb.pouch_index_at(armor, _half_at(mb.position.x))
		if i >= 0:
			pouch_off.emit(int((ItemDb.pouch_list(armor)[i] as Dictionary).at))
			accept_event()


func _get_drag_data(at: Vector2) -> Variant:
	var i := ItemDb.pouch_index_at(armor, _half_at(at.x))
	if i < 0:
		return null
	var p: Dictionary = ItemDb.pouch_list(armor)[i]
	GridView.drag_rot = false
	var s := ItemDb.size(String(p.id))
	var pr := ColorRect.new()
	pr.color = Color(0.9, 0.8, 0.5, 0.35)
	pr.size = Vector2(s) * GridView.CELL
	pr.position = -Vector2(GridView.CELL, GridView.CELL) * 0.5
	var holder := Control.new()
	holder.add_child(pr)
	set_drag_preview(holder)
	return {"slot": "pouch:%d" % int(p.at), "id": String(p.id), "idx": -1, "base_r": false, "grab": Vector2i.ZERO, "pouch_at": int(p.at)}


## Что тащат и откуда: [id, номер подсумка на броне (свой) или -1, GridView-источник, индекс в нём].
func _source(data: Variant) -> Array:
	if not data is Dictionary or not (data as Dictionary).has("id"):
		return []
	var d: Dictionary = data
	var id := String(d.id)
	if ItemDb.pouch_cost(id) <= 0.0:
		return []
	if d.has("pouch_at"):
		return [id, ItemDb.pouch_index_at(armor, int(d.pouch_at)), null, -1]
	if not d.has("view"):
		return []
	var src: GridView = GridView.drag_source(d)
	if src == null or src.drag_index(d) < 0:
		return []
	return [id, -1, src, src.drag_index(d)]


func _can_drop_data(at: Vector2, data: Variant) -> bool:
	var s := _source(data)
	if s.is_empty() or places() <= 0:
		_hover_at = -1
		queue_redraw()
		return false
	var id := String(s[0])
	_hover_at = _snap(id, _half_at(at.x))
	_hover_n = ItemDb.pouch_half(id)
	_hover_ok = ItemDb.pouch_fits(armor, id, _hover_at, int(s[1]))
	queue_redraw()
	return true


func _drop_data(at: Vector2, data: Variant) -> void:
	var s := _source(data)
	_hover_at = -1
	queue_redraw()
	if s.is_empty():
		return
	var id := String(s[0])
	var to := _snap(id, _half_at(at.x))
	if not ItemDb.pouch_fits(armor, id, to, int(s[1])):
		return
	if int(s[1]) >= 0:
		pouch_moved.emit(int((data as Dictionary).pouch_at), to)
	else:
		pouch_from.emit(s[2] as GridView, int(s[3]), to)


func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_DRAG_END:
		_hover_at = -1
		queue_redraw()
