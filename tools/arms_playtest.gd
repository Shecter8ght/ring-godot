extends Node
## Реальная игровая сцена: каждый ствол, каждый совместимый обвес и заполненные сборки.
## Ввод подаётся через Input; профиль игрока не меняется. ARMS_QUICK=1 — короткая калибровка.

var _player: Player
var _camera: CameraRig
var _report: Array[Dictionary] = []
var _page: Image
var _tiles: int = 0
var _pages: int = 0
var _failures: int = 0
var _case_error: float = 0.0
var _length_error: float = 0.0
var _sample: bool = false
var _label: Label
var _frames: Array[Dictionary] = []
var _output: String = "res://docs/screens/arms_audit/"


func _ready() -> void:
	if OS.get_environment("ARMS_UNDERBARREL") == "1":
		_output = "res://docs/screens/arms_audit_underbarrel/"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_output))
	FileAccess.open(_output + ".gdignore", FileAccess.WRITE).close()
	var overlay: CanvasLayer = CanvasLayer.new()
	overlay.layer = 100
	add_child(overlay)
	_label = Label.new()
	_label.position = Vector2(20, 65)
	_label.add_theme_font_size_override("font_size", 20)
	_label.add_theme_color_override("font_shadow_color", Color.BLACK)
	_label.add_theme_constant_override("shadow_offset_x", 2)
	_label.add_theme_constant_override("shadow_offset_y", 2)
	overlay.add_child(_label)
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
	var cases: Array[Dictionary] = _cases()
	print("ARMS AUDIT START cases=", cases.size())
	var start: int = Time.get_ticks_msec()
	for index: int in range(cases.size()):
		await _run_case(cases[index], index)
	Input.action_release("aim")
	Input.action_release("move_left")
	Input.action_release("move_right")
	if _tiles > 0:
		_save_page()
	var file: FileAccess = FileAccess.open(_output + "report.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"cases": _report, "frames": _frames, "failures": _failures, "seconds": (Time.get_ticks_msec() - start) / 1000.0}, "\t"))
	print("ARMS AUDIT DONE cases=", _report.size(), " failures=", _failures, " seconds=", (Time.get_ticks_msec() - start) / 1000.0)
	get_tree().quit(1 if _failures else 0)


func _process(_delta: float) -> void:
	if _sample and _camera and _camera._arms:
		_case_error = maxf(_case_error, _camera._arms.max_grip_error)
		_length_error = maxf(_length_error, _camera._arms.max_length_error)


func _cases() -> Array[Dictionary]:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(WeaponDb.WEAPONS_PATH)) as Dictionary
	var result: Array[Dictionary] = []
	var quick: bool = OS.get_environment("ARMS_QUICK") == "1"
	for id: String in data.weapons:
		if quick and not id in ["wpn_hg_01", "wpn_ar_06", "wpn_smg_01", "wpn_sg_01", "wpn_sr_01"]:
			continue
		result.append({"id": id, "label": "base", "mods": {}})
		var entry: Dictionary = {"id": id, "mods": {}}
		for attachment: String in data.attachments:
			if quick and not attachment in ["grip_vertical_01", "grip_angled_01", "grip_compact_01", "optic_offset_rd_01"]:
				continue
			for mount: String in WeaponDb.MOUNTS:
				if WeaponDb.attach_block(entry, mount, attachment) == "":
					result.append({"id": id, "label": mount + "_" + attachment, "mods": {mount: {"id": attachment}}})
		# Полные комплекты: каждая рукоятка вместе с прицелом, дульным, светом и прикладом.
		for grip: String in ["grip_vertical_01", "grip_angled_01", "grip_compact_01", "grip_heavy_01", "grip_handstop_01", "bipod_01"]:
			entry = {"id": id, "mods": {}}
			if WeaponDb.attach_block(entry, "underbarrel", grip) != "":
				continue
			entry.mods["underbarrel"] = {"id": grip}
			for mount: String in WeaponDb.MOUNTS:
				if entry.mods.has(mount):
					continue
				for attachment: String in data.attachments:
					if WeaponDb.attach_block(entry, mount, attachment) == "":
						entry.mods[mount] = {"id": attachment, "light": true, "laser": true}
						break
			result.append({"id": id, "label": "full_" + grip, "mods": entry.mods})
	if OS.get_environment("ARMS_UNDERBARREL") == "1":
		var affected: Array[Dictionary] = []
		for config: Dictionary in result:
			var attachment: Dictionary = WeaponDb.attachment(WeaponDb.mod_id(config.mods.get("underbarrel", {})))
			if not attachment.is_empty() and not String(attachment.get("look", "")) in ["grip_vertical", "grip_angled"]:
				affected.append(config)
		return affected
	return result


func _run_case(config: Dictionary, index: int) -> void:
	_sample = false
	_case_error = 0.0
	_length_error = 0.0
	Input.action_release("aim")
	var slot: String = String(WeaponDb.sandbox()[1])
	var id: String = config.id
	var weapon: Dictionary = WeaponDb.weapon(id)
	var magazine: String = WeaponDb.default_mag(id)
	var ammo: String = WeaponDb.default_ammo(String(weapon.caliber))
	var capacity: int = int(weapon.get("internal_mag", WeaponDb.magazine(magazine).get("capacity", 30)))
	_player.sandbox_weapons[slot] = {"id": id, "n": 1, "dur": 100.0, "mods": config.mods,
		"mag": {"id": magazine, "ammo": ammo, "rounds": capacity}, "sight": "primary", "rev": index + 1}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	_player.stance = index % 3
	_player._apply_stance()
	await get_tree().create_timer(0.15).timeout
	_sample = true
	await _capture(id + "_" + String(config.label) + "_hip")
	Input.action_press("aim")
	var move: String = "move_left" if index % 2 == 0 else "move_right"
	Input.action_press(move)
	await get_tree().create_timer(float(_player.spec().aim_time) + 0.15).timeout
	Input.action_release(move)
	if config.label == "base":
		Input.action_press("fire")
		await get_tree().create_timer(0.07).timeout
		Input.action_release("fire")
		await get_tree().create_timer(0.12).timeout
	await _capture(id + "_" + String(config.label) + "_ads")
	if config.mods.has("optic_offset"):
		Input.action_press("toggle_sight")
		await get_tree().physics_frame
		Input.action_release("toggle_sight")
		await get_tree().create_timer(Balance.SIGHT_SWITCH_SEC + 0.1).timeout
		await _capture(id + "_" + String(config.label) + "_offset")
	var ok: bool = _camera._arms.visible and _case_error < 0.002 and _length_error < 0.002 and _camera._viewmodel_id.begins_with(id)
	if not ok:
		_failures += 1
	_report.append({"id": id, "config": config.label, "mods": config.mods, "stance": _player.stance_key(), "grip_error_m": _case_error, "length_error_m": _length_error, "ok": ok})
	if index % 20 == 0 or not ok:
		print("ARMS CASE ", index, " ", id, " ", config.label, " ok=", ok, " error=", _case_error)


func _capture(label: String) -> void:
	_label.text = label + " / " + _player.stance_key()
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var screenshot: Image = get_viewport().get_texture().get_image()
	if OS.get_environment("ARMS_QUICK") == "1":
		screenshot.save_png(_output + label + ".png")
	screenshot.resize(384, 216, Image.INTERPOLATE_LANCZOS)
	if _tiles == 0:
		_page = Image.create(384 * 5, 216 * 6, false, Image.FORMAT_RGB8)
	screenshot.convert(Image.FORMAT_RGB8)
	_page.blit_rect(screenshot, Rect2i(0, 0, 384, 216), Vector2i((_tiles % 5) * 384, (_tiles / 5) * 216))
	_frames.append({"label": label, "page": _pages, "tile": _tiles})
	_tiles += 1
	if _tiles == 30:
		_save_page()


func _save_page() -> void:
	_page.save_png(_output + "page_%03d.png" % _pages)
	_pages += 1
	_tiles = 0
