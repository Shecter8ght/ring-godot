@tool
class_name HideoutEntrance
extends Node3D
## Спуск в убежище у ТЦ: бетонный приямок с лестницей ниже земли, площадка и гермодверь убежища.
## Отсюда игроки начинают рейд — точка появления (SpawnPoint с bunker = true) на площадке внизу:
## стены приямка и парапет прячут от тех, кто на улице. Уровень, если такие точки есть, выбирает
## только их. Земля над приямком вырезается (группа "ground_holes", hole_rect) — SectorBuilder.
##
## Узел ставится и поворачивается руками (сцена улицы); начало — верх лестницы на уровне земли,
## спуск идёт вдоль +Z. Геометрия строится из параметров, в сцену не сохраняется.
##
## Столкновения: земля сектора — бесконечная плоскость (SectorBuilder, группа "ground_plane"), она
## вытолкнула бы вниз стоящего наверх. Кто внутри контура приямка — тому столкновение с ней
## снимается (держат ступени и площадка), вышел — возвращается. Лучи (пули, зрение мародёров)
## плоскость по-прежнему останавливает: с улицы в приямок не видно и не простреливается.

## По ширине — четверо в ряд, глубина — внизу два роста человека (Balance.STANCE_HEIGHT.stand).
@export var width: float = 4.4:
	set(v):
		width = maxf(2.0, v)
		_queue_rebuild()
@export var depth: float = 3.6:
	set(v):
		depth = clampf(v, 1.5, 6.0)
		_queue_rebuild()
@export var stair_len: float = 6.3:
	set(v):
		stair_len = maxf(2.0, v)
		_queue_rebuild()
@export var landing_len: float = 4.2:
	set(v):
		landing_len = maxf(2.0, v)
		_queue_rebuild()
@export var display_name: String = "Спуск в убежище"

const WALL_T := 0.3
## Парапет над землёй: по пояс — из-за него можно смотреть, лёжа — не видно.
const PARAPET_H := 1.05
const STEP_H := 0.17
## Сколько метров земли вокруг приямка тоже вырезать (края прячутся под стенами и порогом).
const HOLE_PAD := 0.05
## Порог у верха лестницы: бетонная плита на уровне земли, закрывает срез асфальта.
const SILL_LEN := 0.8

var _built: Node3D
var _rebuild_queued: bool = false


func _ready() -> void:
	add_to_group("ground_holes")
	add_to_group("prop_keepout")
	_rebuild()
	set_physics_process(not Engine.is_editor_hint())


## Внутри ли контура приямка (с порогом) точка мира p.
func contains(p: Vector3, pad: float = 0.0) -> bool:
	var l := global_transform.affine_inverse() * p
	return absf(l.x) <= width * 0.5 + WALL_T + pad and l.z >= -SILL_LEN * 0.5 - pad and l.z <= total_len() + WALL_T + pad and l.y < 1.0


func _physics_process(_delta: float) -> void:
	var ground := get_tree().get_first_node_in_group("ground_plane") as PhysicsBody3D
	if ground == null:
		return
	for n in get_tree().get_nodes_in_group("all_players"):
		var p := n as PhysicsBody3D
		if p == null:
			continue
		var inside := contains(p.global_position, 0.3)
		var had: bool = p.get_meta("bunker_" + name, false)
		if inside and not had:
			p.add_collision_exception_with(ground)
			p.set_meta("bunker_" + name, true)
		elif not inside and had:
			p.remove_collision_exception_with(ground)
			p.set_meta("bunker_" + name, false)


func _queue_rebuild() -> void:
	if not is_inside_tree() or _rebuild_queued:
		return
	_rebuild_queued = true
	(func() -> void:
		_rebuild_queued = false
		_rebuild()).call_deferred()


func total_len() -> float:
	return stair_len + landing_len


## Прямоугольник выреза земли: центр (мир, XZ), половины размеров (вдоль X и Z узла), курс, рад.
func hole_rect() -> Dictionary:
	var hw := width * 0.5 + WALL_T + HOLE_PAD
	var z0 := -HOLE_PAD
	var z1 := total_len() + WALL_T + HOLE_PAD
	var c := global_transform * Vector3(0.0, 0.0, (z0 + z1) * 0.5)
	return {"center": Vector2(c.x, c.z), "half": Vector2(hw, (z1 - z0) * 0.5), "yaw": global_rotation.y}


## Для расстановки пропсов (прямоугольник в мире, с запасом).
func keepout_rect() -> Rect2:
	var hw := width * 0.5 + WALL_T + 1.0
	var r := Rect2()
	var first := true
	for x in [-hw, hw]:
		for z in [-SILL_LEN - 1.0, total_len() + WALL_T + 1.0]:
			var p := global_transform * Vector3(x, 0.0, z)
			if first:
				r = Rect2(Vector2(p.x, p.z), Vector2.ZERO)
				first = false
			else:
				r = r.expand(Vector2(p.x, p.z))
	return r


func _rebuild() -> void:
	if _built:
		_built.queue_free()
	_built = Node3D.new()
	_built.name = "Built"
	add_child(_built)
	var L := total_len()
	var hw := width * 0.5
	var wall_mat := SectorMaterials.get_material("concrete_wall_006", true)
	var floor_mat := SectorMaterials.get_material("concrete_floor_worn_001", true)
	var walls := SurfaceTool.new()
	walls.begin(Mesh.PRIMITIVE_TRIANGLES)
	var floors := SurfaceTool.new()
	floors.begin(Mesh.PRIMITIVE_TRIANGLES)
	var wall_h := depth + PARAPET_H
	var wy := (PARAPET_H - depth) * 0.5
	# стены приямка с парапетом: две боковые и торцевая (с дверью)
	var wall_boxes: Array = [
		[Vector3(-hw - WALL_T * 0.5, wy, L * 0.5 + WALL_T * 0.5 - SILL_LEN * 0.5), Vector3(WALL_T, wall_h, L + WALL_T + SILL_LEN)],
		[Vector3(hw + WALL_T * 0.5, wy, L * 0.5 + WALL_T * 0.5 - SILL_LEN * 0.5), Vector3(WALL_T, wall_h, L + WALL_T + SILL_LEN)],
		[Vector3(0.0, wy, L + WALL_T * 0.5), Vector3(width, wall_h, WALL_T)],
	]
	for b in wall_boxes:
		_box(walls, b[0], b[1])
	# площадка внизу и порог наверху
	_box(floors, Vector3(0.0, -depth - 0.15, stair_len + landing_len * 0.5), Vector3(width, 0.3, landing_len))
	_box(floors, Vector3(0.0, -0.12, -SILL_LEN * 0.5), Vector3(width, 0.26, SILL_LEN))
	# ступени — видимые; ходят по пандусу под ними (капсула по ступенькам не шагает)
	var steps := maxi(4, int(round(depth / STEP_H)))
	var rise := depth / steps
	var run := stair_len / steps
	for i in range(steps):
		var top := -rise * (i + 1)
		var bottom := -depth - 0.3
		_box(floors, Vector3(0.0, (top + bottom) * 0.5, run * (i + 0.5)), Vector3(width, top - bottom, run))
	_mesh(walls, wall_mat, "Walls")
	_mesh(floors, floor_mat, "Floors")
	# коллизия: стены — источник навмеша (обходятся), пандус и площадка — нет: мародёры сюда не
	# заходят по навигации, спуск только для игроков
	var wall_body := StaticBody3D.new()
	wall_body.name = "WallBody"
	_built.add_child(wall_body)
	for b in wall_boxes:
		_shape(wall_body, Transform3D(Basis(), b[0]), b[1])
	if not Engine.is_editor_hint():
		wall_body.add_to_group("nav_source")
	var floor_body := StaticBody3D.new()
	floor_body.name = "FloorBody"
	_built.add_child(floor_body)
	_shape(floor_body, Transform3D(Basis(), Vector3(0.0, -depth - 0.15, stair_len + landing_len * 0.5)), Vector3(width, 0.3, landing_len))
	_shape(floor_body, Transform3D(Basis(), Vector3(0.0, -0.12, -SILL_LEN * 0.5)), Vector3(width, 0.26, SILL_LEN))
	# пандус от верха лестницы до площадки
	var slope := atan2(depth, stair_len)
	var ramp_len := sqrt(depth * depth + stair_len * stair_len)
	var ramp_basis := Basis(Vector3.RIGHT, slope)
	var ramp_center := Vector3(0.0, -depth * 0.5, stair_len * 0.5) + ramp_basis * Vector3(0.0, -0.15, 0.0)
	_shape(floor_body, Transform3D(ramp_basis, ramp_center), Vector3(width, 0.3, ramp_len))
	_door(L)
	_railings(hw, slope, ramp_len)
	# лампа над дверью: тусклая, тёплая — ночью видно ступени
	var lamp := OmniLight3D.new()
	lamp.name = "DoorLamp"
	lamp.light_color = Color(1.0, 0.78, 0.5)
	lamp.light_energy = 0.6
	lamp.omni_range = 5.5
	lamp.shadow_enabled = false
	lamp.position = Vector3(0.0, -depth + 2.55, L - 0.35)
	_built.add_child(lamp)
	var bulb := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.06
	sm.height = 0.12
	bulb.mesh = sm
	var bm := StandardMaterial3D.new()
	bm.emission_enabled = true
	bm.emission = Color(1.0, 0.8, 0.5)
	bm.emission_energy_multiplier = 4.0
	bulb.material_override = bm
	bulb.position = lamp.position + Vector3(0.0, 0.05, 0.15)
	_built.add_child(bulb)
	# табличка на двери
	var sign := Label3D.new()
	sign.text = "УБЕЖИЩЕ"
	sign.font_size = 42
	sign.pixel_size = 0.004
	sign.modulate = Color(0.95, 0.9, 0.75)
	sign.position = Vector3(0.0, -depth + 2.25, L - 0.02)
	sign.rotation.y = PI
	_built.add_child(sign)
	# точка появления — на площадке (игроки встают вокруг неё)
	if not Engine.is_editor_hint():
		var sp := SpawnPoint.new()
		sp.name = "Spawn"
		sp.display_name = display_name
		sp.bunker = true
		sp.position = Vector3(0.0, -depth + 0.05, stair_len + landing_len * 0.5)
		_built.add_child(sp)


## Гермодверь в торце: стальное полотно в раме, штурвал, петли.
func _door(L: float) -> void:
	var steel := SectorMaterials.get_material("green_metal_rust", true)
	var dark := SectorMaterials.get_material("steel_dark", true)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var y0 := -depth
	_box(st, Vector3(0.0, y0 + 1.05, L - 0.06), Vector3(1.2, 2.1, 0.12))
	_mesh(st, steel, "Door")
	var fr := SurfaceTool.new()
	fr.begin(Mesh.PRIMITIVE_TRIANGLES)
	_box(fr, Vector3(-0.68, y0 + 1.12, L - 0.08), Vector3(0.14, 2.24, 0.16))
	_box(fr, Vector3(0.68, y0 + 1.12, L - 0.08), Vector3(0.14, 2.24, 0.16))
	_box(fr, Vector3(0.0, y0 + 2.2, L - 0.08), Vector3(1.5, 0.14, 0.16))
	# штурвал и засовы
	_box(fr, Vector3(0.0, y0 + 1.15, L - 0.16), Vector3(0.5, 0.05, 0.05))
	_box(fr, Vector3(0.0, y0 + 1.15, L - 0.16), Vector3(0.05, 0.5, 0.05))
	for y in [0.45, 1.75]:
		_box(fr, Vector3(-0.52, y0 + y, L - 0.14), Vector3(0.12, 0.22, 0.06))
	_mesh(fr, dark, "DoorFrame")


## Перила вдоль лестницы: стойки и поручень с обеих сторон.
func _railings(hw: float, slope: float, ramp_len: float) -> void:
	var dark := SectorMaterials.get_material("steel_dark", true)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var b := Basis(Vector3.RIGHT, slope)
	for side in [-1.0, 1.0]:
		var x: float = side * (hw - 0.08)
		_box(st, Vector3(x, -depth * 0.5 + 0.9, stair_len * 0.5), Vector3(0.05, 0.05, ramp_len), b)
		for k in range(4):
			var z := stair_len * (0.1 + 0.8 * float(k) / 3.0)
			var y := -depth * z / stair_len
			_box(st, Vector3(x, y + 0.45, z), Vector3(0.04, 0.9, 0.04))
	_mesh(st, dark, "Rails")


func _mesh(st: SurfaceTool, mat: Material, nm: String) -> void:
	st.generate_tangents()
	var mi := MeshInstance3D.new()
	mi.name = nm
	mi.mesh = st.commit()
	mi.material_override = mat
	_built.add_child(mi)


func _shape(body: StaticBody3D, xf: Transform3D, size: Vector3) -> void:
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	cs.transform = xf
	body.add_child(cs)


## Коробка с UV в метрах (как у геометрии сектора): center, size, поворот basis. Лицевая сторона
## грани — по часовой, если смотреть снаружи (как у Godot).
func _box(st: SurfaceTool, center: Vector3, size: Vector3, basis: Basis = Basis()) -> void:
	var h := size * 0.5
	# грань: нормаль и две оси в её плоскости (локальные оси коробки)
	var faces := [
		[Vector3.RIGHT, Vector3.BACK, Vector3.UP], [Vector3.LEFT, Vector3.BACK, Vector3.UP],
		[Vector3.UP, Vector3.RIGHT, Vector3.BACK], [Vector3.DOWN, Vector3.RIGHT, Vector3.BACK],
		[Vector3.BACK, Vector3.RIGHT, Vector3.UP], [Vector3.FORWARD, Vector3.RIGHT, Vector3.UP],
	]
	for f in faces:
		var n: Vector3 = f[0]
		var u: Vector3 = f[1]
		var v: Vector3 = f[2]
		var c := n * h
		var hu := u * h
		var hv := v * h
		var loc: Array[Vector3] = [c - hu - hv, c + hu - hv, c + hu + hv, c - hu + hv]
		var pts: Array[Vector3] = []
		var uvs: Array[Vector2] = []
		for p in loc:
			var wp := center + basis * p
			pts.append(wp)
			uvs.append(Vector2((center + p).dot(u), -(center + p).dot(v)))
		var wn := (basis * n).normalized()
		for tri in [[0, 1, 2], [0, 2, 3]]:
			var a: int = tri[0]
			var b: int = tri[1]
			var d: int = tri[2]
			# по часовой снаружи: нормаль треугольника по правилу правой руки — внутрь
			if (pts[b] - pts[a]).cross(pts[d] - pts[a]).dot(wn) > 0.0:
				var t := b
				b = d
				d = t
			for k in [a, b, d]:
				st.set_normal(wn)
				st.set_uv(uvs[k])
				st.add_vertex(pts[k])
