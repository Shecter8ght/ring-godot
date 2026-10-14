class_name Perception
extends RefCounted
## Зрение AI: конус по дальности и углу + луч до цели сквозь мир (стены, стеллажи, витрины).
## Это единственное место, где AI получает позицию игрока — и только если реально его видит.

## Точка на теле, по которой проверяется видимость, по стойке (м над полом).
const TARGET_HEIGHT := {"stand": 1.3, "crouch": 0.8, "prone": 0.3}

## Общие свойства видимой цели — один снимок физического шага для всех наблюдателей.
## Лучи до цели не кэшируются: у каждого свои стены, двери и точка зрения.
static var _range_frame: int = -1
static var _ranges: Dictionary = {}
static var _light_strengths: Dictionary = {}
static var work_profile_enabled: bool = false
static var work_profile: Dictionary = {}


static func stance_key(p: Player) -> String:
	match p.stance:
		Player.Stance.CROUCH:
			return "crouch"
		Player.Stance.PRONE:
			return "prone"
	return "stand"


## Видит ли ИИ другого ИИ (враждебная фракция): тот же конус и луч, точка — грудь (лежащий — ниже);
## освещённость места — как для игрока.
static func can_see_body(world: World3D, eye: Vector3, forward: Vector3, body: Node3D, exclude: Array[RID], view: float = 1.0, downed: bool = false) -> bool:
	var point := body.global_position + Vector3.UP * (0.35 if downed else 1.3)
	var to := point - eye
	var dist := to.length()
	# Тот, кто вне поля зрения, не требует расчёта освещения и луча физики.
	var flat := Vector3(to.x, 0.0, to.z).normalized()
	var fwd := Vector3(forward.x, 0.0, forward.z).normalized()
	if dist > 2.0 and fwd.dot(flat) < cos(deg_to_rad(Balance.AI_VIEW_HALF_ANGLE_DEG)):
		return false
	var base: float = _view_range(body, false)
	if dist > base * view:
		return false
	var query := PhysicsRayQueryParameters3D.create(eye, point, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER, exclude)
	if work_profile_enabled:
		work_profile["rays"] = int(work_profile.get("rays", 0)) + 1
	var hit := world.direct_space_state.intersect_ray(query)
	return not hit.is_empty() and hit.collider == body


## Видит ли наблюдатель с глазом eye, смотрящий вдоль forward, игрока target.
## view — множитель дальности (тип мародёра: у снайпера дальше).
static func can_see(world: World3D, eye: Vector3, forward: Vector3, target: Player, exclude: Array[RID], view: float = 1.0) -> bool:
	var key := stance_key(target)
	var point := target.global_position + Vector3.UP * float(TARGET_HEIGHT[key]) + target.lean_vector()
	var to := point - eye
	var dist := to.length()
	var flat := Vector3(to.x, 0.0, to.z).normalized()
	var fwd := Vector3(forward.x, 0.0, forward.z).normalized()
	if dist > 2.0 and fwd.dot(flat) < cos(deg_to_rad(Balance.AI_VIEW_HALF_ANGLE_DEG)):
		return false
	var light: bool = target.has_light_on()
	var base: float = _view_range(target, light, _light_view(target) if light else 1.0, target.laser_on)
	var max_dist: float = base * view * float(Balance.AI_VIEW_STANCE_SCALE[key])
	if dist > max_dist:
		return false
	var query := PhysicsRayQueryParameters3D.create(eye, point, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_PLAYER, exclude)
	if work_profile_enabled:
		work_profile["rays"] = int(work_profile.get("rays", 0)) + 1
	var hit := world.direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return true
	return hit.collider == target


static func _begin_frame() -> void:
	var frame: int = Engine.get_physics_frames()
	if frame != _range_frame:
		_range_frame = frame
		_ranges.clear()
		_light_strengths.clear()


## Состав включённого фонаря может измениться в этом же шаге — сравниваем обвесы.
static func _light_view(target: Player) -> float:
	if not Engine.is_in_physics_frame():
		return target.light_view()
	_begin_frame()
	var id: int = target.get_instance_id()
	var mods: int = target.weapon_mods.hash()
	var saved: Dictionary = _light_strengths.get(id, {})
	if not saved.is_empty() and int(saved.mods) == mods:
		return float(saved.value)
	var strength: float = target.light_view()
	_light_strengths[id] = {"mods": mods, "value": strength}
	return strength


static func _view_range(body: Node3D, light: bool, strength: float = 1.0, laser: bool = false) -> float:
	if work_profile_enabled:
		work_profile["range_requests"] = int(work_profile.get("range_requests", 0)) + 1
	var atmosphere: RaidAtmosphere = RaidAtmosphere.current
	if atmosphere == null:
		return Balance.AI_VIEW_DISTANCE
	# Вызовы из инструментов вне физического шага всегда получают свежее состояние мира.
	if not Engine.is_in_physics_frame():
		return atmosphere.view_distance(body.global_position, light, strength, laser)
	_begin_frame()
	var id: int = body.get_instance_id()
	var position: Vector3 = body.global_position
	var conditions: int = RaidConditions.current.hash()
	var daylight: float = DayCycle.current.view if DayCycle.current else -1.0
	var saved: Dictionary = _ranges.get(id, {})
	if not saved.is_empty() and saved.position == position and saved.atmosphere == atmosphere.get_instance_id() \
			and int(saved.conditions) == conditions and float(saved.daylight) == daylight \
			and bool(saved.light) == light and float(saved.strength) == strength and bool(saved.laser) == laser:
		return float(saved.value)
	var value: float = atmosphere.view_distance(position, light, strength, laser)
	_ranges[id] = {"position": position, "atmosphere": atmosphere.get_instance_id(), "conditions": conditions,
		"daylight": daylight, "light": light, "strength": strength, "laser": laser, "value": value}
	if work_profile_enabled:
		work_profile["range_calculations"] = int(work_profile.get("range_calculations", 0)) + 1
	return value
