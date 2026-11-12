extends Node
## «Проспект»: достижимость мест второй очереди по навигации ИИ. От точки на проспекте (0; 0,1; −15) запрос пути
## тем же вызовом, что у prospekt_raid_check («от захода до выходов»); печатает таблицу «место — путь есть / нет — длина».
## Геометрию не правит: что недостижимо — только в таблицу (и в отчёт этапа). Код выхода — всегда 0.
##   tools/godot.cmd --headless res://tools/prospekt_nav_reach.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
const START := Vector3(0.0, 0.1, -15.0)
## (место, x, y пола, z)
const TARGETS: Array = [
	["«Ярус», 2-й этаж: галерея у атриума", -102.0, 6.02, 53.0],
	["«Ярус», 2-й этаж: «Техно»", -130.0, 6.02, 68.0],
	["«Ярус», мостки склада (север)", -110.0, 6.02, 89.5],
	["«Ярус», мостик поперёк склада", -106.5, 6.02, 103.0],
	["«Ярус», крыша склада", -110.0, 10.92, 112.0],
	["«Ярус», площадка на камерах", -136.0, 3.62, 94.0],
	["«Ярус», диспетчерская на стойках", -75.0, 3.22, 113.0],
	["«Ярус», двор разгрузки", -100.0, 0.1, 128.0],
	["Вокзал, конкорс", 146.0, 7.62, 244.0],
	["Вокзал, платформа", 130.0, 7.62, 260.2],
	["Вокзал, 2-й этаж западного крыла", 115.0, 3.82, 226.0],
	["Вокзал, 2-й этаж восточного крыла", 175.0, 3.82, 226.0],
	["Вокзал, терраса западного крыла", 115.0, 7.62, 240.0],
	["Вокзал, терраса восточного крыла", 175.0, 7.62, 240.0],
	["Вокзал, привокзальная площадь", 146.0, 0.1, 190.0],
	["Вокзал, площадка башни", 144.2, 24.02, 221.2],
	["Полиция, 2-й этаж", -193.0, 3.52, 22.0],
	["Полиция, холл", -192.0, 0.1, 19.0],
	["Туалет сквера (пол −3,2)", -29.0, -3.18, 111.0],
	["Лагерь, вышка (143,5; −45)", 143.5, 5.52, -45.0],
	["Лагерь, вышка (187,5; 56)", 187.5, 5.52, 56.0],
	["Лагерь, вертолётная площадка", 176.0, 0.1, 30.0],
	["Полотно эстакады, остановка", -221.3, 12.7, 207.0],
	["Полотно эстакады, открытый участок (z 165)", -233.0, 9.65, 165.0],
	["Под эстакадой, севернее блокпоста (z −80)", -233.0, 0.1, -80.0],
	["Под эстакадой, блокпост (z −17)", -233.0, 0.1, -17.0],
	["Под эстакадой, южнее блокпоста (z 30)", -233.0, 0.1, 30.0],
	["Под эстакадой, рынок (z 85)", -234.0, 0.1, 85.0],
	["Под эстакадой, техника дорожников (z 160)", -232.0, 0.1, 160.0],
	["Под эстакадой, почтовые фургоны (z 230)", -232.0, 0.1, 230.0],
	["Городок строителей", -200.0, 0.1, 150.0],
	["Гаражный кооператив", -190.0, 0.1, 125.0],
	["Почтовый двор", -170.0, 0.1, 232.0],
	["Автостанция", 172.0, 0.1, 170.0],
	# первая очередь — для сравнения
	["Банк, крыша (гнездо)", -20.0, 12.3, -63.8],
	["Паркинг −1 (пост)", -128.0, -7.2, -91.3],
	["Подземный переход", -156.0, -3.3, -15.65],
]


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_nav_reach.json", true)
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	var map: RID = (level as Node3D).get_world_3d().navigation_map
	var a: Vector3 = NavigationServer3D.map_get_closest_point(map, START)
	print("старт %s → на навигации %s" % [START, a])
	var no: int = 0
	for t: Array in TARGETS:
		var want := Vector3(float(t[1]), float(t[2]), float(t[3]))
		var b: Vector3 = NavigationServer3D.map_get_closest_point(map, want)
		var off: float = b.distance_to(want)
		var q := NavigationPathQueryParameters3D.new()
		q.map = map
		q.start_position = a
		q.target_position = b
		q.path_search_max_polygons = 0
		var r := NavigationPathQueryResult3D.new()
		NavigationServer3D.query_path(q, r)
		var path: PackedVector3Array = r.path
		var ok: bool = not path.is_empty() and path[path.size() - 1].distance_to(b) < 0.6 and off < 1.2
		var len_m: float = 0.0
		for i in range(1, path.size()):
			len_m += path[i - 1].distance_to(path[i])
		if not ok:
			no += 1
		var why: String = ""
		if off >= 1.2:
			why = ", точка вне навигации (до неё %.1f м, ближайшая %s)" % [off, b]
		elif path.is_empty():
			why = ", пути нет"
		elif not ok:
			why = ", путь обрывается в %s" % path[path.size() - 1]
		print("REACH | %s | %s | %.0f м%s" % [t[0], "путь есть" if ok else "НЕТ", len_m, why])
	print("REACH итого: мест %d, без пути %d" % [TARGETS.size(), no])
	get_tree().quit(0)
