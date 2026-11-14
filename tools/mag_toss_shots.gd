extends Node
## Снимки быстрой перезарядки ВЕРАС-54 от первого лица в настоящей игре: старый магазин выбит новым и вылетает
## настоящим телом (TossedItem, Balance.MAG_TOSS) — кадры клипа: за два до сброса (магазин ещё ведёт клип) и сразу
## после — глазами игрока (mag_toss_eye_fNN), полёт и падение — камерой сбоку (mag_toss_side_fNN: от первого лица
## магазин закрыт рукой и уходит вниз за кадр), лежащий магазин глазами игрока и крупно (mag_toss_lying, _lying_close).
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/mag_toss_shots.tscn → docs/screens/mag_toss_*.png
## MAG_TOSS_POS=x,y,z — где стоять (по умолчанию — место появления на карте ТЦ), MAG_TOSS_YAW=град — куда смотреть.

const ID := "wpn_ar_01"
const OUT := "res://docs/screens/"

var _player: Player
var _camera: CameraRig
var _failures: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
		(enemy as Node3D).visible = false
	_player = get_tree().get_first_node_in_group("players") as Player
	_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.health.invulnerable = true
	var at: PackedStringArray = OS.get_environment("MAG_TOSS_POS").split(",", false)
	if at.size() == 3:
		_player.global_position = Vector3(float(at[0]), float(at[1]), float(at[2]))
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.6).timeout
	if OS.get_environment("MAG_TOSS_YAW") != "":
		_camera._look_yaw = deg_to_rad(float(OS.get_environment("MAG_TOSS_YAW")))
	# смотреть чуть вниз: начало падения остаётся в кадре
	await _look_at(_player.eye_position() + _flat_forward() * 2.0 + Vector3.DOWN * 0.75)
	await _arm(12)
	await get_tree().create_timer(0.6).timeout
	# вид сбоку: от первого лица полёт закрыт левой рукой с новым магазином, и магазин быстро уходит вниз за кадр
	var forward: Vector3 = _flat_forward()
	var left: Vector3 = Vector3.UP.cross(forward).normalized()
	var eye: Vector3 = _player.eye_position()
	var side := Camera3D.new()
	side.fov = 60.0
	get_tree().current_scene.add_child(side)
	side.look_at_from_position(eye + left * 1.15 + forward * 0.75 + Vector3.DOWN * 0.55, eye + forward * 0.4 + Vector3.DOWN * 0.75, Vector3.UP)
	var own: Camera3D = get_viewport().get_camera_3d()
	await _tap()
	await _tap()
	_check("двойное R — быстрая перезарядка", _player._reload_fast and _player.reload_timer > 0.0)
	var vm := _camera._viewmodel as ViewmodelClips
	if vm == null:
		_check("в руках модель с клипами", false)
		get_tree().quit(1)
		return
	while _player.reload_timer > 0.0 and not vm._fast:
		await get_tree().process_frame
	_check("у клипа есть кадр сброса", vm._drop_frame >= 0)
	var body: TossedItem = null
	var start: Vector3 = Vector3.ZERO
	# кадры клипа: за два до сброса (магазин ещё ведёт клип) и сразу после — глазами игрока; дальше полёт — сбоку
	for clip_at: int in [vm._drop_frame - 2, vm._drop_frame + 1, vm._drop_frame + 2, vm._drop_frame + 5, vm._drop_frame + 8, vm._drop_frame + 11, vm._drop_frame + 14]:
		while _player.reload_timer > 0.0 and vm._anim.current_animation_position * 30.0 < float(clip_at):
			await get_tree().process_frame
		if body == null:
			body = get_tree().get_first_node_in_group("tossed_items") as TossedItem
			if body != null:
				start = body.start
				print("mag_toss_shots: вылет %s, скорость %s (%.2f м/с), вращение %.1f рад/с" % [str(start), str(body._velocity), body._velocity.length(), body._spin.length()])
		var from_side: bool = clip_at >= vm._drop_frame + 2
		if from_side:
			side.make_current()
		if is_instance_valid(body):
			print("mag_toss_shots: кадр клипа %d — тело %s, над точкой вылета %.2f м" % [clip_at, str(body.global_position), body.global_position.y - start.y])
		await _shot("mag_toss_%s_f%02d" % ["side" if from_side else "eye", clip_at])
	own.make_current()
	side.queue_free()
	_check("магазин вылетел настоящим телом до конца перезарядки", body != null)
	if body == null:
		get_tree().quit(1)
		return
	_check("в руках магазин больше не рисуется", vm._spare_gone or _player.mag_body_seen)
	while is_instance_valid(body) and not body.is_queued_for_deletion():
		await get_tree().process_frame
	while _player.reload_timer > 0.0:
		await get_tree().process_frame
	await get_tree().create_timer(0.4).timeout
	var lying: LooseLoot = null
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LooseLoot
		if c != null and c.dropped and not c.items.is_empty():
			lying = c
	_check("магазин лежит там, куда прилетел (как упал)", lying != null and lying.posed)
	if lying:
		print("mag_toss_shots: лежит %s, от точки вылета %.2f м по земле, патронов %d" % [str(lying.global_position),
			Vector2(lying.global_position.x - start.x, lying.global_position.z - start.z).length(), int((lying.items[0] as Dictionary).get("rounds", -1))])
		await _look_at(lying.global_position)
		await get_tree().create_timer(0.3).timeout
		await _shot("mag_toss_lying")
		# крупно: своя камера над магазином
		var close := Camera3D.new()
		close.fov = 40.0
		get_tree().current_scene.add_child(close)
		var from: Vector3 = lying.global_position + (_player.eye_position() - lying.global_position).normalized() * 0.55 + Vector3.UP * 0.12
		close.look_at_from_position(from, lying.global_position, Vector3.UP)
		close.make_current()
		await get_tree().create_timer(0.3).timeout
		await _shot("mag_toss_lying_close")
		close.queue_free()
	print("mag_toss_shots: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	get_tree().quit(0 if _failures == 0 else 1)


## Игрок со снаряжением: ВЕРАС-54 с магазином на rounds патронов и полным магазином в рюкзаке.
func _arm(rounds: int) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	var ammo_id: String = WeaponDb.default_ammo("545x39")
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": ammo_id, "rounds": rounds}
	_player.loadout_mode = true
	_player.cancel_weapon_action()
	_player.inventory.equipment = {"primary": entry}
	_player.inventory.items = []
	_player.inventory.add_entry(WeaponDb.make_mag(WeaponDb.default_mag(ID), ammo_id, 30))
	_player.weapon_slot = ""
	_player._ws.clear()
	_player._switch("primary", false)


func _tap() -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame


func _flat_forward() -> Vector3:
	var f: Vector3 = -get_viewport().get_camera_3d().global_basis.z
	return Vector3(f.x, 0.0, f.z).normalized()


## Повернуть взгляд на точку: знак углов CameraRig подбирается по тому, куда камера повернулась на самом деле.
func _look_at(point: Vector3) -> void:
	for pass_i: int in range(6):
		var cam: Camera3D = get_viewport().get_camera_3d()
		var want: Vector3 = (point - cam.global_position).normalized()
		var have: Vector3 = -cam.global_basis.z
		var yaw_err: float = wrapf(atan2(want.x, want.z) - atan2(have.x, have.z), -PI, PI)
		var pitch_err: float = asin(clampf(want.y, -1.0, 1.0)) - asin(clampf(have.y, -1.0, 1.0))
		if absf(yaw_err) < 0.01 and absf(pitch_err) < 0.01:
			return
		var yaw0: float = _camera._look_yaw
		var pitch0: float = _camera._look_pitch
		_camera._look_yaw = yaw0 + yaw_err
		_camera._look_pitch = pitch0 + pitch_err
		await get_tree().process_frame
		await get_tree().process_frame
		cam = get_viewport().get_camera_3d()
		have = -cam.global_basis.z
		want = (point - cam.global_position).normalized()
		# стало хуже — знак у этого угла обратный
		if absf(wrapf(atan2(want.x, want.z) - atan2(have.x, have.z), -PI, PI)) > absf(yaw_err) + 0.001:
			_camera._look_yaw = yaw0 - yaw_err
		if absf(asin(clampf(want.y, -1.0, 1.0)) - asin(clampf(have.y, -1.0, 1.0))) > absf(pitch_err) + 0.001:
			_camera._look_pitch = pitch0 - pitch_err
		await get_tree().process_frame
		await get_tree().process_frame


func _shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT + label + ".png"))
	print("mag_toss_shots: ", label)


func _check(label: String, ok: bool) -> void:
	if not ok:
		_failures += 1
	print("%s %s" % ["[ok]  " if ok else "[FAIL]", label])
