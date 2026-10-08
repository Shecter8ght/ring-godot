@tool
class_name DistrictModel
extends StaticBody3D
## Постройка или крупный проп района из GLB (генераторы tools/build_*.py): материалы — по именам
## слотов из папки materials_dir (<слот>.tres), коллизии — коробки из манифеста модели
## (<папка модели>/<manifest>.json → [имя модели].collisions). Двигать и крутить в редакторе.
## Модели нет (игра без assets) — серые коробки коллизий, чтобы уровень оставался проходимым.

@export_file("*.glb") var model: String = "":
	set(value):
		model = value
		_queue()
@export_file("*.json") var manifest: String = "":
	set(value):
		manifest = value
		_queue()
@export_dir var materials_dir: String = "res://assets/zone01/materials":
	set(value):
		materials_dir = value
		_queue()
@export var surface: String = "concrete":
	set(value):
		surface = value
		set_meta("surface", value)

var _pending: bool = false


func _ready() -> void:
	set_meta("surface", surface)
	_build()


func _queue() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	for child in get_children():
		if String(child.name).begins_with("_"):
			child.free()
	var boxes: Array = _collisions()
	for i in range(boxes.size()):
		var info: Dictionary = boxes[i]
		var shape := BoxShape3D.new()
		var size: Array = info.get("size", [1, 1, 1])
		var pos: Array = info.get("pos", [0, 0, 0])
		shape.size = Vector3(float(size[0]), float(size[1]), float(size[2]))
		var col := CollisionShape3D.new()
		col.name = "_Col_%d" % i
		col.shape = shape
		col.position = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
		col.rotation_degrees.y = float(info.get("yaw", 0.0))
		add_child(col)
	if model != "" and ResourceLoader.exists(model):
		var inst: Node3D = (load(model) as PackedScene).instantiate() as Node3D
		inst.name = "_Model"
		add_child(inst)
		# пустая папка материалов — у модели свои (Sketchfab): ничего не подменять
		if materials_dir != "":
			_apply_materials(inst)
		return
	# запасной вид — коробки коллизий
	var fallback := MeshInstance3D.new()
	fallback.name = "_Fallback"
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for info: Dictionary in boxes:
		var size: Array = info.get("size", [1, 1, 1])
		var pos: Array = info.get("pos", [0, 0, 0])
		var bm := BoxMesh.new()
		bm.size = Vector3(float(size[0]), float(size[1]), float(size[2]))
		st.append_from(bm, 0, Transform3D(Basis.from_euler(Vector3(0, deg_to_rad(float(info.get("yaw", 0.0))), 0)), Vector3(float(pos[0]), float(pos[1]), float(pos[2]))))
	fallback.mesh = st.commit()
	fallback.material_override = SectorMaterials.flat(Color(0.55, 0.55, 0.53), 0.9, 0.0)
	add_child(fallback)


func _collisions() -> Array:
	if manifest == "" or not FileAccess.file_exists(manifest):
		return []
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest))
	if not parsed is Dictionary:
		return []
	var entry: Dictionary = (parsed as Dictionary).get(model.get_file().get_basename(), {})
	return entry.get("collisions", [])


func _apply_materials(root: Node) -> void:
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		for i in range(mi.mesh.get_surface_count()):
			var src: Material = mi.mesh.surface_get_material(i)
			if src == null:
				continue
			var path: String = "%s/%s.tres" % [materials_dir, src.resource_name]
			if ResourceLoader.exists(path):
				mi.set_surface_override_material(i, load(path))
