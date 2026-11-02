extends Node
## Real production weapon + attachment tree, and a fixed exposure beam comparison.

var vp: SubViewport
var camera: Camera3D


func _ready() -> void:
	await get_tree().process_frame
	vp = SubViewport.new()
	vp.size = Vector2i(1600, 900)
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	ItemStudio.setup(vp)
	camera = Camera3D.new()
	camera.current = true
	camera.near = 0.005
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	vp.add_child(camera)
	for wid: String in ["wpn_ar_01", "wpn_ar_09", "wpn_sg_02"]:
		var mods: Dictionary = {"side_right": {"id": DozorGear.MOUNT}, "side_right/light": {"id": "tac_flashlight_01"}}
		var gun: Node3D = WeaponModels.build(wid)
		vp.add_child(gun)
		WeaponMods.fit(gun, String(WeaponDb.weapon(wid).model), mods, 0, wid)
		camera.size = 0.72
		camera.position = Vector3(-0.72, 0.40, 0.58)
		camera.look_at(Vector3(0, 0.06, 0.12))
		await _capture("integration_" + wid)
		if wid == "wpn_ar_01":
			camera.size = 0.20
			camera.position = Vector3(-0.35, 0.20, 0.38)
			camera.look_at(Vector3(-0.055, 0.094, 0.22))
			await _capture("integration_mount_close")
		gun.free()
	# Same wall, exposure and camera for regular / high power / strobe off and on.
	for node: Node in vp.get_children():
		if node is DirectionalLight3D:
			(node as DirectionalLight3D).light_energy = 0.0
		if node is WorldEnvironment:
			var env: Environment = (node as WorldEnvironment).environment
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			env.ambient_light_color = Color.BLACK
			env.ambient_light_energy = 0.0
	var wall: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3(12, 8, 0.1)
	wall.mesh = box
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.albedo_color = Color(0.45, 0.45, 0.45)
	mat.roughness = 0.9
	wall.material_override = mat
	wall.position = Vector3(0, 0, 5)
	vp.add_child(wall)
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 65
	camera.position = Vector3(0, 0.3, -0.4)
	camera.look_at(Vector3(0, 0, 5))
	for id: String in DozorGear.VARIANTS:
		var torch: Node3D = DozorAsset.flashlight(String(DozorGear.VARIANTS[id]))
		vp.add_child(torch)
		WeaponMods._light_node(torch, {}, WeaponDb.attachment(id), Vector3(0, 0, 0.0805))
		var light: SpotLight3D = torch.find_child("Flashlight*", true, false) as SpotLight3D
		light.visible = true
		var pulse: FlashlightPulse = light.get_node_or_null("Pulse") as FlashlightPulse
		if pulse:
			pulse.set_process(false)
			pulse.apply_at(0.1)
			await _capture("integration_beam_strobe_off")
			pulse.apply_at(0.01)
		await _capture("integration_beam_" + String(DozorGear.VARIANTS[id]))
		torch.free()
	print("dozor_integration_shots: complete")
	get_tree().quit()


func _capture(label: String) -> void:
	for i: int in range(10):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/dozor/" + label + ".png"
	var err: Error = vp.get_texture().get_image().save_png(path)
	print("DOZOR screenshot ", path, " error=", err)
