extends Node
## Места заказа «Вернуть машину» на карте ТЦ (scenes/levels/mall_map.tscn, места — scenes/levels/mall/car_recovery_sites.tscn):
## рейд грузится, игрок на заходе, навигация из кэша, три выхода; стоянка у доков — два снимка (F) засчитаны, после отчёта
## и ответа Нине — бокс скупки у АЗС, номер и накладная засчитаны; с этапа «дворы» на складе техники колесо — F, оно в рюкзаке.
## У каждого места — путь по навигации от захода.
##   tools/godot.cmd --headless res://tools/car_mall_sites_shots.tscn            — проверка
##   tools/godot.cmd --windowed --resolution 1600x900 res://tools/car_mall_sites_shots.tscn — и снимки docs/screens/car_mall_*.png

const Q := "car_recovery"
const SITES: Array[String] = ["car_mall_parking_wide", "car_mall_parking_detail", "car_mall_lead_plate", "car_mall_lead_invoice",
	"car_mall_supply_wheel"]

var _fails: int = 0
var _shots: bool = false


func _ready() -> void:
	if name != "CarMallSitesRunner":
		var runner: Node = Node.new()
		runner.name = "CarMallSitesRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_shots = DisplayServer.get_name() != "headless"
	Profile.use_file("user://car_mall_sites_shots.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Quests.dev_start(Q)
	Quests.finish_talk(Q, "ilya", "order")
	get_tree().change_scene_to_file("res://scenes/levels/mall_map.tscn")
	for frame: int in range(40):
		await get_tree().process_frame
	var level: Node3D = get_tree().current_scene as Node3D
	var waited: float = 0.0
	while not bool(level.get("_nav_baked")) and waited < 120.0:
		await get_tree().create_timer(0.25).timeout
		waited += 0.25
	_check("навигация готова", bool(level.get("_nav_baked")), "%.1f с" % waited)
	var player: Player = Raid.current.local_player()
	_check("игрок в рейде", player != null)
	if player == null:
		_finish()
		return
	var entry: SpawnPoint = _nearest_entry(player.global_position)
	_check("игрок на точке захода", entry != null and entry.global_position.distance_to(player.global_position) < 3.0,
		str(player.global_position))
	var exits: int = 0
	for e: Node in get_tree().get_nodes_in_group("extractions"):
		exits += 1 if level.is_ancestor_of(e) else 0
	_check("выходов три", exits == 3, str(exits))
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
		enemy.set_process(false)
	var rig: Node = level.get_node("CameraRig")
	var cam: Camera3D = get_viewport().get_camera_3d()
	if _shots:
		rig.set_process(false)
		rig.set_physics_process(false)
	# стоянка у северо-восточных доков: оба снимка — отчёт Илье
	for sid: String in ["car_mall_parking_wide", "car_mall_parking_detail"]:
		await _use(player, sid)
	_check("стоянка снята — ждём отчёта", String(Quests.objective(Q).get("id", "")) == "report_park", str(Quests.objective(Q).get("id", "")))
	if _shots:
		var wide: Node3D = _site("car_mall_parking_wide")
		if wide:
			await _shot(cam, player, wide.global_position + Vector3(-5.0, 2.2, -6.5), wide.global_position + Vector3(0.0, 0.0, 0.6), "parking")
			await _shot(cam, player, wide.global_position + Vector3(-0.8, 1.6, 3.6), wide.global_position + Vector3(0.4, 0.0, 1.3), "parking_detail")
	Quests.finish_talk(Q, "ilya", "report_park")
	Quests.finish_talk(Q, "perevalka", "hint")
	# бокс скупки у АЗС
	for sid: String in ["car_mall_lead_plate", "car_mall_lead_invoice"]:
		await _use(player, sid)
	_check("номер и накладная сняты — ждём отчёта", String(Quests.objective(Q).get("id", "")) == "report_lead", str(Quests.objective(Q).get("id", "")))
	if _shots:
		var plate: Node3D = _site("car_mall_lead_plate")
		if plate:
			await _shot(cam, player, plate.global_position + Vector3(3.9, 1.65, -3.2), plate.global_position + Vector3(3.9, 0.9, 1.6), "lead_box")
			await _shot(cam, player, plate.global_position + Vector3(0.0, 1.65, -1.2), plate.global_position + Vector3(0.0, 1.15, 1.6), "lead_plates")
	# этап «дворы»: склад техники у ТЦ — второй источник колеса
	Quests.dev_stage(Q, 4)
	for frame: int in range(10):
		await get_tree().process_frame
	var had: int = player.inventory.count("car_wheel")
	if _shots:
		var supply: Node3D = _site("car_mall_supply_wheel")
		if supply:
			await _shot(cam, player, supply.global_position + Vector3(-1.5, 1.6, 3.0), supply.global_position + Vector3(0.0, 0.3, 0.0), "supply_wheel")
	await _use(player, "car_mall_supply_wheel")
	_check("колесо со склада техники в рюкзаке", player.inventory.count("car_wheel") == had + 1, "%d → %d" % [had, player.inventory.count("car_wheel")])
	_finish()


func _use(player: Player, sid: String) -> void:
	var site: QuestSite = _site(sid) as QuestSite
	_check("место %s на карте" % sid, site != null)
	if site == null:
		return
	# путь мародёров (навигация) — от каждого захода; игроку речку можно перейти и вброд, навигации — только по мостам
	var map: RID = get_viewport().get_world_3d().navigation_map
	var reached: PackedStringArray = []
	var missed: PackedStringArray = []
	for p: Node in get_tree().get_nodes_in_group("spawn_points"):
		var entry: SpawnPoint = p as SpawnPoint
		if entry == null or not entry.entry:
			continue
		var path: PackedVector3Array = NavigationServer3D.map_get_path(map, entry.global_position, site.global_position, true)
		var gap: float = path[path.size() - 1].distance_to(site.global_position) if not path.is_empty() else INF
		if gap < 2.5:
			reached.append(entry.display_name)
		else:
			missed.append("%s %.0f м" % [entry.display_name, gap])
	_check("к месту %s есть путь по навигации" % sid, not reached.is_empty(),
		"от: %s%s" % [", ".join(reached), ("; нет от: " + ", ".join(missed)) if not missed.is_empty() else ""])
	player.global_position = site.global_position + Vector3(0.0, 0.1, -1.0)
	for frame: int in range(6):
		await get_tree().process_frame
	_check("у места %s можно нажать F" % sid, site.can_use(), site.prompt() if site.can_use() else "")
	site.request_use()
	for frame: int in range(6):
		await get_tree().process_frame


func _site(sid: String) -> Node3D:
	return get_tree().current_scene.find_child("Quest_" + sid, true, false) as Node3D


func _nearest_entry(at: Vector3) -> SpawnPoint:
	var best: SpawnPoint = null
	for p: Node in get_tree().get_nodes_in_group("spawn_points"):
		var s: SpawnPoint = p as SpawnPoint
		if s and s.entry and (best == null or s.global_position.distance_to(at) < best.global_position.distance_to(at)):
			best = s
	return best


func _shot(cam: Camera3D, player: Player, eye: Vector3, at: Vector3, tag: String) -> void:
	player.global_position = eye - Vector3.UP * 1.5
	cam.global_position = eye
	cam.look_at(at)
	for frame: int in range(14):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/car_mall_%s.png" % tag
	get_viewport().get_texture().get_image().save_png(path)
	print("car_mall_sites_shots: ", path)


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s%s" % ["ok" if ok else "ПРОВАЛ", what, (" — " + detail) if detail != "" else ""])


func _finish() -> void:
	print("car_mall_sites_shots: провалов %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)
