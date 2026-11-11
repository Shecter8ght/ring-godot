extends Node
## Actual Prospekt raid lighting, collision and player controller in an isolated profile.

const PROSPEKT := preload("res://scenes/levels/prospekt.tscn")
const LOCATION := Vector3(-184, 0, -53.8)
const VIEWS := [
	["01_street", Vector3(-4.28,1.67,10.34), Vector3(-.78,2.36,5.37)],
	["02_hall", Vector3(-1.37,1.66,3.96), Vector3(-.37,1.53,-2.13)],
	["03_menu", Vector3(1.85,1.68,2.92), Vector3(3.87,2.25,2.58)],
	["04_washroom", Vector3(-5.31,1.63,-3.14), Vector3(-6.70,1.14,-4.93)],
	["05_stockroom", Vector3(5.32,1.69,-1.47), Vector3(6.06,1.29,-5.07)],
	["06_utility", Vector3(4.60,1.60,.14), Vector3(7.29,1.12,-2.18)],
	["07_exit", Vector3(6.17,1.64,-3.67), Vector3(5.98,1.55,-6.76)],
]
const SHADOW_VIEWS := [
	["02_hall", Vector3(-1.37,1.66,3.96), Vector3(-.37,1.53,-2.13)],
	["08_washroom_door", Vector3(-5.47,1.64,-4.63), Vector3(-5.97,1.69,-2.58)],
	["09_washroom_bin", Vector3(-5.52,1.63,-3.85), Vector3(-7.24,.58,-4.26)],
	["10_counter_back", Vector3(2.73,1.65,.83), Vector3(1.38,.67,2.52)],
	["11_utility_side", Vector3(6.64,1.65,-1.80), Vector3(6.09,1.47,3.95)],
	["12_exit_closed", Vector3(6.17,1.64,-3.67), Vector3(5.98,1.55,-6.76)],
]

var _level: Node3D
var _cafe: Node3D
var _player: Player
var _failures: Array[String] = []


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var check := "--check" in args
	var shots := "--shots" in args
	var weather := "overcast" if "--overcast" in args else "clear"
	Profile.use_file("user://profile_zerno_review.json", true)
	Profile.ensure()
	if check:
		Profile.profile_name = "Зерно · проверка"
		Profile.flags["new_game"] = true
		Profile.prologue_start()
		Profile.save()
		Quests.start("prologue")
		Profile.pending_raid = true
	RaidEvents.enabled = false
	RivalRaids.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": weather, "power": "off"}
	get_tree().node_added.connect(_quiet_marauders)
	await get_tree().process_frame
	_level = PROSPEKT.instantiate() as Node3D
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	_cafe = _level.get_node("World/West/Coffee") as Node3D
	if not await _wait_for_player():
		get_tree().quit(2)
		return
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig == null:
		push_error("No player camera rig")
		get_tree().quit(2)
		return
	if check:
		await _check()
		get_tree().quit(0 if _failures.is_empty() else 3)
	elif shots:
		await _capture(rig, weather)
		get_tree().quit(0 if _failures.is_empty() else 4)
	else:
		_move_player(LOCATION + Vector3(-1.22,.055,8.3))
		var yaw := atan2(1.22, -2.95)
		_player.face(yaw)
		rig._look_yaw = yaw
		print("ZERNO_READY ", weather)


func _quiet_marauders(node: Node) -> void:
	if node is Marauder:
		node.process_mode = Node.PROCESS_MODE_DISABLED
		(node as Node3D).hide()


func _wait_for_player() -> bool:
	var start := Time.get_ticks_msec()
	while Time.get_ticks_msec() - start < 120000:
		if Raid.current:
			_player = Raid.current.local_player()
			if _player:
				await get_tree().physics_frame
				await get_tree().physics_frame
				return true
		await get_tree().process_frame
	push_error("Timed out waiting for Prospekt player")
	return false


func _move_player(at: Vector3) -> void:
	_player.global_position = at
	_player.velocity = Vector3.ZERO


func _assert(ok: bool, name: String) -> void:
	print("ZERNO ", "OK " if ok else "FAIL ", name)
	if not ok:
		_failures.append(name)


func _ray(a: Vector3, b: Vector3, mask: int) -> Dictionary:
	return _level.get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(LOCATION + a, LOCATION + b, mask))


func _check() -> void:
	var doors: Dictionary = _cafe.get("leaves")
	var glass := _cafe.get_node("ZernoGlazing") as GlassPanes
	_assert(doors.size() == 5, "five authored door leaves")
	_assert(Prologue.current != null, "actual prologue attached to Prospekt")
	_assert(glass.panes.size() == 8 and glass.panes[5].broken, "seven glass panes and the authored broken bay")
	var containers := _cafe.get_node("Gameplay").get_children()
	_assert(containers.size() == 4 and containers.all(func(c: Node) -> bool:
		return c is LootContainer and (c as LootContainer).table == "register"), "four original raid loot spots")
	var pane_ray := _ray(Vector3(2.93,1.48,6), Vector3(2.93,1.48,4.85), Hitscan.LAYER_GLASS)
	var pane := GlassPanes.pane_of(pane_ray)
	_assert(pane.size() == 2 and pane[0] == glass and pane[1] == 6, "storefront bullet addresses the right pane")
	var gap := _ray(Vector3(1.50,1.48,6), Vector3(1.50,1.48,4.85), Hitscan.LAYER_WORLD | Hitscan.LAYER_GLASS)
	_assert(gap.is_empty(), "pre-broken bay remains open")
	_assert(not _ray(Vector3(0,1.5,6.1), Vector3(0,1.5,4.8), Hitscan.LAYER_DOOR).is_empty(), "entry closed initially")
	var daylight := _cafe.get_node("Stock doorway") as SpotLight3D
	_assert(not daylight.visible, "closed stock door blocks the daylight proxy")
	glass.bullet(6, 10000.0, LOCATION + Vector3(2.93,1.48,5.315), Vector3.FORWARD)
	for d: Door in doors.values():
		d.toggle(d.global_position + Vector3(0,0,1))
	for i in range(48):
		await get_tree().physics_frame
	_assert(daylight.visible, "open stock door admits daylight")
	_assert(glass.panes[6].broken and _ray(Vector3(2.93,1.48,6), Vector3(2.93,1.48,4.85),
		Hitscan.LAYER_GLASS).is_empty(), "actual glass shatter removes its collision")
	var routes: Dictionary = {
		"street through hall to stock": [Vector2(0,7.7),Vector2(0,4.08),Vector2(0,0.0),Vector2(5.75,0.0)],
		"washroom": [Vector2(-4.08,-.81),Vector2(-4.17,-2.16),Vector2(-5.88,-2.22),Vector2(-5.88,-3.73)],
		"stock exit through service corridor": [Vector2(5.85,-.75),Vector2(5.94,-3),Vector2(6.02,-4.85),
			Vector2(6.02,-6.75),Vector2(6,-12),Vector2(6,-15.15)],
		"checkout aisle": [Vector2(2.35,.8),Vector2(2.35,4.15)],
		"hall shelf": [Vector2(3.12,-1.0),Vector2(3.12,-4.17)],
		"stock shelf": [Vector2(5.75,0),Vector2(5.24,-3.3),Vector2(4.98,-4.10)],
		"stock boxes": [Vector2(5.75,0),Vector2(5.24,2.0),Vector2(5.24,4.21)],
	}
	for label: String in routes:
		_assert(_route_clear(routes[label]), label)
	var bags := get_tree().get_nodes_in_group("loot_containers").filter(func(c: Node) -> bool:
		return c is LootContainer and (c as LootContainer).display_name.begins_with(String(Balance.PROLOGUE.bag_name) + " · "))
	_assert(not bags.is_empty(), "real prologue spawned its bag")
	if not bags.is_empty():
		var at := (bags[0] as Node3D).global_position - LOCATION
		_assert(at.x > 4.3 and at.x < 7.7 and absf(at.z) < 2.0, "bag is accessible in stock aisle")
	var weather_light := _level.get_node_or_null("Atmosphere") as RaidAtmosphere
	_assert(weather_light != null and DayCycle.current != null, "actual raid atmosphere active")
	print("ZERNO_CHECK ", "ok" if _failures.is_empty() else _failures)


func _route_clear(points: Array) -> bool:
	var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	var passed := true
	for i in range(points.size() - 1):
		var a: Vector2 = points[i]
		var b: Vector2 = points[i+1]
		var side := (b-a).normalized().orthogonal()
		for height: float in [.20, .90, 1.61]:
			for offset: float in [-.23, .0, .23]:
				var u := a + side * offset
				var v := b + side * offset
				var hit := _ray(Vector3(u.x,height,u.y),Vector3(v.x,height,v.y),mask)
				if not hit.is_empty():
					print("ZERNO blocked ", a, " -> ", b, " at ", hit.position,
						" by ", (hit.collider as Node).get_path())
					passed = false
		var count := ceili(a.distance_to(b) / .4)
		for j in range(count + 1):
			var at := a.lerp(b,float(j)/count)
			if _ray(Vector3(at.x,.35,at.y),Vector3(at.x,-.4,at.y),Hitscan.LAYER_WORLD).is_empty():
				print("ZERNO floor missing at ", at)
				passed = false
	return passed


func _capture(rig: CameraRig, weather: String) -> void:
	for node: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		if node.name != "LensLayer":
			(node as CanvasLayer).hide()
	for label: Node in _level.find_children("*", "Label3D", true, false):
		(label as Label3D).hide()
	_player.set_physics_process(false)
	CameraRig.first_person_mode = true
	await RenderingServer.frame_post_draw
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var rid := get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(rid, true)
	var out := OS.get_environment("ZERNO_OUTPUT")
	if out.is_empty():
		out = ProjectSettings.globalize_path("user://zerno_review")
	DirAccess.make_dir_recursive_absolute(out)
	var results: Array[Dictionary] = []
	var shadows := "--shadow-views" in OS.get_cmdline_user_args()
	if shadows and is_instance_valid(DayCycle.current):
		DayCycle.current.set_hour(11.3)
		DayCycle.current.set_process(false)
	var doors: Dictionary = _cafe.get("leaves")
	for view: Array in SHADOW_VIEWS if shadows else VIEWS:
		var open_for_view: Array = {
			"02_hall": ["StreetDoor"], "04_washroom": ["WashroomDoor"], "05_stockroom": ["StockDoor"],
			"07_exit": ["StockRearDoor", "DeliveryDoor"],
			"08_washroom_door": ["WashroomDoor"], "11_utility_side": ["StockDoor"],
			"12_exit_closed": ["StockRearDoor"],
		}.get(view[0], [])
		for name: String in open_for_view:
			var d: Door = doors[name]
			if not d.is_open:
				d.toggle(d.global_position + Vector3(0,0,1))
		var at: Vector3 = view[1]
		var direction: Vector3 = view[2] - at
		_move_player(LOCATION + at - Vector3.UP * float(Balance.ADS_EYE.stand))
		var yaw := atan2(direction.x, direction.z)
		_player.face(yaw)
		rig._look_yaw = yaw
		rig._look_pitch = atan2(direction.y, Vector2(direction.x, direction.z).length())
		for i in range(168):
			await RenderingServer.frame_post_draw
		var path := out.path_join("v13_%s_%s.png" % [weather, view[0]])
		var err := get_viewport().get_texture().get_image().save_png(path)
		_assert(err == OK, "screenshot " + path)
		if view[0] in ["01_street","02_hall","05_stockroom"]:
			var timings: Array[float] = []
			var last := Time.get_ticks_usec()
			for i in range(120):
				await RenderingServer.frame_post_draw
				var now := Time.get_ticks_usec()
				timings.append((now-last)*.001)
				last = now
			timings.sort()
			results.append({"view": view[0], "median_frame_ms": timings[59], "p95_frame_ms": timings[113],
				"visible_triangles": RenderingServer.viewport_get_render_info(rid, RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE,
					RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)})
	var report := out.path_join("v13_" + weather + ".json")
	var file := FileAccess.open(report, FileAccess.WRITE)
	file.store_string(JSON.stringify({"gpu": RenderingServer.get_video_adapter_name(),
		"size": str(get_viewport().get_visible_rect().size), "results": results}, "  "))
	print("ZERNO_BENCH ", JSON.stringify(results))
