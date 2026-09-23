extends Node
## Оптика против солнца: болтовка (6×) и автомат с 4× на площади у входа — солнце в поле, рядом
## с полем (блик по краю) и в сторону (только аберрация). Снимки — docs/screens/scope_*.png.
## godot --path . res://tools/scope_sun_shots.tscn

var _player: Player
var _rig: CameraRig


func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(60):
		await get_tree().physics_frame
	_player = get_tree().get_first_node_in_group("players") as Player
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.health.hp = 1e9
	# площадь у входа — открытое небо; солнце низко на западе-северо-западе
	_player.global_position = SectorBuilder.polar(-100.0, 176.0) + Vector3(0, 0.05, 0)
	var sun := (get_tree().current_scene.find_children("*", "DirectionalLight3D", true, false)[0] as DirectionalLight3D).global_basis.z
	_player.sandbox_mods = {"rifle": {"optic": "mod_scope4x"}}
	for w in [["weapon_4", "bolt"], ["weapon_2", "rifle4x"]]:
		_tap(String(w[0]))
		await get_tree().create_timer(0.4).timeout
		Input.action_press("aim")
		await get_tree().create_timer(0.6).timeout
		# солнце: чуть в стороне от центра, у края поля, далеко от оси
		var half := _rig.scope_fov() * 0.5
		for shot in [["sun", half * 0.55], ["edge", half + 4.0], ["away", 60.0]]:
			var dir := sun.rotated(Vector3.UP, deg_to_rad(float(shot[1])))
			if shot[0] == "away":
				# на горизонт с постройками — видно аберрацию на контрастных краях
				dir = (dir + Vector3.DOWN * 0.16).normalized()
			await _look_dir(dir)
			await _frames(10)
			_save("scope_%s_%s" % [w[1], shot[0]])
		Input.action_release("aim")
		await _frames(10)
	# открытые прицельные из глаза: мушка в прорези целика, на фасад здания
	_player.sandbox_mods = {}
	var facade := SectorBuilder.polar(-92.0, 125.0) + Vector3(0, 1.6, 0)
	for w in [["weapon_1", "pistol"], ["weapon_2", "rifle"], ["weapon_3", "shotgun"]]:
		_tap(String(w[0]))
		await get_tree().create_timer(0.4).timeout
		Input.action_press("aim")
		await get_tree().create_timer(0.8).timeout
		await _look_dir((facade - _player.eye_position()).normalized())
		await _frames(20)
		_save("irons_%s" % w[1])
		Input.action_release("aim")
		await _frames(10)
	get_tree().quit(0)


func _look_dir(d: Vector3) -> void:
	for i in range(8):
		var yaw := atan2(d.x, d.z)
		var pitch := atan2(d.y, Vector2(d.x, d.z).length())
		var dy := wrapf(yaw - _player.look_yaw, -PI, PI)
		var dp := pitch - _player.look_pitch
		var sens := _rig.ads_sens()
		var e := InputEventMouseMotion.new()
		e.relative = Vector2(-dy / sens, -dp / sens)
		Input.parse_input_event(e)
		await _frames(2)


func _tap(action: String) -> void:
	Input.action_press(action)
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release(action)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("scope_sun_shots: ", n)
