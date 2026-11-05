extends Node
## Запечь точки укрытия карты (src/ai/cover_points.gd, Balance.AI_POINTS.bake): по навигации карты (все этажи) с шагом
## step — места «низкое укрытие» и «угол» с направлением, откуда прикрывают; прореживание — не ближе min_gap,
## лучшие первыми. Пишет <nav_cache>/cover_points.json рядом с кэшем навигации (его печёт bake_*_nav).
##   tools/godot.cmd --headless res://tools/bake_cover_points.tscn [-- prospekt mall_map zone01_mall]
## После правки карты — перепечь навигацию, затем точки.

const CoverPoints = preload("res://src/ai/cover_points.gd")
const MAPS := {
	"prospekt": ["res://scenes/levels/prospekt.tscn", "res://data/sectors/prospekt.json"],
	"mall_map": ["res://scenes/levels/mall_map.tscn", "res://data/sectors/mall_map.json"],
	"zone01_mall": ["res://scenes/levels/zone01_mall.tscn", "res://data/sectors/zone01_mall.json"],
}


func _ready() -> void:
	# корень ещё собирает детей — карту добавляем со следующего кадра
	await get_tree().process_frame
	var ids: PackedStringArray = OS.get_cmdline_user_args()
	if ids.is_empty():
		ids = PackedStringArray(["prospekt"])
	for id: String in ids:
		if not MAPS.has(id):
			push_error("bake_cover_points: нет карты %s" % id)
			continue
		await _bake(id, String((MAPS[id] as Array)[0]), String((MAPS[id] as Array)[1]))
	get_tree().quit()


func _bake(id: String, scene: String, sector: String) -> void:
	var began: int = Time.get_ticks_msec()
	var level: Node3D = (load(scene) as PackedScene).instantiate() as Node3D
	level.set_script(null)
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var def: Dictionary = SectorBuilder.load_def(sector)
	var navigation := UrbanNavigation.new()
	navigation.definition = def
	var ready: Array = [false]
	navigation.ready_for_agents.connect(func() -> void: ready[0] = true)
	level.get_node("Navigation").add_child(navigation)
	while not ready[0]:
		await get_tree().process_frame
	for i: int in range(3):
		await get_tree().physics_frame
	var b: Dictionary = Balance.AI_POINTS.bake
	var space: PhysicsDirectSpaceState3D = level.get_world_3d().direct_space_state
	var map: RID = level.get_world_3d().navigation_map
	var samples: Array[Vector3] = _samples(navigation, float(b.step))
	var found: Array = []
	for p: Vector3 in samples:
		var c: Dictionary = CoverPoints.classify(space, p)
		if c.is_empty():
			continue
		# придвинуть к препятствию (навигация отстоит от стен на радиус бойца), не уходя с навигации
		var fwd: Vector3 = c.fwd
		var want: Vector3 = p + fwd * maxf(0.0, float(c.dist) - float(b.hug))
		var on_nav: Vector3 = NavigationServer3D.map_get_closest_point(map, want)
		var at: Vector3 = on_nav if Vector2(on_nav.x - want.x, on_nav.z - want.z).length() < 0.25 and absf(on_nav.y - p.y) < 0.4 else p
		found.append([float(c.score) + (1.0 if String(c.kind) == "low" else 0.0), at, fwd, String(c.kind)])
	found.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) > float(y[0]))
	# прореживание: лучшие первыми, не ближе min_gap к уже взятой (по клеткам)
	var gap: float = float(b.min_gap)
	var taken: Dictionary = {}
	var points: Array = []
	var counts: Dictionary = {"low": 0, "corner": 0}
	for f: Array in found:
		var p: Vector3 = f[1]
		var c := Vector3i(floori(p.x / gap), floori(p.y / 2.0), floori(p.z / gap))
		var close: bool = false
		for dx: int in range(-1, 2):
			for dz: int in range(-1, 2):
				for q: Vector3 in taken.get(c + Vector3i(dx, 0, dz), []):
					close = close or (q.distance_to(p) < gap)
		if close:
			continue
		if not taken.has(c):
			taken[c] = []
		(taken[c] as Array).append(p)
		var fwd: Vector3 = f[2]
		points.append([snappedf(p.x, 0.01), snappedf(p.y, 0.01), snappedf(p.z, 0.01), snappedf(rad_to_deg(atan2(fwd.x, fwd.z)), 0.1), f[3]])
		counts[f[3]] = int(counts[f[3]]) + 1
	var dir: String = String(def.get("nav_cache", ""))
	var path: String = dir.path_join(CoverPoints.FILE)
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify({"version": 1, "map": id, "step": float(b.step), "points": points}, "", false) + "\n")
	file.close()
	print("bake_cover_points: %s — выборок %d, мест %d, точек %d (низких %d, углов %d) за %d мс → %s" % [
		id, samples.size(), found.size(), points.size(), int(counts.low), int(counts.corner), Time.get_ticks_msec() - began, path])
	level.queue_free()
	await get_tree().process_frame


## Точки пола по навигации с шагом step: решётка внутри каждого треугольника многоугольников всех регионов (все этажи).
func _samples(navigation: Node, step: float) -> Array[Vector3]:
	var out: Array[Vector3] = []
	var seen: Dictionary = {}
	for child: Node in navigation.get_children():
		var region := child as NavigationRegion3D
		if region == null or region.navigation_mesh == null:
			continue
		var xf: Transform3D = region.global_transform
		var verts: PackedVector3Array = region.navigation_mesh.get_vertices()
		for pi: int in region.navigation_mesh.get_polygon_count():
			var poly: PackedInt32Array = region.navigation_mesh.get_polygon(pi)
			for t: int in range(1, poly.size() - 1):
				var a: Vector3 = xf * verts[poly[0]]
				var b2: Vector3 = xf * verts[poly[t]]
				var c: Vector3 = xf * verts[poly[t + 1]]
				var x0: float = floorf(minf(a.x, minf(b2.x, c.x)) / step) * step
				var z0: float = floorf(minf(a.z, minf(b2.z, c.z)) / step) * step
				var x1: float = maxf(a.x, maxf(b2.x, c.x))
				var z1: float = maxf(a.z, maxf(b2.z, c.z))
				var x: float = x0
				while x <= x1:
					var z: float = z0
					while z <= z1:
						var w: Vector3 = _bary(Vector2(x, z), Vector2(a.x, a.z), Vector2(b2.x, b2.z), Vector2(c.x, c.z))
						if w.x >= 0.0 and w.y >= 0.0 and w.z >= 0.0:
							var p := Vector3(x, a.y * w.x + b2.y * w.y + c.y * w.z, z)
							var key := Vector3i(roundi(x / step), roundi(p.y / 1.5), roundi(z / step))
							if not seen.has(key):
								seen[key] = true
								out.append(p)
						z += step
					x += step
	return out


## Барицентрические веса точки p в треугольнике abc (на плоскости XZ).
func _bary(p: Vector2, a: Vector2, b: Vector2, c: Vector2) -> Vector3:
	var v0: Vector2 = b - a
	var v1: Vector2 = c - a
	var v2: Vector2 = p - a
	var den: float = v0.x * v1.y - v1.x * v0.y
	if absf(den) < 0.000001:
		return Vector3(-1.0, -1.0, -1.0)
	var v: float = (v2.x * v1.y - v1.x * v2.y) / den
	var w: float = (v0.x * v2.y - v2.x * v0.y) / den
	return Vector3(1.0 - v - w, v, w)
