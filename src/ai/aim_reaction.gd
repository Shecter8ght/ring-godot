extends RefCounted
## Пауза между подтверждённым зрением и огнём. Хранит только последнюю увиденную точку.
## Короткое исчезновение не даёт нового безопасного окна при каждом выглядывании.

var rng: RandomNumberGenerator = RandomNumberGenerator.new()
var remaining: float = 0.0
var last_delay: float = 0.0
var target_id: int = 0
var unseen_sec: float = 0.0
var last_visible: Vector3 = Vector3.INF


func reset() -> void:
	remaining = 0.0
	last_delay = 0.0
	target_id = 0
	unseen_sec = 0.0
	last_visible = Vector3.INF


## true — началось новое доведение прицела; в этот тик полная пауза ещё не расходуется.
func step(delta: float, visible: bool, contact_id: int, at: Vector3,
		observer: Vector3, profile: String, prepared: bool) -> bool:
	var tuning: Dictionary = Balance.AI_FIRE_REACTION
	if not visible:
		unseen_sec += delta
		remaining = maxf(0.0, remaining - delta)
		return false
	var fresh: bool = target_id != contact_id or unseen_sec >= float(tuning.reset_sec)
	if last_visible.is_finite() and not fresh:
		var old_bearing: Vector3 = last_visible - observer
		var new_bearing: Vector3 = at - observer
		if old_bearing.length_squared() > 0.01 and new_bearing.length_squared() > 0.01:
			fresh = old_bearing.angle_to(new_bearing) >= deg_to_rad(float(tuning.turn_deg))
	if fresh:
		var limits: Array = tuning.profiles.get(profile, tuning.profiles.scav)
		var distance_k: float = smoothstep(float(tuning.close_m), float(tuning.full_m), observer.distance_to(at))
		var low: float = lerpf(float(tuning.close_sec[0]), float(limits[0]), distance_k)
		var high: float = lerpf(float(tuning.close_sec[1]), float(limits[1]), distance_k)
		if prepared:
			low = float(tuning.prepared_sec[0])
			high = float(tuning.prepared_sec[1])
		last_delay = rng.randf_range(low, high)
		remaining = last_delay
	else:
		remaining = maxf(0.0, remaining - delta)
	target_id = contact_id
	unseen_sec = 0.0
	last_visible = at
	return fresh


func can_fire() -> bool:
	return remaining <= 0.0
