@tool
class_name UrbanProps
extends Node3D
## Редактируемый блок статических примитивов. Повторяющиеся меши склеивает PropBatcher района.

@export var pieces: Array[Dictionary] = []:
	set(value):
		pieces = value
		if is_inside_tree():
			_build.call_deferred()
@export var surface: String = "concrete"

var _generated: Node3D


func _ready() -> void:
	_build()
	if not Engine.is_editor_hint():
		add_to_group("nav_source")


static func vec(value: Array) -> Vector3:
	return Vector3(float(value[0]), float(value[1]), float(value[2]))


func _build() -> void:
	if _generated:
		_generated.free()
	_generated = Node3D.new()
	_generated.name = "_Generated"
	add_child(_generated)
	for index in range(pieces.size()):
		var piece: Dictionary = pieces[index]
		var size: Vector3 = vec(piece.get("size", [1, 1, 1]))
		var center: Vector3 = vec(piece.get("at", [0, 0, 0]))
		var form: String = String(piece.get("shape", "box"))
		var mesh: PrimitiveMesh
		var shape: Shape3D
		match form:
			"sphere":
				var sphere := SphereMesh.new()
				sphere.radius = size.x * 0.5
				sphere.height = size.y
				sphere.radial_segments = 12
				sphere.rings = 6
				mesh = sphere
				var solid := SphereShape3D.new()
				solid.radius = size.x * 0.5
				shape = solid
			"cylinder":
				var cylinder := CylinderMesh.new()
				cylinder.top_radius = size.x * 0.5
				cylinder.bottom_radius = size.x * 0.5
				cylinder.height = size.y
				cylinder.radial_segments = 12
				mesh = cylinder
				var solid := CylinderShape3D.new()
				solid.radius = size.x * 0.5
				solid.height = size.y
				shape = solid
			_:
				var box := BoxMesh.new()
				box.size = size
				mesh = box
				var solid := BoxShape3D.new()
				solid.size = size
				shape = solid
		var instance := MeshInstance3D.new()
		instance.name = "Part_%d" % index
		instance.mesh = mesh
		instance.position = center
		var tint: Array = piece.get("color", [0.58, 0.59, 0.6])
		instance.material_override = SectorMaterials.flat(Color(float(tint[0]), float(tint[1]), float(tint[2])), 0.9, 0.0)
		if piece.has("rotation"):
			instance.rotation_degrees = vec(piece.rotation)
		if not bool(piece.get("shadow", true)):
			instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if bool(piece.get("render", true)):
			_generated.add_child(instance)
		if bool(piece.get("collision", false)):
			var body := StaticBody3D.new()
			body.name = "Solid_%d" % index
			body.transform = instance.transform
			body.set_meta("surface", String(piece.get("surface", surface)))
			var collision := CollisionShape3D.new()
			collision.shape = shape
			body.add_child(collision)
			_generated.add_child(body)
		if not bool(piece.get("render", true)):
			instance.free()
