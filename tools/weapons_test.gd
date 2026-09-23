extends Node
## Прогон новой механики без рук в тире: смена оружия, прицел от первого лица (камера, мышь,
## WASD по взгляду), оптика, граната, регдолл мародёра, вращение камеры средней кнопкой.
## Печатает проверки и сохраняет снимки docs/screens/wt_*.png.
## godot --path . res://tools/weapons_test.tscn

var _player: Player
var _rig: CameraRig
var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/test_range.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(20):
		await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.health.hp = 100000.0

	# 1. средняя кнопка крутит изометрическую камеру
	var yaw0 := _rig.rotation.y
	_mouse_button(MOUSE_BUTTON_MIDDLE, true)
	_mouse_motion(Vector2(120, 0))
	_mouse_button(MOUSE_BUTTON_MIDDLE, false)
	await _frames(3)
	_check("СКМ вращает камеру", absf(_rig.rotation.y - yaw0) > 0.3, "Δ=%.2f рад" % (_rig.rotation.y - yaw0))

	# 2. смена оружия клавишами
	_tap("weapon_2")
	await _frames(4)
	_check("клавиша 2 — автомат", _player.weapon_id == "rifle", _player.weapon_id)

	# 3. прицел: камера от первого лица, мышь захвачена
	Input.action_press("aim")
	await _frames(6)
	_check("ПКМ — вид из глаз", _rig.ads_active and get_viewport().get_camera_3d().name == "AdsCamera", str(get_viewport().get_camera_3d().name))
	var cam := get_viewport().get_camera_3d()
	_check("камера на высоте глаз", absf(cam.global_position.y - (_player.global_position.y + 1.62)) < 0.1, "y=%.2f" % cam.global_position.y)
	# мышь вправо — взгляд вправо (курс уменьшается)
	var look0 := _player.look_yaw
	_mouse_motion(Vector2(300, 0))
	await _frames(3)
	_check("мышь вправо — поворот вправо", _player.look_yaw < look0 - 0.3, "Δ=%.2f" % (_player.look_yaw - look0))
	# W — вперёд по взгляду
	var p0 := _player.global_position
	Input.action_press("move_forward")
	await get_tree().create_timer(0.6).timeout
	Input.action_release("move_forward")
	var moved := _player.global_position - p0
	moved.y = 0.0
	var fwd := Vector3(sin(_player.look_yaw), 0, cos(_player.look_yaw))
	_check("W идёт по взгляду", moved.length() > 0.2 and moved.normalized().dot(fwd) > 0.95, "dot=%.2f dist=%.2f" % [moved.normalized().dot(fwd), moved.length()])
	# D — вправо от взгляда
	p0 = _player.global_position
	Input.action_press("move_right")
	await get_tree().create_timer(0.5).timeout
	Input.action_release("move_right")
	moved = _player.global_position - p0
	moved.y = 0.0
	_check("D идёт вправо от взгляда", moved.normalized().dot(fwd.cross(Vector3.UP)) > 0.95, "dot=%.2f" % moved.normalized().dot(fwd.cross(Vector3.UP)))
	# навести взгляд на мишень и дать очередь
	var target := get_tree().get_nodes_in_group("shootable")[2] as Target
	await _look_at(target.global_position + Vector3(0, 1.1, 0))
	var hits := [0]
	target.hit.connect(func(_d: float, _h: bool) -> void: hits[0] += 1)
	Input.action_press("fire")
	await get_tree().create_timer(0.45).timeout
	Input.action_release("fire")
	await _frames(2)
	_save("wt_ads_rifle")
	_check("очередь из прицела попадает", hits[0] >= 2, "попаданий %d, патронов %d" % [hits[0], _player.ammo])

	# 4. оптика болтовки
	_tap("weapon_4")
	await get_tree().create_timer(0.5).timeout
	await _look_at(target.global_position + Vector3(0, 1.5, 0))
	await _frames(8)
	_save("wt_scope")
	_check("болтовка — оптика отдельным рендером", _rig.scope_active and _rig.scope_fov() < 10.0 and get_viewport().get_camera_3d().fov > 40.0,
		"окуляр fov=%.1f, основной fov=%.1f" % [_rig.scope_fov(), get_viewport().get_camera_3d().fov])
	Input.action_release("aim")
	await _frames(6)
	_check("отпустил ПКМ — изометрия", not _rig.ads_active and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "")

	# 5. мародёр и регдолл: ставим перед игроком, убиваем из дробовика в прицеле
	var m := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	inst.add_child(m)
	m.global_position = _player.global_position + Vector3(0, 0.1, -5)
	m.set_physics_process(false)
	await _frames(3)
	_tap("weapon_3")
	await get_tree().create_timer(0.4).timeout
	Input.action_press("aim")
	await _frames(4)
	await _look_at(m.global_position + Vector3(0, 1.2, 0))
	for i in range(3):
		Input.action_press("fire")
		await _frames(2)
		Input.action_release("fire")
		await get_tree().create_timer(0.85).timeout
		if not (m.get_node("Health") as Health).alive:
			break
	Input.action_release("aim")
	await get_tree().create_timer(0.8).timeout
	var rd := get_tree().get_first_node_in_group("ragdolls") as Ragdoll
	_check("мародёр умер — регдолл", rd != null, "")
	if rd:
		var chest := rd.chest()
		_check("регдолл лёг", chest.global_position.y < 0.7, "грудь на высоте %.2f" % chest.global_position.y)
	_save("wt_ragdoll")

	# 6. граната навесом в точку под курсором
	var cam_iso := get_viewport().get_camera_3d()
	var spot := get_tree().get_nodes_in_group("shootable")[0] as Target
	var ghits := [0]
	spot.hit.connect(func(_d: float, _h: bool) -> void: ghits[0] += 1)
	for k in range(25):
		Input.warp_mouse(cam_iso.unproject_position(spot.global_position + Vector3(1.0, 0, 0.5)))
		await get_tree().process_frame
	var nades := _player.grenades
	_tap("grenade")
	await _frames(3)
	_check("граната брошена", _player.grenades == nades - 1, "осталось %d" % _player.grenades)
	await get_tree().create_timer(float(Balance.GRENADE.fuse) + 0.08).timeout
	_save("wt_explosion")
	await _frames(2)
	_check("взрыв задел мишень рядом", ghits[0] >= 1, "")
	print("weapons_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _look_at(p: Vector3) -> void:
	# курс/тангаж из глаз на точку — через «мышь», как у игрока
	for i in range(6):
		var d := p - _player.eye_position()
		var yaw := atan2(d.x, d.z)
		var pitch := atan2(d.y, Vector2(d.x, d.z).length())
		var dy := wrapf(yaw - _player.look_yaw, -PI, PI)
		var dp := pitch - _player.look_pitch
		var sens := _rig.ads_sens()
		_mouse_motion(Vector2(-dy / sens, -dp / sens))
		await _frames(2)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _tap(action: String) -> void:
	Input.action_press(action)
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(action)


func _mouse_button(b: MouseButton, pressed: bool) -> void:
	var e := InputEventMouseButton.new()
	e.button_index = b
	e.pressed = pressed
	Input.parse_input_event(e)


func _mouse_motion(rel: Vector2) -> void:
	var e := InputEventMouseMotion.new()
	e.relative = rel
	Input.parse_input_event(e)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
