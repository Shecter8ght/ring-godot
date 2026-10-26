extends Node
## ВСС-М v8 в руках днём под небом (Пригород, ясно): игровая модель (assets/models/weapons/vss_m, общие руки по меткам
## хвата), прицелы-модели и обвесы на планках муфты и крышки. Наборы: iron — механический прицел, магазин на 10;
## pso — ПСО на «ласточкином хвосте», фонарь на левой планке муфты, магазин на 20; rail — 4×32 на крышке, фонарь справа, рукоятка снизу, магазин на 30.
## Каждый — от бедра, в прицеливании (у оптики с подсветкой — ещё с горящей сеткой, _ads_lit) и модель сбоку
## справа и слева (vss_<набор>_side_r / _l).
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/vss_shots.tscn → docs/screens/vss_*.png
## (VSS_ONLY=iron,pso — выборочно; VSS_POS=x,y,z — место, по умолчанию открытая поляна у тропы)

const ID := "wpn_sp_02"
const OUT := "res://docs/screens/"
const SETS: Array = [
	["iron", {}, "mag_939_10"],
	["pso", {"optic_primary": {"id": "optic_pso_01", "dur": 100.0},
		"side_left": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 1}}, "mag_939_20"],
	["rail", {"top_front": {"id": "optic_4x_01", "dur": 100.0, "slot": 0},
		"side_right": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 1},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 1}}, "mag_939_30"],
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
		push_error("vss_shots: игрок не появился")
		get_tree().quit(1)
		return
	var marauders: Node = level.get_node_or_null("Marauders")
	if marauders:
		for enemy: Node in marauders.get_children():
			enemy.process_mode = Node.PROCESS_MODE_DISABLED
			(enemy as Node3D).visible = false
	_player.health.hp = 100000.0
	var pos: PackedStringArray = OS.get_environment("VSS_POS").split(",", false)
	_player.global_position = Vector3(float(pos[0]), float(pos[1]), float(pos[2])) if pos.size() == 3 else Vector3(-95.0, 0.45, 294.0)
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(2.0).timeout
	# интерфейс прячем, слой окуляра оптики — нет: картинка прицела рисуется на нём
	for canvas: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		if canvas != _camera._scope_view.get_parent():
			(canvas as CanvasLayer).visible = false
	var only: PackedStringArray = OS.get_environment("VSS_ONLY").split(",", false)
	for set: Array in SETS:
		if not only.is_empty() and not String(set[0]) in only:
			continue
		await _equip(set[1] as Dictionary, String(set[2]))
		_player.carry_low = false
		_camera._look_yaw = 0.0
		_camera._look_pitch = 0.05
		await get_tree().create_timer(1.2).timeout
		await _shot(String(set[0]) + "_hip")
		Input.action_press("aim")
		await get_tree().create_timer(float(_player.spec().aim_time) + 0.6).timeout
		await _shot(String(set[0]) + "_ads")
		var fr: Node3D = _camera._vm_frame()
		if fr and fr.has_meta("reticle_illum"):
			# подсветка сетки горит вместе с фонарём на оружии (T)
			_player._toggle_tac("light")
			await get_tree().create_timer(0.4).timeout
			if _player.light_on:
				await _shot(String(set[0]) + "_ads_lit")
				_player._toggle_tac("light")
				await get_tree().create_timer(0.3).timeout
		if fr and fr.has_meta("ocular"):
			var oc: Vector3 = fr.to_global(fr.get_meta("ocular"))
			print("vss_shots: окуляр ", fr.get_meta("ocular"), " r ", fr.get_meta("ocular_r"), " ads_z ", fr.get_meta("ads_z", -1.0),
				" sight_h ", fr.get_meta("sight_h", -1.0), " sight_x ", fr.get_meta("sight_x", 0.0), " до глаза ",
				snappedf(_camera._ads_cam.global_position.distance_to(oc), 0.001), " масштаб ", _camera._vm_space.scale.x)
		Input.action_release("aim")
		await get_tree().create_timer(0.6).timeout
		await _side(String(set[0]), set[1] as Dictionary)
	get_tree().quit(0)


## Сбоку справа и слева — собранная модель с обвесами (крепления на планках видно целиком).
func _side(label: String, mods: Dictionary) -> void:
	var gun: Node3D = WeaponModels.build(ID, mods.duplicate(true))
	var holder := Node3D.new()
	get_tree().current_scene.add_child(holder)
	holder.add_child(gun)
	var eye: Vector3 = _player.global_position + Vector3(0, 1.6, 0)
	holder.global_position = eye + Vector3(0, 0, -3.0)
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var cam := Camera3D.new()
	cam.fov = 30.0
	holder.add_child(cam)
	# поляна в тени деревьев — подсветка со стороны камеры, чтобы были видны обвесы на планках
	var fill := OmniLight3D.new()
	fill.omni_range = 4.0
	fill.light_energy = 1.6
	holder.add_child(fill)
	for side: Array in [["r", -1.0], ["l", 1.0]]:
		# модель дулом по +Z, −X — правая сторона стрелка; середина модели — 0.13 м перед хватом
		cam.global_position = holder.global_position + Vector3(float(side[1]) * 1.15, 0.12, 0.13)
		cam.look_at(holder.global_position + Vector3(0, 0.07, 0.13))
		fill.global_position = holder.global_position + Vector3(float(side[1]) * 0.9, 0.6, -0.2)
		cam.current = true
		await get_tree().create_timer(0.3).timeout
		await _shot("%s_side_%s" % [label, side[0]])
	# вид — снова камере игрока (иначе следующий набор снимается чужой камерой уровня)
	player_cam.current = true
	holder.queue_free()


func _equip(mods: Dictionary, mag: String) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods.duplicate(true),
		"mag": {"id": mag, "ammo": "ammo_939_sp5", "rounds": int(WeaponDb.magazine(mag).get("capacity", 10))},
		"sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.8).timeout


func _shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var name: String = "vss_%s.png" % label
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(OUT + name))
	print("vss_shots: ", name, " в руках ", _player.weapon_id)
