extends Node
## ИЗЛОМ-45 в движке (tools/smg03/game_*.py): узлы игровой модели — подвижные и съёмные детали отдельно, метки, карты
## атласов, треугольники в руках; ствол из данных (WeaponModels.build): затвор с ходом и задержкой, флажки переводчика и
## спуск с покоем, магазин, приклад и заглушка резьбы помечены; обвесы на планках встают, с прицелом сверху откидные
## прицельные лежат; глушитель .45 прячет заглушку; магазин на 30 — свой корпус из файла; режимы огня и темп из данных.
## tools/godot.cmd --headless res://tools/smg03_check.tscn — код выхода 1, если есть ошибки.

const ID := "wpn_smg_03"
const DIR := "res://assets/models/weapons/smg03/"
const NODES := ["Receiver_Upper", "Receiver_Lower", "Receiver_Steel", "Receiver_Stock", "Bolt_Steel",
	"ChargingHandle_Steel", "ChargingSlider_Steel", "Trigger_Steel", "SafetyL_Steel", "SafetyR_Steel", "SelectorL_Steel",
	"SelectorR_Steel", "MagReleaseL_Steel", "MagReleaseR_Steel", "BoltCatch_Steel", "RearSightLeaf_Steel",
	"FrontSightLeaf_Steel", "Stock_Stock", "StockLatch_Stock", "Magazine", "MuzzleDevice"]
const MARKERS := ["Muzzle", "SightRear", "SightFront"]
const ATLASES := ["Upper", "Lower", "Steel", "Stock", "Mag13", "Mag30"]
const TRIS_MAX := 60000

var _errors: Array[String] = []


func _ready() -> void:
	var scene: PackedScene = load(DIR + "smg03.gltf") as PackedScene
	if scene == null:
		_fail("нет smg03.gltf")
		return _finish()
	var raw: Node3D = scene.instantiate() as Node3D
	add_child(raw)
	for n: String in NODES + MARKERS:
		if raw.find_child(n, true, false) == null:
			_fail("нет узла " + n)
	var tris: int = 0
	for mi: Node in raw.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (mi as MeshInstance3D).mesh
		for s in range(mesh.get_surface_count()):
			tris += (mesh.surface_get_arrays(s)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
	print("smg03_check: треугольников в руках ", tris)
	if tris > TRIS_MAX:
		_fail("треугольников %d > %d" % [tris, TRIS_MAX])
	for a: String in ATLASES:
		for kind: String in ["albedo", "normal", "orm"]:
			if not ResourceLoader.exists(DIR + "smg03_%s_100_%s.png" % [a, kind]):
				_fail("нет карты %s %s" % [a, kind])
	for item: String in ["smg03_mag13.gltf", "smg03_mag30.gltf"]:
		if not ResourceLoader.exists(DIR + item):
			_fail("нет магазина-предмета " + item)
	# ствол из данных
	var w: Dictionary = WeaponDb.weapon(ID)
	print("smg03_check: ", ID, ", темп ", (w.get("stats", {}) as Dictionary).get("rpm"), ", режимы ",
		WeaponDb.fire_modes(ID))
	if int((w.get("stats", {}) as Dictionary).get("rpm", 0)) != 1200:
		_fail("темп не 1200")
	if WeaponDb.fire_modes(ID) != ["auto", "burst", "semi"]:
		_fail("режимы огня не АВ — 2 — ОД")
	var gun: Node3D = WeaponModels.build(ID)
	add_child(gun)
	if not bool(gun.get_meta("asset_loaded", false)):
		_fail("модель не из файла (процедурная заглушка)")
	var bolt: Node3D = gun.find_child("Bolt_Steel", true, false) as Node3D
	if bolt == null or not bolt.has_meta("action"):
		_fail("у затвора нет хода (models.smg03.action)")
	else:
		var act: Dictionary = bolt.get_meta("action")
		print("smg03_check: ход затвора ", act.get("travel"), " м, задержка ", act.get("hold_open"))
		if not bool(act.get("hold_open", false)):
			_fail("нет затворной задержки")
	for lever: String in ["SelectorL_Steel", "SelectorR_Steel", "Trigger_Steel"]:
		var node: Node3D = gun.find_child(lever, true, false) as Node3D
		if node == null or not node.has_meta("rest"):
			_fail("у %s нет покоя (флажки и спуск не будут ходить)" % lever)
	var parts: Dictionary = {}
	for mi: Node in gun.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("part"):
			parts[String(mi.get_meta("part"))] = true
	for p: String in ["mag", "stock", "muzzle_device"]:
		if not parts.has(p):
			_fail("нет части " + p)
	if not gun.has_meta("muzzle") or not gun.has_meta("sight_h"):
		_fail("нет меток дула и линии прицеливания")
	else:
		print("smg03_check: дуло ", gun.get_meta("muzzle"), ", линия прицеливания ", gun.get_meta("sight_h"))
	for mount: String in ["optic_primary", "top_front", "side_left", "side_right", "underbarrel", "muzzle", "stock", "mag"]:
		if WeaponMods.socket("smg03", mount).is_empty():
			_fail("нет сокета " + mount)
	# обвесы на планках: коллиматор сверху, фонарь слева, рукоятка снизу
	var mods := {"optic_primary": {"id": "optic_holo_01", "dur": 100.0, "slot": 2},
		"side_left": {"id": "tac_laser_01", "dur": 100.0, "slot": 0},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 0}}
	var dressed: Node3D = WeaponModels.build(ID, mods)
	add_child(dressed)
	print("smg03_check: с обвесами узлов ", dressed.find_children("*", "Node3D", true, false).size(), " против ",
		gun.find_children("*", "Node3D", true, false).size())
	if dressed.find_children("*", "Node3D", true, false).size() <= gun.find_children("*", "Node3D", true, false).size():
		_fail("обвесы на планках не встали")
	for leaf: String in ["RearSightLeaf_Steel", "FrontSightLeaf_Steel"]:
		var up_node: Node3D = gun.find_child(leaf, true, false) as Node3D
		var down: Node3D = dressed.find_child(leaf, true, false) as Node3D
		if up_node == null or down == null:
			_fail("нет листа " + leaf)
			continue
		var turn: float = rad_to_deg(up_node.basis.get_rotation_quaternion().angle_to(down.basis.get_rotation_quaternion()))
		print("smg03_check: ", leaf, " с прицелом повёрнут на ", snappedf(turn, 0.1), "°")
		if absf(turn - 89.0) > 1.0:
			_fail("%s не сложился (%.1f°)" % [leaf, turn])
	# глушитель .45 на резьбу: заглушка прячется
	var supp: Node3D = WeaponModels.build(ID, {"muzzle": {"id": "muzzle_supp_45_01", "dur": 100.0}})
	add_child(supp)
	var cap: Node3D = supp.find_child("MuzzleDevice", true, false) as Node3D
	print("smg03_check: с глушителем заглушка видна — ", cap.visible if cap else "нет узла")
	if cap and cap.is_visible_in_tree():
		_fail("с глушителем заглушка резьбы видна")
	if not bool(supp.get_meta("suppressed", false)):
		_fail("ствол с глушителем не помечен suppressed")
	# магазин на 30 — свой корпус из файла на сокете mag, штатный на 13 спрятан
	var m30: Node3D = WeaponModels.build(ID, {}, 0, 100.0, "mag_45_vector30")
	add_child(m30)
	var look: Node3D = m30.find_child("MagAsset", true, false) as Node3D
	var own: Node3D = m30.find_child("Magazine", true, false) as Node3D
	print("smg03_check: магазин на 30 — ", "из файла" if look else "НЕТ", ", штатный виден — ", own.visible if own else "нет")
	if look == null:
		_fail("магазин на 30 не встал моделью из файла")
	if own and own.visible:
		_fail("со своим магазином на 30 штатный на 13 виден")
	_finish()


func _fail(msg: String) -> void:
	_errors.append(msg)


func _finish() -> void:
	for e: String in _errors:
		print("smg03_check: ОШИБКА ", e)
	print("smg03_check: ", "PASS" if _errors.is_empty() else "FAIL (%d)" % _errors.size())
	get_tree().quit(0 if _errors.is_empty() else 1)
