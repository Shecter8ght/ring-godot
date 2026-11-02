class_name WetBounce
extends Node3D
## Отражённый луч фонаря от мокрой земли: кладётся дочерним узлом фонаря (SpotLight3D). Луч
## упёрся в асфальт на улице, земля мокрая (RaidWeather: плёнка и лужи) — в точке попадания
## второй прожектор по отражённому направлению (зеркально от поверхности): блик уходит дальше
## и подсвечивает стены, машины, людей впереди. Чем площе луч к земле и чем мокрее — тем
## сильнее. Считается только у видимых фонарей недалеко от камеры (Balance.WET_BOUNCE).

var _spot: SpotLight3D
var _t: float = 0.0


func _ready() -> void:
	_spot = SpotLight3D.new()
	_spot.name = "Bounce"
	_spot.top_level = true
	_spot.visible = false
	_spot.shadow_enabled = true
	_spot.distance_fade_enabled = true
	_spot.distance_fade_begin = float(Balance.WET_BOUNCE.max_cam_m)
	_spot.distance_fade_length = 10.0
	_spot.light_specular = 0.6
	add_child(_spot)


func _physics_process(delta: float) -> void:
	_t -= delta
	if _t > 0.0:
		return
	_t = float(Balance.WET_BOUNCE.tick)
	_spot.visible = _update()


func _update() -> bool:
	var src := get_parent() as SpotLight3D
	var w := RaidWeather.current
	if src == null or w == null or not src.is_visible_in_tree():
		return false
	var cfg: Dictionary = Balance.WET_BOUNCE
	var wet := w.wet * float(cfg.film) + w.puddles * float(cfg.puddle)
	if wet < 0.02:
		return false
	var cam := get_viewport().get_camera_3d()
	var from := src.global_position
	if cam == null or cam.global_position.distance_to(from) > float(cfg.max_cam_m):
		return false
	var dir := -src.global_basis.z
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * src.spot_range, Hitscan.LAYER_WORLD)
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	if hit.is_empty():
		return false
	var n: Vector3 = hit.normal
	if n.y < 0.8 or Surfaces.kind_at(hit) != "asphalt":
		return false
	var at: Vector3 = hit.position
	if RaidAtmosphere.current and RaidAtmosphere.current.is_indoor(at):
		return false
	# под острым углом вода отражает сильнее (Френель), в упор — почти ничего
	var cos_i := absf(dir.dot(n))
	var fres := float(cfg.base) + (1.0 - float(cfg.base)) * pow(1.0 - cos_i, 3.0)
	var left := src.spot_range - from.distance_to(at)
	if left < 1.0:
		return false
	var out := dir.bounce(n).normalized()
	_spot.global_position = at + n * 0.06
	_spot.look_at(at + n * 0.06 + out, Vector3.UP if absf(out.y) < 0.99 else Vector3.FORWARD)
	_spot.light_color = src.light_color
	# The raycast is throttled; a strobe gates this node every rendered frame instead.
	var source_energy: float = src.light_energy
	if src.has_node("Pulse"):
		source_energy = float(src.get_meta("condition_energy", 0.0)) * float(src.get_meta("condition_k", 1.0))
	_spot.light_energy = source_energy * wet * fres * float(cfg.energy)
	_spot.spot_range = left
	# мокрый асфальт — не зеркало: пятно шире исходного
	_spot.spot_angle = minf(src.spot_angle * float(cfg.spread), 60.0)
	_spot.spot_attenuation = src.spot_attenuation
	return _spot.light_energy > 0.02
