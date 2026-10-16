extends CharacterBody3D
## Контроллер измерительной прогулки. Скорости и размеры взяты из Balance игры.
## Нет снаряжения, урона, миссий и записи в основной профиль.

var camera: Camera3D
var capsule: CollisionShape3D
var flight: bool = false
var crouched: bool = false
var blocked_input: bool = false
var is_probe: bool = false
var probe_direction: Vector3 = Vector3.ZERO
var probe_sprint: bool = true
var travelled_m: float = 0.0
var walking_sec: float = 0.0
var previous_position: Vector3
var maximum_y: float = 0.0

func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	floor_snap_length = 0.32
	floor_max_angle = deg_to_rad(48.0)
	var shape: CapsuleShape3D = CapsuleShape3D.new()
	shape.radius = Balance.CAPSULE_RADIUS
	shape.height = Balance.STANCE_HEIGHT.stand
	capsule = CollisionShape3D.new()
	capsule.name = "Capsule"
	capsule.shape = shape
	capsule.position.y = shape.height * 0.5
	add_child(capsule)
	camera = Camera3D.new()
	camera.name = "Eye"
	camera.position.y = Balance.ADS_EYE.stand
	camera.fov = Settings.fps_fov_v()
	camera.near = 0.07
	camera.far = 1400.0
	add_child(camera)
	camera.current = true
	previous_position = global_position

func _unhandled_input(event: InputEvent) -> void:
	if is_probe or blocked_input:
		return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		# ADS_SENS уже в радианах на отсчёт мыши, как в основной CameraRig.
		var sensitivity: float = Balance.ADS_SENS * Settings.sens_fps * (Balance.FPS_FOV / 62.0)
		rotate_y(-motion.relative.x * sensitivity)
		camera.rotation.x = clampf(camera.rotation.x - motion.relative.y * sensitivity, deg_to_rad(-87), deg_to_rad(87))
	if event is InputEventKey and (event as InputEventKey).pressed and not event.is_echo():
		var key: InputEventKey = event as InputEventKey
		if key.physical_keycode == KEY_F:
			flight = not flight
			velocity = Vector3.ZERO
		if key.physical_keycode == KEY_C:
			_set_crouch(not crouched)
		if key.physical_keycode == KEY_SPACE and is_on_floor() and not flight:
			velocity.y = Balance.JUMP.speed

func _set_crouch(value: bool) -> void:
	if not value:
		var stand: CapsuleShape3D = CapsuleShape3D.new()
		stand.radius = Balance.CAPSULE_RADIUS
		stand.height = Balance.STANCE_HEIGHT.stand
		var query: PhysicsShapeQueryParameters3D = PhysicsShapeQueryParameters3D.new()
		query.shape = stand
		query.transform = Transform3D(Basis.IDENTITY, global_position + Vector3.UP * stand.height * 0.5)
		query.collision_mask = 1
		if not get_world_3d().direct_space_state.intersect_shape(query, 1).is_empty():
			return
	crouched = value
	var shape: CapsuleShape3D = capsule.shape as CapsuleShape3D
	shape.height = Balance.STANCE_HEIGHT.crouch if crouched else Balance.STANCE_HEIGHT.stand
	capsule.position.y = shape.height * 0.5
	camera.position.y = Balance.ADS_EYE.crouch if crouched else Balance.ADS_EYE.stand

func _physics_process(delta: float) -> void:
	var direction: Vector3 = Vector3.ZERO
	var sprint: bool = probe_sprint if is_probe else Input.is_physical_key_pressed(KEY_SHIFT)
	if is_probe:
		direction = probe_direction
	elif not blocked_input and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		var axis: Vector2 = Vector2(float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A)), float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W)))
		direction = (global_basis * Vector3(axis.x, 0, axis.y)).normalized()
	if flight:
		var axis: Vector2 = Vector2(float(Input.is_physical_key_pressed(KEY_D)) - float(Input.is_physical_key_pressed(KEY_A)), float(Input.is_physical_key_pressed(KEY_S)) - float(Input.is_physical_key_pressed(KEY_W)))
		direction = camera.global_basis * Vector3(axis.x, 0, axis.y)
		direction.y += float(Input.is_physical_key_pressed(KEY_SPACE)) - float(Input.is_physical_key_pressed(KEY_CTRL))
		if blocked_input or Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			direction = Vector3.ZERO
		# Ускоренный полёт — только инструмент осмотра, его путь не считается прогулкой.
		global_position += direction.normalized() * (60.0 if sprint else 18.0) * delta
		velocity = Vector3.ZERO
	else:
		var speed_m: float = Balance.PLAYER_CROUCH_SPEED if crouched else (Balance.PLAYER_SPRINT_SPEED if sprint else Balance.PLAYER_WALK_SPEED)
		var target: Vector3 = direction * speed_m
		var acceleration: float = Balance.PLAYER_ACCEL if direction.length_squared() > 0.0 else Balance.PLAYER_DECEL
		velocity.x = move_toward(velocity.x, target.x, acceleration * delta)
		velocity.z = move_toward(velocity.z, target.z, acceleration * delta)
		if not is_on_floor():
			velocity.y -= Balance.IMPACT_GRAVITY * delta
		elif velocity.y < 0.0:
			velocity.y = 0.0
		_small_step(direction)
		move_and_slide()
		var moved: float = Vector2(global_position.x - previous_position.x, global_position.z - previous_position.z).length()
		if moved > 0.001 and moved < 2.0:
			travelled_m += moved
			walking_sec += delta
	previous_position = global_position
	maximum_y = maxf(maximum_y, global_position.y)
	if global_position.y < -20.0:
		global_position = Vector3(-177.6, 2.0, 94.4)
		velocity = Vector3.ZERO

func _small_step(direction: Vector3) -> void:
	if direction.length_squared() < 0.01 or not is_on_floor():
		return
	# Невысокий цоколь и перрон не превращаются в непреодолимую стену.
	var at: Vector3 = global_position + direction * 0.38
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(at + Vector3.UP * 0.25, at - Vector3.UP * 0.05, 1)
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	if not hit.is_empty():
		var rise: float = (hit.position as Vector3).y - global_position.y
		if rise > 0.025 and rise < 0.22 and (hit.normal as Vector3).y > 0.8:
			if not test_move(global_transform, Vector3.UP * (rise + 0.015)):
				global_position.y += rise + 0.005

func teleport(at: Vector3, toward: Vector3) -> void:
	global_position = at
	velocity = Vector3.ZERO
	previous_position = at
	var direction: Vector3 = toward - at
	rotation.y = atan2(-direction.x, -direction.z)
	camera.rotation.x = 0.0
	flight = false
