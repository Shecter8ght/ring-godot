extends Node3D
## Тестовый полигон: процедурные стены и ящики, чтобы проверять свет, тени, укрытия и движение.
## Это не сектор — сектора собираются из данных в src/world/sector_builder.gd.

@onready var _props: Node3D = $Props


func _ready() -> void:
	var wall := StandardMaterial3D.new()
	wall.albedo_color = Color(0.55, 0.52, 0.47)
	wall.roughness = 0.9
	var crate := StandardMaterial3D.new()
	crate.albedo_color = Color(0.36, 0.28, 0.18)
	crate.roughness = 0.85
	# Г-образная стена и ряд ящиков — типичная ситуация укрытия.
	_box(Vector3(0, 1.5, -8), Vector3(16, 3, 0.3), wall)
	_box(Vector3(-8, 1.5, -2), Vector3(0.3, 3, 12), wall)
	_box(Vector3(8, 1.5, 4), Vector3(0.3, 3, 8), wall)
	for i in range(5):
		_box(Vector3(-4 + i * 1.6, 0.45, 3), Vector3(1.2, 0.9, 1.0), crate)
	for i in range(3):
		_box(Vector3(5, 0.6, -4 + i * 1.5), Vector3(1.2, 1.2, 1.2), crate)
	# Колонны — вертикальные ориентиры для теней.
	for x in [-5.0, 0.0, 5.0]:
		_box(Vector3(x, 2.0, -12), Vector3(0.6, 4, 0.6), wall)


func _box(at: Vector3, size: Vector3, mat: Material) -> void:
	var body := StaticBody3D.new()
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = mat
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(mi)
	body.add_child(cs)
	body.position = at
	_props.add_child(body)
