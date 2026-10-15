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
## Здание полое внутри: сплошной невидимый объём (по коробкам коллизий, чуть внутри стен) только
## отбрасывает тень — низкое солнце не пробивает дом насквозь через окна, подъезды и швы.
@export var shadow_proxy: bool = false:
	set(value):
		shadow_proxy = value
		_queue()
## Фонарный столб: где светильник (локально, низ стекла), Vector3.ZERO — не фонарь. Горит в
## сумерки и ночью (LampHead, как StreetLamp).
@export var lamp_head: Vector3 = Vector3.ZERO:
	set(value):
		lamp_head = value
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
		var angles: Array = info.get("rotation", [0.0, float(info.get("yaw", 0.0)), 0.0])
		col.rotation_degrees = Vector3(float(angles[0]), float(angles[1]), float(angles[2]))
		add_child(col)
	if shadow_proxy:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		for info: Dictionary in boxes:
			var size: Array = info.get("size", [1, 1, 1])
			var pos: Array = info.get("pos", [0, 0, 0])
			var bm := BoxMesh.new()
			# внутри фасада на 0.4 м — не затеняет собственную стену на солнечной стороне
			bm.size = Vector3(maxf(0.1, float(size[0]) - 0.8), float(size[1]), maxf(0.1, float(size[2]) - 0.8))
			st.append_from(bm, 0, Transform3D(Basis.from_euler(Vector3(0, deg_to_rad(float(info.get("yaw", 0.0))), 0)), Vector3(float(pos[0]), float(pos[1]), float(pos[2]))))
		var proxy := MeshInstance3D.new()
		proxy.name = "_ShadowProxy"
		proxy.mesh = st.commit()
		proxy.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		proxy.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		add_child(proxy)
	if model != "" and ResourceLoader.exists(model):
		var inst: Node3D = (load(model) as PackedScene).instantiate() as Node3D
		inst.name = "_Model"
		add_child(inst)
		# пустая папка материалов — у модели свои (Sketchfab): ничего не подменять
		if materials_dir != "":
			_apply_materials(inst)
		else:
			_lit_scans(inst)
		if lamp_head != Vector3.ZERO:
			var lh := LampHead.new()
			lh.name = "_LampHead"
			lh.position = lamp_head
			inst.add_child(lh)
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


## Фотосканы со Sketchfab часто без освещения (KHR_materials_unlit — свет запечён в текстуру):
## в игре такой предмет светится сам по себе, ночью — как фонарь. Делаем обычным, освещаемым.
func _lit_scans(root: Node) -> void:
	for n in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as BaseMaterial3D
			if m == null or m.shading_mode != BaseMaterial3D.SHADING_MODE_UNSHADED:
				continue
			var lit := m.duplicate() as BaseMaterial3D
			lit.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
			lit.roughness = maxf(lit.roughness, 0.85)
			lit.metallic = 0.0
			mi.set_surface_override_material(i, lit)
