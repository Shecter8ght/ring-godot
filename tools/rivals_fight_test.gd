extends Node
## Бой между группами (RivalSquad): отряд, потерявший в бою бойца, разрывает контакт и уходит к выходу;
## «крысы» с добычей отходят при первом контакте; победители не гонятся дальше предела; бой стих —
## ведущий обыскивает ящики с убитых, остальные стоят вокруг в прикрытии, добыча уходит в сумки.
## tools/godot.cmd --headless res://tools/rivals_fight_test.tscn

var _fails: int = 0
var _level: Node
var _rivals: RivalRaids


func _ready() -> void:
	RaidEvents.enabled = false
	RivalRoster.use_file("user://rivals_fight_test.json", true)
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
	var player := get_tree().get_first_node_in_group("players") as Player
	player.health.hp = 1e9
	player.set_physics_process(false)
	player.global_position = Vector3(0, -80, 0)
	_rivals = RivalRaids.current
	# Сравниваем один состав и расстановку, а не разных случайных противников.
	seed(20261014)
	(_level.get("_rng") as RandomNumberGenerator).seed = 20261014
	_rivals._rng.seed = 20261014
	var exits: Array = _rivals._exits()
	var free: Array = exits.filter(func(e: Dictionary) -> bool: return String(e.key) == "" and String(e.switch) == "")
	var exit: Vector3 = (free[0] if not free.is_empty() else exits[0]).pos
	Engine.time_scale = 3.0
	await _retreat(exit)
	await _rats(exit)
	await _leash(exit)
	await _sweep(exit)
	Engine.time_scale = 1.0
	print("rivals_fight_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Кольцевая улица ТЦ Ø200 (r 58–68): середина (r 72 — уже внешние магазины, было от кольца Ø250).
const STREET_R := 63.0


## Место на кольцевой улице, не ближе 60 м к выходу отряда.
func _spot(exit: Vector3, shift: float = 0.0) -> Vector3:
	for a: float in [-100.0, -60.0, -140.0, -30.0]:
		var p: Vector3 = SectorBuilder.polar(a + shift, STREET_R)
		if p.distance_to(exit) > 60.0:
			return p
	return SectorBuilder.polar(-100.0 + shift, STREET_R)


func _squad(index: int, at: Vector3, exit: Vector3) -> RivalSquad:
	var s: RivalSquad = _rivals.enter(RivalRoster.squads()[index], at, exit)
	if s:
		for m: Marauder in s.alive():
			m.patrol_point_provider = func() -> Vector3: return at
	return s


func _scavs(at: Vector3, archs: Array) -> Squad:
	var sq: Squad = _level.call("spawn_squad", at, archs, {}) as Squad
	for m: Marauder in sq.alive():
		m.patrol_point_provider = func() -> Vector3: return at
	return sq


func _in_combat(s: RivalSquad) -> bool:
	for m: Marauder in s.alive():
		if m.state == Marauder.State.COMBAT:
			return true
	return false


func _kill(m: Marauder) -> void:
	var health: Health = m.get_node("Health") as Health
	for i: int in range(3):
		if is_instance_valid(m) and m.state != Marauder.State.DEAD:
			health.apply_or_request_damage(100000.0, m.global_position + Vector3(0, 1, 2), "head", -1)


## Потеряли в бою бойца — разрывают контакт, идут к выходу.
func _retreat(exit: Vector3) -> void:
	var at: Vector3 = _spot(exit)
	var s: RivalSquad = _squad(0, at, exit)
	var foes: Squad = _scavs(_spot(exit, -7.0), ["gunner", "gunner"])
	_check("отряд и мародёры на улице", s != null and foes != null and s.alive().size() >= 2)
	var t: float = 0.0
	while t < 40.0 and not _in_combat(s):
		await _wait(0.5)
		t += 0.5
	_check("бой начался", _in_combat(s), "ждали %d с" % int(t))
	var before: float = s.squad.leader().global_position.distance_to(exit)
	_check("до потерь отряд не отступает", s.breaks == 0 and s.phase == RivalSquad.Phase.LOOT)
	var victim: Marauder = s.alive()[s.alive().size() - 1]
	# остальных мародёры добить не должны — смотрим именно отход
	for m: Marauder in s.alive():
		if m != victim:
			(m.get_node("Health") as Health).invulnerable = true
	_kill(victim)
	await _wait(1.5)
	var running: int = 0
	for m: Marauder in s.alive():
		if m.state == Marauder.State.RETREAT:
			running += 1
	_check("потеряли бойца — разрывают контакт и идут на выход", s.breaks == 1 and s.phase == RivalSquad.Phase.EXTRACT and running >= 1,
		"отходов %d, фаза %d, бегут %d" % [s.breaks, s.phase, running])
	# мародёров убираем: дальше смотрим, что отход — это движение к выходу, а не отсидка за углом
	for m: Marauder in foes.alive():
		m.queue_free()
	await _wait(float(Balance.RIVALS.retreat_sec) * 0.6)
	var lead: Marauder = s.squad.leader()
	_check("отходят к выходу", lead != null and lead.global_position.distance_to(exit) < before - 12.0,
		"было %.0f м, стало %.0f м" % [before, lead.global_position.distance_to(exit) if lead else -1.0])
	await _wait(float(Balance.RIVALS.retreat_sec) * 0.6)
	var calm: bool = true
	for m: Marauder in s.alive():
		if m.state == Marauder.State.RETREAT:
			calm = false
	_check("отбежали — дальше идут по плану, отход повторно не объявляют", calm and s.breaks == 1)
	await _clear(s)


## «Крысы» с добычей в сумках отходят при первом же контакте, без потерь.
func _rats(exit: Vector3) -> void:
	var at: Vector3 = _spot(exit)
	var s: RivalSquad = _squad(1, at, exit)
	_check("«крысы» вошли", s != null and bool(s.style.get("flee", false)))
	if s == null:
		return
	for i: int in range(int(Balance.RIVALS.flee_packed)):
		s.squad.leader().pack.append({"id": "cash", "n": 1})
	var foes: Squad = _scavs(_spot(exit, -7.0), ["gunner", "gunner"])
	var t: float = 0.0
	while t < 40.0 and s.breaks == 0 and not s.alive().is_empty():
		await _wait(0.5)
		t += 0.5
	_check("«крысы» с добычей отходят при первом контакте, без потерь", s.breaks == 1 and s.alive().size() == s._size0, "отходов %d, живых %d" % [s.breaks, s.alive().size()])
	for m: Marauder in foes.alive():
		m.queue_free()
	await _clear(s)


## Победители не гонятся дальше предела от места боя.
func _leash(exit: Vector3) -> void:
	var at: Vector3 = _spot(exit)
	var s: RivalSquad = _squad(4, at, exit)
	_check("отряд для погони", s != null)
	if s == null:
		return
	await _wait(1.0)
	var m: Marauder = s.squad.leader()
	# бой был здесь и стих; боец ушёл искать дальше предела
	s._fight_at = at
	s._fight_size = s.alive().size()
	s._calm = 0.0
	m.last_known = at + Vector3(float(Balance.RIVALS.pursuit_m) + 30.0, 0, 0)
	m.state = Marauder.State.SEARCH
	m.global_position = m._snap(SectorBuilder.polar(-100.0 + 50.0, 72.0)) if at.distance_to(SectorBuilder.polar(-50.0, 72.0)) > float(Balance.RIVALS.pursuit_m) else m._snap(SectorBuilder.polar(-160.0, 72.0))
	await _wait(1.2)
	_check("ушёл искать дальше предела погони — возвращается к плану", m.state == Marauder.State.PATROL, "состояние %d, от места боя %.0f м" % [m.state, m.global_position.distance_to(at)])
	await _clear(s)


## Бой стих: ведущий обыскивает ящики с убитых, остальные прикрывают; добыча — в сумки.
func _sweep(exit: Vector3) -> void:
	var at: Vector3 = _spot(exit)
	var s: RivalSquad = _squad(5, at, exit)
	var foes: Squad = _scavs(_spot(exit, -6.0), ["gunner", "gunner"])
	_check("отряд и мародёры для обыска", s != null and foes != null and not bool(s.style.get("flee", false)))
	if s == null:
		return
	# отряд не должен уйти по времени или отступить из-за случайной потери, пока идёт проверка
	s.loot_budget = 100000.0
	s.pack_goal = 100
	for m: Marauder in s.alive():
		(m.get_node("Health") as Health).invulnerable = true
	var t: float = 0.0
	while t < 40.0 and not _in_combat(s):
		await _wait(0.5)
		t += 0.5
	_check("бой начался", _in_combat(s))
	for m: Marauder in foes.alive():
		_kill(m)
	await _wait(0.5)
	var crates: Array = get_tree().get_nodes_in_group("loot_containers").filter(func(n: Node) -> bool:
		return (n as LootContainer).look == LootContainer.Look.CRATE and (n as Node3D).global_position.distance_to(at) < float(Balance.RIVALS.sweep_m))
	var value_before: int = 0
	for c: Node in crates:
		(c as LootContainer).roll()
		value_before += ItemDb.value_of((c as LootContainer).items)
	_check("с убитых остались ящики", crates.size() >= 2 and value_before > 0, "ящиков %d, на %d" % [crates.size(), value_before])
	t = 0.0
	while t < 60.0 and s.sweeps == 0 and not s.alive().is_empty():
		await _wait(0.5)
		t += 0.5
	_check("бой стих — отряд начал обыск тел", s.sweeps == 1 and s.breaks == 0, "обысков %d, отходов %d, ждали %d с" % [s.sweeps, s.breaks, int(t)])
	await _wait(2.0)
	var lead: Marauder = s.squad.leader()
	var holding: int = 0
	for m: Marauder in s.alive():
		if m != lead and String(m._order.get("kind", "")) == "hold":
			holding += 1
	_check("ведущий идёт к телу, остальные встали в прикрытие", lead != null and lead.is_looting() and holding == s.alive().size() - 1,
		"обыскивает %s, прикрывают %d из %d" % [str(lead != null and lead.is_looting()), holding, s.alive().size() - 1])
	t = 0.0
	while t < float(Balance.RIVALS.sweep_sec) + 20.0 and not s._sweep.is_empty():
		await _wait(0.5)
		t += 0.5
	var value_after: int = 0
	for c: Node in crates:
		if is_instance_valid(c):
			value_after += ItemDb.value_of((c as LootContainer).items)
	var still: int = 0
	for m: Marauder in s.alive():
		if String(m._order.get("kind", "")) == "hold":
			still += 1
	_check("обыск окончен: лучшее с тел — в сумках отряда, прикрытие снято", s._sweep.is_empty() and s.packed() > 0 and value_after < value_before and still == 0,
		"в сумках %d, на телах было %d — осталось %d, стоят %d" % [s.packed(), value_before, value_after, still])
	await _clear(s)


func _clear(s: RivalSquad) -> void:
	if s:
		for m: Marauder in s.alive():
			m.queue_free()
	for n: Node in _level.get_node("Marauders").get_children():
		n.queue_free()
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		if (n as LootContainer).look == LootContainer.Look.CRATE:
			n.queue_free()
	await _wait(0.6)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec, true, true).timeout


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
