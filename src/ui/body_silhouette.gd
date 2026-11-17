class_name BodySilhouette
extends Control
## Плоская фигура в окне снаряжения: одежда и надетые вещи читаются по форме, без 3D-модели.
## Координаты — в рамке 244 × 258 (EquipDoll.FIGURE).

const BOX := Vector2(244.0, 258.0)

var _eq: Dictionary = {}
var _line := Color(0.58, 0.61, 0.59, 0.78)
var _cloth := Color(0.18, 0.205, 0.205, 0.96)
var _cloth_light := Color(0.27, 0.3, 0.29, 0.95)
var _shadow := Color(0.075, 0.085, 0.09, 0.96)
var _seam := Color(0.48, 0.51, 0.48, 0.34)
var _gear := Color(0.32, 0.32, 0.235, 1.0)
var _gear_dark := Color(0.15, 0.16, 0.125, 1.0)
var _gear_light := Color(0.53, 0.51, 0.36, 0.9)
var _accent := Color(0.93, 0.77, 0.43, 0.95)
var _skin := Color(0.34, 0.31, 0.27, 1.0)


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = BOX


func set_equipment(eq: Dictionary) -> void:
	_eq = eq
	queue_redraw()


func _has(slot: String) -> bool:
	return _eq.get(slot) is Dictionary and not (_eq[slot] as Dictionary).is_empty()


func _id(slot: String) -> String:
	return String((_eq[slot] as Dictionary).get("id", "")) if _has(slot) else ""


func _rect(r: Rect2, fill: Color, edge: Color, radius: int = 2, width: float = 1.0) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = edge
	sb.set_border_width_all(maxi(1, int(width)))
	sb.set_corner_radius_all(radius)
	draw_style_box(sb, r)


func _shape(points: Array, fill: Color, edge: Color, width: float = 1.0, closed: bool = true) -> void:
	var poly := PackedVector2Array()
	for p: Variant in points:
		poly.append(p as Vector2)
	if closed and fill.a > 0.0:
		draw_colored_polygon(poly, fill)
	if closed and not poly.is_empty():
		poly.append(poly[0])
	draw_polyline(poly, edge, width, true)


func _mirrored(points: Array) -> Array:
	var out: Array = []
	for p: Variant in points:
		var v := p as Vector2
		out.append(Vector2(BOX.x - v.x, v.y))
	return out


func _pair(points: Array, fill: Color, edge: Color, width: float = 1.0) -> void:
	_shape(points, fill, edge, width)
	_shape(_mirrored(points), fill, edge, width)


func _stroke(a: Vector2, b: Vector2, color: Color, width: float = 1.0) -> void:
	draw_line(a, b, color, width, true)


func _ellipse(center: Vector2, radii: Vector2, fill: Color, edge: Color, width: float = 1.0) -> void:
	var points: Array = []
	for i in range(32):
		var a := TAU * float(i) / 32.0
		points.append(center + Vector2(cos(a) * radii.x, sin(a) * radii.y))
	_shape(points, fill, edge, width)


func _colors(light: bool) -> void:
	if light:
		_line = Color(0.26, 0.28, 0.28, 0.78)
		_cloth = Color(0.48, 0.51, 0.48, 0.98)
		_cloth_light = Color(0.59, 0.61, 0.55, 0.98)
		_shadow = Color(0.3, 0.33, 0.31, 0.98)
		_seam = Color(0.22, 0.25, 0.23, 0.35)
		_gear = Color(0.49, 0.47, 0.32, 1.0)
		_gear_dark = Color(0.3, 0.31, 0.23, 1.0)
		_gear_light = Color(0.7, 0.65, 0.44, 0.95)
		_accent = Color(0.72, 0.31, 0.08, 0.98)
		_skin = Color(0.64, 0.54, 0.43, 1.0)
	else:
		_line = Color(0.58, 0.61, 0.59, 0.78)
		_cloth = Color(0.18, 0.205, 0.205, 0.96)
		_cloth_light = Color(0.27, 0.3, 0.29, 0.95)
		_shadow = Color(0.075, 0.085, 0.09, 0.96)
		_seam = Color(0.48, 0.51, 0.48, 0.34)
		_gear = Color(0.32, 0.32, 0.235, 1.0)
		_gear_dark = Color(0.15, 0.16, 0.125, 1.0)
		_gear_light = Color(0.53, 0.51, 0.36, 0.9)
		_accent = Color(0.93, 0.77, 0.43, 0.95)
		_skin = Color(0.34, 0.31, 0.27, 1.0)


func _draw() -> void:
	_colors(LightUi.inside(self))
	_draw_backpack()
	_draw_body()
	_draw_armor()
	_draw_helmet()
	_draw_weapons()


func _draw_body() -> void:
	# Ноги, ботинки и развёрнутые руки образуют цельный силуэт, а не набор палочек.
	var leg := [Vector2(122, 127), Vector2(146, 128), Vector2(149, 158), Vector2(157, 231), Vector2(153, 242), Vector2(139, 242), Vector2(134, 177), Vector2(122, 157)]
	_pair(leg, _cloth, _line, 1.2)
	var boot := [Vector2(138, 229), Vector2(157, 229), Vector2(160, 246), Vector2(169, 250), Vector2(168, 256), Vector2(137, 256)]
	_pair(boot, _shadow, _line, 1.1)
	for y: float in [237.0, 242.0, 247.0]:
		_stroke(Vector2(140, y), Vector2(156, y), _seam)
		_stroke(Vector2(244 - 156, y), Vector2(244 - 140, y), _seam)
	var arm := [Vector2(148, 52), Vector2(161, 57), Vector2(183, 88), Vector2(224, 122), Vector2(233, 132), Vector2(228, 141), Vector2(216, 139), Vector2(174, 105), Vector2(151, 82)]
	_pair(arm, _cloth, _line, 1.2)
	_pair([Vector2(219, 119), Vector2(228, 122), Vector2(235, 133), Vector2(229, 143), Vector2(217, 139), Vector2(213, 130)], _shadow, _line, 1.0)
	_pair([Vector2(170, 88), Vector2(180, 84), Vector2(187, 96), Vector2(177, 103)], _cloth_light, _seam, 0.8)
	# Торс с боковыми тенями, воротником и шириной плеч.
	_shape([Vector2(108, 45), Vector2(136, 45), Vector2(153, 53), Vector2(149, 91), Vector2(145, 132), Vector2(99, 132), Vector2(95, 91), Vector2(91, 53)], _cloth, _line, 1.3)
	_shape([Vector2(91, 54), Vector2(101, 58), Vector2(104, 126), Vector2(99, 132), Vector2(95, 91)], _shadow, _shadow, 1.0)
	_shape([Vector2(153, 54), Vector2(143, 58), Vector2(140, 126), Vector2(145, 132), Vector2(149, 91)], _cloth_light, _cloth_light, 1.0)
	_stroke(Vector2(122, 59), Vector2(122, 128), _seam)
	_stroke(Vector2(104, 126), Vector2(140, 126), _seam)
	_rect(Rect2(113, 37, 18, 17), _skin, _line, 4)
	_shape([Vector2(108, 47), Vector2(115, 43), Vector2(122, 52), Vector2(129, 43), Vector2(136, 47), Vector2(130, 60), Vector2(114, 60)], _shadow, _line, 0.8)
	# Голова с подбородком, ушами и затенённой линией лица.
	_shape([Vector2(109, 9), Vector2(118, 4), Vector2(130, 6), Vector2(136, 14), Vector2(135, 28), Vector2(130, 39), Vector2(122, 43), Vector2(114, 39), Vector2(108, 28), Vector2(107, 16)], _skin, _line, 1.2)
	_ellipse(Vector2(107, 23), Vector2(2.5, 5), _skin, _line)
	_ellipse(Vector2(137, 23), Vector2(2.5, 5), _skin, _line)
	_shape([Vector2(128, 8), Vector2(136, 15), Vector2(134, 30), Vector2(128, 39), Vector2(122, 42), Vector2(127, 29)], Color(_shadow, 0.32), Color(_shadow, 0.0), 0.0)
	_stroke(Vector2(114, 24), Vector2(119, 24), _seam)
	_stroke(Vector2(125, 24), Vector2(130, 24), _seam)
	_stroke(Vector2(119, 34), Vector2(126, 34), _seam)


func _draw_backpack() -> void:
	if not _has("backpack"):
		return
	_rect(Rect2(78, 58, 88, 91), _gear_dark, _accent, 9, 1.4)
	_rect(Rect2(84, 66, 76, 70), _gear, _gear_light, 7)
	_rect(Rect2(91, 51, 62, 22), _gear, _accent, 7)
	_rect(Rect2(73, 83, 15, 43), _gear, _gear_light, 5)
	_rect(Rect2(156, 83, 15, 43), _gear, _gear_light, 5)
	_rect(Rect2(94, 115, 56, 25), _gear_dark, _gear_light, 4)
	_stroke(Vector2(98, 122), Vector2(146, 122), _seam)
	_stroke(Vector2(108, 55), Vector2(108, 47), _accent, 2.0)
	_stroke(Vector2(108, 47), Vector2(136, 47), _accent, 2.0)
	_stroke(Vector2(136, 47), Vector2(136, 55), _accent, 2.0)
	for x: float in [103.0, 141.0]:
		_shape([Vector2(x - 5, 53), Vector2(x + 5, 53), Vector2(x + 8, 107), Vector2(x + 3, 113), Vector2(x - 3, 107)], _gear, _accent, 1.1)
		_rect(Rect2(x - 3, 76, 7, 9), _gear_light, _gear_dark, 1)


func _draw_armor() -> void:
	if not _has("armor"):
		return
	var vest := WeaponDb.vest(_id("armor"))
	var belt: bool = vest.get("soft") == null
	if belt:
		_rect(Rect2(96, 119, 52, 17), _gear_dark, _accent, 3, 1.3)
		_rect(Rect2(116, 121, 12, 12), _gear_light, _gear_dark, 1)
		for x: float in [101.0, 108.0, 136.0, 143.0]:
			_stroke(Vector2(x, 121), Vector2(x, 134), _gear_light)
	else:
		_shape([Vector2(101, 54), Vector2(113, 58), Vector2(131, 58), Vector2(143, 54), Vector2(147, 72), Vector2(142, 124), Vector2(102, 124), Vector2(97, 72)], _gear, _accent, 1.4)
		_pair([Vector2(101, 54), Vector2(111, 57), Vector2(113, 74), Vector2(103, 78), Vector2(98, 67)], _gear_dark, _gear_light, 0.9)
		_rect(Rect2(103, 66, 38, 48), _gear_dark, _gear_light, 3)
		_rect(Rect2(107, 70, 30, 21), _gear, _gear_light, 2)
		# Стропы MOLLE и шов края плитоносца.
		for y: float in [94.0, 101.0, 108.0]:
			_stroke(Vector2(104, y), Vector2(140, y), _gear_light, 0.8)
			for x: float in [110.0, 120.0, 130.0]:
				_stroke(Vector2(x, y - 3), Vector2(x, y + 3), _seam, 0.7)
		_stroke(Vector2(104, 118), Vector2(140, 118), _accent, 0.8)
	_draw_pouches(_eq.armor as Dictionary, belt)


func _draw_pouches(armor: Dictionary, belt: bool) -> void:
	var places := int(WeaponDb.vest(String(armor.get("id", ""))).get("places", 0))
	if places <= 0:
		return
	var rows := 2 if places > 5 else 1
	var per_row := ceili(float(places) / float(rows))
	var w := 52.0 / float(per_row)
	for p: Dictionary in ItemDb.pouch_list(armor):
		var at := int(p.at)
		var half := ItemDb.pouch_half(String(p.id))
		var first := (at - 1) / 2
		var row := first / per_row
		var col := float((at - 1) - row * per_row * 2) * 0.5
		var y := 127.0 if belt else 94.0 + float(row) * 20.0
		var rect := Rect2(96.0 + col * w + 1.0, y, maxf(5.0, w * float(half) * 0.5 - 2.0), 17.0 if belt else 18.0)
		_rect(rect, _gear, _accent, 2, 0.9)
		_rect(Rect2(rect.position + Vector2(1, 1), Vector2(rect.size.x - 2, 5)), _gear_light, _gear_dark, 1, 0.7)
		if rect.size.x > 9.0:
			_stroke(rect.position + Vector2(rect.size.x * 0.5, 7), rect.position + Vector2(rect.size.x * 0.5, rect.size.y - 2), _seam, 0.7)


func _draw_helmet() -> void:
	if _has("helmet"):
		_shape([Vector2(105, 22), Vector2(106, 13), Vector2(112, 5), Vector2(122, 1), Vector2(133, 5), Vector2(139, 14), Vector2(139, 23), Vector2(133, 20), Vector2(111, 20)], _gear, _accent, 1.3)
		_shape([Vector2(109, 13), Vector2(116, 6), Vector2(122, 4), Vector2(122, 18), Vector2(110, 19)], _gear_light, _gear_light, 0.6)
		_stroke(Vector2(106, 22), Vector2(138, 22), _accent, 1.2)
		_stroke(Vector2(110, 23), Vector2(113, 36), _gear_dark, 1.6)
		_stroke(Vector2(134, 23), Vector2(131, 36), _gear_dark, 1.6)
		if "NVG" in ItemDb.helmet_mounts(_eq):
			_rect(Rect2(117, 0, 10, 7), _gear_dark, _accent, 1)
	if _has("eyes"):
		if bool(ItemDb.equip(_id("eyes")).get("nvg", false)):
			_rect(Rect2(116, 15, 12, 8), _gear_dark, _accent, 1)
			for x: float in [113.0, 126.0]:
				_rect(Rect2(x, 20, 9, 15), _gear_dark, _accent, 3, 1.0)
				_ellipse(Vector2(x + 4.5, 32), Vector2(4.0, 3.0), Color(0.18, 0.42, 0.32), _gear_light)
				_stroke(Vector2(x + 2, 31), Vector2(x + 4, 30), Color(0.65, 0.9, 0.72, 0.75), 1.0)
			if not _has("helmet"):
				_shape([Vector2(106, 19), Vector2(110, 8), Vector2(122, 4), Vector2(134, 8), Vector2(138, 19)], Color(0, 0, 0, 0), _accent, 1.4, false)
		else:
			_rect(Rect2(109, 20, 11, 7), Color(0.08, 0.12, 0.14, 0.9), _accent, 2)
			_rect(Rect2(124, 20, 11, 7), Color(0.08, 0.12, 0.14, 0.9), _accent, 2)
			_stroke(Vector2(120, 22), Vector2(124, 22), _accent, 1.2)
			_stroke(Vector2(112, 21), Vector2(116, 21), Color(0.7, 0.85, 0.9, 0.45), 0.8)
			_stroke(Vector2(127, 21), Vector2(131, 21), Color(0.7, 0.85, 0.9, 0.45), 0.8)


func _draw_weapons() -> void:
	if _has("primary") or _has("secondary"):
		_stroke(Vector2(99, 55), Vector2(145, 129), Color(_accent, 0.65), 2.4)
		# Оружие на ремне: ствол, ствольная коробка, магазин и приклад.
		_stroke(Vector2(104, 65), Vector2(140, 119), _shadow, 6.0)
		_stroke(Vector2(104, 65), Vector2(140, 119), _gear_light, 2.0)
		_shape([Vector2(98, 55), Vector2(105, 57), Vector2(115, 75), Vector2(109, 80), Vector2(102, 70)], _gear_dark, _accent, 0.8)
		_shape([Vector2(120, 91), Vector2(127, 96), Vector2(124, 108), Vector2(119, 105)], _gear_dark, _accent, 0.8)
	if _has("sidearm"):
		_shape([Vector2(151, 143), Vector2(164, 143), Vector2(166, 166), Vector2(157, 174), Vector2(151, 166)], _gear_dark, _accent, 1.0)
		_stroke(Vector2(153, 149), Vector2(164, 149), _gear_light)
		_stroke(Vector2(151, 140), Vector2(159, 155), _shadow, 3.0)
	if _has("launcher"):
		_shape(_mirrored([Vector2(151, 143), Vector2(164, 143), Vector2(166, 166), Vector2(157, 174), Vector2(151, 166)]), _gear_dark, _accent, 1.0)
		_stroke(Vector2(91, 149), Vector2(80, 149), _gear_light)
