class_name SlungWeapons
extends Node
## Убранное оружие на теле (владелец 2026-10-29: «надетая разгрузка и убранное оружие — надо, чтобы было видно»).
## Длинные стволы — за спиной наискосок (второй — накрест), пистолет — стволом вниз в кобуре на правом бедре,
## ракетница — на левом. Крепится к костям скелета модели тела (Spine2, бёдра) — идёт за телом в любой позе;
## отступ от спины — по тому, что надето (тело, броня, рюкзак), в rest-позе. Только вид: у каждого peer свой
## из синхронизированного (игрок — снаряжение и ствол в руках, бот — какой ствол в руках). Числа — Balance.SLUNG.

## Что сейчас висит: ключ набора (id, обвес, магазин, слот) — пересобирается только при смене.
var _key: String = ""
var _anchors: Array[Node] = []


## Повесить на тело: список записей entry() — то, что не в руках. true — набор сменился (пересобран).
func show_list(list: Array) -> bool:
	var key := JSON.stringify(list)
	if key == _key:
		return false
	_key = key
	_clear()
	var sk := _skeleton()
	if sk == null:
		return true
	var longs: int = 0
	for raw: Variant in list:
		var e := raw as Dictionary
		var id := String(e.get("id", ""))
		if id == "":
			continue
		var model := WeaponModels.build(id, e.get("mods", {}), 1, 100.0, String(e.get("mag", "*")), e.get("marks", {}))
		_strip(model)
		match kind_of(String(e.get("slot", "")), id):
			"thigh_r":
				_hang_thigh(sk, model, true)
			"thigh_l":
				_hang_thigh(sk, model, false)
			_:
				_hang_back(sk, model, longs)
				longs += 1
	_fade_far()
	return true


## Запись для show_list из экземпляра оружия в слоте: вид модели (обвес, магазин, гравировка); прочность
## на вид не влияет (вид оружия один, владелец 2026-10-19).
static func entry(slot: String, e: Dictionary) -> Dictionary:
	return {"slot": slot, "id": String(e.get("id", "")), "mods": e.get("mods", {}), "mag": WeaponMods.mag_state(e), "marks": WeaponMark.marks(e)}


## Снять всё (смерть, ушёл из рейда).
func clear() -> void:
	_key = ""
	_clear()


## Где носят: пистолет — правое бедро, ракетница (слот launcher) — левое, остальное — за спиной.
static func kind_of(slot: String, id: String) -> String:
	if slot == "launcher":
		return "thigh_l"
	if String(WeaponDb.weapon(id).get("class", "")) == "PISTOL":
		return "thigh_r"
	return "back"


## Узлы, которые сейчас висят (для проверок): имена мест.
func anchors() -> Array[Node]:
	var out: Array[Node] = []
	for a: Node in _anchors:
		if is_instance_valid(a):
			out.append(a)
	return out


## За спиной: ствол в плоскости спины, приклад вверх-вправо, дуло вниз-влево (второй — зеркально накрест),
## боком к спине. Центр модели — у позвонка Spine2, сразу за самым дальним назад, что надето.
func _hang_back(sk: Skeleton3D, model: Node3D, n: int) -> void:
	var cfg: Dictionary = Balance.SLUNG
	var bone := sk.find_bone("mixamorig_Spine2")
	if bone < 0:
		model.free()
		return
	var rest := sk.get_bone_global_rest(bone)
	var box := ItemModels.bounds(model)
	var tilt := deg_to_rad(float(cfg.back_tilt_deg)) * (1.0 if n % 2 == 0 else -1.0)
	# оси модели: +Z — дуло, +Y — верх, X — бок; у тела +Z — вперёд, +X — его левая сторона
	var z := Vector3(sin(tilt), -cos(tilt), 0.0)
	var x := Vector3(0.0, 0.0, -1.0)
	var y := z.cross(x).normalized()
	var basis := Basis(x, y, z)
	var half := box.size.x * 0.5
	var back := _back_z(sk, rest.origin.y) - float(cfg.back_gap_m) - half - float(cfg.second_gap_m) * float(n)
	var centre := Vector3(rest.origin.x, rest.origin.y + float(cfg.back_y), back)
	_attach(sk, bone, "Slung_back_%d" % n, Transform3D(basis, centre - basis * box.get_center()), model)


## В кобуре на бедре: дуло вниз, верх затвора — вперёд, рукоять — назад, боком к ноге; кобура — коробка
## по модели: от дула на holster_k длины и от верха затвора на holster_h высоты — рукоять снаружи.
func _hang_thigh(sk: Skeleton3D, model: Node3D, right: bool) -> void:
	var cfg: Dictionary = Balance.SLUNG
	var bone := sk.find_bone("mixamorig_RightUpLeg" if right else "mixamorig_LeftUpLeg")
	if bone < 0:
		model.free()
		return
	var rest := sk.get_bone_global_rest(bone)
	var box := ItemModels.bounds(model)
	var side := -1.0 if right else 1.0
	var basis := Basis(Vector3(1.0, 0.0, 0.0), Vector3(0.0, 0.0, 1.0), Vector3(0.0, -1.0, 0.0))
	var out := float(cfg.thigh_out_m) + box.size.x * 0.5
	var centre := rest.origin + Vector3(side * out, -float(cfg.thigh_down_m), float(cfg.thigh_fwd_m))
	_attach(sk, bone, "Slung_thigh_%s" % ("r" if right else "l"), Transform3D(basis, centre - basis * box.get_center()), model)
	# кобура: затвор и ствол от дула на holster_k длины, сверху на holster_h высоты; рукоять торчит
	var pad := float(cfg.holster_pad_m)
	var size := Vector3(box.size.x + pad * 2.0, box.size.y * float(cfg.holster_h) + pad, box.size.z * float(cfg.holster_k) + pad)
	var mi := MeshInstance3D.new()
	mi.name = "Holster"
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = cfg.holster_color
	mat.roughness = 0.85
	mi.material_override = mat
	mi.position = Vector3(box.get_center().x, box.end.y + pad - size.y * 0.5, box.end.z + pad - size.z * 0.5)
	model.add_child(mi)


## Место на кости: держатель в rest-позе стоит в xf (оси скелета), модель — в нём.
func _attach(sk: Skeleton3D, bone: int, name_: String, xf: Transform3D, model: Node3D) -> Node3D:
	var att := BoneAttachment3D.new()
	att.name = name_
	att.bone_name = sk.get_bone_name(bone)
	sk.add_child(att)
	var holder := Node3D.new()
	holder.name = "Holder"
	att.add_child(holder)
	holder.transform = sk.get_bone_global_rest(bone).affine_inverse() * xf
	holder.add_child(model)
	_anchors.append(att)
	return holder


## Самое дальнее назад (−Z, rest), что надето на уровне груди: тело, броня, рюкзак (сетки на скелете, без LOD).
func _back_z(sk: Skeleton3D, chest_y: float) -> float:
	var back := 0.0
	var to_sk := sk.global_transform.affine_inverse()
	for c: Node in sk.get_children():
		var mi := c as MeshInstance3D
		if mi == null or mi.mesh == null or not mi.visible or "_LOD" in String(mi.name):
			continue
		var box: AABB = to_sk * mi.global_transform * mi.get_aabb()
		if box.position.y > chest_y + 0.15 or box.end.y < chest_y - 0.15:
			continue
		back = minf(back, box.position.z)
	return back


## Оружие на теле — без света: фонари (со свечением) и лазеры не нужны. Модель ещё не в дереве — удаляем сразу,
## иначе свечение фонаря попадёт в габарит и кобура вырастет в коробку.
static func _strip(model: Node3D) -> void:
	for n: Node in model.find_children("*", "Light3D", true, false):
		n.get_parent().remove_child(n)
		n.free()
	for n: Node in model.find_children("LaserBeam*", "Node3D", true, false):
		n.get_parent().remove_child(n)
		n.free()
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		if n.has_meta("weapon_clearance_ignore"):
			n.get_parent().remove_child(n)
			n.free()
	model.process_mode = Node.PROCESS_MODE_DISABLED


func _fade_far() -> void:
	var far := float(Balance.SLUNG.draw_m)
	for a: Node in _anchors:
		for mi: Node in a.find_children("*", "GeometryInstance3D", true, false):
			(mi as GeometryInstance3D).visibility_range_end = far


func _clear() -> void:
	for a: Node in _anchors:
		if is_instance_valid(a):
			a.get_parent().remove_child(a)
			a.queue_free()
	_anchors.clear()


func _skeleton() -> Skeleton3D:
	var model: Node = get_parent().get_node_or_null("Body/Persona")
	if model == null:
		return null
	var found: Array[Node] = model.find_children("*", "Skeleton3D", true, false)
	return found[0] as Skeleton3D if not found.is_empty() else null
