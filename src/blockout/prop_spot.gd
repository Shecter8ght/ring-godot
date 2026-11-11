@tool
class_name PropSpot
extends Node3D
## Одна вещь наполнения карты (машина, киоск, забор, мусор, модель города), правится руками: двигать (W),
## поворачивать (E), масштаб (R), копировать (Ctrl+D), удалять, прятать глазком (docs/level_editing.md).
## item — запись наполнения как у генератора: [набор или «m:модель», x, z, поворот°, масштаб, подъём, оттенок, крен°,
## закреплённая модель «вперемешку»];
## base — где вещь стояла при переносе (её мировой трансформ). В игре уровень берёт item, сдвинутый так, как узел
## сдвинули от base (MallLandscape.load_plan → plan.filler.items), сам узел убирается; в редакторе виден её вид —
## сетку даёт россыпь MallFiller (preview_mesh), поэтому вещь выделяется щелчком.

@export var item: Array = []
@export var base: Transform3D = Transform3D.IDENTITY
## Место записи в прежнем плане: вещи собираются по нему (копия — рядом с исходной; новые — в конце).
@export var order: int = 1000000

var _pending: bool = false


func _enter_tree() -> void:
	add_to_group("prop_spot")


func _ready() -> void:
	if Engine.is_editor_hint():
		_queue()


func _queue() -> void:
	if _pending:
		return
	_pending = true
	_preview.call_deferred()


## Запись наполнения по нынешнему положению узла (сдвиг, поворот вокруг вертикали, масштаб — от base).
func current_item() -> Array:
	var delta: Transform3D = global_transform * base.affine_inverse()
	if delta.is_equal_approx(Transform3D.IDENTITY):
		return item.duplicate()
	var out: Array = item.duplicate()
	while out.size() < 6:
		out.append(1.0 if out.size() == 4 else 0.0)
	var o: Vector3 = delta * base.origin
	var rot: Basis = delta.basis.orthonormalized()
	out[1] = snappedf(o.x, 0.001)
	out[2] = snappedf(o.z, 0.001)
	out[3] = snappedf(float(item[3]) + rad_to_deg(atan2(rot.z.x, rot.z.z)), 0.01)
	out[4] = snappedf(float(out[4]) * delta.basis.get_scale().y, 0.001)
	out[5] = snappedf(float(out[5]) + o.y - base.origin.y, 0.001)
	return out


func _preview() -> void:
	_pending = false
	for child: Node in get_children():
		if String(child.name).begins_with("_"):
			child.free()
	if item.is_empty():
		return
	var filler: Node = get_parent()
	while filler != null and not filler.has_method("preview_mesh"):
		filler = filler.get_parent()
	if filler == null:
		return
	var mesh: Mesh = filler.call("preview_mesh", String(item[0]), float(item[1]), float(item[2]),
		String(item[8]) if item.size() > 8 else "") as Mesh
	if mesh == null:
		return
	# узел стоит ровно так, как вещь ставит россыпь (поворот модели, крен, масштаб, подъём) — вид без своего сдвига
	var mi: MeshInstance3D = MeshInstance3D.new()
	mi.name = "_Preview"
	mi.mesh = mesh
	if mesh.get_surface_count() > 0 and mesh.surface_get_material(0) == null:
		mi.material_override = filler.call("preview_material") as Material
	add_child(mi)
	# щелчок по вещи — гизмо по габариту вида (addons/ring_level_tools/pick_gizmo.gd)
	update_gizmos()
