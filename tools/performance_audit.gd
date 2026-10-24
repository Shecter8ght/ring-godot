extends Node
## Штатная загрузка и кадры в фиксированных точках всех готовых карт. Отдельный APPDATA обязателен.
## tools/godot.cmd --windowed --resolution 1280x720 --disable-vsync res://tools/performance_audit.tscn -- hideout high baseline

const MAPS: Dictionary = {"hideout": "res://scenes/levels/hideout.tscn", "mall": "res://scenes/levels/mall_map.tscn",
	"zone01": "res://scenes/levels/zone01_mall.tscn"}
const SAMPLE_FRAMES: int = 180
var _result: Dictionary = {}
var _stages: Array[Dictionary] = []
var _stage_start: int = 0
var _stage_name: String = ""
var _loading_start: int = 0


func _ready() -> void:
	if name != "PerformanceAuditRunner":
		var runner: Node = Node.new()
		runner.name = "PerformanceAuditRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


func _run() -> void:
	var probe_root: String = ProjectSettings.globalize_path("res://tools/_probe/").replace("\\", "/")
	if not OS.get_user_data_dir().replace("\\", "/").begins_with(probe_root):
		push_error("performance_audit: нужен отдельный APPDATA внутри tools/_probe")
		get_tree().quit(1)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var map: String = args[0] if args.size() > 0 else "hideout"
	var quality: String = args[1] if args.size() > 1 else "high"
	var tag: String = args[2] if args.size() > 2 else "audit"
	Profile.use_file("user://performance_audit.json", true)
	Profile.equipment["primary"] = ItemDb.make(WeaponDb.canonical("w_rifle"), 1)
	Profile.pending_raid = map != "hideout"
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Settings.set_quality(quality)
	_result = {"map": map, "quality": quality, "tag": tag, "cpu": OS.get_processor_name(),
		"gpu": RenderingServer.get_video_adapter_name(), "resolution": str(get_viewport().get_visible_rect().size),
		"window": str(DisplayServer.window_get_size()), "engine": Engine.get_version_info(), "samples": []}
	Loading.stage_changed.connect(_stage)
	_loading_start = Time.get_ticks_msec()
	_stage_start = _loading_start
	Net.change_scene(String(MAPS[map]), "Замер производительности")
	var previous: int = Time.get_ticks_usec()
	var max_stall: float = 0.0
	while Loading.active and Time.get_ticks_msec() - _loading_start < 240000:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		max_stall = maxf(max_stall, float(now - previous) / 1000.0)
		previous = now
	_result.load_ms = Time.get_ticks_msec() - _loading_start
	_result.load_max_frame_ms = max_stall
	_stage("loaded", 100.0)
	_result.stages = _stages
	if Loading.active or get_tree().current_scene.scene_file_path != MAPS[map]:
		push_error("performance_audit: загрузка не завершилась")
		get_tree().quit(1)
		return
	print("AUDIT LOAD ", map, " ", _result.load_ms, " ms; max frame ", max_stall, " ms")
	var player: Player = get_tree().get_first_node_in_group("players") as Player
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	player.health.invulnerable = true
	rig.set_process_unhandled_input(false)
	var world_wait_start: int = Time.get_ticks_msec()
	var world_wait_max: float = 0.0
	previous = Time.get_ticks_usec()
	while map != "hideout" and int(get_tree().current_scene.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - world_wait_start < 120000:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		world_wait_max = maxf(world_wait_max, float(now - previous) / 1000.0)
		previous = now
	_result.world_ready_ms = Time.get_ticks_msec() - _loading_start
	_result.world_wait_max_ms = world_wait_max
	print("AUDIT WORLD READY ", _result.world_ready_ms, " ms; post-load max frame ", world_wait_max, " ms")
	var original: Vector3 = player.global_position
	var spots: Array[Dictionary] = [{"name": "start", "pos": original, "yaw": 0.0}]
	match map:
		"f1":
			spots = [{"name": "alley", "pos": Vector3(0, 0.05, -108), "yaw": 0.0},
				{"name": "atrium", "pos": SectorBuilder.polar(-80.0, 35.0) + Vector3.UP * 0.05, "yaw": 0.0}]
		"zone01":
			spots = [{"name": "courtyard", "pos": Vector3(-170, 0, 7), "yaw": 0.0},
				{"name": "center", "pos": Vector3(-20, 0, 40), "yaw": PI}]
	for spot: Dictionary in spots:
		player.global_position = _ground(spot.pos as Vector3, player)
		player.velocity = Vector3.ZERO
		rig._look_yaw = float(spot.yaw)
		rig._look_pitch = 0.0
		for aim: bool in [false, true]:
			if aim:
				Input.action_press("aim")
			else:
				Input.action_release("aim")
			var warm_until: int = Time.get_ticks_msec() + 3000
			while Time.get_ticks_msec() < warm_until:
				await get_tree().process_frame
			var sample: Dictionary = await _measure()
			if absf(player.global_position.y - (_ground(player.global_position, player)).y) > 1.0:
				push_error("performance_audit: точка не на полу")
				get_tree().quit(1)
				return
			sample.spot = spot.name
			sample.ads = aim
			sample.position = str(player.global_position)
			(_result.samples as Array).append(sample)
			print("AUDIT SAMPLE ", JSON.stringify(sample))
	Input.action_release("aim")
	if args.size() > 3 and args[3] == "ablate":
		_result.ablations = await _ablate(get_tree().current_scene)
	_result.nodes = Performance.get_monitor(Performance.OBJECT_NODE_COUNT)
	_result.resources = Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)
	_result.static_mb = Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0
	_result.video_mb = RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / 1048576.0
	_result.geometry = _census(get_tree().current_scene)
	var output: String = "res://tools/_probe/performance_%s_%s_%s.json" % [tag, map, quality]
	var file: FileAccess = FileAccess.open(output, FileAccess.WRITE)
	file.store_string(JSON.stringify(_result, "\t"))
	print("AUDIT RESULT ", output)
	get_tree().quit(0)


func _stage(text: String, _percent: float) -> void:
	if text == _stage_name:
		return
	var now: int = Time.get_ticks_msec()
	if _stage_name != "":
		_stages.append({"stage": _stage_name, "ms": now - _stage_start})
	_stage_name = text
	_stage_start = now
	print("AUDIT STAGE ", text, " +", now - _loading_start, " ms")


func _ground(pos: Vector3, player: Player) -> Vector3:
	var terrain: Node = get_tree().get_first_node_in_group("district_terrain")
	var y: float = float(terrain.call("height_at", pos.x, pos.z)) if terrain and terrain.has_method("height_at") else pos.y
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(Vector3(pos.x, y + 2.0, pos.z), Vector3(pos.x, y - 10.0, pos.z), Hitscan.LAYER_WORLD)
	query.exclude = [player.get_rid()]
	var hit: Dictionary = player.get_world_3d().direct_space_state.intersect_ray(query)
	return (hit.position as Vector3) + Vector3.UP * 0.05 if not hit.is_empty() else pos


func _measure() -> Dictionary:
	var times: Array[float] = []
	var previous: int = Time.get_ticks_usec()
	var start: int = previous
	var draw: float = 0.0
	var triangles: float = 0.0
	var process: float = 0.0
	var physics: float = 0.0
	while times.size() < SAMPLE_FRAMES or Time.get_ticks_usec() - start < 4000000:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		times.append(float(now - previous) / 1000.0)
		previous = now
		draw += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
		triangles += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
		process += Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
		physics += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
	times.sort()
	var count: int = times.size()
	return {"fps": count * 1000000.0 / float(Time.get_ticks_usec() - start), "frames": count,
		"p95_ms": times[int(count * 0.95)], "max_ms": times[-1], "draw": draw / count,
		"triangles": triangles / count, "process_ms": process / count, "physics_ms": physics / count}


func _ablate(level: Node) -> Array[Dictionary]:
	var results: Array[Dictionary] = []
	for scripts: Array in [[], ["marauder.gd", "rival_squad.gd", "rival_raids.gd"],
		["character_animator.gd", "support_hand_ik.gd", "weapon_collision_ik.gd"],
		["shopping_cart.gd", "cart_contact.gd", "shopping_cart_visuals.gd"],
		["door.gd", "lamp_head.gd", "street_lamp.gd", "health.gd"]]:
		for node: Node in level.find_children("*", "", true, false):
			var script: Script = node.get_script() as Script
			if script != null and script.resource_path.get_file() in scripts:
				node.set_process(false)
				node.set_physics_process(false)
		var warm_until: int = Time.get_ticks_msec() + 3000
		while Time.get_ticks_msec() < warm_until:
			await get_tree().process_frame
		var result: Dictionary = await _measure()
		result.disabled = scripts
		results.append(result)
		print("AUDIT ABLATE ", JSON.stringify(result))
	return results


func _census(root: Node) -> Array[Dictionary]:
	var by: Dictionary = {}
	for node: Node in root.find_children("*", "GeometryInstance3D", true, false):
		var mesh: Mesh = null
		var instances: int = 1
		if node is MeshInstance3D:
			mesh = (node as MeshInstance3D).mesh
		elif node is MultiMeshInstance3D:
			var mm: MultiMesh = (node as MultiMeshInstance3D).multimesh
			if mm:
				mesh = mm.mesh
				instances = mm.instance_count
		if mesh == null:
			continue
		var triangles: int = 0
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			if arrays.is_empty():
				continue
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
			triangles += indices.size() / 3 if not indices.is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
		var path: String = mesh.resource_path.get_slice("::", 0)
		if path == "":
			var parent: Node = node
			while parent and parent.scene_file_path == "":
				parent = parent.get_parent()
			path = parent.scene_file_path if parent else "generated"
		var entry: Dictionary = by.get(path, {"source": path, "triangles": 0, "meshes": 0})
		entry.triangles = int(entry.triangles) + triangles * instances
		entry.meshes = int(entry.meshes) + 1
		by[path] = entry
	var entries: Array[Dictionary] = []
	for entry: Dictionary in by.values():
		entries.append(entry)
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.triangles) > int(b.triangles))
	return entries.slice(0, 20)
