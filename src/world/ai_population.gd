class_name AIPopulation
extends Node
## Население рейда слоями (docs/design/enemy_population.md): в начале рейда — гарнизоны постов
## (AIPost), патрули по маршрутам (AIRoute) и снайпер в гнезде (AINest); по ходу рейда — подход новых
## групп с краёв карты (AIArrival). Число групп — под число игроков (Balance.AI_POPULATION.party_k).
##
## Считает хост (узел «Population» у уровня); бойцы — обычные Marauder, клиентам их реплицирует спавнер
## уровня (SectorLevel.spawn_marauder). Точек на карте нет — уровень спавнит по-старому
## (MARAUDER_COUNT по ai_spawn_points), а этот узел ничего не делает.

static var current: AIPopulation
## Тесты: считать, что игроков столько (0 — по рейду).
static var party_override: int = 0

## Данные сектора (ключ "ai" переопределяет Balance.AI_POPULATION).
var definition: Dictionary = {}
var level: Node
## Расставлено ли по слоям (на карте есть точки) — тогда работает и подход.
var layered: bool = false
## Что расставлено: {posts: [имена], routes: [...], nests: [...], arrivals: [{t, at, n}], marauders: N}.
var placed: Dictionary = {}
## Ждут входа: секунды от начала рейда по возрастанию.
var _arrive_queue: Array[float] = []
var _t: float = 0.0
var _retry_t: float = 0.0
var _last_shot_pos: Vector3 = Vector3.INF
var _last_shot_ms: int = -1000000
var _rng := RandomNumberGenerator.new()


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null


func _ready() -> void:
	level = get_parent()
	_rng.randomize()
	NoiseBus.noise.connect(_on_noise)


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


## Настройки населения: Balance + переопределение карты ("ai" в данных сектора).
func cfg() -> Dictionary:
	var out: Dictionary = Balance.AI_POPULATION.duplicate(true)
	var over: Variant = definition.get("ai", {})
	if over is Dictionary:
		out.merge(over as Dictionary, true)
	return out


## Сколько игроков в рейде (1–3): по участникам рейда, без рейда — по игрокам на уровне.
static func party_size() -> int:
	if party_override > 0:
		return clampi(party_override, 1, 3)
	var n := 0
	if Raid.current:
		n = Raid.current.participants.size()
	if n <= 0 and current and current.is_inside_tree():
		n = current.get_tree().get_nodes_in_group("players").size()
	return clampi(n, 1, 3)


## Сколько бойцов в группе ЧВК при нынешнем составе игроков.
static func pmc_size() -> int:
	var by_party: Array = Balance.AI_POPULATION.pmc
	return int(by_party[party_size() - 1])


## На карте стоят точки населения — расставлять по слоям.
static func has_points(tree: SceneTree) -> bool:
	for g in ["ai_posts", "ai_routes", "ai_nests"]:
		if not tree.get_nodes_in_group(g).is_empty():
			return true
	return false


## Групп слоя key у нынешнего состава: [от, до] у троих × party_k, округлённо.
func group_count(key: String) -> int:
	var c := cfg()
	var r: Array = c[key]
	var k: float = float((c.party_k as Array)[party_size() - 1])
	return maxi(0, roundi(float(_rng.randi_range(int(r[0]), int(r[1]))) * k))


# ---------------------------------------------------------------- начало рейда

## Хост, перед расстановкой: навигация из кэша приходит тайлами, и сервер синхронизирует их не за один
## кадр — первое время точка «прилипает» не к своему тайлу, и расстановка отбросила бы посты как стоящие
## вне карты (так было в сетевом рейде на «Пешем маршруте»: ноль бойцов). Ждём, пока все точки населения
## (без слоёв — старые ai_spawn_points) встанут на навигацию, не дольше nav_wait_sec.
func wait_navigation() -> void:
	var points := PackedVector3Array()
	var groups: Array = ["ai_posts", "ai_nests", "ai_arrivals"] if has_points(get_tree()) else ["ai_spawn_points"]
	for g in groups:
		for n in get_tree().get_nodes_in_group(g):
			points.append((n as Node3D).global_position)
	for n in get_tree().get_nodes_in_group("ai_routes"):
		points.append_array((n as AIRoute).points())
	var start := Time.get_ticks_msec()
	var end := start + int(float(cfg().nav_wait_sec) * 1000.0)
	var first := -1
	var frames := 0
	while true:
		var bad := 0
		for p in points:
			if _ground(p) == Vector3.INF:
				bad += 1
		if first < 0:
			first = bad
		if bad == 0 or Time.get_ticks_msec() >= end:
			if first > 0 or bad > 0:
				print("population: навигация приняла точки за %d мс (%d кадров): сначала мимо %d из %d, осталось %d" % [
					Time.get_ticks_msec() - start, frames, first, points.size(), bad])
			return
		frames += 1
		await get_tree().physics_frame


## Хост, навмеш готов: гарнизоны, патрули, гнёзда; расписание подхода. Возвращает, сколько бойцов.
func spawn_start() -> int:
	layered = true
	_t = 0.0
	var count := 0
	var want := {"posts": group_count("posts"), "routes": group_count("routes"), "nests": group_count("nests"),
		"arrivals": group_count("arrivals")}
	placed = {"posts": [], "routes": [], "nests": [], "arrivals": [], "marauders": 0, "party": party_size(), "want": want}
	count += _spawn_posts(int(want.posts))
	count += _spawn_routes(int(want.routes))
	count += _spawn_nests(int(want.nests))
	var c := cfg()
	var windows: Array = c.arrive_at
	var n_arr := int(want.arrivals)
	_arrive_queue.clear()
	for i in range(n_arr):
		var w: Array = windows[mini(i, windows.size() - 1)]
		_arrive_queue.append(_rng.randf_range(float(w[0]), float(w[1])))
	_arrive_queue.sort()
	placed.marauders = count
	print("population: игроков %d — постов %d %s, патрулей %d %s, снайперов %d, бойцов %d; подход %s" % [
		party_size(), (placed.posts as Array).size(), placed.posts, (placed.routes as Array).size(), placed.routes,
		(placed.nests as Array).size(), count, _arrive_queue.map(func(t: float) -> int: return int(t))])
	return count


## Посты: сперва обязательные (always_from), потом по весу; взаимоисключающие — не больше одного.
func _spawn_posts(want: int) -> int:
	var all: Array = get_tree().get_nodes_in_group("ai_posts").filter(func(n: Node) -> bool: return n is AIPost)
	var party := party_size()
	var chosen: Array[AIPost] = []
	var tags: Dictionary = {}
	# пост «не каждый рейд» (главарь): не выпал — в этом рейде его нет вовсе
	all = all.filter(func(p: AIPost) -> bool: return p.chance >= 1.0 or _rng.randf() < p.chance)
	for p: AIPost in all:
		if p.always_from > 0 and party >= p.always_from and _post_ok(p, tags):
			chosen.append(p)
			if p.exclusive != "":
				tags[p.exclusive] = true
	var rest: Array = all.filter(func(p: AIPost) -> bool: return not chosen.has(p))
	while chosen.size() < want and not rest.is_empty():
		var p := _pick_weighted(rest) as AIPost
		rest.erase(p)
		if not _post_ok(p, tags):
			continue
		chosen.append(p)
		if p.exclusive != "":
			tags[p.exclusive] = true
	var count := 0
	var c := cfg()
	for p in chosen:
		var size: Vector2i = p.group_size
		if size == Vector2i.ZERO:
			size = Vector2i(int(c.post_group[0]), int(c.post_group[1]))
		var at := _ground(p.global_position)
		var points := _post_points(p)
		var opts := {"home": at, "home_r": p.radius}
		if p.arch != "":
			opts["arch"] = p.arch
		if p.lead_arch != "":
			opts["lead_arch"] = p.lead_arch
		var squad := _spawn_group(at, _rng.randi_range(size.x, size.y), opts)
		for m in squad.members:
			m.home_points = points
		count += squad.members.size()
		(placed.posts as Array).append(String(p.name))
	return count


## Пост годится: не занят его метка, стоит на навигации, не у точки появления и не на виду у неё.
func _post_ok(p: AIPost, tags: Dictionary) -> bool:
	if p.exclusive != "" and tags.has(p.exclusive):
		return false
	var at := _ground(p.global_position)
	return at != Vector3.INF and _safe_start(at)


## Точки обхода поста: свои (дочерние маркеры) — на навигации; нет — набрать в радиусе.
func _post_points(p: AIPost) -> PackedVector3Array:
	var out := PackedVector3Array()
	for q in p.patrol_points():
		var g := _ground(q)
		if g != Vector3.INF:
			out.append(g)
	if not out.is_empty():
		return out
	var center := _ground(p.global_position)
	var map := _world().navigation_map
	for i in range(int(cfg().post_points) * 3):
		if out.size() >= int(cfg().post_points):
			break
		var a := _rng.randf() * TAU
		var q := NavigationServer3D.map_get_closest_point(map, center + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(2.0, p.radius))
		if absf(q.y - center.y) < 2.0 and _flat_dist(q, center) <= p.radius:
			out.append(q)
	return out


## Патрули: маршрут по весу, встают на ближайшую к середине точку маршрута, что не у игроков.
func _spawn_routes(want: int) -> int:
	var rest: Array = get_tree().get_nodes_in_group("ai_routes").filter(func(n: Node) -> bool: return n is AIRoute)
	var count := 0
	var c := cfg()
	while (placed.routes as Array).size() < want and not rest.is_empty():
		var r := _pick_weighted(rest) as AIRoute
		rest.erase(r)
		var pts := PackedVector3Array()
		for q in r.points():
			var g := _ground(q)
			if g != Vector3.INF:
				pts.append(g)
		if pts.size() < 2:
			continue
		# старт — случайная точка маршрута, где можно появиться
		var order: Array = range(pts.size())
		order.shuffle()
		var start := Vector3.INF
		for i: int in order:
			if _safe_start(pts[i]):
				start = pts[i]
				break
		if start == Vector3.INF:
			continue
		var squad := _spawn_group(start, _rng.randi_range(int(c.route_group[0]), int(c.route_group[1])), {})
		for m in squad.members:
			m.route = pts
			m.route_loop = r.loop
			m.no_loot = true
		count += squad.members.size()
		(placed.routes as Array).append(_name_of(r, r.title))
	return count


## Снайпер: один в гнезде, держит позицию, смотрит в свой сектор.
func _spawn_nests(want: int) -> int:
	var rest: Array = get_tree().get_nodes_in_group("ai_nests").filter(func(n: Node) -> bool: return n is AINest)
	var count := 0
	while (placed.nests as Array).size() < want and not rest.is_empty():
		var nest := _pick_weighted(rest) as AINest
		rest.erase(nest)
		var at := _ground(nest.global_position)
		if at == Vector3.INF or not _safe_start(at):
			continue
		var m: Marauder = level.call("spawn_marauder", at, _holds_archetype(), {}) as Marauder
		var squad := Squad.new()
		squad.add(m)
		m.watch_dir = nest.watch_dir()
		m.watch_sector_deg = nest.sector_deg
		m.hold_radius = nest.radius
		count += 1
		(placed.nests as Array).append(_name_of(nest, nest.title))
	return count


# ---------------------------------------------------------------- подход по ходу рейда

func _process(delta: float) -> void:
	if not layered or not _is_host():
		return
	_t += delta
	_retry_t -= delta
	if _arrive_queue.is_empty() or _t < _arrive_queue[0] or _retry_t > 0.0:
		return
	if arrive_now() > 0:
		_arrive_queue.pop_front()
	else:
		_retry_t = float(cfg().arrive_retry_sec)


## Ввести следующую группу подхода прямо сейчас (и тесты, консоль). Возвращает, сколько бойцов вошло
## (0 — все входы у игроков на виду или слишком близко).
func arrive_now() -> int:
	var at := _arrival_point()
	if at == Vector3.INF:
		print("population: подход отложен — все входы у игроков")
		return 0
	var c := cfg()
	var squad := _spawn_group(at, _rng.randi_range(int(c.arrive_group[0]), int(c.arrive_group[1])), {})
	if squad.members.is_empty():
		return 0
	# шумели недавно — туда; нет — за добычей (обычный патруль с грабежом)
	var lead := squad.leader()
	var fresh := Time.get_ticks_msec() - _last_shot_ms < int(float(c.arrive_noise_sec) * 1000.0)
	if lead and fresh and _last_shot_pos != Vector3.INF:
		lead.investigate_at.call_deferred(_last_shot_pos)
	(placed.arrivals as Array).append({"t": int(_t), "at": at.round(), "n": squad.members.size()})
	placed.marauders = int(placed.marauders) + squad.members.size()
	print("population: подход — %d у %s на %d с%s" % [squad.members.size(), at.round(), int(_t), (" к выстрелам у %s" % _last_shot_pos.round()) if fresh else ""])
	return squad.members.size()


## Вход подхода: игроки дальше arrive_min_m и не видят его; из годных — случайный.
func _arrival_point() -> Vector3:
	var min_m: float = float(cfg().arrive_min_m)
	var ok: Array[Vector3] = []
	for n in get_tree().get_nodes_in_group("ai_arrivals"):
		var a := n as AIArrival
		if a == null:
			continue
		var at := _ground(a.global_position)
		if at == Vector3.INF:
			continue
		var good := true
		for p in get_tree().get_nodes_in_group("players"):
			var pl := p as Player
			if pl == null or not pl.is_alive():
				continue
			if pl.global_position.distance_to(at) < min_m or _visible(pl.global_position, at):
				good = false
				break
		if good:
			ok.append(at)
	if ok.is_empty():
		return Vector3.INF
	return ok[_rng.randi_range(0, ok.size() - 1)]


func _on_noise(pos: Vector3, _radius_m: float, kind: String) -> void:
	if kind == "shot":
		_last_shot_pos = pos
		_last_shot_ms = Time.get_ticks_msec()


# ---------------------------------------------------------------- помощники

## Группа из n бойцов у точки at: ведущий — не снайпер, ведомые — как в старом спавне.
func _spawn_group(at: Vector3, n: int, opts: Dictionary) -> Squad:
	var squad := Squad.new()
	var map := _world().navigation_map
	var lead := _walker_archetype()
	for k in range(maxi(n, 1)):
		var p := at
		if k > 0:
			var a := _rng.randf() * TAU
			p = NavigationServer3D.map_get_closest_point(map, at + Vector3(cos(a), 0.0, sin(a)) * (1.2 + k))
		var arch := lead
		if opts.has("arch"):
			arch = String(opts.arch)                            # пост одного типа (кордон ЧВК)
		if k == 0 and opts.has("lead_arch"):
			arch = String(opts.lead_arch)                       # главарь ведёт свою охрану
		while not opts.has("arch") and k > 0 and (arch == lead and _rng.randf() < 0.4 or bool(Balance.AI_ARCHETYPES[arch].holds)):
			arch = Marauder.pick_archetype(_rng)
		var m: Marauder = level.call("spawn_marauder", p, arch, opts) as Marauder
		if m:
			squad.add(m)
	return squad


## Тип ведущего обычной группы: случайный по долям, но не держащий позицию (снайпер ходит один).
func _walker_archetype() -> String:
	for i in range(12):
		var a := Marauder.pick_archetype(_rng)
		if not bool(Balance.AI_ARCHETYPES[a].holds):
			return a
	return "gunner"


## Тип для гнезда: тот, кто держит позицию (сейчас — снайпер).
func _holds_archetype() -> String:
	for k in Balance.AI_ARCHETYPES:
		var a: Dictionary = Balance.AI_ARCHETYPES[k]
		if bool(a.get("holds", false)) and String(a.get("faction", "marauder")) == "marauder":
			return String(k)
	return "sniper"


## Случайный узел по весу (weight у точек).
func _pick_weighted(list: Array) -> Node:
	var total := 0.0
	for n: Node in list:
		total += maxf(0.0, float(n.get("weight")))
	if total <= 0.0:
		return list[_rng.randi_range(0, list.size() - 1)]
	var roll := _rng.randf() * total
	for n: Node in list:
		roll -= maxf(0.0, float(n.get("weight")))
		if roll <= 0.0:
			return n
	return list[list.size() - 1]


## Точка на навигации под p: ближайшая; если по горизонтали дальше snap_m (маркер поставлен на глаз
## над рельефом) — по лучу вниз до земли. Не нашлось — Vector3.INF.
func _ground(p: Vector3) -> Vector3:
	var map := _world().navigation_map
	var snap_m: float = float(cfg().snap_m)
	var q := NavigationServer3D.map_get_closest_point(map, p)
	if _flat_dist(q, p) <= snap_m and absf(q.y - p.y) <= snap_m:
		return q
	var ray := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 60.0, p + Vector3.DOWN * 60.0, Hitscan.LAYER_WORLD)
	var hit := _world().direct_space_state.intersect_ray(ray)
	if not hit.is_empty():
		q = NavigationServer3D.map_get_closest_point(map, hit.position as Vector3)
		if _flat_dist(q, p) <= snap_m:
			return q
	return Vector3.INF


## Можно ли появиться здесь в начале рейда: не ближе MARAUDER_SPAWN_MIN_DIST к точке появления
## игроков и не на виду у неё (SPAWN_SAFE).
func _safe_start(at: Vector3) -> bool:
	var spawn: Vector3 = level.call("spawn_pos")
	return at.distance_to(spawn) >= Balance.MARAUDER_SPAWN_MIN_DIST and not bool(level.call("sees_spawn", at))


## Видно ли точку at из глаз стоящего в from (открыто, без стен и дверей).
func _visible(from: Vector3, at: Vector3) -> bool:
	var q := PhysicsRayQueryParameters3D.create(from + Vector3.UP * 1.6, at + Vector3.UP * 1.6, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	return _world().direct_space_state.intersect_ray(q).is_empty()


func _world() -> World3D:
	return (level as Node3D).get_world_3d()


static func _flat_dist(a: Vector3, b: Vector3) -> float:
	return Vector2(a.x - b.x, a.z - b.z).length()


static func _name_of(n: Node, title: String) -> String:
	return title if title != "" else String(n.name)
