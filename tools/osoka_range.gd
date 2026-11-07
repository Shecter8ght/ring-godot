extends Node3D
## Стенд ПЗРК «Осока» на карте «Плотина» (владелец 2026-11-06: «тест, как она стреляет по летящему объекту», «сделай
## это на карте "Плотина"»): мир — серый стенд tools/heli_study.tscn (как у tools/dam_play.gd: рельеф, плотина, вода,
## лес, места коробками, общий свет рейдов); его вертолёт-коробки спрятан — по тому же маршруту задания (plan.heli: с
## севера над озером, над плотиной в ущелье, на концах пауза и обратно) летит учебный вертолёт HeliTarget (простые
## формы, процедурный звук винтов, тепловая цель). Игрок — во дворе лесопилки лицом к плотине (старт dam_play), в руках
## «Осока» из песочницы (ракеты без счёта: R — новая труба), бессмертие.
## tools/osoka_range.cmd — играть самому: ПКМ — вскинуть (головка готовится), держать вертолёт в кольце мушки — писк
##   учащается, жёлтая дуга набирается; захват — ровный писк, метка зелёная; ЛКМ — пуск.
## --headless res://tools/osoka_range.tscn -- check — сам наводится: захват, пуск, попадание, падение, новая труба,
##   пуск без захвата не проходит, захват и сбитие осветительной ракеты; код выхода 0 — всё прошло.
## --windowed --resolution 1600x900 res://tools/osoka_range.tscn -- shots — снимки docs/screens/osoka_*.png (у бедра,
##   поиск, сопровождение, захват, пуск, ракета вблизи, полёт, попадание, падение).
## HELI_PLAN, HELI_TIME, HELI_WEATHER — как у стенда «Плотины»; OSOKA_OUT — папка снимков, OSOKA_TAG — приставка имён.
## На «Осоке» — тепловизор ПН-36Т «ПОЛЫНЬ» (optic_polyn_01): ПКМ — взгляд в окуляр, X — канал «ДЕНЬ / ТЕПЛО»; в
## окуляре — кольцо поля головки, рамка захвата и дальность. -- bare — без прицела (открытые прицельные, метка на
## экране). check с прицелом ещё проверяет: прицел на модели, прицельные сложены, экран тепловизора, тёплый
## вертолёт только в тепловом канале, X — дневной и обратно; shots — ещё снимки th_* и day_* в окуляре.

const ID := "wpn_mp_01"
const SIGHT := "optic_polyn_01"
const OUT := "res://docs/screens/"
const WORLD_SCENE: String = "res://tools/heli_study.tscn"
const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
## Старт — двор лесопилки лицом к плотине (как у tools/dam_play.gd).
const START_AT: Vector2 = Vector2(-300.0, 140.0)
const START_LOOK: Vector2 = Vector2(0.0, 450.0)
## Камера видит плотину и горы через всю долину.
const VIEW_FAR: float = 4000.0

var _player: Player
var _camera: CameraRig
var _heli: HeliTarget
var _world: Node3D
var _mode: String = "play"
var _hint: Label
var _status: Label
var _fails: int = 0
## С тепловизором на «Осоке» (-- bare — без него).
var _with_sight: bool = true
## ПКМ держит стенд: окно потеряло фокус — Godot отпускает нажатые клавиши, _track нажимает снова.
var _aim_hold: bool = false


func _enter_tree() -> void:
	Profile.use_file("user://profile_osoka_range_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if "check" in args:
		_mode = "check"
	elif "shots" in args:
		_mode = "shots"
	_with_sight = not "bare" in args
	_world = (load(WORLD_SCENE) as PackedScene).instantiate() as Node3D
	_world.set_meta("embedded", true)
	add_child(_world)
	DisplayServer.window_set_title("RING · «Плотина» · ПЗРК «Осока»")
	var plan: Dictionary = _world.get("plan") as Dictionary
	var y0: float = float(_world.get("y0"))
	# вертолёт-коробки стенда — спрятать и остановить (пустой маршрут); вместо него — учебная цель по тому же маршруту
	var box_heli: Node3D = _world.get("heli") as Node3D
	if box_heli:
		box_heli.visible = false
	_world.set("heli_path", PackedVector3Array())
	var start := Vector3(START_AT.x, float(_world.call("ground", START_AT.x, START_AT.y)), START_AT.y)
	var yaw: float = atan2(START_LOOK.x - START_AT.x, START_LOOK.y - START_AT.y)
	_player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	_player.name = "Player_1"
	add_child(_player)
	_player.global_position = start + Vector3.UP * 0.05
	_player.face(yaw)
	_camera = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	_camera.name = "CameraRig"
	_camera.target_path = NodePath("../Player_1")
	add_child(_camera)
	_camera._look_yaw = yaw
	var cam: Camera3D = _camera.get("_ads_cam") as Camera3D
	if cam:
		cam.far = VIEW_FAR
	_player.set_god(true)
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(1.0).timeout
	_equip()
	_heli = HeliTarget.new()
	_heli.name = "HeliTarget"
	for p: Array in plan.get("heli", []):
		_heli.route.append(Vector3(float(p[0]), y0 + float(p[2]), float(p[1])))
	_heli.route_speed = float(plan.get("heli_speed", 42.0))
	_heli.center = start
	add_child(_heli)
	print("osoka_range: «Плотина», стрелок ", start.snapped(Vector3.ONE * 0.1), ", маршрут вертолёта — точек ", _heli.route.size())
	await get_tree().create_timer(1.0).timeout
	match _mode:
		"check":
			await _check()
			print("osoka_range: проверка ", "ПРОШЛА" if _fails == 0 else "НЕ ПРОШЛА (%d)" % _fails)
			get_tree().quit(0 if _fails == 0 else 1)
		"shots":
			await _shots()
			get_tree().quit(0)
		_:
			_build_hint()


func _process(_delta: float) -> void:
	if _status == null or _heli == null or _player == null:
		return
	var d: float = _player.global_position.distance_to(_heli.global_position)
	var state: String = ["летит", "подбит, падает", "сбит"][_heli.state]
	var seeker: String = ["выключена", "готовится", "поиск", "сопровождение %d %%" % int(_player.osoka.progress * 100.0),
		"ЗАХВАТ"][_player.osoka.state]
	_status.text = "Вертолёт: %s, %d м · сбит раз: %d · головка: %s · ракет в трубе: %d" % [state, int(d), _heli.kills,
		seeker, _player.ammo]


## Ждать, пока вертолёт виден головке (не за горой и не дальше max_m), держа на нём взгляд; true — дождались.
func _wait_visible(max_m: float, timeout: float) -> bool:
	var t0: int = Time.get_ticks_msec()
	while (Time.get_ticks_msec() - t0) / 1000.0 < timeout:
		if _heli.heat_alive():
			_look_at(_heli.heat_point())
		await get_tree().physics_frame
		var eye: Vector3 = _player.eye_position()
		if _heli.heat_alive() and eye.distance_to(_heli.heat_point()) < max_m \
				and _player.osoka._angle(_player, _heli, eye, _player.look_dir()) < 5.0:
			return true
	return false


func _equip() -> void:
	_player.loadout_mode = false
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": {"optic_primary": SIGHT} if _with_sight else {},
		"mag": {"ammo": "msl_zr36", "rounds": 1}, "sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)


func _build_hint() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 12
	add_child(layer)
	var box := VBoxContainer.new()
	box.position = Vector2(16, 12)
	layer.add_child(box)
	_hint = Label.new()
	_hint.text = "«Осока»: ПКМ — вскинуть к прицелу (головка готовится ~1 с) · держи вертолёт в кольце мушки — писк учащается\n" \
		+ "захват — писк ровный, лампа на целике и метка зелёные · ЛКМ — пуск · R — новая труба · вертолёт кружит над тобой"
	if _with_sight:
		_hint.text += "\nТепловизор «ПОЛЫНЬ»: в окуляре кольцо головки, рамка захвата и дальность · X — канал «ДЕНЬ / ТЕПЛО»"
	_hint.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	box.add_child(_hint)
	_status = Label.new()
	_status.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	box.add_child(_status)


# ---------------------------------------------------------------- наведение «руками» для проверок и снимков

## Взгляд на точку (с поправкой: off_deg — мимо цели вправо).
func _look_at(p: Vector3, off_deg: float = 0.0) -> void:
	var d: Vector3 = p - _player.eye_position()
	var yaw: float = atan2(d.x, d.z) - deg_to_rad(off_deg)
	var pitch: float = asin(clampf(d.normalized().y, -1.0, 1.0))
	_camera._look_yaw = yaw
	_camera._look_pitch = pitch


func _aim(on: bool) -> void:
	_aim_hold = on
	if on:
		Input.action_press("aim")
	else:
		Input.action_release("aim")


## Держать взгляд на цели frames кадров (вертолёт движется).
func _track(target: Node3D, frames: int, off_deg: float = 0.0) -> void:
	for _f in range(frames):
		if _aim_hold and not Input.is_action_pressed("aim"):
			Input.action_press("aim")
		if target and is_instance_valid(target):
			_look_at(target.call("heat_point"), off_deg)
		await get_tree().physics_frame


func _wait_lock(target: Node3D, timeout: float) -> float:
	var t0: int = Time.get_ticks_msec()
	var n: int = 0
	while (Time.get_ticks_msec() - t0) / 1000.0 < timeout:
		_look_at(target.call("heat_point"))
		if _aim_hold and not Input.is_action_pressed("aim"):
			Input.action_press("aim")
		await get_tree().physics_frame
		if _player.osoka.locked() and _player.osoka.target == target:
			return (Time.get_ticks_msec() - t0) / 1000.0
		n += 1
		if n % 40 == 0 and _mode == "check":
			_report_seeker(target)
	return -1.0


## Что видит головка: состояние, прицел, угол до цели по взгляду игрока и что закрывает цель.
func _report_seeker(target: Node3D) -> void:
	var eye: Vector3 = _player.eye_position()
	var p: Vector3 = target.call("heat_point")
	var a: float = rad_to_deg(_player.look_dir().angle_to(p - eye))
	var q := PhysicsRayQueryParameters3D.create(eye, p, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS | Hitscan.LAYER_ROOF, [_player.get_rid()])
	var hit: Dictionary = _player.get_world_3d().direct_space_state.intersect_ray(q)
	var block: String = "открыто" if hit.is_empty() else "закрыто %s на %d м" % [str(hit.collider), int(eye.distance_to(hit.position))]
	print("osoka_range: головка ", _player.osoka.state, " доля ", snappedf(_player.osoka.progress, 0.01), " ПКМ ", _player.aiming,
		" вскинут ", snappedf(_player.aim_progress(), 0.01), " угол ", snappedf(a, 0.1), "° ", block, " до цели ", int(eye.distance_to(p)), " м")


func _fire_once() -> void:
	Input.action_press("fire")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("fire")


func _ok(cond: bool, what: String) -> void:
	print("osoka_range: ", "ок   " if cond else "СБОЙ ", what)
	if not cond:
		_fails += 1


func _check() -> void:
	_ok(_player.weapon_id == ID and _player.ammo == 1, "в руках «Осока», в трубе ракета (%s, %d)" % [_player.weapon_id, _player.ammo])
	var vm: Node3D = _camera._vm_frame()
	_ok(vm != null and vm.has_meta("missile_mount") and vm.has_meta("breech"), "у модели в руках есть метки пуска")
	# без захвата: смотрит в небо мимо вертолёта — пуска нет
	_aim(true)
	await get_tree().create_timer(float(_player.spec().aim_time) + 1.5).timeout
	await _track(_heli, 30, 40.0)
	await _fire_once()
	await get_tree().create_timer(0.3).timeout
	_ok(get_tree().get_nodes_in_group("missiles").is_empty() and _player.ammo == 1, "без захвата пуска нет")
	# захват вертолёта: сначала дождаться, пока он выйдет из-за гор и будет ближе 2,5 км
	var t_seen: int = Time.get_ticks_msec()
	var seen: bool = await _wait_visible(2500.0, 150.0)
	_ok(seen, "вертолёт на виду через %.1f с (%d м)" % [(Time.get_ticks_msec() - t_seen) / 1000.0,
		int(_player.global_position.distance_to(_heli.global_position))])
	var lock_t: float = await _wait_lock(_heli, 8.0)
	_ok(lock_t > 0.0, "захват вертолёта за %.2f с (дальность %d м)" % [lock_t, int(_player.global_position.distance_to(_heli.global_position))])
	if _with_sight:
		await _check_sight()
	await _fire_once()
	await get_tree().physics_frame
	var launched: bool = not get_tree().get_nodes_in_group("missiles").is_empty()
	_ok(launched and _player.ammo == 0, "пуск: ракета в воздухе, труба пуста")
	_aim(false)
	var t0: int = Time.get_ticks_msec()
	while _heli.state == HeliTarget.State.FLY and (Time.get_ticks_msec() - t0) < 16000:
		await get_tree().physics_frame
	_ok(_heli.state != HeliTarget.State.FLY, "попадание через %.2f с" % ((Time.get_ticks_msec() - t0) / 1000.0))
	t0 = Time.get_ticks_msec()
	var fall_n: int = 0
	while _heli.state == HeliTarget.State.FALL and (Time.get_ticks_msec() - t0) < 20000:
		await get_tree().physics_frame
		fall_n += 1
		if fall_n % 60 == 0:
			print("osoka_range: падает — высота ", snappedf(_heli.global_position.y, 0.1), ", земля под кругом ",
				snappedf(_heli._ground_y, 0.1), ", скорость ", _heli._vel.snapped(Vector3.ONE * 0.1))
	_ok(_heli.state == HeliTarget.State.WRECK, "упал за %.2f с" % ((Time.get_ticks_msec() - t0) / 1000.0))
	# новая труба
	Input.action_press("reload")
	await get_tree().physics_frame
	Input.action_release("reload")
	await get_tree().create_timer(float(_player.spec().reload) + 1.0).timeout
	_ok(_player.ammo == 1, "R — новая труба с ракетой (%d)" % _player.ammo)
	# осветительная ракета над головой — тоже тепловая цель
	var flare: SkyFlare = SkyFlare.launch(get_tree().current_scene, _player.eye_position() + Vector3(8, 0, 25), Vector3.UP, false, false)
	await get_tree().create_timer(3.0).timeout
	_aim(true)
	await get_tree().create_timer(float(_player.spec().aim_time) + 1.2).timeout
	var flare_lock: float = await _wait_lock(flare, 6.0)
	_ok(flare_lock > 0.0, "захват осветительной ракеты за %.2f с" % flare_lock)
	await _fire_once()
	_aim(false)
	t0 = Time.get_ticks_msec()
	while is_instance_valid(flare) and flare.heat_alive() and (Time.get_ticks_msec() - t0) < 8000:
		await get_tree().physics_frame
	_ok(not is_instance_valid(flare) or not flare.heat_alive(), "осветительная ракета сбита")
	# вертолёт снова в воздухе
	t0 = Time.get_ticks_msec()
	while _heli.state != HeliTarget.State.FLY and (Time.get_ticks_msec() - t0) < 20000:
		await get_tree().physics_frame
	_ok(_heli.state == HeliTarget.State.FLY, "новый заход вертолёта")


## Тепловизор на «Осоке»: прицел на модели в руках, прицельные сложены, взгляд — в экран окуляра, вертолёт тёплый
## только в тепловом канале, знаки — на экране прицела; X — дневной канал (мир — свой), снова X — тепловой.
func _check_sight() -> void:
	var vm: Node3D = _camera._vm_frame()
	_ok(vm != null and vm.has_meta("thermal") and vm.find_child("BodyLever", true, false) != null, "тепловизор на модели в руках (узлы, канал)")
	var rear: Node3D = vm.find_child("RearSight_Launcher", true, false) as Node3D if vm else null
	var front: Node3D = vm.find_child("FrontSight_Launcher", true, false) as Node3D if vm else null
	var folded: bool = rear != null and front != null and rear.has_meta("fold_rest") and front.has_meta("fold_rest") \
		and not rear.transform.basis.is_equal_approx((rear.get_meta("fold_rest") as Transform3D).basis) \
		and not front.transform.basis.is_equal_approx((front.get_meta("fold_rest") as Transform3D).basis)
	_ok(folded, "целик и мушка сложены")
	await _track(_heli, 6)
	_ok(_camera.scope_active and _camera._display_on and _player.sight_thermal, "взгляд в окуляр: экран тепловизора, канал ТЕПЛО")
	var cam: Camera3D = _camera._scope_cam
	_ok(cam.environment != null and (cam.cull_mask & ThermalView.THERMAL_BIT) != 0, "камера окуляра — тепловой канал (своё окружение, бит маски)")
	var warm: int = 0
	for raw: Node in _heli.find_children("*", "MeshInstance3D", true, false):
		if (raw as MeshInstance3D).material_overlay == ThermalView.material():
			warm += 1
	_ok(warm > 4, "вертолёт тёплый: тёплый проход на %d сетках" % warm)
	var hud: OsokaHud = _camera._osoka_hud
	_ok(hud.in_display() and hud._disp_on and hud._range_m > 0.0, "рамка захвата и дальность — на экране прицела (%d м)" % int(hud._range_m))
	_player.toggle_sight_channel()
	await _track(_heli, 30)
	_ok(not _player.sight_thermal and cam.environment == null and (cam.cull_mask & ThermalView.THERMAL_BIT) == 0 \
		and not _camera._thermal_view.active, "X — дневной канал: мир свой, тёплого прохода нет")
	_ok(_player.osoka.locked(), "в дневном канале захват держится")
	_player.toggle_sight_channel()
	await _track(_heli, 30)
	_ok(_player.sight_thermal and cam.environment != null, "X ещё раз — снова тепловой")


# ---------------------------------------------------------------- снимки

func _shots() -> void:
	for canvas: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		var keep: bool = canvas.find_children("*", "OsokaHud", true, false).size() > 0 or canvas == _camera._scope_view.get_parent()
		if not keep:
			(canvas as CanvasLayer).visible = false
	# OSOKA_ONLY=hip — только вид «на плече» и комплекс со стороны, без ожидания вертолёта
	var only_hip: bool = OS.get_environment("OSOKA_ONLY") == "hip"
	# ждём, пока вертолёт выйдет из-за гор и подлетит ближе 1,6 км
	if not only_hip:
		await _wait_visible(1600.0, 180.0)
	await _track(_heli, 30)
	await _shot("hip")
	if _with_sight:
		await _model_shots()
	if only_hip:
		return
	_aim(true)
	await _track(_heli, int((float(_player.spec().aim_time) + 1.4) * 60.0), 7.0)
	await _shot("search")
	var frames_half: int = int(float(Balance.OSOKA.lock_sec) * 0.5 * 60.0)
	await _track(_heli, frames_half)
	await _shot("track")
	await _wait_lock(_heli, 6.0)
	await _track(_heli, 20)
	await _shot("lock")
	if _with_sight:
		_player.toggle_sight_channel()
		await _track(_heli, 30)
		await _shot("day_lock")
		_player.toggle_sight_channel()
		await _track(_heli, 30)
		if await _wait_broadside(900.0, 120.0):
			await _shot("side")
			_player.toggle_sight_channel()
			await _track(_heli, 20)
			await _shot("day_side")
			_player.toggle_sight_channel()
			await _track(_heli, 20)
	await _fire_once()
	await _track(_heli, 8)
	await _shot("launch")
	# ракета вблизи: своя камера сбоку за ракетой
	var missile: Node3D = null
	for m: Node in get_tree().get_nodes_in_group("missiles"):
		missile = m as Node3D
	await _track(_heli, 30)
	if missile and is_instance_valid(missile):
		var player_cam: Camera3D = get_viewport().get_camera_3d()
		var cam := Camera3D.new()
		cam.fov = 40.0
		get_tree().current_scene.add_child(cam)
		var v: Vector3 = (missile as OsokaMissile)._vel.normalized()
		var side: Vector3 = v.cross(Vector3.UP).normalized()
		cam.global_position = missile.global_position - v * 3.0 + side * 1.6 + Vector3.UP * 0.6
		cam.look_at(missile.global_position + v * 0.8)
		cam.current = true
		var was: float = Engine.time_scale
		Engine.time_scale = 0.0
		await get_tree().process_frame
		await _shot("missile_close")
		Engine.time_scale = was
		cam.current = false
		player_cam.current = true
		cam.queue_free()
	_aim(false)
	await _track(_heli, 40)
	await _shot("flight")
	var t0: int = Time.get_ticks_msec()
	while _heli.state == HeliTarget.State.FLY and (Time.get_ticks_msec() - t0) < 15000:
		_look_at(_heli.global_position)
		await get_tree().physics_frame
	await _track(_heli, 6)
	await _shot("hit")
	await _track(_heli, 100)
	await _shot("fall")


## Ждать, пока вертолёт ближе max_m и идёт бортом к стрелку (скорость поперёк взгляда), держа его в прицеле.
func _wait_broadside(max_m: float, timeout: float) -> bool:
	var t0: int = Time.get_ticks_msec()
	while (Time.get_ticks_msec() - t0) / 1000.0 < timeout:
		await _track(_heli, 1)
		var to: Vector3 = _heli.heat_point() - _player.eye_position()
		var v: Vector3 = _heli.heat_velocity()
		if to.length() < max_m and v.length() > 5.0 and absf(to.normalized().dot(v.normalized())) < 0.45 \
				and _player.osoka._angle(_player, _heli, _player.eye_position(), _player.look_dir()) < 5.0:
			return true
	print("osoka_range: вертолёт бортом ближе %d м не дождались" % int(max_m))
	return false


## Комплекс с тепловизором со стороны: своя камера у стрелка, модель как в мире (WeaponModels.build), день.
func _model_shots() -> void:
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	var model: Node3D = WeaponModels.build(ID, {"optic_primary": SIGHT})
	add_child(model)
	var at: Vector3 = _player.global_position + Vector3(0.0, 1.4, 0.0) + _player.global_basis.x * 3.0
	model.global_position = at
	model.rotation = Vector3(0.0, _camera._look_yaw + PI * 0.5, 0.0)
	var cam := Camera3D.new()
	cam.fov = 32.0
	add_child(cam)
	for view: Array in [["model_left", Vector3(0.0, 0.25, 0.0), 1.9, 0.0], ["model_rear", Vector3(0.0, 0.3, -0.25), 1.15, -2.1],
			["model_front", Vector3(0.0, 0.3, 0.3), 1.2, 2.4]]:
		var aim: Vector3 = model.to_global(view[1] as Vector3)
		var side: Vector3 = model.global_basis.x.rotated(Vector3.UP, float(view[3]))
		cam.global_position = aim + side * float(view[2]) + Vector3.UP * 0.25
		cam.look_at(aim)
		cam.current = true
		await get_tree().process_frame
		await _shot(String(view[0]))
	cam.current = false
	player_cam.current = true
	cam.queue_free()
	model.queue_free()


func _shot(label: String) -> void:
	if DisplayServer.get_name() != "headless":
		await RenderingServer.frame_post_draw
	else:
		await get_tree().process_frame
	var tag: String = OS.get_environment("OSOKA_TAG")
	var name: String = "osoka_%s%s%s.png" % [tag, "_" if tag != "" else "", label]
	var dir: String = OS.get_environment("OSOKA_OUT")
	var path: String = dir.path_join(name) if dir != "" else ProjectSettings.globalize_path(OUT + name)
	var img: Image = get_viewport().get_texture().get_image() if DisplayServer.get_name() != "headless" else null
	if img:
		img.save_png(path)
	print("osoka_range: снимок ", name, " головка ", _player.osoka.state, " захват ", snappedf(_player.osoka.progress, 0.01),
		" вертолёт ", _heli.state, " в ", int(_player.global_position.distance_to(_heli.global_position)), " м")
