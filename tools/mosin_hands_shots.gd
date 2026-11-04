extends Node
## Мосин 1891/30 ПУ (wpn_sr_03) в руках днём под небом (Пригород, ясно): игровая модель assets/models/weapons/mosin_pu,
## общие руки по меткам хвата data/weapon_grips.json (mosin_pu), съёмный прицел ПУ 3,5× на кронштейне (обвес optic_pu_01,
## assets/models/attachments/pu_mosin: окуляр — метка ScopeEye, своя сетка), продольно-скользящий затвор
## (CameraRig._tick_bolt_action). Кадры: от бедра; выстрел — середина цикла затвора (рукоять вверху, затвор отведён, правая
## кисть на шаре); в прицеле (картинка ПУ в окуляре); перезарядка — затвор открыт; модель сбоку справа (покой и затвор
## отведён), мировая модель (ветки LOD1 винтовки и прицела) с 3 м; ПУ отдельно — как предмет; без ПУ — открытые
## прицельные (iron_hip, iron_ads), на винтовке остаётся только основание кронштейна.
## Сделано по tools/ar15_shots.gd.
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/mosin_hands_shots.tscn → docs/screens/mosin_hands_*.png
## (MOSIN_ONLY=hip,fire,ads,reload,side,world,item,iron — выборочно; MOSIN_POS=x,y,z — место; без окна — только лог)

const ID := "wpn_sr_03"
const SCOPE := "optic_pu_01"
const MODS := {"optic_primary": {"id": SCOPE, "dur": 100.0}}
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
	await _equip(MODS)
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
			push_error("mosin_hands_shots: у модели в руках нет окуляра (ПУ)")
		if not _camera.scope_active or not is_equal_approx(float(_player.spec().get("zoom", 0.0)), 3.5):
			fails += 1
			push_error("mosin_hands_shots: в прицел — не оптика ПУ 3,5×")
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
	if _want("item"):
		fails += await _item()
	if _want("iron"):
		fails += await _iron()
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
	var gun: Node3D = WeaponModels.build(ID, MODS)
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


## Мировая модель (lod 1: ветка Mosin_PU_LOD1 и Body_*_LOD1 прицела) с 3 м — как у чужих рук и на земле.
func _world() -> void:
	var gun: Node3D = WeaponModels.build(ID, MODS, 1)
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


## ПУ отдельно — как предмет (значок, на полу): модель обвеса сама по себе, материалы — общий атлас винтовки.
func _item() -> int:
	var item: Node3D = WeaponMods.standalone(SCOPE)
	if item == null:
		push_error("mosin_hands_shots: у ПУ нет модели предмета")
		return 1
	var holder := Node3D.new()
	get_tree().current_scene.add_child(holder)
	holder.add_child(item)
	holder.global_position = _player.global_position + Vector3(0, 1.5, -3.0)
	var shown: int = 0
	var textured: int = 0
	for raw: Node in item.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		if mi.is_visible_in_tree():
			shown += 1
			# стекло — без цвета из карты, только шероховатость из атласа
			var mat: BaseMaterial3D = mi.get_active_material(0) as BaseMaterial3D
			if mat and (mat.albedo_texture != null or mat.roughness_texture != null or mat.orm_texture != null):
				textured += 1
	print("mosin_hands_shots: ПУ предметом: видно сеток ", shown, ", с картами ", textured, ", размер ", ItemModels.bounds(item).size)
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var cam := Camera3D.new()
	cam.fov = 24.0
	holder.add_child(cam)
	var fill := OmniLight3D.new()
	fill.omni_range = 3.0
	fill.light_energy = 1.2
	holder.add_child(fill)
	cam.global_position = holder.global_position + Vector3(0.75, 0.3, 0.35)
	cam.look_at(holder.global_position)
	fill.global_position = holder.global_position + Vector3(0.6, 0.5, -0.2)
	cam.current = true
	await get_tree().create_timer(0.4).timeout
	await _shot("pu_item")
	player_cam.current = true
	holder.queue_free()
	return 0 if shown == 3 and textured == 3 else 1


## Без ПУ: открытые прицельные (метки SightRear / SightFront), на винтовке только основание кронштейна, без оптики.
func _iron() -> int:
	await _equip({})
	_camera._look_yaw = 0.0
	_camera._look_pitch = 0.05
	await get_tree().create_timer(1.0).timeout
	var fr: Node3D = _camera._vm_frame()
	var pu_parts: int = fr.find_children("Body_*", "MeshInstance3D", true, false).size()
	var base: bool = fr.find_child("Mount_Base_Mesh", true, false) != null
	print("mosin_hands_shots: без ПУ: оптика ", fr.get_meta("scoped", false), ", окуляр ", fr.has_meta("ocular"), ", сеток ПУ ", pu_parts,
		", основание ", base, ", sight_h ", fr.get_meta("sight_h", -1.0), ", sight_x ", fr.get_meta("sight_x", 0.0),
		", увеличение ", _player.spec().get("zoom", 0.0))
	await _shot("iron_hip")
	Input.action_press("aim")
	await get_tree().create_timer(float(_player.spec().aim_time) + 0.8).timeout
	await _shot("iron_ads")
	print("mosin_hands_shots: без ПУ в прицел: оптика ", _camera.scope_active)
	Input.action_release("aim")
	await get_tree().create_timer(0.6).timeout
	var bad: bool = bool(fr.get_meta("scoped", false)) or pu_parts > 0 or not base or _camera.scope_active 		or float(_player.spec().get("zoom", 0.0)) > 0.0
	if bad:
		push_error("mosin_hands_shots: без ПУ осталась оптика или нет основания")
	return 1 if bad else 0


func _equip(mods: Dictionary) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods.duplicate(true),
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
