extends Node3D
## Export the actual runtime pose in camera space. Never changes profile/grip files.
const WORK := "res://_asset_src/quest_phone/grip/"

func frames(n: int) -> void:
	for i: int in range(n): await get_tree().process_frame

func matrix(t: Transform3D) -> Array:
	return [[t.basis.x.x, t.basis.y.x, t.basis.z.x, t.origin.x],
		[t.basis.x.y, t.basis.y.y, t.basis.z.y, t.origin.y],
		[t.basis.x.z, t.basis.y.z, t.basis.z.z, t.origin.z], [0, 0, 0, 1]]

func _ready() -> void:
	Profile.use_file("user://phone_grip_export.json", true)
	var env := WorldEnvironment.new(); env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.1, 0.13, 0.18); add_child(env)
	var rig := (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(rig)
	var player := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(player); player.set_physics_process(false); player.health.invulnerable = true
	player.inventory.items = [ItemDb.make(PhoneGear.ID, 1)]
	rig.set_target(player); rig.first_person_mode = true
	await frames(35)
	Phone.set_active(true)
	if not Phone.active:
		push_error("Cannot export phone grip: phone did not equip")
		get_tree().quit(1); return
	Phone.preview = true
	await frames(60)
	rig.set_process(false); rig.set_physics_process(false)
	Phone.set_process(false)
	var space := rig._ads_cam.global_transform.affine_inverse()
	var sk := Phone.arms.skeleton
	var bones: Array = []
	for i: int in range(sk.get_bone_count()):
		bones.append({"name":sk.get_bone_name(i),
			"rest":matrix(space * sk.global_transform * sk.get_bone_global_rest(i)),
			"pose":matrix(space * sk.global_transform * sk.get_bone_global_pose(i))})
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(WORK))
	var record := {"bones":bones, "phone":matrix(space * Phone.model.global_transform),
		"source_arms":"res://assets/models/characters/veras_arms.gltf", "pose":"Actual runtime @phone, camera space, metres",
		"grip_profile":HandGripProfiles.values(HandGripProfiles.active(), "@phone", "Right")}
	FileAccess.open(WORK + "phone_pose.json", FileAccess.WRITE).store_string(JSON.stringify(record, " "))
	await RenderingServer.frame_post_draw
	Phone.screen_viewport.get_texture().get_image().save_png(WORK + "phone_display.png")
	print("PHONE GRIP EXPORT ", bones.size(), " bones, phone and screen snapshot")
	Phone.close(); Phone.preview = false
	get_tree().quit()
