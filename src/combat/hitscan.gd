class_name Hitscan
extends RefCounted
## Выстрел лучом: разброс, трассировка по физике, урон по Health, если он есть у цели.
## Общий для игрока и мародёров; кто стреляет — передаёт маску того, во что можно попасть.

const LAYER_WORLD := 1
const LAYER_PLAYER := 2
const LAYER_MARAUDER := 4
const LAYER_DOOR := 8

## Возвращает словарь intersect_ray (пустой — промах) и наносит урон, если у попавшего есть Health.
static func fire(world: World3D, from: Vector3, dir: Vector3, spread_deg: float, range_m: float, mask: int, damage: float, exclude: Array[RID], rng: RandomNumberGenerator) -> Dictionary:
	var d := _spread(dir, spread_deg, rng)
	var query := PhysicsRayQueryParameters3D.create(from, from + d * range_m, mask, exclude)
	query.collide_with_areas = false
	var hit := world.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		hit["end"] = from + d * range_m
		return hit
	var body: Object = hit.collider
	if body is Node:
		var h := (body as Node).get_node_or_null("Health") as Health
		if h:
			h.apply_or_request_damage(damage, from)
		if body is Target:
			(body as Target).on_hit(hit.position, d, damage)
	ImpactFx.spawn_hit(hit, d)
	return hit


## Случайное отклонение направления в конусе полуугла spread_deg.
static func _spread(dir: Vector3, spread_deg: float, rng: RandomNumberGenerator) -> Vector3:
	if spread_deg <= 0.0:
		return dir.normalized()
	var axis := dir.cross(Vector3.UP).normalized()
	if axis.length_squared() < 1e-6:
		axis = Vector3.RIGHT
	var tilt := deg_to_rad(rng.randf_range(0.0, spread_deg))
	var roll := rng.randf_range(0.0, TAU)
	return dir.normalized().rotated(axis, tilt).rotated(dir.normalized(), roll)
