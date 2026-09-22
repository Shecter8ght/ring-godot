class_name CameraRig
extends Node3D
## Изометрическая камера: следует за локальным игроком, чуть уезжает к курсору,
## зум колесом. Даёт игроку точку на земле под курсором.

@export var target_path: NodePath

var _distance: float = Balance.CAMERA_DISTANCE
var _target: Node3D
var _shake: float = 0.0
var _hitmarker: Control
var _hitmarker_t: float = 0.0
var _rng := RandomNumberGenerator.new()

@onready var _pivot: Node3D = $Pivot
@onready var _camera: Camera3D = $Pivot/Camera3D


func _ready() -> void:
	add_to_group("camera_rig")
	rotation_degrees.y = Balance.CAMERA_YAW_DEG
	_pivot.rotation_degrees.x = -Balance.CAMERA_PITCH_DEG
	_camera.fov = Balance.CAMERA_FOV
	if target_path != NodePath():
		_target = get_node(target_path)
	_build_hitmarker()


## Толчок камеры (выстрел, попадание по тебе); складывается и затухает сам.
func add_shake(amount: float) -> void:
	_shake = minf(_shake + amount, 1.0)


## Крестик у курсора: попал; kill — крупнее и красный (голова/добил).
func show_hitmarker(kill: bool) -> void:
	_hitmarker_t = Balance.HITMARKER_SEC * (1.6 if kill else 1.0)
	_hitmarker.modulate = Color(1.0, 0.25, 0.2) if kill else Color(1, 1, 1)
	_hitmarker.scale = Vector2.ONE * (1.5 if kill else 1.0)


func _build_hitmarker() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	_hitmarker = Control.new()
	_hitmarker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hitmarker.visible = false
	layer.add_child(_hitmarker)
	for ang in [45.0, 135.0, 225.0, 315.0]:
		var r := ColorRect.new()
		r.color = Color(1, 1, 1)
		r.size = Vector2(10, 2)
		r.position = Vector2(6, -1)
		r.pivot_offset = Vector2(-6, 1)
		r.rotation_degrees = ang
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_hitmarker.add_child(r)


func set_target(node: Node3D) -> void:
	_target = node


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_distance = maxf(Balance.CAMERA_ZOOM_MIN, _distance - Balance.CAMERA_ZOOM_STEP)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_distance = minf(Balance.CAMERA_ZOOM_MAX, _distance + Balance.CAMERA_ZOOM_STEP)


func _process(delta: float) -> void:
	# Вращение камеры вокруг игрока: Q/E, плавно, пока зажато.
	var turn := Input.get_axis("camera_left", "camera_right")
	if turn != 0.0:
		rotation.y -= deg_to_rad(Balance.CAMERA_TURN_DEG_PER_SEC) * turn * delta
	if _target == null:
		_target = get_tree().get_first_node_in_group("players") as Node3D
		if _target == null:
			return
	_camera.position.z = lerpf(_camera.position.z, _distance, minf(1.0, 6.0 * delta))
	# Тряска — смещение камеры в её плоскости; квадрат силы, чтобы мелкие толчки были мягкими.
	_shake = maxf(0.0, _shake - Balance.SHAKE_DECAY * _shake * delta - 0.01 * delta)
	var s := _shake * _shake * 4.0
	_camera.position.x = _rng.randf_range(-s, s)
	_camera.position.y = _rng.randf_range(-s, s)
	_hitmarker_t -= delta
	_hitmarker.visible = _hitmarker_t > 0.0
	if _hitmarker.visible:
		_hitmarker.position = get_viewport().get_mouse_position()
	SectorMaterials.set_cutaway_distance(_camera.position.z * Balance.CAMERA_CUTAWAY_NEAR, _camera.position.z * Balance.CAMERA_CUTAWAY_FAR)
	var cursor := cursor_on_ground()
	var lead := (cursor - _target.global_position) * Balance.CAMERA_CURSOR_LEAD
	lead.y = 0.0
	lead = lead.limit_length(Balance.CAMERA_CURSOR_LEAD_MAX)
	var want := _target.global_position + lead
	global_position = global_position.lerp(want, minf(1.0, Balance.CAMERA_FOLLOW_SMOOTH * delta))
	if _target is Player:
		var pl := _target as Player
		pl.cursor_ground = cursor
		pl.cursor_body = _body_under_cursor()


## Тело под курсором (мародёр): луч из камеры сквозь курсор по физике. Пусто — если под курсором пол/стена.
func _body_under_cursor() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * 200.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DOOR)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty() or not ((hit.collider as Node).is_in_group("marauders") or (hit.collider as Node).is_in_group("shootable")):
		return Vector3.ZERO
	return hit.position


## Пересечение луча из курсора с плоскостью пола игрока (y = высота цели).
func cursor_on_ground() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var plane := Plane(Vector3.UP, _target.global_position.y)
	var hit: Variant = plane.intersects_ray(from, dir)
	if hit == null:
		return _target.global_position
	return hit
