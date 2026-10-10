class_name RivalRaids
extends Node
## Чужие отряды в рейде — «другие игроки»: в ТЦ, кроме вас, заходят ещё группы за добычей. Каждая
## входит со своей стороны, обыскивает контейнеры (после неё они пустые), воюет с мародёрами,
## «Периметром», жильцами, другими отрядами и с вами, а набрав своё — уходит через настоящую точку
## эвакуации. Выбили отряд — его сумки ваши. Дизайн — docs/design/rival_raids.md.
##
## Считает хост (узел «Rivals» у уровня): расписание входов, планы отрядов (RivalSquad), память
## состава (RivalRoster). Остальным — только сообщения рации. Бойцы — обычные Marauder фракции
## «rival»: позицию игрока знают только по зрению, шуму и окрику своего отряда.
##
## Работает в настоящем рейде (Profile.pending_raid, не тестовый профиль). Запуск уровня напрямую и
## тесты — без чужих отрядов, если не взвести RivalRaids.forced.

## Выключить совсем (тесты других систем) / включить и без настоящего рейда (тест, консоль).
static var enabled: bool = true
static var forced: bool = false
static var current: RivalRaids

var level: Node
## Все отряды этого рейда (и ушедшие, и выбитые) — для итога и тестов.
var squads: Array[RivalSquad] = []
## Ждут входа: [{t, record}] по возрастанию t.
var _queue: Array = []
var _t: float = 0.0
var _tick: float = 0.0
var _ready_host: bool = false
var _rng := RandomNumberGenerator.new()


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null


func _ready() -> void:
	level = get_parent()
	_rng.randomize()


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


static func active() -> bool:
	if forced:
		return true
	return enabled and Profile.pending_raid and not Profile.path.contains("_test")


func _process(delta: float) -> void:
	if not _is_host():
		return
	if not _ready_host:
		# уровень расставил мародёров — навигация готова, можно планировать входы
		if int(level.get("_marauders_spawned")) <= 0:
			return
		_ready_host = true
		if active():
			_plan()
	_t += delta
	while not _queue.is_empty() and float(_queue[0].t) <= _t:
		var next: Dictionary = _queue.pop_front()
		enter(next.record)
	_tick -= delta
	if _tick > 0.0:
		return
	_tick = 0.5
	for s: RivalSquad in squads:
		var changed: int = s.tick(0.5)
		if changed >= 0:
			_on_phase(s, changed)


## Расписание рейда: сколько отрядов и когда входят.
func _plan() -> void:
	var cfg: Dictionary = Balance.RIVALS
	var n := _rng.randi_range(int(cfg.squads[0]), int(cfg.squads[1]))
	for record: Variant in RivalRoster.pick(n, _rng):
		_queue.append({"t": _rng.randf_range(float(cfg.enter_sec[0]), float(cfg.enter_sec[1])), "record": record})
	_queue.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.t) < float(b.t))
	print("rivals: отрядов %d, входы %s" % [_queue.size(), _queue.map(func(q: Dictionary) -> String: return "%s@%d" % [q.record.name, int(q.t)])])


## Отряд входит в рейд: у дальней от игроков точки эвакуации (не нашлось — в дальней комнате),
## выход — другая точка. at / exit_at — задать явно (тесты, консоль). Возвращает отряд или null.
func enter(record: Dictionary, at: Vector3 = Vector3.INF, exit_at: Vector3 = Vector3.INF) -> RivalSquad:
	if not _is_host() or not level.has_method("spawn_squad"):
		return null
	var exits: Array = _exits()
	if at == Vector3.INF:
		at = _entry_point(exits)
	if at == Vector3.INF:
		print("rivals: «%s» — некуда войти (игроки рядом со всеми входами)" % record.get("name", "?"))
		return null
	var exit_name := "выход"
	if exit_at == Vector3.INF:
		var out: Dictionary = _pick_exit(exits, at)
		exit_at = out.pos
		exit_name = out.name
	var style: Dictionary = RivalRoster.style(String(record.get("style", "assault")))
	var archs: Array = (style.get("archs", ["rival", "rival"]) as Array).duplicate()
	var cfg: Dictionary = Balance.RIVALS
	archs.resize(clampi(_rng.randi_range(int(cfg.size[0]), int(cfg.size[1])), 1, archs.size()))
	var sq: Squad = level.call("spawn_squad", at, archs, {}) as Squad
	if sq == null or sq.members.is_empty():
		return null
	var s := RivalSquad.new()
	s.setup(record, sq, exit_at, exit_name, _rng)
	squads.append(s)
	RivalRoster.note(s.id, "raids")
	print("rivals: вошли «%s» (%d) у %s, выход «%s», грабят %d с, хватит %d" % [s.name, sq.members.size(), at.round(), exit_name, int(s.loot_budget), s.pack_goal])
	_radio("В ТЦ зашла ещё одна группа — «%s»." % s.name)
	return s


func _on_phase(s: RivalSquad, phase: int) -> void:
	match phase:
		RivalSquad.Phase.EXTRACT:
			print("rivals: «%s» идут к выходу «%s», в сумках %d" % [s.name, s.exit_name, s.packed()])
		RivalSquad.Phase.OUT:
			RivalRoster.note(s.id, "out")
			RivalRoster.note(s.id, "loot", s.loot_value)
			print("rivals: «%s» ушли через «%s», вынесли на %d" % [s.name, s.exit_name, s.loot_value])
			_radio("«%s» вышли через %s. %s" % [s.name, s.exit_name, "С добычей." if s.loot_value > 0 else "Пустые."])
		RivalSquad.Phase.WIPED:
			RivalRoster.note(s.id, "wiped")
			var by_you: bool = s.killed_by_players > s.killed_by_ai
			if by_you:
				RivalRoster.note(s.id, "wiped_by_you")
			print("rivals: «%s» выбиты (%s), игроки %d / остальные %d" % [s.name, "игроками" if by_you else "не игроками", s.killed_by_players, s.killed_by_ai])
			if not by_you:
				_radio("«%s» больше не отвечают." % s.name)


## Точки эвакуации уровня: [{pos, name}].
func _exits() -> Array:
	var out: Array = []
	for n: Node in get_tree().get_nodes_in_group("extractions"):
		var e := n as ExtractionPoint
		if e and e.is_inside_tree():
			out.append({"pos": e.global_position, "name": e.display_name if e.display_name != "" else "выход"})
	return out


## Где войти: точка эвакуации, самая дальняя от игроков, но не ближе spawn_min_m; нет таких —
## случайная комната на таком же удалении; игроки везде рядом — INF (вход откладывается).
func _entry_point(exits: Array) -> Vector3:
	var min_d: float = float(Balance.RIVALS.spawn_min_m)
	var best: Vector3 = Vector3.INF
	var best_d: float = min_d
	for e: Dictionary in exits:
		var d: float = _players_distance(e.pos) + _rng.randf() * 15.0
		if d > best_d:
			best = e.pos
			best_d = d
	if best != Vector3.INF:
		return best
	for i in range(12):
		var p: Vector3 = level.call("_room_point")
		if _players_distance(p) >= min_d:
			return p
	return Vector3.INF


## Куда уйти: не там, где вошли, если есть выбор.
func _pick_exit(exits: Array, entry: Vector3) -> Dictionary:
	var options: Array = exits.filter(func(e: Dictionary) -> bool: return (e.pos as Vector3).distance_to(entry) > 10.0)
	if options.is_empty():
		options = exits
	if options.is_empty():
		return {"pos": entry, "name": "выход"}
	return options[_rng.randi_range(0, options.size() - 1)]


func _players_distance(p: Vector3) -> float:
	var best: float = INF
	for n: Node in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl and pl.is_alive():
			best = minf(best, pl.global_position.distance_to(p))
	return best


## Рация: слышат все в рейде, но не каждое событие (Balance.RIVALS.radio_chance) — чужие группы
## не отчитываются, это обрывки эфира.
func _radio(text: String) -> void:
	if _rng.randf() > float(Balance.RIVALS.radio_chance):
		return
	if Net.is_networked():
		_rpc_radio.rpc("Рация: " + text)
	else:
		_rpc_radio("Рация: " + text)


@rpc("authority", "call_local", "reliable")
func _rpc_radio(text: String) -> void:
	if Raid.current:
		Raid.current.notify(text)


## Итог по чужим отрядам для экрана рейда и тестов: [{name, phase, loot, by_you}].
func results() -> Array:
	var out: Array = []
	for s: RivalSquad in squads:
		out.append({"name": s.name, "phase": int(s.phase), "loot": s.loot_value, "by_you": s.killed_by_players, "alive": s.alive().size()})
	return out
