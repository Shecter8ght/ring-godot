extends Node
## AR-15 «ГРАНЬ-15» в руках днём под небом (Пригород, ясно): игровая модель (assets/models/weapons/ar15, общие руки по
## меткам хвата data/weapon_grips.json), обвесы на планках Picatinny. Наборы: iron — откидные механические прицельные;
## rail — коллиматор на планке ресивера, фонарь на левой планке цевья, рукоятка на нижней; supp — глушитель ГРАНЬ на тормозе,
## supprail — глушитель с коллиматором и рукояткой. Каждый — от бедра (у iron —
## ещё на выстреле, рама отошла: _hip_fire), в прицеливании, на отдаче и модель сбоку справа и слева; у iron справа —
## ещё рама отведена до упора (_side_r_bolt_open: шторка откинута, окно открыто, затвор провёрнут).
## Сделано по tools/vss_shots.gd (ВСС-М).
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/ar15_shots.tscn → docs/screens/ar15_*.png
## (AR15_ONLY=iron,rail — выборочно; AR15_POS=x,y,z — место, по умолчанию открытая поляна у тропы; AR15_TIME — время суток)

const ID := "wpn_ar_09"
const OUT := "res://docs/screens/"
const SETS: Array = [
	["iron", {}, "mag_556_30_gran"],
	["rail", {"optic_primary": {"id": "optic_rd_01", "dur": 100.0, "slot": 2},
		"side_left": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 0},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}}, "mag_556_30_gran"],
	["optic", {"optic_primary": {"id": "optic_rd_01", "dur": 100.0, "slot": 2}}, "mag_556_30_gran"],
	["grip", {"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}}, "mag_556_30_gran"],
	["light", {"side_left": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 0}}, "mag_556_30_gran"],
	["lightr", {"side_right": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 0}}, "mag_556_30_gran"],
	["supp", {"muzzle": {"id": "muzzle_supp_gran_01", "dur": 100.0}}, "mag_556_30_gran"],
	["supprail", {"muzzle": {"id": "muzzle_supp_gran_01", "dur": 100.0},
		"optic_primary": {"id": "optic_rd_01", "dur": 100.0, "slot": 2},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}}, "mag_556_30_gran"],
]

var _player: Player
var _camera: CameraRig


func _ready() -> void:
	var res: PackedStringArray = OS.get_environment("AR15_RES").split("x", false)
	if res.size() == 2:
		get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		get_window().content_scale_size = Vector2i(int(res[0]), int(res[1]))
	RaidEvents.enabled = false
	var hour: String = OS.get_environment("AR15_TIME")
	RaidConditions.from_host = {"time": hour if hour != "" else "day", "weather": "clear", "power": "on"}
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
		push_error("ar15_shots: игрок не появился")
		get_tree().quit(1)
		return
	var marauders: Node = level.get_node_or_null("Marauders")
	if marauders:
		for enemy: Node in marauders.get_children():
			enemy.process_mode = Node.PROCESS_MODE_DISABLED
			(enemy as Node3D).visible = false
	_player.health.hp = 100000.0
	var pos: PackedStringArray = OS.get_environment("AR15_POS").split(",", false)
	if OS.get_environment("AR15_POS") != "spawn":
		_player.global_position = Vector3(float(pos[0]), float(pos[1]), float(pos[2])) if pos.size() == 3 else Vector3(-95.0, 0.45, 294.0)
	print("ar15_shots: игрок ", _player.global_position)
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(2.0).timeout
	# интерфейс прячем, слой окуляра оптики — нет: картинка прицела рисуется на нём
	for canvas: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		if canvas != _camera._scope_view.get_parent():
			(canvas as CanvasLayer).visible = false
	var only: PackedStringArray = OS.get_environment("AR15_ONLY").split(",", false)
	for set: Array in SETS:
		if not only.is_empty() and not String(set[0]) in only:
			continue
		await _equip(set[1] as Dictionary, String(set[2]))
		_player.carry_low = false
		var looks: PackedStringArray = OS.get_environment("AR15_LOOK").split(";", false)
		var look: PackedStringArray = looks[0].split(",", false) if not looks.is_empty() else PackedStringArray()
		_camera._look_yaw = float(look[0]) if look.size() == 2 else 0.0
		_camera._look_pitch = float(look[1]) if look.size() == 2 else 0.05
		await get_tree().create_timer(1.2).timeout
		await _shot(String(set[0]) + "_hip")
		_eyecup_log(String(set[0]) + " от бедра")
		if OS.get_environment("AR15_HERO") == "1":
			# ещё направления взгляда (курс,наклон;…) — выбрать, где солнце ложится на оружие
			for i in range(1, looks.size()):
				look = looks[i].split(",", false)
				_camera._look_yaw = float(look[0])
				_camera._look_pitch = float(look[1])
				await get_tree().create_timer(1.0).timeout
				await _shot("%s_hip_%d" % [set[0], i])
			continue
		if String(set[0]) == "iron":
			# выстрел от бедра — кадр, когда рама отошла (узлы BoltCarrier_Steel и Bolt_Steel, ход 91 мм)
			# от бедра выстрел — после вскидки: ждём, пока уйдёт патрон, и снимаем при наибольшем отходе рамы
			var before: int = _player.ammo
			Input.action_press("fire")
			var best: float = 0.0
			for _f in range(90):
				await get_tree().process_frame
				var c: Node3D = _camera._vm_frame().find_child("BoltCarrier_Steel", true, false) as Node3D
				var off: float = (c.get_meta("rest") as Transform3D).origin.z - c.position.z if c and c.has_meta("rest") else 0.0
				best = maxf(best, off)
				if _player.ammo < before and off > 0.05:
					break
			Input.action_release("fire")
			print("ar15_shots: патронов было ", before, ", стало ", _player.ammo, ", наибольший отход рамы ", snappedf(best, 0.001), " м")
			_bolt_log("на выстреле")
			await _shot("iron_hip_fire")
			await get_tree().create_timer(0.6).timeout
			_bolt_log("после выстрела")
		Input.action_press("aim")
		await get_tree().create_timer(float(_player.spec().aim_time) + 0.6).timeout
		await _shot(String(set[0]) + "_ads")
		var fr: Node3D = _camera._vm_frame()
		_eyecup_log(String(set[0]) + " в прицеле")
		# выстрел — кадр на отдаче: оружие уходит назад к лицу, наглазник не должен резаться камерой
		Input.action_press("fire")
		await get_tree().process_frame
		await get_tree().process_frame
		await _shot(String(set[0]) + "_ads_recoil")
		_eyecup_log(String(set[0]) + " на отдаче")
		Input.action_release("fire")
		await get_tree().create_timer(0.8).timeout
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
			print("ar15_shots: окуляр ", fr.get_meta("ocular"), " r ", fr.get_meta("ocular_r"), " ads_z ", fr.get_meta("ads_z", -1.0),
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
	# модель дулом по +Z, −X — правая сторона стрелка; середина модели — 0.13 м перед хватом, с глушителем (+0,12 м) — 0.19
	var mid_z: float = 0.19 if mods.has("muzzle") else 0.13
	for side: Array in [["r", -1.0], ["l", 1.0]]:
		cam.global_position = holder.global_position + Vector3(float(side[1]) * 1.15, 0.12, mid_z)
		cam.look_at(holder.global_position + Vector3(0, 0.07, mid_z))
		fill.global_position = holder.global_position + Vector3(float(side[1]) * 0.9, 0.6, -0.2)
		cam.current = true
		await get_tree().create_timer(0.3).timeout
		await _shot("%s_side_%s" % [label, side[0]])
		if label == "iron" and side[0] == "r":
			# рама отведена до упора (как на выстреле): рукоятка взведения в конце паза, затвор провёрнут
			var c: Node3D = gun.find_child("BoltCarrier_Steel", true, false) as Node3D
			var b: Node3D = gun.find_child("Bolt_Steel", true, false) as Node3D
			if c and b and c.has_meta("action"):
				var act: Dictionary = c.get_meta("action")
				var rc: Transform3D = c.get_meta("rest")
				var rb: Transform3D = b.get_meta("rest")
				var s: float = float(act.travel)
				c.transform = Transform3D(rc.basis, rc.origin - Vector3(0, 0, s))
				b.transform = Transform3D(rb.basis * Basis(Vector3.BACK, deg_to_rad(float(act.unlock_deg))),
					rb.origin - Vector3(0, 0, s - float(act.bolt_lag)))
				# рама откинула шторку (action.cover) — окно открыто
				var cv: Node3D = gun.find_child(String(act.get("cover", "")), true, false) as Node3D
				if cv and cv.has_meta("rest"):
					var rv: Transform3D = cv.get_meta("rest")
					cv.transform = Transform3D(Basis(Vector3.BACK, deg_to_rad(float(act.get("cover_deg", 0.0)))) * rv.basis, rv.origin)
				await get_tree().create_timer(0.2).timeout
				await _shot("iron_side_r_bolt_open")
				c.transform = rc
				b.transform = rb
				if cv and cv.has_meta("rest"):
					cv.transform = cv.get_meta("rest")
	# вид — снова камере игрока (иначе следующий набор снимается чужой камерой уровня)
	player_cam.current = true
	holder.queue_free()


## Рама и затвор модели в руках (узлы BoltCarrier_Steel, Bolt_Steel): насколько отошли от места, м, и поворот затвора.
func _bolt_log(label: String) -> void:
	var frame: Node3D = _camera._vm_frame()
	for node_name: String in ["BoltCarrier_Steel", "Bolt_Steel"]:
		var n: Node3D = frame.find_child(node_name, true, false) as Node3D
		if n == null or not n.has_meta("rest"):
			var seen: Array = []
			for raw: Node in frame.find_children("*Bolt*", "Node3D", true, false):
				seen.append("%s(%s, action=%s, rest=%s)" % [raw.name, raw.get_class(), raw.has_meta("action"), raw.has_meta("rest")])
			print("ar15_shots: ", node_name, " ", label, ": узла нет; есть ", seen)
			continue
		var rest: Transform3D = n.get_meta("rest")
		print("ar15_shots: ", node_name, " ", label, ": отход ", snappedf(rest.origin.z - n.position.z, 0.001), " м, поворот ",
			snappedf(rad_to_deg(n.basis.get_euler().z - rest.basis.get_euler().z), 0.1), "°")


## Наглазник оптики (meta near_hide): виден ли и на какой глубине его ближняя точка перед камерой, м.
func _eyecup_log(label: String) -> void:
	for raw: Node in _camera._vm_frame().find_children("*", "GeometryInstance3D", true, false):
		var gi: GeometryInstance3D = raw as GeometryInstance3D
		if not gi.has_meta("near_hide"):
			continue
		var local: Transform3D = _camera._ads_cam.global_transform.affine_inverse() * gi.global_transform
		var depth: float = INF
		for i in range(8):
			depth = minf(depth, -(local * gi.get_aabb().get_endpoint(i)).z)
		print("ar15_shots: наглазник ", label, ": виден ", gi.visible, ", ближе всего ", snappedf(depth, 0.001), " м")


func _equip(mods: Dictionary, mag: String) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": mods.duplicate(true),
		"mag": {"id": mag, "ammo": "ammo_556_std", "rounds": int(WeaponDb.magazine(mag).get("capacity", 10))},
		"sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.8).timeout
	# новая сборка грузит карты и шейдеры — кадр-другой по секунде: подъём ствола идёт по кадрам и к снимку не успевал
	# (ствол стоял торчком или внизу); ждём ещё кадров
	for _f in range(90):
		await get_tree().process_frame


func _shot(label: String) -> void:
	# без окна (--headless) кадров нет: только лог — где игрок и сложен ли ствол
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
	else:
		await get_tree().process_frame
	var name: String = "ar15_%s.png" % label
	var dir: String = OS.get_environment("AR15_OUT")
	var path: String = dir.path_join(name) if dir != "" else ProjectSettings.globalize_path(OUT + name)
	var img: Image = get_viewport().get_texture().get_image() if DisplayServer.get_name() != "headless" else null
	if img:
		img.save_png(path)
	# отвод от преграды (WeaponClearance): ствол сложен вверх / вниз, если перед ним что-то есть
	print("ar15_shots: ", name, " в руках ", _player.weapon_id, " у ", _player.global_position.snapped(Vector3.ONE * 0.01),
		" отвод ", snappedf(_camera.weapon_clearance.weight, 0.01), " преграда ", snappedf(_player.weapon_obstruction, 0.01))
