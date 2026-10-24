extends Node
## ADS: мир без увеличения, кратность только в линзе, колесо и состояние экземпляра.
## tools/godot.cmd --headless res://tools/ads_optics_test.tscn
## С окном и аргументом -- capture — контрольные снимки в docs/screens/ads_optics_*.png.

const WEAPON: String = "wpn_ar_01"
const TEST_PROFILE: String = "user://ads_optics_test.json"
const TEST_MOUSE_DEVICE: int = 166

var _player: Player
var _rig: CameraRig
var _fails: int = 0
var _revision: int = 0
var _slot: String
var _capture: bool = false


## Оконный прогон получает только мышь теста: обычное движение и прокрутка не меняют кадр.
func _input(event: InputEvent) -> void:
	if event is InputEventMouse and event.device != TEST_MOUSE_DEVICE:
		get_viewport().set_input_as_handled()


func _ready() -> void:
	Profile.use_file(TEST_PROFILE, true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_capture = DisplayServer.get_name() != "headless" and OS.get_cmdline_user_args().has("capture")
	await get_tree().process_frame
	var level: Node = (load("res://scenes/levels/mall_map.tscn") as PackedScene).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	for i: int in range(60):
		await get_tree().physics_frame
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.health.hp = 100000.0
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_rig._look_pitch = deg_to_rad(-2.0)
	_slot = String(WeaponDb.sandbox()[0])
	CameraRig.first_person_mode = true
	Settings.set_sens(1.0, 1.0)
	Settings.set_sens_ads(1.0)
	await _frames(2)
	await _fov_cases()
	await _wheel_cases()
	_state_cases()
	Input.action_release("aim")
	print("ads_optics_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _equip(optic: String, mount: String = "optic_primary", extra: Dictionary = {}) -> void:
	Input.action_release("aim")
	var mods: Dictionary = extra.duplicate(true)
	if optic != "":
		mods[mount] = {"id": optic, "dur": 100.0}
	_revision += 1
	var entry: Dictionary = {"id": WEAPON, "n": 1, "dur": 100.0, "mods": mods, "sight": "primary", "rev": _revision,
		"mag": {"id": WeaponDb.default_mag(WEAPON), "ammo": WeaponDb.default_ammo(String(WeaponDb.weapon(WEAPON).caliber)), "rounds": 30}}
	entry = WeaponBuild.upgrade(entry)[0]
	_player.sandbox_weapons[_slot] = entry
	_player.weapon_slot = ""
	_player._switch(_slot, false)
	await _frames(3)


func _fov_cases() -> void:
	var optics: Array[String] = ["", "optic_rd_01", "optic_holo_01", "optic_2x_01", "optic_4x_01", "optic_8x_01", "optic_12x_01", "optic_lpvo_01"]
	for horizontal: float in [50.0, 90.0, 120.0]:
		Settings.set_fov_h(horizontal)
		for optic: String in optics:
			await _equip(optic)
			var expected: float = Settings.fps_fov_v()
			var hip: Transform3D = _rig._viewmodel.transform
			var stable: bool = is_equal_approx(_rig._ads_cam.fov, expected)
			if horizontal == 90.0 and optic == "optic_rd_01":
				await _save("hip")
			Input.action_press("aim")
			for frame: int in range(40):
				await get_tree().physics_frame
				await get_tree().process_frame
				stable = stable and is_equal_approx(_rig._ads_cam.fov, expected)
			var stats: Dictionary = _player.spec()
			_check("FOV %.0f°, %s: вскидка сохраняет обзор" % [horizontal, optic if optic != "" else "механика"], stable)
			_check("оружие подведено к глазам", not hip.origin.is_equal_approx(_rig._viewmodel.transform.origin))
			if bool(stats.scoped):
				_check("линза работает", _rig.scope_active)
				if _rig.scope_active:
					_check_magnification(float(stats.zoom))
				else:
					print("    aim=%s, progress=%.3f, ocular=%s, obstruction=%.3f, arms=%s, pos=%s, model=%s" % [_player.aiming, _player.aim_progress(), _rig._viewmodel.has_meta("ocular"), _player.weapon_obstruction, _rig._arms.arms_clear, _player.global_position, _rig._viewmodel_id])
			else:
				_check("механика/коллиматор без отдельного увеличения", not _rig.scope_active)
			if horizontal == 90.0 and optic in ["", "optic_rd_01", "optic_4x_01"]:
				await _save("iron" if optic == "" else ("reddot" if optic == "optic_rd_01" else "fixed4"))
			Input.action_release("aim")
			await _frames(2)
			_check("выход из ADS сохраняет обзор", is_equal_approx(_rig._ads_cam.fov, expected))
	Settings.set_fov_h(90.0)
	# Дальний окуляр и 32× требуют угла меньше 1°: масштаб не должен упираться в ограничение FOV.
	await _equip("optic_12x_01", "top_front")
	Input.action_press("aim")
	await _frames(40)
	_check("оптика на цевье работает", _rig.scope_active)
	if _rig.scope_active:
		_check_magnification(12.0)
		_rig._update_scope(32.0)
		_check_magnification(32.0)
		_check("камера линзы допускает угол меньше 1°", _rig.scope_fov() < 1.0)


## Измеряем проекцию одной мировой точки на основном экране и внутри окна оптики.
func _check_magnification(expected: float) -> void:
	var cam: Camera3D = _rig._ads_cam
	var centre: Vector3 = cam.global_position - cam.global_basis.z * 20.0
	var point: Vector3 = centre + cam.global_basis.x * 0.02
	var outside: float = (cam.unproject_position(point) - cam.unproject_position(centre)).x
	var inside: float = (_rig._scope_cam.unproject_position(point) - _rig._scope_cam.unproject_position(centre)).x
	inside *= _rig._scope_view.size.x / float(_rig._scope_vp.size.x)
	var measured: float = inside / outside
	_check("масштаб в линзе %.0f× (измерено %.3f×)" % [expected, measured], absf(measured - expected) < 0.03)


func _wheel_cases() -> void:
	await _equip("optic_lpvo_01")
	Input.action_press("aim")
	await _frames(40)
	_check("старый LPVO без выбранной кратности остаётся на 5×", is_equal_approx(float(_player.spec().zoom), 5.0))
	var model_id: int = _rig._viewmodel.get_instance_id()
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_check("колесо вверх: 6×", is_equal_approx(float(_player.spec().zoom), 6.0))
	_check_magnification(6.0)
	var sens6: float = _rig.ads_sens()
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_check("выше 6× колесо не выходит", is_equal_approx(float(_player.spec().zoom), 6.0))
	await _save("lpvo6")
	for step: int in range(7):
		await _wheel(MOUSE_BUTTON_WHEEL_DOWN)
	_check("колесо вниз ограничено 1×", is_equal_approx(float(_player.spec().zoom), 1.0))
	_check_magnification(1.0)
	_check("чувствительность следует кратности", is_equal_approx(_rig.ads_sens(), sens6 * 6.0))
	_check("колесо сохраняет модель и анимации", model_id == _rig._viewmodel.get_instance_id())
	_check("текущая кратность и колесо видны в HUD", "1×" in _rig._weapon_label.text and "колесо" in _rig._weapon_label.text)
	await _save("lpvo1")
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_check("середина диапазона: 3×", is_equal_approx(float(_player.spec().zoom), 3.0))
	PauseMenu.shown = true
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	PauseMenu.shown = false
	await _frames(2)
	_check("открытое меню блокирует колесо оптики", is_equal_approx(float(_player.spec().zoom), 3.0))
	_player.aim_cant = true
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_player.aim_cant = false
	_check("с завалом кратность не меняется", is_equal_approx(float(_player.spec().zoom), 3.0))
	Input.action_release("aim")
	await _frames(2)
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_check("от бедра колесо не меняет кратность", is_equal_approx(float(_player.spec().zoom), 3.0))
	_player._switch(String(WeaponDb.sandbox()[1]), false)
	await _frames(2)
	_player._switch(_slot, false)
	await _frames(2)
	_check("смена оружия сохраняет 3×", is_equal_approx(float(_player.spec().zoom), 3.0))
	# Новая ревизия (перезарядка/обвес) перечитывает сохранённый выбор из экземпляра.
	_player.flush_weapon_state()
	Gear._bump(_player.sandbox_weapons[_slot])
	_check("перечитывание экземпляра сохраняет 3×", is_equal_approx(float(_player.spec().zoom), 3.0))
	var remembered: Dictionary = _player.weapon_entry().duplicate(true)
	_player.inventory.equipment = {"primary": remembered}
	_player.inventory.apply_weapon_state("primary", _player._ws_state(_slot))
	_check("хост принимает выбранные 3×", is_equal_approx(float(WeaponStats.compute(_player.inventory.equipment.primary).zoom), 3.0))
	await _equip("optic_4x_01")
	Input.action_press("aim")
	await _frames(40)
	await _wheel(MOUSE_BUTTON_WHEEL_UP)
	_check("фиксированные 4× колесом не меняются", is_equal_approx(float(_player.spec().zoom), 4.0))
	await _equip("optic_lpvo_01", "top_front", {"optic_offset": "optic_offset_rd_01"})
	Input.action_press("aim")
	await _frames(40)
	_player._toggle_sight()
	await _frames(20)
	await _wheel(MOUSE_BUTTON_WHEEL_DOWN)
	_check("угловой коллиматор без увеличения", not _rig.scope_active and not bool(_player.spec().scoped))
	_player._toggle_sight()
	await _frames(20)
	_check("возвращение к основной оптике сохраняет 5×", is_equal_approx(float(_player.spec().zoom), 5.0))


func _state_cases() -> void:
	var entry: Dictionary = _player.inventory.equipment.primary
	var rounds: int = Gear.total_rounds(entry)
	var state: Dictionary = {"id": String(entry.id), "rev": int(entry.get("rev", 0)), "optic_zoom": {"optic_primary": 10000.0, "missing": 32.0}}
	_player.inventory.apply_weapon_state("primary", state)
	entry = _player.inventory.equipment.primary
	_check("хост ограничивает кратность диапазоном прицела", is_equal_approx(float(WeaponStats.compute(entry).zoom), 6.0))
	_check("состояние кратности сохраняет боезапас", Gear.total_rounds(entry) == rounds)
	state["rev"] = int(state.rev) + 1
	state.optic_zoom.optic_primary = 1.0
	_player.inventory.apply_weapon_state("primary", state)
	_check("устаревшая ревизия не меняет прицел", is_equal_approx(float(WeaponStats.compute(_player.inventory.equipment.primary).zoom), 6.0))
	Profile.equipment = _player.inventory.equipment.duplicate(true)
	Profile.save()
	Profile.use_file(TEST_PROFILE, false)
	var saved: Dictionary = Profile.equipment.primary
	_check("кратность переживает сохранение профиля", is_equal_approx(float(WeaponStats.compute(saved).zoom), 6.0))
	var stripped: Array = Gear.strip(saved, "mod:optic_primary")
	_check("снятый прицел сохраняет выбранные 6×", is_equal_approx(float((stripped[1] as Dictionary).get("zoom", 0.0)), 6.0))
	var fitted: Array = Gear.fit(stripped[0], stripped[1], "optic_primary")
	_check("повторная установка сохраняет 6×", String(fitted[2]) == "" and is_equal_approx(float(WeaponStats.compute(fitted[0]).zoom), 6.0))
	var range_def: Dictionary = {"zoom": 4.0, "zoom_min": 4.0, "zoom_max": 32.0}
	_check("данные поддерживают диапазон 4–32×", is_equal_approx(WeaponStats.zoom_value(range_def, {"zoom": 16.0}), 16.0)
		and is_equal_approx(WeaponStats.zoom_value(range_def, {"zoom": 100.0}), 32.0))


func _wheel(button: MouseButton) -> void:
	var event: InputEventMouseButton = InputEventMouseButton.new()
	event.device = TEST_MOUSE_DEVICE
	event.button_index = button
	event.pressed = true
	event.position = get_viewport().get_visible_rect().size * 0.5
	Input.parse_input_event(event)
	await _frames(2)


func _frames(count: int) -> void:
	for frame: int in range(count):
		await get_tree().physics_frame
		await get_tree().process_frame


func _save(label: String) -> void:
	if not _capture:
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/ads_optics_%s.png" % label))


func _check(label: String, passed: bool) -> void:
	if not passed:
		_fails += 1
	print("  [%s] %s" % ["ok" if passed else "FAIL", label])
