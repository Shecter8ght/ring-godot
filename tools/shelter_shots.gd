extends Node
## Фиксированные ракурсы finished interior: FPS внутри помещений и общий cutaway.

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_shots_test.json", true)
	Profile.modules.generator = 1
	Profile.hideout_media = {"tv": 1, "radio": 0}
	get_tree().change_scene_to_file("res://levels/shelter/Shelter_Interior.tscn")
	await _frames(180)
	var level: Node = get_tree().current_scene
	var rig: CameraRig = level.get_node("CameraRig") as CameraRig
	var pl: Player = level.get("_player") as Player
	for canvas: Node in level.find_children("*", "CanvasLayer", true, false):
		(canvas as CanvasLayer).visible = false
	rig.set_process(false)
	pl.set_physics_process(false)
	var cam: Camera3D = Camera3D.new()
	cam.name = "CaptureCamera"
	cam.fov = 70
	cam.near = .05
	level.add_child(cam)
	cam.make_current()
	SectorMaterials.set_cutaway_distance(0,.001)
	for shot: Array in [["entry",Vector3(0,1.67,10.4),Vector3(0,1.2,0)],["hub",Vector3(-4.5,1.67,4.2),Vector3(1,1.25,-2)],["living",Vector3(-9.4,1.67,-6.4),Vector3(-13.4,1.0,-9.3)],["trader",Vector3(-9.4,1.67,-.2),Vector3(-13.5,1.1,-3.0)],["workshop",Vector3(9.7,1.67,.1),Vector3(14,.95,-4)],["armory",Vector3(-9.4,1.67,6),Vector3(-14,1.1,2.4)],["storage",Vector3(10,1.67,2.3),Vector3(14,1.0,6.1)],["generator",Vector3(9.8,1.67,-5.5),Vector3(14,1.1,-8.8)],["sleeping",Vector3(5.2,4.27,-7.3),Vector3(0,3.3,-9.5)],["ceiling",Vector3(0,1.67,4),Vector3(3,4.25,-3)]]:
		cam.position = shot[1]
		cam.look_at(shot[2])
		await _frames(50)
		_save(String(shot[0]))
	# Крупные планы показывают ориентацию печати, крепёж и разделение поверхностей.
	for shot: Array in [["wall_plan",Vector3(-4.7,1.85,.95),Vector3(-7.73,1.85,.95)],["room_sign",Vector3(4.8,2.5,-2),Vector3(7.78,2.65,-2)],["tabletop",Vector3(-.85,1.35,1.4),Vector3(-.85,.79,.28)],["bay_sign",Vector3(5.1,2.25,5.6),Vector3(5.1,2.24,7.7)]]:
		cam.position = shot[1]
		cam.look_at(shot[2])
		await _frames(50)
		_save(String(shot[0]))
	(_level_power(level) as ShelterPower).request_use()
	cam.position = Vector3(0,1.67,10.4)
	cam.look_at(Vector3(0,1.2,0))
	await _frames(70)
	_save("power_off")
	_level_power(level).request_use()
	await _frames(60)
	cam.cull_mask &= ~SectorBuilder.CEILING_LAYER
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 33
	cam.position = Vector3(27,37,35)
	cam.look_at(Vector3(0,0,-1))
	await _frames(60)
	_save("overview")
	get_tree().quit()

func _level_power(level: Node) -> ShelterPower:
	return level.get_node("Gameplay/GeneratorPower") as ShelterPower

func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().process_frame

func _save(label: String) -> void:
	get_viewport().get_texture().get_image().save_png("res://docs/shelter/validation/"+label+".png")
