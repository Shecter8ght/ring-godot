extends Node
## Шаги: поверхность под ногами (внутри — плитка/бетон, снаружи — асфальт), темп от скорости
## (шаг, бег, присед), стена между ушами и шагами — глуше. Печатает [ok]/[FAIL] и итог.
## godot --path . res://tools/steps_test.tscn (можно --headless)

var _fails: int = 0
var _steps: Array = []


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	while inst.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in inst.get_node("Marauders").get_children():
		m.queue_free()
	await get_tree().physics_frame
	Audio.stepped.connect(func(kind: String, surf: String, pos: Vector3) -> void: _steps.append([kind, surf, pos]))
	# поверхности: внутри кольца и снаружи (двор, парковка) по нескольким направлениям
	var seen := {}
	var asphalt_at := Vector3.INF
	for a in [-100.0, -60.0, -20.0, 20.0, 60.0, 120.0, 180.0]:
		for r in [20.0, 72.0, 100.0, 118.0, 150.0, 190.0]:
			var p := SectorBuilder.polar(a, r)
			var s: String = Audio._surface_under(p)
			seen[s] = int(seen.get(s, 0)) + 1
			if s == "asphalt" and asphalt_at == Vector3.INF:
				asphalt_at = p
	_check("под ногами разные поверхности (плитка, бетон, асфальт)", seen.size() >= 3, str(seen))
	_check("асфальт — отдельный набор бетона и асфальта", asphalt_at != Vector3.INF and Audio.step_hook("asphalt") == "step_concrete", str(asphalt_at))
	# темп: болванка с Footsteps едет с заданной скоростью
	# рядом с игроком (уши на нём): дальние шаги не считаются вовсе
	var home := (get_tree().get_first_node_in_group("players") as Node3D).global_position
	var dummy := Node3D.new()
	inst.add_child(dummy)
	dummy.global_position = home
	var fs := Footsteps.new()
	dummy.add_child(fs)
	var counts := {}
	for pair in [["шаг", Balance.PLAYER_WALK_SPEED], ["бег", Balance.PLAYER_SPRINT_SPEED], ["присед", Balance.PLAYER_CROUCH_SPEED]]:
		_steps.clear()
		var t := 0.0
		while t < 3.0:
			await get_tree().process_frame
			var dt := get_process_delta_time()
			t += dt
			# туда-обратно у игрока
			dummy.global_position = home + Vector3(pingpong(t * float(pair[1]), 8.0) - 4.0, 0, 0)
		counts[pair[0]] = _steps.size()
		var run := _steps.filter(func(s: Array) -> bool: return String(s[0]).ends_with("_run")).size()
		print("   %s %.1f м/с: шагов за 3 с — %d, из них бегом %d" % [pair[0], float(pair[1]), _steps.size(), run])
		dummy.global_position = home
		await get_tree().process_frame
	_check("темп от скорости: бег чаще шага, присед реже", int(counts["бег"]) > int(counts["шаг"]) and int(counts["шаг"]) > int(counts["присед"]) and int(counts["шаг"]) >= 4,
		str(counts))
	# глушение: уши на улице, шаги — внутри модуля за стеной
	var cam := get_viewport().get_camera_3d()
	var ears := cam.global_position if cam else Vector3.ZERO
	var far_inside := SectorBuilder.polar(-60.0, 40.0)
	print("   уши %s" % ears)
	_check("стена между ушами и шагами — глуше", Audio._occluded(SectorBuilder.polar(-100.0, 180.0) + Vector3.UP * 1.6, far_inside), "")
	print("steps_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
