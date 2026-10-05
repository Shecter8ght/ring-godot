@tool
class_name UrbanTerrain
extends Node3D
## Небольшой городской уклон, плоские строительные площадки и низкий берег реки.

@export_file("*.json") var data_path: String = "res://data/sectors/zone02_urban_belt.json":
	set(value):
		data_path = value
		_queue_build()
@export var tile_size: float = 100.0:
	set(value):
		tile_size = maxf(5.0, value)
		_queue_build()
@export var sample_step: float = 5.0:
	set(value):
		sample_step = maxf(1.0, value)
		_queue_build()

var _definition: Dictionary = {}
var _pending: bool = false


static func height_at(x: float, z: float) -> float:
	return -0.004 * x - 0.004 * z


func sample_height(x: float, z: float) -> float:
	var height: float = height_at(x, z)
	for pad_value in (_definition.get("terrain", {}) as Dictionary).get("pads", []):
		var pad: Dictionary = pad_value
		var rect: Array = pad.rect
		var outside_x: float = maxf(maxf(float(rect[0]) - x, x - float(rect[2])), 0.0)
		var outside_z: float = maxf(maxf(float(rect[1]) - z, z - float(rect[3])), 0.0)
		var distance: float = maxf(outside_x, outside_z)
		if distance < 8.0:
			height = lerpf(float(pad.height), height, smoothstep(0.0, 8.0, distance))
	var river: Dictionary = _definition.get("river", {})
	var river_points: Array = river.get("points", [])
	var bank_distance: float = INF
	for index in range(river_points.size() - 1):
		var from := Vector2(float(river_points[index][0]), float(river_points[index][1]))
		var to := Vector2(float(river_points[index + 1][0]), float(river_points[index + 1][1]))
		bank_distance = minf(bank_distance, Vector2(x, z).distance_to(Geometry2D.get_closest_point_to_segment(Vector2(x, z), from, to)))
	var half_width: float = float(river.get("width", 100.0)) * 0.5
	if bank_distance < half_width + 16.0:
		height = lerpf(-11.0, height, smoothstep(half_width - 10.0, half_width + 16.0, bank_distance))
	return height


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
	_definition = SectorBuilder.load_def(data_path)
	var old: Node = get_node_or_null("_Generated")
	if old:
		old.free()
	var root := Node3D.new()
	root.name = "_Generated"
	add_child(root)
	var bounds: Array = _definition.get("bounds", [-750, -625, 750, 625])
	var x: float = float(bounds[0])
	while x < float(bounds[2]):
		var z: float = float(bounds[1])
		while z < float(bounds[3]):
			_tile(root, x, z, minf(tile_size, float(bounds[2]) - x), minf(tile_size, float(bounds[3]) - z))
			z += tile_size
		x += tile_size


func _tile(root: Node3D, x: float, z: float, width: float, depth: float) -> void:
	var columns: int = maxi(2, int(round(width / sample_step)) + 1)
	var rows: int = maxi(2, int(round(depth / sample_step)) + 1)
	var step_x: float = width / float(columns - 1)
	var step_z: float = depth / float(rows - 1)
	var samples := PackedFloat32Array()
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for row in range(rows):
		for column in range(columns):
			samples.append(sample_height(x + float(column) * step_x, z + float(row) * step_z))
	for row in range(rows - 1):
		for column in range(columns - 1):
			var a := Vector3(float(column) * step_x, samples[row * columns + column], float(row) * step_z)
			var b := Vector3(float(column + 1) * step_x, samples[row * columns + column + 1], float(row) * step_z)
			var c := Vector3(float(column) * step_x, samples[(row + 1) * columns + column], float(row + 1) * step_z)
			var d := Vector3(float(column + 1) * step_x, samples[(row + 1) * columns + column + 1], float(row + 1) * step_z)
			for vertex in [a, b, c, b, d, c]:
				st.set_uv(Vector2(vertex.x, vertex.z) * 0.1)
				st.add_vertex(vertex)
	st.generate_normals()
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = "Terrain_%d_%d" % [int(x), int(z)]
	mesh_instance.position = Vector3(x, 0, z)
	mesh_instance.mesh = st.commit()
	mesh_instance.material_override = SectorMaterials.flat(Color(0.29, 0.37, 0.28), 0.95, 0.0)
	mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	root.add_child(mesh_instance)
	var body := StaticBody3D.new()
	body.name = "Ground_%d_%d" % [int(x), int(z)]
	body.position = Vector3(x + width * 0.5, 0, z + depth * 0.5)
	body.set_meta("surface", "concrete")
	var shape := HeightMapShape3D.new()
	shape.map_width = columns
	shape.map_depth = rows
	shape.map_data = samples
	var collision := CollisionShape3D.new()
	collision.shape = shape
	collision.scale = Vector3(step_x, 1, step_z)
	body.add_child(collision)
	root.add_child(body)
