extends Node
## Замер производительности уровня: встаёт в несколько точек, меряет кадр в изометрии и в прицеле
## (ПКМ) — FPS, вызовы отрисовки, объекты, треугольники. Печатает таблицу и выходит.
## godot --path . res://tools/perf_test.tscn [-- res://scenes/levels/xxx.tscn]; PERF_COND=night:rain:on — условия

## Точки замера: угол, радиус, курс взгляда (град от севера по часовой).
const SPOTS := [
	["аллея у эскалаторов", -90.0, 108.0, 180.0],
	["галерея у атриума", -80.0, 35.0, 170.0],
	["гипермаркет", -45.0, 94.0, 150.0],
	["площадь снаружи", -95.0, 160.0, 180.0],
]
const WARM_FRAMES := 90
const MEASURE_FRAMES := 120


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var scene := args[0] if args.size() > 0 else "res://scenes/levels/f1_ring.tscn"
	# условия рейда: PERF_COND=время:погода:свет (например night:rain:on)
	var pc := OS.get_environment("PERF_COND").split(":")
	if pc.size() == 3:
		RaidConditions.from_host = {"time": pc[0], "weather": pc[1], "power": pc[2]}
		RaidEvents.enabled = false
	await get_tree().process_frame
	var inst: Node = load(scene).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	# ждём навмеш и мародёров — как в игре
	for i in range(600):
		await get_tree().process_frame
		if get_tree().get_nodes_in_group("marauders").size() > 0 and i > 120:
			break
	var player := get_tree().get_first_node_in_group("players") as Player
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	player.health.hp = 1e9
	print("perf: %s" % scene)
	print("  %-20s %-6s %7s %8s %8s %10s" % ["точка", "режим", "FPS", "draw", "объектов", "треуг."])
	for spot in SPOTS:
		player.global_position = SectorBuilder.polar(float(spot[1]), float(spot[2])) + Vector3(0, 0.05, 0)
		var yaw := deg_to_rad(float(spot[3]))
		rig.rotation.y = -yaw
		for mode in ["iso", "ads"]:
			if mode == "ads":
				player.look_yaw = PI - yaw
				Input.action_press("aim")
			await _frames(WARM_FRAMES)
			var r := await _measure()
			print("  %-20s %-6s %7.1f %8d %8d %10d" % [spot[0], mode, r.fps, r.draw, r.objects, r.prims])
			Input.action_release("aim")
			await _frames(10)
	get_tree().quit(0)


func _measure() -> Dictionary:
	var t0 := Time.get_ticks_usec()
	var draw := 0
	var objects := 0
	var prims := 0
	for i in range(MEASURE_FRAMES):
		await get_tree().process_frame
		draw += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
		objects += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME)
		prims += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
	var sec := float(Time.get_ticks_usec() - t0) / 1e6
	return {"fps": MEASURE_FRAMES / sec, "draw": draw / MEASURE_FRAMES, "objects": objects / MEASURE_FRAMES, "prims": prims / MEASURE_FRAMES}


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
