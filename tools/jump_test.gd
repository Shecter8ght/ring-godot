extends Node
## Настоящий ввод пробела и физика в убежище и рейде; отдельный профиль, без AI-боёв.

var _fails: int = 0
var _checks: int = 0
var _pl: Player

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://jump_test.json", true)
	RaidEvents.enabled = false
	for scene: String in [Balance.HIDEOUT_SCENE, "res://scenes/levels/mall_map.tscn"]:
		get_tree().change_scene_to_file(scene)
		await _frames(40)
		for enemy: Node in get_tree().get_nodes_in_group("marauders"):
			enemy.queue_free()
		_pl = get_tree().get_first_node_in_group("players") as Player
		_check(scene+" player", _pl != null)
		if not _pl:
			continue
		await _frames(30)
		_check("settled on floor", _pl.is_on_floor())
		await _jump_trial()
		for stance: Player.Stance in [Player.Stance.CROUCH, Player.Stance.PRONE]:
			_pl.stance = stance
			_pl._apply_stance()
			_pl._try_jump()
			_check("no jump from stance %d" % stance, not _pl.airborne and _pl.velocity.y <= 0.0)
		_pl.stance = Player.Stance.STAND
		_pl._apply_stance()
		_pl.stamina = 0.0
		_pl._try_jump()
		_check("exhausted cannot jump", not _pl.airborne)
		_pl.stamina = Balance.STAMINA_MAX
		_pl._winded = false
		_pl.seated = true
		_pl._try_jump()
		_check("seated cannot jump directly", not _pl.airborne)
		_pl.seated = false
		_pl.health.downed = true
		_pl._try_jump()
		_check("downed cannot jump", not _pl.airborne)
		_pl.health.downed = false
		PauseMenu.shown = true
		_pl._try_jump()
		_check("menu cannot jump", not _pl.airborne)
		PauseMenu.shown = false
		# Реальное столкновение головы: потолок гасит подъём, тело снова приземляется.
		var ceiling: StaticBody3D = StaticBody3D.new()
		var collider: CollisionShape3D = CollisionShape3D.new()
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = Vector3(3,.2,3)
		collider.shape = shape
		ceiling.add_child(collider)
		get_tree().current_scene.add_child(ceiling)
		ceiling.global_position = _pl.global_position + Vector3(0,2.12,0)
		await _frames(30)
		var base_y: float = _pl.global_position.y
		var peak: float = base_y
		_pl._try_jump()
		for i: int in range(60):
			await get_tree().physics_frame
			peak = maxf(peak, _pl.global_position.y)
		_check("ceiling stops jump", peak-base_y < .35 and _pl.is_on_floor() and not _pl.airborne)
		ceiling.queue_free()
	print("JUMP_TEST checks=%d failures=%d" % [_checks,_fails])
	get_tree().quit(1 if _fails > 0 else 0)

func _jump_trial() -> void:
	_pl.stamina = Balance.STAMINA_MAX
	_pl._winded = false
	_pl._jump_cd = 0.0
	var base_y: float = _pl.global_position.y
	var peak: float = base_y
	var pose_seen: bool = false
	var fall_started: bool = false
	var double_impulse: bool = false
	var previous_y: float = _pl.velocity.y
	_space(true)
	await _frames(3)
	_check("Space lifts body", _pl.airborne and _pl.global_position.y > base_y+.04)
	_check("jump costs stamina", _pl.stamina <= Balance.STAMINA_MAX-float(Balance.JUMP.stamina))
	# Новый press во время подъёма не должен заново подбросить игрока.
	_space(false)
	await _frames(2)
	_space(true)
	for i: int in range(90):
		await get_tree().physics_frame
		peak = maxf(peak, _pl.global_position.y)
		if _pl.airborne:
			pose_seen = pose_seen or _pl._animator._current == "jump_loop"
			fall_started = fall_started or _pl.velocity.y < 0.0
			if fall_started and _pl.velocity.y > previous_y+.5:
				double_impulse = true
		previous_y = _pl.velocity.y
	_space(false)
	_check("realistic jump height", peak-base_y > .4 and peak-base_y < .65)
	_check("airborne animation", pose_seen)
	_check("no double jump or hold repeat", not double_impulse and not _pl.airborne and _pl.is_on_floor())
	_check("lands at original floor", absf(_pl.global_position.y-base_y) < .04)

func _space(pressed: bool) -> void:
	var event: InputEventKey = InputEventKey.new()
	event.physical_keycode = KEY_SPACE
	event.keycode = KEY_SPACE
	event.pressed = pressed
	Input.parse_input_event(event)

func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame

func _check(label: String, ok: bool) -> void:
	_checks += 1
	if not ok: _fails += 1
	print("[%s] %s" % ["ok" if ok else "FAIL", label])
