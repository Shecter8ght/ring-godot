class_name Player
extends CharacterBody3D
## Игрок: движение по стойкам относительно камеры, корпус смотрит на курсор.
## Сеть: узлом владеет тот peer, чей id записан в `peer_id`; чужих игроков двигает синхронизация.

enum Stance { STAND, CROUCH, PRONE }

@export var peer_id: int = 1

var stance: Stance = Stance.STAND
var aiming: bool = false
## Точка на земле под курсором — ставит камера/уровень; корпус поворачивается к ней.
var cursor_ground: Vector3 = Vector3.ZERO
## Точка на теле противника под курсором (Vector3.ZERO — под курсором никого): выстрел идёт в неё.
var cursor_body: Vector3 = Vector3.ZERO

## Оружие: патроны в магазине, таймеры выстрела и перезарядки.
var ammo: int = int(Balance.PISTOL.mag)
var fire_timer: float = 0.0
var reload_timer: float = 0.0
var _step_timer: float = 0.0
var _rng := RandomNumberGenerator.new()

@onready var _capsule: CollisionShape3D = $Capsule
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle
@onready var health: Health = $Health
@onready var _camera_rig: Node3D = get_tree().get_first_node_in_group("camera_rig")


func _ready() -> void:
	add_to_group("players")
	_rng.randomize()
	health.max_hp = Balance.PLAYER_HP
	health.hp = health.max_hp
	_muzzle.visible = false
	_apply_stance()
	# Слушаем мир из своей позиции, а не из камеры в 28 м над головой.
	if is_local():
		var listener := AudioListener3D.new()
		add_child(listener)
		listener.position = Vector3(0, 1.5, 0)
		listener.make_current()


func is_alive() -> bool:
	return health.alive


func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()


func _physics_process(delta: float) -> void:
	if not is_local() or not is_alive():
		return
	_read_stance()
	_combat(delta)
	var wish := _wish_direction()
	var speed := _stance_speed()
	var target := wish * speed
	var rate := Balance.PLAYER_ACCEL if wish.length() > 0.0 else Balance.PLAYER_DECEL
	velocity.x = move_toward(velocity.x, target.x, rate * delta)
	velocity.z = move_toward(velocity.z, target.z, rate * delta)
	if not is_on_floor():
		velocity.y -= ProjectSettings.get_setting("physics/3d/default_gravity") * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	_face_cursor(delta)
	_footsteps(delta)


## Шаги слышны AI: радиус по стойке и бегу, только пока реально движемся.
func _footsteps(delta: float) -> void:
	var moving := Vector2(velocity.x, velocity.z).length() > 0.3
	if not moving:
		_step_timer = 0.0
		return
	_step_timer -= delta
	if _step_timer > 0.0:
		return
	_step_timer = Balance.NOISE_STEP_INTERVAL
	var key := "stand"
	match stance:
		Stance.CROUCH:
			key = "crouch"
		Stance.PRONE:
			key = "prone"
		_:
			if Input.is_action_pressed("sprint") and not aiming:
				key = "sprint"
	NoiseBus.emit(global_position, float(Balance.NOISE_STEP[key]), "step")
	var step_db: Dictionary = {"stand": 0.0, "sprint": 4.0, "crouch": -8.0, "prone": -14.0}
	Audio.play("step", global_position, float(step_db[key]))


## Стрельба хитсканом в точку под курсором, перезарядка на R.
func _combat(delta: float) -> void:
	fire_timer -= delta
	if reload_timer > 0.0:
		reload_timer -= delta
		if reload_timer <= 0.0:
			ammo = int(Balance.PISTOL.mag)
		return
	if Input.is_action_just_pressed("reload") and ammo < int(Balance.PISTOL.mag):
		reload_timer = float(Balance.PISTOL.reload)
		Audio.play("reload", global_position)
		return
	if Input.is_action_pressed("fire") and fire_timer <= 0.0:
		if ammo <= 0:
			reload_timer = float(Balance.PISTOL.reload)
			Audio.play("reload", global_position)
			return
		ammo -= 1
		fire_timer = float(Balance.PISTOL.interval)
		var from := global_position + Vector3.UP * 1.3
		var target := cursor_body if cursor_body != Vector3.ZERO else cursor_ground + Vector3.UP * 1.3
		var dir := (target - from)
		if dir.length_squared() < 0.01:
			dir = Vector3(sin(_body.rotation.y), 0.0, cos(_body.rotation.y))
		var exclude: Array[RID] = [get_rid()]
		var spread: float = float(Balance.PISTOL.spread_deg) * (0.6 if aiming else 1.0)
		var hit := Hitscan.fire(get_world_3d(), from, dir.normalized(), spread, float(Balance.PISTOL.range_m),
			Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER, float(Balance.PISTOL.damage), exclude, _rng)
		Tracer.spawn(get_tree().current_scene, from, hit.get("position", hit.get("end", from)), Color(1.0, 0.85, 0.5))
		_muzzle.visible = true
		get_tree().create_timer(0.05).timeout.connect(func() -> void: _muzzle.visible = false)
		NoiseBus.emit(global_position, float(Balance.PISTOL.noise_m), "shot")
		Audio.play("shot_pistol", from)


func _read_stance() -> void:
	if Input.is_action_just_pressed("crouch"):
		stance = Stance.STAND if stance == Stance.CROUCH else Stance.CROUCH
		_apply_stance()
	if Input.is_action_just_pressed("prone"):
		stance = Stance.STAND if stance == Stance.PRONE else Stance.PRONE
		_apply_stance()
	aiming = Input.is_action_pressed("aim")


func _stance_speed() -> float:
	var s: float
	match stance:
		Stance.CROUCH:
			s = Balance.PLAYER_CROUCH_SPEED
		Stance.PRONE:
			s = Balance.PLAYER_PRONE_SPEED
		_:
			s = Balance.PLAYER_SPRINT_SPEED if Input.is_action_pressed("sprint") and not aiming else Balance.PLAYER_WALK_SPEED
	if aiming:
		s *= Balance.PLAYER_ADS_SPEED_SCALE
	return s


## WASD относительно камеры: «вверх» на экране — от камеры вглубь.
func _wish_direction() -> Vector3:
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if input.length_squared() == 0.0:
		return Vector3.ZERO
	var yaw := _camera_rig.rotation.y if _camera_rig else 0.0
	var forward := Vector3(-sin(yaw), 0.0, -cos(yaw))
	var right := Vector3(cos(yaw), 0.0, -sin(yaw))
	return (right * input.x + forward * -input.y).normalized()


func _face_cursor(delta: float) -> void:
	var to := cursor_ground - global_position
	to.y = 0.0
	if to.length_squared() < 0.04:
		return
	var want := atan2(to.x, to.z)
	_body.rotation.y = lerp_angle(_body.rotation.y, want, minf(1.0, Balance.PLAYER_TURN_SPEED * delta))


func _apply_stance() -> void:
	var key := "stand"
	match stance:
		Stance.CROUCH:
			key = "crouch"
		Stance.PRONE:
			key = "prone"
	var h: float = Balance.STANCE_HEIGHT[key]
	var shape := _capsule.shape as CapsuleShape3D
	shape.height = h
	shape.radius = minf(Balance.CAPSULE_RADIUS, h * 0.5)
	_capsule.position.y = h * 0.5
	_body.scale.y = h / Balance.STANCE_HEIGHT["stand"]
