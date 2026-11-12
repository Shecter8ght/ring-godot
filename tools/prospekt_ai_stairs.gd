extends Node
## «Проспект»: живой мародёр ходит по лестницам. Для пяти лестниц (западная лестница вестибюля «Яруса», лестница полиции, сход эстакады,
## спуск в туалет сквера, лестница крыла вокзала) мародёра ставят внизу, наверху — шум (NoiseBus, как выстрел: он сам идёт
## проверять, никакой телепатии); за TIME_SEC он должен оказаться наверху (высота тела у цели), потом шум внизу — и обратно.
## Время не ускоряется. Печатает PASS / FAIL по каждому направлению, код выхода — число провалов.
##   tools/godot.cmd --headless res://tools/prospekt_ai_stairs.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
## Сколько секунд даём мародёру на подъём (спуск) и как близко (по плоскости / по высоте) он должен оказаться, м.
const TIME_SEC := 60.0
const NEAR_FLAT_M := 6.0
const NEAR_Y_M := 1.5
## Радиус шума выстрела, м.
const NOISE_M := 150.0
## (название, низ, верх): точки на полу; низ — на улице у лестницы, верх — на этаже за ней.
const CASES: Array = [
	["западная лестница вестибюля «Яруса» (на галерею 2-го этажа)", Vector3(-116.0, 0.1, 58.2), Vector3(-119.0, 6.02, 61.0)],
	["лестница полиции (на 2-й этаж)", Vector3(-187.05, 0.1, 19.0), Vector3(-193.0, 3.52, 22.0)],
	["сход эстакады (на полотно)", Vector3(-232.0, 0.1, 207.0), Vector3(-221.3, 12.7, 207.0)],
	["спуск в туалет сквера", Vector3(-43.0, 0.1, 111.0), Vector3(-29.0, -3.18, 111.0)],
	["лестница крыла вокзала (на террасу)", Vector3(107.05, 0.1, 221.0), Vector3(115.0, 7.62, 240.0)],
]

var _fails: int = 0
var _level: Node
var _map: RID


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_ai_stairs.json", true)
	await get_tree().process_frame
	_level = load(LEVEL).instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	var t0: int = Time.get_ticks_msec()
	while int(_level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	_map = (_level as Node3D).get_world_3d().navigation_map
	# своих бойцов карты убираем: проверяем одного; игрок не мешает (бессмертен, не ходит)
	for n: Node in get_tree().get_nodes_in_group("marauders"):
		n.queue_free()
	var me := get_tree().get_first_node_in_group("players") as Player
	if me:
		me.health.hp = 1e9
		me.set_physics_process(false)
	await get_tree().physics_frame
	for c: Array in CASES:
		await _case(String(c[0]), c[1] as Vector3, c[2] as Vector3)
	print("prospekt_ai_stairs: провалено %d" % _fails)
	get_tree().quit(_fails)


func _case(title: String, low: Vector3, high: Vector3) -> void:
	var a: Vector3 = _on_floor(low)
	var b: Vector3 = _on_floor(high)
	# низ должен быть на основной сетке карты (а не в кармане у стены): от точки на проспекте путь есть
	var q := NavigationPathQueryParameters3D.new()
	q.map = _map
	q.start_position = NavigationServer3D.map_get_closest_point(_map, Vector3(0.0, 0.1, -15.0))
	q.target_position = a + Vector3.UP * 0.5
	q.path_search_max_polygons = 0
	var r := NavigationPathQueryResult3D.new()
	NavigationServer3D.query_path(q, r)
	if r.path.is_empty() or r.path[r.path.size() - 1].distance_to(a + Vector3.UP * 0.5) > 1.0:
		print("ВНИМАНИЕ | %s: низ %s вне основной сетки (от проспекта пути нет)" % [title, a])
	var m := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.archetype = "gunner"
	m.weapon = "rifle"
	_level.get_node("Marauders").add_child(m)
	m.global_position = a
	m.patrol_point_provider = func() -> Vector3: return m.global_position
	m.state = Marauder.State.PATROL
	for i in range(30):
		await get_tree().physics_frame
	# вверх: шум наверху
	NoiseBus.emit(b + Vector3.UP * 0.5, NOISE_M, "shot")
	var up: float = await _walk(m, b)
	_report(title + ": вверх", up, m, b)
	if up >= 0.0:
		# вниз: шум внизу
		NoiseBus.emit(a + Vector3.UP * 0.5, NOISE_M, "shot")
		var down: float = await _walk(m, a)
		_report(title + ": вниз", down, m, a)
	else:
		print("FAIL | %s: вниз — не проверялось, наверх не поднялся" % title)
		_fails += 1
	m.queue_free()
	await get_tree().physics_frame


## Ждать, пока тело окажется у цели; вернёт время, с, или −1, если не успел.
func _walk(m: Marauder, goal: Vector3) -> float:
	var t: float = 0.0
	while t < TIME_SEC:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
		if _near(m.global_position, goal):
			return t
		# в бой с кем-то случайным (мародёр один, но мало ли) не ввязываемся: нет цели — продолжаем ждать
	return -1.0


func _near(p: Vector3, goal: Vector3) -> bool:
	return Vector2(p.x - goal.x, p.z - goal.z).length() < NEAR_FLAT_M and absf(p.y - goal.y) < NEAR_Y_M


func _report(title: String, took: float, m: Marauder, goal: Vector3) -> void:
	if took >= 0.0:
		print("PASS | %s: дошёл за %.1f с" % [title, took])
	else:
		_fails += 1
		print("FAIL | %s: за %.0f с не дошёл; тело %s, цель %s, состояние %d" % [title, TIME_SEC, m.global_position.snapped(Vector3(0.1, 0.1, 0.1)), goal, int(m.state)])


## Точка на полу по сетке навигации (сетка лежит над полом — вернём высоту пола, где стоять).
func _on_floor(p: Vector3) -> Vector3:
	var net: Vector3 = NavigationServer3D.map_get_closest_point(_map, p)
	if Vector2(net.x - p.x, net.z - p.z).length() > 1.2:
		print("ВНИМАНИЕ | точка %s вне навигации (ближайшая %s)" % [p, net])
	return Vector3(net.x, p.y if absf(net.y - 0.5 - p.y) < 0.4 else net.y - 0.45, net.z)
