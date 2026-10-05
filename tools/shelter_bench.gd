extends Node
## Одинаковый замер старого и нового убежища на отдельном профиле; FPS не ограничен VSync.

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_bench_test.json", true)
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var path: String = args[0] if not args.is_empty() else Balance.HIDEOUT_SCENE
	get_tree().change_scene_to_file(path)
	for i: int in range(150):
		await get_tree().process_frame
	var level: Node = get_tree().current_scene
	var rig: CameraRig = level.get_node("CameraRig") as CameraRig
	var pl: Player = level.get("_player") as Player
	var output: Array[Dictionary] = []
	for mode: String in ["iso", "fps"]:
		if mode == "fps":
			pl.look_yaw = PI
			rig._set_ads(true, pl)
		for i: int in range(100):
			await get_tree().process_frame
		var start: int = Time.get_ticks_usec()
		var calls: int = 0
		var tris: int = 0
		for i: int in range(180):
			await get_tree().process_frame
			calls += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
			tris += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
		var seconds: float = float(Time.get_ticks_usec() - start) / 1e6
		output.append({"mode": mode, "fps": 180.0 / seconds, "frame_ms": seconds * 1000.0 / 180.0, "draw_calls": calls / 180, "triangles": tris / 180})
	print("SHELTER_BENCH " + JSON.stringify({"scene": path, "resolution": get_viewport().get_visible_rect().size, "results": output}))
	get_tree().quit()
