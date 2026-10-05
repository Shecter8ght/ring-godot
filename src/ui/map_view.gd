class_name MapView
extends CanvasLayer
## Карта этажа на M: план из данных сектора (помещения кольца и полосы аллеи), постройки сцены,
## эскалаторы, точки эвакуации с названиями, свой игрок стрелкой и напарники точками. Врагов,
## лута и ключей на карте нет — только то, что знает человек с планом ТЦ. Север (-Z) вверху.
## Колесо — приблизить к себе, Esc или M — закрыть.

const FILL := {
	"atrium": Color(0.36, 0.43, 0.48), "gallery": Color(0.4, 0.4, 0.38), "retail": Color(0.5, 0.44, 0.33),
	"storage": Color(0.33, 0.32, 0.29), "office": Color(0.39, 0.35, 0.43), "security": Color(0.44, 0.33, 0.3),
	"utility": Color(0.31, 0.36, 0.39), "corridor": Color(0.34, 0.34, 0.32), "yard": Color(0.22, 0.23, 0.23),
	"parking": Color(0.2, 0.21, 0.22),
}
const BG := Color(0.08, 0.085, 0.09, 0.94)
const LINE := Color(0.08, 0.08, 0.08)

var _rooms: Array = []
var _ring: Dictionary = {}
var _open_angle: Vector2 = Vector2(-180, 0)
var _root: Control
var _canvas: Control
var _zoom: float = 1.0
## Постройки сцены: [4 угла в мировых XZ, имя]; эскалаторы — [4 угла].
var _buildings: Array = []
var _escalators: Array = []
var _font: Font
## Где подписывать помещения (считается один раз: полоса аллеи перекрывает часть кольцевых).
var _label_at: Dictionary = {}
var _width_of: Dictionary = {}
## Мировые XZ, в которые вписывается карта: открытая часть, постройки, точки эвакуации.
var _bounds: Rect2 = Rect2()
var _urban: Dictionary = {}


func setup(rooms: Array, ring: Dictionary, open_angle: Vector2) -> void:
	_rooms = rooms
	_ring = ring
	_open_angle = open_angle


func setup_urban(definition: Dictionary) -> void:
	_urban = definition
	_rooms = definition.get("rooms", [])
	var bounds: Array = definition.bounds
	_bounds = Rect2(float(bounds[0]), float(bounds[1]), float(bounds[2]) - float(bounds[0]), float(bounds[3]) - float(bounds[1]))


func _ready() -> void:
	layer = 30
	add_to_group("esc_windows")
	_font = ThemeDB.fallback_font
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.visible = false
	_root.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_root)
	_canvas = Control.new()
	_canvas.set_anchors_preset(Control.PRESET_FULL_RECT)
	_canvas.mouse_filter = Control.MOUSE_FILTER_PASS
	_canvas.draw.connect(_draw_map)
	_canvas.gui_input.connect(_on_gui_input)
	_root.add_child(_canvas)
	_collect_scene.call_deferred()


func is_open() -> bool:
	return _root.visible


## Постройки и эскалаторы — узлы сцены уровня: их двигают руками, берём как есть.
func _collect_scene() -> void:
	var scene := get_tree().current_scene
	if scene == null:
		return
	for n in scene.find_children("*", "Node3D", true, false):
		if n is BlockoutBuilding:
			var b := n as BlockoutBuilding
			_buildings.append([_corners(b.global_transform, b.size.x, b.size.y), b.display_name])
		elif n is Escalator:
			var e := n as Escalator
			var l := e.total_length() + e.top_platform
			var xf := e.global_transform.translated_local(Vector3(0, 0, -e.top_platform * 0.5))
			_escalators.append(_corners(xf, e.total_width(), l))
	# рамка карты — всё, что открыто: помещения, постройки, эвакуации
	var pts: Array[Vector2] = []
	for room in _rooms:
		if room.has("rect"):
			continue
		if SectorBuilder.is_strip(room):
			continue
		for i in range(9):
			for r in [float(room.r[0]), float(room.r[1])]:
				var p := SectorBuilder.polar(lerpf(float(room.a[0]), float(room.a[1]), i / 8.0), r)
				pts.append(Vector2(p.x, p.z))
	for b in _buildings:
		for p in b[0]:
			pts.append(p)
	for x in get_tree().get_nodes_in_group("extractions"):
		pts.append(Vector2((x as Node3D).global_position.x, (x as Node3D).global_position.z))
	if not pts.is_empty() and _urban.is_empty():
		_bounds = Rect2(pts[0], Vector2.ZERO)
		for p in pts:
			_bounds = _bounds.expand(p)
		_bounds = _bounds.grow(12.0)


static func _corners(xf: Transform3D, w: float, d: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for c in [Vector3(-w, 0, -d), Vector3(w, 0, -d), Vector3(w, 0, d), Vector3(-w, 0, d)]:
		var p: Vector3 = xf * (c * 0.5)
		out.append(Vector2(p.x, p.z))
	return out


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("map") and not event.is_echo() and not PauseMenu.shown:
		if not _root.visible and Raid.current and Raid.current.ui_open():
			return
		_root.visible = not _root.visible
		Audio.play_ui("map" if _root.visible else "bag_close")
		_zoom = 1.0
		get_viewport().set_input_as_handled()
	elif _root.visible and event.is_action_pressed("ui_cancel"):
		_root.visible = false
		Audio.play_ui("bag_close")
		get_viewport().set_input_as_handled()


func _on_gui_input(event: InputEvent) -> void:
	var mb := event as InputEventMouseButton
	if mb and mb.pressed:
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_zoom = minf(_zoom * 1.25, 6.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_zoom = maxf(_zoom / 1.25, 1.0)


func _process(_delta: float) -> void:
	if _root.visible:
		_canvas.queue_redraw()


func _me() -> Player:
	for p in get_tree().get_nodes_in_group("players"):
		if (p as Player).is_local():
			return p
	return null


# ---------------------------------------------------------------- рисование

var _scale: float = 1.0
var _center: Vector2 = Vector2.ZERO
var _origin: Vector2 = Vector2.ZERO


func _to_screen(w: Vector2) -> Vector2:
	return _origin + (w - _center) * _scale


func _draw_map() -> void:
	var size := _canvas.size
	_canvas.draw_rect(Rect2(Vector2.ZERO, size), BG)
	var me := _me()
	var fit := _bounds if _bounds.size != Vector2.ZERO else Rect2(-150, -150, 300, 300)
	# У южной границы города нужна также полоса для подписи КПП.
	var vertical_margin: float = 150.0 if not _urban.is_empty() else 110.0
	_scale = minf(size.x / fit.size.x, (size.y - vertical_margin) / fit.size.y) * _zoom
	_origin = Vector2(size.x * 0.5, 100.0 + (size.y - vertical_margin) * 0.5)
	_center = fit.get_center()
	if _zoom > 1.0 and me:
		_center = Vector2(me.global_position.x, me.global_position.z)
	# закрытая часть кольца — бледный силуэт: видно, что здание продолжается
	if _urban.is_empty():
		var outer := float(_ring.get("outer_r", 100.0))
		_canvas.draw_colored_polygon(_arc_poly(_open_angle.y, _open_angle.x + 360.0, 0.0, outer), Color(0.16, 0.165, 0.17))
	else:
		_draw_urban()
	# сначала улица, потом здание, поверх — полосы аллеи
	var order := _rooms.duplicate()
	order.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return _rank(a) < _rank(b))
	for room in order:
		if room.has("rect"):
			continue
		var poly := _room_poly(room)
		if poly.size() < 3:
			continue
		var col: Color = FILL.get(String(room.get("type", "")), Color(0.4, 0.4, 0.4))
		_canvas.draw_colored_polygon(poly, col)
		var closed := poly.duplicate()
		closed.append(poly[0])
		_canvas.draw_polyline(closed, LINE, 1.0)
	for b in _buildings:
		var poly := PackedVector2Array()
		for p in b[0]:
			poly.append(_to_screen(p))
		_canvas.draw_colored_polygon(poly, Color(0.3, 0.33, 0.35))
		var closed := poly.duplicate()
		closed.append(poly[0])
		_canvas.draw_polyline(closed, Color(0.6, 0.62, 0.6), 1.2)
		if String(b[1]) != "" and (_urban.is_empty() or _zoom > 2.0):
			_label(_poly_center(poly), String(b[1]), 13, Color(0.85, 0.87, 0.85))
	for e in _escalators:
		var poly := PackedVector2Array()
		for p in e:
			poly.append(_to_screen(p))
		_canvas.draw_colored_polygon(poly, Color(0.45, 0.4, 0.6))
	# подписи магазинов и крупных помещений
	for room in _rooms:
		if room.has("rect"):
			continue
		var t := String(room.get("type", ""))
		if t in ["corridor", "yard", "parking"] and not bool(room.get("outdoor", false)):
			continue
		var id := String(room.get("id", ""))
		if not _label_at.has(id):
			_label_at[id] = _label_point(room)
		var at: Vector2 = _label_at[id]
		if at == Vector2.INF:
			continue
		# подпись — только если помещается в помещение на экране (приближение открывает остальные)
		var fs := 13
		var title := String(room.get("name", ""))
		if not _width_of.has(id):
			_width_of[id] = _room_width(room)
		var room_w := float(_width_of[id]) * _scale
		var room_h := (float(room.r[1]) - float(room.r[0])) * _scale
		if room_w < _font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x * 0.9 or room_h < fs * 1.4:
			continue
		_label(_to_screen(at), title, fs, Color(0.92, 0.9, 0.84, 0.9))
	# точки эвакуации
	if not _urban.is_empty() and _zoom <= 2.0:
		for district in _urban.get("districts", []):
			var rect: Array = district.rect
			var center := Vector2((float(rect[0]) + float(rect[2])) * 0.5, (float(rect[1]) + float(rect[3])) * 0.5)
			_label(_to_screen(center), String(district.name), 15, Color(0.93, 0.93, 0.88))
	for x in get_tree().get_nodes_in_group("extractions"):
		var ep := x as ExtractionPoint
		if ep == null:
			continue
		var s := _to_screen(Vector2(ep.global_position.x, ep.global_position.z))
		_canvas.draw_colored_polygon(PackedVector2Array([s + Vector2(0, -11), s + Vector2(10, 7), s + Vector2(-10, 7)]), Color(0.2, 0.75, 0.35))
		_label(s + Vector2(0, 20), ep.display_name, 13, Color(0.55, 1.0, 0.65))
	# свет ТЦ: главный рубильник и генератор — ромб (генератор встал — красный)
	var power_labels: Array[Rect2] = []
	for n in get_tree().get_nodes_in_group("power_points"):
		var pp := n as Node3D
		var down := n is MallGenerator and (n as MallGenerator).is_down()
		var col := Color(1.0, 0.3, 0.2) if down else Color(1.0, 0.8, 0.25)
		var s := _to_screen(Vector2(pp.global_position.x, pp.global_position.z))
		_canvas.draw_colored_polygon(PackedVector2Array([s + Vector2(0, -8), s + Vector2(8, 0), s + Vector2(0, 8), s + Vector2(-8, 0)]), col)
		var title: String = String(pp.get("display_name"))
		var label_at: Vector2 = s + Vector2(0, 18)
		var text_size: Vector2 = _font.get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
		var label_rect := Rect2(label_at - text_size * 0.5, text_size).grow(2.0)
		if not _urban.is_empty():
			for previous: Rect2 in power_labels:
				if label_rect.intersects(previous):
					label_at.y = previous.end.y + text_size.y * 0.5 + 4.0
					label_rect.position = label_at - text_size * 0.5
		power_labels.append(label_rect)
		_label(label_at, title, 12, col)
	# напарники — точки, сам — стрелка по взгляду
	for p in get_tree().get_nodes_in_group("players"):
		var pl := p as Player
		if pl == me or not pl.is_alive():
			continue
		_canvas.draw_circle(_to_screen(Vector2(pl.global_position.x, pl.global_position.z)), 6.0, Color(0.35, 0.65, 1.0))
	if me:
		var s := _to_screen(Vector2(me.global_position.x, me.global_position.z))
		var yaw := me.body_yaw()
		var f := Vector2(sin(yaw), cos(yaw))
		var r := Vector2(f.y, -f.x)
		_canvas.draw_colored_polygon(PackedVector2Array([s + f * 14.0, s - f * 8.0 + r * 8.0, s - f * 4.0, s - f * 8.0 - r * 8.0]), Color(1.0, 0.85, 0.3))
	# рамка: название этажа, север, подсказки
	_canvas.draw_string(_font, Vector2(30, 46), _floor_title(), HORIZONTAL_ALIGNMENT_LEFT, -1, 26, Color(1.0, 0.86, 0.6))
	_canvas.draw_string(_font, Vector2(30, 74), "С ↑   ·   колесо — приблизить к себе   ·   M / Esc — закрыть", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(0.7, 0.72, 0.7))


func _floor_title() -> String:
	if not _urban.is_empty():
		return "Карта · " + String(_urban.name)
	var f := Floors.find(Profile.floor)
	return "Карта · " + String(f.get("name", "1F"))


func _draw_urban() -> void:
	var boundary := PackedVector2Array()
	for point in _urban.get("boundary", []):
		boundary.append(_to_screen(Vector2(float(point[0]), float(point[1]))))
	if boundary.size() >= 3:
		_canvas.draw_colored_polygon(boundary, Color(0.22, 0.29, 0.22))
		boundary.append(boundary[0])
		_canvas.draw_polyline(boundary, Color(0.6, 0.7, 0.72), 2.0)
	var river: Dictionary = _urban.get("river", {})
	var water := PackedVector2Array()
	for point in river.get("points", []):
		water.append(_to_screen(Vector2(float(point[0]), float(point[1]))))
	if water.size() > 1:
		_canvas.draw_polyline(water, Color(0.18, 0.38, 0.52), float(river.get("width", 100)) * _scale)
	for road in _urban.get("roads", []):
		var points := PackedVector2Array()
		for point in road.points:
			points.append(_to_screen(Vector2(float(point[0]), float(point[1]))))
		if points.size() > 1:
			_canvas.draw_polyline(points, Color(0.54, 0.55, 0.55), (float(road.width) + float(road.get("sidewalk", 0)) * 2) * _scale)
			_canvas.draw_polyline(points, Color(0.16, 0.17, 0.18), maxf(1.0, float(road.width) * _scale))
	for district in _urban.get("districts", []):
		if String(district.id) != "sports":
			continue
		var rect: Array = district.rect
		var top_left: Vector2 = _to_screen(Vector2(float(rect[0]), float(rect[1])))
		var bottom_right: Vector2 = _to_screen(Vector2(float(rect[2]), float(rect[3])))
		var pitch := Rect2(top_left, bottom_right - top_left)
		_canvas.draw_rect(pitch, Color(0.27, 0.4, 0.27))
		_canvas.draw_rect(pitch.grow(-2.0), Color(0.65, 0.73, 0.65), false, 1.0)
		_canvas.draw_line(Vector2(pitch.get_center().x, pitch.position.y), Vector2(pitch.get_center().x, pitch.end.y), Color(0.65, 0.73, 0.65), 1.0)
	var scale_m: float = 100.0
	var left := Vector2(32, _canvas.size.y - 35)
	_canvas.draw_line(left, left + Vector2(scale_m * _scale, 0), Color.WHITE, 2)
	_label(left + Vector2(scale_m * _scale * 0.5, -14), "100 м", 12, Color.WHITE)


func _rank(room: Dictionary) -> int:
	if bool(room.get("outdoor", false)):
		return 0
	return 2 if SectorBuilder.is_strip(room) else 1


func _room_poly(room: Dictionary) -> PackedVector2Array:
	if SectorBuilder.is_strip(room):
		var out := PackedVector2Array()
		var ax := float(room.axis)
		var t0 := float(room.t[0])
		var t1 := float(room.t[1])
		for i in range(9):
			var t := lerpf(t0, t1, i / 8.0)
			var p := SectorBuilder.strip_point(ax, SectorBuilder._strip_s(float(room.r[1]), t), t)
			out.append(_to_screen(Vector2(p.x, p.z)))
		for i in range(8, -1, -1):
			var t := lerpf(t0, t1, i / 8.0)
			var p := SectorBuilder.strip_point(ax, SectorBuilder._strip_s(float(room.r[0]), t), t)
			out.append(_to_screen(Vector2(p.x, p.z)))
		return out
	return _arc_poly(float(room.a[0]), float(room.a[1]), float(room.r[0]), float(room.r[1]))


func _arc_poly(a0: float, a1: float, r0: float, r1: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := maxi(2, int(absf(a1 - a0) / 2.0) + 1)
	for i in range(n + 1):
		var p := SectorBuilder.polar(lerpf(a0, a1, float(i) / n), r1)
		out.append(_to_screen(Vector2(p.x, p.z)))
	if r0 < 0.6:
		out.append(_to_screen(Vector2.ZERO))
	else:
		for i in range(n, -1, -1):
			var p := SectorBuilder.polar(lerpf(a0, a1, float(i) / n), r0)
			out.append(_to_screen(Vector2(p.x, p.z)))
	return out


## Где подписать помещение: середина видимой части (аллея перекрывает часть кольцевых).
func _label_point(room: Dictionary) -> Vector2:
	var id := String(room.get("id", ""))
	if SectorBuilder.is_strip(room):
		var p := SectorBuilder.strip_point(float(room.axis), SectorBuilder._strip_s((float(room.r[0]) + float(room.r[1])) * 0.5, 0.0), 0.0)
		return Vector2(p.x, p.z)
	var rm := (float(room.r[0]) + float(room.r[1])) * 0.5
	var sum := Vector2.ZERO
	var n := 0
	for i in range(11):
		var p := SectorBuilder.polar(lerpf(float(room.a[0]), float(room.a[1]), i / 10.0), rm)
		if String(SectorBuilder.owner_of(_rooms, p).get("id", "")) == id:
			sum += Vector2(p.x, p.z)
			n += 1
	return sum / n if n > 0 else Vector2.INF


## Ширина помещения поперёк радиуса, м (у кольцевого — видимая дуга на среднем радиусе).
func _room_width(room: Dictionary) -> float:
	if SectorBuilder.is_strip(room):
		return float(room.t[1]) - float(room.t[0])
	var rm := (float(room.r[0]) + float(room.r[1])) * 0.5
	var id := String(room.get("id", ""))
	var seen := 0
	for i in range(11):
		var p := SectorBuilder.polar(lerpf(float(room.a[0]), float(room.a[1]), i / 10.0), rm)
		if String(SectorBuilder.owner_of(_rooms, p).get("id", "")) == id:
			seen += 1
	return deg_to_rad(float(room.a[1]) - float(room.a[0])) * rm * seen / 11.0


func _poly_center(poly: PackedVector2Array) -> Vector2:
	var c := Vector2.ZERO
	for p in poly:
		c += p
	return c / maxf(1.0, poly.size())


func _label(at: Vector2, text: String, fs: int, col: Color) -> void:
	var w := _font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var pos := at + Vector2(-w * 0.5, fs * 0.35)
	_canvas.draw_string_outline(_font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color(0, 0, 0, 0.75))
	_canvas.draw_string(_font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
