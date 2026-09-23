@tool
class_name ModelProp
extends StaticBody3D
## Проп из готовой модели (.glb / .gltf из assets/models) — ставится руками в редакторе в любую
## сцену (убежище, уровень). Коллизия — коробка box_size (ставится сама). Модели нет (игру
## запустили без assets/models) — вместо неё серая коробка того же размера: проект обязан
## работать и так. «Подогнать коробку» в инспекторе — размер коллизии по габариту модели.
## Из чего проп для шагов и попаданий — meta "surface" (metal, wood, concrete…), см. Surfaces.

@export_file("*.glb", "*.gltf") var model: String = "":
	set(v):
		model = v
		_rebuild()
## Коллизия и запасная коробка: размер и центр относительно узла, м.
@export var box_size: Vector3 = Vector3(1, 1, 1):
	set(v):
		box_size = v
		_rebuild()
@export var box_center: Vector3 = Vector3(0, 0.5, 0):
	set(v):
		box_center = v
		_rebuild()
## Цвет запасной коробки (когда модели нет).
@export var fallback_color: Color = Color(0.45, 0.45, 0.43)
## Нажать в инспекторе — коробка коллизии по габариту модели.
@export var fit_box_to_model: bool = false:
	set(v):
		if v:
			_fit_box()

var _built: Node3D
var _col: CollisionShape3D


func _ready() -> void:
	_rebuild()


func _rebuild() -> void:
	if not is_inside_tree():
		return
	# собранное — не часть сцены (не сохраняется в .tscn): при открытии строится заново
	if _built:
		_built.queue_free()
		_built = null
	if _col:
		_col.queue_free()
		_col = null
	if model != "" and ResourceLoader.exists(model):
		var ps := load(model) as PackedScene
		if ps:
			_built = ps.instantiate() as Node3D
	if _built == null:
		var mi := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = box_size
		mi.mesh = box
		mi.position = box_center
		var m := StandardMaterial3D.new()
		m.albedo_color = fallback_color
		m.roughness = 0.85
		mi.material_override = m
		_built = mi
	_built.name = "_Model"
	add_child(_built, false, Node.INTERNAL_MODE_FRONT)
	_col = CollisionShape3D.new()
	_col.name = "_Col"
	var shape := BoxShape3D.new()
	shape.size = box_size
	_col.shape = shape
	_col.position = box_center
	add_child(_col, false, Node.INTERNAL_MODE_FRONT)


## Габарит всех мешей модели (в координатах узла) → коробка коллизии.
func _fit_box() -> void:
	if _built == null:
		return
	var inv := global_transform.affine_inverse()
	var out := AABB()
	var first := true
	for n in _built.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null:
			continue
		var box: AABB = inv * mi.global_transform * mi.get_aabb()
		out = box if first else out.merge(box)
		first = false
	if first:
		return
	box_center = out.get_center()
	box_size = out.size
