extends Node
## ВЕРАС ↔ Glock: затраты переключения, повторное использование моделей и плавный выход из ADS.

var _player: Player
var _rig: CameraRig
var _fails: int = 0


func _input(event: InputEvent) -> void:
	if event is InputEventMouse:
		get_viewport().set_input_as_handled()


func _ready() -> void:
	Profile.use_file("user://weapon_switch_test.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = (load("res://scenes/levels/f1_market.tscn") as PackedScene).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	for frame: int in range(60):
		await get_tree().physics_frame
		await get_tree().process_frame
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_player.health.hp = 100000.0
	_player.set_process(false)
	_player.set_physics_process(false)
	_rig.set_process(false)
	Settings.set_fov_h(90.0)
	var keys: Array = _player.weapon_keys()
	var ids: Dictionary = {}
	var worst_warm: float = 0.0
	for cycle: int in range(8):
		var key: String = String(keys[cycle % 2])
		var started: int = Time.get_ticks_usec()
		_player._switch(key, false)
		_player._physics_process(1.0 / 60.0)
		var switched: int = Time.get_ticks_usec()
		_player._update_hand()
		var world_done: int = Time.get_ticks_usec()
		_rig._process_ads(_player, 1.0 / 60.0, 0.0)
		var finished: int = Time.get_ticks_usec()
		var elapsed: float = (finished - started) / 1000.0
		print("switch %d %s: state %.2f ms, world %.2f ms, view %.2f ms, total %.2f ms" % [cycle, _player.weapon_id, (switched - started) / 1000.0, (world_done - switched) / 1000.0, (finished - world_done) / 1000.0, elapsed])
		var current: Array[int] = [_player._weapon_model.get_instance_id(), _rig._viewmodel.get_instance_id()]
		if ids.has(key):
			_check("готовые модели %s используются повторно" % _player.weapon_id, current == ids[key])
			worst_warm = maxf(worst_warm, elapsed)
		else:
			ids[key] = current
		await get_tree().process_frame
		await get_tree().process_frame
		if DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
	_check("повторное переключение укладывается в 16 мс", worst_warm < 16.0)
	_player._switch(String(keys[0]), false)
	_tick()
	Input.action_press("aim")
	for frame: int in range(45):
		_tick()
	var aimed: Transform3D = _rig._viewmodel.transform
	Input.action_release("aim")
	_tick()
	var released: Transform3D = _rig._viewmodel.transform
	for frame: int in range(45):
		_tick()
	var lowered: Transform3D = _rig._viewmodel.transform
	var full: float = aimed.origin.distance_to(lowered.origin)
	var first: float = aimed.origin.distance_to(released.origin)
	print("ADS lowering: first %.4f m of %.4f m" % [first, full])
	_check("первый кадр опускания не переносит оружие сразу к бедру", full > 0.02 and first < full * 0.25 and released.origin.distance_to(lowered.origin) > full * 0.5)
	_check("при отпускании ПКМ боевая точность сразу перестаёт быть ADS", is_zero_approx(_player.aim_progress()))
	# Быстрое повторное нажатие меняет направление перехода от текущей позы.
	Input.action_press("aim")
	for frame: int in range(10):
		_tick()
	var partial: Transform3D = _rig._viewmodel.transform
	Input.action_release("aim")
	_tick()
	_check("короткое нажатие ПКМ тоже опускает плавно", partial.origin.distance_to(_rig._viewmodel.position) < full * 0.25)
	Input.action_press("aim")
	var reverse: Transform3D = _rig._viewmodel.transform
	_tick()
	_check("повторная вскидка продолжается с текущей позы", reverse.origin.distance_to(_rig._viewmodel.position) < full * 0.25)
	Input.action_release("aim")
	# Спрятанные модели остановлены; слот/износ/рисунок сборки корректно различаются кэшем.
	_player._switch(String(keys[1]), false)
	_tick()
	var old_rifle: Node3D = _rig._viewmodel_cache.values().filter(func(n: Node3D) -> bool: return n is ViewmodelClips and (n as ViewmodelClips).weapon_id == "wpn_ar_01")[0]
	_check("неактивный автомат скрыт и не обрабатывается", not old_rifle.visible and old_rifle.process_mode == Node.PROCESS_MODE_DISABLED)
	var fresh_key: String = WeaponCondition.model_key("wpn_ar_01", {"optic_primary": {"id": "optic_rd_01", "slot": 0}}, 100.0)
	var moved_key: String = WeaponCondition.model_key("wpn_ar_01", {"optic_primary": {"id": "optic_rd_01", "slot": 3}}, 100.0)
	_check("разные пазы не берут чужую готовую сборку", fresh_key != moved_key)
	for optic: String in ["optic_rd_01", "optic_holo_01", "optic_2x_01", "optic_4x_01", "optic_8x_01"]:
		_player.set_sandbox_mods(String(keys[0]), {"optic_primary": optic})
		_player._switch(String(keys[0]), false)
		_tick()
		_player._switch(String(keys[1]), false)
		_tick()
		await get_tree().process_frame
	_check("память готовых моделей ограничена", _rig._viewmodel_cache.size() <= Balance.WEAPON_VISUAL_CACHE and _player._weapon_model_cache.size() <= Balance.WEAPON_VISUAL_CACHE)
	print("weapon_switch_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _tick() -> void:
	_player._physics_process(1.0 / 60.0)
	_player._update_hand()
	_rig._process_ads(_player, 1.0 / 60.0, 0.0)


func _check(label: String, passed: bool) -> void:
	if not passed:
		_fails += 1
	print("  [%s] %s" % ["ok" if passed else "FAIL", label])
