extends Node
## Тактика отряда без рук на кольце: окрик (второй узнаёт о цели, не видя её), укрытие под огнём
## (присел за стеной), перезарядка, поиск после потери цели, не стреляет в стену, попали издалека —
## укрытие и перебежки, двое не идут в одну точку. Печатает [ok]/[FAIL] и итог.
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
	a.archetype = "gunner"
	a.weapon = "rifle"
	level.get_node("Marauders").add_child(a)
	a.global_position = SectorBuilder.polar(-118.0, 72.0) + Vector3(0, 0.1, 0)
	var b := scene.instantiate() as Marauder
	b.name = "SquadB"
	b.archetype = "gunner"
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
	_check("B не стреляет в стену, пока не видит", b._mag == int(b._spec.mag) or b._seen_now, "в магазине %d из %d" % [b._mag, int(b._spec.mag)])
	# двое идут к одной точке — каждый в свою
	var sp := SectorBuilder.polar(-100.0, 76.0)
	var d1 := scene.instantiate() as Marauder
	var d2 := scene.instantiate() as Marauder
	for pair in [[d1, "SpreadD1", -96.0], [d2, "SpreadD2", -95.0]]:
		var dm: Marauder = pair[0]
		dm.name = String(pair[1])
		dm.archetype = "gunner"
		level.get_node("Marauders").add_child(dm)
		dm.global_position = SectorBuilder.polar(float(pair[2]), 78.0) + Vector3(0, 0.1, 0)
	await get_tree().physics_frame
	for dm in [d1, d2]:
		(dm as Marauder).last_known = sp
		(dm as Marauder).state = Marauder.State.COMBAT
		(dm as Marauder)._set_tactic(Marauder.Tactic.PUSH)
	_check("двое к одной точке — в разные места", d1.move_target().distance_to(d2.move_target()) >= Balance.AI_SPREAD_CLAIM_M * 0.9,
		"между целями %.1f м" % d1.move_target().distance_to(d2.move_target()))
	d1.queue_free()
	d2.queue_free()
	# попали издалека, стрелка не видно — угадал направление, укрытие или перебежка (не в лоб)
	var c := scene.instantiate() as Marauder
	c.name = "FarC"
	c.archetype = "gunner"
	c.weapon = "rifle"
	level.get_node("Marauders").add_child(c)
	c.global_position = SectorBuilder.polar(-72.0, 72.0) + Vector3(0, 0.1, 0)
	c._facing = atan2(c.global_position.x - ppos.x, c.global_position.z - ppos.z)
	await get_tree().physics_frame
	var c0 := c.global_position.distance_to(ppos)
	c.get_node("Health").call("take_damage", 10.0, ppos + Vector3.UP * 1.3)
	await _wait(0.3)
	_check("попали издалека — в укрытие / перебежкой", c.state == Marauder.State.COMBAT and c.tactic in [Marauder.Tactic.COVER_MOVE, Marauder.Tactic.COVER_HIDE, Marauder.Tactic.COVER_PEEK, Marauder.Tactic.ADVANCE],
		"%s, направление угадано с ошибкой %.1f м" % [_st(c), c.last_known.distance_to(ppos)])
	await _wait(8.0)
	_check("…и продвигается к стрелку", c.global_position.distance_to(ppos) < c0 - 3.0 or c._seen_now,
		"было %.1f м, стало %.1f, %s" % [c0, c.global_position.distance_to(ppos), _st(c)])
	c.queue_free()
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
	if DisplayServer.get_name() != "headless":
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
	# доходят до последней известной точки (перебежками) — там пусто, память кончается → поиск
	for i in range(60):
		await _wait(0.5)
		if a.state in [Marauder.State.SEARCH, Marauder.State.PATROL] and b.state in [Marauder.State.SEARCH, Marauder.State.PATROL]:
			break
	_check("цель потеряна — поиск", a.state in [Marauder.State.SEARCH, Marauder.State.PATROL] and b.state in [Marauder.State.SEARCH, Marauder.State.PATROL],
		"%s / %s" % [_st(a), _st(b)])
	_check("здоровье мародёра — из баланса", is_equal_approx((a.get_node("Health") as Health).max_hp, Balance.MARAUDER_HP), "%.0f" % Balance.MARAUDER_HP)
	# типы: здоровье, броня, фигура; попадание «ведёт» и откидывает корпус; снайпер не сближается
	var kinds := {}
	for k in Balance.AI_ARCHETYPES:
		var t := scene.instantiate() as Marauder
		t.name = "Type_" + String(k)
		t.archetype = String(k)
		level.get_node("Marauders").add_child(t)
		t.global_position = SectorBuilder.polar(-140.0 - 6.0 * kinds.size(), 72.0) + Vector3(0, 0.1, 0)
		kinds[k] = t
	await get_tree().physics_frame
	var hp_ok := true
	for k in kinds:
		var t: Marauder = kinds[k]
		hp_ok = hp_ok and is_equal_approx((t.get_node("Health") as Health).max_hp, Balance.MARAUDER_HP * float(Balance.AI_ARCHETYPES[k].hp)) 			and t.weapon in Balance.AI_ARCHETYPES[k].weapons
	_check("типы: здоровье и оружие по типу", hp_ok, str(kinds.keys()))
	var hv: Marauder = kinds["heavy"]
	var hh := hv.get_node("Health") as Health
	var before_hp := hh.hp
	hh.take_damage(20.0, hv.global_position + Vector3(0, 1.3, 10))
	_check("тяжёлый: броня снимает часть урона", is_equal_approx(before_hp - hh.hp, 20.0 * float(Balance.AI_ARCHETYPES.heavy.armor)), "прошло %.1f из 20" % (before_hp - hh.hp))
	await get_tree().physics_frame
	_check("попадание: повело и откинуло", hv._stagger_t > 0.0 and hv._body.rotation.x < -0.01, "%.2f с, наклон %.2f" % [hv._stagger_t, hv._body.rotation.x])
	var sn: Marauder = kinds["sniper"]
	var sn0 := sn.global_position
	NoiseBus.shout(sn.global_position, 50.0, sn.global_position + Vector3(25, 0, 0), hv)
	await _wait(3.0)
	_check("снайпер держит позицию (окрик — не бежит)", sn.state == Marauder.State.COMBAT and sn.global_position.distance_to(sn0) < 1.5,
		"%s, сдвинулся на %.1f м" % [_st(sn), sn.global_position.distance_to(sn0)])
	# грабёж: одиночка у ближайшего контейнера — идёт, роется, забирает самое ценное в сумку
	var lp := SectorBuilder.polar(-150.0, 100.0)
	var box: LootContainer = null
	for cn in get_tree().get_nodes_in_group("loot_containers"):
		var cc := cn as LootContainer
		if box == null or cc.global_position.distance_to(lp) < box.global_position.distance_to(lp):
			box = cc
	box.rolled = true
	box.items = [ItemDb.make("gold_chain", 2), ItemDb.make("bandage", 1), ItemDb.make("water", 1)]
	var looter := scene.instantiate() as Marauder
	looter.name = "Looter"
	looter.archetype = "scout"
	looter.patrol_point_provider = func() -> Vector3: return looter.global_position
	level.get_node("Marauders").add_child(looter)
	looter.global_position = NavigationServer3D.map_get_closest_point(looter.get_world_3d().navigation_map, box.global_position + Vector3(4, 0, 0)) + Vector3(0, 0.1, 0)
	for i in range(40):
		await _wait(0.5)
		if not looter.pack.is_empty():
			break
	_check("мародёр грабит контейнер: самое ценное — в сумку", not looter.pack.is_empty() and String(looter.pack[0].id) == "gold_chain" and box.items.size() < 3,
		"сумка %s, в ящике %s" % [looter.pack, box.items])
	# роли отрядов: трое вступают в бой у одной цели — штурм, обход, прикрытие
	Squad.engaged.clear()
	var tgt := SectorBuilder.polar(-100.0, 72.0)
	var roles: Array = []
	var cover_m: Marauder = null
	for k in range(3):
		var sq := Squad.new()
		var m := scene.instantiate() as Marauder
		m.name = "Role%d" % k
		m.archetype = "gunner"
		m.weapon = "rifle"
		level.get_node("Marauders").add_child(m)
		m.global_position = SectorBuilder.polar(-130.0 + 12.0 * k, 72.0) + Vector3(0, 0.1, 0)
		sq.add(m)
		await get_tree().physics_frame
		m.last_known = tgt
		m.memory_timer = 20.0
		m._enter_combat(Marauder.Tactic.PUSH)
		roles.append(sq.role)
		if sq.role == Squad.Role.COVER:
			cover_m = m
	_check("роли по порядку: штурм, обход, прикрытие", roles == [Squad.Role.ASSAULT, Squad.Role.FLANK, Squad.Role.COVER], str(roles))
	_check("прикрытие идёт на позицию с обзором", cover_m != null and cover_m.tactic == Marauder.Tactic.OVERWATCH, Marauder.Tactic.keys()[cover_m.tactic] if cover_m else "-")
	# граната: штурм, цель пропала из виду 2 с назад, 15 м
	var gm := level.get_node("Marauders/Role0") as Marauder
	gm.global_position = tgt + Vector3(15, 0.1, 0)
	gm.last_known = tgt
	gm._seen_now = false
	gm._unseen_t = 2.0
	gm._grenade_t = 0.0
	for n in get_tree().get_nodes_in_group("marauders"):
		if n != gm:
			(n as Node3D).global_position += Vector3(0, 0, 60)
	gm._try_grenade(0.016)
	await get_tree().process_frame
	var nades := 0
	for n in get_tree().root.find_children("Grenade*", "", true, false):
		nades += 1
	_check("штурм кидает гранату туда, где цель скрылась", gm._grenades == 0 and nades > 0, "гранат осталось %d, в мире %d" % [gm._grenades, nades])
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
