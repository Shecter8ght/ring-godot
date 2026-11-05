extends Node
## ИЗЛОМ-45 в руках днём под небом (Пригород, ясно): игровая модель (assets/models/weapons/smg03, общие руки по меткам хвата
## data/weapon_grips.json — smg03). Наборы: iron — откидные механические, магазин на 13; rail — коллиматор сверху, фонарь
## слева (фонарь ДОЗОР прямо на планке сейчас встаёт в начало осей у всех стволов), рукоятка снизу, магазин на 30. У iron ещё: очередь (затвор на ходу), магазин расстрелян — затвор на задержке,
## середина перезарядки, после неё — затвор впереди; флажки переводчика по режимам (АВ → 2 → ОД — в лог углы).
## Сделано по tools/ar15_shots.gd.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/smg03_shots.tscn → docs/screens/smg03_*.png
## (SMG03_ONLY=iron,rail — выборочно; SMG03_POS=x,y,z — место; SMG03_OUT — папка снимков)

const ID := "wpn_smg_03"
const OUT := "res://docs/screens/"
const SETS: Array = [
	["iron", {}, "mag_45_vector13"],
	["rail", {"optic_primary": {"id": "optic_holo_01", "dur": 100.0, "slot": 2},
		"side_left": {"id": "tac_laser_01", "dur": 100.0, "slot": 0},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 0}}, "mag_45_vector30"],
]

var _player: Player
var _camera: CameraRig


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/zone01_mall.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	for _i in range(3000):
		_player = get_tree().get_first_node_in_group("players") as Player
		_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
		if _player != null and _camera != null:
			break
		await get_tree().process_frame
	if _player == null:
		push_error("smg03_shots: игрок не появился")
		get_tree().quit(1)
		return
	var marauders: Node = level.get_node_or_null("Marauders")
	if marauders:
		for enemy: Node in marauders.get_children():
			enemy.process_mode = Node.PROCESS_MODE_DISABLED
			(enemy as Node3D).visible = false
	_player.health.hp = 100000.0
	var pos: PackedStringArray = OS.get_environment("SMG03_POS").split(",", false)
	_player.global_position = Vector3(float(pos[0]), float(pos[1]), float(pos[2])) if pos.size() == 3 else Vector3(-95.0, 0.45, 294.0)
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(2.0).timeout
	for canvas: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		if canvas != _camera._scope_view.get_parent():
			(canvas as CanvasLayer).visible = false
	var only: PackedStringArray = OS.get_environment("SMG03_ONLY").split(",", false)
	for set: Array in SETS:
		if not only.is_empty() and not String(set[0]) in only:
			continue
		await _equip(set[1] as Dictionary, String(set[2]))
		_player.carry_low = false
		_camera._look_yaw = 0.0
		_camera._look_pitch = 0.05
		await get_tree().create_timer(1.2).timeout
		await _shot(String(set[0]) + "_hip")
		if String(set[0]) == "iron":
			await _iron_action()
		Input.action_press("aim")
		await get_tree().create_timer(float(_player.spec().aim_time) + 0.6).timeout
		await _shot(String(set[0]) + "_ads")
		Input.action_release("aim")
		await get_tree().create_timer(0.6).timeout
		await _side(String(set[0]), set[1] as Dictionary, String(set[2]))
	get_tree().quit(0)


## Очередь, затворная задержка, перезарядка, переводчик — у модели в руках.
func _iron_action() -> void:
	# короткая очередь: снимок, когда затвор отошёл дальше всего
	var before: int = _player.ammo
	Input.action_press("fire")
	var best: float = 0.0
	for _f in range(40):
		await get_tree().process_frame
		var off: float = _bolt_off()
		best = maxf(best, off)
		if _player.ammo < before - 1 and off > 0.03:
			break
	await _shot("iron_hip_fire")
	Input.action_release("fire")
	print("smg03_shots: очередь — патронов было ", before, ", стало ", _player.ammo, ", наибольший отход затвора ",
		snappedf(best, 0.001), " м")
	await get_tree().create_timer(0.5).timeout
	# расстрелять магазин: затвор встаёт на задержку и стоит сзади
	Input.action_press("fire")
	for _f in range(240):
		await get_tree().process_frame
		if _player.ammo <= 0:
			break
	Input.action_release("fire")
	await get_tree().create_timer(0.6).timeout
	print("smg03_shots: магазин пуст (патронов ", _player.ammo, ") — затвор отошёл на ", snappedf(_bolt_off(), 0.001), " м")
	await _shot("iron_empty_hold")
	# перезарядка: середина и после неё — затвор идёт вперёд
	Input.action_press("reload")
	await get_tree().process_frame
	Input.action_release("reload")
	await get_tree().create_timer(maxf(0.4, _player.reload_timer * 0.5)).timeout
	print("smg03_shots: середина перезарядки — затвор ", snappedf(_bolt_off(), 0.001), " м, осталось ",
		snappedf(_player.reload_timer, 0.01), " с")
	await _shot("iron_reload")
	for _f in range(400):
		await get_tree().process_frame
		if _player.reload_timer <= 0.0:
			break
	await get_tree().create_timer(0.5).timeout
	print("smg03_shots: после перезарядки патронов ", _player.ammo, ", затвор ", snappedf(_bolt_off(), 0.001), " м")
	await _shot("iron_reloaded")
	# переводчик: АВ → 2 → ОД → АВ, углы флажков в руках
	for _i in range(3):
		_player.cycle_fire_mode()
		await get_tree().create_timer(1.0).timeout
		print("smg03_shots: режим ", _player.fire_mode(), " — флажок ", _lever_deg("SelectorR_Steel"), "°")


func _bolt_off() -> float:
	var c: Node3D = _camera._vm_frame().find_child("Bolt_Steel", true, false) as Node3D
	return (c.get_meta("rest") as Transform3D).origin.z - c.position.z if c and c.has_meta("rest") else -1.0


func _lever_deg(node_name: String) -> float:
	var n: Node3D = _camera._vm_frame().find_child(node_name, true, false) as Node3D
	if n == null or not n.has_meta("rest"):
		return -999.0
	var rest: Transform3D = n.get_meta("rest")
	return snappedf(rad_to_deg((n.basis * rest.basis.inverse()).get_euler().x), 0.1)


## Сбоку справа и слева — собранная модель с обвесами.
func _side(label: String, mods: Dictionary, mag: String) -> void:
	var gun: Node3D = WeaponModels.build(ID, mods.duplicate(true), 0, 100.0, mag)
	var holder := Node3D.new()
	get_tree().current_scene.add_child(holder)
	holder.add_child(gun)
	var eye: Vector3 = _player.global_position + Vector3(0, 1.6, 0)
	holder.global_position = eye + Vector3(0, 0, -3.0)
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var cam := Camera3D.new()
	cam.fov = 30.0
	holder.add_child(cam)
	var fill := OmniLight3D.new()
	fill.omni_range = 4.0
	fill.light_energy = 1.6
	holder.add_child(fill)
	var mid_z: float = 0.05
	for side: Array in [["r", -1.0], ["l", 1.0]]:
		cam.global_position = holder.global_position + Vector3(float(side[1]) * 1.25, 0.08, mid_z)
		cam.look_at(holder.global_position + Vector3(0, 0.0, mid_z))
		fill.global_position = holder.global_position + Vector3(float(side[1]) * 0.9, 0.6, -0.2)
		cam.current = true
		await get_tree().create_timer(0.3).timeout
		await _shot("%s_side_%s" % [label, side[0]])
	player_cam.current = true
	holder.queue_free()


func _equip(mods: Dictionary, mag: String) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods.duplicate(true),
		"mag": {"id": mag, "ammo": "ammo_45_fmj", "rounds": int(WeaponDb.magazine(mag).get("capacity", 10))},
		"sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.8).timeout
	for _f in range(90):
		await get_tree().process_frame


func _shot(label: String) -> void:
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
	else:
		await get_tree().process_frame
	var name: String = "smg03_%s.png" % label
	var dir: String = OS.get_environment("SMG03_OUT")
	var path: String = dir.path_join(name) if dir != "" else ProjectSettings.globalize_path(OUT + name)
	var img: Image = get_viewport().get_texture().get_image() if DisplayServer.get_name() != "headless" else null
	if img:
		img.save_png(path)
	print("smg03_shots: ", name, " в руках ", _player.weapon_id, " патронов ", _player.ammo, " отвод ",
		snappedf(_camera.weapon_clearance.weight, 0.01))
