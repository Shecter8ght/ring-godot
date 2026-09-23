extends Node
## Тактика отряда без рук на кольце: окрик (второй узнаёт о цели, не видя её), укрытие под огнём
## (присел за стеной), перезарядка, поиск после потери цели. Печатает [ok]/[FAIL] и итог.
## godot --path . res://tools/ai_squad_test.tscn

var _fails: int = 0
var _said: Array[String] = []


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	var level := inst
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 1e9
	# игрок — на кольцевой улице, отряд — дальше по улице (видно), второй — за углом в проходе
	var ppos := SectorBuilder.polar(-100.0, 72.0)
	player.global_position = ppos + Vector3(0, 0.1, 0)
	var scene := preload("res://scenes/ai/marauder.tscn")
	var squad := Squad.new()
	var a := scene.instantiate() as Marauder
	a.name = "SquadA"
	a.weapon = "rifle"
	level.get_node("Marauders").add_child(a)
	a.global_position = SectorBuilder.polar(-118.0, 72.0) + Vector3(0, 0.1, 0)
	var b := scene.instantiate() as Marauder
	b.name = "SquadB"
	b.weapon = "pistol"
	level.get_node("Marauders").add_child(b)
	# в поперечном проходе за стеной: улицы не видно
	b.global_position = SectorBuilder.polar(-120.0, 90.0) + Vector3(0, 0.1, 0)
	squad.add(a)
	squad.add(b)
	for m in [a, b]:
		(m as Marauder).patrol_point_provider = func() -> Vector3: return (m as Marauder).global_position
		var mm: Marauder = m
		mm._facing = atan2(ppos.x - mm.global_position.x, ppos.z - mm.global_position.z)
	await _wait(1.5)
	_check("A видит игрока — бой", a.state == Marauder.State.COMBAT, _st(a))
	_check("B за стеной сам не видит, но знает по окрику — бой", b.state == Marauder.State.COMBAT and not b._seen_now and b.last_known.distance_to(ppos) < 3.0,
		"%s, видит %s, до цели по памяти %.1f м" % [_st(b), b._seen_now, b.last_known.distance_to(ppos)])
	# игрок стреляет в A: попадание → укрытие
	a.get_node("Health").call("take_damage", 20.0, ppos + Vector3.UP * 1.3)
	NoiseBus.emit(ppos, 60.0, "shot")
	var covered := false
	var crouched := false
	var cover_d := a._cover_pos.distance_to(a.global_position)
	for i in range(420):
		await get_tree().physics_frame
		if a.tactic in [Marauder.Tactic.COVER_MOVE, Marauder.Tactic.COVER_HIDE, Marauder.Tactic.COVER_PEEK]:
			covered = true
		if a.crouched:
			crouched = true
	_check("A под огнём ищет укрытие и приседает", covered and crouched, "тактика %s, присел %s, до укрытия было %.1f м, осталось %.1f" % [Marauder.Tactic.keys()[a.tactic], crouched, cover_d, a._cover_pos.distance_to(a.global_position)])
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/ai_squad.png"))
	# патроны кончились — перезарядка
	a._mag = 0
	a._reload_t = 0.0
	a._try_fire()
	_check("пустой магазин — перезарядка", a._reload_t > 0.0, "%.1f с" % a._reload_t)
	# игрок исчезает (далеко за зданием) — память кончается → поиск
	player.global_position = SectorBuilder.polar(-90.0, 180.0) + Vector3(0, 0.1, 0)
	for m in [a, b]:
		(m as Marauder).memory_timer = 0.5
	await _wait(2.0)
	_check("цель потеряна — поиск", a.state in [Marauder.State.SEARCH, Marauder.State.PATROL] and b.state in [Marauder.State.SEARCH, Marauder.State.PATROL],
		"%s / %s" % [_st(a), _st(b)])
	_check("здоровье мародёра удвоено", is_equal_approx((a.get_node("Health") as Health).max_hp, Balance.MARAUDER_HP) and Balance.MARAUDER_HP >= 120.0, "%.0f" % Balance.MARAUDER_HP)
	print("ai_squad_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _st(m: Marauder) -> String:
	return "%s/%s" % [Marauder.State.keys()[m.state], Marauder.Tactic.keys()[m.tactic]]


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
