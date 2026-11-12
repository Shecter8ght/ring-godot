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
		var res: Dictionary = _fit(space, c, spec)
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


func _fit(space: PhysicsDirectSpaceState3D, c: LootContainer, spec: Dictionary) -> Dictionary:
	var pos: Vector3 = c.global_position
	var floor_y: float = _floor(space, pos)
	if floor_y == INF:
		return {"ok": false, "why": "нет пола", "yaw": 0.0, "drop": 0.0}
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
			return {"ok": true, "why": "у стены" if best_dir != Vector2.ZERO else "на свободном месте", "yaw": snappedf(wrapf(yaw, -180.0, 180.0), 0.1), "drop": snappedf(drop, 0.01)}
	return {"ok": false, "why": "не помещается: стена, стеллаж или проход", "yaw": 0.0, "drop": snappedf(drop, 0.01),
		"hit": _blocker(space, pos, floor_y, candidates[0], box), "box": str(box.size)}
