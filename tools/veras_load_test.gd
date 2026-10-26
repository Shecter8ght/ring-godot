extends "res://tools/weapon_ik_test.gd"
## ВЕРАС с полной навеской: эффекты ЛЦУ/фонаря не расширяют твёрдый габарит,
## руки стабильны, у настоящей стены оружие складывается. С окном — кадры хвата.

const LOADED: Dictionary = {
	"optic_primary": {"id": "optic_lpvo_01", "slot": 1},
	"optic_primary#2": {"id": "mount_offset45_01", "slot": 7},
	"optic_primary#2/rail": {"id": "optic_holo_01"},
	"underbarrel": {"id": "grip_vertical_01", "slot": 3},
	"side_left": {"id": "tac_combo_01"},
	"side_right": {"id": "tac_flashlight_01"},
	"muzzle": {"id": "muzzle_supp_545_01"},
}


func _ready() -> void:
	Engine.max_fps = 90
	Profile.use_file("user://veras_load_test.json", true)
	RaidEvents.enabled = false
	CameraRig._settings_loaded = true
	CameraRig.first_person_mode = true
	_floor_and_light()
	_wall = _obstacle("Wall", Vector3(6, 3, 0.2), Vector3(0, 1.5, 0.62))
	_wall.collision_layer = 0
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(_player)
	_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(_camera)
	_camera.set_process_unhandled_input(false)
	_camera.set_process_input(false)
	_camera._target = _player
	_player._camera_rig = _camera
	_player.global_position = Vector3(0, 0.02, -2)
	_player.health.invulnerable = true
	await _frames(40)
	_camera._look_yaw = 0.0
	_camera._look_pitch = 0.0
	for label: String in ["bare", "laser", "light", "loaded"]:
		var mods: Dictionary = LOADED.duplicate(true) if label == "loaded" else {"side_left": {"id": "tac_laser_01"}} if label == "laser" else {"side_right": {"id": "tac_flashlight_01"}} if label == "light" else {}
		await _weapon("wpn_ar_01", mods)
		await _frames(45)
		var vm: ViewmodelClips = _camera._viewmodel as ViewmodelClips
		_check(label + ": imported clips", vm != null)
		if vm == null:
			continue
		print(label, " bounds=", _camera.weapon_clearance.bounds)
		_check(label + ": free weapon visible", vm.visible and _player.weapon_obstruction < 0.001)
		_check(label + ": physical dimensions", _camera.weapon_clearance.bounds.size.length() < 1.5)
		await _stable_hand(label, vm)
		if label in ["bare", "loaded"]:
			await _capture_pose(label + "_hip")
		var clearance: WeaponClearance = _camera.weapon_clearance
		clearance._refresh_bounds(vm)
		var before: AABB = clearance.bounds
		var effects: Array[Dictionary] = []
		# Луч и световой спрайт меняют размер при включении и во время перезарядки.
		# Их удалённые точки не должны влиять на габарит собранного оружия.
		for effect: Node in vm.find_children("*", "Node3D", true, false):
			if effect is LaserSight:
				var laser: LaserSight = effect as LaserSight
				effects.append({"laser": laser, "beam": laser._beam.transform, "dot": laser._dot.global_transform, "visible": laser.visible})
				laser.set_process(false)
				laser.visible = true
				laser._beam.scale.z = 100.0
				laser._beam.position.z = 50.0
				laser._dot.global_position = Vector3(100, 100, 100)
				laser._dot.scale = Vector3.ONE * 2.0
			elif effect is MeshInstance3D and effect.name == "Glow":
				effects.append({"glow": effect, "scale": (effect as Node3D).scale})
				(effect as Node3D).scale = Vector3.ONE * 100.0
		clearance._refresh_bounds(vm)
		_check(label + ": light effects leave bounds unchanged", before.position.is_equal_approx(clearance.bounds.position) and before.size.is_equal_approx(clearance.bounds.size))
		for saved: Dictionary in effects:
			if saved.has("laser"):
				var laser: LaserSight = saved.laser as LaserSight
				laser._beam.transform = saved.beam
				laser._dot.global_transform = saved.dot
				laser.visible = bool(saved.visible)
				laser.set_process(true)
			else:
				(saved.glow as Node3D).scale = saved.scale
		Input.action_press("aim")
		await _frames(90)
		_check(label + ": ADS visible in free space", vm.visible and _player.weapon_obstruction < 0.001)
		if label in ["bare", "loaded"]:
			await _capture_pose(label + "_ads")
		Input.action_release("aim")
	# Обвесы как твёрдые детали по-прежнему учитываются у настоящей стены.
	await _weapon("wpn_ar_01", LOADED.duplicate(true))
	_wall.collision_layer = Hitscan.LAYER_WORLD
	_player.global_position = Vector3(0, 0.02, 0.05)
	await _frames(90)
	_check("loaded: real wall folds weapon", _player.weapon_obstruction > 0.12)
	_player.global_position = Vector3(0, 0.02, -2)
	await _frames(90)
	_check("loaded: moving away restores weapon", _camera._viewmodel.visible and _player.weapon_obstruction < 0.001)
	var vm: ViewmodelClips = _camera._viewmodel as ViewmodelClips
	_player._start_reload(_player.spec())
	_check("loaded: reload starts", _player.reload_timer > 0.0)
	var action_bounds: float = 0.0
	for i: int in range(400):
		await get_tree().process_frame
		action_bounds = maxf(action_bounds, _camera.weapon_clearance.bounds.size.length())
		if _player.reload_timer <= 0.0 and not vm.is_busy():
			break
	_check("loaded: reload uses physical bounds", action_bounds < 1.5)
	await _frames(45)
	_check("loaded: visible after reload", vm.visible and _player.weapon_obstruction < 0.001)
	await _stable_hand("after reload", vm)
	print("VERAS_LOAD_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


func _stable_hand(label: String, vm: ViewmodelClips) -> void:
	var last: Vector3 = vm._arm_skel.get_bone_global_pose(vm._arm_bones[2]).origin
	var jump: float = 0.0
	for i: int in range(60):
		await get_tree().process_frame
		var current: Vector3 = vm._arm_skel.get_bone_global_pose(vm._arm_bones[2]).origin
		jump = maxf(jump, current.distance_to(last))
		last = current
	print(label, " hand step=", jump)
	_check(label + ": idle hand stable", jump < 0.005)


func _capture_pose(label: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	var suffix: String = OS.get_environment("VERAS_LOAD_SUFFIX")
	get_viewport().get_texture().get_image().save_png("res://docs/screens/veras_load_%s%s.png" % [label, suffix])
