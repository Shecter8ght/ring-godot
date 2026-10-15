extends Node
## Живые 24 NPC на готовой карте, одинаковое зерно, без событий и входа новых отрядов.
## Отдельный APPDATA в tools/_probe; -- f1|zone01 before|after [profile].

var _seeded: bool = false
var _profile: bool = false
var _map: String = "f1"
var _tag: String = "before"
var _player: Player
var _rig: CameraRig
var _result: Dictionary = {}


func _ready() -> void:
	if name != "AIWorkBenchmarkRunner":
		var runner: Node = Node.new()
		runner.name = "AIWorkBenchmarkRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


func _run() -> void:
	if not OS.get_user_data_dir().replace("\\", "/").begins_with(ProjectSettings.globalize_path("res://tools/_probe/").replace("\\", "/")):
		push_error("ai_work_benchmark: нужен отдельный APPDATA в tools/_probe")
		get_tree().quit(1)
		return
	var args: PackedStringArray = OS.get_cmdline_user_args()
	_map = args[0] if args.size() > 0 else "f1"
	_tag = args[1] if args.size() > 1 else "before"
	_profile = "profile" in args
	seed(20261014)
	Profile.use_file("user://ai_work_benchmark_test.json", true)
	Profile.equipment["primary"] = ItemDb.make(WeaponDb.canonical("w_rifle"), 1)
	Profile.pending_raid = true
	RaidEvents.enabled = false
	RivalRaids.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Settings.set_quality("high")
	Loading.stage_changed.connect(_stage)
	var path: String = "res://scenes/levels/f1_ring.tscn" if _map == "f1" else "res://scenes/levels/zone01_mall.tscn"
	Net.change_scene(path, "Проверка расчётов противников")
	var began: int = Time.get_ticks_msec()
	while Loading.active or get_tree().get_nodes_in_group("marauders").size() < Balance.MARAUDER_COUNT:
		await get_tree().process_frame
		if Time.get_ticks_msec() - began > 180000:
			push_error("ai_work_benchmark: мир не готов")
			get_tree().quit(1)
			return
	_player = Raid.current.local_player()
	_player.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_rig.set_process_unhandled_input(false)
	_result = {"map": _map, "tag": _tag, "seed": 20261014, "profile": _profile,
		"gpu": RenderingServer.get_video_adapter_name(), "viewport": str(get_viewport().get_visible_rect().size), "samples": []}
	var positions: Array[Vector3] = []
	if _map == "f1":
		positions.assign([Vector3(0, 0.05, -108), SectorBuilder.polar(-80, 35) + Vector3.UP * 0.05])
	else:
		positions.assign([Vector3(-515, 3.57, -365), Vector3(400, -2.58, 240)])
	for index: int in range(positions.size()):
		_player.global_position = positions[index]
		_player.velocity = Vector3.ZERO
		_rig._look_yaw = 0.0
		_rig._look_pitch = 0.0
		await get_tree().create_timer(3.0).timeout
		Marauder.work_profile.clear()
		Marauder.work_profile_enabled = _profile
		Perception.work_profile.clear()
		Perception.work_profile_enabled = _profile
		var sample: Dictionary = await _measure()
		Marauder.work_profile_enabled = false
		Perception.work_profile_enabled = false
		sample.work = Marauder.work_profile.duplicate(true)
		sample.perception = Perception.work_profile.duplicate(true)
		sample.position = str(_player.global_position)
		sample.npc = get_tree().get_nodes_in_group("marauders").size()
		(_result.samples as Array).append(sample)
		print("AI WORK ", JSON.stringify(sample))
	var file: FileAccess = FileAccess.open("res://tools/_probe/ai_work_%s_%s%s.json" % [_tag, _map, "_profile" if _profile else ""], FileAccess.WRITE)
	file.store_string(JSON.stringify(_result, "\t"))
	get_tree().quit(0)


func _stage(text: String, _percent: float) -> void:
	if text != "Подготовка мира" or _seeded:
		return
	_seeded = true
	var level: Node = get_tree().current_scene
	(level.get("_rng") as RandomNumberGenerator).seed = 20261014
	level.set("_start_ms", Time.get_ticks_msec())
	level.set("_spawn", Vector3(0, 0, -160) if _map == "f1" else Vector3(-100, 2.72, -580))


func _measure() -> Dictionary:
	var samples: Array[float] = []
	var start: int = Time.get_ticks_usec()
	var previous: int = start
	var draw: float = 0.0
	while Time.get_ticks_usec() - start < 10000000:
		await get_tree().process_frame
		var now: int = Time.get_ticks_usec()
		samples.append(float(now - previous) / 1000.0)
		previous = now
		draw += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	var duration: float = float(Time.get_ticks_usec() - start) / 1000000.0
	samples.sort()
	return {"fps": samples.size() / duration, "seconds": duration, "frames": samples.size(),
		"p95_ms": samples[int(samples.size() * 0.95)], "p99_ms": samples[int(samples.size() * 0.99)],
		"max_ms": samples[-1], "draw": draw / samples.size()}
