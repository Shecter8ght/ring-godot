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
## Витринное стекло: пуля пробивает (и бьёт его), ИИ сквозь него видит, ходить сквозь нельзя.
const LAYER_GLASS := 32

## Возвращает словарь intersect_ray (пустой — промах) и наносит урон, если у попавшего есть Health.
## attacker — кто стрелял (peer игрока; 0 — ИИ: убийство никому не засчитывается; -1 — сам этот peer).
static func fire(world: World3D, from: Vector3, dir: Vector3, spread_deg: float, range_m: float, mask: int, damage: float, exclude: Array[RID], rng: RandomNumberGenerator, attacker: int = -1) -> Dictionary:
	var d := _spread(dir, spread_deg, rng)
	var to := from + d * range_m
	var start := from
	var hit: Dictionary = {}
	# стекло пробивается: бьём панель и летим дальше (немного теряя урон)
	for i in range(6):
		var query := PhysicsRayQueryParameters3D.create(start, to, mask | LAYER_GLASS, exclude)
		query.collide_with_areas = false
		hit = world.direct_space_state.intersect_ray(query)
		if hit.is_empty():
			hit["end"] = to
			return hit
		var pane := GlassPanes.pane_of(hit)
		if pane.is_empty():
			break
		(pane[0] as GlassPanes).bullet(int(pane[1]), damage, hit.position)
		ImpactFx.spawn_hit(hit, d)
		damage *= float(Balance.GLASS.pass_k)
		start = (hit.position as Vector3) + d * 0.05
	if not hit.has("collider"):
		hit["end"] = to
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
