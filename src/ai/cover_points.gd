extends RefCounted
## Точки укрытия карты с направлением (приём Road to Vostok, docs/research/road_to_vostok.md): заранее найденные места,
## где присевшего закрывает препятствие с одной стороны — «низкое укрытие» (по пояс: машина, парапет, ящики — стоя
## можно стрелять поверх) и «угол» (высокая стена, шаг вбок — выглянуть). Направление точки — откуда она прикрывает.
## Запекает tools/bake_cover_points.tscn по физике и навигации карты в <nav_cache>/cover_points.json; SectorLevel
## подгружает, когда навигация готова; мародёр (Marauder._cover_point) смотрит их раньше случайного поиска лучами.
## Числа — Balance.AI_POINTS. Подключается preload (без class_name).

const FILE := "cover_points.json"
## Точки по мирам: id мира → {"cell": размер клетки, "grid": {клетка: [индексы]}, "points": [{pos, fwd, kind}]}.
static var _maps: Dictionary = {}
## Кто занял точку: id мира → {индекс точки: id мародёра}.
static var _claims: Dictionary = {}


## Подгрузить точки карты из папки кэша навигации; нет файла — точек нет. Сколько точек.
static func load_for(world: World3D, nav_cache: String) -> int:
	var key: int = world.get_rid().get_id()
	_maps.erase(key)
	_claims.erase(key)
	var path: String = nav_cache.path_join(FILE)
	if nav_cache == "" or not FileAccess.file_exists(path):
		return 0
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return 0
	var cell: float = float(Balance.AI_POINTS.grid_m)
	var grid: Dictionary = {}
	var points: Array = []
	for raw: Variant in (parsed as Dictionary).get("points", []):
		var p: Array = raw
		var yaw: float = deg_to_rad(float(p[3]))
		var pos := Vector3(float(p[0]), float(p[1]), float(p[2]))
		var c := Vector2i(floori(pos.x / cell), floori(pos.z / cell))
		if not grid.has(c):
			grid[c] = []
		(grid[c] as Array).append(points.size())
		points.append({"pos": pos, "fwd": Vector3(sin(yaw), 0.0, cos(yaw)), "kind": String(p[4])})
	_maps[key] = {"cell": cell, "grid": grid, "points": points}
	_claims[key] = {}
	return points.size()


## Точки в радиусе (по горизонтали, ±3 м по высоте): [{"i", "pos", "fwd", "kind"}].
static func near(world: World3D, pos: Vector3, radius: float) -> Array:
	var data: Dictionary = _maps.get(world.get_rid().get_id(), {})
	if data.is_empty():
		return []
	var cell: float = float(data.cell)
	var grid: Dictionary = data.grid
	var points: Array = data.points
	var out: Array = []
	var c0 := Vector2i(floori((pos.x - radius) / cell), floori((pos.z - radius) / cell))
	var c1 := Vector2i(floori((pos.x + radius) / cell), floori((pos.z + radius) / cell))
	for cx: int in range(c0.x, c1.x + 1):
		for cz: int in range(c0.y, c1.y + 1):
			for i: int in grid.get(Vector2i(cx, cz), []):
				var pt: Dictionary = points[i]
				var p: Vector3 = pt.pos
				if absf(p.y - pos.y) > 3.0 or Vector2(p.x - pos.x, p.z - pos.z).length() > radius:
					continue
				out.append({"i": i, "pos": p, "fwd": pt.fwd, "kind": pt.kind})
	return out


## Занята ли точка другим (он ещё жив и его укрытие — на ней).
static func taken_by_other(world: World3D, index: int, who: Node3D, cover_of: Callable) -> bool:
	var claims: Dictionary = _claims.get(world.get_rid().get_id(), {})
	var id: int = int(claims.get(index, 0))
	if id == 0 or id == who.get_instance_id():
		return false
	var other: Object = instance_from_id(id)
	if other == null or not is_instance_valid(other):
		claims.erase(index)
		return false
	var data: Dictionary = _maps.get(world.get_rid().get_id(), {})
	var p: Vector3 = (data.points as Array)[index].pos
	if (cover_of.call(other) as Vector3).distance_to(p) > float(Balance.AI_POINTS.claim_m):
		claims.erase(index)
		return false
	return true


## Занять точку (прежнюю свою — отпустить).
static func claim(world: World3D, index: int, who: Node3D) -> void:
	var claims: Dictionary = _claims.get(world.get_rid().get_id(), {})
	for k: Variant in claims.keys():
		if int(claims[k]) == who.get_instance_id():
			claims.erase(k)
	if index >= 0:
		claims[index] = who.get_instance_id()


# ---------------------------------------------------------------- разметка (для запекания и проверки)

## Что за место в точке p пола (на навигации): {"kind": "low"|"corner", "fwd": направление, "score", "dist" — до
## препятствия, м} или пусто.
## Низкое — впереди близко препятствие по пояс и на высоте глаз присевшего, на высоте глаз стоящего свободно (стоя
## стрелять поверх). Угол — впереди
## высокая стена близко, а на шаг вбок свободно и вперёд, и сам шаг. Из восьми направлений — лучшее.
static func classify(space: PhysicsDirectSpaceState3D, p: Vector3) -> Dictionary:
	var b: Dictionary = Balance.AI_POINTS.bake
	var best: Dictionary = {}
	for k: int in range(8):
		var a: float = TAU * float(k) / 8.0
		var d := Vector3(sin(a), 0.0, cos(a))
		var low: float = _hit(space, p + Vector3.UP * float(b.low_h), d, float(b.reach))
		if low < 0.0:
			continue
		var chest: float = _hit(space, p + Vector3.UP * float(b.over_h), d, float(b.over_reach))
		# низкое: закрывает и на высоте глаз присевшего, а поверх — свободно
		if chest < 0.0 and _hit(space, p + Vector3.UP * float(b.crouch_h), d, float(b.reach)) >= 0.0:
			var score: float = 2.0 - low
			if best.is_empty() or score > float(best.score):
				best = {"kind": "low", "fwd": d, "score": score, "dist": low}
			continue
		if chest < 0.0 or chest > float(b.reach) or (not best.is_empty() and String(best.kind) == "low"):
			continue
		# угол: шаг вбок свободен, и оттуда вперёд видно
		var side := Vector3(d.z, 0.0, -d.x)
		for s: float in [1.0, -1.0]:
			var step: Vector3 = side * s * float(b.corner_side)
			if _hit(space, p + Vector3.UP * float(b.over_h), step.normalized(), step.length()) >= 0.0:
				continue
			if _hit(space, p + step + Vector3.UP * float(b.over_h), d, float(b.corner_reach)) >= 0.0:
				continue
			var cscore: float = 1.0 - chest
			if best.is_empty() or cscore > float(best.score):
				best = {"kind": "corner", "fwd": d, "score": cscore, "dist": chest}
	return best


## Расстояние до препятствия по лучу (только мир) или −1.
static func _hit(space: PhysicsDirectSpaceState3D, from: Vector3, dir: Vector3, length: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * length, Hitscan.LAYER_WORLD)
	var hit: Dictionary = space.intersect_ray(q)
	return from.distance_to(hit.position as Vector3) if not hit.is_empty() else -1.0
