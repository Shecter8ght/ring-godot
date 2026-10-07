extends Node
## Офлайн-авторинг: слой старения убежища — декали поверх архитектуры. Лучами от точек навигации
## находит стены, потолок и пол и ставит: подтёки от потолка вниз, пыль и грязь на полу вдоль стен,
## копоть над настенными лампами, пятна на полу, надписи маркером и мелом. Расстановка случайная, но
## с фиксированным зерном — повторный запуск даёт ту же сцену. Слой «Grime» пересоздаётся целиком.
## Запуск — после author_shelter_scene и author_shelter_dressing (они пересобирают сцену):
## tools/godot.cmd --headless res://tools/author_shelter_grime.tscn

const BASE: String = "res://levels/shelter/"
const GRIME: String = "res://assets/shelter/textures/grime/"
const SEED: int = 4021
const LEAKS: int = 5
const NOTES: int = 9
## Сколько каких декалей и как далеко друг от друга (м).
const DUST_SPACING: float = 2.4
const LEAK_SPACING: float = 2.2
const LEAK_SHARE: float = 0.45
const FLOOR_SPOTS: int = 26
const NOTE_COUNT: int = 9
const FADE_BEGIN: float = 28.0

var _level: Node3D
var _group: Node3D
var _arch: Node
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _space: PhysicsDirectSpaceState3D
var _counts: Dictionary = {}


func _ready() -> void:
	_rng.seed = SEED
	_level = (load(BASE + "Shelter_Interior.tscn") as PackedScene).instantiate() as Node3D
	var previous: Node = _level.get_node_or_null("Grime")
	if previous:
		previous.free()
	var original_script: Script = _level.get_script() as Script
	_level.set_script(null)
	add_child(_level)
	for i: int in range(3):
		await get_tree().physics_frame
	_space = _level.get_world_3d().direct_space_state
	_arch = _level.get_node("Architecture")
	_group = Node3D.new()
	_group.name = "Grime"
	_level.add_child(_group)
	_group.owner = _level
	var points: Array[Vector3] = _sample_points()
	var walls: Array[Dictionary] = _find_walls(points)
	_counts["points"] = points.size()
	_counts["walls"] = walls.size()
	_dust(walls)
	_leaks(walls)
	_soot()
	_floor_spots()
	_notes(walls)
	remove_child(_level)
	_level.set_script(original_script)
	var packed: PackedScene = PackedScene.new()
	assert(packed.pack(_level) == OK)
	assert(ShelterSave.save(packed, BASE + "Shelter_Interior.tscn") == OK)
	print("GRIME_AUTHORED " + JSON.stringify(_counts))
	_level.free()
	get_tree().quit()


# ---------------------------------------------------------------- поиск стен

## Точки на полу: случайные точки внутри полигонов навигации, примерно одна на квадратный метр
## (вершин мало — большие полигоны), не чаще одной на клетку 1 м.
func _sample_points() -> Array[Vector3]:
	var region: NavigationRegion3D = _level.get_node("Navigation/Interior") as NavigationRegion3D
	var nav: NavigationMesh = region.navigation_mesh
	var verts: PackedVector3Array = nav.get_vertices()
	var seen: Dictionary = {}
	var out: Array[Vector3] = []
	for i: int in range(nav.get_polygon_count()):
		var poly: PackedInt32Array = nav.get_polygon(i)
		for t: int in range(1, poly.size() - 1):
			var a: Vector3 = region.global_transform * verts[poly[0]]
			var b: Vector3 = region.global_transform * verts[poly[t]]
			var c: Vector3 = region.global_transform * verts[poly[t + 1]]
			var area: float = (b - a).cross(c - a).length() * 0.5
			for k: int in range(ceili(area * 1.2)):
				var u: float = _rng.randf()
				var v: float = _rng.randf()
				if u + v > 1.0:
					u = 1.0 - u
					v = 1.0 - v
				var p: Vector3 = a + (b - a) * u + (c - a) * v
				var key: Vector3i = Vector3i(roundi(p.x), roundi(p.y * 2.0), roundi(p.z))
				if not seen.has(key):
					seen[key] = true
					out.append(p)
	return out


## Стены вокруг точек: попадание луча в архитектуру с горизонтальной нормалью; у каждой — высота
## потолка над ней. Не чаще одной на клетку 0.8 м и одно направление нормали.
func _find_walls(points: Array[Vector3]) -> Array[Dictionary]:
	var seen: Dictionary = {}
	var out: Array[Dictionary] = []
	for p: Vector3 in points:
		# навигация лежит и на крышках ящиков и столов — нужна точка прямо над полом архитектуры
		var below: Dictionary = _ray(p + Vector3.UP * 0.3, p + Vector3.DOWN * 0.8)
		if below.is_empty() or (below.normal as Vector3).y < 0.9:
			continue
		var floor_y: float = (below.position as Vector3).y
		var ceiling: Dictionary = _ray(p + Vector3.UP * 0.4, p + Vector3.UP * 14.0)
		if ceiling.is_empty() or (ceiling.normal as Vector3).y > -0.7:
			continue
		var ceil_y: float = (ceiling.position as Vector3).y
		for k: int in range(8):
			var a: float = TAU * float(k) / 8.0
			var dir: Vector3 = Vector3(sin(a), 0.0, cos(a))
			var from: Vector3 = p + Vector3.UP * 1.2
			var hit: Dictionary = _ray(from, from + dir * 7.0)
			if hit.is_empty():
				continue
			var n: Vector3 = hit.normal
			if absf(n.y) > 0.2:
				continue
			n = Vector3(n.x, 0.0, n.z).normalized()
			# луч из-под геометрии возвращает нулевую нормаль — такую стену не брать
			if n.length() < 0.5:
				continue
			var at: Vector3 = hit.position
			var key: Vector3i = Vector3i(roundi(at.x / 0.8), roundi(at.z / 0.8), roundi(atan2(n.x, n.z) * 2.0))
			if seen.has(key):
				continue
			seen[key] = true
			out.append({"at": Vector3(at.x, floor_y, at.z), "n": n, "floor": floor_y, "ceil": _ceiling_at(at + n * 0.2, floor_y, ceil_y)})
	# порядок — по зерну, не по порядку вершин
	for i: int in range(out.size() - 1, 0, -1):
		var j: int = _rng.randi_range(0, i)
		var t: Dictionary = out[i]
		out[i] = out[j]
		out[j] = t
	return out


## Потолок прямо у стены (у стены может быть ниже — балка, антресоль).
func _ceiling_at(p: Vector3, floor_y: float, fallback: float) -> float:
	var hit: Dictionary = _ray(Vector3(p.x, floor_y + 0.4, p.z), Vector3(p.x, floor_y + 14.0, p.z))
	return (hit.position as Vector3).y if not hit.is_empty() else fallback


## Луч только по архитектуре (стены, пол, потолок, перекрытия), не по предметам.
func _ray(from: Vector3, to: Vector3) -> Dictionary:
	var exclude: Array[RID] = []
	for attempt: int in range(6):
		var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from, to)
		q.exclude = exclude
		var hit: Dictionary = _space.intersect_ray(q)
		if hit.is_empty():
			return {}
		var collider: Node = hit.collider as Node
		if collider and _arch.is_ancestor_of(collider):
			return hit
		exclude.append(hit.rid)
	return {}


func _far_enough(at: Vector3, placed: Array[Vector3], spacing: float) -> bool:
	for q: Vector3 in placed:
		if q.distance_to(at) < spacing:
			return false
	return true


# ---------------------------------------------------------------- декали

func _decal(label: String, at: Vector3, basis: Basis, size: Vector3, albedo: String, orm: String = "", normal: String = "", modulate: Color = Color.WHITE) -> Decal:
	var d: Decal = Decal.new()
	d.name = label
	d.transform = Transform3D(basis, at)
	d.size = size
	d.texture_albedo = load(GRIME + albedo)
	if orm != "":
		d.texture_orm = load(GRIME + orm)
	if normal != "":
		d.texture_normal = load(GRIME + normal)
	d.modulate = modulate
	d.upper_fade = 0.15
	d.lower_fade = 0.15
	d.distance_fade_enabled = true
	d.distance_fade_begin = FADE_BEGIN
	d.distance_fade_length = 8.0
	_group.add_child(d)
	d.owner = _level
	_counts[label.get_slice("_", 0)] = int(_counts.get(label.get_slice("_", 0), 0)) + 1
	return d


## Декаль на стене: проецирует к стене (локальная -Y = внутрь стены), верх текстуры — вверх.
func _wall_basis(n: Vector3) -> Basis:
	var y: Vector3 = n
	var z: Vector3 = Vector3.DOWN
	return Basis(y.cross(z).normalized(), y, z)


## Пыль на полу вдоль стен: полоса, плотная у стены.
func _dust(walls: Array[Dictionary]) -> void:
	var placed: Array[Vector3] = []
	for w: Dictionary in walls:
		var at: Vector3 = w.at
		if not _far_enough(at, placed, DUST_SPACING):
			continue
		placed.append(at)
		var n: Vector3 = w.n
		var length: float = _rng.randf_range(2.2, 3.4)
		var across: float = _rng.randf_range(0.45, 0.8)
		var y: Vector3 = Vector3.UP
		var z: Vector3 = n
		var basis: Basis = Basis(y.cross(z).normalized(), y, z)
		var pos: Vector3 = at + n * (across * 0.5 - 0.02) + Vector3.UP * 0.02
		_decal("Dust_%03d" % placed.size(), pos, basis, Vector3(length, 0.5, across), "dust_strip.png", "", "", Color(1, 1, 1, _rng.randf_range(0.75, 1.0)))


## Подтёки от потолка (у высоких стен — от середины) вниз.
func _leaks(walls: Array[Dictionary]) -> void:
	var placed: Array[Vector3] = []
	for w: Dictionary in walls:
		if _rng.randf() > LEAK_SHARE:
			continue
		var at: Vector3 = w.at
		if not _far_enough(at, placed, LEAK_SPACING):
			continue
		var room_h: float = float(w.ceil) - float(w.floor)
		if room_h < 2.2:
			continue
		placed.append(at)
		var length: float = _rng.randf_range(1.2, minf(2.8, room_h - 0.4))
		var width: float = _rng.randf_range(0.7, 1.6)
		var top: float = float(w.ceil) - 0.02
		if room_h > 5.0 and _rng.randf() < 0.5:
			top = float(w.floor) + _rng.randf_range(2.8, room_h * 0.7)
		var pos: Vector3 = Vector3(at.x, top - length * 0.5, at.z)
		var k: int = _rng.randi_range(0, LEAKS - 1)
		# тёмный мокрый подтёк или белёсые высолы — как на старом кирпиче и краске
		var salt: bool = _rng.randf() < 0.45
		var albedo: String = ("salt_%d.png" if salt else "leak_%d.png") % k
		_decal("Leak_%03d" % placed.size(), pos, _wall_basis(w.n), Vector3(width, 0.5, length),
			albedo, "leak_%d_orm.png" % k, "leak_%d_normal.png" % k, Color(1, 1, 1, _rng.randf_range(0.45, 0.7) if salt else _rng.randf_range(0.75, 1.0)))


## Копоть над светильниками у стен: язык вверх от лампы.
func _soot() -> void:
	var i: int = 0
	for node: Node in _level.get_node("Lights").get_children():
		var light: Light3D = node as Light3D
		# солнце и дневной свет — не лампы (солнце стоит в начале координат, внутри стены: луч из
		# него давал нулевую нормаль и вырожденную декаль — ошибка basis.cpp каждый кадр)
		if not light or light.name == &"TvGlow" or String(light.name).begins_with("Emergency") or ShelterPower.daylight(light):
			continue
		var p: Vector3 = light.global_position
		for k: int in range(4):
			var dir: Vector3 = Vector3(sin(TAU * k / 4.0), 0.0, cos(TAU * k / 4.0))
			var hit: Dictionary = _ray(p, p + dir * 0.7)
			if hit.is_empty() or absf((hit.normal as Vector3).y) > 0.2:
				continue
			var n: Vector3 = Vector3((hit.normal as Vector3).x, 0.0, (hit.normal as Vector3).z).normalized()
			if n.length() < 0.5:
				continue
			var h: float = _rng.randf_range(0.9, 1.4)
			var at: Vector3 = (hit.position as Vector3) + Vector3.UP * (h * 0.5 - 0.05)
			i += 1
			_decal("Soot_%03d" % i, at, _wall_basis(n), Vector3(h * 0.55, 0.5, h), "soot.png", "", "", Color(1, 1, 1, 0.75))
			break


## Пятна на полу в проходах: засаленное, пролитое, затоптанное.
func _floor_spots() -> void:
	var region: NavigationRegion3D = _level.get_node("Navigation/Interior") as NavigationRegion3D
	var verts: PackedVector3Array = region.navigation_mesh.get_vertices()
	var placed: Array[Vector3] = []
	var tries: int = 0
	while placed.size() < FLOOR_SPOTS and tries < 600:
		tries += 1
		var p: Vector3 = region.global_transform * verts[_rng.randi_range(0, verts.size() - 1)]
		p += Vector3(_rng.randf_range(-0.6, 0.6), 0.0, _rng.randf_range(-0.6, 0.6))
		if not _far_enough(p, placed, 2.6):
			continue
		var below: Dictionary = _ray(p + Vector3.UP * 0.5, p + Vector3.DOWN * 0.6)
		if below.is_empty() or (below.normal as Vector3).y < 0.9:
			continue
		placed.append(p)
		var s: float = _rng.randf_range(0.8, 2.2)
		var basis: Basis = Basis(Vector3.UP, _rng.randf() * TAU)
		_decal("Spot_%03d" % placed.size(), (below.position as Vector3) + Vector3.UP * 0.02, basis, Vector3(s, 0.4, s * _rng.randf_range(0.6, 1.0)),
			"floor_grime_%d.png" % _rng.randi_range(0, 2), "", "", Color(1, 1, 1, _rng.randf_range(0.7, 1.0)))


## Надписи маркером и мелом на уровне глаз, по одной каждого вида.
func _notes(walls: Array[Dictionary]) -> void:
	var placed: Array[Vector3] = []
	var k: int = 0
	for w: Dictionary in walls:
		if k >= NOTE_COUNT:
			break
		var at: Vector3 = w.at
		if not _far_enough(at, placed, 6.0):
			continue
		# не поверх двери: над точкой на 2.2 м должна быть та же стена
		var n: Vector3 = w.n
		var probe: Dictionary = _ray(at + n * 0.4 + Vector3.UP * 1.5, at - n * 0.2 + Vector3.UP * 1.5)
		if probe.is_empty():
			continue
		placed.append(at)
		var width: float = _rng.randf_range(0.9, 1.3)
		var pos: Vector3 = at + Vector3.UP * _rng.randf_range(1.35, 1.7)
		_decal("Note_%02d" % k, pos, _wall_basis(n).rotated(n, _rng.randf_range(-0.05, 0.05)), Vector3(width, 0.3, width * 0.5), "note_%d.png" % k)
		k += 1
