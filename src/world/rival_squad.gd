class_name RivalSquad
extends RefCounted
## Один чужой отряд в рейде: у него, как у игроков, свой рейд — войти, обыскать, унести через
## выход. Бойцы — обычные Marauder фракции «rival» (зрение, слух, бой, обыск контейнеров — их
## собственные); здесь только план: когда хватит и куда уходить.
## Фазы: LOOT — ходит и обыскивает (маршрут выбирает ведущий, как мародёры); EXTRACT — идёт к выходу,
## по дороге не грабит, у выхода стоит без боя Balance.RIVALS.extract_sec и уходит с добычей (OUT);
## WIPED — никого не осталось (сумки лежат на телах — добыча достаётся тому, кто их выбил).

enum Phase { LOOT, EXTRACT, OUT, WIPED }

var id: String = ""
var name: String = ""
var style: Dictionary = {}
var squad: Squad
var phase: Phase = Phase.LOOT
## Выход: где и как называется (точка эвакуации уровня).
var exit_pos: Vector3 = Vector3.INF
var exit_name: String = ""
## Сколько секунд рейда отряд грабит, прежде чем идти к выходу; сколько записей в сумках ему хватит.
var loot_budget: float = 240.0
var pack_goal: int = 5
## Итог: сколько вынесли (цена), сколько бойцов выбили игроки / остальные.
var loot_value: int = 0
var killed_by_players: int = 0
var killed_by_ai: int = 0

var _age: float = 0.0
var _wait: float = 0.0
var _size0: int = 0
var _counted: Dictionary = {}
var _rng := RandomNumberGenerator.new()


func setup(record: Dictionary, sq: Squad, exit_at: Vector3, exit_label: String, rng: RandomNumberGenerator) -> void:
	id = String(record.get("id", ""))
	name = String(record.get("name", "Чужие"))
	style = RivalRoster.style(String(record.get("style", "assault")))
	squad = sq
	exit_pos = exit_at
	exit_name = exit_label
	_rng.seed = rng.randi()
	_size0 = sq.members.size()
	var cfg: Dictionary = Balance.RIVALS
	loot_budget = rng.randf_range(float(cfg.loot_sec[0]), float(cfg.loot_sec[1])) * float(style.get("loot_k", 1.0))
	pack_goal = maxi(1, roundi(float(cfg.pack_goal) * float(style.get("goal_k", 1.0))))


func alive() -> Array[Marauder]:
	return squad.alive() if squad else ([] as Array[Marauder])


## Сколько записей добычи в сумках живых.
func packed() -> int:
	var n := 0
	for m: Marauder in alive():
		n += m.pack.size()
	return n


## Шаг плана (хост). Возвращает фазу, если она сменилась на этом шаге, иначе -1.
func tick(delta: float) -> int:
	if phase == Phase.OUT or phase == Phase.WIPED:
		return -1
	_age += delta
	_count_losses()
	var living: Array[Marauder] = alive()
	if living.is_empty():
		phase = Phase.WIPED
		return phase
	if phase == Phase.LOOT:
		var lost: float = 1.0 - float(living.size()) / float(maxi(_size0, 1))
		if _age >= loot_budget or packed() >= pack_goal or lost >= float(Balance.RIVALS.loss_share):
			_head_out(living)
			return phase
		return -1
	# к выходу: ведущий мог смениться — цель и запрет на обыск повторяются каждый шаг
	for m: Marauder in living:
		m.no_loot = true
		m.patrol_point_provider = _exit_point
	var here: bool = true
	for m: Marauder in living:
		# раненого у выхода ждут: лежащий не ушёл
		if m.state in [Marauder.State.COMBAT, Marauder.State.DOWNED, Marauder.State.RESCUE] \
				or m.global_position.distance_to(exit_pos) > float(Balance.RIVALS.extract_m):
			here = false
			break
	_wait = _wait + delta if here else 0.0
	if _wait >= float(Balance.RIVALS.extract_sec):
		_leave(living)
		return phase
	return -1


func _head_out(living: Array[Marauder]) -> void:
	phase = Phase.EXTRACT
	_wait = 0.0
	for m: Marauder in living:
		m.no_loot = true
		m._drop_loot_claim()
		m.patrol_point_provider = _exit_point
	var lead: Marauder = squad.leader()
	if lead:
		lead.pause_timer = 0.0
		lead.investigate_at(_exit_point())


## Точка у выхода (с разбросом — отряд не встаёт в одну клетку).
func _exit_point() -> Vector3:
	var a := _rng.randf() * TAU
	return exit_pos + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(0.5, float(Balance.RIVALS.extract_m) * 0.5)


## Ушли: добыча из сумок уходит с ними, бойцы исчезают (у всех — спавнер снимает узлы).
func _leave(living: Array[Marauder]) -> void:
	for m: Marauder in living:
		for e: Variant in m.pack:
			loot_value += ItemDb.entry_value(e as Dictionary)
		m.queue_free()
	phase = Phase.OUT


## Потери: кто выбил бойца — игрок (Health.last_attacker — его peer) или остальные.
func _count_losses() -> void:
	for m: Marauder in squad.members:
		if not is_instance_valid(m) or m.state != Marauder.State.DEAD or _counted.has(m.get_instance_id()):
			continue
		_counted[m.get_instance_id()] = true
		var health: Health = m.get_node_or_null("Health") as Health
		if health and health.last_attacker > 0:
			killed_by_players += 1
		else:
			killed_by_ai += 1
