class_name CameraRig
extends Node3D
## Изометрическая камера: следует за локальным игроком, чуть уезжает к курсору,
## зум колесом. Даёт игроку точку на земле под курсором.

@export var target_path: NodePath

var _distance: float = Balance.CAMERA_DISTANCE
var _target: Node3D

@onready var _pivot: Node3D = $Pivot
@onready var _camera: Camera3D = $Pivot/Camera3D


func _ready() -> void:
	add_to_group("camera_rig")
	rotation_degrees.y = Balance.CAMERA_YAW_DEG
	_pivot.rotation_degrees.x = -Balance.CAMERA_PITCH_DEG
	_camera.fov = Balance.CAMERA_FOV
	if target_path != NodePath():
		_target = get_node(target_path)


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
	if _target == null:
		_target = get_tree().get_first_node_in_group("players") as Node3D
		if _target == null:
			return
	_camera.position.z = lerpf(_camera.position.z, _distance, minf(1.0, 6.0 * delta))
	var cursor := cursor_on_ground()
	var lead := (cursor - _target.global_position) * Balance.CAMERA_CURSOR_LEAD
	lead.y = 0.0
	lead = lead.limit_length(Balance.CAMERA_CURSOR_LEAD_MAX)
	var want := _target.global_position + lead
	global_position = global_position.lerp(want, minf(1.0, Balance.CAMERA_FOLLOW_SMOOTH * delta))
	if _target is Player:
		(_target as Player).cursor_ground = cursor


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
