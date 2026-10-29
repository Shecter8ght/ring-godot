class_name RivalSquad
extends RefCounted
## Один чужой отряд в рейде: у него, как у игроков, свой рейд — войти, обыскать, унести через
## выход. Бойцы — обычные Marauder фракции «rival» (зрение, слух, бой, обыск контейнеров — их
## собственные); здесь только план: когда хватит и куда уходить.
## Фазы: LOOT — ходит и обыскивает (маршрут выбирает ведущий, как мародёры); EXTRACT — идёт к выходу,
## по дороге не грабит, у выхода стоит без боя Balance.RIVALS.extract_sec и уходит с добычей (OUT);
## WIPED — никого не осталось (сумки лежат на телах — добыча достаётся тому, кто их выбил).
##
## Бой между группами (Balance.RIVALS): потеряли в бою бойца — разрывают контакт и уходят из рейда
## (бегом к выходу, а не до последнего); победители не гонятся дальше pursuit_m от места боя; бой стих
## — ведущий обыскивает тела, остальные прикрывают, потом отряд идёт дальше. Так ждать, пока все
## перебьют друг друга, невыгодно: проигравшие уносят своё, победители забирают лучшее с тел.
##
## Правила мира для них те же, что для игроков (решение владельца, 2026-10-10): дверь, запертая на
## ключ, без ключа не открывается — отряд идёт за ключом (KeyPickup: подобрал — на карте его больше
## нет, лежит в сумке ведущего и выпадает с телом); выход за рубильником — сначала щёлкнуть рубильник
## (слышно, и выход открыт для всех); выход по ключу — только с ключом. Такие дела — «поручения»
## (_errand): отряд идёт к месту, ведущий делает дело, план продолжается.

enum Phase { LOOT, EXTRACT, OUT, WIPED }

## Сколько секунд отряд тратит на одно поручение; с какого расстояния ведущий дотягивается, м, и с какого —
## если его путь кончился, не дойдя.
const ERRAND_SEC := 150.0
## Сколько секунд ведущий ждёт у выхода отставших.
const STRAGGLER_SEC := 60.0
const ERRAND_REACH := 3.0
const ERRAND_FAR := 9.0

var id: String = ""
var name: String = ""
var style: Dictionary = {}
var squad: Squad
var phase: Phase = Phase.LOOT
## Выход: где, как называется, что нужно, чтобы уйти (рубильник / ключ; "" — ничего).
var exit_pos: Vector3 = Vector3.INF
var exit_name: String = ""
var exit_switch: String = ""
var exit_key: String = ""
## Сколько секунд рейда отряд грабит, прежде чем идти к выходу; сколько записей в сумках ему хватит.
var loot_budget: float = 240.0
var pack_goal: int = 5
## Ключи, которые отряд подобрал.
var keys: Array[String] = []
## Итог: сколько вынесли (цена), сколько бойцов выбили игроки / остальные.
var loot_value: int = 0
var killed_by_players: int = 0
var killed_by_ai: int = 0
## Выход стал недоступен (ключ забрали, питания нет) — RivalRaids даёт другой: func(RivalSquad) -> bool.
var other_exit: Callable

var _age: float = 0.0
var _wait: float = 0.0
var _stall: float = 0.0
var _size0: int = 0
var _counted: Dictionary = {}
## Текущее поручение {kind: "key" | "switch", node, pos, id} и когда последний раз упёрлись в дверь.
var _errand: Dictionary = {}
var _door_cd: float = 0.0
## Откуда ведущий берёт точки, пока грабит (как дал уровень), и смотрели ли уже, есть ли на карте ключ.
var _patrol: Callable
var _key_checked: bool = false
var _rng := RandomNumberGenerator.new()
## Бой: где начался (INF — боя нет), сколько боеспособных было в начале, сколько секунд тихо; сколько
## секунд назад отступили (−1 — не отступали). Обыск тел: {left, bodies, i}. Счётчики — для итога и тестов.
var _fight_at: Vector3 = Vector3.INF
var _fight_size: int = 0
## Сколько боеспособных было до боя (потеря в первые же мгновения боя — тоже потеря).
var _peace_able: int = 0
var _calm: float = 0.0
var _broke_t: float = -1.0
var _sweep: Dictionary = {}
var breaks: int = 0
var sweeps: int = 0


func setup(record: Dictionary, sq: Squad, exit: Dictionary, rng: RandomNumberGenerator) -> void:
	id = String(record.get("id", ""))
	name = String(record.get("name", "Чужие"))
	style = RivalRoster.style(String(record.get("style", "assault")))
	squad = sq
	set_exit(exit)
	_rng.seed = rng.randi()
	_size0 = sq.members.size()
	_peace_able = _size0
	if not sq.members.is_empty():
		_patrol = sq.members[0].patrol_point_provider
	var cfg: Dictionary = Balance.RIVALS
	loot_budget = rng.randf_range(float(cfg.loot_sec[0]), float(cfg.loot_sec[1])) * float(style.get("loot_k", 1.0))
	pack_goal = maxi(1, roundi(float(cfg.pack_goal) * float(style.get("goal_k", 1.0))))


## Выход отряда: {pos, name[, switch, key]}.
func set_exit(exit: Dictionary) -> void:
	exit_pos = exit.get("pos", Vector3.INF)
	exit_name = String(exit.get("name", "выход"))
	exit_switch = String(exit.get("switch", ""))
	exit_key = String(exit.get("key", ""))


func alive() -> Array[Marauder]:
	return squad.alive() if squad else ([] as Array[Marauder])


## Сколько записей добычи в сумках живых (ключи не в счёт).
func packed() -> int:
	var n := 0
	for m: Marauder in alive():
		for e: Variant in m.pack:
			if not String((e as Dictionary).get("id", "")) in keys:
				n += 1
	return n


## Шаг плана (хост). Возвращает фазу, если она сменилась на этом шаге, иначе -1.
func tick(delta: float) -> int:
	if phase == Phase.OUT or phase == Phase.WIPED:
		return -1
	_age += delta
	_door_cd = maxf(0.0, _door_cd - delta)
	_count_losses()
	var living: Array[Marauder] = alive()
	if living.is_empty():
		phase = Phase.WIPED
		return phase
	var was: Phase = phase
	if _tick_fight(living, delta):
		return phase if phase != was else -1
	if phase == Phase.LOOT:
		var lost: float = 1.0 - float(living.size()) / float(maxi(_size0, 1))
		if _age >= loot_budget or packed() >= pack_goal or lost >= float(Balance.RIVALS.loss_share):
			_head_out(living)
			return phase
		if not _key_checked:
			# на карте лежит ключ — часть отрядов первым делом идёт за ним
			_key_checked = true
			var any_key: KeyPickup = _any_key(living[0].get_tree())
			if any_key and _rng.randf() < float(Balance.RIVALS.key_chance):
				_set_errand({"kind": "key", "node": any_key, "pos": any_key.global_position, "id": any_key.key_id})
		_run_errand(living)
		return -1
	# к выходу: сначала дела (ключ, рубильник), потом сам выход
	if _errand.is_empty() and not _exit_ready(living):
		return -1
	if _run_errand(living):
		return -1
	# ведущий мог смениться — цель и запрет на обыск повторяются каждый шаг
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
	# отставших (застрял, отбился) ведущий ждёт у выхода не вечно: STRAGGLER_SEC — и уходят те, кто в зоне
	var lead: Marauder = squad.leader()
	var lead_here: bool = lead != null and lead.state != Marauder.State.COMBAT 			and lead.global_position.distance_to(exit_pos) <= float(Balance.RIVALS.extract_m)
	_stall = _stall + delta if lead_here and not here else 0.0
	if _wait >= float(Balance.RIVALS.extract_sec) or _stall >= STRAGGLER_SEC:
		_leave(living.filter(func(m: Marauder) -> bool:
			return m.global_position.distance_to(exit_pos) <= float(Balance.RIVALS.extract_m) and m.state != Marauder.State.DOWNED))
		return phase
	return -1


# ---------------------------------------------------------------- бой: отход, предел погони, обыск тел

func _able(living: Array[Marauder]) -> Array[Marauder]:
	return living.filter(func(m: Marauder) -> bool: return not m.state in [Marauder.State.DOWNED, Marauder.State.RESCUE])


## Шаг боя. true — отряд занят (отходит или обыскивает тела): обычный план в этот шаг не идёт.
func _tick_fight(living: Array[Marauder], delta: float) -> bool:
	var cfg: Dictionary = Balance.RIVALS
	var able: Array[Marauder] = _able(living)
	var fighting: bool = false
	for m: Marauder in living:
		if m.state == Marauder.State.COMBAT:
			fighting = true
			break
	if _broke_t >= 0.0:
		_broke_t += delta
		if _broke_t > float(cfg.rearm_sec) and not fighting:
			_broke_t = -1.0
	var lead: Marauder = squad.leader()
	if fighting:
		_calm = 0.0
		_cancel_sweep(living)
		if _fight_at == Vector3.INF:
			_fight_at = lead.global_position if lead else living[0].global_position
			_fight_size = maxi(able.size(), _peace_able)
			# «крысы» с добычей в драку не лезут — отходят при первом контакте
			if bool(style.get("flee", false)) and packed() >= int(cfg.flee_packed) and _broke_t < 0.0:
				_break_contact(living)
				return true
		# потеряли в этом бою бойца (убит или лежит) — разрываем контакт; прижали повторно — дерутся
		if _broke_t < 0.0 and not able.is_empty() and able.size() < _fight_size:
			_break_contact(living)
			return true
		return false
	_peace_able = able.size()
	if _fight_at != Vector3.INF:
		_calm += delta
		# победители не гонятся бесконечно: ушёл дальше предела от места боя — возвращается к плану
		for m: Marauder in able:
			if m.state in [Marauder.State.SEARCH, Marauder.State.INVESTIGATE] and m.global_position.distance_to(_fight_at) > float(cfg.pursuit_m):
				m.stand_down()
		if _calm >= float(cfg.calm_sec):
			if _broke_t < 0.0 and phase == Phase.LOOT:
				_start_sweep(living)
			_fight_at = Vector3.INF
			_fight_size = 0
	if not _sweep.is_empty():
		return _run_sweep(living, delta)
	return false


## Разорвать контакт: все, кто на ногах, бегут к выходу; отряд из рейда уходит.
func _break_contact(living: Array[Marauder]) -> void:
	breaks += 1
	_broke_t = 0.0
	_cancel_sweep(living)
	var lead: Marauder = squad.leader()
	if lead:
		lead.say("Отходим!")
	if phase == Phase.LOOT:
		_head_out(living)
	var to: Vector3 = _exit_point()
	for m: Marauder in _able(living):
		m.no_loot = true
		m.break_contact(to, float(Balance.RIVALS.retreat_sec))
	print("rivals: «%s» разрывают контакт, уходят к выходу «%s»" % [name, exit_name])


## Бой стих, отряд на ногах: ведущий обыскивает ящики с убитых рядом с местом боя, остальные прикрывают.
func _start_sweep(living: Array[Marauder]) -> void:
	var cfg: Dictionary = Balance.RIVALS
	var lead: Marauder = squad.leader()
	if lead == null or packed() >= pack_goal or bool(style.get("flee", false)):
		return
	var bodies: Array = []
	for n: Node in lead.get_tree().get_nodes_in_group("loot_containers"):
		var c: LootContainer = n as LootContainer
		if c == null or c.look != LootContainer.Look.CRATE or (c.rolled and c.items.is_empty()) or not c.ai_may_search():
			continue
		if c.global_position.distance_to(_fight_at) <= float(cfg.sweep_m):
			bodies.append(c)
	if bodies.is_empty():
		return
	var from: Vector3 = lead.global_position
	bodies.sort_custom(func(a: LootContainer, b: LootContainer) -> bool: return a.global_position.distance_to(from) < b.global_position.distance_to(from))
	bodies.resize(mini(bodies.size(), int(cfg.sweep_bodies)))
	_sweep = {"left": float(cfg.sweep_sec), "bodies": bodies, "i": -1}
	sweeps += 1
	lead.say("Проверю тела. Прикройте.")
	print("rivals: «%s» обыскивают тела (%d) после боя" % [name, bodies.size()])


## true — обыск идёт. Ведущий берёт ящики по очереди; на каждый остальные встают вокруг лицом наружу.
func _run_sweep(living: Array[Marauder], delta: float) -> bool:
	_sweep["left"] = float(_sweep.left) - delta
	var lead: Marauder = squad.leader()
	if lead == null or float(_sweep.left) <= 0.0:
		_cancel_sweep(living)
		return false
	if lead.state in [Marauder.State.SEARCH, Marauder.State.INVESTIGATE]:
		lead.stand_down()
	# прикрытие: остальные — вокруг тела, лицом наружу (кто ещё «ищет» — бой окончен, встаёт на пост)
	if _sweep.has("at"):
		var k: int = 0
		for m: Marauder in living:
			if m == lead:
				continue
			if m.state in [Marauder.State.SEARCH, Marauder.State.INVESTIGATE]:
				m.stand_down()
			if m.state == Marauder.State.PATROL and String(m._order.get("kind", "")) != "hold":
				var ang: float = float(_sweep.turn) + TAU * 0.5 * float(k)
				var out: Vector3 = Vector3(cos(ang), 0.0, sin(ang))
				var at0: Vector3 = _sweep.at
				m.hold_post(at0 + out * float(Balance.RIVALS.cover_m), at0 + out * 30.0, float(_sweep.left))
			k += 1
	if lead.is_looting():
		return true
	var bodies: Array = _sweep.bodies
	var i: int = int(_sweep.i) + 1
	while i < bodies.size() and (not is_instance_valid(bodies[i]) or ((bodies[i] as LootContainer).rolled and (bodies[i] as LootContainer).items.is_empty())):
		i += 1
	_sweep["i"] = i
	if i >= bodies.size() or not lead.order_loot(bodies[i] as LootContainer):
		_cancel_sweep(living)
		return false
	# новое тело — прикрытие переставляется вокруг него
	_sweep["at"] = (bodies[i] as LootContainer).global_position
	_sweep["turn"] = _rng.randf() * TAU
	for m: Marauder in living:
		m.release_post()
	return true


func _cancel_sweep(living: Array[Marauder]) -> void:
	if _sweep.is_empty():
		return
	_sweep = {}
	for m: Marauder in living:
		m.release_post()


func _head_out(living: Array[Marauder]) -> void:
	phase = Phase.EXTRACT
	_wait = 0.0
	_errand = {}
	for m: Marauder in living:
		m.no_loot = true
		m._drop_loot_claim()
		m.patrol_point_provider = _exit_point
	if _exit_ready(living):
		_send(_exit_point())


## Можно ли уйти через выбранный выход; если чего-то не хватает — ставит поручение (ключ, рубильник)
## или просит у RivalRaids другой выход. true — можно идти к выходу прямо сейчас.
func _exit_ready(living: Array[Marauder]) -> bool:
	var tree: SceneTree = living[0].get_tree()
	if exit_key != "" and not exit_key in keys:
		var pickup: KeyPickup = _key_pickup(tree, exit_key)
		if pickup:
			_set_errand({"kind": "key", "node": pickup, "pos": pickup.global_position, "id": exit_key})
		elif not (other_exit.is_valid() and bool(other_exit.call(self))):
			exit_key = ""        # другого выхода нет: уходят, как смогут
		return false
	if exit_switch != "" and Raid.current and not bool(Raid.current.switches.get(exit_switch, false)):
		var sw: PowerSwitch = _switch(tree, exit_switch)
		var dark: bool = String(RaidConditions.current.get("power", "on")) == "off"
		if sw and not dark:
			_set_errand({"kind": "switch", "node": sw, "pos": sw.global_position, "id": exit_switch})
		elif not (other_exit.is_valid() and bool(other_exit.call(self))):
			exit_switch = ""
		return false
	return true


## Дверь заперта на ключ key_id, а ключа у отряда нет (зовёт Door через RivalRaids): идут за ключом,
## если он ещё лежит; иначе ведущий выбирает другое место.
func on_locked_door(key_id: String, redirect: Vector3) -> void:
	if _door_cd > 0.0 or key_id in keys:
		return
	_door_cd = 6.0
	var lead: Marauder = squad.leader()
	if lead == null:
		return
	var pickup: KeyPickup = _key_pickup(lead.get_tree(), key_id)
	if pickup and _errand.is_empty() and phase == Phase.LOOT:
		_set_errand({"kind": "key", "node": pickup, "pos": pickup.global_position, "id": key_id})
		lead.say("Заперто. Ищем ключ.")
	elif redirect != Vector3.INF and _errand.is_empty():
		_send(redirect)


func has_key(key_id: String) -> bool:
	return key_id in keys


## Поручение: pos — куда встать (ближайшая проходимая точка у предмета: рубильник висит на стене,
## ключ может лежать на столе), left — сколько секунд на него есть (не дошли — бросают).
func _set_errand(e: Dictionary) -> void:
	var lead: Marauder = squad.leader()
	if lead:
		e["pos"] = lead._snap(e.pos)
	e["left"] = ERRAND_SEC
	_errand = e
	_send(e.pos)


## Вести отряд по поручению. true — поручение ещё выполняется.
func _run_errand(living: Array[Marauder]) -> bool:
	if _errand.is_empty():
		return false
	var node: Node3D = _errand.get("node") as Node3D
	var gone: bool = not is_instance_valid(node) or (node is KeyPickup and (node as KeyPickup).taken)
	_errand["left"] = float(_errand.get("left", ERRAND_SEC)) - 0.5
	if gone or float(_errand.left) <= 0.0:
		# ключ успели забрать другие или к месту не пройти — поручение снято; выход, которому оно
		# было нужно, меняется на другой
		var for_exit: bool = phase == Phase.EXTRACT
		_errand = {}
		if for_exit and not (other_exit.is_valid() and bool(other_exit.call(self))):
			exit_key = ""
			exit_switch = ""
		_resume(living)
		return false
	var at: Vector3 = _errand.pos
	for m: Marauder in living:
		m.no_loot = true
		m.patrol_point_provider = func() -> Vector3: return at
	var lead: Marauder = squad.leader()
	if lead == null or lead.state in [Marauder.State.COMBAT, Marauder.State.DOWNED, Marauder.State.RESCUE, Marauder.State.RETREAT]:
		return true
	var d: float = Vector2(lead.global_position.x - at.x, lead.global_position.z - at.z).length()
	# дошёл: рядом, или путь кончился поодаль — рубильник и ключ часто стоят там, куда навигация ботов
	# не доходит (в постройке, на площадке): считаем, что дотянулся с конца пути
	if d > ERRAND_REACH and not (d <= ERRAND_FAR and lead._agent.is_navigation_finished()):
		# стоит и смотрит по сторонам, а не идёт — подтолкнуть
		if lead.state == Marauder.State.PATROL and lead.pause_timer > 1.0:
			lead.pause_timer = 0.0
		return true
	match String(_errand.kind):
		"key":
			var pickup := node as KeyPickup
			pickup.taken = true
			Audio.play("key_pickup", pickup.global_position)
			keys.append(String(_errand.id))
			# ключ — в сумке ведущего: выбили отряд — ключ на теле
			lead.pack.append({"id": String(_errand.id), "n": 1})
			lead.say("Ключ у меня")
		"switch":
			var sw := node as PowerSwitch
			if sw.can_use():
				sw._use(0)
	_errand = {}
	_resume(living)
	return false


## После поручения: в фазе грабежа — снова грабить, к выходу — идти к выходу.
func _resume(living: Array[Marauder]) -> void:
	for m: Marauder in living:
		m.no_loot = phase == Phase.EXTRACT
		if phase == Phase.LOOT and _patrol.is_valid():
			m.patrol_point_provider = _patrol
	var lead: Marauder = squad.leader()
	if lead:
		lead.pause_timer = 0.0


## Послать ведущего в точку сейчас (а не когда кончится его пауза).
func _send(at: Vector3) -> void:
	var lead: Marauder = squad.leader()
	if lead:
		lead.pause_timer = 0.0
		lead.investigate_at(at)


static func _key_pickup(tree: SceneTree, key_id: String) -> KeyPickup:
	for n: Node in tree.get_nodes_in_group("key_pickups"):
		var k := n as KeyPickup
		if k and k.key_id == key_id and not k.taken:
			return k
	return null


static func _any_key(tree: SceneTree) -> KeyPickup:
	for n: Node in tree.get_nodes_in_group("key_pickups"):
		var k := n as KeyPickup
		if k and not k.taken:
			return k
	return null


static func _switch(tree: SceneTree, switch_id: String) -> PowerSwitch:
	for n: Node in tree.get_nodes_in_group("interactables"):
		var s := n as PowerSwitch
		if s and s.switch_id == switch_id:
			return s
	return null


## Точка у выхода (с разбросом — отряд не встаёт в одну клетку).
func _exit_point() -> Vector3:
	var a := _rng.randf() * TAU
	return exit_pos + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(0.5, float(Balance.RIVALS.extract_m) * 0.5)


## Ушли: добыча из сумок уходит с ними (и ключи тоже), бойцы исчезают (у всех — спавнер снимает узлы).
func _leave(living: Array[Marauder]) -> void:
	for m: Marauder in living:
		for e: Variant in m.pack:
			if not String((e as Dictionary).get("id", "")) in keys:
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
