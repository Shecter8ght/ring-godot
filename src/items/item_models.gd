class_name ItemModels
extends RefCounted
## Модели предметов для иконок (tools/icon_bake → assets/icons/<id>.png) и, при желании, для
## предметов на полу. Оружие — WeaponModels, обвесы — WeaponMods (на пустом узле по точке
## крепления первого подходящего ствола), граната — WeaponModels, остальное — простые формы
## из примитивов с фасками в реальных размерах: бинт — рулон, аптечка — кейс с крестом,
## патроны — пачка с патронами, деньги — пачка с бандеролью.

static var _mats: Dictionary = {}


static func build(id: String) -> Node3D:
	var it := ItemDb.item(id)
	var eq: Dictionary = it.get("equip", {})
	if eq.has("weapon"):
		return WeaponModels.build(String(eq.weapon))
	if id == "grenade":
		return WeaponModels.build("grenade")
	var ms: Dictionary = it.get("mod", {})
	if not ms.is_empty():
		var host := String((ms.get("fits", ["rifle"]) as Array)[0])
		var r := Node3D.new()
		WeaponMods.fit(r, host, {String(ms.slot): id})
		return r
	var root := Node3D.new()
	root.name = "Item_" + id
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
		"vest_light", "vest_heavy":
			var heavy := id == "vest_heavy"
			var cloth := _m(Color(0.22, 0.25, 0.18) if not heavy else Color(0.14, 0.15, 0.13), 0.9)
			_cbox(root, Vector3.ZERO, Vector3(0.3, 0.36, 0.06 if not heavy else 0.08), cloth, 0.02)
			for sx in [-1.0, 1.0]:
				_cbox(root, Vector3(sx * 0.1, 0.22, -0.02), Vector3(0.06, 0.1, 0.03), cloth, 0.01)
			for i in range(3):
				_cbox(root, Vector3(-0.09 + i * 0.09, -0.08, 0.045), Vector3(0.075, 0.1, 0.035), _m(Color(0.2, 0.22, 0.16) if not heavy else Color(0.1, 0.11, 0.1), 0.95), 0.008)
			if heavy:
				_cbox(root, Vector3(0, 0.05, 0.045), Vector3(0.24, 0.1, 0.03), _m(Color(0.1, 0.11, 0.1), 0.95), 0.008)
				for sx in [-1.0, 1.0]:
					_cbox(root, Vector3(sx * 0.17, -0.02, -0.02), Vector3(0.04, 0.22, 0.12), cloth, 0.01)
		"helmet":
			var shell := _sphere(root, Vector3.ZERO, 0.12, _m(Color(0.25, 0.28, 0.2), 0.7))
			shell.scale = Vector3(1.0, 0.8, 1.1)
			_torus(root, Vector3(0, -0.005, 0), 0.118, 0.13, _m(Color(0.2, 0.22, 0.16), 0.7))
		_:
			if String(it.get("cat", "")) == "ammo":
				_ammo_box(root, id)
			else:
				_cbox(root, Vector3.ZERO, Vector3(0.06, 0.04, 0.06), _m(Color(0.4, 0.4, 0.4), 0.6), 0.005)
	return root


## Пачка патронов: картонная коробка цвета калибра и несколько патронов перед ней.
static func _ammo_box(root: Node3D, id: String) -> void:
	var col := Color(0.55, 0.45, 0.25)
	var r := 0.0048
	var l := 0.029
	match id:
		"ammo_9x19":
			col = Color(0.3, 0.35, 0.5)
			r = 0.0048
			l = 0.029
		"ammo_545":
			col = Color(0.45, 0.4, 0.2)
			r = 0.0045
			l = 0.057
		"ammo_12":
			col = Color(0.6, 0.15, 0.12)
			r = 0.0105
			l = 0.07
		"ammo_762r":
			col = Color(0.3, 0.38, 0.28)
			r = 0.0062
			l = 0.077
	_cbox(root, Vector3(0, 0, -0.03), Vector3(0.11, maxf(l * 0.8, 0.04), 0.06), _m(col, 0.85), 0.003)
	var brass := _m(Color(0.8, 0.62, 0.3), 0.3, 0.9)
	var tip := _m(Color(0.72, 0.45, 0.3) if id != "ammo_12" else Color(0.7, 0.1, 0.08), 0.35, 0.7)
	for i in range(4):
		var x := -0.04 + i * 0.027
		_cyl(root, Vector3(x, -maxf(l * 0.4, 0.02) + l * 0.35, 0.02), r, l * 0.7, brass if id != "ammo_12" else tip)
		_cyl(root, Vector3(x, -maxf(l * 0.4, 0.02) + l * 0.78, 0.02), r * 0.85, l * 0.25, tip if id != "ammo_12" else brass, r * 0.3 if id != "ammo_12" else -1.0)


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
