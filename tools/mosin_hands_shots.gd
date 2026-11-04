extends Node
## Мосин 1891/30 ПУ (wpn_sr_03) в руках днём под небом (Пригород, ясно): игровая модель assets/models/weapons/mosin_pu,
## общие руки по меткам хвата data/weapon_grips.json (mosin_pu), встроенный прицел ПУ 3,5× (метка ScopeEye, своя
## сетка), продольно-скользящий затвор (CameraRig._tick_bolt_action). Кадры: от бедра; выстрел — середина цикла
## затвора (рукоять вверху, затвор отведён, правая кисть на шаре); в прицеле (картинка ПУ в окуляре); перезарядка —
## затвор открыт; модель сбоку справа (покой и затвор отведён) и мировая модель (ветка LOD1) с 3 м.
## Сделано по tools/ar15_shots.gd.
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/mosin_hands_shots.tscn → docs/screens/mosin_hands_*.png
## (MOSIN_ONLY=hip,fire,ads,reload,side,world — выборочно; MOSIN_POS=x,y,z — место; без окна — только лог затвора и прицела)

const ID := "wpn_sr_03"
const OUT := "res://docs/screens/"

var _player: Player
var _camera: CameraRig
var _only: PackedStringArray = []


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	_only = OS.get_environment("MOSIN_ONLY").split(",", false)
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
		push_error("mosin_hands_shots: игрок не появился")
		get_tree().quit(1)
		return
	var marauders: Node = level.get_node_or_null("Marauders")
	if marauders:
		for enemy: Node in marauders.get_children():
			enemy.process_mode = Node.PROCESS_MODE_DISABLED
			(enemy as Node3D).visible = false
	_player.health.hp = 100000.0
	var pos: PackedStringArray = OS.get_environment("MOSIN_POS").split(",", false)
	_player.global_position = Vector3(float(pos[0]), float(pos[1]), float(pos[2])) if pos.size() == 3 else Vector3(-95.0, 0.45, 294.0)
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(2.0).timeout
	for canvas: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		if canvas != _camera._scope_view.get_parent():
			(canvas as CanvasLayer).visible = false
	await _equip()
	_player.carry_low = false
	_camera._look_yaw = 0.0
	_camera._look_pitch = 0.05
	await get_tree().create_timer(1.2).timeout
	var fails: int = 0
	if _want("hip"):
		await _shot("hip")
	if _want("fire"):
		var before: int = _player.ammo
		Input.action_press("fire")
		await get_tree().create_timer(0.08).timeout
		Input.action_release("fire")
		var best: float = 0.0
		var best_turn: float = 0.0
		var shot_taken := false
		for _f in range(240):
			await get_tree().process_frame
			var st: Array = _bolt_state()
			best = maxf(best, float(st[0]))
			best_turn = maxf(best_turn, absf(float(st[1])))
			if not shot_taken and float(st[0]) > 0.06:
				await _shot("fire_cycle")
				shot_taken = true
		print("mosin_hands_shots: выстрел: патронов ", before, " → ", _player.ammo, ", отвод затвора до ", snappedf(best, 0.001),
			" м, поворот рукояти до ", snappedf(best_turn, 0.1), "°, после цикла ", _bolt_state())
		if _player.ammo >= before or best < 0.1 or best_turn < 80.0:
			fails += 1
			push_error("mosin_hands_shots: затвор не прошёл цикл")
	if _want("ads"):
		await get_tree().create_timer(1.5).timeout
		Input.action_press("aim")
		await get_tree().create_timer(float(_player.spec().aim_time) + 0.8).timeout
		await _shot("ads")
		var fr: Node3D = _camera._vm_frame()
		if fr and fr.has_meta("ocular"):
			var oc: Vector3 = fr.to_global(fr.get_meta("ocular"))
			print("mosin_hands_shots: окуляр ", fr.get_meta("ocular"), " r ", fr.get_meta("ocular_r"), " ads_z ", fr.get_meta("ads_z", -1.0),
				" sight_h ", fr.get_meta("sight_h", -1.0), " sight_x ", fr.get_meta("sight_x", 0.0), " до глаза ",
				snappedf(_camera._ads_cam.global_position.distance_to(oc), 0.001), " оптика ", _camera.scope_active,
				" увеличение ", _player.spec().get("zoom", 0.0), " сетка ", fr.get_meta("reticle_tex", ""))
		else:
			fails += 1
			push_error("mosin_hands_shots: у модели в руках нет окуляра (встроенный ПУ)")
		Input.action_release("aim")
		await get_tree().create_timer(0.8).timeout
	if _want("reload"):
		# два выстрела — магазин неполный, перезарядка: затвор открыт и отведён, пока патроны входят
		for _k in range(2):
			Input.action_press("fire")
			await get_tree().create_timer(0.08).timeout
			Input.action_release("fire")
			await get_tree().create_timer(1.9).timeout
		Input.action_press("reload")
		await get_tree().create_timer(0.1).timeout
		Input.action_release("reload")
		await get_tree().create_timer(1.2).timeout
		print("mosin_hands_shots: перезарядка: осталось ", snappedf(_player.reload_timer, 0.01), " с, затвор ", _bolt_state())
		await _shot("reload_open")
		await get_tree().create_timer(3.0).timeout
		print("mosin_hands_shots: после перезарядки: патронов ", _player.ammo, ", затвор ", _bolt_state())
	if _want("side"):
		await _side()
	if _want("world"):
		await _world()
	print("mosin_hands_shots: провалено ", fails)
	get_tree().quit(1 if fails > 0 else 0)


func _want(key: String) -> bool:
	return _only.is_empty() or key in _only


## Затвор модели в руках: [отвод, м; поворот рукояти, °].
func _bolt_state() -> Array:
	var frame: Node3D = _camera._vm_frame()
	var bolt: Node3D = frame.find_child("Bolt", true, false) as Node3D
	var rotor: Node3D = frame.find_child("Bolt_Rotor", true, false) as Node3D
	if bolt == null or rotor == null or not bolt.has_meta("rest") or not rotor.has_meta("rest"):
		return [0.0, 0.0]
	var back: float = (bolt.get_meta("rest") as Transform3D).origin.z - bolt.position.z
	var turn: float = rad_to_deg(rotor.basis.get_euler().z - (rotor.get_meta("rest") as Transform3D).basis.get_euler().z)
	return [snappedf(back, 0.001), snappedf(turn, 0.1)]


## Сбоку справа — модель как в руках (lod 0), затвор в покое и отведён до упора (рукоять вверх).
func _side() -> void:
	var gun: Node3D = WeaponModels.build(ID)
	var holder := Node3D.new()
	get_tree().current_scene.add_child(holder)
	holder.add_child(gun)
	holder.global_position = _player.global_position + Vector3(0, 1.6, -3.0)
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var cam := Camera3D.new()
	cam.fov = 34.0
	holder.add_child(cam)
	var fill := OmniLight3D.new()
	fill.omni_range = 4.0
	fill.light_energy = 1.4
	holder.add_child(fill)
	var mid_z: float = 0.36
	cam.global_position = holder.global_position + Vector3(-1.7, 0.1, mid_z)
	cam.look_at(holder.global_position + Vector3(0, 0.02, mid_z))
	fill.global_position = holder.global_position + Vector3(-1.0, 0.6, 0.0)
	cam.current = true
	await get_tree().create_timer(0.4).timeout
	await _shot("side_r")
	var bolt: Node3D = gun.find_child("Bolt", true, false) as Node3D
	var rotor: Node3D = gun.find_child("Bolt_Rotor", true, false) as Node3D
	if bolt and rotor and bolt.has_meta("action"):
		var act: Dictionary = bolt.get_meta("action")
		var rb: Transform3D = bolt.get_meta("rest")
		var rr: Transform3D = rotor.get_meta("rest")
		bolt.transform = Transform3D(rb.basis, rb.origin - Vector3(0, 0, float(act.travel)))
		rotor.transform = Transform3D(rr.basis * Basis(Vector3.BACK, deg_to_rad(float(act.turn_deg))), rr.origin)
		# крупнее — коробка и затвор
		cam.fov = 14.0
		cam.global_position = holder.global_position + Vector3(-0.9, 0.12, 0.12)
		cam.look_at(holder.global_position + Vector3(0, 0.05, 0.12))
		await get_tree().create_timer(0.3).timeout
		await _shot("side_r_bolt_open")
	player_cam.current = true
	holder.queue_free()


## Мировая модель (lod 1: ветка Mosin_PU_LOD1) с 3 м — как у чужих рук и на земле.
func _world() -> void:
	var gun: Node3D = WeaponModels.build(ID, {}, 1)
	var holder := Node3D.new()
	get_tree().current_scene.add_child(holder)
	holder.add_child(gun)
	holder.global_position = _player.global_position + Vector3(0, 1.4, -4.0)
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var cam := Camera3D.new()
	cam.fov = 40.0
	holder.add_child(cam)
	cam.global_position = holder.global_position + Vector3(-3.0, 0.4, 0.36)
	cam.look_at(holder.global_position + Vector3(0, 0, 0.36))
	cam.current = true
	var shown: int = 0
	var hidden: int = 0
	for raw: Node in gun.find_children("*", "MeshInstance3D", true, false):
		if (raw as MeshInstance3D).is_visible_in_tree():
			shown += 1
		else:
			hidden += 1
	print("mosin_hands_shots: мировая модель: видно сеток ", shown, ", спрятано ", hidden)
	await get_tree().create_timer(0.4).timeout
	await _shot("world_3m")
	player_cam.current = true
	holder.queue_free()


func _equip() -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": {},
		"mag": {"id": "", "ammo": "ammo_76254_std", "rounds": 5}, "sight": "primary", "rev": randi()}
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
	var name: String = "mosin_hands_%s.png" % label
	var img: Image = get_viewport().get_texture().get_image() if DisplayServer.get_name() != "headless" else null
	if img:
		img.save_png(ProjectSettings.globalize_path(OUT + name))
	print("mosin_hands_shots: ", name, " в руках ", _player.weapon_id, " патронов ", _player.ammo, " затвор ", _bolt_state(),
		" отвод от преграды ", snappedf(_camera.weapon_clearance.weight, 0.01))
