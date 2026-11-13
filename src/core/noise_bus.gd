extends Node
## Шина шума — единственный способ для AI «услышать» игрока. Autoload `NoiseBus`.
## Кто шумит — зовёт emit; слушатель проверяет расстояние и преграды.
## Сеть: мародёры живут и слушают только на хосте (см. marauder.gd), поэтому шум с клиента
## пересылается туда RPC'ом, а не летит локальным сигналом — там его слушать некому.

## pos — где, radius_m — до какого расстояния слышно, kind — "step" / "shot" / "door" / "death".
signal noise(pos: Vector3, radius_m: float, kind: String)
## Окрик мародёра: from — где кричал, radius_m — докуда слышно, target — где он видел цель.
## Так (и только так) товарищи узнают о цели, которую сами не видят. Только на хосте.
signal callout(from: Vector3, radius_m: float, target: Vector3, speaker: Node)

var _active_noise: Vector3 = Vector3.INF
var _occlusion_by_ear: Dictionary = {}


## Прямая до источника звука. Сквозь стену/закрытую дверь слышно ближе, чем через проём.
func audible(world: World3D, ear: Vector3, pos: Vector3, radius_m: float, kind: String) -> bool:
	var source := pos + Vector3.UP * (1.4 if kind == "voice" else 0.45)
	var distance := ear.distance_to(source)
	if distance > radius_m:
		return false
	var loud := kind in ["shot", "shot_ai", "alarm", "drop"]
	var blocked_k := float(Balance.AI_HEARING_BLOCKED.loud if loud else Balance.AI_HEARING_BLOCKED.quiet)
	if distance <= radius_m * blocked_k:
		return true
	var use_cache := pos == _active_noise and kind != "voice"
	if use_cache and _occlusion_by_ear.has(ear):
		return not bool(_occlusion_by_ear[ear])
	# Дверь сама шумит при открытии. Остановить луч чуть перед источником, чтобы створка
	# у источника не заглушала собственный звук с обеих сторон.
	var end := source.move_toward(ear, 0.25 if kind == "door" else 0.04)
	var query := PhysicsRayQueryParameters3D.create(ear, end, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	var blocked := not world.direct_space_state.intersect_ray(query).is_empty()
	if use_cache:
		_occlusion_by_ear[ear] = blocked
	return not blocked


func shout(from: Vector3, radius_m: float, target: Vector3, speaker: Node) -> void:
	callout.emit(from, radius_m, target, speaker)


func emit(pos: Vector3, radius_m: float, kind: String) -> void:
	# в дождь слышно хуже — шум доносится ближе
	radius_m *= float(RaidConditions.spec("weather").get("hear", 1.0))
	if Net.is_networked() and not multiplayer.is_server():
		_report.rpc_id(1, pos, radius_m, kind)
	else:
		_dispatch(pos, radius_m, kind)


@rpc("any_peer", "call_remote", "reliable")
func _report(pos: Vector3, radius_m: float, kind: String) -> void:
	if multiplayer.is_server():
		_dispatch(pos, radius_m, kind)


func _dispatch(pos: Vector3, radius_m: float, kind: String) -> void:
	# При выборе ближайшего отряда бойцы несколько раз спрашивают про те же уши и источник.
	var previous_noise := _active_noise
	var previous_ears := _occlusion_by_ear
	_active_noise = pos
	_occlusion_by_ear = {}
	noise.emit(pos, radius_m, kind)
	_active_noise = previous_noise
	_occlusion_by_ear = previous_ears
