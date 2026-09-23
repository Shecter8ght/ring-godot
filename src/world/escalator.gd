@tool
class_name Escalator
extends Node3D
## Эскалаторы блокаута: пара (или больше) рядом, остановленных — по ним ходят как по лестнице.
## Своя сцена (scenes/world/escalator.tscn): двигать, крутить и менять размеры в редакторе.
## Геометрия строится скриптом из параметров (и в редакторе тоже) и в .tscn не сохраняется.
##
## Оси: X — ширина пары, Z — длина; подъём идёт в сторону -Z (перед узла — верх эскалатора).
## Размеры — по типовому торговому эскалатору: ступень 1000 мм, уклон 30°, горизонтальные
## площадки у концов ~2.4 м (3 плоские ступени + гребёнка), балюстрада из стекла ~1 м.
## Наверху — площадка второго этажа и опущенная противопожарная штора: этажи отрезаны друг
## от друга (см. docs/STATUS.md — как объясняется переход между этажами).
##
## Узел в группе "prop_keepout": под ним и вокруг пропсы кольца не ставятся (keepout_rect).

## Высота подъёма, м (от пола до пола).
@export var rise: float = 6.0:
	set(v):
		rise = clampf(v, 1.0, 12.0)
		queue_build()
## Угол наклона, град (30 — норма для торговых, 35 — только при подъёме до 6 м).
@export_range(25.0, 35.0, 0.5) var incline_deg: float = 30.0:
	set(v):
		incline_deg = v
		queue_build()
## Ширина ступени, м.
@export var step_width: float = 1.0:
	set(v):
		step_width = clampf(v, 0.6, 1.2)
		queue_build()
## Сколько эскалаторов рядом.
@export_range(1, 4) var units: int = 2:
	set(v):
		units = v
		queue_build()
## Зазор между эскалаторами, м.
@export var unit_gap: float = 0.4:
	set(v):
		unit_gap = maxf(0.0, v)
		queue_build()
## Горизонтальная площадка у каждого конца, м.
@export var landing: float = 2.4:
	set(v):
		landing = maxf(1.0, v)
		queue_build()
## Площадка второго этажа за верхним концом, м (до шторы).
@export var top_platform: float = 3.0:
	set(v):
		top_platform = maxf(0.0, v)
		queue_build()
## Опущенная противопожарная штора наверху — этаж выше закрыт.
@export var fire_curtain: bool = true:
	set(v):
		fire_curtain = v
		queue_build()
## Отступ от эскалатора, где кольцо не ставит пропсы, м.
@export var keepout_margin: float = 2.0

## Боковой отступ от края ступени до внешней грани (фартук + балюстрада), м.
const SIDE := 0.32
const BALUSTRADE_H := 1.0
const SLAB_T := 0.3
## Проступь ступени по горизонтали, м.
const TREAD := 0.4

var _gen: Node3D
var _pending: bool = false


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("nav_source")
	add_to_group("prop_keepout")
	_build()


func queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


## Длина по горизонтали: площадка + марш + площадка.
func run_length() -> float:
	return rise / tan(deg_to_rad(incline_deg))


func total_length() -> float:
	return landing * 2.0 + run_length()


func unit_width() -> float:
	return step_width + SIDE * 2.0


func total_width() -> float:
	return units * unit_width() + (units - 1) * unit_gap


## Прямоугольник в мировых XZ, где кольцо не ставит пропсы: эскалаторы, верхняя площадка и отступ.
func keepout_rect() -> Rect2:
	var hw := total_width() * 0.5 + 0.3
	var l := total_length()
	var z0 := l * 0.5
	var z1 := -l * 0.5 - top_platform
	var rect := Rect2()
	var first := true
	for x in [-hw, hw]:
		for z in [z0, z1]:
			var p := global_transform * Vector3(x, 0, z)
			if first:
				rect = Rect2(Vector2(p.x, p.z), Vector2.ZERO)
				first = false
			else:
				rect = rect.expand(Vector2(p.x, p.z))
	return rect.grow(keepout_margin)


func _build() -> void:
	_pending = false
	if _gen:
		_gen.free()
	_gen = Node3D.new()
	_gen.name = "_Generated"
	# без owner — сгенерированное не попадает в сохранённую сцену
	add_child(_gen)
	var l := total_length()
	var zb := l * 0.5 - landing
	var zt := -l * 0.5 + landing
	var uw := unit_width()
	var w := total_width()
	var body := BlockoutMesh.new()
	var steps := BlockoutMesh.new()
	var glass := BlockoutMesh.new()
	var col := StaticBody3D.new()
	col.name = "Walk"
	_gen.add_child(col)
	for u in range(units):
		var xc := -w * 0.5 + uw * 0.5 + u * (uw + unit_gap)
		var x0 := xc - uw * 0.5
		var x1 := xc + uw * 0.5
		# ферма под маршем: верх чуть ниже ступеней, низ уходит под пол у нижнего конца
		body.ramp("gb_partition", x0, x1, zb, zt, -0.25, rise - 0.25, 1.1)
		# нижняя площадка (плита с гребёнкой) и верхняя — на уровне плиты этажа
		body.box("steel_dark", Vector3(xc, 0.01, zb + landing * 0.5), Vector3(uw, 0.02, landing))
		# ступени: проступь TREAD, подступенок по уклону
		var n := int(floor(run_length() / TREAD))
		var riser := rise / float(n)
		for i in range(n):
			var za := zb - i * TREAD * run_length() / (n * TREAD)
			var zc := zb - (i + 1) * TREAD * run_length() / (n * TREAD)
			var top := riser * (i + 1)
			steps.box("gb_slab", Vector3(xc, top - 0.13, (za + zc) * 0.5), Vector3(step_width, 0.26, absf(za - zc)))
		# балюстрады по обе стороны: стекло по маршу и площадкам, поручень поверх
		for side in [-1.0, 1.0]:
			var xb: float = xc + side * (step_width * 0.5 + 0.1)
			glass.ramp("glass", xb - 0.01, xb + 0.01, zb, zt, BALUSTRADE_H, rise + BALUSTRADE_H, BALUSTRADE_H)
			glass.box("glass", Vector3(xb, BALUSTRADE_H * 0.5, zb + landing * 0.5), Vector3(0.02, BALUSTRADE_H, landing))
			glass.box("glass", Vector3(xb, rise + BALUSTRADE_H * 0.5, zt - landing * 0.5), Vector3(0.02, BALUSTRADE_H, landing))
			body.ramp("steel_dark", xb - 0.04, xb + 0.04, zb, zt, BALUSTRADE_H + 0.06, rise + BALUSTRADE_H + 0.06, 0.08)
			body.box("steel_dark", Vector3(xb, BALUSTRADE_H + 0.02, zb + landing * 0.5), Vector3(0.08, 0.08, landing))
			body.box("steel_dark", Vector3(xb, rise + BALUSTRADE_H + 0.02, zt - landing * 0.5), Vector3(0.08, 0.08, landing))
			# концевые стойки балюстрады
			body.box("gb_partition", Vector3(xb, BALUSTRADE_H * 0.5, l * 0.5 - 0.1), Vector3(0.12, BALUSTRADE_H, 0.2))
		# по чему ходят: гладкий наклон по носкам ступеней (ступени — только картинка)
		var cs := CollisionShape3D.new()
		var shape := ConvexPolygonShape3D.new()
		var hx := step_width * 0.5
		shape.points = PackedVector3Array([
			Vector3(xc - hx, 0.0, zb), Vector3(xc + hx, 0.0, zb), Vector3(xc - hx, rise, zt), Vector3(xc + hx, rise, zt),
			Vector3(xc - hx, -0.4, zb), Vector3(xc + hx, -0.4, zb), Vector3(xc - hx, rise - 0.4, zt), Vector3(xc + hx, rise - 0.4, zt),
		])
		cs.shape = shape
		col.add_child(cs)
	body.emit(_gen, "Body", true, true)
	steps.emit(_gen, "Steps", false, false)
	glass.emit(_gen, "Balustrade", true, false)
	_build_upper(w, l, zt)


## Площадка второго этажа, колонны под её дальним краем, ограждение и штора.
func _build_upper(w: float, l: float, zt: float) -> void:
	# всё верхнее — один узел-перекрытие: уровень прячет его целиком, когда игрок внизу
	var up := BlockoutMesh.new()
	var ww := w + 0.6
	var z_end := -l * 0.5 - top_platform
	var depth := zt - z_end
	up.box("gb_slab", Vector3(0, rise - SLAB_T * 0.5, (zt + z_end) * 0.5), Vector3(ww, SLAB_T, depth))
	for side in [-1.0, 1.0]:
		up.box("gb_structural", Vector3(side * (ww * 0.5 - 0.3), (rise - SLAB_T) * 0.5, z_end + 0.3), Vector3(0.5, rise - SLAB_T, 0.5))
		up.box("glass", Vector3(side * ww * 0.5, rise + 0.55, (zt + z_end) * 0.5), Vector3(0.02, 1.1, depth))
	if fire_curtain:
		# полотно шторы до плиты и короб рулона над ним
		up.box("gb_fire", Vector3(0, rise + 1.6, z_end + 0.08), Vector3(ww, 3.2, 0.12))
		up.box("steel_dark", Vector3(0, rise + 3.4, z_end + 0.1), Vector3(ww + 0.2, 0.4, 0.4))
	var deck := up.emit(_gen, "Upper", true, true)
	# перекрытие выше игрока уровень прячет в изометрии (тень остаётся) — как этажи паркинга
	deck.add_to_group("decks")
	deck.set_meta("deck_y", rise)
