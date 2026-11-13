extends RefCounted
## Преграды для ушей игрока. x — потеря уровня в дБ, y — насколько исчезает верх.

static func sample(space: PhysicsDirectSpaceState3D, ear: Vector3, source: Vector3) -> Vector2:
	var distance := ear.distance_to(source)
	if distance < 0.25:
		return Vector2.ZERO
	# Чуть выше пола, чтобы луч к шагу не принял поверхность под ногами за стену.
	var at := source + Vector3.UP * 0.12
	var middle := _trace(space, ear, at)
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	if distance > float(cfg.wide_probe_max_m):
		return middle
	# Две пробы рядом с прямой дают частичное перекрытие у косяка и на краю угла.
	var side := (at - ear).cross(Vector3.UP).normalized() * float(cfg.probe_width_m)
	if side.length_squared() < 0.001:
		return middle
	return (middle * 2.0 + _trace(space, ear + side, at + side) + _trace(space, ear - side, at - side)) * 0.25


static func _trace(space: PhysicsDirectSpaceState3D, ear: Vector3, at: Vector3) -> Vector2:
	var end := at.move_toward(ear, 0.08)
	var query := PhysicsRayQueryParameters3D.create(ear, end,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS)
	var hit := space.intersect_ray(query)
	if hit.is_empty():
		return Vector2.ZERO
	var collider := hit.collider as CollisionObject3D
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	if collider.collision_layer & Hitscan.LAYER_DOOR:
		return cfg.door
	if collider.collision_layer & Hitscan.LAYER_GLASS or Surfaces.kind_at(hit) == "glass":
		return cfg.glass
	return cfg.wall


## Есть один открытый проём, через который видны и источник, и слушатель.
static func through_door(space: PhysicsDirectSpaceState3D, ear: Vector3, source: Vector3, doors: Array[Node]) -> Vector3:
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	var direct := ear.distance_to(source)
	if direct > float(cfg.door_path_max_m):
		return Vector3.INF
	var candidates: Array[Vector4] = []
	for node: Node in doors:
		var door := node as Door
		if not is_instance_valid(door) or not door.is_open:
			continue
		if door.to_local(ear).z * door.to_local(source).z >= 0.0:
			continue
		var center := door.to_global(Vector3(door.width * 0.5, minf(1.35, door.height * 0.6), 0.0))
		if ear.distance_squared_to(center) < 0.09:
			continue
		var via := ear.distance_to(center) + source.distance_to(center)
		if via > direct + float(cfg.door_path_extra_m):
			continue
		candidates.append(Vector4(center.x, center.y, center.z, via))
	candidates.sort_custom(func(a: Vector4, b: Vector4) -> bool: return a.w < b.w)
	for i in range(mini(candidates.size(), int(cfg.door_path_probes))):
		var point := candidates[i]
		var at := Vector3(point.x, point.y, point.z)
		if _trace(space, ear, at) == Vector2.ZERO and _trace(space, at, source + Vector3.UP * 0.12) == Vector2.ZERO:
			return at
	return Vector3.INF
