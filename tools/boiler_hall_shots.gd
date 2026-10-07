extends Node
## Снимки котельной и тира в docs/screens/boiler_*.png: зал от двери, вид стрелка с рубежа, котлы,
## насосы, шкаф стойки, пульт дорожки, мишени вблизи, прежние комнаты и общий план без кровли.
## tools/godot.cmd res://tools/boiler_hall_shots.tscn

const SHOTS: Array = [
	["hall_door", Vector3(19.2, 1.67, 4.2), Vector3(40, 2.6, -2)],
	["firing_line", Vector3(23.2, 1.67, .6), Vector3(55, 1.35, .6)],
	["boilers", Vector3(25.5, 2.3, -4.2), Vector3(40, 3.2, -9)],
	["boiler_front", Vector3(26.6, 1.7, -6.2), Vector3(30, 2.0, -8.4)],
	["pumps", Vector3(23.4, 1.7, -6.4), Vector3(20.6, .8, -9.8)],
	["gun_cabinet", Vector3(21.2, 1.67, .6), Vector3(18.3, 1.25, .6)],
	["console", Vector3(23.7, 1.55, -.4), Vector3(24.55, .95, .6)],
	["targets", Vector3(31.0, 1.67, -.6), Vector3(37, 1.4, .6)],
	["mannequins", Vector3(31.0, 1.67, 4.2), Vector3(37, 1.2, 4.2)],
	["storage_door", Vector3(10.4, 1.67, 4.0), Vector3(18, 1.5, 4.0)],
	["hub", Vector3(-4.5, 1.67, 4.2), Vector3(1, 1.25, -2)],
	["armory", Vector3(-9.4, 1.67, 6), Vector3(-14, 1.1, 2.4)],
	["living", Vector3(-9.4, 1.67, -6.4), Vector3(-13.4, 1.0, -9.3)],
	["workshop", Vector3(9.7, 1.67, .1), Vector3(14, .95, -4)],
]


func _ready() -> void:
	await get_tree().process_frame
	# инструмент остаётся в дереве, когда уровень сменяет текущую сцену
	get_tree().current_scene = null
	Profile.use_file("user://boiler_shots_test.json", true)
	Profile.modules.generator = 1
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	await _frames(200)
	var level: Node = get_tree().current_scene
	for canvas: Node in level.find_children("*", "CanvasLayer", true, false):
		(canvas as CanvasLayer).visible = false
	(level.get_node("CameraRig") as Node).set_process(false)
	var pl: Player = level.get("_player") as Player
	pl.set_physics_process(false)
	pl.global_position = Vector3(0, -50, 0)
	var cam: Camera3D = Camera3D.new()
	cam.fov = 72
	cam.near = .05
	level.add_child(cam)
	cam.make_current()
	SectorMaterials.set_cutaway_distance(0, .001)
	var only: String = OS.get_environment("BOILER_ONLY")
	for shot: Array in SHOTS:
		if only != "" and not String(shot[0]) in only.split(","):
			continue
		cam.position = shot[1]
		cam.look_at(shot[2])
		await _frames(45)
		_save(String(shot[0]))
	if only == "" or "overview" in only.split(","):
		cam.cull_mask &= ~SectorBuilder.CEILING_LAYER
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = 62
		cam.position = Vector3(64, 58, 52)
		cam.look_at(Vector3(22, 0, -2))
		await _frames(60)
		_save("overview")
	get_tree().quit()


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().process_frame


func _save(label: String) -> void:
	get_viewport().get_texture().get_image().save_png("res://docs/screens/boiler_" + label + ".png")
