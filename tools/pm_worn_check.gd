extends Node3D
## ПМ «пошарпанный» v01 в движке (tools/pm_worn): pm.gltf с ригом и ветка LOD1, обойма pm_mag.gltf, глушитель-обвес,
## ЗОРИН К-1 (самостоятельный прицел: на креплении ПМ и на планке автомата) и крепление к затвору ПМ как модели (в руках,
## предмет сам по себе, на полу — LooseLoot.lay_item), шейдер жировых следов на картах с маской _coat, бюджеты треугольников.
## tools/godot.cmd --headless res://tools/pm_worn_check.tscn — только проверка (код выхода 1 — есть ошибки);
## с окном (--windowed --resolution 1600x900) — ещё снимки docs/screens/pm_worn_*.png: предметы на полу, ПМ с К-1 и
## глушителем сбоку и из глаза по линии прицеливания.

const PM := "wpn_hg_01"
const SUPP := "muzzle_supp_pm_01"
const K1 := "optic_zorin_k1"
const MOUNT := "mount_pm_k1"
const MAG := "mag_918_8"
const PRESET := "PM_TAC"
const RIFLE := "wpn_ar_01"
## бюджет в руках (владелец: 20–30 тыс. на пистолет, до 40 тыс. в руках со всем)
const PISTOL_MAX := 31000
const HANDS_MAX := 40000
const LOD1_MAX := 5000

var _errors: Array[String] = []
var _cam: Camera3D


func _ready() -> void:
	var shots: bool = DisplayServer.get_name() != "headless"
	if shots:
		_stage()
	_check_pistol()
	_check_magazine()
	var k1: Node3D = _check_attachment(K1, ["Body", "Lens", "Reticle"])
	var supp: Node3D = _check_attachment(SUPP, ["Body"])
	_check_mount_item()
	var gun: Node3D = _check_kit()
	_check_on_rifle()
	var laid: Array[Node3D] = _check_floor()
	if shots:
		await _shots(gun, laid, k1, supp)
	for e: String in _errors:
		print("pm_worn_check: ОШИБКА ", e)
	print("pm_worn_check: ", "PASS" if _errors.is_empty() else "FAIL (%d)" % _errors.size())
	get_tree().quit(0 if _errors.is_empty() else 1)


func _fail(msg: String) -> void:
	_errors.append(msg)


func _triangles(root: Node3D, visible_only: bool = true) -> int:
	var n: int = 0
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		if mi.mesh == null or (visible_only and not mi.is_visible_in_tree()):
			continue
		for s: int in range(mi.mesh.get_surface_count()):
			var arrays: Array = mi.mesh.surface_get_arrays(s)
			var idx: Variant = arrays[Mesh.ARRAY_INDEX]
			var count: int = (idx as PackedInt32Array).size() if idx is PackedInt32Array else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()
			n += count / 3
	return n


func _coated_surfaces(root: Node3D) -> int:
	var coated: int = 0
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		for s: int in range(mi.mesh.get_surface_count() if mi.mesh else 0):
			var sm: ShaderMaterial = mi.get_active_material(s) as ShaderMaterial
			if sm and sm.shader and sm.shader.resource_path == WeaponCondition.WEAR_SHADER and sm.get_shader_parameter("coat_tex") != null:
				coated += 1
	return coated


func _check_pistol() -> void:
	var model: Node3D = WeaponModels.build(PM)
	add_child(model)
	var rig: WeaponRig = WeaponRig.find_on(model)
	if rig == null:
		_fail("pm.gltf: нет WeaponRig (модель не загрузилась)")
		model.queue_free()
		return
	for part_name: String in ["Frame", "Slide", "Barrel", "Trigger", "Hammer", "SlideStop", "Safety", "MagCatch", "Magazine", "Suppressor"]:
		if rig.part(part_name) == null:
			_fail("pm.gltf: нет детали " + part_name)
	for marker_name: String in ["Muzzle", "MuzzleSuppressed", "SightFront", "SightRear"]:
		if rig.marker(marker_name) == null:
			_fail("pm.gltf: нет метки " + marker_name)
	if not model.get_meta("wear_shader", false):
		_fail("ПМ: шейдер жировых следов не включился (нет карт _coat рядом с картой цвета)")
	var coated: int = _coated_surfaces(model)
	if coated < 5:
		_fail("ПМ: карта следов есть только у %d поверхностей (ждём сталь, щёчку, магазин, патроны, глушитель)" % coated)
	var muzzle_bare: Vector3 = model.get_meta("muzzle", Vector3.ZERO)
	rig.set_suppressed(true)
	rig.set_ammo_state(9)
	var muzzle_sup: Vector3 = model.get_meta("muzzle", Vector3.ZERO)
	if muzzle_sup.z <= muzzle_bare.z + 0.1:
		_fail("ПМ: с глушителем срез не ушёл вперёд (%s → %s)" % [muzzle_bare, muzzle_sup])
	var hands: int = _triangles(model)
	if hands > HANDS_MAX:
		_fail("ПМ в руках с глушителем и патронами: %d треугольников > %d" % [hands, HANDS_MAX])
	rig.set_suppressed(false)
	var pistol: int = _triangles(model)
	if pistol > PISTOL_MAX:
		_fail("ПМ с обоймой: %d треугольников > %d" % [pistol, PISTOL_MAX])
	print("pm_worn_check: ПМ с обоймой %d треугольников, с глушителем %d, поверхностей с плёнкой %d" % [pistol, hands, coated])
	model.queue_free()
	var lod: Node3D = WeaponModels.build(PM, {}, 1)
	add_child(lod)
	var lod_tris: int = _triangles(lod)
	if WeaponRig.find_on(lod) == null or lod_tris > LOD1_MAX:
		_fail("ПМ LOD1: нет рига или %d треугольников > %d" % [lod_tris, LOD1_MAX])
	print("pm_worn_check: ПМ LOD1 %d треугольников" % lod_tris)
	lod.queue_free()


func _check_magazine() -> void:
	var item: Node3D = ItemModels.build(MAG)
	add_child(item)
	var rounds: int = 0
	for i: int in range(1, 9):
		if item.find_child("Round_%02d" % i, true, false) != null:
			rounds += 1
	if item.find_child("Magazine_Mesh", true, false) == null or rounds != 8:
		_fail("обойма (предмет): нет Magazine_Mesh или патронов (%d из 8) — pm_mag.gltf" % rounds)
	item.queue_free()
	var loose: Node3D = ItemModels.weapon_magazine(MAG)
	if loose == null or loose.find_child("Magazine_Mesh", true, false) == null:
		_fail("обойма на полу: не деталь магазина из pm.gltf")
	if loose:
		loose.free()


func _check_attachment(id: String, nodes: Array) -> Node3D:
	var model: Node3D = ItemModels.build(id)
	add_child(model)
	for node_name: String in nodes:
		if model.find_child(node_name, true, false) == null:
			_fail("%s: в модели предмета нет узла %s" % [id, node_name])
	var body: MeshInstance3D = model.find_child("Body", true, false) as MeshInstance3D
	if body and not (body.material_override is ShaderMaterial):
		_fail("%s: у корпуса нет шейдера следов (карты <id>_100_* и _coat)" % id)
	print("pm_worn_check: %s — %d треугольников" % [id, _triangles(model)])
	return model


## Крепление К-1 как предмет: модель переходника на пустом узле (ItemModels через посадку на ПМ).
func _check_mount_item() -> void:
	var item: Node3D = ItemModels.build(MOUNT)
	add_child(item)
	if item.find_child("Adapter", true, false) == null:
		_fail("%s: предмет без модели крепления (узел Adapter)" % MOUNT)
	print("pm_worn_check: %s — %d треугольников" % [MOUNT, _triangles(item)])
	item.queue_free()


## Прицел — самостоятельный ассет: встаёт на верхнюю планку автомата без крепления ПМ.
func _check_on_rifle() -> void:
	var gun: Node3D = WeaponModels.build(RIFLE, {"optic_primary": {"id": K1}})
	add_child(gun)
	var att: Node3D = gun.find_child("Attachment_optic_primary", true, false) as Node3D
	var reticle: MeshInstance3D = gun.find_child("Reticle", true, false) as MeshInstance3D
	if att == null or att.find_child("Body", true, false) == null or reticle == null:
		_fail("К-1 на автомате: нет модели прицела или метки")
	var sight_h: float = float(gun.get_meta("sight_h", 0.0))
	if reticle and absf(reticle.global_position.y - gun.global_position.y - sight_h) > 0.003:
		_fail("К-1 на автомате: метка (%.4f) не на линии прицеливания (%.4f)" % [reticle.global_position.y - gun.global_position.y, sight_h])
	print("pm_worn_check: К-1 на автомате — линия прицеливания %.4f" % sight_h)
	gun.queue_free()


func _check_kit() -> Node3D:
	var pr: Dictionary = WeaponDb.preset(PRESET)
	var gun: Node3D = WeaponModels.build(PM, pr.get("mods", {}))
	add_child(gun)
	var mount: Node3D = gun.find_child("Attachment_optic_primary", true, false) as Node3D
	if mount == null or mount.find_child("Adapter", true, false) == null:
		_fail("ПМ + крепление: на затворе нет модели крепления")
	var att: Node3D = gun.find_child("Attachment_" + WeaponBuild.node_name("optic_primary/rail"), true, false) as Node3D
	if att == null or att.find_child("Body", true, false) == null:
		_fail("ПМ + К-1: на креплении нет модели прицела")
	var reticle: MeshInstance3D = gun.find_child("Reticle", true, false) as MeshInstance3D
	if reticle == null or not reticle.get_meta("reticle_dot", false):
		_fail("ПМ + К-1: метка прицела не помечена reticle_dot (свечение в модели)")
	var sight_h: float = float(gun.get_meta("sight_h", 0.0))
	var rig: WeaponRig = WeaponRig.find_on(gun)
	# высота штатной прицельной линии — по метке мушки (meta sight_h у корня уже заменена прицелом)
	var iron: float = (rig.get_meta("sight_front", Vector3.ZERO) as Vector3).y if rig else 0.0
	if sight_h < iron + 0.02 or sight_h > iron + 0.06:
		_fail("ПМ + К-1: линия прицеливания %.4f не над целиком %.4f" % [sight_h, iron])
	if reticle and absf(reticle.global_position.y - gun.global_position.y - sight_h) > 0.003:
		_fail("ПМ + К-1: метка (%.4f) не на линии прицеливания (%.4f)" % [reticle.global_position.y - gun.global_position.y, sight_h])
	if rig and not rig.part("Suppressor").visible:
		_fail("ПМ + глушитель: деталь глушителя рига не показана")
	if rig:
		rig.set_ammo_state(9)
	var hands: int = _triangles(gun)
	if hands > HANDS_MAX:
		_fail("ПМ + К-1 + глушитель в руках: %d треугольников > %d" % [hands, HANDS_MAX])
	print("pm_worn_check: ПМ с К-1 и глушителем — %d треугольников, линия прицеливания %.4f (целик %.4f)" % [hands, sight_h, iron])
	return gun


func _check_floor() -> Array[Node3D]:
	var out: Array[Node3D] = []
	var x: float = 0.0
	for id: String in [PM, MAG, SUPP, K1, MOUNT]:
		var holder: Node3D = Node3D.new()
		holder.position = Vector3(x, 0.0, 0.0)
		add_child(holder)
		LooseLoot.lay_item(holder, id, 0.4 * x)
		var laid: Node3D = holder.find_child("Laid", false, false) as Node3D
		var box: AABB = ItemModels.bounds(laid) if laid else AABB()
		if laid == null or box.size.length() < 0.03 or box.position.y < -0.001:
			_fail("%s на полу: модели нет или она под полом (%s)" % [id, box])
		out.append(holder)
		x += 0.25
	return out


func _stage() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.25, 0.27, 0.3)
	sky_mat.sky_horizon_color = Color(0.4, 0.4, 0.42)
	sky_mat.ground_bottom_color = Color(0.05, 0.05, 0.05)
	sky_mat.ground_horizon_color = Color(0.3, 0.3, 0.3)
	sky.sky_material = sky_mat
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.03, 0.03, 0.03)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.sky = sky
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-40.0, 35.0, 0.0)
	key.light_energy = 2.2
	key.shadow_enabled = true
	add_child(key)
	var fill := OmniLight3D.new()
	fill.position = Vector3(-0.6, 0.4, 0.8)
	fill.omni_range = 4.0
	fill.light_energy = 0.8
	add_child(fill)
	# бетонный пол под предметами
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(3.0, 3.0)
	floor_mesh.mesh = plane
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.38, 0.37, 0.35)
	fm.roughness = 0.9
	floor_mesh.material_override = fm
	floor_mesh.position = Vector3(0.4, -0.0005, 0.0)
	add_child(floor_mesh)
	_cam = Camera3D.new()
	_cam.fov = 40.0
	_cam.near = 0.01
	add_child(_cam)
	_cam.make_current()


func _save(name: String) -> void:
	for _i: int in range(20):
		await get_tree().process_frame
	var path: String = "res://docs/screens/pm_worn_%s.png" % name
	get_viewport().get_texture().get_image().save_png(path)
	print("pm_worn_check: ", path)


func _shots(gun: Node3D, laid: Array[Node3D], k1: Node3D, supp: Node3D) -> void:
	gun.position = Vector3(0.0, 1.0, 0.0)
	k1.position = Vector3(2.0, 1.0, 0.0)
	supp.position = Vector3(3.0, 1.0, 0.0)
	# предметы на полу: все вместе и каждый крупно
	_cam.position = Vector3(0.38, 0.55, 0.75)
	_cam.look_at(Vector3(0.38, 0.0, 0.0))
	await _save("floor_all")
	var names: Array = ["pistol", "mag", "supp", "k1", "mount"]
	for i: int in range(laid.size()):
		var c: Vector3 = laid[i].global_position + Vector3(0.0, 0.02, 0.0)
		_cam.position = c + Vector3(0.12, 0.2, 0.22)
		_cam.look_at(c)
		await _save("floor_" + String(names[i]))
	# ПМ с К-1 и глушителем: сбоку, три четверти, из глаза по линии прицеливания
	var g: Vector3 = gun.global_position + Vector3(0.0, 0.06, 0.08)
	_cam.position = g + Vector3(-0.55, 0.05, 0.0)
	_cam.look_at(g)
	await _save("kit_side")
	_cam.position = g + Vector3(0.32, 0.22, -0.3)
	_cam.look_at(g)
	await _save("kit_34")
	var sh: float = float(gun.get_meta("sight_h", 0.08))
	_cam.fov = 40.0
	_cam.position = gun.global_position + Vector3(0.0, sh, -0.3)
	_cam.look_at(gun.global_position + Vector3(0.0, sh, 1.0))
	await _save("kit_eye")
	# прицел и глушитель как предметы, крупно
	for pair: Array in [["k1_item", k1], ["supp_item", supp]]:
		var c: Vector3 = (pair[1] as Node3D).global_position
		_cam.position = c + Vector3(0.1, 0.07, 0.14)
		_cam.look_at(c)
		await _save(String(pair[0]))
