extends Node
## Тени деревьев (Balance.TREE_SHADOWS, приём Road to Vostok — docs/research/road_to_vostok.md):
## видимые модели деревьев тень не отбрасывают; вблизи тень — невидимая копия полной модели «только тень»,
## дальше — скрещённые карточки дальнего вида «только тень»; пороги клетки у них совпадают (ни дыр, ни двойной тени).
## Зона 1 (DistrictScatter) и «Проспект» (MallFiller, растения P_* с LOD); кусты ниже min_height — как были.
## Ещё — сколько треугольников деревья дают в тень вокруг точки до дальности тени солнца: было / стало.
## tools/godot.cmd --headless res://tools/tree_shadows_test.tscn

const ZONE01 := "res://scenes/levels/zone01_mall.tscn"
const PROSPEKT := "res://scenes/levels/prospekt_study.tscn"
## Точки подсчёта треугольников в тени: опушка зоны 1 и сквер «Проспекта» (как у стендов замера).
const SHADOW_DISTANCE := 260.0

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	await _zone01()
	await _prospekt()
	print("tree_shadows_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _zone01() -> void:
	var level: Node = (load(ZONE01) as PackedScene).instantiate()
	add_child(level)
	await _frames(3)
	var scatters: Array[Node] = level.find_children("*", "DistrictScatter", true, false)
	var trees: int = 0
	var bad_visible: int = 0
	var bad_pairs: int = 0
	var near_n: int = 0
	var card_n: int = 0
	for raw: Node in scatters:
		var s: DistrictScatter = raw as DistrictScatter
		if not s.shadows or s.far_model == "":
			continue
		trees += 1
		for child: Node in s.get_children():
			var n: String = String(child.name)
			if not child is MultiMeshInstance3D:
				continue
			var mmi: MultiMeshInstance3D = child as MultiMeshInstance3D
			if n.begins_with("_Cell_") or n.begins_with("_Mid_") or n.begins_with("_Far_"):
				if mmi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
					bad_visible += 1
			if n.begins_with("_Cell_"):
				var key: String = n.trim_prefix("_Cell_")
				var near: MultiMeshInstance3D = s.get_node_or_null("_ShadowNear_" + key) as MultiMeshInstance3D
				var cards: MultiMeshInstance3D = s.get_node_or_null("_ShadowCards_" + key) as MultiMeshInstance3D
				var ok: bool = near != null and cards != null \
					and near.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY \
					and cards.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY \
					and is_equal_approx(near.visibility_range_end, cards.visibility_range_begin) \
					and near.multimesh.instance_count == cards.multimesh.instance_count
				if not ok:
					bad_pairs += 1
				else:
					near_n += 1
					card_n += 1
	_check("зона 1: есть деревья с дальним видом", trees > 5, str(trees))
	_check("зона 1: видимые модели деревьев тень не отбрасывают", bad_visible == 0, "%d с тенью" % bad_visible)
	_check("зона 1: у каждой клетки тень вблизи (модель) и дальше (карточки), порог общий", bad_pairs == 0 and near_n > 0,
		"%d пар, %d плохих" % [near_n, bad_pairs])
	var at: Vector3 = _densest(level)
	_report("зона 1", level, at)
	level.queue_free()
	await _frames(2)


func _prospekt() -> void:
	var level: Node = (load(PROSPEKT) as PackedScene).instantiate()
	add_child(level)
	await _frames(3)
	var trees: int = 0
	var bad: int = 0
	var bushes_shadow: int = 0
	for raw: Node in level.find_children("model_P_*", "MultiMeshInstance3D", true, false):
		var mmi: MultiMeshInstance3D = raw as MultiMeshInstance3D
		var n: String = String(mmi.name)
		var is_tree: bool = n.begins_with("model_P_birch") or n.begins_with("model_P_linden") or n.begins_with("model_P_poplar")
		if "_shadow_" in n:
			if mmi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
				bad += 1
			continue
		if is_tree:
			trees += 1
			if mmi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
				bad += 1
		elif mmi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			bushes_shadow += 1
	var shadow_nodes: int = level.find_children("model_P_*_shadow_*", "MultiMeshInstance3D", true, false).size()
	_check("«Проспект»: деревья P_* на месте", trees > 0, str(trees))
	_check("«Проспект»: видимые деревья без тени, тень — отдельными «только тень»", bad == 0 and shadow_nodes > 0,
		"%d плохих, %d теневых" % [bad, shadow_nodes])
	_check("«Проспект»: кусты (сирень, изгородь) отбрасывают тень, как раньше", bushes_shadow > 0, str(bushes_shadow))
	_report("«Проспект»", level, _densest(level))
	level.queue_free()
	await _frames(2)


## Треугольники деревьев в тени вокруг точки (до SHADOW_DISTANCE) — что рисуется в карту тени солнца
## (на каскад), по дальностям видимости узлов. «Было» — видимые узлы деревьев с тенью, как до правки.
func _report(label: String, level: Node, at: Vector3) -> void:
	var before: int = 0
	var after: int = 0
	for raw: Node in level.find_children("*", "MultiMeshInstance3D", true, false):
		var mmi: MultiMeshInstance3D = raw as MultiMeshInstance3D
		if mmi.multimesh == null or mmi.multimesh.mesh == null:
			continue
		if not _is_tree_node(mmi):
			continue
		var d: float = _center(mmi).distance_to(at)
		if d > SHADOW_DISTANCE or d < mmi.visibility_range_begin or (mmi.visibility_range_end > 0.0 and d > mmi.visibility_range_end):
			continue
		var tris: int = _tris(mmi.multimesh.mesh) * mmi.multimesh.instance_count
		var shadow_only: bool = mmi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		if shadow_only:
			after += tris
		else:
			before += tris
	print("%s: треугольники деревьев в тени у точки %s — было %d, стало %d (×%.1f меньше)" % [
		label, str(at.round()), before, after, float(before) / maxf(1.0, float(after))])
	_check("%s: в тень уходит меньше треугольников" % label, after < before, "%d → %d" % [before, after])


func _is_tree_node(mmi: MultiMeshInstance3D) -> bool:
	var n: String = String(mmi.name)
	if mmi.get_parent() is DistrictScatter:
		var s: DistrictScatter = mmi.get_parent() as DistrictScatter
		return s.shadows and s.far_model != "" and (n.begins_with("_Cell_") or n.begins_with("_Mid_") or n.begins_with("_Far_") or n.begins_with("_Shadow"))
	return n.begins_with("model_P_birch") or n.begins_with("model_P_linden") or n.begins_with("model_P_poplar")


## Точка, где больше всего деревьев (центр самой населённой клетки) — там тени дороже всего.
func _densest(level: Node) -> Vector3:
	var best: Vector3 = Vector3.ZERO
	var best_n: int = -1
	for raw: Node in level.find_children("*", "MultiMeshInstance3D", true, false):
		var mmi: MultiMeshInstance3D = raw as MultiMeshInstance3D
		if not _is_tree_node(mmi) or mmi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
			continue
		if mmi.visibility_range_begin > 0.0 or mmi.multimesh == null:
			continue
		if mmi.multimesh.instance_count > best_n:
			best_n = mmi.multimesh.instance_count
			best = _center(mmi)
	print("  самая густая клетка: %d деревьев, центр %s" % [best_n, str(best.round())])
	return best


## Центр пачки (дальность видимости движок меряет от него). Без окна Godot не хранит ни габаритов MultiMesh,
## ни положений экземпляров — у DistrictScatter центр берётся по номеру клетки в имени узла и размеру клетки,
## у пачек MallFiller узел и так стоит в центре.
func _center(mmi: MultiMeshInstance3D) -> Vector3:
	var s: DistrictScatter = mmi.get_parent() as DistrictScatter
	if s == null:
		return mmi.global_position
	var parts: PackedStringArray = String(mmi.name).split("_", false)
	if parts.size() < 3:
		return mmi.global_position
	var size: float = s.far_cell if parts[0] == "Far" and s.far_cell > s.cell else s.cell
	var p := Vector3((float(parts[parts.size() - 2]) + 0.5) * size, 0.0, (float(parts[parts.size() - 1]) + 0.5) * size)
	if s.local_points:
		var frame: Node3D = s.owner as Node3D if s.owner is Node3D else s.get_parent_node_3d()
		return frame.global_transform * p if frame else p
	return p


func _tris(mesh: Mesh) -> int:
	var n: int = 0
	for i: int in mesh.get_surface_count():
		var arr: Array = mesh.surface_get_arrays(i)
		var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX] if arr[Mesh.ARRAY_INDEX] != null else PackedInt32Array()
		n += idx.size() / 3 if idx.size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size() / 3
	return n


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["OK  " if ok else "FAIL", what, ("  (" + detail + ")") if detail != "" else ""])
