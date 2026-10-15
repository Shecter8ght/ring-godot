extends Node
## Снимки согласованного фрагмента из реального Forward+, без вмешательства в профиль.

const SHOTS := {
	"yard_entry": [Vector3(-211,2.1,-124), Vector3(-216.8,2.0,-132.5)],
	"stairwell": [Vector3(-216.8,3.1,-137.1), Vector3(-217.55,4.0,-133.8)],
	"apartment": [Vector3(-223.7,3.05,-136.8), Vector3(-219.2,2.25,-133.3)],
	"market": [Vector3(-177,2.2,-32), Vector3(-177,1.9,33)],
	"hangar": [Vector3(-191.0,2.3,-10), Vector3(-197,4.3,19)],
	"office": [Vector3(-202.1,5.7,18), Vector3(-196.0,4.9,24.0)],
	"houses": [Vector3(-255,2.3,17), Vector3(-275,2.6,11)],
	"attic": [Vector3(-270.34,4.87,5.09), Vector3(-271.07,3.82,.96)],
	"bridge": [Vector3(-316,2.0,35), Vector3(-350,1.2,36)],
	"aerial_market": [Vector3(-130,60,112), Vector3(-180,0,20)],
}


func _ready() -> void:
	Profile.use_file("user://zone01_nw_shots.json", true)
	var time_key: String = OS.get_environment("NW_TIME")
	if time_key == "":
		time_key = "dusk"
	RaidConditions.from_host = {"time": time_key, "weather": "clear", "power": "on"}
	RaidEvents.enabled = false
	var level: Node3D = (load("res://scenes/levels/zone01_mall.tscn") as PackedScene).instantiate() as Node3D
	get_tree().root.add_child.call_deferred(level)
	await get_tree().process_frame
	get_tree().current_scene = level
	var deadline: int = Time.get_ticks_msec() + 120000
	while (Raid.current == null or Raid.current.local_player() == null or int(level.get("_marauders_spawned")) == 0) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	if Raid.current == null or Raid.current.local_player() == null or int(level.get("_marauders_spawned")) == 0:
		push_error("NW_SHOTS: рейд не загрузился")
		get_tree().quit(1)
		return
	Raid.current.local_player().set_physics_process(false)
	for layer: Node in level.find_children("*", "CanvasLayer", true, false):
		(layer as CanvasLayer).visible = false
	var cam := Camera3D.new()
	cam.fov = 76
	cam.far = 1800
	cam.cull_mask &= ~RainOcclusion.LAYER
	level.add_child(cam)
	cam.make_current()
	var selected: PackedStringArray = OS.get_environment("NW_SHOTS").split(",", false)
	var root: String = "res://docs/screens/zone01_nw"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(root))
	for title: String in SHOTS:
		if not selected.is_empty() and title not in selected:
			continue
		cam.global_position = SHOTS[title][0]
		cam.look_at(SHOTS[title][1])
		for tick in range(35):
			await get_tree().process_frame
		var measure_start: int = Time.get_ticks_usec()
		var draw_calls: int = 0
		var triangles: int = 0
		for tick in range(60):
			await get_tree().process_frame
			draw_calls += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
			triangles += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME)
		print("NW_RENDER %s fps=%.1f draw=%d triangles=%d" % [title,
			60000000.0 / float(Time.get_ticks_usec() - measure_start), draw_calls / 60, triangles / 60])
		await RenderingServer.frame_post_draw
		var suffix: String = "_night" if time_key == "night" else ""
		var error: Error = get_viewport().get_texture().get_image().save_png(root + "/" + title + suffix + ".png")
		print("NW_SHOT ", title, " ", error)
	get_tree().quit()


func _process(_delta: float) -> void:
	# Оператор не участвует в бою; игровые условия и освещение остаются штатными.
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.queue_free()
