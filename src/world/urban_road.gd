@tool
class_name UrbanRoad
extends Node3D
## Полилиния реальной улицы: проезжая часть, тротуары, бордюры и разметка.

@export var points: PackedVector3Array = PackedVector3Array():
	set(value):
		points = value
		_queue_build()
@export var carriage_width: float = 14.0:
	set(value):
		carriage_width = maxf(1.0, value)
		_queue_build()
@export var sidewalk_width: float = 4.0:
	set(value):
		sidewalk_width = maxf(0.0, value)
		_queue_build()
@export var markings: bool = true:
	set(value):
		markings = value
		_queue_build()
@export var sidewalks: bool = true:
	set(value):
		sidewalks = value
		_queue_build()

var _pending: bool = false


func _ready() -> void:
	_build()
	if not Engine.is_editor_hint():
		add_to_group("nav_source")


func _queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	var old: Node = get_node_or_null("_Generated")
	if old:
		old.free()
	var root := Node3D.new()
	root.name = "_Generated"
	add_child(root)
	for index in range(points.size() - 1):
		_segment(root, points[index], points[index + 1], index)


func _segment(root: Node3D, from: Vector3, to: Vector3, index: int) -> void:
	var delta: Vector3 = to - from
	var length: float = Vector2(delta.x, delta.z).length()
	if length < 0.01:
		return
	var segment := Node3D.new()
	segment.name = "Segment_%d" % index
	segment.position = from
	segment.rotation.y = atan2(delta.x, delta.z)
	root.add_child(segment)
	var road := BlockoutMesh.new()
	var half: float = carriage_width * 0.5
	road.ramp("gbf_asphalt", -half, half, 0, length, 0.04, delta.y + 0.04, 0.16)
	var road_body: StaticBody3D = road.emit(segment, "Carriageway", false, false)
	road_body.set_meta("surface", "asphalt")
	_prism(road_body, -half, half, length, 0.04, delta.y + 0.04, 0.16)
	if sidewalks and sidewalk_width > 0.0:
		for side in [-1.0, 1.0]:
			var x0: float = side * half
			var x1: float = side * (half + sidewalk_width)
			var walk := BlockoutMesh.new()
			walk.ramp("gbf_concrete", minf(x0, x1), maxf(x0, x1), 0, length, 0.16, delta.y + 0.16, 0.22)
			var body: StaticBody3D = walk.emit(segment, "Sidewalk_%d" % int(side), false, false)
			body.set_meta("surface", "concrete")
			_prism(body, minf(x0, x1), maxf(x0, x1), length, 0.16, delta.y + 0.16, 0.22)
			# На концах сегмента бордюр понижен: пересечения улиц остаются проходимыми.
			if length > 12.0:
				var curb := BlockoutMesh.new()
				var rise: float = delta.y / length
				curb.ramp("gb_structural", side * half - 0.12, side * half + 0.12, 5.0, length - 5.0, 0.19 + rise * 5.0, 0.19 + rise * (length - 5.0), 0.15)
				curb.emit(segment, "Curb_%d" % int(side), false, false)
	if markings:
		var lines := BlockoutMesh.new()
		for side in [-1.0, 1.0]:
			var x: float = side * (half - 0.3)
			lines.ramp("gbf_tile", x - 0.05, x + 0.05, 0, length, 0.052, delta.y + 0.052, 0.008)
		var z: float = 0.0
		while z < length:
			var end: float = minf(z + 4.0, length)
			lines.ramp("gbf_tile", -0.06, 0.06, z, end, 0.052 + delta.y * z / length, 0.052 + delta.y * end / length, 0.008)
			z += 8.0
		var body: StaticBody3D = lines.emit(segment, "Markings", false, false)
		for mesh_node in body.get_children():
			(mesh_node as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


func _prism(body: StaticBody3D, x0: float, x1: float, length: float, start_y: float, end_y: float, thickness: float) -> void:
	var vertices := PackedVector3Array()
	for x in [x0, x1]:
		for point in [Vector2(0, start_y), Vector2(length, end_y)]:
			vertices.append(Vector3(x, point.y, point.x))
			vertices.append(Vector3(x, point.y - thickness, point.x))
	var shape := ConvexPolygonShape3D.new()
	shape.points = vertices
	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
