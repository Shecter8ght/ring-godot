extends Node
## Кооп на троих: хост и два клиента — каждый своим процессом, роль — аргументом после «--»:
##   godot --headless res://tools/coop_raid_test.tscn -- host
##   godot --headless res://tools/coop_raid_test.tscn -- c1      (через 3 с)
##   godot --headless res://tools/coop_raid_test.tscn -- c2      (ещё через 3 с)
## c1 приходит как из главного меню («Собрание»), c2 — из своего убежища («подключиться по IP»).
## Проверки у каждого: в убежище видны оба других и видно, как они ходят; в рейде — то же, плюс
## выстрелы других видны (трассеры у стрелявшего), дверь, открытая клиентом, открыта у всех;
## генератор ТЦ встал (хост) — у всех стоит, c2 чинит в мастерской — у всех снова весь свет;
## эвакуация группой: хост и c1 в зоне, c2 нет — у всех общий отсчёт и «ждём c2», отсчёт кончился —
## хост и c1 ушли, c2 не успел (у каждого своя хроника: «вышел» / «не успел»).
## Мародёров хост убирает — чтобы никого не подстрелили посреди проверок.

const ROLES := ["host", "c1", "c2"]
## Во сколько секунд от готовности рейда (все трое на месте) кто что делает.
const RAID_PLAN := {
	"host": {"move": 3.0, "fire": 6.0, "gen_fail": 24.0},
	"c1": {"move": 9.0, "fire": 12.0, "door": 15.0},
	"c2": {"move": 18.0, "fire": 21.0, "unload": 24.0, "gen_fix": 27.0},
}
const RAID_CHECK_AT := 42.0
const HIDEOUT_MOVE_AT := {"host": 5.0, "c1": 3.0, "c2": 3.0}

var _role: String = "host"
var _fails: int = 0
## Сцена сейчас: "menu" / "hideout" / "raid" — трекинг движения по фазам.
var _phase: String = ""
## peer → [первая позиция, наибольший сдвиг от неё] в текущей фазе.
var _track: Dictionary = {}
var _moved: Dictionary = {"hideout": {}, "raid": {}}
## Сколько трассеров чужих выстрелов видно: peer стрелявшего → число.
var _remote_tracers: Dictionary = {}
## Свои трассеры — что сам действительно выстрелил.
var _own_tracers: int = 0
var _door_path: String = ""
## Видел ли генератор стоящим (авария хоста дошла).
var _saw_gen_down: bool = false


func _ready() -> void:
	if name == "CoopRaidRunner":
		_run()
		return
	var runner := Node.new()
	runner.name = "CoopRaidRunner"
	runner.set_script(get_script())
	get_tree().root.add_child.call_deferred(runner)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if not args.is_empty() and String(args[0]) in ROLES:
		_role = String(args[0])
	Profile.use_file("user://profile_coop3_%s.json" % _role, true)
	Profile.ensure()
	_gear_up()
	get_tree().node_added.connect(_on_node_added)
	match _role:
		"host":
			await _host()
		_:
			await _client()
	print("coop_raid[%s]: провалено %d" % [_role, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _host() -> void:
	_check("сервер поднят", Net.host("Хост") == "", "")
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _wait(func() -> bool: return _in_hideout() and _players().size() == 3, 40.0)
	_check("убежище: вижу обоих", _players().size() == 3, str(Net.peer_scene))
	await _hideout_moves()
	_check_moved("hideout")
	Net.start_level.rpc(Floors.scene(Profile.floor), Profile.next_conditions)
	await _raid()


func _client() -> void:
	if _role == "c1":
		# как из главного меню: «Собрание» → подключился → в убежище
		Net.enter_scene("menu")
		_check("подключение", Net.join("127.0.0.1", "Друг 1") == "", "")
		await Net.joined
		get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	else:
		# как из своего убежища: сидел один, подключился — убежище перезагрузилось
		get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
		await _wait(_in_hideout, 20.0)
		await get_tree().create_timer(1.0).timeout
		_check("подключение", Net.join("127.0.0.1", "Друг 2") == "", "")
		await Net.joined
		get_tree().reload_current_scene()
	await get_tree().create_timer(0.5).timeout
	await _wait(func() -> bool: return _in_hideout() and _players().size() == 3, 20.0)
	_check("убежище: вижу хоста и второго друга", _in_hideout() and _players().size() == 3, "игроков %d, сцены %s" % [_players().size(), str(Net.peer_scene)])
	await _hideout_moves()
	# рейд начинает хост
	await _wait(func() -> bool: return _phase == "raid", 60.0)
	_check_moved("hideout")
	await _raid()


## В убежище каждый проходит вперёд в своё время; остальные видят сдвиг.
func _hideout_moves() -> void:
	await get_tree().create_timer(float(HIDEOUT_MOVE_AT[_role])).timeout
	await _walk(1.2)
	# ждать, пока пройдут все (хост начинает рейд позже всех проходов)
	await get_tree().create_timer(10.0 if _role == "host" else 0.0).timeout


func _raid() -> void:
	await _wait(func() -> bool: return Raid.current != null and Raid.current.local_player() != null and _players().size() == 3, 60.0)
	_check("рейд: все трое на месте", _players().size() == 3, "игроков %d, сцены %s" % [_players().size(), str(Net.peer_scene)])
	var t0 := Time.get_ticks_msec()
	var plan: Dictionary = RAID_PLAN[_role]
	var done: Dictionary = {}
	while _since(t0) < RAID_CHECK_AT:
		if _role == "host":
			_clear_marauders()
		for what in plan:
			if not done.has(what) and _since(t0) >= float(plan[what]):
				done[what] = true
				match String(what):
					"move":
						await _walk(1.5)
					"fire":
						await _shoot(3)
					"door":
						await _open_door()
					"gen_fail":
						RaidEvents.current.trigger("generator")
					"gen_fix":
						await _fix_generator()
					"unload":
						await _unload_to_buffer()
		if RaidEvents.current and RaidEvents.current.generator_down:
			_saw_gen_down = true
		await get_tree().process_frame
	_check_moved("raid")
	_check("рейд: сам выстрелил", _own_tracers > 0, "своих трассеров %d" % _own_tracers)
	for r in ROLES:
		if r == _role:
			continue
		var peer := _peer_of_role(r)
		_check("рейд: выстрелы %s видно" % r, int(_remote_tracers.get(peer, 0)) > 0, "трассеров %d" % int(_remote_tracers.get(peer, 0)))
	# дверь открыл c1 — у всех открыта
	var door := _door_by_path(_door_path) if _door_path != "" else _test_door()
	_check("рейд: дверь, открытая c1, открыта", door != null and door.is_open, str(door.get_path()) if door else "двери нет")
	_check("рейд: генератор встал — видно у меня", _saw_gen_down, "")
	_check("рейд: c2 починил генератор — весь свет", RaidEvents.current != null and not RaidEvents.current.generator_down and String(RaidConditions.current.power) == "on", String(RaidConditions.current.power))
	await _evac()
	# хост уходит последним — иначе клиентов выкинет в убежище посреди проверок
	await get_tree().create_timer(8.0 if _role == "host" else 2.0).timeout


## Эвакуация группой: хост и c1 встают в зону «Автобусная остановка», c2 остаётся где был.
func _evac() -> void:
	var ext := get_tree().current_scene.get_node_or_null("Extractions/Bus") as ExtractionPoint
	var me := Raid.current.local_player()
	if ext == null or me == null:
		_check("эвакуация: точка Bus", false, "")
		return
	var c2 := _peer_of_role("c2")
	if _role != "c2":
		me.global_position = ext.global_position + Vector3(1.0 if _role == "host" else -1.0, 0.3, 0.0)
	await get_tree().create_timer(4.0).timeout
	var r := Raid.current
	_check("эвакуация: общий отсчёт идёт, ждём c2", r.evac_left > 0.0 and r.evac_left < Balance.EXTRACT_GROUP_SEC and c2 in r.evac_wait,
		"осталось %.1f, ждём %s" % [r.evac_left, str(r.evac_wait)])
	# ждать 3 минуты тест не будет: хост укорачивает отсчёт (чуть позже — клиенты отстают на пару секунд)
	if _role == "host":
		await get_tree().create_timer(3.0).timeout
		r.evac_left = 1.5
	await _wait(func() -> bool: return r.over, 12.0)
	_check("эвакуация: хост и c1 ушли, c2 не успел", r.is_extracted(_peer_of_role("host")) and r.is_extracted(_peer_of_role("c1")) and r.stranded.has(c2) and not r.is_extracted(c2),
		"%s / %s" % [str(r.extracted), str(r.stranded)])
	await get_tree().create_timer(2.0).timeout
	var want := "stranded" if _role == "c2" else "extract"
	_check("эвакуация: моя хроника — «%s»" % want, r.chronicle != null and r.analytics.outcome == want, "%s: %s" % [r.analytics.outcome, r.chronicle.verdict if r.chronicle else "нет"])


## Новый профиль держит всё в тайнике: стволы — в руки, патроны и магазины — в рюкзак.
func _gear_up() -> void:
	var guard := 0
	var i := 0
	while i < Profile.stash.size() and guard < 200:
		guard += 1
		var id := String(Profile.stash[i].id)
		var moved := false
		if WeaponDb.is_weapon(id):
			moved = Profile.equip_from_stash(i)
		elif id.begins_with("ammo_") or id.begins_with("mag_"):
			moved = Profile.stash_to_backpack(i, int(Profile.stash[i].n))
		i = 0 if moved else i + 1
	_check("снаряжение: стволы надеты", Profile.equipment.has("primary") or Profile.equipment.has("pistol"), str(Profile.equipment.keys()))


func _walk(sec: float) -> void:
	Input.action_press("move_forward")
	await get_tree().create_timer(sec).timeout
	Input.action_release("move_forward")


## Стрельба у игрока — в физическом кадре: «только что нажато» видно, если нажать в его начале.
func _shoot(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame
		Input.action_press("fire")
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_release("fire")
		await get_tree().create_timer(0.6).timeout


## c1 встаёт у двери (одной и той же у всех — по пути в дереве) и жмёт F.
func _open_door() -> void:
	var door := _test_door()
	var me := Raid.current.local_player() if Raid.current else null
	if door == null or me == null:
		_check("c1: дверь найдена", false, "")
		return
	_door_path = str(door.get_path())
	me.global_position = door.to_global(Vector3(door.width * 0.5, 0.1, 0.8))
	await get_tree().create_timer(0.5).timeout
	# дверь ловит F в _process — нажать в начале кадра
	await get_tree().process_frame
	Input.action_press("interact")
	await get_tree().process_frame
	await get_tree().process_frame
	Input.action_release("interact")
	await get_tree().create_timer(1.5).timeout
	_check("c1: дверь открылась у меня", door.is_open, _door_path)


## c2: разрядить магазин из рюкзака в буфер (просьба хосту), потом буфер — обратно в рюкзак.
func _unload_to_buffer() -> void:
	var inv := Raid.current.local_player().inventory
	var idx := -1
	for i in range(inv.items.size()):
		if (inv.items[i] as Dictionary).has("rounds") and int(inv.items[i].rounds) > 0:
			idx = i
			break
	if idx < 0:
		_check("c2: есть снаряжённый магазин", false, str(inv.items))
		return
	Raid.current.request_unload("backpack", idx, "buffer")
	await get_tree().create_timer(1.0).timeout
	_check("c2: разрядил магазин в буфер через хост", not inv.buffer.is_empty() and not WeaponDb.ammo(String(inv.buffer[0].id)).is_empty(), str(inv.buffer))
	Raid.current.request_flush_buffer()
	await get_tree().create_timer(1.0).timeout
	_check("c2: буфер — обратно в рюкзак", inv.buffer.is_empty(), str(inv.buffer))


## c2 идёт к щитку генератора в мастерской и чинит (просьба хосту, как по F); ждёт ремонт.
func _fix_generator() -> void:
	var gen := RaidEvents.current.generator() if RaidEvents.current else null
	var me := Raid.current.local_player() if Raid.current else null
	if gen == null or me == null:
		_check("c2: генератор найден", false, "")
		return
	me.global_position = gen.to_global(Vector3(-0.85, 0.1, -1.3))
	await get_tree().create_timer(0.5).timeout
	_check("c2: генератор стоит — можно чинить", gen.can_use(), gen.prompt())
	gen.request_use()
	await get_tree().create_timer(float(Balance.RAID_EVENTS.repair_sec) + 1.5).timeout


## Первая незапертая дверь самого ТЦ (кольцо собирает SectorBuilder, у всех peer одинаково) —
## у них раньше были автоимена, и просьба клиента открыть не находила дверь у хоста.
func _test_door() -> Door:
	var scene := get_tree().current_scene
	if scene == null:
		return null
	var doors: Array[Node] = scene.find_children("*", "Node3D", true, false).filter(func(n: Node) -> bool: return n is Door and n.get_parent().name == "Doors")
	doors.sort_custom(func(a: Node, b: Node) -> bool: return str(a.get_path()) < str(b.get_path()))
	for d in doors:
		if (d as Door).required_key == "":
			return d as Door
	return null


func _door_by_path(p: String) -> Door:
	return get_tree().root.get_node_or_null(p) as Door


func _clear_marauders() -> void:
	var root := get_tree().current_scene.get_node_or_null("Marauders") if get_tree().current_scene else null
	if root:
		for m in root.get_children():
			if not m.is_queued_for_deletion():
				m.queue_free()


func _process(_delta: float) -> void:
	var key := String(Net.peer_scene.get(multiplayer.get_unique_id(), ""))
	if key != _phase:
		_phase = key
		_track.clear()
	if not _moved.has(_phase):
		return
	for peer in _players():
		var pl: Player = _players()[peer]
		if pl.is_local():
			continue
		if not _track.has(peer):
			_track[peer] = [pl.global_position, 0.0]
		var d := pl.global_position.distance_to(_track[peer][0])
		_track[peer][1] = maxf(float(_track[peer][1]), d)
		var m: Dictionary = _moved[_phase]
		m[peer] = maxf(float(m.get(peer, 0.0)), d)


func _check_moved(phase: String) -> void:
	for r in ROLES:
		if r == _role:
			continue
		var peer := _peer_of_role(r)
		var d := float((_moved[phase] as Dictionary).get(peer, 0.0))
		_check("%s: вижу, как %s ходит" % [phase, r], d > 0.5, "сдвиг %.2f м" % d)


## Трассер чужого выстрела: начало — у дула стрелявшего (ближайший игрок в 3 м).
func _on_node_added(n: Node) -> void:
	if not n is Tracer:
		return
	_attribute_tracer.call_deferred(n)


func _attribute_tracer(n: Node) -> void:
	if not is_instance_valid(n):
		return
	var im := (n as Tracer).mesh as ImmediateMesh
	if im == null or im.get_surface_count() == 0:
		return
	var verts: PackedVector3Array = im.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	if verts.is_empty():
		return
	var best := 0
	var best_d := 3.0
	for peer in _players():
		var pl: Player = _players()[peer]
		var d := (pl.global_position + Vector3.UP * 1.3).distance_to(verts[0])
		if d < best_d:
			best_d = d
			best = int(peer)
	if best == multiplayer.get_unique_id():
		_own_tracers += 1
	elif best != 0:
		_remote_tracers[best] = int(_remote_tracers.get(best, 0)) + 1


## peer_id по роли: хост — 1, клиенты — по имени, которое они назвали.
func _peer_of_role(r: String) -> int:
	if r == "host":
		return 1
	var want := "Друг 1" if r == "c1" else "Друг 2"
	for id in Net.player_names:
		if String(Net.player_names[id]) == want:
			return int(id)
	return -1


func _players() -> Dictionary:
	var out: Dictionary = {}
	for p in get_tree().get_nodes_in_group("players"):
		if is_instance_valid(p) and not p.is_queued_for_deletion():
			out[(p as Player).peer_id] = p
	return out


func _in_hideout() -> bool:
	return get_tree().current_scene != null and get_tree().current_scene.scene_file_path == Balance.HIDEOUT_SCENE


func _since(t0: int) -> float:
	return float(Time.get_ticks_msec() - t0) / 1000.0


func _wait(cond: Callable, limit: float) -> void:
	var t := 0.0
	while not bool(cond.call()) and t < limit:
		await get_tree().process_frame
		t += get_process_delta_time()


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
