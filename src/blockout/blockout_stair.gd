@tool
class_name BlockoutStair
extends Node3D
## Марш лестницы блокаута, правится руками: узел стоит в середине нижнего края, лестница идёт вперёд (−Z узла)
## на run метров и поднимается на rise. Ступени видом; шаг игрока — по наклонной поверхности (без застревания капсулы).
## solid — ступени сплошные до отметки solid_bottom (от низа марша, обычно отрицательная) и твёрдые; иначе — тонкие
## ступени 0,16 м (винтовая лестница маяка). В игре марш склеивается с остальным блокаутом (BlockoutMerge).

@export var run: float = 3.0:
	set(value):
		run = value
		_queue()
@export var rise: float = 2.0:
	set(value):
		rise = value
		_queue()
@export var width: float = 1.2:
	set(value):
		width = value
		_queue()
@export var steps: int = 12:
	set(value):
		steps = maxi(value, 1)
		_queue()
@export var solid: bool = true:
	set(value):
		solid = value
		_queue()
@export var solid_bottom: float = -0.05:
	set(value):
		solid_bottom = value
		_queue()
@export var material: Material:
	set(value):
		material = value
		_queue()

var _pending: bool = false


func _ready() -> void:
	if Engine.is_editor_hint():
		_preview()


func _queue() -> void:
	if not Engine.is_editor_hint() or not is_inside_tree() or _pending:
		return
	_pending = true
	_preview.call_deferred()


## Низ и верх марша в мире (середины краёв).
func world_ends() -> Array[Vector3]:
	var xf: Transform3D = global_transform
	return [xf * Vector3.ZERO, xf * Vector3(0.0, rise, -run)]


## Вид в редакторе — ступени коробками (в игре — склейка, этот вид не строится).
func _preview() -> void:
	_pending = false
	var old: Node = get_node_or_null("_Preview")
	if old:
		old.free()
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var cube: BoxMesh = BoxMesh.new()
	cube.size = Vector3.ONE
	var arrays: Array = cube.get_mesh_arrays()
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var norms: PackedVector3Array = arrays[Mesh.ARRAY_NORMAL]
	var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
	for i: int in range(steps):
		var tread: float = rise * float(i + 1) / float(steps)
		var h: float = maxf(tread - solid_bottom, 0.05) if solid else 0.16
		var at: Vector3 = Vector3(0.0, tread - h * 0.5, -run * (float(i) + 0.5) / float(steps))
		var size: Vector3 = Vector3(width, h, run / float(steps) + 0.01)
		for k: int in idx:
			st.set_normal(norms[k])
			st.add_vertex(at + verts[k] * size)
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "_Preview"
	mi.mesh = st.commit()
	mi.material_override = material
	add_child(mi)
	update_gizmos()
