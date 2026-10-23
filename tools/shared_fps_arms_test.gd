extends Node3D
## Один внешний вид рук у процедурных хватов, клипов ВЕРАСа, ракетницы и гранаты.
## Проверка точек хвата и независимости плеч дополняется кадрами настоящих моделей.

var _failures: int = 0
var _arms: FirstPersonArms
var _camera: Camera3D
var _records: Array[Dictionary] = []
var _shots: bool = false
var _output: String = "res://docs/screens/shared_fps_arms/"


func _ready() -> void:
	_shots = DisplayServer.get_name() != "headless"
	DirAccess.make_dir_recursive_absolute(_output)
	FileAccess.open(_output + ".gdignore", FileAccess.WRITE).close()
	_stage()
	_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	add_child(_arms)
	_check("общие руки загружены", _arms.skeleton != null)
	_check("размер ладони взят из новой сетки", _arms._palm_offsets.size() == 2)
	_check("геометрия Persona отсутствует", _arms.find_children("Human*", "MeshInstance3D", true, false).is_empty())
	for raw: Variant in WeaponDb.ids("weapons"):
		var id: String = String(raw)
		await _weapon(id, {})
	for grip: String in ["grip_vertical_01", "grip_angled_01", "grip_compact_01"]:
		await _weapon("wpn_ar_02", {"underbarrel": {"id": grip}})
	var grenade: GrenadeModel = GrenadeModel.create(true)
	add_child(grenade)
	_arms.unbind_weapon()
	grenade.position = Vector3(0.13, -0.10, -0.38)
	_check("граната использует руки ВЕРАСа", grenade.hands_skeleton != null)
	grenade.prepare(0.0)
	await _capture("grenade")
	grenade.free()
	FileAccess.open(_output + "report.json", FileAccess.WRITE).store_string(JSON.stringify({"failures": _failures, "cases": _records}, "\t"))
	print("shared_fps_arms_test: cases=", _records.size(), " failures=", _failures)
	get_tree().quit(1 if _failures else 0)


func _stage() -> void:
	var environment: WorldEnvironment = WorldEnvironment.new()
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.19, 0.22, 0.26)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color.WHITE
	env.ambient_light_energy = 0.8
	environment.environment = env
	add_child(environment)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -40, 0)
	light.light_energy = 1.8
	add_child(light)
	_camera = Camera3D.new()
	_camera.near = 0.02
	_camera.fov = Balance.FPS_VIEWMODEL_FOV
	add_child(_camera)
	_camera.current = true


func _weapon(id: String, mods: Dictionary) -> void:
	var model: Node3D
	if ViewmodelClips.available(id):
		model = ViewmodelClips.create(id, mods)
	else:
		model = WeaponModels.build(id, mods)
	add_child(model)
	_camera.transform = Transform3D.IDENTITY
	var entry: Dictionary = {"id": id, "mods": mods, "clipped": model is ViewmodelClips}
	var tag: String = id + ("_" + String(mods.underbarrel.id) if mods.has("underbarrel") else "")
	if model is ViewmodelClips:
		_arms.unbind_weapon()
		var vm: ViewmodelClips = model as ViewmodelClips
		var idle: String = String((vm.config.get("clips", {}) as Dictionary).get("idle", "idle"))
		vm._anim.play(idle)
		vm._anim.seek(0.0, true)
		var hand: Node3D = model.find_child("FPS_Arms*", true, false) as Node3D
		_check(tag + " имеет собственные руки", hand != null)
	else:
		model.rotation.y = PI
		model.position = Balance.FPS_HIP_POSE
		_arms.bind_weapon(model)
		_arms.update_pose()
		_check(tag + " руки видимы", _arms.visible)
		_check(tag + " запястья достигают хвата", _arms.max_grip_error < 0.001)
		_check(tag + " кости не растянуты", _arms.max_length_error < 0.001)
		entry["grip_error"] = _arms.max_grip_error
		entry["length_error"] = _arms.max_length_error
		if id == "wpn_hg_02":
			_independent_hands(model)
	await _capture(tag)
	if id in ["wpn_hg_01", "wpn_hg_02", "wpn_ar_02", "wpn_sg_01", "wpn_sr_01"]:
		var marker: Node3D = model.find_child("RightGrip", true, false) as Node3D
		if marker:
			_camera.position = marker.global_position + Vector3(0.24, 0.09, 0.16)
			_camera.look_at(marker.global_position)
			await _capture(tag + "_right")
	_records.append(entry)
	_arms.unbind_weapon()
	model.free()


func _independent_hands(model: Node3D) -> void:
	var sk: Skeleton3D = _arms.skeleton
	var right: int = sk.find_bone("mixamorig_RightHand")
	var before: Transform3D = sk.get_bone_global_pose(right)
	var target: Node3D = Node3D.new()
	add_child(target)
	target.global_transform = (model.find_child("LeftGrip", true, false) as Node3D).global_transform
	target.position.y += 0.08
	_arms.set_hand_target("Left", target, 1.0)
	for frame: int in range(120):
		_arms.update_pose()
	_check("левая рука в действии не двигает правую", sk.get_bone_global_pose(right).origin.distance_to(before.origin) < 0.0001 and sk.get_bone_global_pose(right).basis.is_equal_approx(before.basis))
	_check("повторная подгонка не растягивает кости", _arms.max_length_error < 0.001)
	_arms.set_hand_target("Left", null, 0.0)
	_arms.update_pose()
	target.free()


func _capture(tag: String) -> void:
	if not _shots:
		return
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(_output + tag + ".png")


func _check(label: String, passed: bool) -> void:
	if not passed:
		_failures += 1
	print("  [%s] %s" % ["ok" if passed else "FAIL", label])
