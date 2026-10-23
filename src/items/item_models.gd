class_name ItemModels
extends RefCounted
## Модели предметов для иконок (tools/icon_bake → assets/icons/<id>.png) и, при желании, для
## предметов на полу. Оружие — WeaponModels (со штатным обвесом нет — голый ствол), обвесы —
## WeaponMods (на пустом узле по точке крепления первого ствола с подходящим интерфейсом),
## граната — WeaponModels, арсенал (магазины, плиты, жилеты и плитоносцы, шлемы, гарнитуры) — по
## данным: размер от ёмкости / класса, цвет от материала и тира; остальное — простые формы из
## примитивов с фасками в реальных размерах: бинт — рулон, аптечка — кейс с крестом, патроны —
## пачка цвета калибра, деньги — пачка с бандеролью.

static var _mats: Dictionary = {}


static func build(id: String) -> Node3D:
	var it := ItemDb.item(id)
	if id == Metka4Model.ID:
		return Metka4Model.standalone()
	if WeaponDb.is_weapon(id):
		return WeaponModels.build(id)
	if id == "grenade":
		return WeaponModels.build("grenade")
	var att := WeaponDb.attachment(id)
	if not att.is_empty():
		# обвес со своей моделью (глушитель ПМ, ЗОРИН К-1) — сама модель
		var own: Node3D = WeaponMods.standalone(id)
		if own:
			return own
		# на пустом узле — в точке крепления первого ствола, куда он встаёт по интерфейсу
		var r := Node3D.new()
		r.name = "Item_" + id
		for wid in WeaponDb.ids("weapons"):
			var mounts := WeaponDb.mounts_of(String(wid))
			for mount in mounts:
				if String(mounts[mount]) in att.get("fits", []):
					WeaponMods.fit(r, String(WeaponDb.weapon(String(wid)).model), {String(mount): {"id": id}})
					return r
		return r
	var root := Node3D.new()
	root.name = "Item_" + id
	if String(it.get("model", "")) != "" and _scan_path(root, String(it.model)):
		return root
	if id in ["laser_head", "engraver_frame", "engraver_controller"] and _scan_path(root, "res://assets/items/models/%s.glb" % id):
		return root
	# рюкзаки — модели проекта (tools/build_backpacks.py)
	if String(it.get("cat", "")) == "backpack" and _scan_path(root, "res://assets/items/models/%s.glb" % id):
		return root
	# разгрузки — модели проекта (tools/build_rigs.py)
	if it.has("rig") and _scan_path(root, "res://assets/items/models/%s.glb" % id):
		return root
	if _arsenal(root, id):
		return root
	match id:
		"nvg":
			# корпус с креплением и два окуляра
			_cbox(root, Vector3(0, 0, 0), Vector3(0.12, 0.06, 0.07), _m(Color(0.16, 0.17, 0.15), 0.7), 0.01)
			for sx in [-0.032, 0.032]:
				_cyl(root, Vector3(sx, 0.0, 0.055), 0.022, 0.05, _m(Color(0.12, 0.12, 0.11), 0.6)).rotation.x = PI * 0.5
				_cyl(root, Vector3(sx, 0.0, 0.082), 0.018, 0.003, _m(Color(0.2, 0.45, 0.3, 0.9), 0.1, 0.3, true)).rotation.x = PI * 0.5
			_box(root, Vector3(0, 0.045, -0.02), Vector3(0.05, 0.03, 0.03), _m(Color(0.1, 0.1, 0.1), 0.8))
		"sunglasses":
			for sx in [-0.034, 0.034]:
				_cbox(root, Vector3(sx, 0, 0), Vector3(0.056, 0.036, 0.006), _m(Color(0.08, 0.07, 0.05, 0.85), 0.05, 0.4, true), 0.012)
			_box(root, Vector3(0, 0.012, 0), Vector3(0.016, 0.005, 0.006), _m(Color(0.7, 0.62, 0.35), 0.3, 0.9))
			for sx in [-0.064, 0.064]:
				_box(root, Vector3(sx, 0.01, -0.05), Vector3(0.004, 0.005, 0.1), _m(Color(0.7, 0.62, 0.35), 0.3, 0.9))
		"flare":
			_cyl(root, Vector3.ZERO, 0.018, 0.16, _m(Color(0.75, 0.12, 0.08), 0.7)).rotation.z = PI * 0.5
			_cyl(root, Vector3(0.085, 0, 0), 0.019, 0.02, _m(Color(0.15, 0.15, 0.15), 0.6)).rotation.z = PI * 0.5
		"chemlight":
			_cyl(root, Vector3.ZERO, 0.008, 0.15, _m(Color(0.4, 1.0, 0.5, 0.8), 0.2, 0.0, true)).rotation.z = PI * 0.5
			_cyl(root, Vector3(0.08, 0, 0), 0.009, 0.015, _m(Color(0.2, 0.2, 0.2), 0.6)).rotation.z = PI * 0.5
		"bandage":
			_cyl(root, Vector3.ZERO, 0.035, 0.07, _m(Color(0.93, 0.92, 0.88), 0.9)).rotation.z = PI * 0.5
			_box(root, Vector3(0, -0.034, 0.05), Vector3(0.068, 0.002, 0.1), _m(Color(0.9, 0.89, 0.85), 0.9))
		"painkillers":
			_box(root, Vector3.ZERO, Vector3(0.1, 0.004, 0.06), _m(Color(0.75, 0.77, 0.8), 0.35, 0.7))
			for i in range(5):
				for j in range(2):
					_sphere(root, Vector3(-0.04 + i * 0.02, 0.004, -0.013 + j * 0.026), 0.007, _m(Color(0.95, 0.95, 0.95), 0.5))
		"medkit":
			_cbox(root, Vector3.ZERO, Vector3(0.2, 0.08, 0.13), _m(Color(0.7, 0.08, 0.07), 0.6), 0.01)
			_box(root, Vector3(0, 0.041, 0), Vector3(0.07, 0.003, 0.02), _m(Color(0.95, 0.95, 0.95), 0.6))
			_box(root, Vector3(0, 0.041, 0), Vector3(0.02, 0.003, 0.07), _m(Color(0.95, 0.95, 0.95), 0.6))
			_cbox(root, Vector3(0, 0.05, -0.068), Vector3(0.08, 0.012, 0.012), _m(Color(0.1, 0.1, 0.1), 0.7), 0.004)
		"water":
			_cyl(root, Vector3.ZERO, 0.034, 0.19, _m(Color(0.55, 0.75, 0.9, 0.55), 0.1, 0.0, true))
			_cyl(root, Vector3(0, 0.105, 0), 0.014, 0.02, _m(Color(0.1, 0.35, 0.8), 0.5))
			_cyl(root, Vector3(0, 0.0, 0), 0.0345, 0.06, _m(Color(0.15, 0.45, 0.85), 0.6))
		"canned":
			_cyl(root, Vector3.ZERO, 0.042, 0.1, _m(Color(0.7, 0.7, 0.72), 0.35, 0.8))
			_cyl(root, Vector3.ZERO, 0.0425, 0.07, _m(Color(0.65, 0.2, 0.12), 0.7))
		"energy_bar":
			_cbox(root, Vector3.ZERO, Vector3(0.12, 0.02, 0.04), _m(Color(0.9, 0.5, 0.1), 0.5), 0.004)
			_box(root, Vector3(0, 0.0105, 0), Vector3(0.05, 0.001, 0.03), _m(Color(0.25, 0.1, 0.05), 0.6))
		"phone":
			_cbox(root, Vector3.ZERO, Vector3(0.075, 0.008, 0.155), _m(Color(0.05, 0.05, 0.06), 0.3, 0.3), 0.004)
			_box(root, Vector3(0, 0.0042, 0), Vector3(0.068, 0.001, 0.145), _m(Color(0.1, 0.18, 0.3), 0.1))
		"headphones":
			var band := _torus(root, Vector3(0, 0.02, 0), 0.075, 0.085, _m(Color(0.08, 0.08, 0.09), 0.6))
			band.rotation.x = PI * 0.5
			for sx in [-1.0, 1.0]:
				_cyl(root, Vector3(sx * 0.08, -0.03, 0), 0.035, 0.03, _m(Color(0.12, 0.12, 0.13), 0.7)).rotation.z = PI * 0.5
		"powerbank":
			_cbox(root, Vector3.ZERO, Vector3(0.07, 0.022, 0.13), _m(Color(0.25, 0.26, 0.28), 0.4, 0.4), 0.005)
			_box(root, Vector3(0, 0.012, 0.05), Vector3(0.012, 0.001, 0.004), _m(Color(0.2, 0.9, 0.4), 0.3, 0.0, false, 2.0))
		"laptop":
			_cbox(root, Vector3.ZERO, Vector3(0.32, 0.018, 0.22), _m(Color(0.6, 0.62, 0.64), 0.35, 0.8), 0.004)
			var lid := _cbox(root, Vector3(0, 0.1, -0.12), Vector3(0.32, 0.21, 0.01), _m(Color(0.6, 0.62, 0.64), 0.35, 0.8), 0.004)
			lid.rotation.x = deg_to_rad(-15.0)
			_box(root, Vector3(0, 0.1, -0.113), Vector3(0.29, 0.18, 0.001), _m(Color(0.08, 0.14, 0.22), 0.1)).rotation.x = deg_to_rad(-15.0)
			_box(root, Vector3(0, 0.0095, 0.02), Vector3(0.27, 0.001, 0.1), _m(Color(0.15, 0.15, 0.16), 0.7))
		"gpu":
			_cbox(root, Vector3.ZERO, Vector3(0.27, 0.04, 0.11), _m(Color(0.12, 0.12, 0.13), 0.5, 0.4), 0.004)
			for i in range(2):
				_cyl(root, Vector3(-0.06 + i * 0.12, 0.021, 0), 0.042, 0.004, _m(Color(0.05, 0.05, 0.05), 0.8))
			_box(root, Vector3(0, -0.02, 0.058), Vector3(0.2, 0.004, 0.012), _m(Color(0.75, 0.6, 0.2), 0.3, 0.9))
		"camera":
			_cbox(root, Vector3.ZERO, Vector3(0.13, 0.085, 0.06), _m(Color(0.06, 0.06, 0.07), 0.5), 0.008)
			var lens := _cyl(root, Vector3(0.0, -0.005, 0.06), 0.03, 0.06, _m(Color(0.08, 0.08, 0.08), 0.4, 0.4))
			lens.rotation.x = PI * 0.5
			_cyl(root, Vector3(0.0, -0.005, 0.091), 0.024, 0.002, _m(Color(0.2, 0.3, 0.45), 0.05, 0.3)).rotation.x = PI * 0.5
		"server_drive":
			_cbox(root, Vector3.ZERO, Vector3(0.1, 0.026, 0.147), _m(Color(0.55, 0.56, 0.58), 0.35, 0.85), 0.003)
			_box(root, Vector3(0, 0.0135, 0.02), Vector3(0.07, 0.001, 0.05), _m(Color(0.9, 0.9, 0.88), 0.6))
		"watch":
			_cyl(root, Vector3.ZERO, 0.02, 0.01, _m(Color(0.75, 0.62, 0.3), 0.25, 0.9))
			_cyl(root, Vector3(0, 0.0055, 0), 0.017, 0.001, _m(Color(0.95, 0.94, 0.9), 0.3))
			for sz in [-1.0, 1.0]:
				_box(root, Vector3(0, -0.002, sz * 0.04), Vector3(0.018, 0.004, 0.04), _m(Color(0.25, 0.14, 0.08), 0.7))
		"gold_chain":
			var gold := _m(Color(0.85, 0.65, 0.2), 0.25, 1.0)
			# звенья вплотную по овалу, через одно — ребром (как у настоящей цепи)
			for i in range(30):
				var a := TAU * float(i) / 30.0
				var link := _torus(root, Vector3(cos(a) * 0.05, 0, sin(a) * 0.038), 0.0035, 0.0065, gold)
				link.scale = Vector3(1.0, 1.0, 1.6)
				link.rotation = Vector3(0.0, -a, PI * 0.5 * float(i % 2))
		"diamond_ring":
			var ring := _torus(root, Vector3.ZERO, 0.009, 0.011, _m(Color(0.85, 0.65, 0.2), 0.2, 1.0))
			ring.rotation.x = PI * 0.5
			_sphere(root, Vector3(0, 0.012, 0), 0.005, _m(Color(0.8, 0.9, 1.0, 0.7), 0.02, 0.0, true))
		"cash":
			_cbox(root, Vector3.ZERO, Vector3(0.155, 0.02, 0.07), _m(Color(0.35, 0.5, 0.35), 0.8), 0.002)
			_box(root, Vector3(0, 0, 0), Vector3(0.03, 0.021, 0.071), _m(Color(0.9, 0.85, 0.7), 0.8))
		"cigarettes":
			_cbox(root, Vector3.ZERO, Vector3(0.055, 0.085, 0.022), _m(Color(0.92, 0.92, 0.9), 0.6), 0.002)
			_box(root, Vector3(0, 0.03, 0), Vector3(0.056, 0.025, 0.023), _m(Color(0.75, 0.1, 0.1), 0.6))
		"lighter":
			_cbox(root, Vector3.ZERO, Vector3(0.025, 0.06, 0.012), _m(Color(0.1, 0.35, 0.8, 0.8), 0.2, 0.0, true), 0.003)
			_box(root, Vector3(0, 0.036, 0), Vector3(0.024, 0.014, 0.011), _m(Color(0.7, 0.7, 0.72), 0.3, 0.9))
		"perfume":
			_cbox(root, Vector3.ZERO, Vector3(0.06, 0.08, 0.03), _m(Color(0.85, 0.65, 0.75, 0.55), 0.05, 0.0, true), 0.006)
			_cyl(root, Vector3(0, 0.05, 0), 0.012, 0.02, _m(Color(0.8, 0.65, 0.3), 0.25, 0.9))
		"battery":
			_cbox(root, Vector3.ZERO, Vector3(0.08, 0.14, 0.05), _m(Color(0.1, 0.1, 0.11), 0.6), 0.004)
			_box(root, Vector3(0, 0.02, 0.026), Vector3(0.07, 0.05, 0.001), _m(Color(0.9, 0.7, 0.1), 0.6))
			for sx in [-1.0, 1.0]:
				_cyl(root, Vector3(sx * 0.022, 0.078, 0), 0.006, 0.014, _m(Color(0.8, 0.2, 0.1) if sx > 0 else Color(0.2, 0.2, 0.2), 0.5, 0.6))
		"wires":
			var cu := _m(Color(0.75, 0.4, 0.2), 0.3, 0.9)
			for i in range(3):
				_torus(root, Vector3(0, i * 0.008, 0), 0.04, 0.047, cu)
			_torus(root, Vector3(0, 0.026, 0), 0.03, 0.036, _m(Color(0.1, 0.1, 0.1), 0.7))
		"toolset":
			_cbox(root, Vector3.ZERO, Vector3(0.32, 0.085, 0.2), _m(Color(0.75, 0.15, 0.1), 0.55), 0.01)
			_box(root, Vector3(0, 0.0, 0.101), Vector3(0.3, 0.004, 0.002), _m(Color(0.1, 0.1, 0.1), 0.7))
			_cbox(root, Vector3(0, 0.055, 0), Vector3(0.12, 0.02, 0.025), _m(Color(0.1, 0.1, 0.1), 0.7), 0.006)
			for sx in [-1.0, 1.0]:
				_box(root, Vector3(sx * 0.1, 0.02, 0.101), Vector3(0.025, 0.02, 0.004), _m(Color(0.7, 0.7, 0.72), 0.3, 0.9))
		"documents":
			_box(root, Vector3.ZERO, Vector3(0.22, 0.012, 0.31), _m(Color(0.8, 0.7, 0.45), 0.8))
			_box(root, Vector3(0.01, 0.007, -0.01), Vector3(0.2, 0.002, 0.28), _m(Color(0.95, 0.95, 0.92), 0.8))
			_box(root, Vector3(0.0, 0.0085, 0.06), Vector3(0.12, 0.001, 0.02), _m(Color(0.7, 0.1, 0.1), 0.8))
		"key_server", "key_jewelry":
			var metal := _m(Color(0.75, 0.68, 0.45) if id == "key_jewelry" else Color(0.7, 0.72, 0.75), 0.3, 0.95)
			_torus(root, Vector3(-0.03, 0, 0), 0.009, 0.016, metal)
			_box(root, Vector3(0.012, 0, 0), Vector3(0.05, 0.003, 0.007), metal)
			for i in range(3):
				_box(root, Vector3(0.02 + i * 0.01, 0, 0.006), Vector3(0.005, 0.003, 0.006 + (i % 2) * 0.004), metal)
		"keycard_security":
			_cbox(root, Vector3.ZERO, Vector3(0.086, 0.002, 0.054), _m(Color(0.92, 0.92, 0.9), 0.5), 0.0008)
			_box(root, Vector3(0, 0.0011, -0.015), Vector3(0.086, 0.001, 0.012), _m(Color(0.1, 0.2, 0.55), 0.5))
			_box(root, Vector3(-0.025, 0.0011, 0.012), Vector3(0.02, 0.001, 0.015), _m(Color(0.8, 0.65, 0.3), 0.3, 0.9))
		_:
			if String(it.get("cat", "")) == "ammo":
				_ammo_box(root, id)
			else:
				_cbox(root, Vector3.ZERO, Vector3(0.06, 0.04, 0.06), _m(Color(0.4, 0.4, 0.4), 0.6), 0.005)
	return root


## Калибр → цвет пачки, радиус и длина патрона, м.
const CALIBER_LOOK := {
	"9x18": [Color(0.42, 0.36, 0.28), 0.0046, 0.025], "9x19": [Color(0.3, 0.35, 0.5), 0.0048, 0.029],
	"9x39": [Color(0.36, 0.3, 0.42), 0.0048, 0.056], "12x70": [Color(0.6, 0.15, 0.12), 0.0105, 0.07],
	"545x39": [Color(0.45, 0.4, 0.2), 0.0045, 0.057], "556x45": [Color(0.3, 0.42, 0.36), 0.0045, 0.057],
	"762x39": [Color(0.5, 0.32, 0.18), 0.0056, 0.056], "762x51": [Color(0.28, 0.3, 0.34), 0.0062, 0.071],
	"762x54r": [Color(0.3, 0.38, 0.28), 0.0062, 0.077]}


## Пачка патронов: картонная коробка цвета калибра и несколько патронов перед ней; бронебойные —
## с чёрной вершинкой, пулевые 12-го — с полосой.
static func _ammo_box(root: Node3D, id: String) -> void:
	var cal := String(WeaponDb.ammo(id).get("caliber", "9x19"))
	var look: Array = CALIBER_LOOK.get(cal, CALIBER_LOOK["9x19"])
	var col: Color = look[0]
	var r := float(look[1])
	var l := float(look[2])
	var ap := id.ends_with("_ap") or id.ends_with("_apslug")
	if ap:
		col = col.darkened(0.35)
	var shot := cal == "12x70"
	id = "ammo_12" if shot else id
	_cbox(root, Vector3(0, 0, -0.03), Vector3(0.11, maxf(l * 0.8, 0.04), 0.06), _m(col, 0.85), 0.003)
	var brass := _m(Color(0.8, 0.62, 0.3), 0.3, 0.9)
	var tip := _m(Color(0.08, 0.08, 0.08) if ap and not shot else (Color(0.72, 0.45, 0.3) if not shot else Color(0.7, 0.1, 0.08)), 0.35, 0.7)
	for i in range(4):
		var x := -0.04 + i * 0.027
		_cyl(root, Vector3(x, -maxf(l * 0.4, 0.02) + l * 0.35, 0.02), r, l * 0.7, brass if id != "ammo_12" else tip)
		_cyl(root, Vector3(x, -maxf(l * 0.4, 0.02) + l * 0.78, 0.02), r * 0.85, l * 0.25, tip if id != "ammo_12" else brass, r * 0.3 if id != "ammo_12" else -1.0)


# ---------------------------------------------------------------- арсенал

## Магазин, плита, жилет / плитоносец, шлем, гарнитура — по данным (data/weapons.json, armor.json).
static func _arsenal(root: Node3D, id: String) -> bool:
	var mag := WeaponDb.magazine(id)
	if not mag.is_empty():
		_magazine(root, id, mag)
		return true
	var pl := WeaponDb.plate(id)
	if not pl.is_empty():
		var mat := String(pl.get("material", "steel"))
		var col := {"steel": Color(0.36, 0.37, 0.38), "ceramic": Color(0.62, 0.58, 0.5), "composite": Color(0.2, 0.22, 0.2),
			"uhmwpe": Color(0.82, 0.82, 0.78)}.get(mat, Color(0.3, 0.32, 0.3)) as Color
		var t := 0.012 + 0.004 * float(pl["class"])
		var p := _cbox(root, Vector3.ZERO, Vector3(0.25, 0.3, t), _m(col, 0.75 if mat != "steel" else 0.45, 0.6 if mat == "steel" else 0.0), 0.02)
		p.rotation.x = -0.08
		_cbox(root, Vector3(0, 0.1, t * 0.5), Vector3(0.12, 0.03, 0.002), _m(Color(0.9, 0.88, 0.8), 0.8), 0.001)
		return true
	var v := WeaponDb.vest(id)
	if not v.is_empty():
		var carrier := (v.get("plates", []) as Array).size() > 0
		# плитоносец — модель Sketchfab (CC-BY, assets/CREDITS.md); мягкий жилет — пока из форм
		if carrier and _scan(root, "plate_carrier"):
			return true
		var tier := int(ItemDb.item(id).get("tier", 1))
		var cloth := [Color(0.3, 0.28, 0.22), Color(0.22, 0.25, 0.18), Color(0.2, 0.22, 0.16), Color(0.14, 0.15, 0.13), Color(0.1, 0.11, 0.12)][clampi(tier, 0, 4)] as Color
		_vest(root, carrier, cloth)
		return true
	var h := WeaponDb.helmet(id)
	if not h.is_empty():
		# армейский шлем — модель Sketchfab; строительная каска — из форм
		if id != "helmet_hardhat" and _scan(root, "helmet"):
			return true
		var tier := int(ItemDb.item(id).get("tier", 1))
		var col := Color(0.85, 0.72, 0.2) if id == "helmet_hardhat" else ([Color(0.3, 0.32, 0.24), Color(0.25, 0.28, 0.2), Color(0.18, 0.2, 0.22), Color(0.14, 0.15, 0.16), Color(0.1, 0.11, 0.12)][clampi(tier, 0, 4)] as Color)
		_helmet(root, col, "VISOR" in (h.get("mounts", []) as Array))
		return true
	if not WeaponDb.headset(id).is_empty():
		# активные (тактические) — модель Sketchfab; пассивные «строительные» красные — из форм
		if id != "headset_passive" and _scan(root, "headset"):
			return true
		var shell := _m(Color(0.16, 0.17, 0.15) if id != "headset_passive" else Color(0.55, 0.12, 0.1), 0.6)
		for sx in [-1.0, 1.0]:
			_cyl(root, Vector3(sx * 0.08, 0, 0), 0.042, 0.035, shell).rotation.z = PI * 0.5
			_cyl(root, Vector3(sx * 0.06, 0, 0), 0.036, 0.008, _m(Color(0.08, 0.08, 0.08), 0.9)).rotation.z = PI * 0.5
		_torus(root, Vector3(0, 0.035, 0), 0.075, 0.085, _m(Color(0.1, 0.1, 0.1), 0.7)).rotation.x = PI * 0.5
		if id != "headset_passive":
			var mic := _cyl(root, Vector3(-0.05, -0.04, 0.035), 0.003, 0.08, _m(Color(0.1, 0.1, 0.1), 0.7))
			mic.rotation = Vector3(0, 0, 1.2)
		return true
	return false


## Магазин: коробка по ёмкости и длине патрона (у калашниковских — изогнутый, двумя секциями).
static func _magazine(root: Node3D, id: String, mag: Dictionary) -> void:
	var cal := WeaponDb.mag_caliber(id)
	var look: Array = CALIBER_LOOK.get(cal, CALIBER_LOOK["9x19"])
	var cap := int(mag.get("capacity", 30))
	var l := float(look[2])
	var r := float(look[1])
	var w := l + 0.012
	var t := r * 2.0 + 0.008
	var h := 0.03 + float(cap) * r * (1.0 if cap <= 20 else 0.62)
	var ak := String(mag.get("if", "")).begins_with("MAG_AK")
	var mat := _m(Color(0.5, 0.3, 0.16) if String(mag.get("if", "")) == "MAG_AK762" else Color(0.14, 0.14, 0.13), 0.6, 0.3)
	if ak:
		var top := _cbox(root, Vector3(0, h * 0.25, 0), Vector3(w, h * 0.5, t), mat, 0.004)
		var bot := _cbox(root, Vector3(0.018, -h * 0.22, 0), Vector3(w, h * 0.5, t), mat, 0.004)
		top.rotation.z = 0.12
		bot.rotation.z = 0.32
	else:
		_cbox(root, Vector3.ZERO, Vector3(w, h, t), mat, 0.004)
	# верхний патрон
	var brass := _m(Color(0.8, 0.62, 0.3), 0.3, 0.9)
	_cyl(root, Vector3(0, h * 0.5 + r, 0), r, l * 0.9, brass).rotation.z = PI * 0.5


## Магазин таким, каким он стоит в оружии: из модели ствола, к которому он штатный (или хотя бы
## подходит), остаётся одна деталь магазина. Центр — в начале узла. Нет такой детали — null.
static func weapon_magazine(mag_id: String) -> Node3D:
	var owner: String = ""
	for wid: Variant in WeaponDb.ids("weapons"):
		if WeaponDb.default_mag(String(wid)) == mag_id:
			owner = String(wid)
			break
		if owner == "" and WeaponDb.mag_fits(String(wid), mag_id):
			owner = String(wid)
	if owner == "":
		return null
	var gun: Node3D = WeaponModels.build(owner, {}, 0, 100.0, mag_id)
	var parts: Array[Node3D] = []
	var poses: Array[Transform3D] = []
	for node: Node in gun.find_children("*", "Node3D", true, false):
		var part: Node3D = node as Node3D
		if (String(part.get_meta("part", "")) == "mag" and part.visible) or part.name == "MagLook":
			parts.append(part)
			poses.append(WeaponModels.between(gun, part))
	if parts.is_empty():
		gun.free()
		return null
	var root := Node3D.new()
	root.name = "Item_" + mag_id
	for i: int in range(parts.size()):
		parts[i].get_parent().remove_child(parts[i])
		parts[i].owner = null
		root.add_child(parts[i])
		parts[i].transform = poses[i]
	gun.free()
	var center: Vector3 = bounds(root).get_center()
	for child: Node in root.get_children():
		(child as Node3D).position -= center
	return root


## Границы всей видимой геометрии с трансформом корня: опора физической находки.
static func bounds(root: Node3D) -> AABB:
	var box: AABB = AABB()
	var first: bool = true
	var meshes: Array = root.find_children("*", "MeshInstance3D", true, false)
	if root is MeshInstance3D:
		meshes.append(root)
	for node: Node in meshes:
		var mesh: MeshInstance3D = node as MeshInstance3D
		if mesh.mesh == null or not mesh.visible:
			continue
		var part: AABB = _xf_to(root, mesh) * mesh.get_aabb()
		box = part if first else box.merge(part)
		first = false
	return box


## Готовая модель снаряжения по центру узла; нет файла — false (запасные формы).
static func _scan(root: Node3D, name: String) -> bool:
	return _scan_path(root, "res://assets/zone01/models/sf_%s.glb" % name)


## Готовая модель по пути — по центру узла; нет файла — false.
static func _scan_path(root: Node3D, path: String) -> bool:
	if not ResourceLoader.exists(path):
		return false
	var inst := (load(path) as PackedScene).instantiate() as Node3D
	root.add_child(inst)
	var box := AABB()
	var first := true
	# корень GLB из одного меша — сам MeshInstance3D (find_children его не включает)
	var meshes: Array = inst.find_children("*", "MeshInstance3D", true, false)
	if inst is MeshInstance3D:
		meshes.append(inst)
	for n in meshes:
		var mi := n as MeshInstance3D
		var b: AABB = inst.transform.affine_inverse() * (_xf_to(inst, mi) * mi.get_aabb())
		box = b if first else box.merge(b)
		first = false
	inst.position = -box.get_center()
	return true


## Преобразование узла в систему предка (без дерева сцены: global_transform ещё не готов).
static func _xf_to(top: Node3D, n: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = n
	while cur != null and cur != top.get_parent():
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t


static func _vest(root: Node3D, heavy: bool, color: Color) -> void:
	var cloth := _m(color, 0.9)
	var pouch := _m(color.darkened(0.15), 0.95)
	_cbox(root, Vector3.ZERO, Vector3(0.3, 0.36, 0.06 if not heavy else 0.08), cloth, 0.02)
	for sx in [-1.0, 1.0]:
		_cbox(root, Vector3(sx * 0.1, 0.22, -0.02), Vector3(0.06, 0.1, 0.03), cloth, 0.01)
	for i in range(3):
		_cbox(root, Vector3(-0.09 + i * 0.09, -0.08, 0.045), Vector3(0.075, 0.1, 0.035), pouch, 0.008)
	if heavy:
		_cbox(root, Vector3(0, 0.05, 0.045), Vector3(0.24, 0.1, 0.03), pouch, 0.008)
		for sx in [-1.0, 1.0]:
			_cbox(root, Vector3(sx * 0.17, -0.02, -0.02), Vector3(0.04, 0.22, 0.12), cloth, 0.01)


static func _helmet(root: Node3D, color: Color, visor: bool) -> void:
	var shell := _sphere(root, Vector3.ZERO, 0.12, _m(color, 0.7))
	shell.scale = Vector3(1.0, 0.8, 1.1)
	_torus(root, Vector3(0, -0.005, 0), 0.118, 0.13, _m(color.darkened(0.2), 0.7))
	if visor:
		var vz := _cbox(root, Vector3(0, -0.02, 0.1), Vector3(0.2, 0.1, 0.01), _m(Color(0.25, 0.3, 0.32, 0.6), 0.1, 0.2, true), 0.01)
		vz.rotation.x = 0.25


# ---------------------------------------------------------------- примитивы

static func _m(c: Color, rough: float, metal: float = 0.0, transparent: bool = false, emit: float = 0.0) -> StandardMaterial3D:
	var key := "%s|%.2f|%.2f|%s|%.1f" % [c.to_html(), rough, metal, transparent, emit]
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	if transparent or c.a < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emit
	_mats[key] = m
	return m


static func _cbox(p: Node3D, at: Vector3, size: Vector3, mat: Material, b: float) -> MeshInstance3D:
	return WeaponModels._cbox(p, at, size, mat, b)


static func _box(p: Node3D, at: Vector3, size: Vector3, mat: Material) -> MeshInstance3D:
	return WeaponModels._box(p, at, size, mat)


## Цилиндр стоя (вдоль Y); лёжа — повернуть узел.
static func _cyl(p: Node3D, at: Vector3, r: float, length: float, mat: Material, top_r: float = -1.0) -> MeshInstance3D:
	var mi := WeaponModels._cyl(p, at, r, length, mat, top_r)
	mi.rotation = Vector3.ZERO
	return mi


static func _sphere(p: Node3D, at: Vector3, r: float, mat: Material) -> MeshInstance3D:
	return WeaponModels._sphere(p, at, r, mat)


static func _torus(p: Node3D, at: Vector3, inner: float, outer: float, mat: Material) -> MeshInstance3D:
	return WeaponModels._torus(p, at, inner, outer, mat)
