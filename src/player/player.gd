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

@onready var _capsule: CollisionShape3D = $Capsule
@onready var _body: Node3D = $Body
@onready var _camera_rig: Node3D = get_tree().get_first_node_in_group("camera_rig")


func _ready() -> void:
	add_to_group("players")
	_apply_stance()


func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()


func _physics_process(delta: float) -> void:
	if not is_local():
		return
	_read_stance()
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
