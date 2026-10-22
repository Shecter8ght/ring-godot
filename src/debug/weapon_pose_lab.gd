class_name WeaponPoseLab
extends Node3D
## Отдельная песочница с настоящими Player/CameraRig. Пока открыт интерфейс, поза зафиксирована;
## F6 возвращает обычное управление, стрельбу и перезарядку с текущим черновиком.

var _draft: Dictionary = {}
var _catalog: Array[Dictionary] = []
var _weapon_index: int = 0
var _pose: String = "hip"
var _editing: bool = true
var _dirty: bool = false

@onready var _player: Player = $Player
@onready var _rig: CameraRig = $CameraRig
@onready var _panel: WeaponPosePanel = $Interface/Panel
@onready var _hint: Label = $Interface/Hint/Label


func _ready() -> void:
	add_to_group("esc_windows")
	Net.enter_scene("weapon_pose_lab")
	_draft = WeaponPoseProfiles.snapshot()
	_panel.use_in_game.set_pressed_no_signal(WeaponPoseProfiles.enabled())
	_rig.set_target(_player)
	_rig._compass.visible = false
	_player._camera_rig = _rig
	_player.health.invulnerable = true
	_player.set_physics_process(false)
	_rig.weapon_pose_preview = true
	_build_catalog()
	_panel.weapon_selected.connect(_select_weapon)
	_panel.pose_selected.connect(_select_pose)
	_panel.stance_selected.connect(_select_stance)
	_panel.values_changed.connect(_change_values)
	_panel.comparison_changed.connect(func(_original: bool) -> void: _sync_preview())
	_panel.save_requested.connect(_save)
	_panel.restore_requested.connect(_restore)
	_panel.reset_requested.connect(_reset_pose)
	_panel.play_requested.connect(func() -> void: _set_editing(false))
	_panel.back_requested.connect(_back)
	_panel.copy_requested.connect(_copy)
	_panel.use_in_game.toggled.connect(func(_on: bool) -> void: _dirty = true)
	_select_weapon(_weapon_index)
	for x: float in [-4.0, 0.0, 4.0]:
		var target: Target = Target.new()
		target.name = "Target_%d" % int(x + 4.0)
		$Targets.add_child(target)
		target.position = Vector3(x, 0.0, 8.0 + absf(x))
		target.look_at(_player.global_position, Vector3.UP, true)
	_set_editing(true)
	_panel.set_status("Черновик. Сохранение применяет все выбранные позы.")


func is_open() -> bool:
	return _editing


func _build_catalog() -> void:
	for id: String in WeaponDb.items():
		if not WeaponDb.is_weapon(id):
			continue
		var item: Dictionary = WeaponDb.items()[id]
		_catalog.append({"id": id, "preset": "", "name": String(item.get("name", id))})
	for key: Variant in WeaponDb.sandbox():
		var preset: Dictionary = WeaponDb.preset(String(key))
		if preset.is_empty():
			continue
		var id: String = String(preset.weapon)
		var item: Dictionary = WeaponDb.items().get(id, {})
		_catalog.append({"id": id, "preset": String(key), "name": String(item.get("name", id)) + " · сборка " + String(key)})
	for index: int in range(_catalog.size()):
		_panel.weapons.add_item(String(_catalog[index].name))
		if String(_catalog[index].id) == "wpn_ar_01" and String(_catalog[index].preset) == "":
			_weapon_index = index


func _select_weapon(index: int) -> void:
	if index < 0 or index >= _catalog.size():
		return
	_weapon_index = index
	_panel.weapons.select(index)
	var entry: Dictionary = _catalog[index]
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 54
	var weapon: Dictionary = WeaponDb.bare_weapon(String(entry.id), rng, [100, 100]) if String(entry.preset) == "" else WeaponDb.make_weapon(String(entry.preset), rng, [100, 100])
	_player.set_range_weapon(weapon)
	_player.grenade_equipped = false
	_player.aim_cant = false
	_apply_preview_pose()
	_refresh_values()


func _select_pose(index: int) -> void:
	_pose = WeaponPoseProfiles.POSES[index]
	_panel.poses.select(index)
	# Лёжа опущенная стойка игровым правилом недоступна.
	if _pose == "low" and _player.stance == Player.Stance.PRONE:
		_select_stance(0)
	_apply_preview_pose()
	_refresh_values()


func _select_stance(index: int) -> void:
	match index:
		1: _player.stance = Player.Stance.CROUCH
		2: _player.stance = Player.Stance.PRONE
		_: _player.stance = Player.Stance.STAND
	_panel.stances.select(index)
	_player._apply_stance()
	_player._eye_tick_ready = false
	if index == 2 and _pose == "low":
		_select_pose(0)
	_apply_preview_pose()


func _apply_preview_pose() -> void:
	_player.carry_low = _pose == "low"
	if _editing:
		_player.aiming = _pose == "ads"
	_player.velocity = Vector3.ZERO
	_player.lean = 0.0


func _refresh_values() -> void:
	_panel.show_values(WeaponPoseProfiles.values(_draft, _player.weapon_id, _pose))
	_sync_preview()


func _sync_preview() -> void:
	_rig.weapon_pose_profiles = {} if _panel.compare.button_pressed else _draft


func _change_values(position: Vector3, rotation: Vector3) -> void:
	WeaponPoseProfiles.put(_draft, _player.weapon_id, _pose, position, rotation)
	_dirty = true
	_panel.set_status("Есть несохранённые изменения · Ctrl+S — сохранить всё")
	_sync_preview()


func _save() -> bool:
	var result: Error = WeaponPoseProfiles.save_profiles(_draft, _panel.use_in_game.button_pressed)
	if result != OK:
		_panel.set_status("Не удалось сохранить: " + error_string(result))
		return false
	_dirty = false
	_panel.set_status("Сохранено. " + ("Позы используются в игре." if _panel.use_in_game.button_pressed else "Применение в игре выключено; на стенде виден черновик."))
	return true


func _restore() -> void:
	WeaponPoseProfiles.reload()
	_draft = WeaponPoseProfiles.snapshot()
	_panel.use_in_game.set_pressed_no_signal(WeaponPoseProfiles.enabled())
	_panel.compare.set_pressed_no_signal(false)
	_dirty = false
	_refresh_values()
	_panel.set_status("Загружены последние сохранённые настройки.")


func _reset_pose() -> void:
	_panel.compare.set_pressed_no_signal(false)
	_change_values(Vector3.ZERO, Vector3.ZERO)
	_refresh_values()
	_panel.set_status("Эта поза сброшена. Нажми «Сохранить», чтобы оставить сброс.")


func _copy() -> void:
	var value: Dictionary = WeaponPoseProfiles.values(_draft, _player.weapon_id, _pose)
	var position: Vector3 = value.position as Vector3
	var rotation: Vector3 = value.rotation as Vector3
	DisplayServer.clipboard_set(JSON.stringify({"weapon": _player.weapon_id, "pose": _pose,
		"position_cm": [position.x * 100.0, position.y * 100.0, position.z * 100.0],
		"rotation_deg": [rotation.x, rotation.y, rotation.z]}, "\t"))
	_panel.set_status("Значения этой позы скопированы в буфер обмена.")


func _set_editing(editing: bool) -> void:
	_editing = editing
	_panel.visible = editing
	_player.set_physics_process(not editing)
	_apply_preview_pose()
	var focus: Control = get_viewport().gui_get_focus_owner()
	if focus:
		focus.release_focus()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if editing else Input.MOUSE_MODE_CAPTURED
	_update_hint()


func _process(delta: float) -> void:
	if _editing:
		_player._tick_stance_eye(delta)
	_update_hint()


func _update_hint() -> void:
	if _editing:
		_hint.text = "F6 — проверить в движении  ·  F7 — сравнить с исходной позой\nCtrl+S — сохранить  ·  Пол — клетки 1 м"
	else:
		_hint.text = "F6 — вернуть настройки  ·  WASD — движение  ·  ПКМ — прицел  ·  ЛКМ — огонь  ·  R — перезарядка\nКолесо — поднять / опустить  ·  C / Z — сесть / лечь  ·  Shift — бег  ·  Esc — меню"


func _input(event: InputEvent) -> void:
	if PauseMenu.shown or not event is InputEventKey or event.is_echo() or not event.is_pressed():
		return
	var key: InputEventKey = event as InputEventKey
	if key.keycode == KEY_F6 or key.physical_keycode == KEY_F6:
		_set_editing(not _editing)
		get_viewport().set_input_as_handled()
	elif key.keycode == KEY_F7 or key.physical_keycode == KEY_F7:
		_panel.compare.button_pressed = not _panel.compare.button_pressed
		get_viewport().set_input_as_handled()
	elif _editing and key.ctrl_pressed and (key.keycode == KEY_S or key.physical_keycode == KEY_S):
		_save()
		get_viewport().set_input_as_handled()
	elif _editing and event.is_action_pressed("pause"):
		_set_editing(false)
		get_viewport().set_input_as_handled()


func _back() -> void:
	if not _dirty:
		_go_to_menu()
		return
	var dialog: ConfirmationDialog = ConfirmationDialog.new()
	dialog.title = "Несохранённые настройки"
	dialog.dialog_text = "Изменения на стенде ещё не сохранены. Выйти в меню?"
	dialog.ok_button_text = "Выйти без сохранения"
	dialog.cancel_button_text = "Остаться"
	dialog.confirmed.connect(_go_to_menu)
	dialog.canceled.connect(dialog.queue_free)
	add_child(dialog)
	dialog.popup_centered()


func _go_to_menu() -> void:
	Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню")
