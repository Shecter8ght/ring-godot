extends Node
## Точки укрытия карты (src/ai/cover_points.gd, Balance.AI_POINTS; приём Road to Vostok):
## - разметка на простом полигоне: у низкого ящика — «низкое укрытие» лицом к ящику, у конца высокой стены — «угол»,
##   посреди стены и в чистом поле — ничего;
## - «Проспект»: запечённые точки грузятся при готовой навигации, мародёр в бою берёт точку, где препятствие закрывает
##   его со стороны угрозы (присевшего не видно), и занимает её — второй ту же не берёт; угроза не с той стороны —
##   точку не берёт.
## tools/godot.cmd --headless res://tools/cover_points_test.tscn  (сначала — bake_cover_points.tscn)

const CoverPoints = preload("res://src/ai/cover_points.gd")
const LEVEL := "res://scenes/levels/prospekt.tscn"

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_cover_points_test.json", true)
	await get_tree().process_frame
	await _classify_cases()
	_map_files()
	await _prospekt_cases()
	print("cover_points_test: провалено %d" % _fails)
	get_tree().quit(_fails)


# ---------------------------------------------------------------- разметка на полигоне

func _classify_cases() -> void:
	var root := Node3D.new()
	root.position = Vector3(0.0, 500.0, 0.0)
	add_child(root)
	_box(root, Vector3(0.0, -0.1, 0.0), Vector3(60.0, 0.2, 60.0))
	# низкий ящик 2 × 1,1 × 1 м: грань к −Z на z = −0,5
	_box(root, Vector3(0.0, 0.55, 0.0), Vector3(2.0, 1.1, 1.0))
	# высокая стена вдоль X от 10 до 14, лицо к −Z на z = 4,85
	_box(root, Vector3(12.0, 1.5, 5.0), Vector3(4.0, 3.0, 0.3))
	for i: int in range(3):
		await get_tree().physics_frame
	var space: PhysicsDirectSpaceState3D = get_viewport().world_3d.direct_space_state
	var base: Vector3 = root.global_position
	var low: Dictionary = CoverPoints.classify(space, base + Vector3(0.0, 0.0, -1.2))
	_check("у низкого ящика — «низкое укрытие» лицом к ящику", String(low.get("kind", "")) == "low"
		and (low.fwd as Vector3).dot(Vector3(0, 0, 1)) > 0.9, str(low))
	var corner: Dictionary = CoverPoints.classify(space, base + Vector3(13.6, 0.0, 4.3))
	_check("у конца высокой стены — «угол» лицом к стене", String(corner.get("kind", "")) == "corner"
		and (corner.fwd as Vector3).dot(Vector3(0, 0, 1)) > 0.9, str(corner))
	var mid: Dictionary = CoverPoints.classify(space, base + Vector3(12.0, 0.0, 4.3))
	_check("посреди высокой стены — не укрытие и не угол", mid.is_empty(), str(mid))
	var open: Dictionary = CoverPoints.classify(space, base + Vector3(-20.0, 0.0, -20.0))
	_check("в чистом поле — ничего", open.is_empty(), str(open))
	root.queue_free()
	await get_tree().physics_frame


func _box(parent: Node3D, center: Vector3, size: Vector3) -> void:
	var b := StaticBody3D.new()
	b.collision_layer = Hitscan.LAYER_WORLD
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	b.add_child(cs)
	b.position = center
	parent.add_child(b)


# ---------------------------------------------------------------- «Проспект»

func _prospekt_cases() -> void:
	var level: Node = (load(LEVEL) as PackedScene).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	var world: World3D = get_viewport().world_3d
	var me := get_tree().get_first_node_in_group("players") as Player
	if me:
		me.health.hp = 1e9
		me.set_physics_process(false)
	var all: Array = CoverPoints.near(world, Vector3.ZERO, 2000.0)
	_check("точки «Проспекта» загружены вместе с навигацией", all.size() > 50, str(all.size()))
	var marauders: Array[Marauder] = []
	for n: Node in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m and m.state != Marauder.State.DEAD:
			marauders.append(m)
	_check("мародёры есть", marauders.size() >= 2, str(marauders.size()))
	if all.is_empty() or marauders.size() < 2:
		level.queue_free()
		return
	# мародёра ставим в 4 м позади точки (со своей стороны), угроза — в 14 м перед ней (за препятствием)
	var a: Marauder = marauders[0]
	var b: Marauder = marauders[1]
	var picked: int = -1
	var tried: int = 0
	var space: PhysicsDirectSpaceState3D = world.direct_space_state
	for pt: Dictionary in all:
		if tried >= 40:
			break
		var p: Vector3 = pt.pos
		var fwd: Vector3 = pt.fwd
		var behind: Vector3 = NavigationServer3D.map_get_closest_point(world.navigation_map, p - fwd * 4.0)
		if behind.distance_to(p - fwd * 4.0) > 0.5:
			continue
		tried += 1
		_place(a, behind, p + fwd * 14.0)
		var got: Vector3 = a._cover_point(Balance.AI_COVER_RADIUS, false)
		if got != Vector3.INF and a._cover_point_index >= 0:
			picked = a._cover_point_index
			var q := PhysicsRayQueryParameters3D.create(a.last_known + Vector3.UP * 1.3, got + Vector3.UP * Marauder.CROUCH_EYE, Hitscan.LAYER_WORLD)
			_check("мародёр берёт точку карты; присевшего за ней с угрозы не видно", not space.intersect_ray(q).is_empty(),
				"точка %s, %s" % [str(got.round()), String(pt.kind)])
			# угроза с другой стороны — эту точку не берёт
			_place(a, behind, p - fwd * 14.0)
			a._cover_point(Balance.AI_COVER_RADIUS, false)
			_check("угроза с другой стороны — эту точку не берёт", a._cover_point_index != picked, str(a._cover_point_index))
			# занятая точка: первый занял — второй с той же угрозой берёт другое
			_place(a, behind, p + fwd * 14.0)
			a._try_cover(Balance.AI_COVER_RADIUS, false)
			var a_index: int = a._cover_point_index
			_place(b, behind, p + fwd * 14.0)
			b._cover_point(Balance.AI_COVER_RADIUS, false)
			_check("точку занял первый — второй берёт другое место", a_index >= 0 and b._cover_point_index != a_index,
				"%d и %d" % [a_index, b._cover_point_index])
			break
	_check("среди %d проб мародёр хоть раз выбрал точку карты" % tried, picked >= 0)
	level.queue_free()
	await get_tree().process_frame


## Поставить мародёра в точку и дать ему угрозу (последнее известное место цели).
func _place(m: Marauder, at: Vector3, threat: Vector3) -> void:
	m.global_position = at
	m.last_known = threat
	m._cover_miss.clear()


## Точки запечены на всех рейдовых картах (владелец 2026-11-05: «чтобы были умными везде») — файл каждой читается.
func _map_files() -> void:
	var world := World3D.new()
	for sector: String in ["res://data/sectors/prospekt.json", "res://data/sectors/mall_map.json", "res://data/sectors/zone01_mall.json"]:
		var cache: String = String(SectorBuilder.load_def(sector).get("nav_cache", ""))
		var n: int = CoverPoints.load_for(world, cache)
		_check("точки укрытия карты %s: %d" % [sector.get_file().get_basename(), n], n > 500, cache)


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["OK  " if ok else "FAIL", what, ("  (" + detail + ")") if detail != "" else ""])
