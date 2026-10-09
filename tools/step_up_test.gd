extends Node
## Ступеньки: игрок идёт вперёд на уступ разной высоты (порожек, бордюр, ступень) и должен
## встать на него без прыжка; выше Balance.STEP_UP.max_h — упереться.
## godot --path . --headless res://tools/step_up_test.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://step_up_test.json", true)
	CameraRig.first_person_mode = true
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	for i in range(60):
		await get_tree().physics_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	if pl == null:
		print("step_up_test: нет игрока")
		get_tree().quit(1)
		return
	# куда ведёт «вперёд» — пройти немного и замерить
	var start := pl.global_position
	Input.action_press("move_forward")
	for i in range(30):
		await get_tree().physics_frame
	Input.action_release("move_forward")
	var dir := pl.global_position - start
	dir.y = 0.0
	dir = dir.normalized()
	for h: float in [0.06, 0.12, 0.2, 0.3, 0.45]:
		pl.global_position = start
		pl.velocity = Vector3.ZERO
		for i in range(10):
			await get_tree().physics_frame
		var base_y := pl.global_position.y
		var box := StaticBody3D.new()
		var cs := CollisionShape3D.new()
		var shape := BoxShape3D.new()
		shape.size = Vector3(3.0, h, 1.2)
		cs.shape = shape
		box.add_child(cs)
		get_tree().current_scene.add_child(box)
		var at := start + dir * 1.4
		box.global_transform = Transform3D(Basis.looking_at(dir, Vector3.UP), Vector3(at.x, base_y + h * 0.5, at.z))
		await get_tree().physics_frame
		# по уступу можно пройти насквозь и сойти с другой стороны — берём наибольший подъём
		Input.action_press("move_forward")
		var rise := 0.0
		for i in range(150):
			await get_tree().physics_frame
			rise = maxf(rise, pl.global_position.y - base_y)
		Input.action_release("move_forward")
		var walked := Vector2(pl.global_position.x - start.x, pl.global_position.z - start.z).length()
		var want_up := h <= float(Balance.STEP_UP.max_h)
		var ok := (rise > h - 0.03) if want_up else (rise < 0.05)
		print("step_up_test: уступ %.2f м — поднялся на %.2f м, прошёл %.1f м  %s" % [h, rise, walked, "ок" if ok else "ПРОВАЛ"])
		if not ok:
			_fails += 1
		box.queue_free()
		await get_tree().physics_frame
	print("step_up_test: провалено %d" % _fails)
	get_tree().quit(_fails)
