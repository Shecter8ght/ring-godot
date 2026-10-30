extends Node
## AR-15 «ГРАНЬ-15» в движке (tools/ar15/game_*.py): узлы игровой модели — подвижные и съёмные детали отдельно, метки,
## карты атласов, треугольники в руках, габарит; ствол из данных (WeaponModels.build): ход рамы, шторка, магазин и приклад
## помечены, сокеты планок Picatinny (models.ar15.sockets) есть у каждого крепления ствола и планки длиннее зажима.
## tools/godot.cmd --headless res://tools/ar15_check.tscn — код выхода 1, если есть ошибки.

const ID := "wpn_ar_09"
const DIR := "res://assets/models/weapons/ar15/"
const NODES := ["Upper_Receiver", "Upper_Handguard", "Upper_Steel", "Lower_Receiver", "Lower_Polymer", "BoltCarrier_Steel",
	"Bolt_Steel", "ChargingHandle_Receiver", "ChLatchL_Receiver", "ChLatchR_Receiver", "DustCover_Receiver",
	"ForwardAssist_Receiver", "Trigger_Receiver", "Selector_Receiver", "MagCatch_Receiver", "MagReleaseL_Receiver",
	"BoltCatch_Receiver", "PivotPin_Receiver", "TakedownPin_Receiver", "Stock_Polymer", "StockLatch_Polymer",
	"RearSightLeaf_Handguard", "RearAperture_Handguard", "FrontSightLeaf_Handguard", "Magazine"]
const MARKERS := ["Muzzle", "SightRear", "SightFront"]
const ATLASES := ["Receiver", "Handguard", "Steel", "Polymer", "Mag"]
const TRIS_MAX := 41000
const SIZE_TOL := 0.003

var _errors: Array[String] = []


func _ready() -> void:
	var rep: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(DIR + "ar15.json"))
	var scene: PackedScene = load(DIR + "ar15.gltf") as PackedScene
	if scene == null:
		_fail("нет ar15.gltf")
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
	print("ar15_check: треугольников в руках ", tris)
	if tris > TRIS_MAX:
		_fail("треугольников %d > %d" % [tris, TRIS_MAX])
	for a: String in ATLASES:
		for kind: String in ["albedo", "normal", "orm"]:
			if not ResourceLoader.exists(DIR + "ar15_%s_100_%s.png" % [a, kind]):
				_fail("нет карты %s %s" % [a, kind])
	if not ResourceLoader.exists(DIR + "ar15_mag30.gltf"):
		_fail("нет магазина-предмета")
	# ствол из данных: ход механики, части, габарит
	var gun: Node3D = WeaponModels.build(ID)
	add_child(gun)
	var carrier: Node3D = gun.find_child("BoltCarrier_Steel", true, false) as Node3D
	if carrier == null or not carrier.has_meta("action"):
		_fail("у рамы нет хода (models.ar15.action)")
	# пылезащитная шторка (action.cover): откинутая на cover_deg вокруг своей оси уходит вправо (−X) и вниз — как в
	# исходнике, где она висит под окном на шарнире
	var cover: Node3D = gun.find_child(String((carrier.get_meta("action", {}) as Dictionary).get("cover", "")), true, false) as Node3D 		if carrier else null
	if cover == null or not cover.has_meta("rest"):
		_fail("нет шторки (models.ar15.action.cover)")
	else:
		var cmi: MeshInstance3D = (cover if cover is MeshInstance3D else cover.find_child("*", true, false)) as MeshInstance3D
		var mid: Vector3 = cmi.get_aabb().get_center() if cmi else Vector3.ZERO
		var turned: Vector3 = Basis(Vector3.BACK, deg_to_rad(float((carrier.get_meta("action") as Dictionary).get("cover_deg", 0.0)))) * mid
		print("ar15_check: шторка откинута — середина сдвинулась на ", (turned - mid).snapped(Vector3.ONE * 0.0001), " м")
		if not (turned.x < mid.x - 0.005 and turned.y < mid.y - 0.005):
			_fail("шторка откидывается не вниз и вправо: %s → %s" % [mid, turned])
	var parts: Dictionary = {}
	for mi: Node in gun.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("part"):
			parts[String(mi.get_meta("part"))] = true
	for p: String in ["mag", "stock"]:
		if not parts.has(p):
			_fail("нет части " + p)
	var box := AABB()
	var first: bool = true
	for mi: Node in raw.find_children("*", "MeshInstance3D", true, false):
		var gi: MeshInstance3D = mi as MeshInstance3D
		var bb: AABB = raw.global_transform.affine_inverse() * gi.global_transform * gi.get_aabb()
		box = bb if first else box.merge(bb)
		first = false
	var want: Array = rep.get("size_game_m", [])
	if want.size() == 3:
		var got: Vector3 = box.size
		print("ar15_check: габарит ", got, " ожидалось ", want)
		for i in range(3):
			if absf(got[i] - float(want[i])) > SIZE_TOL:
				_fail("габарит по оси %d: %.4f против %.4f" % [i, got[i], float(want[i])])
	# сокеты планок Picatinny: у каждого крепления ствола есть сокет, планка длиннее зажима обвеса
	var w: Dictionary = WeaponDb.weapon(ID)
	for point: String in (w.get("mounts", {}) as Dictionary):
		var s: Dictionary = WeaponMods.socket("ar15", point)
		if s.is_empty():
			_fail("нет сокета " + point)
			continue
		if s.has("rail_z"):
			var rz: Array = s.rail_z
			print("ar15_check: планка ", point, " ", rz, " длина ", snappedf(float(rz[1]) - float(rz[0]), 0.001), " м")
			if float(rz[1]) - float(rz[0]) < 0.029:
				_fail("планка %s короче зажима" % point)
	# обвесы на планках: коллиматор на ресивере, фонарь слева, рукоятка снизу — модель собирается
	var mods := {"optic_primary": {"id": "optic_rd_01", "dur": 100.0, "slot": 2},
		"side_left": {"id": "tac_flashlight_01", "dur": 100.0, "slot": 0},
		"underbarrel": {"id": "grip_vertical_01", "dur": 100.0, "slot": 3}}
	var dressed: Node3D = WeaponModels.build(ID, mods)
	add_child(dressed)
	print("ar15_check: с обвесами узлов ", dressed.find_children("*", "Node3D", true, false).size(), " против ",
		gun.find_children("*", "Node3D", true, false).size())
	if dressed.find_children("*", "Node3D", true, false).size() <= gun.find_children("*", "Node3D", true, false).size():
		_fail("обвесы на планках не встали")
	# откидные прицельные (models.ar15.fold_sights): с прицелом на верхней планке целик и мушка лежат (90°), без — стоят
	for leaf: String in ["RearSightLeaf_Handguard", "FrontSightLeaf_Handguard", "RearAperture_Handguard"]:
		var up_node: Node3D = gun.find_child(leaf, true, false) as Node3D
		var down: Node3D = dressed.find_child(leaf, true, false) as Node3D
		if up_node == null or down == null:
			_fail("нет листа " + leaf)
			continue
		var turn: float = rad_to_deg(up_node.basis.get_rotation_quaternion().angle_to(down.basis.get_rotation_quaternion()))
		print("ar15_check: ", leaf, " с прицелом повёрнут на ", snappedf(turn, 0.1), "°")
		if absf(turn - 90.0) > 1.0:
			_fail("%s не сложился (%.1f°)" % [leaf, turn])
	_finish()


func _fail(msg: String) -> void:
	_errors.append(msg)


func _finish() -> void:
	for e: String in _errors:
		print("ar15_check: ОШИБКА ", e)
	print("ar15_check: ", "PASS" if _errors.is_empty() else "FAIL (%d)" % _errors.size())
	get_tree().quit(0 if _errors.is_empty() else 1)
