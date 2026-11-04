extends Node3D
## Imported asset checks and close/working-distance views; -- check is headless-safe.

var failures: int = 0
var model: Node3D
var camera: Camera3D


func check(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error("PHONE: " + message)


func _ready() -> void:
	model = ItemModels.build("quest_phone")
	add_child(model)
	await get_tree().process_frame
	var box := ItemModels.bounds(model)
	check(absf(box.size.x - 0.07836) < 0.0001, "width in metres")
	check(absf(box.size.y - 0.163) < 0.0001, "height in metres")
	check(absf(box.size.z - 0.011132) < 0.0001, "thickness in metres")
	var count: int = 0
	var names: Array[String] = []
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := raw as MeshInstance3D
		names.append(String(mesh.name))
		for surface: int in mesh.mesh.get_surface_count():
			var arrays := mesh.mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			count += indices.size() / 3 if not indices.is_empty() else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
		check(mesh.material_override != null, "assigned game material: " + String(mesh.name))
	check(count <= 5000 and count > 0, "complete assembly <=5000 triangles")
	for name: String in ["DisplaySurface", "Housing", "CameraGlass", "CameraOptics", "ButtonPower", "ButtonShutter", "ButtonAction", "ButtonVolumeUp", "ButtonVolumeDown"]:
		check(name in names, "separate part " + name)
	for name: String in ["ScreenMarker", "CameraLensMarker"]:
		check(model.find_child(name, true, false) != null, "mount marker " + name)
	for channel: String in ["albedo", "normal", "orm"]:
		var path := "res://assets/items/models/quest_phone/quest_phone_%s.png" % channel
		check(ResourceLoader.exists(path), "texture " + channel)
		var config := ConfigFile.new()
		check(config.load(path + ".import") == OK, "import settings " + channel)
		check(bool(config.get_value("params", "mipmaps/generate", false)), "mipmaps " + channel)
		if channel == "normal":
			check(int(config.get_value("params", "compress/normal_map", 0)) == 1, "normal compression")
		if channel == "orm":
			check(int(config.get_value("params", "roughness/mode", 0)) == 3, "ORM green roughness filter")
			check(not String(config.get_value("params", "roughness/src_normal", "")).is_empty(), "roughness normal source")
	print("PHONE ASSET: ", count, " triangles, ", names.size(), " mesh nodes ", names, ", bounds ", box.size, ", failures ", failures)
	if "check" in OS.get_cmdline_user_args():
		get_tree().quit(1 if failures else 0)
		return
	var world := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.23, 0.24, 0.26)
	var sky := Sky.new()
	var panorama := PanoramaSkyMaterial.new()
	panorama.panorama = load("res://assets/sky/kloppenheim_03_puresky.hdr") as Texture2D
	sky.sky_material = panorama
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	world.environment = env
	add_child(world)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45, -35, 0)
	sun.light_energy = 1.5
	add_child(sun)
	camera = Camera3D.new()
	camera.near = 0.005
	camera.fov = 54.0
	add_child(camera)
	camera.make_current()
	await shot("front", Vector3(0.06, 0.025, 0.23), Vector3.ZERO)
	await shot("back", Vector3(-0.055, 0.035, -0.23), Vector3.ZERO)
	await shot("cameras", Vector3(-0.005, 0.075, -0.072), Vector3(0.018, 0.060, -0.005))
	await shot("usb", Vector3(0.02, -0.125, 0.047), Vector3(0, -0.073, 0))
	await shot("work", Vector3(0.13, 0.09, 0.40), Vector3.ZERO)
	get_tree().quit(1 if failures else 0)


func shot(tag: String, eye: Vector3, target: Vector3) -> void:
	camera.look_at_from_position(eye, target)
	for i: int in range(12):
		await get_tree().process_frame
	var path := "res://docs/screens/quest_phone_game_%s.png" % tag
	get_viewport().get_texture().get_image().save_png(path)
	print("PHONE SHOT ", path)
