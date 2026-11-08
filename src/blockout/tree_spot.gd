@tool
class_name TreeSpot
extends Node3D
## Одно дерево, правится руками: двигать, поворачивать, копировать (Ctrl+D), удалять; порода — в инспекторе.
## В редакторе видна модель (вблизи полная, дальше карточки); в игре деревья собираются в россыпи MultiMesh
## (DistrictScatter) с коллизией ствола, сам узел убирается: в «Санатории» — узлом Landscape, в «Пригороде» —
## россыпью своей породы с from_nodes (группа "tree_spot", та же сцена). on_ground — дерево всегда стоит на земле:
## высоту берёт рельеф (узел земли в группе "blockout_terrain"), двигать можно только по плану. Скрытое глазком —
## в игре его нет.

const M: String = "res://assets/zone01/models/"
const T: String = "res://assets/zone01/trees/"
const MATERIALS: String = "res://assets/zone01/materials"
const TREE_MATERIALS: String = "res://assets/zone01/trees/materials"
## Породы: модель, дальний вид (карточки), радиус ствола для коллизии, папка материалов слотов.
## «Санаторий» — spruce_a…pine_slim; «Пригород» — ключи его россыпей (data/zone01_vegetation.json).
const SPECIES: Dictionary = {
	"spruce_a": [M + "spruce_forest_a.glb", M + "spruce_forest_a_far.glb", 0.3, MATERIALS],
	"spruce_b": [M + "spruce_forest_b.glb", M + "spruce_forest_b_far.glb", 0.3, MATERIALS],
	"spruce_young": [M + "spruce_young_a.glb", M + "spruce_young_a_far.glb", 0.2, MATERIALS],
	"pine": [M + "pine_forest.glb", M + "pine_forest_far.glb", 0.3, MATERIALS],
	"pine_slim": [M + "pine_slim_a.glb", M + "pine_slim_a_far.glb", 0.25, MATERIALS],
	"tree_poplar_0": [T + "tree_poplar_0_lod0.glb", T + "tree_poplar_0_far.glb", 0.36, TREE_MATERIALS],
	"tree_poplar_1": [T + "tree_poplar_1_lod0.glb", T + "tree_poplar_1_far.glb", 0.44, TREE_MATERIALS],
	"tree_poplar_2": [T + "tree_poplar_2_lod0.glb", T + "tree_poplar_2_far.glb", 0.16, TREE_MATERIALS],
	"tree_maple_0": [T + "tree_maple_0_lod0.glb", T + "tree_maple_0_far.glb", 0.22, TREE_MATERIALS],
	"tree_maple_1": [T + "tree_maple_1_lod0.glb", T + "tree_maple_1_far.glb", 0.13, TREE_MATERIALS],
	"tree_maple_2": [T + "tree_maple_2_lod0.glb", T + "tree_maple_2_far.glb", 0.18, TREE_MATERIALS],
	"spruce_forest_a": [M + "spruce_forest_a.glb", M + "spruce_forest_a_far.glb", 0.3, MATERIALS],
	"spruce_forest_b": [M + "spruce_forest_b.glb", M + "spruce_forest_b_far.glb", 0.3, MATERIALS],
	"spruce_open": [M + "spruce_open.glb", M + "spruce_open_far.glb", 0.3, MATERIALS],
	"spruce_young_a": [M + "spruce_young_a.glb", M + "spruce_young_a_far.glb", 0.08, MATERIALS],
	"spruce_young_b": [M + "spruce_young_b.glb", M + "spruce_young_b_far.glb", 0.08, MATERIALS],
	"birch_a": [M + "birch_a.glb", M + "birch_a_far.glb", 0.21, MATERIALS],
	"birch_b": [M + "birch_b.glb", M + "birch_b_far.glb", 0.21, MATERIALS],
	"birch_c": [M + "birch_c.glb", M + "birch_c_far.glb", 0.21, MATERIALS],
	"birch_bare": [M + "birch_bare.glb", M + "birch_bare_far.glb", 0.21, MATERIALS],
	"birch_young": [M + "birch_young.glb", M + "birch_young_far.glb", 0.056, MATERIALS],
	"pine_young": [M + "pine_young.glb", M + "pine_young_far.glb", 0.077, MATERIALS],
	"pine_slim_a": [M + "pine_slim_a.glb", M + "pine_slim_a_far.glb", 0.118, MATERIALS],
	"pine_slim_b": [M + "pine_slim_b.glb", M + "pine_slim_b_far.glb", 0.157, MATERIALS],
	"pine_forest": [M + "pine_forest.glb", M + "pine_forest_far.glb", 0.254, MATERIALS],
	"pine_thick": [M + "pine_thick.glb", M + "pine_thick_far.glb", 0.371, MATERIALS],
	"pine_old": [M + "pine_old.glb", M + "pine_old_far.glb", 0.473, MATERIALS],
	"pine_twin": [M + "pine_twin.glb", M + "pine_twin_far.glb", 0.282, MATERIALS],
	"pine_yard": [M + "pine_yard.glb", M + "pine_yard_far.glb", 0.298, MATERIALS],
}
## Дальше этого в редакторе — карточки (как в игре у россыпи: near_distance).
const EDITOR_NEAR_M: float = 80.0
## Дерево сидит в земле на столько (как у генератора: высота рельефа − 0,1).
const SINK_M: float = 0.1

@export_enum("spruce_a", "spruce_b", "spruce_young", "pine", "pine_slim", "tree_poplar_0", "tree_poplar_1", "tree_poplar_2", "tree_maple_0", "tree_maple_1", "tree_maple_2", "spruce_forest_a", "spruce_forest_b", "spruce_open", "spruce_young_a", "spruce_young_b", "birch_a", "birch_b", "birch_c", "birch_bare", "birch_young", "pine_young", "pine_slim_a", "pine_slim_b", "pine_forest", "pine_thick", "pine_old", "pine_twin", "pine_yard") var species: String = "spruce_a":
	set(value):
		species = value
		_queue()
@export var on_ground: bool = true

static var _meshes: Dictionary = {}
var _pending: bool = false
var _snapping: bool = false


func _enter_tree() -> void:
	add_to_group("tree_spot")


func _ready() -> void:
	if Engine.is_editor_hint():
		set_notify_transform(true)
		_preview()


## Точка для россыпи DistrictScatter: x, y, z, поворот (град), масштаб.
func scatter_point() -> Array:
	var p: Vector3 = global_position
	return [p.x, p.y, p.z, rad_to_deg(global_rotation.y), tree_scale()]


func _notification(what: int) -> void:
	if what == NOTIFICATION_TRANSFORM_CHANGED and Engine.is_editor_hint() and on_ground and not _snapping:
		_snap.call_deferred()


func _queue() -> void:
	if not Engine.is_editor_hint() or not is_inside_tree() or _pending:
		return
	_pending = true
	_preview.call_deferred()


## Высота земли под деревом (NAN — земли рядом нет).
func ground_y() -> float:
	if not is_inside_tree():
		return NAN
	for t: Node in get_tree().get_nodes_in_group("blockout_terrain"):
		if t.has_method("height_at"):
			var h: float = float(t.call("height_at", global_position.x, global_position.z))
			if not is_nan(h):
				return h - SINK_M
	return NAN


## Масштаб дерева (россыпь берёт один на все оси).
func tree_scale() -> float:
	return global_transform.basis.get_scale().y


func _snap() -> void:
	var y: float = ground_y()
	if is_nan(y) or absf(global_position.y - y) < 0.01:
		return
	_snapping = true
	global_position.y = y
	_snapping = false


func _preview() -> void:
	_pending = false
	for child: Node in get_children():
		if String(child.name).begins_with("_"):
			child.free()
	var spec: Array = SPECIES.get(species, SPECIES.spruce_a)
	var near: Mesh = _mesh(String(spec[0]), String(spec[3]))
	var far: Mesh = _mesh(String(spec[1]), String(spec[3])) if String(spec[1]) != "" else null
	for pair: Array in [[near, 0.0, EDITOR_NEAR_M if far else 0.0], [far, EDITOR_NEAR_M, 0.0]]:
		if pair[0] == null:
			continue
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "_Preview"
		mi.mesh = pair[0]
		mi.visibility_range_begin = float(pair[1])
		mi.visibility_range_end = float(pair[2])
		add_child(mi)


## Первый меш модели с материалами слотов из папки материалов (как у DistrictScatter), один на модель.
static func _mesh(path: String, materials_dir: String = MATERIALS) -> Mesh:
	if _meshes.has(path):
		return _meshes[path]
	var mesh: Mesh = null
	if ResourceLoader.exists(path):
		var inst: Node = (load(path) as PackedScene).instantiate()
		var found: Array[Node] = inst.find_children("*", "MeshInstance3D", true, false)
		if not found.is_empty():
			mesh = ((found[0] as MeshInstance3D).mesh).duplicate()
			for i: int in range(mesh.get_surface_count()):
				var mat: Material = mesh.surface_get_material(i)
				if mat:
					var mat_path: String = "%s/%s.tres" % [materials_dir, mat.resource_name]
					if ResourceLoader.exists(mat_path):
						mesh.surface_set_material(i, load(mat_path))
		inst.free()
	_meshes[path] = mesh
	return mesh
