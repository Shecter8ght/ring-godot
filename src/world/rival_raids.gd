class_name RivalRaids
extends Node
## Чужие отряды в рейде — «другие игроки»: в район, кроме вас, заходят ещё группы за добычей. Каждая
## входит со своей стороны, обыскивает контейнеры (после неё они пустые), воюет с мародёрами,
## «Периметром», жильцами, другими отрядами и с вами, а набрав своё — уходит через настоящую точку
## эвакуации. Выбили отряд — его сумки ваши. Дизайн — docs/design/rival_raids.md.
##
## Считает хост (узел «Rivals» у уровня): расписание входов, планы отрядов (RivalSquad), память
## состава (RivalRoster). Остальным — сообщения рации и временные метки для плейтеста. Бойцы — Marauder фракции
## «rival»: позицию игрока знают только по зрению, шуму и окрику своего отряда.
##
## Работает в настоящем рейде (Profile.pending_raid, не тестовый профиль). Запуск уровня напрямую и
## тесты — без чужих отрядов, если не взвести RivalRaids.forced.

## Выключить совсем (тесты других систем) / включить и без настоящего рейда (тест, консоль).
static var enabled: bool = true
static var forced: bool = false
static var current: RivalRaids

var level: Node
var sector_id: String = ""
## Все отряды этого рейда (и ушедшие, и выбитые) — для итога и тестов.
var squads: Array[RivalSquad] = []
## Снимок для временных меток в рейде, обновляется у всех игроков.
var map_marks: Array = []
## Ждут входа: [{t, record}] по возрастанию t.
var _queue: Array = []
## Очерёдность чужих групп на «Проспекте»: каждый позывной заходит один раз за рейд.
var _prospekt_roster: Array = []
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
	Net.scenes_changed.connect(_publish_map_marks)


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
	if sector_id == "prospekt":
		_advance_prospekt_arrivals()
	else:
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
	_publish_map_marks()


## Расписание рейда: сколько отрядов и когда входят.
func _plan() -> void:
	var cfg: Dictionary = Balance.RIVALS
	if sector_id == "prospekt":
		_prospekt_roster = RivalRoster.pick(RivalRoster.squads().size(), _rng)
		_plan_prospekt_arrival(cfg.enter_sec)
		return
	# сколько отрядов — под число игроков
	var by_party: Array = cfg.squads[AIPopulation.party_size() - 1]
	var n := _rng.randi_range(int(by_party[0]), int(by_party[1]))
	for record: Variant in RivalRoster.pick(n, _rng):
		_queue.append({"t": _rng.randf_range(float(cfg.enter_sec[0]), float(cfg.enter_sec[1])), "record": record})
	_queue.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.t) < float(b.t))
	print("rivals: отрядов %d, входы %s" % [_queue.size(), _queue.map(func(q: Dictionary) -> String: return "%s@%d" % [q.record.name, int(q.t)])])


func _plan_prospekt_arrival(window: Array) -> void:
	if not _prospekt_roster.is_empty():
		_queue.append({"t": _t + _rng.randf_range(float(window[0]), float(window[1])),
			"record": _prospekt_roster.pop_front()})


func _active_squads() -> Array[RivalSquad]:
	return squads.filter(func(s: RivalSquad) -> bool:
		return s.phase == RivalSquad.Phase.LOOT or s.phase == RivalSquad.Phase.EXTRACT)


func _advance_prospekt_arrivals() -> void:
	if _queue.is_empty() or float(_queue[0].t) > _t:
		return
	if Raid.current and Raid.current.over:
		_queue.clear()
		return
	var cfg: Dictionary = Balance.PROSPEKT_RIVALS
	var next: Dictionary = _queue[0]
	if _active_squads().size() >= int(cfg.max_active) or enter(next.record) == null:
		next["t"] = _t + float(cfg.retry_sec)
		return
	_queue.pop_front()
	_plan_prospekt_arrival(cfg.interval_sec)


## Отряд входит с края карты на «Проспекте» или у дальней точки эвакуации на других картах.
## at / exit_at — задать явно (тесты, консоль). Возвращает отряд или null.
func enter(record: Dictionary, at: Vector3 = Vector3.INF, exit_at: Vector3 = Vector3.INF) -> RivalSquad:
	if not _is_host() or not level.has_method("spawn_squad"):
		return null
	var exits: Array = _exits()
	var style: Dictionary = RivalRoster.style(String(record.get("style", "assault")))
	var archs: Array = (style.get("archs", ["rival", "rival"]) as Array).duplicate()
	var cfg: Dictionary = Balance.RIVALS
	var prospekt := sector_id == "prospekt"
	var size := _prospekt_group_size() if prospekt else _rng.randi_range(int(cfg.size[0]), int(cfg.size[1]))
	archs.resize(clampi(size, 1, archs.size()))
	var sq: Squad
	if prospekt and at == Vector3.INF:
		sq = _spawn_prospekt_squad(archs)
	else:
		if at == Vector3.INF:
			at = _entry_point(exits)
		if at != Vector3.INF:
			sq = level.call("spawn_squad", at, archs, {}) as Squad
	if sq == null or sq.members.is_empty():
		print("rivals: «%s» — вход не найден" % record.get("name", "?"))
		return null
	if at == Vector3.INF:
		at = sq.members[0].global_position
	if prospekt:
		var patrol := _prospekt_patrol(at)
		if patrol.is_valid():
			for m: Marauder in sq.members:
				m.patrol_point_provider = patrol
	var exit: Dictionary = {"pos": exit_at, "name": "выход"}
	if exit_at == Vector3.INF:
		exit = _pick_exit(exits, at)
	else:
		# выход задан точкой: если это точка эвакуации уровня — с её условиями (рубильник, ключ)
		for e: Dictionary in exits:
			if (e.pos as Vector3).distance_to(exit_at) < 1.0:
				exit = e
	var s := RivalSquad.new()
	s.setup(record, sq, exit, _rng)
	s.other_exit = _other_exit
	squads.append(s)
	RivalRoster.note(s.id, "raids")
	print("rivals: вошли «%s» (%d) у %s, выход «%s», грабят %d с, хватит %d" % [s.name, sq.members.size(), at.round(), s.exit_name, int(s.loot_budget), s.pack_goal])
	_radio("%s зашла ещё одна группа — «%s»." % ["На «Проспект»" if prospekt else "В ТЦ", s.name])
	_publish_map_marks()
	return s


func _prospekt_group_size() -> int:
	var cfg: Dictionary = Balance.PROSPEKT_RIVALS
	var weights: Array = cfg.solo_size_weights if AIPopulation.party_size() == 1 else cfg.coop_size_weights
	return 1 + _rng.rand_weighted(PackedFloat32Array(weights))


func _spawn_prospekt_squad(archs: Array) -> Squad:
	var pop := level.get_node_or_null("Population") as AIPopulation
	if pop == null or int(level.get("_marauders_spawned")) <= 0:
		return null
	var entries := pop.arrival_points()
	var opts := {"can_spawn": _hidden_from_players, "spread_inward": true}
	while not entries.is_empty():
		var at: Vector3 = entries.pop_at(_rng.randi_range(0, entries.size() - 1))
		if not _hidden_from_players(at):
			continue
		var sq := level.call("spawn_squad", at, archs, opts) as Squad
		if sq and not sq.members.is_empty():
			return sq
	return null


func _hidden_from_players(at: Vector3) -> bool:
	var space := (level as Node3D).get_world_3d().direct_space_state
	var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR
	for n: Node in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl == null or not pl.is_alive():
			continue
		if pl.global_position.distance_to(at) < float(Balance.RIVALS.spawn_min_m):
			return false
		var eye := pl.eye_position()
		for height: float in [Marauder.EYE_HEIGHT, Marauder.CROUCH_EYE, 0.0]:
			var q := PhysicsRayQueryParameters3D.create(eye, at + Vector3.UP * height, mask)
			if space.intersect_ray(q).is_empty():
				return false
	return true


## Между обысками отряд выбирает точки ближайшего к месту входа уличного маршрута.
func _prospekt_patrol(at: Vector3) -> Callable:
	var route_points := PackedVector3Array()
	var best := INF
	for n: Node in get_tree().get_nodes_in_group("ai_routes"):
		var route := n as AIRoute
		if route == null:
			continue
		var points := route.points()
		for p: Vector3 in points:
			var distance := at.distance_squared_to(p)
			if distance < best:
				best = distance
				route_points = points
	if route_points.is_empty():
		return Callable()
	return func() -> Vector3: return route_points[_rng.randi_range(0, route_points.size() - 1)]


func _publish_map_marks() -> void:
	if not _is_host():
		return
	var marks: Array = []
	for s: RivalSquad in squads:
		if s.phase in [RivalSquad.Phase.OUT, RivalSquad.Phase.WIPED]:
			continue
		var leader := s.squad.leader()
		if leader == null:
			continue
		var style_name := String(s.style.get("name", ""))
		if bool(s.style.get("flee", false)):
			style_name = "осторожные"
		marks.append({"pos": leader.global_position, "name": s.name, "style": style_name,
			"leaving": s.phase == RivalSquad.Phase.EXTRACT})
	if not marks.is_empty() or not map_marks.is_empty():
		if Net.is_networked():
			Net.broadcast_scene(self, &"_sync_map_marks", [marks])
		else:
			map_marks = marks


@rpc("authority", "call_local", "reliable")
func _sync_map_marks(marks: Array) -> void:
	map_marks = marks


static func mark_color(mark: Dictionary) -> Color:
	match String(mark.style):
		"осторожные": return Color("dcadff")
		"жадные": return Color("ffd36e")
		"стрелки": return Color("ff9db6")
	return Color("ffa36d")


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
			_radio("«%s» больше не отвечают." % s.name)


## Точки эвакуации уровня: [{pos, name, switch, key}] — с тем, что нужно, чтобы через них уйти.
func _exits() -> Array:
	var out: Array = []
	for n: Node in get_tree().get_nodes_in_group("extractions"):
		var e := n as ExtractionPoint
		if e and e.is_inside_tree():
			out.append({"pos": e.global_position, "name": e.display_name if e.display_name != "" else "выход",
				"switch": e.required_switch, "key": e.required_key})
	return out


## Выход отряда стал недоступен (ключ унесли, питания нет): дать другой — без условий, а если таких
## нет, любой другой. true — выход сменён.
func _other_exit(s: RivalSquad) -> bool:
	var options: Array = _exits().filter(func(e: Dictionary) -> bool: return (e.pos as Vector3).distance_to(s.exit_pos) > 1.0)
	var free: Array = options.filter(func(e: Dictionary) -> bool: return String(e.key) == "" and String(e.switch) == "")
	if not free.is_empty():
		options = free
	if options.is_empty():
		return false
	s.set_exit(options[_rng.randi_range(0, options.size() - 1)])
	print("rivals: «%s» меняют выход на «%s»" % [s.name, s.exit_name])
	return true


## Отряд бойца (хост); null — не из чужих отрядов.
func squad_of(m: Marauder) -> RivalSquad:
	for s: RivalSquad in squads:
		if s.squad == m.squad:
			return s
	return null


## Зовёт Door: можно ли бойцу открыть дверь, запертую на ключ key_id. Чужим отрядам — только с
## ключом (как игрокам); без ключа отряд идёт его искать или выбирает другое место. Остальным
## ботам двери открыты, как раньше.
static func may_open(m: Marauder, key_id: String) -> bool:
	if key_id == "" or m.faction != "rival" or current == null:
		return true
	var s: RivalSquad = current.squad_of(m)
	if s == null or s.has_key(key_id):
		return true
	s.on_locked_door(key_id, current.level.call("_room_point") if current.level.has_method("_room_point") else Vector3.INF)
	return false


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


## Рация: сообщения о чужих группах получают все, кто в рейде (решение владельца, 2026-10-10).
func _radio(text: String) -> void:
	Net.broadcast_scene(self, &"_rpc_radio", ["Рация: " + text])


@rpc("authority", "call_local", "reliable")
func _rpc_radio(text: String) -> void:
	var voiced := Audio.play_voice_line("rival_radio", text.trim_prefix("Рация: "))
	if not voiced and text.begins_with("Рация: На «Проспект»"):
		Audio.play_ui("radio")
	if Raid.current:
		Raid.current.notify(text)


## Итог по чужим отрядам для экрана рейда и тестов: [{name, phase, loot, by_you}].
func results() -> Array:
	var out: Array = []
	for s: RivalSquad in squads:
		out.append({"name": s.name, "phase": int(s.phase), "loot": s.loot_value, "by_you": s.killed_by_players, "alive": s.alive().size()})
	return out
