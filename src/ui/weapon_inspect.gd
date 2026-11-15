extends PanelContainer
## Осмотр оружия в руках. Время клипа хранится здесь, чтобы смена обвеса не сбрасывала позу.

const SOURCES := ["backpack", "pocket"]
enum Side { CLOSED, LEFT, RIGHT }

var _side: int = Side.CLOSED
var _poses: Vector3
var _time: float = -1.0
var _player: Player
var _slot: String
var _weapon: String
var _generation: String
var _editable: bool

var _title: Label
var _scroll: ScrollContainer
var _list: VBoxContainer
var _hint: Label
var _popup: PopupMenu
var _shown_mods: Dictionary
var _shown_items: Array
var _shown_pocket: Array
var _screen: Vector2
var _hovered: MenuButton
var _camera: Camera3D
var _frame: Node3D


func _ready() -> void:
	name = "WeaponInspect"
	add_to_group("esc_windows")
	add_theme_stylebox_override("panel", UiTheme.face(Color(0.075, 0.07, 0.062, 0.96), Color(0.48, 0.41, 0.32), 1, 8))
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 9)
	add_child(column)
	_title = ItemCard._label("", 20, UiTheme.C_TEXT)
	_title.autowrap_mode = TextServer.AUTOWRAP_OFF
	column.add_child(_title)
	_scroll = ScrollContainer.new()
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(_scroll)
	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_list.add_theme_constant_override("separation", 7)
	_scroll.add_child(_list)
	_hint = ItemCard._label("", 13, Color(0.78, 0.74, 0.65))
	_hint.autowrap_mode = TextServer.AUTOWRAP_OFF
	column.add_child(_hint)
	resized.connect(_position_panel)
	hide()


func is_open() -> bool:
	return _side != Side.CLOSED


func read_input(pl: Player, clips: ViewmodelClips) -> void:
	var pressed: bool = Input.is_action_just_pressed("inspect_weapon")
	if not pressed and not is_open():
		return
	var entry: Dictionary = pl.inventory.equipment.get(pl.weapon_slot, {}) if pl.loadout_mode else {}
	var generation: String = String(entry.get("_equip_generation", ""))
	var interrupted: bool = pl.ui_blocked(self) or not pl.combat_enabled or pl.is_downed() or pl.is_burdened() \
		or pl.grenade_equipped or pl.seated or pl.ladder != null or pl._vault_t >= 0.0 or Settings.cheat_fly \
		or pl.aiming or pl.mag_inspect or pl.reload_timer > 0.0 or not pl._pm_action.is_empty() \
		or Input.is_action_pressed("aim") or Input.is_action_pressed("sprint") or Input.is_action_pressed("reload") \
		or Input.is_action_just_pressed("inventory") or Input.is_action_just_pressed("pause")
	if is_open():
		if interrupted or _player != pl or _slot != pl.weapon_slot or _weapon != pl.weapon_id or generation != _generation:
			close()
		elif pressed and _side == Side.LEFT:
			_side = Side.RIGHT
			_hide_slots()
		elif pressed:
			close()
		return
	if interrupted or clips == null or clips.weapon_id != pl.weapon_id or clips.is_busy() or Input.is_action_pressed("fire"):
		return
	_poses = clips.inspect_poses()
	if _poses.x < 0.0:
		return
	_player = pl
	_slot = pl.weapon_slot
	_weapon = pl.weapon_id
	_generation = generation
	var host: Node = pl.items_host()
	_editable = pl.loadout_mode and not entry.is_empty() and host != null and host.has_method("request_inspect_mod")
	_time = _poses.x
	_side = Side.LEFT


func advance_clip(delta: float) -> float:
	if is_open():
		_time = move_toward(_time, _poses.y if _side == Side.LEFT else _poses.z, delta)
	return _time


func close() -> void:
	if not is_open():
		return
	_side = Side.CLOSED
	_time = -1.0
	_player = null
	_hide_slots()


func _hide_slots() -> void:
	if is_instance_valid(_popup):
		_popup.hide()
	_popup = null
	_hovered = null
	hide()


func present(camera: Camera3D, frame: Node3D) -> void:
	if _time != (_poses.y if _side == Side.LEFT else _poses.z):
		return
	_camera = camera
	_frame = frame
	var entry: Dictionary = _entry()
	var mods: Dictionary = entry.get("mods", {})
	var inv: Inventory = _player.inventory
	var rebuild: bool = not visible or mods != _shown_mods or inv.items != _shown_items or inv.pocket != _shown_pocket
	if rebuild:
		_rebuild(entry)
		_shown_mods = mods
		_shown_items = inv.items
		_shown_pocket = inv.pocket
	var screen: Vector2 = get_viewport_rect().size
	if rebuild or screen != _screen:
		_screen = screen
		_scroll.custom_minimum_size.y = minf(screen.y * 0.62, _list.get_combined_minimum_size().y)
		size = Vector2(clampf(screen.x * 0.23, 245.0, 335.0), 0.0)
		_position_panel()
	show()
	if is_instance_valid(_hovered):
		queue_redraw()


func _position_panel() -> void:
	position = Vector2(24.0, maxf(52.0, (_screen.y - size.y) * 0.5))


func _entry() -> Dictionary:
	return _player.inventory.equipment.get(_slot, {}) if _player.loadout_mode else _player.weapon_entry()


func _mounts(entry: Dictionary) -> Array[String]:
	var mods: Dictionary = entry.get("mods", {})
	var mounts: Array[String] = []
	mounts.assign(WeaponDb.mounts_of(_weapon).keys())
	for installed: String in WeaponBuild.sorted_keys(mods):
		if not installed in mounts:
			mounts.append(installed)
		var part: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(mods[installed]))
		for socket: Variant in part.get("provides", {}):
			var child: String = installed + "/" + String(socket)
			if not child in mounts:
				mounts.append(child)
	if _editable:
		for role: String in SOURCES:
			for item: Dictionary in _player.inventory.list_of(role):
				if WeaponDb.attachment(String(item.id)).is_empty():
					continue
				for key: String in WeaponBuild.candidate_keys(entry, String(item.id)):
					if not key in mounts and mods.has(WeaponBuild.point_key(key)) and Gear.fit(entry, item, key)[2] == "":
						mounts.append(key)
	return mounts.filter(func(mount: String) -> bool:
		var top: String = WeaponBuild.top_mount(mount)
		return top != ("side_right" if _side == Side.LEFT else "side_left"))


func _rebuild(entry: Dictionary) -> void:
	if is_instance_valid(_popup):
		_popup.hide()
	_popup = null
	_hovered = null
	for child: Node in _list.get_children():
		_list.remove_child(child)
		child.queue_free()
	_title.text = "Левая сторона" if _side == Side.LEFT else "Правая сторона"
	var inspect_key: String = PauseMenu.key_name("inspect_weapon")
	var close_key: String = PauseMenu.key_name("pause").replace("Escape", "Esc")
	_hint.text = "%s — правая сторона    ·    %s — закрыть" % [inspect_key, close_key] if _side == Side.LEFT \
		else "%s / %s — закрыть" % [inspect_key, close_key]
	var mods: Dictionary = entry.get("mods", {})
	for mount: String in _mounts(entry):
		var row := VBoxContainer.new()
		row.add_theme_constant_override("separation", 2)
		_list.add_child(row)
		var label: Label = ItemCard._label(WeaponBuild.label(_weapon, mods, mount), 13, UiTheme.C_ACCENT)
		label.autowrap_mode = TextServer.AUTOWRAP_OFF
		label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		row.add_child(label)
		var installed: String = WeaponDb.mod_id(mods.get(mount, ""))
		var button := MenuButton.new()
		button.set_meta("mount", mount)
		button.flat = false
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		button.text = (ItemDb.item_name(installed) if installed != "" else "Свободно") + ("  ▾" if _editable else "")
		button.tooltip_text = ItemDb.label(WeaponCondition.mod_entry(mods[mount])) if installed != "" else ""
		button.disabled = not _editable
		row.add_child(button)
		button.about_to_popup.connect(_fill_popup.bind(button, mount))
		button.get_popup().index_pressed.connect(_select.bind(button.get_popup(), mount))
		button.mouse_entered.connect(func() -> void: _hovered = button)
		button.mouse_exited.connect(func() -> void:
			_hovered = null
			queue_redraw())


func _fill_popup(button: MenuButton, mount: String) -> void:
	var entry: Dictionary = _entry()
	var popup: PopupMenu = button.get_popup()
	_popup = popup
	popup.clear()
	popup.set_meta("revision", int(entry.get("rev", -1)))
	var locked: String = Inventory.inspect_mod_block(mount, Raid.current != null)
	if locked != "":
		popup.add_item(locked)
		popup.set_item_disabled(0, true)
		return
	var occupied: bool = (entry.get("mods", {}) as Dictionary).has(mount)
	if occupied:
		popup.add_item("Снять в рюкзак")
		popup.set_item_metadata(0, {})
	var added: bool = false
	for role: String in SOURCES:
		var items: Array = _player.inventory.list_of(role)
		for idx: int in range(items.size()):
			var item: Dictionary = items[idx]
			if WeaponDb.attachment(String(item.id)).is_empty() or Gear.fit(entry, item, mount)[2] != "":
				continue
			popup.add_item(("Заменить на " if occupied else "Поставить ") + ItemDb.label(item) + (" (карман)" if role == "pocket" else ""))
			popup.set_item_metadata(popup.item_count - 1, {"role": role, "index": idx, "entry": item.duplicate(true)})
			added = true
	if not added:
		popup.add_item("Подходящих деталей нет")
		popup.set_item_disabled(popup.item_count - 1, true)


func _select(index: int, popup: PopupMenu, mount: String) -> void:
	if visible and is_open() and not popup.is_item_disabled(index):
		_player.request_inspect_mod(mount, int(popup.get_meta("revision")), _generation, popup.get_item_metadata(index))


func _draw() -> void:
	if not is_instance_valid(_hovered) or not is_instance_valid(_frame) or not _frame.is_visible_in_tree():
		return
	var mount: String = String(_hovered.get_meta("mount"))
	var model: String = WeaponBuild.model_of(_weapon)
	var point: Vector3 = WeaponMods.point_frame(_frame, model, _shown_mods, mount).origin
	if mount == "muzzle" and bool(_frame.get_meta("muzzle_own", false)):
		point = _frame.get_meta("muzzle", point)
	var at: Vector3 = _frame.to_global(point)
	if _camera.is_position_behind(at):
		return
	var target: Vector2 = _camera.unproject_position(at) - global_position
	if target.x <= size.x or not get_viewport_rect().has_point(target + global_position):
		return
	var start := Vector2(size.x, _hovered.get_global_rect().get_center().y - global_position.y)
	draw_line(start, target, UiTheme.C_ACCENT, 1.5, true)
	draw_circle(target, 3.0, UiTheme.C_ACCENT, true, -1.0, true)
