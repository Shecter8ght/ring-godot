extends Node3D
## tools/godot.cmd --headless res://tools/weapon_inspect_test.tscn
## В коопе два запуска: -- host и -- client. С окном RING_INSPECT_SHOTS задаёт папку снимков.

const IZHLOM := "wpn_smg_03"
const ASTEN := "wpn_hg_02"
const LASER := "tac_laser_01"
const SUPPRESSOR := "muzzle_supp_9_01"
const PORT := 17814

var _rig: CameraRig
var _me: Player
var _tests: int = 0
var _fails: int = 0
var _guest_ready: bool = false
var _guest_result: int = -1


func _ready() -> void:
	await get_tree().process_frame
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "hideout" in args:
		await _exercise_hideout()
		_finish()
		return
	var host: bool = "host" in args
	var guest: bool = "client" in args
	if host or guest:
		var error: String = Net.host("Inspect host", PORT) if host else Net.join("127.0.0.1", "Inspect guest", PORT)
		if error != "":
			_finish(error)
			return
		if not await _until(func() -> bool: return not multiplayer.get_peers().is_empty(), 18.0):
			_finish("Не дождались напарника")
			return
	var peer: int = int(multiplayer.get_peers()[0]) if host else multiplayer.get_unique_id()
	_boot(peer)
	if host:
		if not await _until(func() -> bool: return _guest_ready):
			_finish("Гость не подготовил сцену")
			return
		_seed_inventory()
		if not await _until(func() -> bool: return _guest_result >= 0, 35.0):
			_finish("Гость не завершил проверку")
			return
		_check("хост подтвердил установки и снятия гостя", _guest_result == 0 and _installed("muzzle", "sidearm") == SUPPRESSOR \
			and _installed("side_right") == "" and _me.inventory.has(LASER) and _me.inventory.has(DozorGear.MOUNT))
		await get_tree().create_timer(0.5).timeout
	else:
		if guest:
			_fixture_ready.rpc_id(1)
		else:
			_seed_inventory()
		if not await _until(func() -> bool: return _me.weapon_id == IZHLOM and _rig._viewmodel is ViewmodelClips):
			_finish("Не выдан ИЗЛОМ-45")
			return
		await _exercise()
		if not guest:
			_inventory_errors()
		else:
			_result.rpc_id(1, _fails)
			await get_tree().create_timer(0.25).timeout
			Net.disconnect_all()
	_finish()


func _boot(peer: int) -> void:
	var raid := Raid.new()
	raid.name = "Raid"
	add_child(raid)
	_rig = preload("res://scenes/player/camera_rig.tscn").instantiate() as CameraRig
	add_child(_rig)
	_me = preload("res://scenes/player/player.tscn").instantiate() as Player
	_me.name = "Player_%d" % peer
	_me.peer_id = peer
	_me.loadout_mode = true
	_me.set_multiplayer_authority(peer)
	add_child(_me)
	_rig.set_target(_me)
	var floor_body := StaticBody3D.new()
	floor_body.position.y = -0.1
	var box := CollisionShape3D.new()
	var bounds := BoxShape3D.new()
	bounds.size = Vector3(20.0, 0.2, 20.0)
	box.shape = bounds
	floor_body.add_child(box)
	var surface := MeshInstance3D.new()
	var mesh_box := BoxMesh.new()
	mesh_box.size = bounds.size
	surface.mesh = mesh_box
	floor_body.add_child(surface)
	add_child(floor_body)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48.0, -35.0, 0.0)
	add_child(sun)


func _seed_inventory() -> void:
	var inv: Inventory = _me.inventory
	var smg: Dictionary = ItemDb.make(IZHLOM, 1)
	var pistol: Dictionary = ItemDb.make(ASTEN, 1)
	inv.equipment = {"primary": smg, "sidearm": pistol, "backpack": ItemDb.make("bp_tourist", 1)}
	for id: String in [DozorGear.MOUNT, LASER, SUPPRESSOR]:
		inv.add(id, 1)
	inv.pocket_grid = Vector2i(2, 2)
	inv.put_at(ItemDb.make("tac_flashlight_01", 1), 0, 0, false, "pocket")
	inv.loadout_ready = true


func _exercise_hideout() -> void:
	Profile.use_file("user://weapon_inspect_hideout_test.json", true)
	Profile.equipment = {"primary": ItemDb.make(IZHLOM, 1), "sidearm": ItemDb.make(ASTEN, 1), "backpack": ItemDb.make("bp_tourist", 1)}
	Profile.backpack = []
	ItemDb.add_to(Profile.backpack, ItemDb.make(SUPPRESSOR, 1), ItemDb.bag_grid(Profile.equipment))
	var scene: PackedScene = load(Balance.HIDEOUT_SCENE) as PackedScene
	if scene == null:
		_check("загрузка убежища", false)
		return
	add_child(scene.instantiate())
	_me = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	await _until(func() -> bool: return _me.weapon_id == IZHLOM and _rig.ads_active)
	await _tap("weapon_3")
	if not await _until(func() -> bool: return _me.weapon_id == ASTEN and _rig._viewmodel is ViewmodelClips):
		_check("АСТЕН-919 в убежище", false)
		return
	await _tap("inspect_weapon")
	if not await _until(func() -> bool: return _rig._inspect.visible):
		_check("осмотр в убежище", false)
		return
	await _choose("muzzle", SUPPRESSOR)
	var mods: Dictionary = Profile.equipment.sidearm.get("mods", {})
	_check("установили обвес в убежище и сохранили его в профиль", _mounted_model("muzzle", SUPPRESSOR, "sidearm") \
		and WeaponDb.mod_id(mods.get("muzzle", "")) == SUPPRESSOR and Profile.backpack.is_empty())


func _exercise() -> void:
	await _tap("inspect_weapon")
	if not await _until(func() -> bool: return _rig._inspect.visible):
		_check("первое I открывает инспект", false)
		return
	_check("слева видна левая планка", _button("side_left") != null and _button("side_right") == null and _facing_left())
	await _shot("inspect_left")
	var left: float = _rig._inspect._time
	await get_tree().create_timer(0.2).timeout
	_check("клип стоит на левом ракурсе", _rig._inspect._time == left and is_equal_approx(_animation_time(), left))
	_check("панель помещается на экране, курсор свободен", get_viewport().get_visible_rect().encloses(_rig._inspect.get_global_rect()) \
		and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE)
	await _tap("inspect_weapon")
	if not await _until(func() -> bool: return _rig._inspect.visible and _button("side_right") != null):
		_check("второе I открывает правый ракурс", false)
		return
	var right: float = _rig._inspect._time
	_check("справа видна правая планка", _button("side_left") == null and not _facing_left())
	var ammo: int = _me.ammo
	await _choose("side_right", DozorGear.MOUNT, "inspect_right_menu")
	_check("крепление установлено справа без сброса позы", _mounted_model("side_right", DozorGear.MOUNT) \
		and _rig._inspect._time == right and is_equal_approx(_animation_time(), right) and _me.ammo == ammo)
	await _choose("side_right/light", "tac_flashlight_01")
	_check("фонарь из кармана установлен в своё крепление", _mounted_model("side_right/light", "tac_flashlight_01") \
		and _me.inventory.pocket.is_empty())
	await _shot("inspect_right_installed")
	await _choose("side_right", LASER)
	var mount_back: Array = _me.inventory.items.filter(func(item: Dictionary) -> bool: return String(item.id) == DozorGear.MOUNT)
	_check("замена вернула крепление с фонарём целиком", _mounted_model("side_right", LASER) and mount_back.size() == 1 \
		and WeaponDb.mod_id(mount_back[0].get("mods", {}).get("light", "")) == "tac_flashlight_01")
	await _choose("side_right", "")
	_check("снятие вернуло деталь и убрало её из модели", _mounted_model("side_right", "") and _me.inventory.has(LASER))
	Input.action_press("fire")
	await _tap("inspect_weapon")
	_check("третье I закрывает панель", not _rig.inspection_open() and not _rig._inspect.visible)
	await get_tree().create_timer(0.24).timeout
	Input.action_release("fire")
	_check("зажатая при закрытии кнопка меню не стреляет", _me.ammo == ammo)
	await _tap("weapon_3")
	if not await _until(func() -> bool: return _me.weapon_id == ASTEN and (_rig._viewmodel as ViewmodelClips).weapon_id == ASTEN):
		_check("достали АСТЕН-919", false)
		return
	await _tap("inspect_weapon")
	await _until(func() -> bool: return _rig._inspect.visible)
	_check("АСТЕН-919 начинает с левой стороны", _rig._inspect.visible and _facing_left())
	await _choose("muzzle", SUPPRESSOR)
	_check("АСТЕН-919 показывает установленный обвес в позе осмотра", _mounted_model("muzzle", SUPPRESSOR, "sidearm"))
	await _tap("inspect_weapon")
	await _until(func() -> bool: return _rig._inspect.visible)
	_check("АСТЕН-919 показывает и правую сторону", _rig._inspect.visible and not _facing_left())
	await _tap("pause")
	_check("Esc закрывает инспект", not _rig.inspection_open() and not PauseMenu.shown)


func _inventory_errors() -> void:
	var inv: Inventory = _me.inventory
	var before: Dictionary = inv.equipment.primary
	_me.entry_of("primary")
	var state: Dictionary = _me._ws_state("primary")
	state.generation = String(before._equip_generation)
	var changed: Dictionary = {"role": "backpack", "index": 0, "entry": ItemDb.make(LASER, 1)}
	_check("двинувшаяся запись не расходуется", inv.change_inspected_mod("primary", "side_right", state, changed, true) != "" \
		and inv.equipment.primary == before)
	var carried: Array = inv.items.duplicate(true)
	var laser_index: int = carried.find_custom(func(item: Dictionary) -> bool: return String(item.id) == LASER)
	if laser_index >= 0:
		var laser: Dictionary = {"role": "backpack", "index": laser_index, "entry": carried[laser_index]}
		_check("повтор старой ревизии не снимает новый обвес", inv.change_inspected_mod("primary", "side_right", state, laser, true) == "" \
			and inv.change_inspected_mod("primary", "side_right", state, {}, true) != "" and _installed("side_right") == LASER)
	var grid: Vector2i = inv.backpack_grid()
	var full: Array = []
	for y: int in grid.y:
		for x: int in grid.x:
			ItemDb.put_at(full, ItemDb.make("bandage", 1), grid, x, y, false)
	inv.items = full
	_me.entry_of("primary")
	state = _me._ws_state("primary")
	state.generation = String(inv.equipment.primary._equip_generation)
	_check("с полным рюкзаком деталь остаётся на оружии", inv.change_inspected_mod("primary", "side_right", state, {}, true) != "" \
		and _installed("side_right") == LASER and inv.items == full)
	var packed: Array = full.duplicate(true)
	ItemDb.remove_at(packed, 0, 1)
	ItemDb.put_at(packed, ItemDb.make("muzzle_comp_9_01", 1), grid, 0, 0, false)
	inv.items = packed
	_me.entry_of("sidearm")
	state = _me._ws_state("sidearm")
	state.generation = String(inv.equipment.sidearm._equip_generation)
	var pick: int = packed.size() - 1
	var source := {"role": "backpack", "index": pick, "entry": packed[pick]}
	_check("замена целиком отклоняется, если снятая деталь не влезает", inv.change_inspected_mod("sidearm", "muzzle", state, source, true) != "" \
		and _installed("muzzle", "sidearm") == SUPPRESSOR and inv.items == packed)


func _choose(mount: String, id: String, screenshot: String = "") -> void:
	var button: MenuButton = _button(mount)
	if button == null:
		_check("слот доступен: " + mount, false)
		return
	button.show_popup()
	if screenshot != "":
		await _shot(screenshot)
	var menu: PopupMenu = button.get_popup()
	for index: int in menu.item_count:
		if menu.is_item_disabled(index):
			continue
		var source: Dictionary = menu.get_item_metadata(index)
		if String((source.get("entry", {}) as Dictionary).get("id", "")) == id:
			menu.index_pressed.emit(index)
			menu.hide()
			await _until(func() -> bool: return _installed(mount, _me.weapon_slot) == id)
			await get_tree().create_timer(0.12).timeout
			return
	menu.hide()
	_check("действие доступно: %s / %s" % [mount, id], false)


func _button(mount: String) -> MenuButton:
	for button: Node in _rig._inspect.find_children("*", "MenuButton", true, false):
		if String(button.get_meta("mount", "")) == mount:
			return button as MenuButton
	return null


func _facing_left() -> bool:
	return _rig._vm_frame().to_local(_rig._ads_cam.global_position).x > 0.0


func _animation_time() -> float:
	return (_rig._viewmodel as ViewmodelClips)._anim.current_animation_position


func _installed(mount: String, slot: String = "primary") -> String:
	var entry: Dictionary = _me.inventory.equipment.get(slot, {})
	return WeaponDb.mod_id((entry.get("mods", {}) as Dictionary).get(mount, ""))


func _mounted_model(mount: String, id: String, slot: String = "primary") -> bool:
	var node: Node = _rig._vm_frame().get_node_or_null("Attachment_" + WeaponBuild.node_name(mount))
	return _installed(mount, slot) == id and (node != null) == (id != "")


func _tap(action: String) -> void:
	var key: InputEventKey = InputMap.action_get_events(action)[0].duplicate() as InputEventKey
	key.pressed = true
	Input.parse_input_event(key)
	await get_tree().create_timer(0.08).timeout
	key = key.duplicate() as InputEventKey
	key.pressed = false
	Input.parse_input_event(key)
	await get_tree().process_frame


func _until(condition: Callable, seconds: float = 8.0) -> bool:
	var until: int = Time.get_ticks_msec() + int(seconds * 1000.0)
	while not condition.call() and Time.get_ticks_msec() < until:
		await get_tree().create_timer(0.05).timeout
	return condition.call()


func _shot(tag: String) -> void:
	var folder: String = OS.get_environment("RING_INSPECT_SHOTS")
	if folder == "" or DisplayServer.get_name() == "headless":
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(folder.path_join(tag + ".png"))


func _check(label: String, ok: bool) -> void:
	_tests += 1
	_fails += 0 if ok else 1
	print("PASS " if ok else "FAIL ", label)


func _finish(error: String = "") -> void:
	if error != "":
		_check(error, false)
	print("weapon_inspect_test: %d checks, %d failures" % [_tests, _fails])
	get_tree().quit(0 if _fails == 0 else 1)


@rpc("any_peer", "call_remote", "reliable")
func _fixture_ready() -> void:
	_guest_ready = true


@rpc("any_peer", "call_remote", "reliable")
func _result(fails: int) -> void:
	_guest_result = fails
