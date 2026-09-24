class_name Hitscan
extends RefCounted
## Выстрел лучом: разброс, трассировка по физике, урон по Health, если он есть у цели.
## Общий для игрока и мародёров; кто стреляет — передаёт маску того, во что можно попасть.

const LAYER_WORLD := 1
const LAYER_PLAYER := 2
const LAYER_MARAUDER := 4
const LAYER_DOOR := 8
## Тела регдоллов и брошенные предметы: пули их толкают, AI сквозь них смотрит.
const LAYER_DEBRIS := 16

## Возвращает словарь intersect_ray (пустой — промах) и наносит урон, если у попавшего есть Health.
## attacker — кто стрелял (peer игрока; 0 — ИИ: убийство никому не засчитывается; -1 — сам этот peer).
static func fire(world: World3D, from: Vector3, dir: Vector3, spread_deg: float, range_m: float, mask: int, damage: float, exclude: Array[RID], rng: RandomNumberGenerator, attacker: int = -1) -> Dictionary:
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
			# куда попали: голова / корпус (игрок, мародёр знают свою высоту головы по стойке)
			var zone := String(body.call("hit_zone", hit.position)) if body.has_method("hit_zone") else ""
			h.apply_or_request_damage(damage, from, zone, attacker)
		if body is Target:
			(body as Target).on_hit(hit.position, d, damage)
		if body is RagdollPart:
			(body.get_parent() as Ragdoll).push(d * damage * Balance.BULLET_PUSH, hit.position)
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
