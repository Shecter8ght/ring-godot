class_name BodySilhouette
extends Control
## Контур человека в А-позе (руки в стороны под 45°) вместо модели в окне снаряжения
## (docs/design/equip_doll_v2.md, п. 1): схема, а не портрет. Надетое обводится тем же контуром толще и тёплым
## цветом: шлем на голове, наушники, ПНВ / очки, броня или пояс на корпусе, рюкзак за спиной, подсумки — плашками
## на своих местах (половинки — как на полоске мест). Координаты — в рамке 244 × 258 (EquipDoll.FIGURE).

const BOX := Vector2(244.0, 258.0)
const LINE := Color(0.78, 0.74, 0.66, 0.5)
const WORN := Color(1.0, 0.8, 0.48, 0.92)
const FILL := Color(1.0, 0.8, 0.48, 0.07)
## Пунктир (true) или сплошная линия.
var dashed: bool = true

var _eq: Dictionary = {}
## Правая половина контура от шеи по часовой стрелке (левая — зеркально): шея, плечо, рука наружу и вниз
## под 45°, кисть, рука обратно к подмышке, бок, бедро, нога наружу, стопа, нога внутри, пах.
const HALF := [
	Vector2(130, 41), Vector2(131, 50), Vector2(156, 54), Vector2(164, 60),
	Vector2(226, 122), Vector2(232, 133), Vector2(224, 140), Vector2(214, 136),
	Vector2(154, 82), Vector2(150, 112), Vector2(149, 140), Vector2(154, 156),
	Vector2(158, 240), Vector2(170, 252), Vector2(168, 257), Vector2(140, 257),
	Vector2(137, 172), Vector2(122, 164),
]
const HEAD := Vector2(122, 24)
const HEAD_R := 17.0
## Корпус под бронёй: плечи — пояс.
const TORSO := [Vector2(90, 56), Vector2(154, 56), Vector2(150, 112), Vector2(148, 142), Vector2(96, 142), Vector2(94, 112)]


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	custom_minimum_size = BOX


func set_equipment(eq: Dictionary) -> void:
	_eq = eq
	queue_redraw()


func _outline() -> PackedVector2Array:
	var pts := PackedVector2Array()
	for p: Vector2 in HALF:
		pts.append(p)
	for i in range(HALF.size() - 2, -1, -1):
		var p: Vector2 = HALF[i]
		pts.append(Vector2(244.0 - p.x, p.y))
	pts.append(HALF[0])
	return pts


func _line(a: Vector2, b: Vector2, c: Color, w: float) -> void:
	if dashed:
		draw_dashed_line(a, b, c, w, 5.0)
	else:
		draw_line(a, b, c, w, true)


func _poly(pts: PackedVector2Array, c: Color, w: float, closed: bool = true) -> void:
	var n := pts.size()
	for i in range(n - 1 if not closed else n):
		_line(pts[i], pts[(i + 1) % n], c, w)


func _has(slot: String) -> bool:
	return _eq.get(slot) is Dictionary and not (_eq[slot] as Dictionary).is_empty()


func _id(slot: String) -> String:
	return String((_eq[slot] as Dictionary).get("id", "")) if _has(slot) else ""


func _draw() -> void:
	# рюкзак — за спиной: выступает из-за корпуса, лямки на плечах
	if _has("backpack"):
		var bp := Rect2(80, 60, 84, 96)
		draw_rect(bp, FILL)
		_poly(PackedVector2Array([bp.position, Vector2(bp.end.x, bp.position.y), bp.end, Vector2(bp.position.x, bp.end.y)]), WORN, 2.0)
	# сам человек
	_poly(_outline(), LINE, 1.5, false)
	if dashed:
		draw_arc(HEAD, HEAD_R, 0.0, TAU, 28, LINE, 1.5)
	else:
		draw_arc(HEAD, HEAD_R, 0.0, TAU, 28, LINE, 1.5, true)
	if _has("backpack"):
		for x: float in [104.0, 140.0]:
			_line(Vector2(x, 54), Vector2(x - (6.0 if x < 122 else -6.0), 112), WORN, 2.0)
	# броня или пояс
	if _has("armor"):
		var v := WeaponDb.vest(_id("armor"))
		# пояс — без мягкой защиты (data/armor.json soft: null)
		var belt: bool = v.get("soft") == null
		if belt:
			var b := Rect2(94, 132, 56, 14)
			draw_rect(b, FILL)
			_poly(PackedVector2Array([b.position, Vector2(b.end.x, b.position.y), b.end, Vector2(b.position.x, b.end.y)]), WORN, 2.2)
		else:
			draw_colored_polygon(PackedVector2Array(TORSO), FILL)
			_poly(PackedVector2Array(TORSO), WORN, 2.2)
		_draw_pouches(_eq.armor as Dictionary, belt)
	# шлем — дугой над головой, крепления — точками
	if _has("helmet"):
		draw_arc(HEAD, HEAD_R + 3.0, PI, TAU, 18, WORN, 3.0, true)
		_line(Vector2(HEAD.x - HEAD_R - 3.0, HEAD.y), Vector2(HEAD.x + HEAD_R + 3.0, HEAD.y), WORN, 1.5)
		if "NVG" in ItemDb.helmet_mounts(_eq):
			draw_rect(Rect2(HEAD.x - 4.0, HEAD.y - HEAD_R - 6.0, 8.0, 5.0), WORN)
	if _has("ears"):
		for sx: float in [-1.0, 1.0]:
			draw_rect(Rect2(HEAD.x + sx * (HEAD_R + 1.0) - 4.0, HEAD.y - 6.0, 8.0, 13.0), WORN)
	if _has("eyes"):
		if bool(ItemDb.equip(_id("eyes")).get("nvg", false)):
			# ПНВ: на площадке шлема или на головном креплении — трубки перед глазами
			for sx: float in [-1.0, 1.0]:
				draw_rect(Rect2(HEAD.x + sx * 6.0 - 3.5, HEAD.y - 5.0, 7.0, 9.0), WORN)
			if not _has("helmet"):
				draw_arc(HEAD, HEAD_R + 1.0, PI * 1.15, PI * 1.85, 12, WORN, 1.5, true)
		else:
			_line(Vector2(HEAD.x - 11.0, HEAD.y - 2.0), Vector2(HEAD.x + 11.0, HEAD.y - 2.0), WORN, 3.0)
	# оружие на теле: пистолет — кобура на правом бедре, ракетница — на левом
	if _has("sidearm"):
		draw_rect(Rect2(156, 160, 10, 24), WORN, false, 2.0)
	if _has("launcher"):
		draw_rect(Rect2(78, 160, 10, 24), WORN, false, 2.0)
	# крупное оружие — ремнём через грудь
	if _has("primary") or _has("secondary"):
		_line(Vector2(96, 60), Vector2(150, 138), Color(WORN, 0.55), 2.0)


## Подсумки — плашками по местам: места в ряд по груди (у тяжёлой брони — два ряда), полуслот — половина места.
func _draw_pouches(armor: Dictionary, belt: bool) -> void:
	var places := int(WeaponDb.vest(String(armor.get("id", ""))).get("places", 0))
	if places <= 0:
		return
	var rows := 2 if places > 5 else 1
	var per_row := ceili(float(places) / float(rows))
	var w := 56.0 / float(per_row)
	for p: Dictionary in ItemDb.pouch_list(armor):
		var at := int(p.at)
		var half := ItemDb.pouch_half(String(p.id))
		var first := (at - 1) / 2
		var row := first / per_row
		var col := float((at - 1) - row * per_row * 2) * 0.5
		var y := 136.0 if belt else 96.0 + float(row) * 20.0
		var rect := Rect2(94.0 + col * w + 1.0, y, w * float(half) * 0.5 - 2.0, 16.0 if belt else 18.0)
		draw_rect(rect, Color(WORN, 0.35))
		draw_rect(rect, WORN, false, 1.5)
