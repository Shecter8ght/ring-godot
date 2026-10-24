extends Node
## Засада мародёра (Balance.AI_AMBUSH) без рук на кольце: цель ушла за угол — бот садится в укрытие
## стволом на последнюю точку и ждёт; цель вышла там же — огонь с уже севшим прицелом; склонность 0 —
## идёт вперёд, как раньше; в отряде ждёт один; никто не вышел — встал и пошёл сам.
## Печатает [ok]/[FAIL] и итог. godot --headless --path . res://tools/ambush_test.tscn

var _fails: int = 0
var _level: Node
var _player: Player
var _street: Vector3
var _hidden: Vector3


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_player.health.hp = 1e9
	# игрок на кольцевой улице (видно с улицы), укрытие — поперечный проход за стеной
	_street = SectorBuilder.polar(-100.0, 72.0) + Vector3(0, 0.1, 0)
	_hidden = SectorBuilder.polar(-120.0, 90.0) + Vector3(0, 0.1, 0)

	# 1. Склонность 100 — сел в засаду, присел, смотрит на последнюю точку, ждёт
	var a := _spawn("AmbushA", 100.0)
	await _contact(a)
	_check("A видит игрока — бой", a.state == Marauder.State.COMBAT and a._seen_now, _st(a))
	var lk := a.last_known
	_hidden = _find_hidden(a)
	_player.global_position = _hidden
	var ambushed := await _wait_tactic(a, Marauder.Tactic.AMBUSH, 9.0)
	await _wait(0.2)
	_check("игрок ушёл за угол — A сел в засаду", ambushed, _st(a))
	var los := a.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(a._eye(), lk + Vector3.UP * 1.2, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [a.get_rid()])).is_empty()
	_check("…присел и видит последнюю точку", a.crouched and los, "присел %s, видит точку %s, отошёл на %.1f м" % [a.crouched, los, a.global_position.distance_to(SectorBuilder.polar(-118.0, 72.0))])
	var face := Vector2(sin(a._facing), cos(a._facing))
	var to_lk := Vector2(lk.x - a.global_position.x, lk.z - a.global_position.z).normalized()
	_check("…стволом на последнюю точку", face.dot(to_lk) > 0.9, "курс·цель = %.2f" % face.dot(to_lk))
	var at_ambush := a._ambush_at
	var prev := a.tactic
	for i in range(360):
		await get_tree().physics_frame
		if a.tactic != prev or a.state != Marauder.State.COMBAT:
			print("    t+%.2f: %s -> %s, ambush_t %.1f, lk-at %.1f, seen %s, hurt %.1f, unseen %.1f, dist %.1f" % [i / 60.0, Marauder.Tactic.keys()[prev], _st(a), a._ambush_t, a.last_known.distance_to(at_ambush), a._seen_now, a._hurt_t, a._unseen_t, a.global_position.distance_to(_player.global_position)])
			prev = a.tactic
	_check("…и ждёт, а не идёт искать (6 с)", a.state == Marauder.State.COMBAT and a.tactic == Marauder.Tactic.AMBUSH
		and a.global_position.distance_to(at_ambush) > 3.0, "%s, память %.1f с" % [_st(a), a.memory_timer])
	# игрок вышел проверить туда же — первые выстрелы не «холодные»
	_player.global_position = _street
	var seen := false
	var aim_at_seen := 0.0
	for i in range(240):
		await get_tree().physics_frame
		if a._seen_now:
			seen = true
			aim_at_seen = a._aim
			break
	_check("игрок вышел на то же место — A увидел", seen, _st(a))
	_check("…и прицел уже сидит (разброс × %.2f, не × %.1f)" % [float(Balance.AI_AMBUSH.aim), Balance.AI_AIM_COLD],
		seen and aim_at_seen <= float(Balance.AI_AMBUSH.aim) + 0.01, "разброс × %.2f" % aim_at_seen)
	await _wait(0.3)
	_check("…и снова в бою в полный рост", a.tactic == Marauder.Tactic.ENGAGE, _st(a))
	a.queue_free()
	await _wait(1.0)

	# 2. Склонность 0 — идёт за целью, как раньше
	var b := _spawn("NoAmbushB", 0.0)
	await _contact(b)
	_player.global_position = _find_hidden(b)
	var b_amb := await _wait_tactic(b, Marauder.Tactic.AMBUSH, 6.0)
	_check("склонность 0 — засады нет, идёт вперёд", not b_amb and b.tactic in [Marauder.Tactic.PUSH, Marauder.Tactic.ADVANCE, Marauder.Tactic.COVER_MOVE, Marauder.Tactic.COVER_HIDE, Marauder.Tactic.COVER_PEEK, Marauder.Tactic.FLANK], _st(b))
	b.queue_free()
	await _wait(1.0)

	# 3. Отряд из двоих со склонностью 100 — в засаде один, второй идёт
	_player.global_position = _street
	var squad := Squad.new()
	var c1 := _spawn("SquadC1", 100.0, -118.0)
	var c2 := _spawn("SquadC2", 100.0, -116.0)
	squad.add(c1)
	squad.add(c2)
	await _contact(c1)
	for i in range(120):
		await get_tree().physics_frame
		if c2.state == Marauder.State.COMBAT:
			break
	_check("отряд: оба в бою", c1.state == Marauder.State.COMBAT and c2.state == Marauder.State.COMBAT, "%s / %s" % [_st(c1), _st(c2)])
	_player.global_position = _find_hidden(c1)
	var n_amb := 0
	for i in range(9 * 60):
		await get_tree().physics_frame
		n_amb = int(c1.tactic == Marauder.Tactic.AMBUSH) + int(c2.tactic == Marauder.Tactic.AMBUSH)
		if n_amb == 1 and i > 4 * 60:
			break
	_check("отряд: в засаде ровно один, второй идёт", n_amb == 1, "%s / %s" % [_st(c1), _st(c2)])
	# 4. Никто не вышел — встал и пошёл сам не позже hold_sec[1]
	var amb := c1 if c1.tactic == Marauder.Tactic.AMBUSH else c2
	var waited := 0.0
	var start := Time.get_ticks_msec()
	while amb.tactic == Marauder.Tactic.AMBUSH and waited < float(Balance.AI_AMBUSH.hold_sec[1]) + 6.0:
		await get_tree().physics_frame
		waited = (Time.get_ticks_msec() - start) / 1000.0
	_check("никто не вышел — через %.0f с (не дольше %.0f) встал и пошёл" % [waited, float(Balance.AI_AMBUSH.hold_sec[1]) + 1.0],
		amb.tactic != Marauder.Tactic.AMBUSH and waited <= float(Balance.AI_AMBUSH.hold_sec[1]) + 1.0, _st(amb))
	print("ambush_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _spawn(nm: String, bias: float, ang: float = -118.0) -> Marauder:
	var m := (preload("res://scenes/ai/marauder.tscn").instantiate()) as Marauder
	m.name = nm
	m.archetype = "gunner"
	m.weapon = "rifle"
	m.ambush_bias = bias
	_level.get_node("Marauders").add_child(m)
	m.global_position = SectorBuilder.polar(ang, 72.0) + Vector3(0, 0.1, 0)
	m.patrol_point_provider = func() -> Vector3: return m.global_position
	m._facing = atan2(_street.x - m.global_position.x, _street.z - m.global_position.z)
	return m


## Игрок на улице, мародёр смотрит на него — ждём, пока заметит.
func _contact(m: Marauder) -> void:
	_player.global_position = _street
	for i in range(240):
		await get_tree().physics_frame
		if m.state == Marauder.State.COMBAT and m._seen_now:
			await _wait(0.5)
			return
		# пока не заметил — смотрит на игрока (патруль сам крутит головой)
		m._facing = atan2(_player.global_position.x - m.global_position.x, _player.global_position.z - m.global_position.z)
	print("    контакта нет: %s, дист %.1f, игрок y %.2f, notice %.2f, видит %s" % [_st(m), m.global_position.distance_to(_player.global_position), _player.global_position.y, m.notice_timer,
		Perception.can_see(m.get_world_3d(), m._eye(), Vector3(sin(m._facing), 0.0, cos(m._facing)), _player, [m.get_rid()], 1.0)])


## Точка в поперечном проходе за стеной, которую с места мародёра не видно (луч в грудь упирается в стену).
func _find_hidden(m: Marauder) -> Vector3:
	var space := m.get_world_3d().direct_space_state
	for r in [86.0, 90.0, 94.0, 98.0, 102.0, 106.0]:
		for ang in [-120.0, -121.5, -118.5, -123.0]:
			var p := SectorBuilder.polar(ang, r) + Vector3(0, 0.1, 0)
			if NavigationServer3D.map_get_closest_point(m.get_world_3d().navigation_map, p).distance_to(p) > 1.0:
				continue
			var q := PhysicsRayQueryParameters3D.create(m._eye(), p + Vector3.UP * 1.2, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [m.get_rid()])
			if not space.intersect_ray(q).is_empty():
				return p
	print("    укрытой точки не нашлось — беру прежнюю")
	return _hidden


func _wait_tactic(m: Marauder, t: Marauder.Tactic, sec: float) -> bool:
	for i in range(int(sec * 60.0)):
		await get_tree().physics_frame
		if m.tactic == t and m.state == Marauder.State.COMBAT:
			return true
	return false


func _st(m: Marauder) -> String:
	return "%s/%s" % [Marauder.State.keys()[m.state], Marauder.Tactic.keys()[m.tactic]]


func _wait(s: float) -> void:
	await get_tree().create_timer(s).timeout


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
