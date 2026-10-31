class_name RegionMapView
extends Control
## Схема района в окне «План рейда» (владелец 2026-10-31, «Карта региона»): убежище и участки маршрутов на одной
## схеме — снимок участка сверху (assets/maps, тот же, что у RaidMapPreview) по его границе и в его масштабе, на месте
## из data/region_map.json; пути от убежища к ближайшему заходу участка, ж/д насыпь, дороги, кордон и город за ним,
## лес и частный сектор. Выбранный маршрут — акцентом, закрытый — серым; этажи ТЦ — плашками у ТЦ. Клик по открытому
## участку — picked(id): окно выбирает маршрут и показывает его план. Раскладку владелец принял 2026-10-31 (data/region_map.json).

signal picked(id: String)

const DATA_PATH := "res://data/region_map.json"
const GROUND := Color("2b2f2c")
const FOREST := Color(0.15, 0.24, 0.16, 0.42)
const HOUSE := Color("575b5c")
const CITY := Color("3a3e44")
const CITY_LIT := Color(0.95, 0.8, 0.5, 0.6)
const RAIL := Color("17181b")
const RAIL_BED := Color(0.8, 0.8, 0.77)
const ROAD := Color(0.62, 0.62, 0.58, 0.7)
const CORDON := Color("d9502e")
const PATH := Color(1, 1, 1, 0.82)
const CLOSED := Color(0.56, 0.57, 0.59)
const LABEL_BG := Color(0.07, 0.08, 0.09, 0.8)
const TERRAIN_TEXT := Color(0.8, 0.82, 0.78, 0.5)
## Шаг сетки кварталов города, м.
const CITY_STEP := 75.0

static var _data: Dictionary = {}

## Выбранный маршрут (Profile.floor): участок и путь к нему — акцентом.
var selected: String = "":
	set(v):
		selected = v
		queue_redraw()
var _font: Font
var _tex: Dictionary = {}
var _hover: String = ""
## Что где на экране (сверху вниз по порядку рисования): [id, PackedVector2Array участка | Rect2 плашки | [центр, радиус]].
var _hits: Array = []
## Что плашкам участков нельзя закрывать: точки путей от убежища и подпись убежища (на экране).
var _keep_clear: Array = []


static func data() -> Dictionary:
	if _data.is_empty() and FileAccess.file_exists(DATA_PATH):
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
		_data = v if v is Dictionary else {}
	return _data


func _init() -> void:
	_font = ThemeDB.fallback_font
	mouse_filter = Control.MOUSE_FILTER_PASS
	clip_contents = true


## Метры схемы → точки окна: вид (view) вписан с сохранением пропорций, по центру.
func _fit() -> Transform2D:
	var v: Array = data().get("view", [-1000, -1000, 1000, 1000])
	var vs := Vector2(float(v[2]) - float(v[0]), float(v[3]) - float(v[1]))
	var k := minf(size.x / vs.x, size.y / vs.y)
	var off := (size - vs * k) * 0.5 - Vector2(float(v[0]), float(v[1])) * k
	return Transform2D(0.0, Vector2(k, k), 0.0, off)


func _pts(xf: Transform2D, list: Array) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p: Array in list:
		out.append(xf * Vector2(float(p[0]), float(p[1])))
	return out


func _draw() -> void:
	_hits.clear()
	_keep_clear.clear()
	draw_rect(Rect2(Vector2.ZERO, size), GROUND)
	var d := data()
	if d.is_empty():
		draw_string(_font, Vector2(0, size.y * 0.5), "Схемы района пока нет", HORIZONTAL_ALIGNMENT_CENTER, size.x, 18, TERRAIN_TEXT)
		return
	var xf := _fit()
	var k := xf.get_scale().x
	# видимая часть схемы в метрах — город и лес рисуются по ней, а не только по рамке view
	var inv := xf.affine_inverse()
	var seen := Rect2(inv * Vector2.ZERO, Vector2.ZERO).expand(inv * size)
	_draw_city(xf, seen)
	_draw_forest(xf, k)
	_draw_houses(xf, k)
	for road: Array in d.get("roads", []):
		draw_polyline(_pts(xf, road), ROAD, 3.0, true)
	var rail := _pts(xf, d.get("rail", []))
	if rail.size() >= 2:
		draw_polyline(rail, RAIL_BED, 6.0, true)
		_dashes(rail, RAIL, 3.0, 9.0, 9.0)
	_draw_cordon(_pts(xf, d.get("cordon", [])))
	var shelter: Dictionary = d.get("shelter", {})
	var home := xf * Vector2(float(shelter.get("x", 0)), float(shelter.get("z", 0)))
	var places: Dictionary = d.get("places", {})
	var tiles := {}
	for id: String in places:
		var at := Vector2(float(places[id].x), float(places[id].z))
		tiles[id] = _draw_tile(id, at, xf)
	# пути от убежища: к ближайшему заходу участка; выбранный — поверх остальных
	var order: Array = places.keys()
	order.sort_custom(func(a: String, b: String) -> bool: return a != selected and b == selected)
	var bend := 1.0
	for id: String in order:
		var at := Vector2(float(places[id].x), float(places[id].z))
		_draw_path(home, _nearest_entry(id, at, xf, home), id, bend)
		bend = -bend
	_draw_shelter(home, shelter)
	for l: Array in d.get("labels", []):
		var p := xf * Vector2(float(l[1]), float(l[2]))
		var t := String(l[0]).to_upper()
		draw_string(LightUi.head_font(), p - Vector2(100, 0), t, HORIZONTAL_ALIGNMENT_CENTER, 200, 13, TERRAIN_TEXT)
	var plates := {}
	for id: String in places:
		if tiles[id] is PackedVector2Array:
			plates[id] = _draw_plate(id, tiles[id] as PackedVector2Array)
	_draw_floor_chips(d.get("floors_on", {}), plates)
	# север и подпись схемы
	var n_at := Vector2(size.x - 26, 26)
	draw_circle(n_at, 13.0, LABEL_BG)
	draw_string(_font, n_at + Vector2(-13, 5), "С", HORIZONTAL_ALIGNMENT_CENTER, 26, 14, Color.WHITE)
	var note := "Схема района: участки в своём масштабе, расстояния между ними сжаты"
	var nw := _font.get_string_size(note, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
	draw_rect(Rect2(Vector2(12, size.y - 32), Vector2(nw + 16, 22)), LABEL_BG)
	draw_string(_font, Vector2(20, size.y - 16), note, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 1, 0.75))


## Город за кордоном: кварталы по сетке (одни и те же при любом размере окна), где-то горят окна.
func _draw_city(xf: Transform2D, seen: Rect2) -> void:
	var line: Array = data().get("cordon", [])
	if line.size() < 2:
		return
	var poly := PackedVector2Array()
	for p: Array in line:
		poly.append(Vector2(float(p[0]), float(p[1])))
	var west := seen.position.x - 500.0
	poly.append(Vector2(west, poly[poly.size() - 1].y))
	poly.append(Vector2(west, poly[0].y))
	var rng := RandomNumberGenerator.new()
	var i0 := int(floor(seen.position.x / CITY_STEP))
	var j0 := int(floor(seen.position.y / CITY_STEP))
	for i in range(i0, int(ceil(seen.end.x / CITY_STEP)) + 1):
		for j in range(j0, int(ceil(seen.end.y / CITY_STEP)) + 1):
			rng.seed = hash(Vector2i(i, j))
			var w := rng.randf_range(32.0, 58.0)
			var h := rng.randf_range(28.0, 56.0)
			var c := Vector2(i * CITY_STEP + CITY_STEP * 0.5, j * CITY_STEP + CITY_STEP * 0.5)
			var r := Rect2(c - Vector2(w, h) * 0.5, Vector2(w, h))
			# квартал целиком за кордоном и не вплотную к нему
			var ok := true
			for q: Vector2 in [r.position, r.end, Vector2(r.end.x, r.position.y), Vector2(r.position.x, r.end.y)]:
				if not Geometry2D.is_point_in_polygon(q + Vector2(35, 0), poly):
					ok = false
			if not ok:
				continue
			var sr := Rect2(xf * r.position, Vector2.ZERO).expand(xf * r.end)
			draw_rect(sr, CITY.lightened(rng.randf_range(0.0, 0.08)))
			for _n in range(rng.randi_range(0, 3)):
				var dot := sr.position + Vector2(rng.randf() * sr.size.x, rng.randf() * sr.size.y)
				draw_rect(Rect2(dot, Vector2(2, 2)), CITY_LIT)


## Лес: в каждой области — пятна крон с одним и тем же рисунком.
func _draw_forest(xf: Transform2D, k: float) -> void:
	var rng := RandomNumberGenerator.new()
	var n := 0
	for a: Array in data().get("forest", []):
		n += 1
		rng.seed = 7919 * n
		var c := Vector2(float(a[0]), float(a[1]))
		var r := float(a[2])
		for _i in range(int(r * r / 900.0)):
			var p := c + Vector2.from_angle(rng.randf() * TAU) * sqrt(rng.randf()) * r
			draw_circle(xf * p, rng.randf_range(16.0, 34.0) * k, FOREST)


## Частный сектор: дома с участками вокруг точки.
func _draw_houses(xf: Transform2D, k: float) -> void:
	var rng := RandomNumberGenerator.new()
	var n := 0
	for a: Array in data().get("houses", []):
		n += 1
		rng.seed = 104729 * n
		var c := Vector2(float(a[0]), float(a[1]))
		for _i in range(int(a[3])):
			var p := xf * (c + Vector2.from_angle(rng.randf() * TAU) * sqrt(rng.randf()) * float(a[2]))
			var s := rng.randf_range(9.0, 14.0) * k
			draw_rect(Rect2(p - Vector2(s, s) * 0.5, Vector2(s, s)), HOUSE)


## Кордон: пунктир с засечками в сторону города (налево по ходу линии — данные идут с севера на юг).
func _draw_cordon(line: PackedVector2Array) -> void:
	if line.size() < 2:
		return
	_dashes(line, CORDON, 3.0, 12.0, 7.0)
	for i in range(line.size() - 1):
		var a := line[i]
		var b := line[i + 1]
		var dir := (b - a).normalized()
		var out := -dir.orthogonal()
		var t := 6.0
		while t < a.distance_to(b):
			var p := a + dir * t
			draw_line(p, p + out * 7.0, CORDON, 2.0, true)
			t += 19.0


## Участок: его снимок сверху по границе (как на плане локации), тень, обводка. Возвращает границу на экране.
func _draw_tile(id: String, at: Vector2, xf: Transform2D) -> Variant:
	var m := RaidMapPreview.data(id)
	if m.is_empty():
		return null
	var b: Array = m.get("bounds", [0, 0, 1, 1])
	var bs := Vector2(float(b[2]) - float(b[0]), float(b[3]) - float(b[1]))
	var poly := PackedVector2Array()
	var uvs := PackedVector2Array()
	for q: Array in m.get("boundary", []):
		var w := Vector2(float(q[0]), float(q[1]))
		poly.append(xf * (at + w))
		uvs.append((w - Vector2(float(b[0]), float(b[1]))) / bs)
	if poly.size() < 3:
		return null
	if not _tex.has(id):
		var path := String(m.get("image", ""))
		_tex[id] = load(path) as Texture2D if path != "" and ResourceLoader.exists(path) else null
	var open := Floors.is_open(id)
	var shadow := PackedVector2Array()
	for p: Vector2 in poly:
		shadow.append(p + Vector2(4, 5))
	draw_colored_polygon(shadow, Color(0, 0, 0, 0.45))
	var tex: Texture2D = _tex[id]
	var tint := Color.WHITE if open else Color(0.42, 0.43, 0.45)
	if tex:
		draw_colored_polygon(poly, tint, uvs, tex)
	else:
		draw_colored_polygon(poly, Color(0.32, 0.34, 0.33) * tint)
	var ring := poly.duplicate()
	ring.append(poly[0])
	var edge := LightUi.ACCENT if id == selected else (Color.WHITE if id == _hover else (Color(1, 1, 1, 0.55) if open else CLOSED))
	draw_polyline(ring, edge, 3.0 if id == selected else (2.5 if id == _hover else 1.5), true)
	_hits.append([id, poly])
	return poly


## Заход участка, ближайший к убежищу, — на экране (нет заходов — середина участка).
func _nearest_entry(id: String, at: Vector2, xf: Transform2D, home: Vector2) -> Vector2:
	var best := xf * at
	var best_d := INF
	for e: Dictionary in RaidMapPreview.data(id).get("entries", []):
		var p := xf * (at + Vector2(float(e.x), float(e.z)))
		if p.distance_to(home) < best_d:
			best_d = p.distance_to(home)
			best = p
	return best


## Путь от убежища к заходу: пологая дуга пунктиром, на конце — стрелка.
func _draw_path(from: Vector2, to: Vector2, id: String, bend: float) -> void:
	var dir := to - from
	if dir.length() < 30.0:
		return
	var mid := (from + to) * 0.5 + dir.orthogonal().normalized() * dir.length() * 0.12 * bend
	var pts := PackedVector2Array()
	for i in range(25):
		var t := float(i) / 24.0
		pts.append(from.lerp(mid, t).lerp(mid.lerp(to, t), t))
	var color := LightUi.ACCENT if id == selected else (PATH if Floors.is_open(id) else CLOSED)
	var width := 3.5 if id == selected else 2.5
	# от кромки значка убежища, не из его середины
	while pts.size() > 2 and pts[1].distance_to(from) < 16.0:
		pts.remove_at(1)
	pts[0] = from + (pts[1] - from).normalized() * 16.0
	_dashes(pts, Color(0, 0, 0, 0.5), width + 2.5, 10.0, 6.0)
	_dashes(pts, color, width, 10.0, 6.0)
	_keep_clear.append(pts)
	var tip := pts[pts.size() - 1]
	var back := (pts[pts.size() - 2] - tip).normalized()
	var arrow := PackedVector2Array([tip, tip + back * 12.0 + back.orthogonal() * 6.0, tip + back * 12.0 - back.orthogonal() * 6.0])
	draw_colored_polygon(arrow, color)


## Убежище: кружок с котельной (домик и труба) и подпись.
func _draw_shelter(at: Vector2, shelter: Dictionary) -> void:
	draw_circle(at, 15.0, Color(0, 0, 0, 0.5))
	draw_circle(at, 13.0, Color.WHITE)
	draw_arc(at, 13.0, 0.0, TAU, 28, LightUi.ACCENT, 3.0, true)
	var ink := Color("2a2b2e")
	draw_colored_polygon(PackedVector2Array([at + Vector2(-7, 6), at + Vector2(-7, -1), at + Vector2(0, -6), at + Vector2(7, -1), at + Vector2(7, 6)]), ink)
	draw_rect(Rect2(at + Vector2(3, -9), Vector2(3, 7)), ink)
	var title := String(shelter.get("name", "Убежище")).to_upper()
	var sub := String(shelter.get("sub", ""))
	var w := maxf(LightUi.head_font().get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x, _font.get_string_size(sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x)
	var r := Rect2(at + Vector2(20, -20), Vector2(w + 16, 40))
	draw_rect(r, LABEL_BG)
	draw_string(LightUi.head_font(), r.position + Vector2(8, 18), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color.WHITE)
	draw_string(_font, r.position + Vector2(8, 34), sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 1, 0.7))
	_hits.append(["shelter", [at, 16.0]])
	_hits.append(["shelter", r])
	_keep_clear.append(r)


## Плашка участка над его верхним краем: название и состояние; выбранный — залит акцентом. Возвращает её место.
func _draw_plate(id: String, poly: PackedVector2Array) -> Rect2:
	var f := Floors.find(id)
	var lo := poly[0]
	var hi := poly[0]
	for p: Vector2 in poly:
		lo = lo.min(p)
		hi = hi.max(p)
	var title := String(f.get("name", id))
	var state := "выбран" if id == selected else ("открыт" if Floors.is_open(id) else "закрыт")
	var w := maxf(LightUi.head_font().get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x, _font.get_string_size(state, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x) + 18.0
	# над серединой; закрывает путь или подпись убежища — над правым или левым краем участка, иначе — внутри
	# у верхнего угла, поверх снимка
	var r := Rect2()
	for at: Vector2 in [Vector2((lo.x + hi.x - w) * 0.5, lo.y - 50.0), Vector2(hi.x - w, lo.y - 50.0), Vector2(lo.x, lo.y - 50.0),
			Vector2(hi.x - w - 8.0, lo.y + 8.0), Vector2(lo.x + 8.0, lo.y + 8.0)]:
		r = Rect2(at, Vector2(w, 42))
		r.position = r.position.clamp(Vector2(6, 6), size - r.size - Vector2(6, 6))
		if _clear(r):
			break
	var on := id == selected
	draw_rect(r, LightUi.ACCENT if on else (Color(0.13, 0.14, 0.15, 0.92) if id == _hover else LABEL_BG))
	var open := Floors.is_open(id)
	draw_string(LightUi.head_font(), r.position + Vector2(9, 19), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, Color.WHITE if open or on else CLOSED)
	draw_string(_font, r.position + Vector2(9, 35), state, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 1, 1, 0.85) if on else Color(1, 1, 1, 0.6))
	_hits.append([id, r])
	return r


func _clear(r: Rect2) -> bool:
	var grown := r.grow(4.0)
	for k: Variant in _keep_clear:
		if k is Rect2 and grown.intersects(k as Rect2):
			return false
		if k is PackedVector2Array:
			for p: Vector2 in k as PackedVector2Array:
				if grown.has_point(p):
					return false
	return true


## Этажи ТЦ — короткие плашки в ряд справа от плашки участка (не влезают — слева): замок, «2F», закрыт / не собран;
## подробности — в подсказке.
func _draw_floor_chips(floors_on: Dictionary, plates: Dictionary) -> void:
	var x := {}
	for fid: String in floors_on:
		var host := String(floors_on[fid])
		if not plates.has(host):
			continue
		var plate := plates[host] as Rect2
		var title := String(Floors.find(fid).get("name", fid)).get_slice(" · ", 0)
		var state := "не собран" if Floors.is_open(fid) else "закрыт"
		var w := maxf(LightUi.head_font().get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x + 20.0, _font.get_string_size(state, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x) + 16.0
		var left := float(x.get(host, plate.end.x + 4.0))
		x[host] = left + w + 4.0
		var r := Rect2(Vector2(left, plate.position.y), Vector2(w, plate.size.y))
		draw_rect(r, Color(0.11, 0.12, 0.13, 0.92) if fid == _hover else LABEL_BG)
		# замок
		var lk := r.position + Vector2(8, 7)
		draw_arc(lk + Vector2(5, 4), 3.5, PI, TAU, 10, CLOSED, 2.0, true)
		draw_rect(Rect2(lk + Vector2(0, 4), Vector2(10, 8)), CLOSED)
		draw_string(LightUi.head_font(), r.position + Vector2(24, 19), title, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, CLOSED)
		draw_string(_font, r.position + Vector2(8, 35), state, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, CLOSED)
		_hits.append([fid, r])


func _dashes(pts: PackedVector2Array, color: Color, width: float, dash: float, gap: float) -> void:
	var on := true
	var left := dash
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var seg := a.distance_to(b)
		var t := 0.0
		while t < seg:
			var step := minf(left, seg - t)
			if on:
				draw_line(a.lerp(b, t / seg), a.lerp(b, (t + step) / seg), color, width, true)
			t += step
			left -= step
			if left <= 0.0:
				on = not on
				left = dash if on else gap


## Что под точкой окна: id участка, этажа или "shelter" ("" — ничего).
func _hit(at: Vector2) -> String:
	for i in range(_hits.size() - 1, -1, -1):
		var h: Array = _hits[i]
		var shape: Variant = h[1]
		if shape is Rect2 and (shape as Rect2).has_point(at):
			return String(h[0])
		if shape is PackedVector2Array and Geometry2D.is_point_in_polygon(at, shape as PackedVector2Array):
			return String(h[0])
		if shape is Array and ((shape as Array)[0] as Vector2).distance_to(at) <= float((shape as Array)[1]):
			return String(h[0])
	return ""


func _tip(id: String) -> String:
	if id == "":
		return ""
	if id == "shelter":
		var s: Dictionary = data().get("shelter", {})
		return "%s — %s.\nВ рейд выходят отсюда пешком: дверь тамбура, коридор, двор, ворота." % [String(s.get("name", "")), String(s.get("sub", ""))]
	var f := Floors.find(id)
	var lines: Array[String] = [String(f.get("name", id)), String(f.get("what", ""))]
	if not Floors.is_open(id):
		var why := Floors.unlock_block(id)
		lines.append("Закрыт — " + (why if why != "" else "Михалыч готов показать дорогу"))
	elif not Floors.built(id):
		lines.append("Маршрут открыт, этаж ещё не собран")
	lines.append("%s — %s" % [String(f.get("route", "")), String(f.get("how", ""))])
	return "\n".join(lines)


func _gui_input(event: InputEvent) -> void:
	var mm := event as InputEventMouseMotion
	if mm:
		var id := _hit(mm.position)
		tooltip_text = _tip(id)
		var pick: bool = id != "" and data().get("places", {}).has(id) and Floors.is_open(id)
		mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if pick else Control.CURSOR_ARROW
		if id != _hover:
			_hover = id
			queue_redraw()
		return
	var mb := event as InputEventMouseButton
	if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
		var id := _hit(mb.position)
		if id != "" and data().get("places", {}).has(id) and Floors.is_open(id):
			accept_event()
			picked.emit(id)
