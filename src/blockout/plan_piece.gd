@tool
class_name PlanPiece
extends Node3D
## Кусок улицы карты (покрытие, плита, стена, коробка — бордюр, разметка, ограждение, газон, — лестница, пандус,
## ряд колонн, балка или труба, фонарь-свет, надпись, вырез в земле), правится руками: двигать (W), поворачивать (E),
## растягивать (R), копировать (Ctrl+D), удалять, прятать глазком (docs/level_editing.md).
## list — из какого списка плана запись; data — запись как у генератора (в мире, на месте base; у записей-массивов —
## под ключом "a"); base — трансформ узла при переносе. Уровень собирает список по узлам (MallLandscape.
## _pieces_from_nodes), сдвигая запись так, как узел сдвинули от base. Поворот — только вокруг вертикали; у покрытий,
## плит, вырезов и колонн — шагами по 90°, у пандуса — только разворот на 180° (уклон у него всегда вдоль Z); стена,
## повёрнутая не на 90°, становится коробкой того же материала. В редакторе у куска — невидимая коробка по его габариту:
## щелчок по стене, бордюру, ступеням выделяет кусок, а после правки улицы пересобираются сами (MallLandscape.
## request_rebuild).

const ARRAY_LISTS: Array[String] = ["beams", "lamps", "ground_holes", "walk_holes"]
const HOLE_LISTS: Array[String] = ["ground_holes", "walk_holes"]
## Ширина и высота рамки, за которую берут вырез в земле (сам вырез — пустота, щёлкнуть в него нельзя), м.
const HOLE_FRAME_M: Vector2 = Vector2(0.3, 0.12)

@export var list: String = ""
@export var data: Dictionary = {}
@export var base: Transform3D = Transform3D.IDENTITY
## Место записи в прежнем списке: куски собираются по нему (у физики — тот же порядок, что у генератора).
@export var order: int = 1000000
## Коробка для щелчка в редакторе (в осях узла).
@export var pick_size: Vector3 = Vector3.ONE
@export var pick_center: Vector3 = Vector3.ZERO

static var _pick_material: StandardMaterial3D


func _enter_tree() -> void:
	add_to_group("plan_piece")
	if Engine.is_editor_hint():
		_notify_landscape()


func _exit_tree() -> void:
	if Engine.is_editor_hint():
		_notify_landscape()


func _ready() -> void:
	if Engine.is_editor_hint():
		set_notify_transform(true)
		_pick()


func _notification(what: int) -> void:
	if not Engine.is_editor_hint():
		return
	if what == NOTIFICATION_TRANSFORM_CHANGED or what == NOTIFICATION_VISIBILITY_CHANGED:
		_notify_landscape()


func _notify_landscape() -> void:
	var n: Node = get_parent()
	while n != null and not n.has_method("request_rebuild"):
		n = n.get_parent()
	if n != null:
		n.call("request_rebuild")


## Невидимая коробка (у выреза — рамка по краю) для щелчка; не своя у сцены — в .tscn не попадает.
func _pick() -> void:
	for old: Node in get_children(true):
		if old.name.begins_with("_Pick"):
			old.free()
	if _pick_material == null:
		_pick_material = StandardMaterial3D.new()
		_pick_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		_pick_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		_pick_material.albedo_color = Color(0.4, 0.8, 1.0, 0.0)
		_pick_material.cull_mode = BaseMaterial3D.CULL_DISABLED
		_pick_material.no_depth_test = false
	var boxes: Array = []
	if list in HOLE_LISTS:
		var s: Vector3 = pick_size
		var f: float = HOLE_FRAME_M.x
		var h: float = HOLE_FRAME_M.y
		boxes = [[Vector3(-s.x * 0.5, 0.0, 0.0), Vector3(f, h, s.z)], [Vector3(s.x * 0.5, 0.0, 0.0), Vector3(f, h, s.z)],
			[Vector3(0.0, 0.0, -s.z * 0.5), Vector3(s.x, h, f)], [Vector3(0.0, 0.0, s.z * 0.5), Vector3(s.x, h, f)]]
	else:
		boxes = [[pick_center, pick_size]]
	var i: int = 0
	for b: Array in boxes:
		var box: BoxMesh = BoxMesh.new()
		box.size = (b[1] as Vector3).max(Vector3.ONE * 0.05)
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = "_Pick%d" % i
		mi.mesh = box
		mi.position = b[0]
		mi.material_override = _pick_material
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# не рисуется вовсе (дальше 1 см от камеры скрыта): нужен только габарит — рамка выделения редактора
		mi.visibility_range_end = 0.01
		add_child(mi)
		i += 1
	update_gizmos()


## Запись по нынешнему положению узла: [список, запись] (стена, повёрнутая не на 90°, уходит в «boxes»).
func current_entry() -> Array:
	var entry: Variant = data.get("a") if list in ARRAY_LISTS else data
	if global_transform.is_equal_approx(base):
		return [list, (entry as Array).duplicate(true) if entry is Array else (entry as Dictionary).duplicate(true)]
	# delta — куда переехала точка мира, бывшая в куске; rel — сдвиг в осях самого куска (масштаб по его сторонам)
	var delta: Transform3D = global_transform * base.affine_inverse()
	var rel: Transform3D = base.affine_inverse() * global_transform
	var rot: Basis = rel.basis.orthonormalized()
	var dyaw: float = rad_to_deg(atan2(rot.z.x, rot.z.z))
	var scale_xyz: Vector3 = rel.basis.get_scale().abs()
	var quarter: int = posmod(int(round(dyaw / 90.0)), 4)
	var free_turn: bool = absf(dyaw - round(dyaw / 90.0) * 90.0) > 0.5
	match list:
		"boxes":
			var e: Dictionary = (entry as Dictionary).duplicate(true)
			e.at = _pt(delta, e.at as Array)
			var sz: Array = e.size
			e.size = [snappedf(float(sz[0]) * scale_xyz.x, 0.001), snappedf(float(sz[1]) * scale_xyz.y, 0.001),
				snappedf(float(sz[2]) * scale_xyz.z, 0.001)]
			e.yaw = snappedf(float(e.get("yaw", 0.0)) + dyaw, 0.01)
			return ["boxes", e]
		"walls":
			var w: Dictionary = (entry as Dictionary).duplicate(true)
			var r: Array = w.rect
			var c: Vector3 = Vector3((float(r[0]) + float(r[2])) * 0.5, (float(w.y0) + float(w.y1)) * 0.5, (float(r[1]) + float(r[3])) * 0.5)
			if free_turn:
				# в формате стены поворота нет — коробка того же материала
				var cc: Vector3 = delta * c
				return ["boxes", {"at": [snappedf(cc.x, 0.001), snappedf(cc.y, 0.001), snappedf(cc.z, 0.001)],
					"size": [snappedf(absf(float(r[2]) - float(r[0])) * scale_xyz.x, 0.001),
						snappedf((float(w.y1) - float(w.y0)) * scale_xyz.y, 0.001),
						snappedf(absf(float(r[3]) - float(r[1])) * scale_xyz.z, 0.001)],
					"mat": w.get("mat", "wall"), "yaw": snappedf(dyaw, 0.01), "solid": true}]
			w.rect = _rect(delta, r, quarter, scale_xyz)
			w.y0 = _y(delta, c, float(w.y0))
			w.y1 = _y(delta, c, float(w.y1))
			return ["walls", w]
		"surfaces", "slabs", "columns":
			var s: Dictionary = (entry as Dictionary).duplicate(true)
			var r2: Array = s.rect
			var c2: Vector3 = Vector3((float(r2[0]) + float(r2[2])) * 0.5, 0.0, (float(r2[1]) + float(r2[3])) * 0.5)
			s.rect = _rect(delta, r2, quarter, scale_xyz)
			if s.has("holes"):
				var holes: Array = []
				for h: Array in s.holes:
					holes.append(_rect(delta, h, quarter, scale_xyz))
				s.holes = holes
			for key: String in ["y", "y_top", "y0", "y1"]:
				if s.has(key):
					s[key] = _y(delta, c2, float(s[key]))
			if s.has("t"):
				s.t = snappedf(float(s.t) * scale_xyz.y, 0.001)
			return [list, s]
		"ground_holes", "walk_holes":
			return [list, _rect(delta, entry as Array, quarter, scale_xyz)]
		"ramps":
			# уклон всегда вдоль Z: поворот на 90° пандус не умеет (остаётся вдоль Z), на 180° — разворот
			var rp: Dictionary = (entry as Dictionary).duplicate(true)
			var mid_y: float = (float(rp.y0) + float(rp.y1)) * 0.5
			var c3: Vector3 = Vector3((float(rp.x0) + float(rp.x1)) * 0.5, mid_y, (float(rp.z0) + float(rp.z1)) * 0.5)
			var c4: Vector3 = delta * c3
			var flip: float = -1.0 if quarter == 2 else 1.0
			var sx: float = scale_xyz.z if quarter % 2 == 1 else scale_xyz.x
			var sz2: float = scale_xyz.x if quarter % 2 == 1 else scale_xyz.z
			for pair: Array in [["x0", c3.x, c4.x, sx], ["x1", c3.x, c4.x, sx], ["z0", c3.z, c4.z, sz2], ["z1", c3.z, c4.z, sz2]]:
				rp[pair[0]] = snappedf(float(pair[2]) + (float(rp[pair[0]]) - float(pair[1])) * float(pair[3]) * flip, 0.001)
			rp.y0 = snappedf(c4.y + (float(rp.y0) - mid_y) * scale_xyz.y, 0.001)
			rp.y1 = snappedf(c4.y + (float(rp.y1) - mid_y) * scale_xyz.y, 0.001)
			return ["ramps", rp]
		"stairs":
			var st: Dictionary = (entry as Dictionary).duplicate(true)
			st.from = _pt(delta, st.from as Array)
			st.to = _pt(delta, st.to as Array)
			st.width = snappedf(float(st.width) * scale_xyz.x, 0.001)
			return ["stairs", st]
		"beams":
			var b: Array = (entry as Array).duplicate(true)
			b[0] = _pt(delta, b[0] as Array)
			b[1] = _pt(delta, b[1] as Array)
			return ["beams", b]
		"lamps":
			var l: Array = (entry as Array).duplicate(true)
			var p: Array = _pt(delta, [l[0], l[1], l[2]])
			l[0] = p[0]
			l[1] = p[1]
			l[2] = p[2]
			return ["lamps", l]
		"signs", "loot":
			var d: Dictionary = (entry as Dictionary).duplicate(true)
			d.at = _pt(delta, d.at as Array)
			if d.has("yaw"):
				d.yaw = snappedf(float(d.yaw) + dyaw, 0.01)
			return [list, d]
	return [list, entry]


static func _pt(delta: Transform3D, p: Array) -> Array:
	var v: Vector3 = delta * Vector3(float(p[0]), float(p[1]), float(p[2]))
	return [snappedf(v.x, 0.001), snappedf(v.y, 0.001), snappedf(v.z, 0.001)]


## Высота у середины куска после сдвига (подъём и растяжение по высоте — от узла).
static func _y(delta: Transform3D, c: Vector3, y: float) -> float:
	return snappedf((delta * Vector3(c.x, y, c.z)).y, 0.001)


## Прямоугольник плана [x0, z0, x1, z1]: середина — сдвигом узла, стороны — растяжением, поворот — четвертями
## (90° и 270° меняют стороны местами).
static func _rect(delta: Transform3D, r: Array, quarter: int, scale_xyz: Vector3) -> Array:
	var c: Vector3 = delta * Vector3((float(r[0]) + float(r[2])) * 0.5, 0.0, (float(r[1]) + float(r[3])) * 0.5)
	var hx: float = absf(float(r[2]) - float(r[0])) * 0.5 * scale_xyz.x
	var hz: float = absf(float(r[3]) - float(r[1])) * 0.5 * scale_xyz.z
	if quarter % 2 == 1:
		var t: float = hx
		hx = hz
		hz = t
	return [snappedf(c.x - hx, 0.001), snappedf(c.z - hz, 0.001), snappedf(c.x + hx, 0.001), snappedf(c.z + hz, 0.001)]
