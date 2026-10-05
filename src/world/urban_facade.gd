@tool
extends Node3D
## Модульные фасады существующего BlockoutBuilding: этажный ритм, окна, цоколь и крыша.

@export_range(1, 8) var floors: int = 5:
	set(value):
		floors = clampi(value, 1, 8)
		_queue_build()
@export var style: String = "residential":
	set(value):
		style = value
		_queue_build()
@export var window_pitch: float = 4.5:
	set(value):
		window_pitch = maxf(0.5, value)
		_queue_build()

var _pending: bool = false


func _ready() -> void:
	var building: BlockoutBuilding = get_parent() as BlockoutBuilding
	if building:
		building.geometry_rebuilt.connect(_queue_build)
	_build()


func _queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	var building := get_parent() as BlockoutBuilding
	if building == null:
		return
	var old: Node = get_node_or_null("_Generated")
	if old:
		old.free()
	var root := Node3D.new()
	root.name = "_Generated"
	add_child(root)
	var facade := BlockoutMesh.new()
	var w: float = building.size.x
	var d: float = building.size.y
	var floor_height: float = building.height / float(floors)
	var facade_offset: float = building.wall_thickness * 0.5 + 0.04
	for floor_index in range(0 if style == "garage" else floors):
		var y: float = float(floor_index) * floor_height
		for x_index in range(maxi(1, int(w / window_pitch))):
			var x: float = -w * 0.5 + window_pitch * 0.5 + float(x_index) * window_pitch
			for side in [-1.0, 1.0]:
				facade.box("steel_dark", Vector3(x, y + floor_height * 0.56, side * (d * 0.5 + facade_offset)), Vector3(window_pitch * 0.52, floor_height * 0.48, 0.06))
		for z_index in range(maxi(1, int(d / window_pitch))):
			var z: float = -d * 0.5 + window_pitch * 0.5 + float(z_index) * window_pitch
			for side in [-1.0, 1.0]:
				facade.box("steel_dark", Vector3(side * (w * 0.5 + facade_offset), y + floor_height * 0.56, z), Vector3(0.06, floor_height * 0.48, window_pitch * 0.52))
		if style != "garage":
			facade.box("gb_structural", Vector3(0, y + 0.08, 0), Vector3(w + 0.25, 0.16, d + 0.25))
	var elevation: StaticBody3D = facade.emit(root, "Elevation", false, true)
	var windows: MeshInstance3D = elevation.get_node_or_null("steel_dark") as MeshInstance3D
	if windows:
		windows.material_override = SectorMaterials.flat(Color(0.15, 0.2, 0.22), 0.95, 0.0)
	if floors > 1:
		_add_deck(root, building, "FirstFloorCeiling", floor_height)
	_add_deck(root, building, "Roof", building.height)


func _add_deck(root: Node3D, building: BlockoutBuilding, deck_name: String, deck_height: float) -> void:
	var w: float = building.size.x
	var d: float = building.size.y
	var roof := Node3D.new()
	roof.name = deck_name
	roof.position.y = deck_height
	roof.add_to_group("decks")
	roof.set_meta("urban_cover_size", building.size)
	root.add_child(roof)
	roof.set_meta("deck_y", roof.global_position.y if is_inside_tree() else deck_height)
	var slab := BlockoutMesh.new()
	slab.box("gb_slab", Vector3(0, 0.05, 0), Vector3(w + 0.3, 0.3, d + 0.3))
	var body: StaticBody3D = slab.emit(roof, "RoofMesh", false, false)
	# Меши перекрытия должны быть непосредственными детьми группы decks.
	for mesh_node in body.get_children():
		mesh_node.reparent(roof)
	body.free()
	var collision_body := StaticBody3D.new()
	collision_body.name = "RoofCollision"
	collision_body.position.y = 0.05
	collision_body.set_meta("surface", "concrete")
	var shape := BoxShape3D.new()
	shape.size = Vector3(w + 0.3, 0.3, d + 0.3)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	collision_body.add_child(collision)
	roof.add_child(collision_body)
