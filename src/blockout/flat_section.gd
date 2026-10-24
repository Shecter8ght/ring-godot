@tool
extends "res://src/blockout/study_building.gd"
## Секция современного жилого дома (блокаут «Проспекта», замечания владельца 2026-10-24: «в каждой квартире —
## кухня, 1–3 комнаты, прихожая, ванная с туалетом, балкон; подъездная группа продумана; вид — новостройки
## и высотки»). Ядро посередине: холл с лифтами, лестница двумя маршами, мусоропровод; на этаже четыре угловые
## квартиры (две 3-комнатные, две 2-комнатные); первый этаж — подъездная группа (тамбур, вестибюль, консьерж,
## почтовые ящики, колясочная) и две квартиры. Открытые этажи — с комнатами и лутом, выше — закрытый объём
## с окнами и балконами (башня). Размеры уже игровые: ширины проходов × 1,3, высоты × 1,15 (AGENTS.md, п. 9).
## Оси: X — вдоль дома, Z — в глубину; подъезд — на стороне −Z (двор), улица — +Z.

## Сколько нижних этажей собирать с интерьерами (остальные — объём).
@export var open_floors: int = 3
## Балконы на длинных фасадах (у башен-«стекляшек» — нет).
@export var balconies: bool = true
## Сплошные ленты остекления вместо окон (небоскрёб).
@export var glass_bands: bool = false

const CORE_HX: float = 4.5      # полуширина ядра по X
const CORE_HZ: float = 1.5      # полуглубина холла по Z
const STAIR_D: float = 4.0      # глубина лестничной клетки (за холлом, +Z)
const LIFT_D: float = 4.0       # глубина лифтов (−Z от холла)
const DOOR_W: float = 1.17      # 0,9 × 1,3
const DOOR_H: float = 2.42      # 2,1 × 1,15
const WALL_T: float = 0.16
const OUTER_T: float = 0.3
const FLAT_V: float = 1.5       # тамбур квартир: от холла до двери


func rebuild() -> void:
	queued = false
	if is_instance_valid(generated):
		generated.free()
	_spots.clear()
	_doors.clear()
	_keys.clear()
	_lamps.clear()
	generated = Node3D.new()
	generated.name = "_Geometry"
	add_child(generated)
	var g: RefCounted = Geometry.new(generated, Geometry.materials())
	_section(g)
	g.finish()
	set_meta("height_m", float(floors) * story_height)
	set_meta("enterable", open_floors > 0)
	_place_gameplay()


func _section(g: RefCounted) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var h: float = story_height
	# основание и плиты перекрытий (с проёмом над маршами лестницы)
	g.box(Vector3(0, -0.18, 0), Vector3(footprint.x + 0.8, 0.56, footprint.y + 0.8), "concrete")
	for level: int in range(1, floors + 1):
		var y: float = float(level) * h
		_floor_slab(g, y, level <= open_floors)
	# этажи
	for level: int in range(floors):
		var y: float = float(level) * h
		if level < open_floors:
			_open_floor(g, y, level)
		else:
			_closed_floor(g, y, level)
	# парапет крыши и будка выхода на крышу над ядром
	var roof: float = float(floors) * h + 0.15
	for sx: float in [-1.0, 1.0]:
		g.box(Vector3(sx * hx, roof + 0.5, 0), Vector3(0.2, 1.0, footprint.y), "concrete")
		g.box(Vector3(0, roof + 0.5, sx * hz), Vector3(footprint.x, 1.0, 0.2), "concrete")
	g.box(Vector3(0, roof + 1.5, 0), Vector3(CORE_HX * 2.0, 3.0, (CORE_HZ + STAIR_D) * 2.0 - 2.0), "wall")
	_entrance_group(g)


## Плита перекрытия: проём над маршами (x −3…3, z холл+лестница) только на открытых этажах.
func _floor_slab(g: RefCounted, y: float, open_below: bool) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var t: float = 0.3
	if not open_below:
		g.box(Vector3(0, y - t * 0.5, 0), Vector3(footprint.x, t, footprint.y), "slab")
		return
	var z0: float = CORE_HZ
	var z1: float = CORE_HZ + STAIR_D
	# четыре куска вокруг проёма лестницы
	g.box(Vector3(0, y - t * 0.5, (-hz + z0) * 0.5), Vector3(footprint.x, t, z0 + hz), "slab")
	g.box(Vector3(0, y - t * 0.5, (z1 + hz) * 0.5), Vector3(footprint.x, t, hz - z1), "slab")
	g.box(Vector3((-hx - CORE_HX) * 0.5, y - t * 0.5, (z0 + z1) * 0.5), Vector3(hx - CORE_HX, t, z1 - z0), "slab")
	g.box(Vector3((hx + CORE_HX) * 0.5, y - t * 0.5, (z0 + z1) * 0.5), Vector3(hx - CORE_HX, t, z1 - z0), "slab")


## Закрытый этаж: наружные стены, окна или ленты остекления, балконы.
func _closed_floor(g: RefCounted, y: float, level: int) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var h: float = story_height
	g.box(Vector3(0, y + h * 0.5, 0), Vector3(footprint.x, h, footprint.y), "wall")
	if glass_bands:
		for sz: float in [-1.0, 1.0]:
			g.box(Vector3(0, y + h * 0.5 + 0.1, sz * (hz + 0.02)), Vector3(footprint.x - 0.6, h - 0.9, 0.04), "dark", false)
		for sx: float in [-1.0, 1.0]:
			g.box(Vector3(sx * (hx + 0.02), y + h * 0.5 + 0.1, 0), Vector3(0.04, h - 0.9, footprint.y - 0.6), "dark", false)
		return
	var bays: int = maxi(2, int(footprint.x / 3.4))
	for bay: int in range(bays):
		var x: float = -hx + (float(bay) + 0.5) * footprint.x / float(bays)
		for sz: float in [-1.0, 1.0]:
			g.box(Vector3(x, y + 1.55, sz * (hz + 0.02)), Vector3(1.6, 1.5, 0.04), "dark", false)
	var ends: int = maxi(1, int(footprint.y / 3.4))
	for k: int in range(ends):
		var z: float = -hz + (float(k) + 0.5) * footprint.y / float(ends)
		for sx: float in [-1.0, 1.0]:
			g.box(Vector3(sx * (hx + 0.02), y + 1.55, z), Vector3(0.04, 1.5, 1.6), "dark", false)
	if balconies and level > 0:
		for sx: float in [-1.0, 1.0]:
			for sz: float in [-1.0, 1.0]:
				_balcony(g, y, sx, sz, false)


## Балкон у комнаты A (длинный фасад), снаружи стены: плита, парапет, проём двери в стене — у открытых этажей.
func _balcony(g: RefCounted, y: float, sx: float, sz: float, open: bool) -> void:
	var hz: float = footprint.y * 0.5
	var u: float = CORE_HX + 2.5 + (footprint.x * 0.5 - CORE_HX - 2.5) * 0.5   # середина комнаты A по длине
	var bx: float = sx * u
	var depth: float = 1.4
	var bz: float = sz * (hz + depth * 0.5 + OUTER_T * 0.5)
	g.box(Vector3(bx, y + 0.08, bz), Vector3(3.2, 0.16, depth), "concrete", open)
	g.box(Vector3(bx, y + 0.6, sz * (hz + depth + OUTER_T * 0.5)), Vector3(3.2, 1.1, 0.08), "steel", open)
	for ex: float in [-1.0, 1.0]:
		g.box(Vector3(bx + ex * 1.6, y + 0.6, bz), Vector3(0.08, 1.1, depth), "steel", open)


## Открытый этаж: ядро, холл, лестница, четыре квартиры (первый этаж — подъездная группа вместо северных).
func _open_floor(g: RefCounted, y: float, level: int) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var h: float = story_height
	var sh: float = h * 0.5
	# наружные стены с окнами и дверями по квартирам — собираются по кускам ниже; здесь — ядро
	# холл: стены вдоль z = ±CORE_HZ между x = ±CORE_HX, двери в тамбуры квартир на торцах (x = ±CORE_HX)
	_wall_x(g, -CORE_HZ, -CORE_HX, CORE_HX, y, h, [[-3.5, 1.0, DOOR_H], [0.0, DOOR_W, DOOR_H], [2.5, 1.9, DOOR_H]])   # мусоропровод, проход, лифты
	_wall_x(g, CORE_HZ, -CORE_HX, CORE_HX, y, h, [[-3.75, DOOR_W, DOOR_H]])                           # дверь на лестницу
	# лифты (нерабочие) и мусоропровод за холлом
	g.box(Vector3(2.5, y + sh, -CORE_HZ - LIFT_D * 0.5), Vector3(4.0, h, LIFT_D), "steel")
	g.box(Vector3(2.5, y + 1.1, -CORE_HZ - 0.06), Vector3(1.8, 2.2, 0.04), "dark", false)
	g.box(Vector3(-2.5, y + sh, -CORE_HZ - LIFT_D * 0.5), Vector3(4.0, h, LIFT_D), "wall")
	# лестничная клетка: два марша вдоль X, площадки по торцам
	var zs0: float = CORE_HZ
	var zs1: float = CORE_HZ + STAIR_D
	_wall_x(g, zs1, -CORE_HX, CORE_HX, y, h, [])
	g.box(Vector3(-CORE_HX, y + sh, (zs0 + zs1) * 0.5), Vector3(WALL_T, h, STAIR_D), "wall")
	g.box(Vector3(CORE_HX, y + sh, (zs0 + zs1) * 0.5), Vector3(WALL_T, h, STAIR_D), "wall")
	var za: float = zs0 + 1.0
	var zb: float = zs1 - 1.0
	g.box(Vector3(-3.75, y - 0.12, (zs0 + zs1) * 0.5), Vector3(1.5, 0.24, STAIR_D), "concrete")          # западная площадка (уровень этажа)
	g.stairs(Vector3(-3.0, y, za), Vector3(3.0, y + sh, za), 1.7, 10, "concrete")
	g.box(Vector3(3.75, y + sh - 0.12, (zs0 + zs1) * 0.5), Vector3(1.5, 0.24, STAIR_D), "concrete")      # восточная площадка (полэтажа)
	g.stairs(Vector3(3.0, y + sh, zb), Vector3(-3.0, y + h, zb), 1.7, 10, "concrete")
	g.box(Vector3(0, y + sh * 0.5 + 0.2, (za + zb) * 0.5), Vector3(6.0, 0.9, 0.06), "steel", false)       # перила между маршами
	_lamps.append(Vector3(0, y + h - 0.4, 0))
	_lamps.append(Vector3(0, y + h - 0.4, (zs0 + zs1) * 0.5))
	# квартиры: четыре угла; на первом этаже северные (−Z, со двора) — подъездная группа
	for sx: float in [-1.0, 1.0]:
		for sz: float in [-1.0, 1.0]:
			if level == 0 and sz < 0.0:
				continue
			_flat(g, y, sx, sz, 3 if sx * sz > 0.0 else 2)
	if level == 0:
		_lobby(g, y)
	# полосы ядра у фасадов — технические (щитовая, кладовая уборщицы): глухие объёмы
	if level > 0:
		g.box(Vector3(0, y + sh, (-hz - CORE_HZ - LIFT_D) * 0.5), Vector3(CORE_HX * 2.0, h, hz - CORE_HZ - LIFT_D), "wall")
	g.box(Vector3(0, y + sh, (hz + CORE_HZ + STAIR_D) * 0.5), Vector3(CORE_HX * 2.0, h, hz - CORE_HZ - STAIR_D), "wall")
	# торцевые наружные стены (x = ±hx) — окна комнат C и A
	for sx: float in [-1.0, 1.0]:
		var gaps: Array = [[-hz * 0.65, 1.6, 2.3, 0.9], [-hz * 0.25, 1.6, 2.3, 0.9], [hz * 0.25, 1.6, 2.3, 0.9], [hz * 0.65, 1.6, 2.3, 0.9]]
		_wall_z(g, sx * hx, -hz, hz, y, h, gaps, OUTER_T)


## Квартира в углу (sx — сторона по X от ядра, sz — сторона по Z от холла): u — от ядра к торцу, v — от оси холла к фасаду.
func _flat(g: RefCounted, y: float, sx: float, sz: float, rooms: int) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var h: float = story_height
	var sh: float = h * 0.5
	var umax: float = hx - CORE_HX           # длина квартиры от ядра до торца
	var vmax: float = hz                     # глубина от оси холла до фасада
	var p := func(u: float, v: float) -> Vector3: return Vector3(sx * (CORE_HX + u), 0.0, sz * v)
	# стены вдоль X (постоянное v) и вдоль Z (постоянное u) — своими коробками
	var wall_u := func(v: float, u0: float, u1: float, gaps: Array, t: float = WALL_T) -> void:
		# стена при фиксированном v, от u0 до u1, проёмы [u, ширина, высота, низ?]
		var cuts: Array = gaps.duplicate()
		cuts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
		var u: float = u0
		for c: Array in cuts:
			var cu0: float = float(c[0]) - float(c[1]) * 0.5
			var cu1: float = float(c[0]) + float(c[1]) * 0.5
			if cu0 > u:
				_seg_u(g, y, sx, sz, v, u, cu0, 0.0, h, t)
			var top: float = float(c[2])
			if top < h:
				_seg_u(g, y, sx, sz, v, cu0, cu1, top, h, t)
			if c.size() > 3 and float(c[3]) > 0.0:
				_seg_u(g, y, sx, sz, v, cu0, cu1, 0.0, float(c[3]), t)
			u = cu1
		if u < u1:
			_seg_u(g, y, sx, sz, v, u, u1, 0.0, h, t)
	var wall_v := func(u: float, v0: float, v1: float, gaps: Array, t: float = WALL_T) -> void:
		var cuts: Array = gaps.duplicate()
		cuts.sort_custom(func(a: Array, b: Array) -> bool: return float(a[0]) < float(b[0]))
		var v: float = v0
		for c: Array in cuts:
			var cv0: float = float(c[0]) - float(c[1]) * 0.5
			var cv1: float = float(c[0]) + float(c[1]) * 0.5
			if cv0 > v:
				_seg_v(g, y, sx, sz, u, v, cv0, 0.0, h, t)
			var top: float = float(c[2])
			if top < h:
				_seg_v(g, y, sx, sz, u, cv0, cv1, top, h, t)
			if c.size() > 3 and float(c[3]) > 0.0:
				_seg_v(g, y, sx, sz, u, cv0, cv1, 0.0, float(c[3]), t)
			v = cv1
		if v < v1:
			_seg_v(g, y, sx, sz, u, v, v1, 0.0, h, t)
	# планировка (u от ядра, v от оси холла):
	#   тамбур u 0…2.5 v 0…1.5 (общий с соседом по стороне) — дверь квартиры в стене v = 1.5
	#   прихожая u 0…5, v 1.5…5; санузел u 5…9, v 1.5…5 (дверь из прихожей)
	#   коридор v 5…7, u 0…9; комната C u 9…umax, v 0…7 (окно в торце); кухня u 0…5 v 7…vmax (окно на фасад);
	#   комната A u 5…umax v 7…vmax (угловая, балкон); при трёх комнатах A делится при u = (5 + umax) / 2
	var uc: float = 9.0 if umax > 12.0 else umax - 3.5
	var ua: float = 5.0
	# стена квартиры у ядра (u = 0): тамбур открыт в холл (дверь в стене холла), дальше глухая
	wall_v.call(0.0, FLAT_V, vmax, [])
	# тамбур: перегородка u = 2.5 от v 0 до 1.5 и дверь квартиры в стене v = 1.5 (u 0…2.5)
	wall_v.call(2.5, 0.0, FLAT_V, [])
	wall_u.call(FLAT_V, 0.0, 2.5, [[1.25, DOOR_W, DOOR_H]])
	# ось холла (v = 0) между соседними квартирами: от u 2.5 до umax — глухая (у сосед квартиры своя сторона)
	wall_u.call(0.0, 2.5, umax, [], WALL_T * 0.5)
	# прихожая / санузел
	wall_v.call(ua, FLAT_V, 5.0, [[3.2, DOOR_W, DOOR_H]])                 # дверь в санузел
	wall_u.call(5.0, 0.0, uc, [[2.5, DOOR_W, DOOR_H]])                     # прихожая → коридор
	g.box(p.call(7.0, 3.2) + Vector3(0, y + 0.45, 0), Vector3(1.6, 0.9, 0.7), "accent")      # ванна
	g.box(p.call(5.6, 4.4) + Vector3(0, y + 0.3, 0), Vector3(0.6, 0.6, 0.5), "accent")       # унитаз
	# комната C у торца
	wall_v.call(uc, 0.0, 7.0, [[6.0, DOOR_W, DOOR_H]])
	# коридор → кухня и комната A (стена v = 7)
	wall_u.call(7.0, 0.0, umax, [[2.5, DOOR_W, DOOR_H], [ua + 2.0, DOOR_W, DOOR_H]])
	wall_v.call(ua, 7.0, vmax, [])
	if rooms == 3:
		var um: float = (ua + umax) * 0.5
		wall_v.call(um, 7.0, vmax, [])
		wall_u.call(7.0, um, umax, [[um + 1.5, DOOR_W, DOOR_H]])          # дверь во вторую комнату
	# фасад (v = vmax): окна кухни и комнат, балконная дверь у A
	var ub: float = CORE_HX + 2.5 + (umax - 2.5) * 0.5 - CORE_HX           # середина A по u
	var fgaps: Array = [[2.5, 1.6, 2.3, 0.9], [ub - 0.8, DOOR_W, DOOR_H], [ub + 0.9, 1.0, 2.3, 0.9]]
	if rooms == 3:
		fgaps = [[2.5, 1.6, 2.3, 0.9], [ub - 2.3, 1.4, 2.3, 0.9], [ub + 1.0, DOOR_W, DOOR_H]]
	wall_u.call(vmax, 0.0, umax, fgaps, OUTER_T)
	if balconies:
		_balcony(g, y, sx, sz, true)
	# мебель и лут: кухня, шкафы в комнатах, тумба в прихожей
	_furniture(g, p.call(2.5, vmax - 0.5) + Vector3(0, y + 0.45, 0), Vector3(3.0, 0.9, 0.6), Vector3(0, 0, -sz), "cabinet", _theme("home"), "Кухня", loot_density)
	_furniture(g, p.call(uc + 1.0, 0.6) + Vector3(0, y + 1.0, 0), Vector3(1.0, 2.0, 0.5), Vector3(0, 0, sz), "cabinet", _theme("home"), "", loot_density)
	_furniture(g, p.call(ua + 0.6, vmax - 0.6) + Vector3(0, y + 1.0, 0), Vector3(0.5, 2.0, 1.0), Vector3(1, 0, 0) * sx, "cabinet", _theme("home"), "", loot_density)
	g.box(p.call(uc + 1.8, 5.5) + Vector3(0, y + 0.25, 0), Vector3(1.6, 0.5, 2.0), "accent")         # кровать
	g.box(p.call(1.0, 2.8) + Vector3(0, y + 0.4, 0), Vector3(0.5, 0.8, 1.0), "accent")               # тумба в прихожей


func _seg_u(g: RefCounted, y: float, sx: float, sz: float, v: float, u0: float, u1: float, y0: float, y1: float, t: float) -> void:
	if u1 - u0 <= 0.01 or y1 - y0 <= 0.01:
		return
	var xc: float = sx * (CORE_HX + (u0 + u1) * 0.5)
	g.box(Vector3(xc, y + (y0 + y1) * 0.5, sz * v), Vector3(u1 - u0, y1 - y0, t), "wall")


func _seg_v(g: RefCounted, y: float, sx: float, sz: float, u: float, v0: float, v1: float, y0: float, y1: float, t: float) -> void:
	if v1 - v0 <= 0.01 or y1 - y0 <= 0.01:
		return
	var zc: float = sz * (v0 + v1) * 0.5
	g.box(Vector3(sx * (CORE_HX + u), y + (y0 + y1) * 0.5, zc), Vector3(t, y1 - y0, v1 - v0), "wall")


## Подъездная группа на первом этаже со стороны двора (−Z): тамбур с двойной дверью, вестибюль с консьержем
## и почтовыми ящиками, колясочная; из вестибюля — в холл ядра.
func _lobby(g: RefCounted, y: float) -> void:
	var hx: float = footprint.x * 0.5
	var hz: float = footprint.y * 0.5
	var h: float = story_height
	var sh: float = h * 0.5
	# наружная стена со стороны двора: тамбур 3 м с двойной дверью 2 × 1,17 по оси, окна по сторонам
	_wall_x(g, -hz, -hx, hx, y, h, [[0.0, 2.4, DOOR_H], [-hx * 0.5, 1.6, 2.3, 0.9], [hx * 0.5, 1.6, 2.3, 0.9], [-hx * 0.8, 1.6, 2.3, 0.9], [hx * 0.8, 1.6, 2.3, 0.9]], OUTER_T)
	# тамбур: стена с второй дверью
	_wall_x(g, -hz + 3.0, -2.5, 2.5, y, h, [[0.0, 2.4, DOOR_H]])
	g.box(Vector3(-2.5, y + sh, -hz + 1.5), Vector3(WALL_T, h, 3.0), "wall")
	g.box(Vector3(2.5, y + sh, -hz + 1.5), Vector3(WALL_T, h, 3.0), "wall")
	# вестибюль: x −9…9, z от тамбура до холла (−CORE_HZ − LIFT_D); стены по бокам отделяют колясочную и комнату консьержа
	var zl0: float = -hz + 3.0
	var zl1: float = -CORE_HZ - LIFT_D
	_wall_z(g, -9.0, -hz, 0.0, y, h, [[zl0 + 1.5, DOOR_W, DOOR_H]])                 # дверь в комнату консьержа
	_wall_z(g, 9.0, -hz, 0.0, y, h, [[zl0 + 1.5, DOOR_W, DOOR_H]])                  # дверь в колясочную
	g.box(Vector3(12.0, y + sh, 0.0), Vector3(6.0, h, WALL_T), "wall")             # колясочная отделена от тамбура квартир
	g.box(Vector3(-12.0, y + sh, 0.0), Vector3(6.0, h, WALL_T), "wall")
	g.box(Vector3(6.75, y + sh, -CORE_HZ), Vector3(4.5, h, WALL_T), "wall")          # ниши у холла закрыты
	g.box(Vector3(-6.75, y + sh, -CORE_HZ), Vector3(4.5, h, WALL_T), "wall")
	g.box(Vector3(12.0, y + 0.6, -hz + 2.0), Vector3(3.0, 1.2, 1.0), "accent")       # коляски и велосипеды
	g.box(Vector3(-12.0, y + 0.4, -hz + 2.0), Vector3(1.4, 0.8, 0.7), "accent")      # стол консьержа
	# колясочная x 9…hx, с окном на двор; комната консьержа x −hx…−9 — закрыта, окно выдачи в вестибюль
	g.box(Vector3(-9.0 + 0.6, y + 0.55, zl0 + 2.0), Vector3(1.2, 1.1, 2.4), "accent")                  # стойка консьержа
	_spot(Vector3(-9.0 + 1.6, y + _lp(), zl0 + 2.0), "desk", "office", "Стойка консьержа", 0, loot_density)
	g.box(Vector3(6.0, y + 1.2, zl1 - 0.4), Vector3(4.0, 1.6, 0.4), "accent")                          # почтовые ящики
	_spot(Vector3(6.0, y + _lp(), zl1 - 1.0), "cabinet", "resident", "Почтовые ящики", 0, loot_density)
	g.box(Vector3(0.0, y + 0.3, zl0 + 1.5), Vector3(3.0, 0.06, 2.0), "dark", false)                     # грязезащитный коврик
	# проход из вестибюля в холл ядра: проём в стене холла со стороны лифтов — лифтовый холл открыт в вестибюль
	# (лифтовые боксы занимают x 0.5…4.5, мусоропровод −4.5…−0.5 — проход между ними шириной 1)
	g.box(Vector3(0, y + sh, zl1 + 0.5), Vector3(0.06, h, 0.06), "steel", false)
	_lamps.append(Vector3(0, y + h - 0.4, (zl0 + zl1) * 0.5))
	# козырёк над входом, ступени и пандус снаружи
	g.box(Vector3(0, y + DOOR_H + 0.5, -hz - 1.6), Vector3(6.0, 0.2, 3.0), "slab", false)
	g.box(Vector3(-3.0, y + DOOR_H + 0.2, -hz - 3.0), Vector3(0.15, 0.6, 0.15), "steel", false)
	g.box(Vector3(3.0, y + DOOR_H + 0.2, -hz - 3.0), Vector3(0.15, 0.6, 0.15), "steel", false)
	g.box(Vector3(0, y + 0.075, -hz - 1.0), Vector3(5.0, 0.15, 2.0), "concrete")                        # площадка входа


func _entrance_group(_g: RefCounted) -> void:
	pass
