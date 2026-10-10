extends Node
## Чужие отряды (RivalRaids): в тестовом запуске сами не появляются; отряд входит, обыскивает
## контейнеры (после него в них меньше), идёт к выходу и уходит с добычей — память состава это
## помнит; два чужих отряда воюют между собой и с мародёрами, внутри отряда — нет; отряд, выбитый
## игроком, записан за игроком. Печатает [ok]/[FAIL] и итог.
## tools/godot.cmd --headless res://tools/rivals_test.tscn

var _fails: int = 0
var _level: Node
var _rivals: RivalRaids


func _ready() -> void:
	RaidEvents.enabled = false
	RivalRoster.use_file("user://rivals_test.json", true)
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	await get_tree().physics_frame
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 1e9
	# игрок — далеко в стороне и под землёй: чужие его не видят и не слышат
	player.set_physics_process(false)
	player.global_position = Vector3(0, -80, 0)
	_rivals = RivalRaids.current
	_check("узел чужих отрядов у уровня", _rivals != null)
	_check("в тестовом запуске сами не приходят", not RivalRaids.active() and _rivals.squads.is_empty() and _rivals._queue.is_empty())
	_check("состав: 15 отрядов, у каждого характер", RivalRoster.squads().size() == 15 and not RivalRoster.style("rats").is_empty())
	var exits: Array = _rivals._exits()
	_check("у уровня есть точки эвакуации", exits.size() >= 1, str(exits.size()))
	if _rivals == null or exits.is_empty():
		_finish()
		return
	Engine.time_scale = 4.0
	await _loot_and_leave(exits)
	await _fights()
	await _wiped_by_player()
	Engine.time_scale = 1.0
	_finish()


## Отряд входит у комнаты с добычей, грабит, уходит через выход.
func _loot_and_leave(exits: Array) -> void:
	var exit: Dictionary = exits[0]
	var at: Vector3 = _container_near(exit.pos)
	var before: int = _loot_left()
	var s: RivalSquad = _rivals.enter(RivalRoster.squads()[0], at, exit.pos)
	_check("отряд вошёл", s != null and s.alive().size() >= 2, "" if s == null else str(s.alive().size()))
	if s == null:
		return
	_check("бойцы — фракция rival, враждебны игрокам", s.alive()[0].faction == "rival" and s.alive()[0].hostile_to_players)
	_check("память: рейд записан", int(RivalRoster.memory(s.id).raids) == 1)
	s.loot_budget = 70.0
	s.pack_goal = 3
	var t := 0.0
	while s.phase == RivalSquad.Phase.LOOT and t < 120.0:
		await _wait(1.0)
		t += 1.0
	_check("набрали добычу и пошли к выходу", s.phase == RivalSquad.Phase.EXTRACT and s.packed() > 0, "фаза %d, в сумках %d, прошло %d с" % [s.phase, s.packed(), int(t)])
	_check("после них в контейнерах меньше", _loot_left() < before, "%d → %d" % [before, _loot_left()])
	var packed: int = s.packed()
	t = 0.0
	while s.phase == RivalSquad.Phase.EXTRACT and t < 240.0:
		await _wait(1.0)
		t += 1.0
	_check("ушли через выход", s.phase == RivalSquad.Phase.OUT, "фаза %d, прошло %d с, до выхода %s" % [s.phase, int(t),
		s.alive().map(func(m: Marauder) -> int: return int(m.global_position.distance_to(s.exit_pos)))])
	await _wait(0.5)
	_check("бойцов на карте не осталось, добыча унесена", s.alive().is_empty() and s.loot_value > 0 and packed > 0, "вынесли на %d" % s.loot_value)
	var mem: Dictionary = RivalRoster.memory(s.id)
	_check("память: ушли с добычей", int(mem.out) == 1 and int(mem.loot) == s.loot_value)


## Два чужих отряда рядом — бой; свои своих не трогают; мародёры им тоже враги.
func _fights() -> void:
	var at: Vector3 = SectorBuilder.polar(-100.0, 72.0)
	var a: RivalSquad = _rivals.enter(RivalRoster.squads()[1], at, at)
	var b: RivalSquad = _rivals.enter(RivalRoster.squads()[2], SectorBuilder.polar(-108.0, 72.0), at)
	_check("два отряда на улице", a != null and b != null)
	if a == null or b == null:
		return
	_check("враг — чужой из другого отряда", "rival" in (Balance.AI_HOSTILE.rival as Array) and a.squad != b.squad)
	for m: Marauder in a.alive() + b.alive():
		m.patrol_point_provider = func() -> Vector3: return at
	var t := 0.0
	var own_fire := false
	while t < 60.0 and a.killed_by_ai + b.killed_by_ai == 0:
		await _wait(0.5)
		t += 0.5
		for m: Marauder in a.alive():
			if m._foe != null and is_instance_valid(m._foe) and m._foe.squad == a.squad:
				own_fire = true
	_check("чужие отряды воюют между собой", a.killed_by_ai + b.killed_by_ai > 0, "прошло %d с" % int(t))
	_check("в своих не целятся", not own_fire)
	for m: Marauder in a.alive() + b.alive():
		m.queue_free()
	await _wait(0.5)
	# мародёр и чужой
	var c: RivalSquad = _rivals.enter(RivalRoster.squads()[3], at, at)
	var scav_squad: Squad = _level.call("spawn_squad", SectorBuilder.polar(-107.0, 72.0), ["gunner", "gunner"], {}) as Squad
	_check("мародёры рядом с чужими", c != null and scav_squad != null)
	if c == null or scav_squad == null:
		return
	for m: Marauder in c.alive() + scav_squad.alive():
		m.patrol_point_provider = func() -> Vector3: return at
	t = 0.0
	while t < 60.0 and c.killed_by_ai == 0 and scav_squad.alive().size() == 2:
		await _wait(0.5)
		t += 0.5
	_check("чужие и мародёры воюют", c.killed_by_ai > 0 or scav_squad.alive().size() < 2, "прошло %d с" % int(t))
	for m: Marauder in c.alive() + scav_squad.alive():
		m.queue_free()
	await _wait(0.5)


## Игрок выбил отряд: записано за игроком.
func _wiped_by_player() -> void:
	var at: Vector3 = SectorBuilder.polar(-100.0, 72.0)
	var s: RivalSquad = _rivals.enter(RivalRoster.squads()[4], at, at)
	_check("отряд для игрока", s != null)
	if s == null:
		return
	await _wait(1.0)
	# тяжело раненый лежит и ещё жив — добиваем, как добивал бы игрок
	for i in range(4):
		for m: Marauder in s.alive():
			var health: Health = m.get_node("Health") as Health
			health.apply_or_request_damage(100000.0, m.global_position + Vector3(0, 1, 2), "head", 1)
		await _wait(1.0)
	_check("отряд выбит игроком", s.phase == RivalSquad.Phase.WIPED and s.killed_by_players >= 2 and s.killed_by_ai == 0,
		"фаза %d, игроки %d, остальные %d" % [s.phase, s.killed_by_players, s.killed_by_ai])
	var mem: Dictionary = RivalRoster.memory(s.id)
	_check("память: выбиты игроком", int(mem.wiped) == 1 and int(mem.wiped_by_you) == 1)
	_check("итог рейда перечисляет отряды", _rivals.results().size() == _rivals.squads.size() and _rivals.results().size() >= 5)


## Точка у ближайшего к p контейнера.
func _container_near(p: Vector3) -> Vector3:
	var best: Vector3 = p
	var best_d: float = INF
	for n in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null:
			continue
		var d: float = c.global_position.distance_to(p)
		if d < best_d:
			best = c.global_position
			best_d = d
	return best


## Сколько записей добычи осталось во всех контейнерах (не открытые считаются полными: 1000 за каждый).
func _loot_left() -> int:
	var n := 0
	for node in get_tree().get_nodes_in_group("loot_containers"):
		var c := node as LootContainer
		if c:
			n += c.items.size() if c.rolled else 1000
	return n


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec, true, true).timeout


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])


func _finish() -> void:
	print("rivals_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)
