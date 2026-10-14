extends Node
## ВЕРАС-54, левая кисть на ходу: с рукоятками под цевьём (свои клипы и поправка IK поверх клипа)
## кости руки не копят масштаб — стоя, на ходу, при входе в прицел и выходе из него, — и кисть
## остаётся у рукоятки.
## tools/godot.cmd --headless res://tools/veras_hand_test.tscn

const ID := "wpn_ar_01"

var _player: Player
var _camera: CameraRig
var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://veras_hand_test.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
	_player = get_tree().get_first_node_in_group("players") as Player
	_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_player.health.hp = 100000.0
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.5).timeout
	var setups: Array = [
		["без рукоятки", {}],
		["ВАРН V1", {"underbarrel": {"id": "grip_vertical_01"}}],
		["ВАРН V2", {"underbarrel": {"id": "grip_offset_01"}}],
		["ВАРН V2, другой паз", {"underbarrel": {"id": "grip_offset_01", "slot": 0}}],
		["угловая", {"underbarrel": {"id": "grip_angled_01"}}],
		["угловая, другой паз", {"underbarrel": {"id": "grip_angled_01", "slot": 0}}],
		["рукоятка на удлинителе", {"underbarrel": {"id": "mount_rail_ext_01", "slot": 2}, "underbarrel/rail": {"id": "grip_angled_01", "slot": 1}}],
	]
	for pair: Array in setups:
		await _run(String(pair[0]), pair[1] as Dictionary)
	Input.action_release("move_forward")
	Input.action_release("aim")
	print("veras_hand_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _run(title: String, mods: Dictionary) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods,
		"mag": {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}, "sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.6).timeout
	var vm := _camera._viewmodel as ViewmodelClips
	if vm == null:
		_check(title + ": вьюмодель с клипами", false, "")
		return
	var worst: float = _stretch(vm)
	# стоим, идём вперёд, на ходу в прицел и обратно — несколько раз
	for step: int in range(6):
		if step >= 1:
			Input.action_press("move_forward")
		if step >= 2:
			if step % 2 == 0:
				Input.action_press("aim")
			else:
				Input.action_release("aim")
		for i: int in range(90):
			await get_tree().process_frame
			worst = maxf(worst, _stretch(vm))
	Input.action_release("move_forward")
	Input.action_release("aim")
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_check("%s: кости левой руки без масштаба" % title, worst < 0.0005, "отклонение %.4f, набор «%s», сдвиг %s" % [worst, vm._set, str(vm._grip_shift)])
	# и кисть осталась у рукоятки: запястье не дальше ладони от места, где она стоит
	var worn: Dictionary = _player.weapon_mods
	var under: String = WeaponGrips._under_key(worn)
	if under != "":
		for i: int in range(30):
			await get_tree().process_frame
		var at: Vector3 = WeaponMods.point_frame(vm.frame, "veras54", worn, under).origin
		var wrist: Vector3 = vm.frame.global_transform.affine_inverse() * (vm._arm_skel.global_transform * vm._arm_skel.get_bone_global_pose(vm._arm_bones[2]).origin)
		var gap: float = Vector2(wrist.y - at.y, wrist.z - at.z).length()
		_check("%s: кисть у рукоятки" % title, gap < 0.14, "%.0f мм" % (gap * 1000.0))


## Наибольшее отклонение масштаба костей рук от единицы (в осях скелета).
func _stretch(vm: ViewmodelClips) -> float:
	var sk: Skeleton3D = vm._arm_skel
	var worst: float = 0.0
	for bone: int in range(sk.get_bone_count()):
		var s: Vector3 = sk.get_bone_global_pose(bone).basis.get_scale()
		worst = maxf(worst, maxf(absf(s.x - 1.0), maxf(absf(s.y - 1.0), absf(s.z - 1.0))))
	return worst


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
