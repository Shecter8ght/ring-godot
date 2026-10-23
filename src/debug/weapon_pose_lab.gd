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
var _hand_draft: Dictionary = {}
var _inspector: HandGripInspector

@onready var _player: Player = $Player
@onready var _rig: CameraRig = $CameraRig
@onready var _panel: WeaponPosePanel = $Interface/Panel
@onready var _hint: Label = $Interface/Hint/Label


func _ready() -> void:
	add_to_group("esc_windows")
	Net.enter_scene("weapon_pose_lab")
	_draft = WeaponPoseProfiles.snapshot()
	_hand_draft = HandGripProfiles.snapshot()
	_panel.use_in_game.set_pressed_no_signal(WeaponPoseProfiles.enabled())
	_panel.grip.use_in_game.set_pressed_no_signal(HandGripProfiles.enabled())
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
	_panel.grip.values_changed.connect(_change_hand)
	_panel.grip.side_selected.connect(func(_index: int) -> void: _refresh_hand_values())
	_panel.grip.reset_requested.connect(_reset_hand)
	_panel.grip.use_in_game.toggled.connect(func(_on: bool) -> void:
		_dirty = true
		_panel.set_status("Есть несохранённые изменения · Ctrl+S"))
	_create_inspector()
	_select_weapon(_weapon_index)
	for x: float in [-4.0, 0.0, 4.0]:
		var target: Target = Target.new()
		target.name = "Target_%d" % int(x + 4.0)
		$Targets.add_child(target)
		target.position = Vector3(x, 0.0, 8.0 + absf(x))
		target.look_at(_player.global_position, Vector3.UP, true)
	_set_editing(true)
	_panel.set_status("Черновик. Хват и положение сохраняются для каждого оружия.")


func is_open() -> bool:
	return _editing


func _build_catalog() -> void:
	for id: String in WeaponDb.items():
		if not WeaponDb.is_weapon(id):
			continue
		var item: Dictionary = WeaponDb.items()[id]
		_catalog.append({"id": id, "preset": "", "name": String(item.get("name", id))})
		# Рукоятки доступны и без готового пресета из песочницы.
		for raw_grip: Variant in WeaponDb.ids("attachments"):
			var grip_id: String = String(raw_grip)
			if not String(WeaponDb.attachment(grip_id).get("look", "")).begins_with("grip_"):
				continue
			var probe: Dictionary = {"id": id, "mods": {}}
			var installed: Array = WeaponBuild.insert(probe, "underbarrel", {"id": grip_id, "dur": 100.0})
			if String(installed[2]) == "":
				_catalog.append({"id": id, "preset": "", "grip": grip_id, "name": String(item.get("name", id)) + " · " + String(WeaponDb.attachment(grip_id).get("name", grip_id))})
	for key: Variant in WeaponDb.sandbox():
		var preset: Dictionary = WeaponDb.preset(String(key))
		if preset.is_empty():
			continue
		var id: String = String(preset.weapon)
		var item: Dictionary = WeaponDb.items().get(id, {})
		_catalog.append({"id": id, "preset": String(key), "name": String(item.get("name", id)) + " · сборка " + String(key)})
	for index: int in range(_catalog.size()):
		_panel.weapons.add_item(String(_catalog[index].name))
		if String(_catalog[index].id) == "wpn_ar_01" and String(_catalog[index].preset) == "" and not _catalog[index].has("grip"):
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
	if entry.has("grip"):
		weapon = WeaponBuild.insert(weapon, "underbarrel", {"id": String(entry.grip), "dur": 100.0})[0] as Dictionary
	_player.set_range_weapon(weapon)
	# На открытом стенде физика Player остановлена, поэтому обновляем видимые поля
	# сразу: обычный игровой тик ещё не успел перенести обвес и магазин из экземпляра.
	var held: Dictionary = _player.weapon_entry()
	_player.weapon_mods = (held.get("mods", {}) as Dictionary).duplicate(true)
	_player.weapon_mag = WeaponMods.mag_state(held)
	_player.weapon_condition = WeaponCondition.percent(held)
	_player.weapon_engraving = WeaponMark.marks(held)
	_player.grenade_equipped = false
	_player.aim_cant = false
	_panel.grip.sides.set_item_disabled(0, _player.weapon_id == "signal_launcher")
	if _player.weapon_id == "signal_launcher":
		_panel.grip.sides.select(1)
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
	_refresh_hand_values()
	_sync_preview()


func _sync_preview() -> void:
	_rig.weapon_pose_profiles = {} if _panel.compare.button_pressed else _draft
	var profiles: Dictionary = {} if _panel.compare.button_pressed else _hand_draft
	_rig._arms.grip_preview = true
	_rig._arms.grip_profiles = profiles
	if _rig._viewmodel is ViewmodelClips:
		var clips: ViewmodelClips = _rig._viewmodel as ViewmodelClips
		clips.grip_preview = true
		clips.grip_profiles = profiles


func _hand_side() -> String:
	return HandGripProfiles.SIDES[_panel.grip.sides.selected]


func _hand_key() -> String:
	return String(HandGripProfiles.keys(_player.weapon_id, _player.weapon_mods)[_hand_side()])


func _refresh_hand_values() -> void:
	_panel.grip.show_values(HandGripProfiles.values(_hand_draft, _hand_key(), _hand_side()))
	var under: String = WeaponGrips._under_key(_player.weapon_mods)
	var attachment: String = WeaponDb.mod_id(_player.weapon_mods.get(under, {}))
	var name: String = String(WeaponDb.attachment(attachment).get("name", attachment))
	_panel.grip.context.text = "Правая кисть — для этого оружия." if _hand_side() == "Right" else ("Левая кисть · " + name if attachment != "" else "Левая кисть · без устройства под цевьём.")
	if _player.weapon_id == "signal_launcher":
		_panel.grip.context.text += " Ракетницу держат одной рукой; левая помогает только при перезарядке."
	_panel.grip.context.visible = (_hand_side() == "Left" and attachment != "") or _player.weapon_id == "signal_launcher"


func _change_hand(value: Dictionary) -> void:
	HandGripProfiles.put(_hand_draft, _hand_key(), _hand_side(), value)
	_panel.compare.set_pressed_no_signal(false)
	_dirty = true
	_panel.set_status("Есть несохранённые изменения хвата · Ctrl+S — сохранить всё")
	_sync_preview()


func _reset_hand() -> void:
	_change_hand({})
	_refresh_hand_values()
	_panel.set_status("Эта кисть сброшена. Сохрани, чтобы оставить исходный хват.")


func _change_values(position: Vector3, rotation: Vector3) -> void:
	WeaponPoseProfiles.put(_draft, _player.weapon_id, _pose, position, rotation)
	_dirty = true
	_panel.set_status("Есть несохранённые изменения · Ctrl+S — сохранить всё")
	_sync_preview()


func _save() -> bool:
	var result: Error = WeaponPoseProfiles.save_profiles(_draft, _panel.use_in_game.button_pressed)
	if result == OK:
		result = HandGripProfiles.save_profiles(_hand_draft, _panel.grip.use_in_game.button_pressed)
	if result != OK:
		_panel.set_status("Не удалось сохранить: " + error_string(result))
		return false
	_dirty = false
	_panel.set_status("Сохранено. " + ("Хват используется в игре." if _panel.grip.use_in_game.button_pressed else "Применение хвата в игре выключено; на стенде виден черновик."))
	return true


func _restore() -> void:
	WeaponPoseProfiles.reload()
	HandGripProfiles.reload()
	_draft = WeaponPoseProfiles.snapshot()
	_hand_draft = HandGripProfiles.snapshot()
	_panel.use_in_game.set_pressed_no_signal(WeaponPoseProfiles.enabled())
	_panel.grip.use_in_game.set_pressed_no_signal(HandGripProfiles.enabled())
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
	if _panel.tabs.current_tab == 1:
		var hand: Dictionary = HandGripProfiles.values(_hand_draft, _hand_key(), _hand_side())
		var fingers: Dictionary = {}
		for finger: String in HandGripProfiles.FINGERS:
			var entry: Dictionary = hand.fingers[finger]
			var bend: Vector3 = entry.bend as Vector3
			fingers[finger] = {"bend_deg": [bend.x, bend.y, bend.z], "spread_deg": entry.spread, "twist_deg": entry.twist}
		var shift: Vector3 = (hand.position as Vector3) * 100.0
		var turn: Vector3 = hand.rotation as Vector3
		DisplayServer.clipboard_set(JSON.stringify({"weapon": _player.weapon_id, "profile": _hand_key(), "side": _hand_side(),
			"position_cm": [shift.x, shift.y, shift.z], "rotation_deg": [turn.x, turn.y, turn.z], "fingers": fingers}, "\t"))
		_panel.set_status("Хват этой кисти скопирован в буфер обмена.")
		return
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
	_sync_preview()
	_update_inspector()
	_update_hint()


func _update_hint() -> void:
	if _editing:
		_hint.text = "F6 — проверить в движении  ·  F7 — исходный хват и положение  ·  F8 — осмотр\nCtrl+S — сохранить  ·  Вкладка «Хват рук» — кисти и пальцы"
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
	elif _editing and (key.keycode == KEY_F8 or key.physical_keycode == KEY_F8):
		_panel.tabs.current_tab = 1
		_panel.grip.views.select(1 if _panel.grip.views.selected == 0 else 0)
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


func _create_inspector() -> void:
	_inspector = HandGripInspector.new()
	_inspector.name = "GripInspector"
	_inspector.set_anchors_preset(Control.PRESET_FULL_RECT)
	_inspector.offset_left = 492.0
	_inspector.offset_top = 108.0
	_inspector.offset_right = -20.0
	_inspector.offset_bottom = -30.0
	$Interface.add_child(_inspector)


func _update_inspector() -> void:
	var mode: int = _panel.grip.views.selected
	_inspector.visible = _editing and _panel.tabs.current_tab == 1 and mode != 0
	if not _inspector.visible or not is_instance_valid(_rig._viewmodel):
		return
	var sk: Skeleton3D = _rig._arms.skeleton
	var clip: ViewmodelClips = _rig._viewmodel as ViewmodelClips
	if clip:
		sk = clip._arm_skel
	if sk == null:
		return
	var side: String = _hand_side()
	var name: String = "hand." + ("L" if side == "Left" else "R") if clip else "mixamorig_" + side + "Hand"
	var bone: int = sk.find_bone(name)
	if bone < 0:
		return
	var at: Vector3 = sk.to_global(sk.get_bone_global_pose(bone).origin)
	var weapon_basis: Basis = _rig._vm_frame().global_basis.orthonormalized()
	if mode == 2:
		var other: int = sk.find_bone("hand." + ("R" if side == "Left" else "L") if clip else "mixamorig_" + ("Right" if side == "Left" else "Left") + "Hand")
		if other >= 0:
			at = at.lerp(sk.to_global(sk.get_bone_global_pose(other).origin), 0.5)
	else:
		var middle: int = sk.find_bone("f_middle.01." + ("L" if side == "Left" else "R") if clip else "mixamorig_" + side + "HandMiddle1")
		if middle >= 0:
			at = at.lerp(sk.to_global(sk.get_bone_global_pose(middle).origin), 0.6)
	_inspector.focus_on(at, weapon_basis, mode, side)
