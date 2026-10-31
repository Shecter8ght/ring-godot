class_name RaidMapPreview
extends Control
## Карта маршрута в окне «План рейда» (владелец 2026-10-31: «чтобы там карту было видно», по образцу Таркова,
## Arena Breakout: Infinite, ExfilZone): снимок уровня сверху (tools/raid_map_bake → assets/maps/<id>.webp), граница
## участка, выходы (зелёные — всегда, янтарные ромбы — с условием: ключ, рубильник, «не каждый рейд», без рюкзака)
## и заходы с края (синие треугольники). Под курсором — подсказка выхода. Север (-Z) вверху, масштаб — полоса 100 м.
## Снимка нет (этаж не собран, карта не снята) — надпись вместо карты.

const DATA_PATH := "res://data/raid_maps.json"
const EXIT := Color("2e9d4a")
const EXIT_COND := Color("e0a030")
const ENTRY := Color("3f7fd0")
const LABEL_BG := Color(0.07, 0.08, 0.09, 0.72)

static var _data: Dictionary = {}

var map_id: String = "":
	set(v):
		map_id = v
		_tex = null
		_map = data(v)
		var path := String(_map.get("image", ""))
		if path != "" and ResourceLoader.exists(path):
			_tex = load(path) as Texture2D
		queue_redraw()
var _map: Dictionary = {}
var _tex: Texture2D
var _font: Font
## Где на экране метки (для подсказки): [центр, текст].
var _spots: Array = []


## Данные карты маршрута id ({} — нет).
static func data(id: String) -> Dictionary:
	if _data.is_empty() and FileAccess.file_exists(DATA_PATH):
		var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
		_data = (v as Dictionary).get("maps", {}) if v is Dictionary else {}
	return _data.get(id, {})


## Условие выхода простыми словами ("" — выход открыт всегда).
static func exit_note(e: Dictionary) -> String:
	var parts: Array[String] = []
	if String(e.get("key", "")) != "":
		var k := "ключ: " + ItemDb.item_name(String(e.key))
		if String(e.get("alt_key", "")) != "":
			k += " или " + ItemDb.item_name(String(e.alt_key))
		parts.append(k)
	if String(e.get("switch", "")) != "":
		parts.append("нужен рубильник")
	if float(e.get("chance", 1.0)) < 1.0:
		parts.append("не каждый рейд")
	if bool(e.get("no_backpack", false)):
		parts.append("без рюкзака")
	return ", ".join(parts)


func _init() -> void:
	_font = ThemeDB.fallback_font
	mouse_filter = Control.MOUSE_FILTER_PASS
	clip_contents = true


## Прямоугольник снимка в окне: вписан с сохранением пропорций, по центру.
func _image_rect() -> Rect2:
	if _tex == null:
		return Rect2()
	var ts := Vector2(_tex.get_size())
	var k := minf(size.x / ts.x, size.y / ts.y)
	var s := ts * k
	return Rect2((size - s) * 0.5, s)


## Мировая точка XZ → точка окна.
func _to_view(x: float, z: float, ir: Rect2) -> Vector2:
	var b: Array = _map.get("bounds", [0, 0, 1, 1])
	var u := (x - float(b[0])) / maxf(0.001, float(b[2]) - float(b[0]))
	var v := (z - float(b[1])) / maxf(0.001, float(b[3]) - float(b[1]))
	return ir.position + Vector2(u, v) * ir.size


func _draw() -> void:
	_spots.clear()
	if _tex == null:
		var msg := "Карты маршрута пока нет" if not _map.is_empty() or map_id == "" else "Этаж ещё не собран — карты нет"
		draw_string(_font, Vector2(0, size.y * 0.5), msg, HORIZONTAL_ALIGNMENT_CENTER, size.x, 18, LightUi.MUTED)
		return
	var ir := _image_rect()
	draw_texture_rect(_tex, ir, false)
	# граница участка: дальше — не пройти
	var line := PackedVector2Array()
	for p in _map.get("boundary", []):
		line.append(_to_view(float(p[0]), float(p[1]), ir))
	if line.size() >= 3:
		line.append(line[0])
		draw_polyline(line, Color(0, 0, 0, 0.55), 5.0, true)
		draw_polyline(line, Color(1, 1, 1, 0.85), 2.0, true)
	for e: Dictionary in _map.get("entries", []):
		var at := _to_view(float(e.x), float(e.z), ir)
		var tri := PackedVector2Array([at + Vector2(0, -8), at + Vector2(7, 5), at + Vector2(-7, 5)])
		draw_colored_polygon(tri, ENTRY)
		tri.append(tri[0])
		draw_polyline(tri, Color.WHITE, 1.5, true)
		_spots.append([at, "Заход: %s" % String(e.name)])
	for e: Dictionary in _map.get("exits", []):
		var at := _to_view(float(e.x), float(e.z), ir)
		var note := exit_note(e)
		if note == "":
			draw_circle(at, 8.0, EXIT)
			draw_arc(at, 8.0, 0.0, TAU, 20, Color.WHITE, 2.0, true)
		else:
			var dia := PackedVector2Array([at + Vector2(0, -9), at + Vector2(9, 0), at + Vector2(0, 9), at + Vector2(-9, 0)])
			draw_colored_polygon(dia, EXIT_COND)
			dia.append(dia[0])
			draw_polyline(dia, Color.WHITE, 2.0, true)
		var name := String(e.name)
		var w := _font.get_string_size(name, HORIZONTAL_ALIGNMENT_LEFT, -1, 13).x
		var lr := Rect2(at + Vector2(12, -10), Vector2(w + 10, 20))
		# подпись не вылезает за край карты
		if lr.end.x > ir.end.x:
			lr.position.x = at.x - 12.0 - lr.size.x
		draw_rect(lr, LABEL_BG)
		draw_string(_font, lr.position + Vector2(5, 15), name, HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color.WHITE)
		var rule := String(e.get("rule", ""))
		_spots.append([at, "Выход: %s%s%s" % [name, "\n" + note if note != "" else "", "\n" + rule if rule != "" else ""]])
	# масштаб: 100 м
	var b: Array = _map.get("bounds", [0, 0, 1, 1])
	var px_m := ir.size.x / maxf(1.0, float(b[2]) - float(b[0]))
	var left := ir.position + Vector2(16, ir.size.y - 18)
	draw_rect(Rect2(left - Vector2(6, 22), Vector2(100.0 * px_m + 12, 30)), LABEL_BG)
	draw_line(left, left + Vector2(100.0 * px_m, 0), Color.WHITE, 2.0)
	draw_string(_font, left + Vector2(0, -6), "100 м", HORIZONTAL_ALIGNMENT_CENTER, 100.0 * px_m, 12, Color.WHITE)
	# север
	var n_at := ir.position + Vector2(ir.size.x - 24, 26)
	draw_circle(n_at, 13.0, LABEL_BG)
	draw_string(_font, n_at + Vector2(-13, 5), "С", HORIZONTAL_ALIGNMENT_CENTER, 26, 14, Color.WHITE)


func _get_tooltip(at: Vector2) -> String:
	var best := ""
	var best_d := 14.0
	for s: Array in _spots:
		var d := (s[0] as Vector2).distance_to(at)
		if d < best_d:
			best_d = d
			best = String(s[1])
	return best


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		tooltip_text = _get_tooltip((event as InputEventMouseMotion).position)
