extends Node
## ВЕРАС-54 от первого лица в настоящей игре: руки и клипы из Blender (ViewmodelClips).
## tools/godot.cmd res://tools/veras_shots.tscn  (с окном) → docs/screens/veras_*.png
## Кадры: у бедра, в прицеле, фазы тактической (12 патронов) и полной (0) перезарядки, проверка
## магазина (держать R), в прицеле с коллиматором на верхней планке. VERAS_ONLY=имя,имя — выборочно.
## Обвесы готовыми моделями: рукоятки ВАРН V1 / V2 (свой хват и клипы) и глушитель — у бедра и сбоку
## (veras_varn_*), задержка «гильза не вышла» и её устранение (veras_jam_*), карты состояний 60 / 20
## (veras_state_*). VERAS_PART=grips|jam|states — только эта часть.

const ID := "wpn_ar_01"
const OUT := "res://docs/screens/"

var _player: Player
var _camera: CameraRig
var _only: PackedStringArray = []
var _failures: int = 0
## Камера глаз игрока: свои камеры снимков возвращают вид ей.
var _eye: Camera3D


func _ready() -> void:
	_only = OS.get_environment("VERAS_ONLY").split(",", false)
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
		(enemy as Node3D).visible = false
	_player = get_tree().get_first_node_in_group("players") as Player
	_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_player.health.hp = 100000.0
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.5).timeout
	_camera._look_yaw = -PI * 0.5
	await _equip({})
	if not _camera._viewmodel is ViewmodelClips:
		push_error("veras_shots: в руках не вьюмодель с клипами (нет ассета?)")
		get_tree().quit(1)
		return
	var vm := _camera._viewmodel as ViewmodelClips
	print("veras_shots: клипы ", vm._anim.get_animation_list(), " патронов-узлов ", vm._rounds.size())
	_eye = get_viewport().get_camera_3d()
	var part: String = OS.get_environment("VERAS_PART")
	if part != "":
		if part == "grips":
			await _grips()
		elif part == "jam":
			await _jam()
		elif part == "states":
			await _states()
		elif part == "hand":
			await _hand()
		elif part == "cant":
			await _cant()
		elif part == "fast":
			await _fast_reload()
		elif part == "check":
			await _check_hold()
		print("veras_shots: ошибок ", _failures)
		get_tree().quit(1 if _failures else 0)
		return
	await _shot("veras_hip")
	var fr: Transform3D = vm.global_transform.affine_inverse() * vm.frame.global_transform
	print("veras_shots: рама у бедра ", fr.origin, " ось ", fr.basis.z, " sight_h ", vm.frame.get_meta("sight_h"), " ads ", vm.ads_transform())
	Input.action_press("aim")
	await get_tree().create_timer(float(_player.spec().aim_time) + 0.3).timeout
	await _shot("veras_ads")
	Input.action_press("fire")
	await get_tree().create_timer(0.03).timeout
	await _shot("veras_ads_fire")
	Input.action_release("fire")
	Input.action_release("aim")
	await get_tree().create_timer(0.6).timeout
	# тактическая: в магазине остались патроны
	await _set_rounds(12)
	await _reload([0.12, 0.3, 0.55, 0.75, 0.95], "veras_reload")
	# полная: пусто
	await _set_rounds(0)
	await _reload([0.2, 0.5, 0.72, 0.78, 0.84], "veras_reload_empty")
	# проверка магазина — держать R
	await _set_rounds(17)
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 0.15).timeout
	Input.action_release("reload")
	var check_len: float = vm._anim.get_animation(vm._clip_name("check")).length
	for t: float in [0.3, 0.45, 0.6]:
		await get_tree().create_timer(check_len * 0.15).timeout
	await _shot("veras_check_mid")
	await get_tree().create_timer(check_len * 0.4).timeout
	# коллиматор на верхней планке
	await _equip({"optic_primary": {"id": "optic_rd_01"}})
	Input.action_press("aim")
	await get_tree().create_timer(float(_player.spec().aim_time) + 0.4).timeout
	await _shot("veras_ads_reddot")
	Input.action_release("aim")
	# рукоятка по пазам нижней планки: левая кисть переезжает к ней (поправка поверх клипа)
	for grip_slot: int in [0, 4]:
		await _equip({"underbarrel": {"id": "grip_vertical_01", "slot": grip_slot}})
		await get_tree().create_timer(0.5).timeout
		await _shot("veras_grip_slot%d" % grip_slot)
	# мировая модель (у напарников, мародёров, на земле): своя камера, модель боком на высоте 2 м
	var world: Node3D = WeaponModels.build(ID, {}, 1)
	add_child(world)
	var at := _player.global_position + Vector3(0, 2.0, 0)
	world.global_transform = Transform3D(Basis(Vector3.UP, PI * 0.5), at)
	var shot_cam := Camera3D.new()
	add_child(shot_cam)
	shot_cam.fov = 30.0
	shot_cam.look_at_from_position(at + Vector3(0.0, 0.25, 2.2), at + Vector3(0, 0.03, 0))
	shot_cam.current = true
	print("veras_shots: мировая модель, ассет ", world.get_meta("asset_loaded", false), " дуло ", world.get_meta("muzzle", Vector3.ZERO))
	await get_tree().create_timer(0.3).timeout
	await _shot("veras_world_model")
	shot_cam.current = false
	shot_cam.queue_free()
	_eye.current = true
	await get_tree().process_frame
	await _grips()
	await _jam()
	await _states()
	await _cant()
	await _fast_reload()
	await _check_hold()
	print("veras_shots: ошибок ", _failures)
	get_tree().quit(1 if _failures else 0)


## Рукоятки ВАРН и глушитель: модель, хват левой и клипы набора — у бедра и сбоку, слева.
func _grips() -> void:
	for pair: Array in [["varn_v1", "grip_vertical_01"], ["varn_v2", "grip_offset_01"]]:
		await _equip({"underbarrel": {"id": pair[1]}, "muzzle": {"id": "muzzle_supp_545_01"}})
		var vm := _camera._viewmodel as ViewmodelClips
		# наборы клипов под рукоятки в игру не внесены (позы кистей правит владелец): есть набор в модели —
		# он берётся, нет — левая держит цевьё позади рукоятки
		var has_set: bool = vm != null and vm._anim.has_animation("idle_" + String(pair[0]))
		_check(String(pair[0]) + ": набор клипов — %s" % ("свой" if has_set else "нет, рука на цевье"), vm != null and vm._set == (String(pair[0]) if has_set else ""))
		_check(String(pair[0]) + ": модель рукоятки из ассета", vm != null and vm.find_child(String(pair[0]), true, false) != null)
		_check(String(pair[0]) + ": модель глушителя из ассета", vm != null and vm.find_child("supp_veras", true, false) != null)
		await get_tree().create_timer(0.5).timeout
		await _shot("veras_%s_hip" % pair[0])
		await _side("veras_%s_side" % pair[0])
		await _set_rounds(12)
		await _reload([0.1, 0.3, 0.92], "veras_%s_reload" % pair[0], true)
	# рукоятка в другом пазу: кисть едет вместе с ней
	await _equip({"underbarrel": {"id": "grip_vertical_01", "slot": 0}})
	await get_tree().create_timer(0.6).timeout
	await _side("veras_varn_v1_slot0_side")


## Левая кисть крупно: на цевье (без рукоятки) и на рукоятках — слева, снизу-слева и спереди.
func _hand() -> void:
	for pair: Array in [["bare", {}], ["varn_v1", {"underbarrel": {"id": "grip_vertical_01"}}], ["varn_v2", {"underbarrel": {"id": "grip_offset_01"}}]]:
		await _equip(pair[1])
		await get_tree().create_timer(0.5).timeout
		await _side("veras_hand_%s_left" % pair[0], false, 0.16, 0.38)
		await _side("veras_hand_%s_low" % pair[0], false, 0.16, 0.3, -0.3)
		await _side("veras_hand_%s_right" % pair[0], true, 0.16, 0.38)


## «С завалом»: СКМ в прицеле кладёт автомат на 45° затвором к глазам — и с одной оптикой на планке;
## выстрел двигает затвор; следующее нажатие возвращает основной прицел.
func _cant() -> void:
	await _equip({"optic_primary": {"id": "optic_4x_01"}, "side_right": {"id": "tac_laser_01", "laser": true}})
	await _set_rounds(30)
	var vm := _camera._viewmodel as ViewmodelClips
	Input.action_press("aim")
	await get_tree().create_timer(float(_player.spec().aim_time) + 0.4).timeout
	await _shot("veras_cant_0_scope")
	_player.toggle_sight()
	_check("завал: включается и с одним прицелом", _player.aim_cant)
	await get_tree().create_timer(float(Balance.SIGHT_SWITCH_SEC) + 0.3).timeout
	var roll: float = rad_to_deg(vm.global_basis.y.signed_angle_to(_eye.global_basis.y, _eye.global_basis.z))
	_check("завал: автомат повёрнут на 45° (%.0f°)" % absf(roll), absf(absf(roll) - 45.0) < 4.0)
	await _shot("veras_cant_1_on")
	# затвор при выстреле: посреди хода он отведён
	var rest: Vector3 = vm._weapon_skel.get_bone_rest(vm._bolt).origin
	var far: float = 0.0
	Input.action_press("fire")
	for i in range(12):
		await get_tree().process_frame
		far = maxf(far, vm._weapon_skel.get_bone_pose_position(vm._bolt).distance_to(rest))
	Input.action_release("fire")
	_check("выстрел: затвор отходит (%.0f мм)" % (far * 1000.0), far > 0.03)
	await _shot("veras_cant_2_fire")
	await get_tree().create_timer(0.3).timeout
	_player.toggle_sight()
	_check("завал: второе нажатие — основной прицел", not _player.aim_cant)
	await get_tree().create_timer(float(Balance.SIGHT_SWITCH_SEC) + 0.3).timeout
	await _shot("veras_cant_3_back")
	Input.action_release("aim")
	await get_tree().create_timer(0.4).timeout


## Быстрая перезарядка (два быстрых R): свой клип, старый магазин виден отдельно и вылетает.
func _fast_reload() -> void:
	await _equip({})
	await _set_rounds(12)
	var vm := _camera._viewmodel as ViewmodelClips
	for i in range(2):
		Input.action_press("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_release("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
	_check("быстрая: два R — быстрая перезарядка", _player._reload_fast and _player.reload_timer > 0.0)
	await get_tree().process_frame
	await get_tree().process_frame
	_check("быстрая: идёт свой клип", vm._fast and vm._clip == "reload_fast", vm._clip)
	var total: float = _player.reload_timer
	var elapsed: float = 0.0
	var spare_seen: bool = false
	for f: float in [0.3, 0.42, 0.47, 0.52, 0.62]:
		await get_tree().create_timer(maxf(0.0, total * f - elapsed)).timeout
		elapsed = total * f
		spare_seen = spare_seen or (not vm._spare_parts.is_empty() and vm._spare_parts[0].visible)
		await _shot("veras_fast_%02d" % int(f * 100))
	_check("быстрая: старый магазин виден отдельно", spare_seen)
	await get_tree().create_timer(total - elapsed + 0.5).timeout
	_check("быстрая: закончена, старый магазин скрыт, патронов 30", _player.ammo == 30 and not vm._spare_parts[0].visible and vm._clip == "")


## Проверка магазина с удержанием: пока R держат — магазин перед глазами, мышь поворачивает кисть.
func _check_hold() -> void:
	await _equip({})
	await _set_rounds(17)
	var vm := _camera._viewmodel as ViewmodelClips
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 1.6).timeout
	_check("проверка: магазин стоит перед глазами, пока держат R", _player.mag_inspect and vm._holding)
	await _shot("veras_check_hold")
	await get_tree().create_timer(2.5).timeout
	_check("проверка: держим долго — всё ещё стоит", vm._holding and vm._clip == vm._clip_name("check"))
	for turn: Array in [["left", Vector2(-1.0, 0.0)], ["right", Vector2(1.0, 0.0)], ["up", Vector2(0.4, -1.0)]]:
		_player.inspect_turn = turn[1]
		await get_tree().create_timer(0.6).timeout
		await _shot("veras_check_turn_%s" % turn[0])
	_check("проверка: кисть с магазином повёрнута", vm._turn.length() > 0.8)
	Input.action_release("reload")
	await get_tree().create_timer(0.3).timeout
	_check("проверка: отпустили — магазин убирается", not _player.mag_inspect and not vm._holding and vm._clip != "")
	await get_tree().create_timer(2.2).timeout
	_check("проверка: магазин на месте, руки на оружии", vm._clip == "" and _player.ammo == 17, vm._clip)


## Задержка: гильза торчит в окне, затвор недозакрыт; R — передёрнуть, гильза выпадает.
func _jam() -> void:
	await _equip({})
	await _set_rounds(14)
	var vm := _camera._viewmodel as ViewmodelClips
	_player._ws[_player.weapon_slot]["jam"] = true
	await get_tree().create_timer(0.3).timeout
	_check("задержка: гильза видна", vm._jam_case != null and vm._jam_case.visible)
	var bolt_x: float = vm._weapon_skel.get_bone_pose_position(vm._bolt).distance_to(vm._weapon_skel.get_bone_rest(vm._bolt).origin)
	_check("задержка: затвор недозакрыт (%.0f мм)" % (bolt_x * 1000.0), bolt_x > 0.02 and bolt_x < 0.045)
	var case_at: Vector3 = vm.frame.global_transform.affine_inverse() * vm._jam_case.global_position
	_check("задержка: гильза в окне коробки %s" % case_at, case_at.distance_to(Vector3(-0.011, 0.077, 0.144)) < 0.01)
	await _shot("veras_jam_hold")
	await _side("veras_jam_hold_right", true)
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	for i in range(30):
		if _player.reload_timer > 0.0:
			break
		await get_tree().physics_frame
	_check("задержка: R запускает устранение", _player._reload_kind == "clear" and _player.reload_timer > 0.0)
	var total: float = _player.reload_timer
	var elapsed: float = 0.0
	for f: float in [0.35, 0.5, 0.58, 0.7]:
		await get_tree().create_timer(maxf(0.0, total * f - elapsed)).timeout
		elapsed = total * f
		_check("устранение: клип jam_clear на %d%%" % int(f * 100), vm._clip == "jam_clear")
		await _shot("veras_jam_clear_%02d" % int(f * 100))
	await get_tree().create_timer(total - elapsed + 0.5).timeout
	_check("задержка устранена: гильзы нет, патроны на месте", not _player.is_jammed() and not vm._jam_case.visible and _player.ammo == 14)
	await _shot("veras_jam_done")


## Карты состояний автомата и обвесов: 60 % и 20 %.
func _states() -> void:
	for dur: float in [100.0, 60.0, 20.0]:
		await _equip({"underbarrel": {"id": "grip_vertical_01", "dur": dur}, "muzzle": {"id": "muzzle_supp_545_01", "dur": dur}}, dur)
		await get_tree().create_timer(0.4).timeout
		await _side("veras_state_%d" % int(dur))
		await _side("veras_state_%d_muzzle" % int(dur), false, 0.42, 0.45)


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_failures += 1
	print("veras_shots: ", "ok   " if ok else "ПРОВАЛ ", label, "  (" + detail + ")" if detail != "" and not ok else "")


## Снимок оружия в руках со стороны: слева (или справа — окно выброса) от стрелка.
func _side(label: String, right: bool = false, forward: float = 0.0, distance: float = 0.62, up: float = 0.12) -> void:
	if not _only.is_empty() and not label in _only:
		return
	var t: Transform3D = _eye.global_transform
	var cam := Camera3D.new()
	add_child(cam)
	cam.fov = 40.0
	cam.near = 0.02
	var k: float = 1.0 if right else -1.0
	var target: Vector3 = t.origin - t.basis.z * (0.42 + forward) + t.basis.x * 0.13 - t.basis.y * 0.13
	cam.look_at_from_position(target + t.basis.x * k * distance + t.basis.y * up - t.basis.z * 0.1, target, t.basis.y)
	cam.current = true
	await get_tree().process_frame
	await _shot(label)
	cam.current = false
	cam.queue_free()
	_eye.current = true
	await get_tree().process_frame


func _equip(mods: Dictionary, dur: float = 100.0) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	var magazine: String = WeaponDb.default_mag(ID)
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": dur, "mods": mods,
		"mag": {"id": magazine, "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}, "sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.4).timeout


## Патроны в магазине: и у игрока, и в состоянии ствола (игра сверяет их каждый кадр).
func _set_rounds(n: int) -> void:
	_player.ammo = n
	if _player._ws.has(_player.weapon_slot):
		_player._ws[_player.weapon_slot]["rounds"] = n
	await get_tree().physics_frame


## Перезарядка по R и кадры на долях её времени.
func _reload(fractions: Array, prefix: String, side: bool = false) -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	# перезарядка начинается по отпусканию R (удержание — проверка магазина): дождаться старта
	for i in range(30):
		if _player.reload_timer > 0.0:
			break
		await get_tree().physics_frame
	var total: float = _player.reload_timer
	var elapsed: float = 0.0
	for f: float in fractions:
		await get_tree().create_timer(maxf(0.0, total * f - elapsed)).timeout
		elapsed = total * f
		if side:
			await _side("%s_%02d" % [prefix, int(f * 100)])
		else:
			await _shot("%s_%02d" % [prefix, int(f * 100)])
	await get_tree().create_timer(maxf(0.0, total - elapsed) + 0.4).timeout


func _shot(label: String) -> void:
	if not _only.is_empty() and not label in _only:
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT + label + ".png"))
	print("veras_shots: ", label)
