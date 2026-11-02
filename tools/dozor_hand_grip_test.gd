extends Node3D
## Starter pose, edit isolation, runtime/lab hookup, screenshots and native-pose transfer.

var checks: int = 0
var failures: int = 0
var camera: Camera3D
var shots: bool
const OUT := "res://docs/screens/dozor/grip/"
const WORK := "res://_asset_src/dozor/grip/"


func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures += 1
	print("PASS " if ok else "FAIL ", label)


func _ready() -> void:
	shots = DisplayServer.get_name() != "headless"
	HandGripProfiles.storage_path = "user://dozor_hand_test_%d.cfg" % OS.get_process_id()
	WeaponPoseProfiles.storage_path = "user://dozor_pose_test_%d.cfg" % OS.get_process_id()
	Profile.use_file("user://dozor_hand_profile_%d.json" % OS.get_process_id(), true)
	HandGripProfiles.reload()
	WeaponPoseProfiles.reload()
	await get_tree().process_frame
	_stage()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(WORK))
	await _pose("wpn_hg_01")
	await _pose("wpn_hg_02")
	await _lab()
	print("dozor_hand_grip_test: checks=%d failures=%d" % [checks, failures])
	get_tree().quit(1 if failures else 0)


func _stage() -> void:
	var world: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.10, 0.13, 0.17)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_energy = 0.8
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	world.environment = env
	add_child(world)
	for angle: Vector3 in [Vector3(-40, -30, 0), Vector3(-25, 140, 0)]:
		var sun: DirectionalLight3D = DirectionalLight3D.new()
		sun.rotation_degrees = angle
		sun.light_energy = 1.5
		add_child(sun)
	camera = Camera3D.new()
	camera.current = true
	camera.near = 0.005
	camera.fov = 65.0
	add_child(camera)
	get_viewport().mesh_lod_threshold = 0.0


func _pose(id: String) -> void:
	var gun: Node3D = WeaponModels.build(id)
	var arms: FirstPersonArms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	add_child(gun)
	add_child(arms)
	arms.bind_weapon(gun)
	arms.update_pose()
	var right: int = arms.skeleton.find_bone("mixamorig_RightHand")
	var original_right: Transform3D = arms.skeleton.get_bone_global_pose(right)
	var left: Node3D = arms._grips.Left as Node3D
	var original_left: Transform3D = left.transform
	var holder: Node3D = DozorHandGrip.apply(gun, true, id)
	var flashlight: Node3D = DozorAsset.flashlight()
	holder.add_child(flashlight)
	for frame: int in range(120): arms.update_pose()
	check(arms.visible and arms.max_grip_error < 0.001, id + " both hands reach starter grip")
	check(arms.max_length_error < 0.001, id + " bones keep lengths after 120 frames")
	check(arms.skeleton.get_bone_global_pose(right).is_equal_approx(original_right), id + " right pistol hand unchanged")
	check(String((gun.get_meta("hand_grip_keys") as Dictionary).Left) == id + "@dozor", id + " separate flashlight profile")
	check(holder.basis.z.dot(Vector3(0, 0, 1)) > 0.999, id + " beam points forward")
	if OS.get_cmdline_user_args().has("export"):
		_export(gun, arms, id)
	camera.position = Vector3(0, 0.04, -0.46)
	camera.look_at(Vector3(0, -0.06, 0.35))
	await _shot(id + "_fps")
	camera.position = Vector3(0.38, 0.05, 0.32)
	camera.look_at(Vector3(0, -0.09, -0.04))
	await _shot(id + "_inspect")
	camera.position = Vector3(0.18, -0.13, -0.27)
	camera.look_at(holder.global_position)
	await _shot(id + "_left")
	arms.grip_preview = true
	HandGripProfiles.put(arms.grip_profiles, id + "@dozor", "Left", {"position": Vector3(0.02, 0, 0), "rotation": Vector3(0, 15, 0)})
	arms.update_pose()
	DozorHandGrip.follow_edits(gun, arms, holder)
	check(not holder.transform.is_equal_approx(DozorHandGrip.tube()), id + " flashlight follows wrist edits")
	check(arms.skeleton.get_bone_global_pose(right).is_equal_approx(original_right), id + " left edits leave right hand alone")
	DozorHandGrip.apply(gun, false, id)
	check(left.transform.is_equal_approx(original_left) and String((gun.get_meta("hand_grip_keys") as Dictionary).Left) == id, id + " normal two-hand grip restored")
	gun.free()
	arms.free()


func _export(gun: Node3D, arms: FirstPersonArms, id: String) -> void:
	var bones: Array = []
	for i: int in range(arms.skeleton.get_bone_count()):
		bones.append({"name": arms.skeleton.get_bone_name(i), "rest": _matrix(arms.skeleton.global_transform * arms.skeleton.get_bone_global_rest(i)),
			"pose": _matrix(arms.skeleton.global_transform * arms.skeleton.get_bone_global_pose(i))})
	FileAccess.open(WORK + id + "_pose.json", FileAccess.WRITE).store_string(JSON.stringify({"bones": bones}, " "))
	var doc: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	var originals: Dictionary = {}
	for node: Node in gun.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		var source: Material = mesh.get_active_material(0)
		if source is ShaderMaterial and (source as ShaderMaterial).shader.resource_path.ends_with("weapon_wear.gdshader"):
			var shader: ShaderMaterial = source as ShaderMaterial
			var mat: StandardMaterial3D = StandardMaterial3D.new()
			mat.albedo_texture = shader.get_shader_parameter("albedo_tex") as Texture2D
			mat.albedo_color = shader.get_shader_parameter("albedo_color") as Color
			mat.roughness_texture = shader.get_shader_parameter("roughness_tex") as Texture2D
			mat.metallic_texture = shader.get_shader_parameter("metallic_tex") as Texture2D
			mat.normal_texture = shader.get_shader_parameter("normal_tex") as Texture2D
			mat.normal_enabled = mat.normal_texture != null
			mat.roughness = float(shader.get_shader_parameter("roughness"))
			mat.metallic = float(shader.get_shader_parameter("metallic"))
			mat.roughness_texture_channel = _channel(shader.get_shader_parameter("roughness_channel"))
			mat.metallic_texture_channel = _channel(shader.get_shader_parameter("metallic_channel"))
			originals[mesh] = mesh.material_override
			mesh.material_override = mat
	var err: Error = doc.append_from_scene(gun, state)
	if err == OK: err = doc.write_to_filesystem(state, ProjectSettings.globalize_path(WORK + id + "_items.gltf"))
	for mesh: MeshInstance3D in originals: mesh.material_override = originals[mesh]
	check(err == OK, id + " native item reference exported")


func _channel(value: Variant) -> int:
	var best: int = 0
	if value != null:
		for i: int in range(1, 4):
			if float(value[i]) > float(value[best]): best = i
	return best


func _matrix(t: Transform3D) -> Array:
	return [[t.basis.x.x, t.basis.y.x, t.basis.z.x, t.origin.x], [t.basis.x.y, t.basis.y.y, t.basis.z.y, t.origin.y], [t.basis.x.z, t.basis.y.z, t.basis.z.z, t.origin.z], [0, 0, 0, 1]]


func _lab() -> void:
	var lab: WeaponPoseLab = (load("res://scenes/debug/weapon_pose_lab.tscn") as PackedScene).instantiate() as WeaponPoseLab
	add_child(lab)
	await _frames(50)
	var idx: int = -1
	for i: int in range(lab._catalog.size()):
		if String(lab._catalog[i].id) == "wpn_hg_02" and lab._catalog[i].has("handheld"): idx = i
	check(idx >= 0, "lab offers pistol + DOZOR")
	if idx >= 0:
		lab._select_weapon(idx)
		await _frames(30)
		var actor: Player = lab._player
		check(actor.handheld_light_on and actor.handheld_flashlight.emitting(), "production FPS creates handheld flashlight")
		check(lab._hand_key() == "wpn_hg_02@dozor", "lab edits separate left profile")
		if actor.handheld_flashlight.model:
			var light: SpotLight3D = actor.handheld_flashlight.model.find_child("Flashlight*", true, false) as SpotLight3D
			check(light.visible, "CameraRig does not extinguish handheld light")
			for mesh: Node in actor.handheld_flashlight.model.find_children("*", "MeshInstance3D", true, false):
				if mesh.name == "Glow": continue # Remote-facing glow stays outside the own-hands layer.
				check((mesh as MeshInstance3D).layers == 2, "flashlight visible in FPS layer " + String(mesh.name))
		var edit: Dictionary = HandGripProfiles.values(lab._hand_draft, lab._hand_key(), "Left")
		edit.position = Vector3(0.012, 0, 0)
		lab._change_hand(edit)
		await _frames(3)
		check(lab._save(), "lab saves editable flashlight hand profile")
		HandGripProfiles.reload()
		check(is_equal_approx((HandGripProfiles.values(HandGripProfiles.active(), "wpn_hg_02@dozor", "Left").position as Vector3).x, 0.012), "saved DOZOR wrist edit survives reload")
		check((HandGripProfiles.values(HandGripProfiles.active(), "wpn_hg_02", "Left").position as Vector3).is_zero_approx(), "ordinary pistol left profile remains unchanged")
		actor.reload_timer = 1.0
		await _frames(3)
		check(not actor.handheld_flashlight.emitting(), "reload releases flashlight grip and hides light")
		actor.reload_timer = 0.0
		await _frames(3)
		check(actor.handheld_flashlight.emitting(), "flashlight grip returns after reload")
		actor._toggle_tac("light")
		await _frames(5)
		check(not actor.handheld_light_on and not actor.handheld_flashlight.emitting(), "T off returns ordinary grip")
	lab.queue_free()
	await _frames(2)


func _frames(n: int) -> void:
	for i: int in range(n): await get_tree().process_frame


func _shot(label: String) -> void:
	if not shots: return
	await _frames(10)
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT + label + ".png")
