@tool
class_name TreeSpot
extends Node3D
## Одно дерево, правится руками: двигать, поворачивать, копировать (Ctrl+D), удалять; порода — в инспекторе.
## В редакторе видна модель (вблизи полная, дальше карточки); в игре деревья собираются в россыпи MultiMesh
## (DistrictScatter) с коллизией ствола, сам узел убирается. on_ground — дерево всегда стоит на земле: высоту
## берёт рельеф (узел земли в группе "blockout_terrain"), двигать можно только по плану.

## Породы — модели зоны 1 (assets/zone01/models): имя модели и радиус ствола для коллизии.
const SPECIES: Dictionary = {
	"spruce_a": ["spruce_forest_a", 0.3], "spruce_b": ["spruce_forest_b", 0.3], "spruce_young": ["spruce_young_a", 0.2],
	"pine": ["pine_forest", 0.3], "pine_slim": ["pine_slim_a", 0.25],
}
const MODELS: String = "res://assets/zone01/models/%s.glb"
const MATERIALS: String = "res://assets/zone01/materials"
## Дальше этого в редакторе — карточки (как в игре у россыпи: near_distance).
const EDITOR_NEAR_M: float = 80.0
## Дерево сидит в земле на столько (как у генератора: высота рельефа − 0,1).
const SINK_M: float = 0.1

@export_enum("spruce_a", "spruce_b", "spruce_young", "pine", "pine_slim") var species: String = "spruce_a":
	set(value):
		species = value
		_queue()
@export var on_ground: bool = true

static var _meshes: Dictionary = {}
var _pending: bool = false
var _snapping: bool = false


func _ready() -> void:
	if Engine.is_editor_hint():
		set_notify_transform(true)
		_preview()


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
	var near: Mesh = _mesh(MODELS % String(spec[0]))
	var far: Mesh = _mesh(MODELS % (String(spec[0]) + "_far"))
	for pair: Array in [[near, 0.0, EDITOR_NEAR_M if far else 0.0], [far, EDITOR_NEAR_M, 0.0]]:
		if pair[0] == null:
			continue
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "_Preview"
		mi.mesh = pair[0]
		mi.visibility_range_begin = float(pair[1])
		mi.visibility_range_end = float(pair[2])
		add_child(mi)


## Первый меш модели с материалами слотов из assets/zone01/materials (как у DistrictScatter), один на породу.
static func _mesh(path: String) -> Mesh:
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
					var mat_path: String = "%s/%s.tres" % [MATERIALS, mat.resource_name]
					if ResourceLoader.exists(mat_path):
						mesh.surface_set_material(i, load(mat_path))
		inst.free()
	_meshes[path] = mesh
	return mesh
