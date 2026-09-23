@tool
class_name BlockoutBuilding
extends Node3D
## Постройка-блокаут вне кольца: здание, многоуровневый паркинг, мачта, навес, остановка.
## Своя сцена (scenes/world/blockout_building.tscn), чтобы в редакторе её двигать, крутить и
## менять размеры в инспекторе. Геометрия строится скриптом из параметров — и в редакторе тоже —
## и в .tscn не сохраняется. Оси: X — ширина вдоль фасада, Z — глубина; перед — сторона -Z.
## Двери и ворота — дочерние BlockoutOpening: проём режется в ближайшей стене.
##
## Перекрытия (этажи паркинга, крыши навесов) — узлы группы "decks" с meta "deck_y":
## уровень прячет их (оставляя тень), когда игрок ниже, иначе изометрия упирается в крышу.

enum Kind { BUILDING, GARAGE, MAST, CANOPY, SHELTER }

const DOOR_SCENE := preload("res://scenes/props/door.tscn")
## Высоты проёмов, м: дверь (СП: не ниже 1.9, берём 2.1), ворота под грузовик.
const DOOR_H := 2.1
const GATE_H := 4.5
## Ограждение перекрытий паркинга — не ниже 1.1 м.
const PARAPET_H := 1.1
const SLAB_T := 0.3

@export var kind: Kind = Kind.BUILDING:
	set(v):
		kind = v
		queue_build()
@export var display_name: String = "":
	set(v):
		display_name = v
		queue_build()
## Ширина (X) и глубина (Z), м.
@export var size: Vector2 = Vector2(20, 16):
	set(v):
		size = Vector2(maxf(2.0, v.x), maxf(2.0, v.y))
		queue_build()
## Высота стен / мачты / навеса, м.
@export var height: float = 6.0:
	set(v):
		height = maxf(1.0, v)
		queue_build()
@export var wall_thickness: float = 0.3:
	set(v):
		wall_thickness = clampf(v, 0.1, 1.0)
		queue_build()
@export_group("Паркинг")
## Уровней, включая землю; верхний — открытая крыша.
@export var levels: int = 3:
	set(v):
		levels = clampi(v, 1, 6)
		queue_build()
## От пола до пола, м (паркинг: чистая высота ≥ 2.2 + плита).
@export var level_height: float = 3.2:
	set(v):
		level_height = maxf(2.6, v)
		queue_build()
@export var ramp_width: float = 5.0:
	set(v):
		ramp_width = maxf(3.0, v)
		queue_build()
## Шаг колонн, м (под три машиноместа по 2.5 м).
@export var column_grid: float = 8.0:
	set(v):
		column_grid = maxf(3.0, v)
		queue_build()
@export var column_size: float = 0.6

var _gen: Node3D
var _pending: bool = false
var _door_count: int = 0


func _ready() -> void:
	if not Engine.is_editor_hint():
		# навмеш уровня печётся по статическим коллайдерам узлов этой группы
		add_to_group("nav_source")
	_build()


func queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	if _gen:
		_gen.free()
	_gen = Node3D.new()
	_gen.name = "_Generated"
	# без owner — сгенерированное не попадает в сохранённую сцену
	add_child(_gen)
	_door_count = 0
	match kind:
		Kind.BUILDING:
			_build_building()
		Kind.GARAGE:
			_build_garage()
		Kind.MAST:
			_build_mast()
		Kind.CANOPY:
			_build_canopy()
		Kind.SHELTER:
			_build_shelter()
	if display_name != "":
		var label := Label3D.new()
		label.text = display_name
		label.pixel_size = 0.04
		label.font_size = 48
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.modulate = Color(0.9, 0.92, 0.95, 0.85)
		label.outline_size = 10
		var top := height if kind != Kind.GARAGE else float(levels - 1) * level_height + PARAPET_H
		label.position = Vector3(0, top + 2.0, 0)
		_gen.add_child(label)


# ---------------------------------------------------------------- здание

func _build_building() -> void:
	var walls := BlockoutMesh.new()
	var slab := BlockoutMesh.new()
	var w := size.x
	var d := size.y
	var t := wall_thickness
	slab.box("gb_slab", Vector3(0, -0.1, 0), Vector3(w, 0.2, d))
	# стороны: начало, конец (по часовой сверху), проёмы режем по дочерним BlockoutOpening
	var sides := [
		[Vector3(-w * 0.5, 0, -d * 0.5), Vector3(w * 0.5, 0, -d * 0.5)],
		[Vector3(w * 0.5, 0, -d * 0.5), Vector3(w * 0.5, 0, d * 0.5)],
		[Vector3(w * 0.5, 0, d * 0.5), Vector3(-w * 0.5, 0, d * 0.5)],
		[Vector3(-w * 0.5, 0, d * 0.5), Vector3(-w * 0.5, 0, -d * 0.5)],
	]
	for side in sides:
		_wall_with_openings(walls, side[0], side[1], t, height)
	var wb := walls.emit(_gen, "Walls", true, true)
	slab.emit(_gen, "Floor", true, false)
	# стены здания закрывают то, что за ними (в прицеле) — см. SectorBuilder._add_occluder
	var meshes: Array[Mesh] = []
	for c in wb.get_children():
		if c is MeshInstance3D:
			meshes.append((c as MeshInstance3D).mesh)
	var oi := BlockoutMesh.make_occluder(meshes)
	if oi:
		_gen.add_child(oi)


## Прямая стена от a до b (в плане), с прорезанными проёмами дочерних BlockoutOpening,
## которые ближе метра к линии. Над проёмом — перемычка до верха стены.
func _wall_with_openings(m: BlockoutMesh, a: Vector3, b: Vector3, t: float, h: float) -> void:
	var dir := (b - a)
	var len := dir.length()
	dir /= len
	var cuts: Array = []
	for c in get_children():
		var op := c as BlockoutOpening
		if op == null:
			continue
		var rel := op.position - a
		rel.y = 0.0
		var along := rel.dot(dir)
		var off := absf(rel.dot(Vector3(-dir.z, 0, dir.x)))
		if off > 1.0 or along < 0.0 or along > len:
			continue
		var half := op.width * 0.5
		cuts.append({"s": clampf(along - half, 0.0, len), "e": clampf(along + half, 0.0, len), "op": op})
	cuts.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return float(x.s) < float(y.s))
	var cur := 0.0
	for cut in cuts:
		_wall_piece(m, a, dir, cur, float(cut.s), t, 0.0, h)
		var op: BlockoutOpening = cut.op
		var oh := DOOR_H if op.kind == BlockoutOpening.Kind.DOOR else GATE_H
		oh = minf(oh, h - 0.3)
		_wall_piece(m, a, dir, float(cut.s), float(cut.e), t, oh, h)
		if op.kind == BlockoutOpening.Kind.DOOR:
			_add_door(a + dir * float(cut.s), dir, float(cut.e) - float(cut.s), oh)
		cur = maxf(cur, float(cut.e))
	_wall_piece(m, a, dir, cur, len, t, 0.0, h)


func _wall_piece(m: BlockoutMesh, a: Vector3, dir: Vector3, s: float, e: float, t: float, y0: float, y1: float) -> void:
	if e - s < 0.01 or y1 - y0 < 0.01:
		return
	var mid := a + dir * ((s + e) * 0.5)
	var basis := Basis(dir, Vector3.UP, dir.cross(Vector3.UP))
	# коробка в осях стены: длина вдоль dir, толщина поперёк
	var size3 := Vector3(e - s, y1 - y0, t)
	var h := size3 * 0.5
	var corners: Array[Vector3] = []
	for sx in [-1.0, 1.0]:
		for sy in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				corners.append(mid + Vector3.UP * ((y0 + y1) * 0.5) + basis * Vector3(h.x * sx, h.y * sy, h.z * sz))
	# стены постройки — вдоль осей X/Z, поэтому хватает AABB по углам
	var lo := corners[0]
	var hi := corners[0]
	for p in corners:
		lo = lo.min(p)
		hi = hi.max(p)
	m.box("gb_facade", (lo + hi) * 0.5, hi - lo)


## Створка двери (та же сцена, что в кольце). Только в игре: в редакторе скрипт двери не работает.
func _add_door(hinge: Vector3, dir: Vector3, width: float, h: float) -> void:
	if Engine.is_editor_hint():
		return
	var door := DOOR_SCENE.instantiate() as Door
	door.name = "Door_%d" % _door_count
	_door_count += 1
	door.width = width - 0.1
	door.height = h - 0.05
	door.transform = Transform3D(Basis(dir, Vector3.UP, dir.cross(Vector3.UP).normalized()), hinge + dir * 0.05)
	_gen.add_child(door)


# ---------------------------------------------------------------- паркинг

## Прямоугольник {x0,x1,z0,z1}.
func _rect(x0: float, x1: float, z0: float, z1: float) -> Dictionary:
	return {"x0": x0, "x1": x1, "z0": z0, "z1": z1}


## Плита уровня минус дыра под пандус: до четырёх прямоугольников вокруг дыры.
func _slab_minus(outer: Dictionary, hole: Dictionary) -> Array:
	var out: Array = []
	if hole.is_empty():
		return [outer]
	out.append(_rect(outer.x0, hole.x0, outer.z0, outer.z1))
	out.append(_rect(hole.x1, outer.x1, outer.z0, outer.z1))
	out.append(_rect(hole.x0, hole.x1, outer.z0, hole.z0))
	out.append(_rect(hole.x0, hole.x1, hole.z1, outer.z1))
	return out.filter(func(r: Dictionary) -> bool: return float(r.x1) - float(r.x0) > 0.05 and float(r.z1) - float(r.z0) > 0.05)


## Пандус k (с уровня k-1 на k): нечётные — у левого края и вверх к +Z, чётные — у правого и к -Z.
func _ramp_rect(k: int) -> Dictionary:
	var w := size.x
	var len := _ramp_len()
	var x0 := -w * 0.5 + 1.0 if k % 2 == 1 else w * 0.5 - 1.0 - ramp_width
	return _rect(x0, x0 + ramp_width, -len * 0.5, len * 0.5)


## Длина пандуса: уклон не круче 1:6 (~9.5°) — удобно и агенту навмеша.
func _ramp_len() -> float:
	return minf(level_height * 6.0, size.y - 8.0)


func _build_garage() -> void:
	var w := size.x
	var d := size.y
	var outer := _rect(-w * 0.5, w * 0.5, -d * 0.5, d * 0.5)
	for lvl in range(levels):
		var y := float(lvl) * level_height
		var m := BlockoutMesh.new()
		if lvl == 0:
			m.box("gb_slab", Vector3(0, -0.1, 0), Vector3(w, 0.2, d))
		else:
			for r in _slab_minus(outer, _ramp_rect(lvl)):
				m.box("gb_slab", Vector3((r.x0 + r.x1) * 0.5, y - SLAB_T * 0.5, (r.z0 + r.z1) * 0.5), Vector3(r.x1 - r.x0, SLAB_T, r.z1 - r.z0))
			# ограждение по краю перекрытия
			var pt := 0.2
			m.box("gb_fence", Vector3(0, y + PARAPET_H * 0.5, -d * 0.5 + pt * 0.5), Vector3(w, PARAPET_H, pt))
			m.box("gb_fence", Vector3(0, y + PARAPET_H * 0.5, d * 0.5 - pt * 0.5), Vector3(w, PARAPET_H, pt))
			m.box("gb_fence", Vector3(-w * 0.5 + pt * 0.5, y + PARAPET_H * 0.5, 0), Vector3(pt, PARAPET_H, d))
			m.box("gb_fence", Vector3(w * 0.5 - pt * 0.5, y + PARAPET_H * 0.5, 0), Vector3(pt, PARAPET_H, d))
		# пандус, который стартует с этого уровня, принадлежит ему (виден вместе с ним)
		if lvl + 1 < levels:
			var rr := _ramp_rect(lvl + 1)
			var up_z := 1.0 if (lvl + 1) % 2 == 1 else -1.0
			var z0: float = rr.z0 if up_z > 0.0 else rr.z1
			var z1: float = rr.z1 if up_z > 0.0 else rr.z0
			m.ramp("gb_slab", rr.x0, rr.x1, z0, z1, y, y + level_height, SLAB_T)
			# бортики пандуса — тоже наклонные
			m.ramp("gb_fence", rr.x0 - 0.2, rr.x0, z0, z1, y + 0.8, y + level_height + 0.8, 0.8)
			m.ramp("gb_fence", rr.x1, rr.x1 + 0.2, z0, z1, y + 0.8, y + level_height + 0.8, 0.8)
		# перекрытия не растворяются у камеры (как полы) — лишние прячет уровень целиком
		var body := m.emit(_gen, "Level_%d" % lvl, true, false)
		body.set_meta("deck_y", y)
		if lvl > 0:
			body.add_to_group("decks")
	# светильники под каждым перекрытием — под плитой темно даже на закате
	for lvl in range(levels - 1):
		var ly := float(lvl + 1) * level_height - SLAB_T - 0.3
		for gx in range(-1, 2):
			for gz in range(-1, 2):
				var lamp := OmniLight3D.new()
				lamp.light_color = Color(0.85, 0.95, 0.9)
				lamp.light_energy = 2.2
				lamp.omni_range = maxf(w, d) * 0.3
				lamp.omni_attenuation = 1.2
				lamp.position = Vector3(float(gx) * w * 0.3, ly, float(gz) * d * 0.3)
				_gen.add_child(lamp)
	# колонны сквозь все уровни до крыши; в дырах под пандусы колонн нет
	var cols := BlockoutMesh.new()
	var top := float(levels - 1) * level_height - SLAB_T
	if top > 0.5:
		var nx := maxi(1, int(round((w - 2.0) / column_grid)))
		var nz := maxi(1, int(round((d - 2.0) / column_grid)))
		for i in range(nx + 1):
			for j in range(nz + 1):
				var x := lerpf(-w * 0.5 + 1.0, w * 0.5 - 1.0, float(i) / nx)
				var z := lerpf(-d * 0.5 + 1.0, d * 0.5 - 1.0, float(j) / nz)
				var blocked := false
				for k in range(1, levels):
					var rr := _ramp_rect(k)
					if x > rr.x0 - 0.8 and x < rr.x1 + 0.8 and z > rr.z0 - 0.8 and z < rr.z1 + 0.8:
						blocked = true
				if not blocked:
					cols.box("gb_structural", Vector3(x, top * 0.5, z), Vector3(column_size, top, column_size))
		cols.emit(_gen, "Columns", true, true)


# ---------------------------------------------------------------- мелочь

func _build_mast() -> void:
	var m := BlockoutMesh.new()
	# ствол сужается ступенями — читается как решётчатая мачта
	var steps := 4
	for i in range(steps):
		var k := 1.0 - float(i) / steps * 0.6
		var h0 := height * float(i) / steps
		m.box("gb_structural", Vector3(0, h0 + height / steps * 0.5, 0), Vector3(size.x * k, height / steps, size.y * k))
	m.emit(_gen, "Mast", true, true)
	var beacon := OmniLight3D.new()
	beacon.light_color = Color(1.0, 0.1, 0.05)
	beacon.light_energy = 4.0
	beacon.omni_range = 6.0
	beacon.position = Vector3(0, height + 0.5, 0)
	_gen.add_child(beacon)


func _build_canopy() -> void:
	var cols := BlockoutMesh.new()
	var w := size.x
	var d := size.y
	var n := maxi(1, int(round(d / 6.0)))
	for i in range(n + 1):
		var z := lerpf(-d * 0.5 + 0.3, d * 0.5 - 0.3, float(i) / n)
		for x in [-w * 0.5 + 0.3, w * 0.5 - 0.3]:
			cols.box("gb_structural", Vector3(x, height * 0.5, z), Vector3(0.4, height, 0.4))
	cols.emit(_gen, "Columns", true, true)
	_roof(height)


func _build_shelter() -> void:
	var m := BlockoutMesh.new()
	var w := size.x
	var d := size.y
	m.box("gb_partition", Vector3(0, height * 0.5, d * 0.5 - 0.1), Vector3(w, height, 0.2))
	m.box("gb_partition", Vector3(-w * 0.5 + 0.1, height * 0.5, d * 0.25), Vector3(0.2, height, d * 0.5))
	m.box("gb_partition", Vector3(w * 0.5 - 0.1, height * 0.5, d * 0.25), Vector3(0.2, height, d * 0.5))
	m.emit(_gen, "Walls", true, true)
	_roof(height)


## Крыша-плита — перекрытие из группы "decks" (прячется, когда игрок под ней).
func _roof(y: float) -> void:
	var m := BlockoutMesh.new()
	m.box("gb_slab", Vector3(0, y + 0.1, 0), Vector3(size.x + 0.6, 0.2, size.y + 0.6))
	var body := m.emit(_gen, "Roof", true, false)
	body.set_meta("deck_y", y)
	body.add_to_group("decks")
