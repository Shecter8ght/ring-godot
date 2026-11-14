extends Node
## «Проспект»: подгонка моделей контейнеров лута (LootContainer.kind с моделью) по физике рейдовой карты. Для каждого места
## Loot_N с моделью: луч вниз — пол или поверхность под точкой (floor_drop), поворот так, чтобы спинка (там шарнир крышки)
## смотрела в ближайшую стену, а при открытой лишней высоте / глубине модель не пересекала мир (коробка по габариту
## закрытой и открытой модели). Не помещается ни в одном повороте — model_off: остаётся бокс.
## Выход — LOOT_FIT_OUT (data/blockouts/prospekt_loot_fit.json): {Loot_N: {yaw, drop, ok, why}}; в сцену его вносит
## python tools/prospekt_loot_kinds.py --fit.
##   LOOT_FIT_OUT=… tools/godot.cmd --headless res://tools/prospekt_loot_fit.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
const MARGIN := 0.03
const WALL_RAY := 1.6


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_loot_fit.json", true)
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	for i in range(30):
		await get_tree().physics_frame
	# тела-коллизии самих контейнеров подгонке не мешают (место ищется по миру, без самих ящиков)
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var own: CollisionObject3D = n.find_child(LootContainerVisual.BODY_NAME, true, false) as CollisionObject3D
		if own != null:
			own.collision_layer = 0
	var space: PhysicsDirectSpaceState3D = (level as Node3D).get_world_3d().direct_space_state
	var out: Dictionary = {}
	var total: int = 0
	var bad: int = 0
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c: LootContainer = n as LootContainer
		if c == null or c.kind == "":
			continue
		var model: String = c.model_id if c.model_id != "" else LootContainerVisual.kind_model(c.kind)
		if model == "":
			continue
		var spec: Dictionary = LootContainerVisual.model_spec(model)
		if spec.is_empty():
			continue
		total += 1
		var res: Dictionary = _fit_wall(space, c, spec) if bool(spec.get("wall", false)) else _fit(space, c, spec)
		if not bool(res.ok):
			bad += 1
		out[String(c.name)] = res
	var f := FileAccess.open(OS.get_environment("LOOT_FIT_OUT"), FileAccess.WRITE)
	f.store_string(JSON.stringify(out, "\t"))
	f.close()
	print("мест с моделью %d, не поместилось %d" % [total, bad])
	get_tree().quit(0)


## Объединённый габарит закрытой и открытой модели (в системе модели): центр и размер.
func _union(spec: Dictionary) -> AABB:
	var a: Dictionary = spec.aabb
	var b: Dictionary = spec.open_aabb
	var ca: Vector3 = Vector3(float(a.center[0]), float(a.center[1]), float(a.center[2]))
	var sa: Vector3 = Vector3(float(a.size[0]), float(a.size[1]), float(a.size[2]))
	var cb: Vector3 = Vector3(float(b.center[0]), float(b.center[1]), float(b.center[2]))
	var sb: Vector3 = Vector3(float(b.size[0]), float(b.size[1]), float(b.size[2]))
	var box: AABB = AABB(ca - sa * 0.5, sa)
	return box.merge(AABB(cb - sb * 0.5, sb))


func _floor(space: PhysicsDirectSpaceState3D, p: Vector3) -> float:
	var q := PhysicsRayQueryParameters3D.create(p + Vector3(0, 0.35, 0), p + Vector3(0, -1.5, 0), 1)
	var h: Dictionary = space.intersect_ray(q)
	if h.is_empty() or (h.normal as Vector3).y < 0.7:
		return INF
	return (h.position as Vector3).y


func _blocker(space: PhysicsDirectSpaceState3D, pos: Vector3, floor_y: float, yaw_deg: float, box: AABB) -> String:
	var basis := Basis(Vector3.UP, deg_to_rad(yaw_deg))
	var sh := BoxShape3D.new()
	sh.size = box.size - Vector3(0.04, MARGIN, 0.04)
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = sh
	q.collision_mask = 1
	q.transform = Transform3D(basis, Vector3(pos.x, floor_y, pos.z) + basis * (box.get_center() + Vector3(0, MARGIN * 0.5, 0)))
	var hits: Array[Dictionary] = space.intersect_shape(q, 1)
	if hits.is_empty():
		return ""
	var col: Object = hits[0].collider
	return "%s (%s)" % [(col as Node).name if col is Node else "?", (col as Node).get_parent().name if col is Node and (col as Node).get_parent() != null else "?"]


func _fits(space: PhysicsDirectSpaceState3D, pos: Vector3, floor_y: float, yaw_deg: float, box: AABB) -> bool:
	var basis := Basis(Vector3.UP, deg_to_rad(yaw_deg))
	var size: Vector3 = box.size - Vector3(0.04, MARGIN, 0.04)
	var center_local: Vector3 = box.get_center() + Vector3(0, MARGIN * 0.5, 0)
	var sh := BoxShape3D.new()
	sh.size = size
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = sh
	q.collision_mask = 1
	q.transform = Transform3D(basis, Vector3(pos.x, floor_y, pos.z) + basis * center_local)
	return space.intersect_shape(q, 1).is_empty()


## Настенная модель (аптечка, "wall" в каталоге): начало модели — на плоскости стены, лицо (+Z модели) — от стены, центр на
## высоте Balance.LOOT_WALL_HEIGHT от пола. Ближайшие стены ищутся лучами в восьми направлениях на этой высоте; берётся
## первая, у которой габарит закрытой и открытой модели (с дверцей) никуда не упирается.
func _fit_wall(space: PhysicsDirectSpaceState3D, c: LootContainer, spec: Dictionary) -> Dictionary:
	var pos: Vector3 = c.global_position
	var floor_y: float = _floor(space, pos)
	if floor_y == INF:
		return {"ok": false, "why": "нет пола", "yaw": 0.0, "drop": 0.0}
	var hang: float = floor_y + Balance.LOOT_WALL_HEIGHT
	var from: Vector3 = Vector3(pos.x, hang, pos.z)
	var hits: Array[Dictionary] = []
	for k in range(8):
		var a: float = float(k) * PI * 0.25
		var d := Vector3(cos(a), 0, sin(a))
		var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from + d * WALL_RAY, 1))
		if not hit.is_empty() and absf((hit.normal as Vector3).y) < 0.3:
			hits.append({"dist": from.distance_to(hit.position as Vector3), "pos": hit.position, "normal": hit.normal})
	hits.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return float(x.dist) < float(y.dist))
	if hits.is_empty():
		return {"ok": false, "why": "нет стены в %.1f м" % WALL_RAY, "yaw": 0.0, "drop": 0.0}
	var box: AABB = _union(spec)
	for h: Dictionary in hits:
		var n: Vector3 = (h.normal as Vector3)
		n.y = 0.0
		n = n.normalized()
		var yaw: float = rad_to_deg(atan2(n.x, n.z))
		var origin: Vector3 = Vector3((h.pos as Vector3).x, hang, (h.pos as Vector3).z)
		var basis := Basis(Vector3.UP, deg_to_rad(yaw))
		var sh := BoxShape3D.new()
		sh.size = box.size - Vector3(0.04, 0.04, 0.04)
		var q := PhysicsShapeQueryParameters3D.new()
		q.shape = sh
		q.collision_mask = 1
		q.transform = Transform3D(basis, origin + basis * box.get_center() + n * 0.01)
		if space.intersect_shape(q, 1).is_empty():
			return {"ok": true, "why": "на стене", "yaw": snappedf(wrapf(yaw, -180.0, 180.0), 0.1), "drop": snappedf(pos.y - hang, 0.01),
				"shift": [snappedf(origin.x - pos.x, 0.01), snappedf(origin.z - pos.z, 0.01)]}
	return {"ok": false, "why": "не помещается: стена занята", "yaw": 0.0, "drop": snappedf(pos.y - hang, 0.01)}


## Под местом ступени или пандус: по прямой через место высота пола растёт в одну сторону (с обеих сторон от места
## выше / ниже самого места больше чем на 0,08 м) — места на лестнице. Край прилавка или стена такой картины не дают.
func _on_steps(space: PhysicsDirectSpaceState3D, pos: Vector3, floor_y: float) -> bool:
	for k in range(4):
		var a: float = float(k) * PI * 0.25
		var d := Vector3(cos(a), 0, sin(a)) * 0.7
		var y1: float = _floor(space, pos + d)
		var y2: float = _floor(space, pos - d)
		if y1 == INF or y2 == INF:
			continue
		if (y1 - floor_y > 0.08 and floor_y - y2 > 0.08) or (y2 - floor_y > 0.08 and floor_y - y1 > 0.08):
			return true
	return false


func _fit(space: PhysicsDirectSpaceState3D, c: LootContainer, spec: Dictionary) -> Dictionary:
	var pos: Vector3 = c.global_position
	var floor_y: float = _floor(space, pos)
	if floor_y == INF:
		return {"ok": false, "why": "нет пола", "yaw": 0.0, "drop": 0.0}
	if bool(spec.get("support", false)):
		# модель «на опоре» (касса): под местом должна быть твёрдая поверхность на высоте Balance.LOOT_SUPPORT_RANGE над полом
		# и достаточно широкая под габарит; пола под ногами мало — касса на плитке не стоит
		var rng: Array = Balance.LOOT_SUPPORT_RANGE
		# опору отличаем от плиты пола (под полом тоже что-то есть): вокруг места, дальше габарита, поверхность должна обрываться вниз
		# на 0,3–1,2 м хотя бы в половине направлений (край прилавка, стола), а не тянуться ровно, как пол
		var ring_r: float = maxf(_union(spec).size.x, _union(spec).size.z) * 0.5 + 0.35
		var lower: Array[float] = []
		var level: int = 0
		for k in range(8):
			var a: float = float(k) * PI * 0.25
			var p0: Vector3 = Vector3(pos.x + cos(a) * ring_r, floor_y + 0.1, pos.z + sin(a) * ring_r)
			var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(p0, p0 + Vector3(0, -2.5, 0), 1))
			var y: float = -INF if hit.is_empty() else (hit.position as Vector3).y
			if y > floor_y - 0.05:
				level += 1
			elif floor_y - y >= float(rng[0]) and floor_y - y <= float(rng[1]):
				lower.append(floor_y - y)
		if lower.size() < 4:
			return {"ok": false, "why": "нет опоры: это пол или широкая поверхность (обрыв вниз %.1f–%.1f м в %d из 8 направлений, ровно в %d)" % [float(rng[0]), float(rng[1]), lower.size(), level], "yaw": 0.0, "drop": 0.0}
		var half: Vector3 = _union(spec).size * 0.5
		for sx in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				var p: Vector3 = Vector3(pos.x + sx * half.x * 0.9, floor_y + 0.1, pos.z + sz * half.z * 0.9)
				var h: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(p, p + Vector3(0, -0.3, 0), 1))
				if h.is_empty():
					return {"ok": false, "why": "нет опоры: поверхность уже кассы", "yaw": 0.0, "drop": 0.0}
	var drop: float = pos.y - floor_y
	var box: AABB = _union(spec)
	# днище мешка и ящика чуть ниже опоры (прогиб, ножки): проверяем только то, что выше 5 см от пола
	var top: float = box.end.y
	box.position.y = maxf(box.position.y, 0.05)
	box.size.y = top - box.position.y
	# спинка — к ближайшей стене: в четыре стороны на высоте 0,5 м от пола
	var best_dir: Vector2 = Vector2.ZERO
	var best_d: float = WALL_RAY
	for k in range(4):
		var a: float = float(k) * PI * 0.5
		var d := Vector3(cos(a), 0, sin(a))
		var from: Vector3 = Vector3(pos.x, floor_y + 0.5, pos.z)
		var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from + d * WALL_RAY, 1))
		if not hit.is_empty():
			var dist: float = from.distance_to(hit.position as Vector3)
			if dist < best_d:
				best_d = dist
				best_dir = Vector2(d.x, d.z)
	var candidates: Array[float] = []
	var seed_yaw: float = float(absi(String(c.name).hash()) % 8) * 45.0
	if best_dir != Vector2.ZERO:
		# local −Z после поворота на θ вокруг Y: (−sinθ, −cosθ); нужно (dx, dz)
		var wall_yaw: float = rad_to_deg(atan2(-best_dir.x, -best_dir.y))
		candidates.append(wall_yaw)
		for off in [90.0, -90.0, 180.0, 45.0, -45.0, 135.0, -135.0]:
			candidates.append(wall_yaw + off)
	else:
		for k in range(8):
			candidates.append(seed_yaw + 45.0 * float(k))
	for yaw: float in candidates:
		if _fits(space, pos, floor_y, yaw, box):
			var res: Dictionary = {"ok": true, "why": "у стены" if best_dir != Vector2.ZERO else "на свободном месте", "yaw": snappedf(wrapf(yaw, -180.0, 180.0), 0.1), "drop": snappedf(drop, 0.01)}
			if _on_steps(space, pos, floor_y):
				res["solid"] = false   # на ступенях тело-коллизия перегородила бы лестницу
				res["why"] += " (на ступенях: без коллизии)"
			return res
	return {"ok": false, "why": "не помещается: стена, стеллаж или проход", "yaw": 0.0, "drop": snappedf(drop, 0.01),
		"hit": _blocker(space, pos, floor_y, candidates[0], box), "box": str(box.size)}
