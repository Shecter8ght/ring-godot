extends Node3D
## Стресс без окна: растёт от пуль рядом (не чаще раза в near_gap), попадания, взрыва; спадает в
## тишине, сидя — быстрее; мало здоровья — не ниже low_hp; адреналин — бег быстрее, дыхание дольше;
## последствия только выше effects_from. godot --headless --path . res://tools/stress_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var geo := StaticBody3D.new()
	add_child(geo)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = Vector3(60, 1, 60)
	cs.shape = sh
	cs.position = Vector3(0, -0.5, 0)
	geo.add_child(cs)
	var pl := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(pl)
	pl.global_position = Vector3(0, 0.05, 0)
	await _frames(5)
	var sc: Dictionary = Balance.STRESS
	# пули рядом: очередь из 10 за один кадр — засчитана одна
	for i in range(10):
		pl.near_miss()
	_check("очередь рядом — не больше одной пули за near_gap", absf(pl.stress - float(sc.near_miss)) < 0.01, "%.1f" % pl.stress)
	# мародёр стреляет мимо — рядом с грудью
	var m := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	add_child(m)
	m.global_position = Vector3(20, 0.1, 0)
	# без «мозга»: иначе сам увидит и начнёт стрелять — нужна только проверка промаха
	m.set_physics_process(false)
	m.set_process(false)
	await get_tree().create_timer(0.3).timeout
	pl.stress = 0.0
	pl._near_t = 0.0
	var s0 := pl.stress
	m._near_miss(Vector3(20, 1.4, 0), {"end": Vector3(-20, 1.4, 1.0)})
	_check("пуля мародёра прошла в метре — страшно", pl.stress > s0, "%.1f → %.1f" % [s0, pl.stress])
	m.queue_free()
	pl.stress = 20.0
	_check("мало стресса — последствий нет", pl.stress_k() == 0.0, "%.2f" % pl.stress_k())
	pl.add_stress(100.0)
	_check("на пределе — последствия в полную силу", pl.stress_k() > 0.99, "%.2f" % pl.stress_k())
	# адреналин: бег быстрее
	Input.action_press("sprint")
	var sprint_hi := pl._stance_speed()
	pl.stress = 0.0
	var sprint_lo := pl._stance_speed()
	Input.action_release("sprint")
	_check("адреналин: бег быстрее", sprint_hi > sprint_lo * 1.05, "%.2f против %.2f" % [sprint_hi, sprint_lo])
	# спадает в тишине, сидя — быстрее
	pl.stress = 80.0
	pl._stress_quiet = 0.0
	await get_tree().create_timer(float(sc.calm_delay) + 1.0).timeout
	var stand_drop := 80.0 - pl.stress
	pl.stress = 80.0
	pl._stress_quiet = float(sc.calm_delay) + 0.01
	pl.stance = Player.Stance.CROUCH
	pl._apply_stance()
	await get_tree().create_timer(1.0).timeout
	var crouch_drop := 80.0 - pl.stress
	_check("в тишине спадает, сидя — быстрее", stand_drop > 1.0 and crouch_drop > stand_drop * 1.5, "стоя %.1f, сидя %.1f за секунду" % [stand_drop, crouch_drop])
	# мало здоровья — не ниже low_hp
	pl.stress = 0.0
	pl.health.hp = pl.health.max_hp * 0.2
	await _frames(3)
	_check("мало здоровья — стресс не ниже порога", pl.stress >= float(sc.low_hp) - 0.01, "%.1f" % pl.stress)
	pl.health.hp = pl.health.max_hp
	# обезболивающее
	pl.stress = 70.0
	pl.add_stress(-float(sc.painkillers))
	_check("обезболивающее успокаивает", absf(pl.stress - (70.0 - float(sc.painkillers))) < 0.5, "%.1f" % pl.stress)
	print("stress_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
