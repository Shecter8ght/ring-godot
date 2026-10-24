extends Node
## Проба размера кистей от первого лица (вопрос владельца 2026-10-24 «руки здоровые, оружие в них миниатюрное»):
## ПМ, Glock и ВЕРАС-54 в тире убежища под лампами — наискосок, от бедра и в прицеле — при масштабах кисти
## 1,0 / 0,85 / 0,8 / 0,75 (HandGripPose.scale_override поверх Balance.FPS_HAND_SCALE)
## → docs/screens/hand_scale/hand_<ствол>_<стойка>_<k>.png.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/hand_scale_shots.tscn
## HAND_ONLY=wpn_hg_01,wpn_ar_01 — только эти стволы; HAND_SCALES=1,0.8 — свои масштабы.
## Сравнение листами: python -X utf8 tools/hand_scale_sheet.py

const OUT := "res://docs/screens/hand_scale"
const WEAPONS: Array[String] = ["wpn_hg_01", "wpn_hg_02", "wpn_ar_01"]
## Место в тире (на полтора метра позади стола, чтобы стол не закрывал опущенный ствол) и курс вдоль
## дорожки (к мишеням, +X) — как у veras_gloss_shots.
const SPOT := Vector3(21.6, 0.1, 0.6)
const YAW := PI * 0.5
const PITCH_DEG := -4.0

var _me: Player
var _rig: CameraRig
var _scales: Array[float] = [1.0, 0.85, 0.8, 0.75]


func _ready() -> void:
	if DisplayServer.get_name() == "headless":
		push_error("hand_scale_shots: снимки — только с окном")
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	var custom: PackedStringArray = OS.get_environment("HAND_SCALES").split(",", false)
	if not custom.is_empty():
		_scales.clear()
		for value: String in custom:
			_scales.append(value.to_float())
	var only: PackedStringArray = OS.get_environment("HAND_ONLY").split(",", false)
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://hand_scale_test.json", true)
	Profile.modules.generator = 1
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	await _frames(200)
	var level: Node = get_tree().current_scene
	for canvas: Node in level.find_children("*", "CanvasLayer", true, false):
		(canvas as CanvasLayer).visible = false
	_me = level.get("_player") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if _me == null or _rig == null:
		push_error("hand_scale_shots: нет игрока в убежище")
		get_tree().quit(1)
		return
	_me.global_position = SPOT
	CameraRig.first_person_mode = true
	# окно стенда ловит мышь и колесо того, кто работает за компьютером: взгляд и стойка — только из стенда
	_rig.set_process_unhandled_input(false)
	_me.set_process_unhandled_input(false)
	await _frames(10)
	for id: String in WEAPONS:
		if not only.is_empty() and not id in only:
			continue
		_me.set_range_weapon(WeaponDb.bare_weapon(id, RandomNumberGenerator.new(), [100, 100]))
		await _frames(60)
		_me.carry_low = true
		await _frames(60)
		await _row(id, "low")
		_me.carry_low = false
		await _frames(60)
		await _row(id, "hip")
		Input.action_press("aim")
		await get_tree().create_timer(float(_me.spec().get("aim_time", 0.4)) + 0.4).timeout
		await _row(id, "ads")
		Input.action_release("aim")
		await _frames(40)
		if _rig._viewmodel is ViewmodelClips:
			# проверка магазина удержанием R: левая кисть с магазином перед глазами — крупнее всего в кадре
			Input.action_press("reload")
			await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 1.4).timeout
			await _row(id, "check")
			Input.action_release("reload")
			await get_tree().create_timer(3.0).timeout
	HandGripPose.scale_override = 0.0
	get_tree().quit(0)


## Одна стойка при всех масштабах: кадры отличаются только размером кистей.
func _row(id: String, pose: String) -> void:
	for k: float in _scales:
		HandGripPose.scale_override = k
		# мышь над окном и толчки капсулы сбивают взгляд — ставим его перед каждым кадром
		_me.global_position = Vector3(SPOT.x, _me.global_position.y, SPOT.z)
		_rig._look_yaw = YAW
		_rig._look_pitch = deg_to_rad(PITCH_DEG)
		await _frames(20)
		print("hand_scale_shots: %s %s k=%.2f кисть ×%.3f" % [id, pose, k, _hand_scale_now()])
		await _shot("hand_%s_%s_%03d" % [id, pose, roundi(k * 100.0)])
	HandGripPose.scale_override = 1.0


## Масштаб правой кисти относительно плеча — проверка, что проба дошла до скелета и не копится.
func _hand_scale_now() -> float:
	var skeleton: Skeleton3D = null
	var hand: int = -1
	if _rig._viewmodel is ViewmodelClips:
		skeleton = (_rig._viewmodel as ViewmodelClips)._arm_skel
		hand = skeleton.find_bone("hand.R") if skeleton else -1
	elif _rig._arms and _rig._arms.visible:
		skeleton = _rig._arms.skeleton
		hand = skeleton.find_bone("mixamorig_RightHand")
	if skeleton == null or hand < 0:
		return 0.0
	var upper: int = skeleton.get_bone_parent(skeleton.get_bone_parent(hand))
	return skeleton.get_bone_global_pose(hand).basis.get_scale().x / skeleton.get_bone_global_pose(upper).basis.get_scale().x


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	image.resize(1280, 720, Image.INTERPOLATE_LANCZOS)
	image.save_png(ProjectSettings.globalize_path("%s/%s.png" % [OUT, name]))
