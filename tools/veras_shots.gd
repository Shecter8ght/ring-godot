extends Node
## ВЕРАС-54 от первого лица в настоящей игре: руки и клипы из Blender (ViewmodelClips).
## tools/godot.cmd res://tools/veras_shots.tscn  (с окном) → docs/screens/veras_*.png
## Кадры: у бедра, в прицеле, фазы тактической (12 патронов) и полной (0) перезарядки, проверка
## магазина (держать R), в прицеле с коллиматором на верхней планке. VERAS_ONLY=имя,имя — выборочно.

const ID := "wpn_ar_01"
const OUT := "res://docs/screens/"

var _player: Player
var _camera: CameraRig
var _only: PackedStringArray = []
var _failures: int = 0


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
	print("veras_shots: ошибок ", _failures)
	get_tree().quit(1 if _failures else 0)


func _equip(mods: Dictionary) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	var magazine: String = WeaponDb.default_mag(ID)
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods,
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
func _reload(fractions: Array, prefix: String) -> void:
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
		await _shot("%s_%02d" % [prefix, int(f * 100)])
	await get_tree().create_timer(maxf(0.0, total - elapsed) + 0.4).timeout


func _shot(label: String) -> void:
	if not _only.is_empty() and not label in _only:
		return
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT + label + ".png"))
	print("veras_shots: ", label)
