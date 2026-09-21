class_name Perception
extends RefCounted
## Зрение AI: конус по дальности и углу + луч до цели сквозь мир (стены, стеллажи, витрины).
## Это единственное место, где AI получает позицию игрока — и только если реально его видит.

## Точка на теле, по которой проверяется видимость, по стойке (м над полом).
const TARGET_HEIGHT := {"stand": 1.3, "crouch": 0.8, "prone": 0.3}


static func stance_key(p: Player) -> String:
	match p.stance:
		Player.Stance.CROUCH:
			return "crouch"
		Player.Stance.PRONE:
			return "prone"
	return "stand"


## Видит ли наблюдатель с глазом eye, смотрящий вдоль forward, игрока target.
static func can_see(world: World3D, eye: Vector3, forward: Vector3, target: Player, exclude: Array[RID]) -> bool:
	var key := stance_key(target)
	var point := target.global_position + Vector3.UP * float(TARGET_HEIGHT[key])
	var to := point - eye
	var dist := to.length()
	var max_dist: float = Balance.AI_VIEW_DISTANCE * float(Balance.AI_VIEW_STANCE_SCALE[key])
	if dist > max_dist:
		return false
	var flat := Vector3(to.x, 0.0, to.z).normalized()
	var fwd := Vector3(forward.x, 0.0, forward.z).normalized()
	if dist > 2.0 and fwd.dot(flat) < cos(deg_to_rad(Balance.AI_VIEW_HALF_ANGLE_DEG)):
		return false
	var query := PhysicsRayQueryParameters3D.create(eye, point, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_PLAYER, exclude)
	var hit := world.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return true
	return hit.collider == target
