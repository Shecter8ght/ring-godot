class_name WeaponMods
extends RefCounted
## Обвесы на процедурные модели оружия. Каждый ставится в точку крепления конкретного ствола
## (MOUNTS — снято с геометрии WeaponModels, метры, оси модели: +Z к дулу, +Y вверх):
## прицел — на планку (планка ставится, если её нет), линия прицеливания — через центр линзы;
## глушитель/компенсатор — на резьбу ствола, дульный срез переезжает на торец; рукоятка — на
## планку под цевьём; приклад, магазин — вместо штатных (они помечены meta "part" и прячутся).
## Меняет meta модели: sight_h (новая линия прицеливания), muzzle, scoped.
## Фонарь и ЛЦУ дают узлы "Flashlight" (SpotLight3D) и "LaserBeam" — включает игрок (T).

## Точки крепления по оружию: слот -> {pos, ...}. surface — поверхность, на которую ложится
## основание (для прицела — верх ствольной коробки/крышки; для рукоятки — низ цевья).
const MOUNTS := {
	"pistol": {
		# по модели «Glock»: вырез под мини-коллиматор — на затворе перед целиком (верх затвора 0.076);
		# дульный срез 0.156; фонарь/ЛЦУ — на планку под пылезащитной частью рамки (низ 0.033);
		# магазин — от верха рукояти по её оси (22° назад), длина рукояти 0.085
		"optic": {"pos": Vector3(0, 0.076, 0.004), "rail": false},
		"muzzle": {"pos": Vector3(0, 0.06, 0.156), "bore_r": 0.0065},
		"tac": {"pos": Vector3(0, 0.031, 0.115), "side": false},
		"mag": {"pos": Vector3(0, 0.033, 0.006), "half": 0.085, "tilt": 22.0},
	},
	"rifle": {
		# планка на крышку ствольной коробки (крышка — цилиндр r 0.0205 по оси y 0.07, z 0.009–0.121,
		# верх 0.0905) — утоплена на 2 мм, длиной с крышку; тормоз снимается — резьба 0.575;
		# рукоятка — под нижнюю накладку цевья (низ ~0.0225); фонарь — на боковую планку цевья справа
		"optic": {"pos": Vector3(0, 0.0885, 0.065), "rail": true, "rail_len": 0.11, "riser": 0.0},
		"muzzle": {"pos": Vector3(0, 0.052, 0.575), "bore_r": 0.0085, "replace": true},
		"grip": {"pos": Vector3(0, 0.0225, 0.35)},
		"stock": {"pos": Vector3(0, 0.045, -0.07)},
		"mag": {"pos": Vector3(0, 0.02, 0.128)},
		"tac": {"pos": Vector3(-0.0245, 0.046, 0.395), "side": true},
	},
	"shotgun": {
		# плоский верх коробки 0.077; дульный срез 0.67; рукоятка — под цевьё-помпу (низ 0.014);
		# фонарь — на хомут подствольного магазина справа
		"optic": {"pos": Vector3(0, 0.077, 0.07), "rail": true, "rail_len": 0.16, "riser": 0.0},
		"muzzle": {"pos": Vector3(0, 0.064, 0.67), "bore_r": 0.0105},
		"grip": {"pos": Vector3(0, 0.014, 0.33)},
		"stock": {"pos": Vector3(0, 0.05, -0.03)},
		"tac": {"pos": Vector3(-0.012, 0.05, 0.585), "side": true},
	},
	"bolt": {
		# дульный срез 0.80 (ствол сужается до 0.0078); сошки — хомут под цевьём (низ ~0.0145)
		"muzzle": {"pos": Vector3(0, 0.062, 0.8), "bore_r": 0.0078},
		"bipod": {"pos": Vector3(0, 0.0145, 0.47)},
	},
}

## Высота планки Пикатинни (основание + зубцы), м.
const RAIL_H := 0.006


static func fit(root: Node3D, weapon: String, mods: Dictionary) -> void:
	var mounts: Dictionary = MOUNTS.get(weapon, {})
	for slot in mods:
		var id := String(mods[slot])
		var spec: Dictionary = ItemDb.item(id).get("mod", {})
		if spec.is_empty() or not mounts.has(slot) or not weapon in spec.get("fits", []):
			continue
		var m: Dictionary = mounts[slot]
		# прицел на планке — целик сложен: иначе торчит в нижней части окна прицела
		if String(slot) == "optic":
			_hide_part(root, "rear_sight")
		match String(spec.look):
			"red_dot":
				_red_dot(root, m)
			"holo":
				_holo(root, m)
			"rmr":
				_rmr(root, m)
			"scope4x":
				_scope4x(root, m)
			"suppressor":
				_suppressor(root, m, float(spec.size[0]), float(spec.size[1]))
			"compensator":
				_compensator(root, m)
			"grip_vertical":
				_grip_vertical(root, m)
			"grip_angled":
				_grip_angled(root, m)
			"stock_tele":
				_stock_tele(root, m)
			"mag_ak45":
				_mag_ak45(root, m)
			"mag_pistol_ext":
				_mag_pistol_ext(root, m)
			"flashlight":
				_flashlight(root, m)
			"laser":
				_laser(root, m)
			"bipod":
				_bipod(root, m)


# ---------------------------------------------------------------- общее

static func _mat(id: String) -> StandardMaterial3D:
	return WeaponModels._mat(id)


static func _hide_part(root: Node3D, part: String) -> void:
	for mi in root.find_children("*", "MeshInstance3D", true, false):
		if String(mi.get_meta("part", "")) == part:
			(mi as MeshInstance3D).visible = false


## Планка Пикатинни вдоль Z: основание от y0, зубцы сверху с шагом 10 мм. Возвращает верх планки.
static func _rail_z(root: Node3D, y0: float, z: float, length: float, x: float = 0.0) -> float:
	var al := _mat("anodized")
	WeaponModels._cbox(root, Vector3(x, y0 + 0.00175, z), Vector3(0.016, 0.0035, length), al, 0.0008)
	var n := int(floor(length / 0.01))
	for i in range(n):
		var zz := z - length * 0.5 + 0.005 + i * 0.01
		WeaponModels._cbox(root, Vector3(x, y0 + 0.0035 + 0.00125, zz), Vector3(0.0212, 0.0025, 0.0052), al, 0.0005)
	return y0 + RAIL_H


## Короткая планка вертикально на боку (x0 — плоскость боковой поверхности, наружу — по знаку x0;
## -X — правая сторона стрелка). Возвращает x внешней грани.
static func _rail_side(root: Node3D, x0: float, y: float, z: float, length: float) -> float:
	var al := _mat("anodized")
	var s := signf(x0) if x0 != 0.0 else 1.0
	WeaponModels._cbox(root, Vector3(x0 + s * 0.00175, y, z), Vector3(0.0035, 0.016, length), al, 0.0008)
	var n := int(floor(length / 0.01))
	for i in range(n):
		var zz := z - length * 0.5 + 0.005 + i * 0.01
		WeaponModels._cbox(root, Vector3(x0 + s * (0.0035 + 0.00125), y, zz), Vector3(0.0025, 0.0212, 0.0052), al, 0.0005)
	return x0 + s * RAIL_H


## Основание прицела: подъём (если у ствола нужна проставка) + планка; возвращает высоту верха.
static func _optic_base(root: Node3D, m: Dictionary, length: float) -> float:
	var p: Vector3 = m.pos
	var y := p.y
	var riser := float(m.get("riser", 0.0))
	if riser > 0.0:
		# проставка повторяет крышку: ложится на рёбра, шире планки
		WeaponModels._cbox(root, Vector3(0, y + riser * 0.5, p.z), Vector3(0.026, riser, float(m.get("rail_len", length))), _mat("anodized"), 0.0012)
		y += riser
	if bool(m.get("rail", false)):
		y = _rail_z(root, y, p.z, float(m.get("rail_len", length)))
	return y


# ---------------------------------------------------------------- прицелы

## Коллиматор-трубка 30 мм на быстросъёмном кронштейне; красная точка — в центре линзы.
static func _red_dot(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var top := _optic_base(root, m, 0.08)
	var al := _mat("anodized")
	var zc := p.z - 0.005
	# кронштейн с рычагом
	WeaponModels._cbox(root, Vector3(0, top + 0.006, zc), Vector3(0.028, 0.012, 0.036), al, 0.0015)
	WeaponModels._cbox(root, Vector3(0.016, top + 0.004, zc + 0.004), Vector3(0.004, 0.006, 0.02), al, 0.001)
	var cy := top + 0.012 + 0.0165
	# труба, кольца-бленды, линзы
	var al2 := _mat("anodized_2s")
	WeaponModels._tube(root, Vector3(0, cy, zc), 0.0165, 0.07, al2)
	WeaponModels._tube(root, Vector3(0, cy, zc + 0.036), 0.0182, 0.008, al2)
	WeaponModels._tube(root, Vector3(0, cy, zc - 0.036), 0.0182, 0.008, al2)
	# торцы бленд — кольца, чтобы стенка трубы читалась толщиной
	for z in [zc + 0.04, zc - 0.04]:
		var ring := WeaponModels._torus(root, Vector3(0, cy, z), 0.0165, 0.0182, al)
		ring.rotation.x = PI * 0.5
	WeaponModels._cyl(root, Vector3(0, cy, zc + 0.0395), 0.0148, 0.001, _mat("glass"))
	WeaponModels._cyl(root, Vector3(0, cy, zc - 0.0395), 0.0148, 0.001, _mat("glass"))
	# барабанчики поправок сверху и справа, колпачок батареи слева
	WeaponModels._cyl(root, Vector3(0, cy + 0.019, zc + 0.004), 0.0065, 0.008, al).rotation = Vector3.ZERO
	WeaponModels._cyl_x(root, Vector3(-0.019, cy, zc + 0.004), 0.0065, 0.008, al)
	WeaponModels._cyl_x(root, Vector3(0.0195, cy, zc - 0.008), 0.0075, 0.01, al)
	# точка — на передней линзе, по оси
	WeaponModels._sphere(root, Vector3(0, cy, zc + 0.0385), 0.0007, _mat("reticle"))
	root.set_meta("sight_h", cy)


## Голографический: коробка-окно с кольцом и точкой, батарейный отсек сзади, кронштейн.
static func _holo(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var top := _optic_base(root, m, 0.09)
	var al := _mat("anodized")
	var zc := p.z
	# основание-корпус; батарея — поперёк в корпусе под окном (как у EOTech), крышка справа.
	# Выше основания сзади ничего нет — иначе закрывало бы низ окна
	WeaponModels._cbox(root, Vector3(0, top + 0.006, zc), Vector3(0.032, 0.012, 0.09), al, 0.0015)
	WeaponModels._cyl_x(root, Vector3(0, top + 0.006, zc + 0.022), 0.0062, 0.034, al)
	WeaponModels._cyl_x(root, Vector3(0.0175, top + 0.006, zc + 0.022), 0.0045, 0.003, _mat("gunmetal"))
	# кнопки яркости сзади — низкие, под линией окна
	for bx in [-0.007, 0.007]:
		WeaponModels._cbox(root, Vector3(bx, top + 0.0125, zc - 0.036), Vector3(0.008, 0.004, 0.008), _mat("rubber"), 0.001)
	# окно: стойки по бокам и козырёк, стекло спереди и сзади
	var wy := top + 0.012 + 0.013
	for sx in [-1.0, 1.0]:
		WeaponModels._cbox(root, Vector3(sx * 0.0155, wy, zc + 0.017), Vector3(0.003, 0.026, 0.046), al, 0.001)
	WeaponModels._cbox(root, Vector3(0, wy + 0.0145, zc + 0.017), Vector3(0.034, 0.004, 0.05), al, 0.0015)
	WeaponModels._box(root, Vector3(0, wy, zc + 0.039), Vector3(0.028, 0.025, 0.0012), _mat("glass"))
	WeaponModels._box(root, Vector3(0, wy, zc - 0.004), Vector3(0.028, 0.025, 0.0012), _mat("glass"))
	# сетка: кольцо и точка на переднем стекле
	var ring := WeaponModels._torus(root, Vector3(0, wy, zc + 0.0385), 0.0038, 0.0043, _mat("reticle"))
	ring.rotation.x = PI * 0.5
	WeaponModels._sphere(root, Vector3(0, wy, zc + 0.0385), 0.0006, _mat("reticle"))
	root.set_meta("sight_h", wy)


## Мини-коллиматор на затвор пистолета: плита в вырезе, корпус-подкова, наклонная линза.
static func _rmr(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var al := _mat("anodized")
	WeaponModels._cbox(root, Vector3(0, p.y + 0.002, p.z), Vector3(0.0235, 0.004, 0.034), al, 0.0008)
	var wy := p.y + 0.004 + 0.008
	for sx in [-1.0, 1.0]:
		WeaponModels._cbox(root, Vector3(sx * 0.0103, wy, p.z + 0.002), Vector3(0.003, 0.016, 0.028), al, 0.0008)
	var hood := WeaponModels._cbox(root, Vector3(0, wy + 0.0085, p.z + 0.005), Vector3(0.0235, 0.003, 0.016), al, 0.001)
	hood.rotation.x = deg_to_rad(-6.0)
	WeaponModels._cbox(root, Vector3(0, p.y + 0.006, p.z - 0.011), Vector3(0.0235, 0.004, 0.01), al, 0.001)
	var lens := WeaponModels._box(root, Vector3(0, wy, p.z + 0.012), Vector3(0.018, 0.013, 0.001), _mat("glass"))
	lens.rotation.x = deg_to_rad(-12.0)
	WeaponModels._sphere(root, Vector3(0, wy, p.z + 0.0115), 0.0005, _mat("reticle"))
	root.set_meta("sight_h", wy)


## Оптика 4×: призменный корпус, объектив и окуляр, волоконный указатель сверху.
static func _scope4x(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var top := _optic_base(root, m, 0.1)
	var al := _mat("anodized")
	var zc := p.z
	WeaponModels._cbox(root, Vector3(0, top + 0.005, zc), Vector3(0.026, 0.01, 0.05), al, 0.0015)
	var cy := top + 0.01 + 0.017
	WeaponModels._cbox(root, Vector3(0, cy, zc), Vector3(0.036, 0.034, 0.075), al, 0.004)
	WeaponModels._cyl(root, Vector3(0, cy, zc + 0.052), 0.0165, 0.03, al, 0.0205)
	WeaponModels._cyl(root, Vector3(0, cy, zc + 0.069), 0.0205, 0.004, al)
	WeaponModels._cyl(root, Vector3(0, cy, zc - 0.049), 0.0175, 0.024, al, 0.016)
	WeaponModels._cyl(root, Vector3(0, cy, zc + 0.0712), 0.018, 0.001, _mat("lens"))
	WeaponModels._cyl(root, Vector3(0, cy, zc - 0.0612), 0.015, 0.001, _mat("lens"))
	WeaponModels._box(root, Vector3(0, cy + 0.0175, zc), Vector3(0.004, 0.003, 0.06), _mat("dot"))
	WeaponModels._cyl(root, Vector3(0, cy + 0.02, zc + 0.012), 0.006, 0.006, al).rotation = Vector3.ZERO
	WeaponModels._cyl_x(root, Vector3(-0.02, cy, zc + 0.012), 0.006, 0.006, al)
	root.set_meta("sight_h", cy)
	root.set_meta("scoped", true)
	# окуляр и вынос глаза ~75 мм: глаз стоит за окуляром, а не у рукояти
	var oz := zc - 0.0615
	root.set_meta("ocular", Vector3(0, cy, oz))
	root.set_meta("ocular_r", 0.0148)
	root.set_meta("ads_z", 0.075 - oz)


# ---------------------------------------------------------------- дульные

## Глушитель: резьбовая муфта по стволу, корпус, скошенный торец, насечка у муфты.
static func _suppressor(root: Node3D, m: Dictionary, r: float, length: float) -> void:
	if bool(m.get("replace", false)):
		_hide_part(root, "muzzle_device")
	var p: Vector3 = m.pos
	var br := float(m.bore_r)
	var sm := _mat("suppressor")
	WeaponModels._cyl(root, Vector3(0, p.y, p.z + 0.006), br + 0.0028, 0.012, _mat("gunmetal"))
	var z0 := p.z + 0.012
	WeaponModels._cyl(root, Vector3(0, p.y, z0 + 0.004), br + 0.0028, 0.008, sm, r)
	WeaponModels._cyl(root, Vector3(0, p.y, z0 + 0.008 + length * 0.5), r, length, sm)
	for i in range(3):
		WeaponModels._cyl(root, Vector3(0, p.y, z0 + 0.016 + i * 0.006), r + 0.0004, 0.0018, _mat("gunmetal"))
	var z1 := z0 + 0.008 + length
	WeaponModels._cyl(root, Vector3(0, p.y, z1 + 0.003), r, 0.006, sm, r * 0.86)
	WeaponModels._cyl(root, Vector3(0, p.y, z1 + 0.0062), br * 0.9, 0.001, _mat("bore"))
	root.set_meta("muzzle", Vector3(0, p.y, z1 + 0.006))
	root.set_meta("suppressed", true)


## Компенсатор вместо дульного тормоза: окна сверху уводят ствол вниз.
static func _compensator(root: Node3D, m: Dictionary) -> void:
	_hide_part(root, "muzzle_device")
	var p: Vector3 = m.pos
	var st := _mat("blued")
	WeaponModels._cyl(root, Vector3(0, p.y, p.z + 0.037), 0.0125, 0.074, st)
	for i in range(3):
		WeaponModels._box(root, Vector3(0, p.y + 0.0105, p.z + 0.022 + i * 0.016), Vector3(0.012, 0.005, 0.007), _mat("bore"))
		for sx in [-1.0, 1.0]:
			WeaponModels._box(root, Vector3(sx * 0.0105, p.y, p.z + 0.03 + i * 0.016), Vector3(0.005, 0.012, 0.006), _mat("bore"))
	WeaponModels._cyl(root, Vector3(0, p.y, p.z + 0.0745), 0.007, 0.001, _mat("bore"))
	root.set_meta("muzzle", Vector3(0, p.y, p.z + 0.075))


# ---------------------------------------------------------------- под цевьё

## Вертикальная рукоятка: планка под цевьём, корпус с наклоном вперёд, рифление, торцевая крышка.
static func _grip_vertical(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var al := _mat("anodized")
	var poly := _mat("polymer")
	WeaponModels._cbox(root, Vector3(0, p.y - 0.003, p.z), Vector3(0.02, 0.006, 0.07), al, 0.001)
	var g := Node3D.new()
	g.position = Vector3(0, p.y - 0.006, p.z + 0.01)
	g.rotation.x = deg_to_rad(-9.0)
	root.add_child(g)
	WeaponModels._cbox(g, Vector3(0, -0.004, 0), Vector3(0.024, 0.008, 0.036), poly, 0.002)
	WeaponModels._cbox(g, Vector3(0, -0.047, 0), Vector3(0.026, 0.082, 0.03), poly, 0.006)
	for i in range(4):
		WeaponModels._box(g, Vector3(0, -0.022 - i * 0.017, 0.0152), Vector3(0.022, 0.006, 0.002), _mat("polymer_grip"))
	WeaponModels._cbox(g, Vector3(0, -0.09, 0), Vector3(0.028, 0.006, 0.032), _mat("rubber"), 0.002)


## Угловая рукоятка: клин вдоль цевья — упор для ладони, без выступа вниз.
static func _grip_angled(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	WeaponModels._cbox(root, Vector3(0, p.y - 0.003, p.z), Vector3(0.02, 0.006, 0.08), _mat("anodized"), 0.001)
	# верх — вплотную по планке (низ планки rb), толщина растёт назад: скос под ладонь
	var rb := p.y - 0.006
	WeaponModels._sweep(root, [Vector3(0, rb - 0.003, p.z + 0.042), Vector3(0, rb - 0.009, p.z + 0.01), Vector3(0, rb - 0.017, p.z - 0.022), Vector3(0, rb - 0.02, p.z - 0.036)] as Array[Vector3],
		[Vector2(0.024, 0.006), Vector2(0.025, 0.018), Vector2(0.026, 0.034), Vector2(0.026, 0.04)] as Array[Vector2], _mat("polymer"), 0.3)


# ---------------------------------------------------------------- приклад, магазин

## Телескопический приклад: переходник к коробке, буферная трубка, приклад на трубке, затыльник.
static func _stock_tele(root: Node3D, m: Dictionary) -> void:
	_hide_part(root, "stock")
	var p: Vector3 = m.pos
	var al := _mat("anodized")
	var poly := _mat("polymer")
	WeaponModels._cbox(root, Vector3(0, p.y - 0.002, p.z - 0.012), Vector3(0.034, 0.044, 0.026), al, 0.003)
	WeaponModels._cyl(root, Vector3(0, p.y, p.z - 0.028), 0.0185, 0.01, al)
	WeaponModels._cyl(root, Vector3(0, p.y, p.z - 0.13), 0.0145, 0.2, al)
	var s := Node3D.new()
	s.position = Vector3(0, p.y, p.z - 0.19)
	root.add_child(s)
	WeaponModels._cheek(WeaponModels._cbox(s, Vector3(0, 0.002, 0), Vector3(0.04, 0.036, 0.12), poly, 0.005))
	WeaponModels._cheek(WeaponModels._sweep(s, [Vector3(0, -0.012, 0.04), Vector3(0, -0.035, -0.02), Vector3(0, -0.052, -0.06)] as Array[Vector3],
		[Vector2(0.036, 0.022), Vector2(0.037, 0.03), Vector2(0.038, 0.034)] as Array[Vector2], poly, 0.3))
	WeaponModels._cheek(WeaponModels._cbox(s, Vector3(0, -0.018, -0.067), Vector3(0.044, 0.096, 0.016), _mat("rubber"), 0.004))
	WeaponModels._cbox(s, Vector3(0, -0.02, 0.03), Vector3(0.008, 0.01, 0.028), al, 0.001)


## Магазин на 45: та же дуга, что у штатного, на треть длиннее.
static func _mag_ak45(root: Node3D, m: Dictionary) -> void:
	_hide_part(root, "mag")
	var mp: Array[Vector3] = []
	var ms: Array[Vector2] = []
	var q: Vector3 = m.pos
	var ang := 0.0
	for i in range(12):
		mp.append(q)
		ms.append(Vector2(0.024, 0.056 - i * 0.001))
		q += Vector3(0, -cos(ang), sin(ang)) * 0.024
		ang += deg_to_rad(4.2)
	WeaponModels._sweep(root, mp, ms, _mat("polymer"), 0.2)
	var rp: Array[Vector3] = []
	var rs: Array[Vector2] = []
	for i in range(1, mp.size() - 1):
		rp.append(mp[i])
		rs.append(Vector2(0.0262, 0.008))
	WeaponModels._sweep(root, rp, rs, _mat("polymer"), 0.3)


## Удлинённый магазин пистолета: вставка-удлинитель и новая пятка ниже по оси рукояти.
static func _mag_pistol_ext(root: Node3D, m: Dictionary) -> void:
	_hide_part(root, "mag")
	var tilt := Basis(Vector3.RIGHT, deg_to_rad(float(m.tilt)))
	var down := tilt * Vector3.DOWN
	# низ рукояти — отсюда вниз по её оси: вставка-удлинитель 24 мм и пятка
	var bottom: Vector3 = (m.pos as Vector3) + down * float(m.half)
	var sleeve := WeaponModels._cbox(root, bottom + down * 0.012, Vector3(0.0295, 0.024, 0.045), _mat("polymer"), 0.003)
	sleeve.basis = tilt
	var base := WeaponModels._cbox(root, bottom + down * (0.024 + 0.0045), Vector3(0.031, 0.009, 0.05), _mat("polymer"), 0.003)
	base.basis = tilt


# ---------------------------------------------------------------- фонарь, ЛЦУ, сошки

## Узел тактического устройства: под рамкой (пистолет) или на боковой планке (длинные стволы).
static func _tac_body(root: Node3D, m: Dictionary) -> Node3D:
	var p: Vector3 = m.pos
	var t := Node3D.new()
	root.add_child(t)
	if bool(m.get("side", false)):
		var outer := _rail_side(root, p.x, p.y, p.z, 0.05)
		t.position = Vector3(outer + signf(p.x) * 0.011, p.y, p.z)
	else:
		WeaponModels._cbox(root, Vector3(p.x, p.y - 0.004, p.z), Vector3(0.022, 0.008, 0.03), _mat("anodized"), 0.001)
		# корпус касается хомута снизу (радиус корпуса 0.0105)
		t.position = Vector3(p.x, p.y - 0.008 - 0.0102, p.z + 0.004)
	return t


static func _flashlight(root: Node3D, m: Dictionary) -> void:
	var t := _tac_body(root, m)
	var al := _mat("anodized")
	WeaponModels._cyl(t, Vector3(0, 0, 0), 0.0105, 0.07, al)
	WeaponModels._cyl(t, Vector3(0, 0, 0.042), 0.0128, 0.016, al, 0.0132)
	WeaponModels._cyl(t, Vector3(0, 0, 0.0505), 0.0115, 0.001, _mat("light_lens"))
	WeaponModels._cyl(t, Vector3(0, 0, -0.037), 0.009, 0.006, _mat("rubber"))
	var light := SpotLight3D.new()
	light.name = "Flashlight"
	light.position = Vector3(0, 0, 0.052)
	light.rotation.y = PI
	light.light_color = Color(1.0, 0.96, 0.9)
	light.light_energy = 6.0
	light.spot_range = 30.0
	light.spot_angle = 22.0
	light.spot_attenuation = 0.8
	light.shadow_enabled = true
	light.light_volumetric_fog_energy = 2.0
	light.visible = false
	t.add_child(light)


static func _laser(root: Node3D, m: Dictionary) -> void:
	var t := _tac_body(root, m)
	var al := _mat("anodized")
	WeaponModels._cbox(t, Vector3(0, 0, 0), Vector3(0.024, 0.02, 0.046), al, 0.003)
	WeaponModels._cyl(t, Vector3(0, 0.003, 0.0235), 0.003, 0.002, _mat("reticle"))
	WeaponModels._cbox(t, Vector3(0, 0.011, -0.006), Vector3(0.01, 0.003, 0.014), _mat("rubber"), 0.001)
	var beam := MeshInstance3D.new()
	beam.name = "LaserBeam"
	var cm := CylinderMesh.new()
	cm.top_radius = 0.0012
	cm.bottom_radius = 0.0012
	cm.height = 40.0
	cm.radial_segments = 6
	beam.mesh = cm
	beam.material_override = _mat("laser_beam")
	beam.rotation.x = PI * 0.5
	beam.position = Vector3(0, 0.003, 0.0245 + 20.0)
	beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	beam.visible = false
	t.add_child(beam)


## Сошки: хомут под цевьём, ось, две сложенные вперёд ноги с резиновыми пятками.
static func _bipod(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var al := _mat("anodized")
	# хомут-скоба охватывает цевьё снизу и с боков (цевьё здесь ~0.04 шириной)
	WeaponModels._cbox(root, Vector3(0, p.y - 0.004, p.z), Vector3(0.048, 0.008, 0.03), al, 0.002)
	for sx in [-1.0, 1.0]:
		WeaponModels._cbox(root, Vector3(sx * 0.0225, p.y + 0.008, p.z), Vector3(0.004, 0.022, 0.03), al, 0.001)
	WeaponModels._cyl_x(root, Vector3(0, p.y - 0.012, p.z), 0.0045, 0.04, _mat("gunmetal"))
	for sx in [-1.0, 1.0]:
		var leg := WeaponModels._cyl(root, Vector3(sx * 0.013, p.y - 0.016, p.z + 0.085), 0.0042, 0.17, al)
		leg.rotation = Vector3(PI * 0.5 + deg_to_rad(-3.0), 0, 0)
		WeaponModels._sphere(root, Vector3(sx * 0.013, p.y - 0.02, p.z + 0.172), 0.006, _mat("rubber"))
