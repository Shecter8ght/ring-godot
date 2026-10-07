extends Node
## Крупные планы готовых предметов и последовательность запечённого пара.

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_dressing_shots_test.json",true)
	Profile.hideout_media = {"power":true,"tv":1,"radio":0}
	Settings.quality = "high"
	get_tree().change_scene_to_file("res://levels/shelter/Shelter_Interior.tscn")
	await _frames(180)
	var level: Node = get_tree().current_scene
	Settings.apply_graphics()
	(level.get_node("CameraRig") as CameraRig).set_process(false)
	(level.get("_player") as Player).set_physics_process(false)
	for canvas: Node in level.find_children("*","CanvasLayer",true,false): (canvas as CanvasLayer).visible=false
	var cam: Camera3D = Camera3D.new()
	cam.fov=55
	cam.near=.04
	level.add_child(cam)
	cam.make_current()
	SectorMaterials.set_cutaway_distance(0,.001)
	for spec: Array in [["tea_corner",Vector3(-15.30,1.65,-9.4),Vector3(-16.35,1.03,-10.35)],
		["weapon_service",Vector3(-13.05,1.45,5.35),Vector3(-13.1,.85,4.10)],
		["repair_bench",Vector3(13.2,1.48,-2.9),Vector3(13.7,1.10,-4.25)],
		["shelf_supplies",Vector3(12.25,1.75,4.77),Vector3(12.25,1.34,6.3)],
		["generator_meters",Vector3(15.36,1.65,-9.15),Vector3(15.50,1.25,-10.7)],
		["sleeping_fabric",Vector3(-2.1,4.1,-8.0),Vector3(-2.1,3.3,-9.4)]]:
		if String(spec[0])=="sleeping_fabric": cam.cull_mask &= ~SectorBuilder.CEILING_LAYER
		cam.position=spec[1]
		cam.look_at(spec[2])
		await _frames(40)
		get_viewport().get_texture().get_image().save_png("res://docs/shelter/validation/"+String(spec[0])+".png")
	cam.position=Vector3(-15.25,1.59,-9.65)
	cam.look_at(Vector3(-16.35,1.25,-10.35))
	DirAccess.make_dir_recursive_absolute("res://_asset_src/shelter/atmosphere/frames")
	for frame: int in range(36):
		await get_tree().create_timer(.10).timeout
		get_viewport().get_texture().get_image().save_png("res://_asset_src/shelter/atmosphere/frames/frame_%03d.png"%frame)
	get_tree().quit()

func _frames(count: int) -> void:
	for frame: int in range(count): await get_tree().process_frame
