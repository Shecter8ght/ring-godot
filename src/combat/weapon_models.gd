class_name WeaponModels
extends RefCounted
## Процедурные модели оружия: пистолет, автомат, помповое ружьё, болтовая винтовка со
## прицелом, граната. Собраны из примитивов с фасками (фаска ловит блик — без неё коробка
## выглядит грубо), тонкие детали — отдельными узлами. Размеры реальные, в метрах.
##
## Система координат модели: начало — середина пистолетной рукояти (где держит рука),
## +Z — к дулу, +Y — вверх. В meta модели:
##   muzzle  (Vector3) — дульный срез, откуда вылетает трассер и вспышка;
##   sight_h (float)   — высота линии прицеливания над началом (для вида из прицела);
##   ads_z   (float)   — на каком расстоянии перед глазом держать рукоять в прицеле.
## Это запасной вариант по правилу проекта: модели из assets/ встанут по тем же meta.

const IDS := ["pistol", "rifle", "shotgun", "bolt", "grenade"]

static var _mats: Dictionary = {}
static var _meshes: Dictionary = {}


static func build(id: String) -> Node3D:
	var root := Node3D.new()
	root.name = "Weapon_" + id
	match id:
		"pistol":
			_pistol(root)
		"rifle":
			_rifle(root)
		"shotgun":
			_shotgun(root)
		"bolt":
			_bolt(root)
		"grenade":
			_grenade(root)
	for child in root.find_children("*", "MeshInstance3D", true, false):
		(child as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return root


# ---------------------------------------------------------------- пистолет
# Современный компактный пистолет: полимерная рамка, стальной затвор с насечками.

static func _pistol(r: Node3D) -> void:
	var steel := _mat("blued")
	var poly := _mat("polymer")
	# затвор
	_cbox(r, Vector3(0, 0.058, 0.048), Vector3(0.027, 0.03, 0.188), steel, 0.004)
	# насечки на затворе сзади, по обе стороны
	for side in [-1.0, 1.0]:
		for i in range(7):
			_box(r, Vector3(side * 0.0137, 0.058, -0.03 + i * 0.0045), Vector3(0.0012, 0.022, 0.0018), _mat("dark"))
	# окно выброса гильзы — тёмная вставка справа
	_box(r, Vector3(0.0137, 0.064, 0.07), Vector3(0.0012, 0.012, 0.03), _mat("dark"))
	# ствол, чуть торчит из затвора
	_cyl(r, Vector3(0, 0.06, 0.145), 0.0062, 0.012, _mat("gunmetal"))
	_cyl(r, Vector3(0, 0.06, 0.1512), 0.0036, 0.001, _mat("bore"))
	# рамка с направляющей под фонарь
	_cbox(r, Vector3(0, 0.032, 0.058), Vector3(0.025, 0.022, 0.15), poly, 0.004)
	for i in range(3):
		_box(r, Vector3(0, 0.0205, 0.085 + i * 0.012), Vector3(0.02, 0.002, 0.005), poly)
	# рукоять с наклоном и текстурой-«пупырками»
	var grip := _cbox(r, Vector3(0, -0.018, -0.004), Vector3(0.029, 0.105, 0.046), poly, 0.006)
	grip.rotation.x = deg_to_rad(-18.0)
	for i in range(5):
		var g := _box(r, Vector3(0, -0.04 + i * 0.016, -0.016 + i * 0.005), Vector3(0.0296, 0.006, 0.02), _mat("polymer_grip"))
		g.rotation.x = deg_to_rad(-18.0)
	# пятка магазина
	var base := _cbox(r, Vector3(0, -0.073, -0.022), Vector3(0.031, 0.009, 0.05), poly, 0.003)
	base.rotation.x = deg_to_rad(-18.0)
	# спусковая скоба — тор, вытянутый вперёд
	# тор лежит в XZ; поворот вокруг Z ставит его в вертикальную плоскость вдоль ствола
	var guard := _torus(r, Vector3(0, 0.008, 0.032), 0.013, 0.0165, poly)
	guard.rotation = Vector3(0, 0, PI * 0.5)
	guard.scale = Vector3(1.0, 1.0, 1.35)
	# спусковой крючок
	var trig := _cbox(r, Vector3(0, 0.01, 0.027), Vector3(0.006, 0.02, 0.005), steel, 0.0015)
	trig.rotation.x = deg_to_rad(12.0)
	# прицельные: мушка и целик с прорезью, белые точки
	_cbox(r, Vector3(0, 0.0765, 0.132), Vector3(0.004, 0.007, 0.006), steel, 0.001)
	_box(r, Vector3(0, 0.079, 0.1325), Vector3(0.0022, 0.0022, 0.0062), _mat("dot"))
	for side in [-1.0, 1.0]:
		_cbox(r, Vector3(side * 0.0055, 0.0765, -0.036), Vector3(0.006, 0.007, 0.008), steel, 0.001)
	r.set_meta("muzzle", Vector3(0, 0.06, 0.152))
	r.set_meta("sight_h", 0.079)
	r.set_meta("ads_z", 0.36)


# ---------------------------------------------------------------- автомат
# Автомат калашниковского типа: штампованная ствольная коробка, деревянные цевьё и приклад,
# изогнутый магазин из сегментов, газовая трубка, дульный тормоз.

static func _rifle(r: Node3D) -> void:
	var steel := _mat("blued")
	var gm := _mat("gunmetal")
	var wood := _mat("wood_red")
	# ствольная коробка и крышка
	_cbox(r, Vector3(0, 0.042, 0.075), Vector3(0.043, 0.055, 0.29), steel, 0.004)
	var cover := _cyl(r, Vector3(0, 0.07, 0.065), 0.0205, 0.25, steel)
	cover.scale = Vector3(1.0, 0.45, 1.0)
	# рёбра жёсткости на крышке
	for i in range(3):
		_box(r, Vector3(0, 0.08, -0.02 + i * 0.07), Vector3(0.034, 0.002, 0.004), gm)
	# рукоятка затворной рамы справа
	_cyl_x(r, Vector3(0.032, 0.058, 0.17), 0.0045, 0.022, gm)
	_sphere(r, Vector3(0.044, 0.058, 0.17), 0.006, gm)
	# предохранитель-переводчик — длинная пластина справа
	_cbox(r, Vector3(0.0225, 0.05, 0.045), Vector3(0.002, 0.012, 0.09), gm, 0.001)
	# ствол, газовая трубка, газовый блок
	_cyl(r, Vector3(0, 0.052, 0.22 + 0.19), 0.0085, 0.38, gm)
	_cyl(r, Vector3(0, 0.077, 0.215 + 0.13), 0.0105, 0.23, steel)
	_cbox(r, Vector3(0, 0.066, 0.465), Vector3(0.022, 0.04, 0.03), steel, 0.003)
	# цевьё: нижняя накладка расширяется к газовому блоку, верхняя — тонкая, над трубкой
	_sweep(r, [Vector3(0, 0.046, 0.232), Vector3(0, 0.044, 0.33), Vector3(0, 0.043, 0.41)] as Array[Vector3],
		[Vector2(0.044, 0.036), Vector2(0.049, 0.043), Vector2(0.047, 0.042)] as Array[Vector2], wood)
	_sweep(r, [Vector3(0, 0.084, 0.245), Vector3(0, 0.085, 0.385)] as Array[Vector3],
		[Vector2(0.029, 0.017), Vector2(0.031, 0.018)] as Array[Vector2], wood, 0.45)
	# колодка мушки и мушка в «ушах»
	_cbox(r, Vector3(0, 0.068, 0.555), Vector3(0.018, 0.028, 0.022), steel, 0.002)
	_box(r, Vector3(0, 0.089, 0.555), Vector3(0.0022, 0.016, 0.003), steel)
	for side in [-1.0, 1.0]:
		_cbox(r, Vector3(side * 0.007, 0.088, 0.555), Vector3(0.002, 0.018, 0.012), steel, 0.0006)
	# дульный тормоз со скосом и окнами
	_cyl(r, Vector3(0, 0.052, 0.605), 0.0115, 0.06, steel)
	for i in range(2):
		_box(r, Vector3(0, 0.052, 0.595 + i * 0.02), Vector3(0.0235, 0.005, 0.008), _mat("bore"))
	_cyl(r, Vector3(0, 0.052, 0.6355), 0.006, 0.001, _mat("bore"))
	# целик на коробке
	_cbox(r, Vector3(0, 0.085, 0.2), Vector3(0.028, 0.012, 0.05), steel, 0.002)
	_cbox(r, Vector3(0, 0.0905, 0.2), Vector3(0.024, 0.005, 0.036), gm, 0.001)
	# магазин: одна гладкая дуга вперёд, чуть сужается книзу, ребро жёсткости по бокам
	var mp: Array[Vector3] = []
	var ms: Array[Vector2] = []
	var q := Vector3(0, 0.02, 0.128)
	var ang := 0.0
	for i in range(9):
		mp.append(q)
		ms.append(Vector2(0.024, 0.056 - i * 0.0012))
		q += Vector3(0, -cos(ang), sin(ang)) * 0.024
		ang += deg_to_rad(4.2)
	_sweep(r, mp, ms, _mat("polymer_plum"), 0.2)
	var rp: Array[Vector3] = []
	var rs: Array[Vector2] = []
	for i in range(1, mp.size() - 1):
		rp.append(mp[i])
		rs.append(Vector2(0.0262, 0.008))
	_sweep(r, rp, rs, _mat("polymer_plum"), 0.3)
	# пистолетная рукоять
	var grip := _cbox(r, Vector3(0, -0.02, -0.008), Vector3(0.03, 0.095, 0.042), _mat("polymer_plum"), 0.006)
	grip.rotation.x = deg_to_rad(-16.0)
	# спусковая скоба и крючок
	_cbox(r, Vector3(0, -0.004, 0.048), Vector3(0.012, 0.004, 0.07), steel, 0.0012)
	_cbox(r, Vector3(0, 0.005, 0.081), Vector3(0.012, 0.018, 0.004), steel, 0.0012)
	var trig := _cbox(r, Vector3(0, 0.008, 0.047), Vector3(0.006, 0.02, 0.005), steel, 0.0015)
	trig.rotation.x = deg_to_rad(10.0)
	# приклад: узкая шейка у коробки, плавно раздаётся и опускается к затыльнику
	_cheek(_sweep(r, [Vector3(0, 0.04, -0.07), Vector3(0, 0.03, -0.13), Vector3(0, 0.016, -0.22), Vector3(0, 0.0, -0.333)] as Array[Vector3],
		[Vector2(0.034, 0.042), Vector2(0.035, 0.05), Vector2(0.039, 0.078), Vector2(0.041, 0.104)] as Array[Vector2], wood, 0.28))
	_cheek(_sweep(r, [Vector3(0, -0.0005, -0.333), Vector3(0, -0.001, -0.342)] as Array[Vector3],
		[Vector2(0.043, 0.107), Vector2(0.043, 0.107)] as Array[Vector2], steel, 0.25))
	# антабка
	_torus(r, Vector3(0, -0.035, -0.2), 0.004, 0.0065, gm).rotation.z = PI * 0.5
	r.set_meta("muzzle", Vector3(0, 0.052, 0.637))
	r.set_meta("sight_h", 0.091)
	r.set_meta("ads_z", 0.3)


# ---------------------------------------------------------------- дробовик
# Помповое ружьё: воронёная коробка, ствол и подствольный магазин, рифлёное цевьё, мушка-бусина.

static func _shotgun(r: Node3D) -> void:
	var steel := _mat("blued")
	var gm := _mat("gunmetal")
	var wood := _mat("wood_walnut")
	_cbox(r, Vector3(0, 0.045, 0.07), Vector3(0.042, 0.064, 0.2), steel, 0.005)
	# окно выброса справа и затворная задержка
	_box(r, Vector3(0.0212, 0.055, 0.1), Vector3(0.001, 0.022, 0.06), _mat("dark"))
	_cbox(r, Vector3(-0.0215, 0.035, 0.02), Vector3(0.003, 0.008, 0.012), gm, 0.001)
	# ствол с вентилируемой планкой
	_cyl(r, Vector3(0, 0.064, 0.17 + 0.25), 0.0105, 0.5, steel)
	_cyl(r, Vector3(0, 0.064, 0.6705), 0.0072, 0.001, _mat("bore"))
	_box(r, Vector3(0, 0.0765, 0.42), Vector3(0.006, 0.002, 0.48), steel)
	for i in range(12):
		_box(r, Vector3(0, 0.0735, 0.2 + i * 0.04), Vector3(0.004, 0.004, 0.006), steel)
	_sphere(r, Vector3(0, 0.08, 0.66), 0.0028, _mat("brass"))
	# подствольный магазин и хомут
	_cyl(r, Vector3(0, 0.036, 0.17 + 0.21), 0.0115, 0.42, steel)
	_cbox(r, Vector3(0, 0.05, 0.585), Vector3(0.024, 0.042, 0.016), steel, 0.003)
	_cyl(r, Vector3(0, 0.036, 0.597), 0.0125, 0.012, gm)
	# цевьё с кольцевыми канавками
	_cyl(r, Vector3(0, 0.036, 0.33), 0.022, 0.16, wood)
	for i in range(7):
		_cyl(r, Vector3(0, 0.036, 0.265 + i * 0.022), 0.02205, 0.0022, _mat("wood_dark"))
	# шейка ложи опускается под руку и плавно переходит в приклад
	_cheek(_sweep(r, [Vector3(0, 0.04, -0.025), Vector3(0, 0.022, -0.075), Vector3(0, 0.006, -0.125), Vector3(0, -0.012, -0.2), Vector3(0, -0.024, -0.3)] as Array[Vector3],
		[Vector2(0.034, 0.05), Vector2(0.031, 0.046), Vector2(0.034, 0.058), Vector2(0.039, 0.09), Vector2(0.042, 0.112)] as Array[Vector2], wood, 0.3))
	_cheek(_sweep(r, [Vector3(0, -0.0245, -0.3), Vector3(0, -0.025, -0.318)] as Array[Vector3],
		[Vector2(0.044, 0.114), Vector2(0.044, 0.114)] as Array[Vector2], _mat("rubber"), 0.3))
	# спусковая скоба и крючок
	_cbox(r, Vector3(0, 0.004, 0.035), Vector3(0.012, 0.004, 0.06), gm, 0.0012)
	_cbox(r, Vector3(0, 0.012, 0.063), Vector3(0.012, 0.018, 0.004), gm, 0.0012)
	var trig := _cbox(r, Vector3(0, 0.015, 0.035), Vector3(0.006, 0.02, 0.005), gm, 0.0015)
	trig.rotation.x = deg_to_rad(10.0)
	r.set_meta("muzzle", Vector3(0, 0.064, 0.671))
	r.set_meta("sight_h", 0.083)
	r.set_meta("ads_z", 0.3)


# ---------------------------------------------------------------- болтовая винтовка
# Снайперская болтовка: ореховое ложе с щекой, круглая ствольная коробка, тонкий
# сужающийся ствол, рукоять затвора с шаром, оптика с кольцами, барабанчиками и линзами.

static func _bolt(r: Node3D) -> void:
	var steel := _mat("blued")
	var gm := _mat("gunmetal")
	var wood := _mat("wood_walnut")
	# ложе одной линией: цевьё сужается к дулу, шейка под руку, приклад с гребнем
	_sweep(r, [Vector3(0, 0.03, 0.54), Vector3(0, 0.034, 0.3), Vector3(0, 0.036, 0.1), Vector3(0, 0.033, 0.04)] as Array[Vector3],
		[Vector2(0.034, 0.03), Vector2(0.042, 0.042), Vector2(0.046, 0.05), Vector2(0.044, 0.056)] as Array[Vector2], wood, 0.35)
	_sweep(r, [Vector3(0, 0.033, 0.04), Vector3(0, 0.012, -0.02), Vector3(0, 0.0, -0.075), Vector3(0, 0.004, -0.13), Vector3(0, 0.0, -0.22), Vector3(0, -0.006, -0.325)] as Array[Vector3],
		[Vector2(0.044, 0.056), Vector2(0.032, 0.05), Vector2(0.031, 0.05), Vector2(0.038, 0.09), Vector2(0.041, 0.118), Vector2(0.042, 0.124)] as Array[Vector2], wood, 0.3)
	# щека — отдельная подушка поверх гребня
	_sweep(r, [Vector3(0, 0.063, -0.12), Vector3(0, 0.07, -0.19), Vector3(0, 0.068, -0.27)] as Array[Vector3],
		[Vector2(0.034, 0.014), Vector2(0.036, 0.018), Vector2(0.036, 0.016)] as Array[Vector2], wood, 0.45)
	_sweep(r, [Vector3(0, -0.006, -0.325), Vector3(0, -0.006, -0.345)] as Array[Vector3],
		[Vector2(0.044, 0.126), Vector2(0.044, 0.126)] as Array[Vector2], _mat("rubber"), 0.3)
	# ствольная коробка и ствол, сужающийся к дулу, с дульным срезом
	_cyl(r, Vector3(0, 0.062, 0.1), 0.0165, 0.2, steel)
	var barrel := _cyl(r, Vector3(0, 0.062, 0.2 + 0.3), 0.0115, 0.6, steel, 0.0078)
	barrel.name = "Barrel"
	_cyl(r, Vector3(0, 0.062, 0.8005), 0.0045, 0.001, _mat("bore"))
	# рукоять затвора: стебель вправо-вниз и шар
	var bolt_stem := _cyl_x(r, Vector3(0.028, 0.058, 0.03), 0.0038, 0.032, gm)
	bolt_stem.rotation.z = PI * 0.5 + deg_to_rad(-25.0)
	_sphere(r, Vector3(0.043, 0.05, 0.03), 0.0085, gm)
	_cyl(r, Vector3(0, 0.062, -0.005), 0.012, 0.012, gm)
	# спуск
	_cbox(r, Vector3(0, 0.002, 0.04), Vector3(0.012, 0.004, 0.06), gm, 0.0012)
	_cbox(r, Vector3(0, 0.01, 0.068), Vector3(0.012, 0.018, 0.004), gm, 0.0012)
	var trig := _cbox(r, Vector3(0, 0.013, 0.04), Vector3(0.006, 0.018, 0.005), gm, 0.0015)
	trig.rotation.x = deg_to_rad(10.0)
	# оптический прицел: труба, объективный и окулярный колокола, барабанчики, кольца
	var sy := 0.118
	_cyl(r, Vector3(0, sy, 0.1), 0.0127, 0.2, _mat("scope"))
	_cyl(r, Vector3(0, sy, 0.235), 0.0127, 0.07, _mat("scope"), 0.0215)
	_cyl(r, Vector3(0, sy, 0.285), 0.0215, 0.03, _mat("scope"))
	_cyl(r, Vector3(0, sy, -0.005), 0.0185, 0.05, _mat("scope"), 0.0127)
	_cyl(r, Vector3(0, sy, -0.045), 0.0185, 0.03, _mat("scope"))
	_cyl(r, Vector3(0, sy, 0.3002), 0.0195, 0.001, _mat("lens"))
	_cyl(r, Vector3(0, sy, -0.0602), 0.016, 0.001, _mat("lens"))
	# барабанчики поправок сверху и справа, с рисками
	_cyl(r, Vector3(0, sy + 0.021, 0.1), 0.0105, 0.016, _mat("scope"), 0.0105).rotation = Vector3.ZERO
	_cyl_x(r, Vector3(0.021, sy, 0.1), 0.0105, 0.016, _mat("scope"))
	_box(r, Vector3(0, sy + 0.0292, 0.1), Vector3(0.002, 0.0004, 0.012), _mat("dot"))
	# кольца и основания
	for z in [0.03, 0.17]:
		_torus(r, Vector3(0, sy, z), 0.0127, 0.0158, gm).rotation.x = PI * 0.5
		_cbox(r, Vector3(0, 0.086, z), Vector3(0.018, 0.034, 0.012), gm, 0.002)
	r.set_meta("muzzle", Vector3(0, 0.062, 0.801))
	r.set_meta("sight_h", sy)
	r.set_meta("ads_z", 0.13)


# ---------------------------------------------------------------- граната
# Оборонительная граната: рубчатый корпус оливкового цвета, запал, спусковой рычаг и кольцо с чекой.

static func _grenade(r: Node3D) -> void:
	var olive := _mat("olive")
	# корпус — эллипсоид: всё рубчатое — внутри узла со сжатием по Y, так рёбра лежат по поверхности
	var shell := Node3D.new()
	shell.scale = Vector3(1.0, 1.18, 1.0)
	r.add_child(shell)
	_sphere(shell, Vector3.ZERO, 0.03, olive)
	# насечка «ананаса»: пояски и меридианы — тонкие торы, чуть утопленные в корпус
	for i in range(5):
		var y := -0.02 + i * 0.01
		var rr := sqrt(0.03 * 0.03 - y * y)
		_torus(shell, Vector3(0, y, 0), rr - 0.0011, rr + 0.0009, _mat("olive_dark"))
	for i in range(4):
		var mer := _torus(shell, Vector3.ZERO, 0.0291, 0.0311, _mat("olive_dark"))
		mer.rotation = Vector3(PI * 0.5, i * PI / 4.0, 0)
	# запал
	# запал вертикальный — _cyl кладёт цилиндр вдоль Z, возвращаем по Y
	_cyl(r, Vector3(0, 0.039, 0), 0.0095, 0.014, _mat("gunmetal")).rotation = Vector3.ZERO
	_cyl(r, Vector3(0, 0.048, 0), 0.0075, 0.006, _mat("gunmetal")).rotation = Vector3.ZERO
	# спусковой рычаг вдоль бока — три изогнутых сегмента
	var lever := _mat("steel_light")
	var seg1 := _cbox(r, Vector3(0.012, 0.05, 0), Vector3(0.016, 0.0018, 0.012), lever, 0.0006)
	seg1.rotation.z = deg_to_rad(-12.0)
	var seg2 := _cbox(r, Vector3(0.0235, 0.036, 0), Vector3(0.0018, 0.026, 0.011), lever, 0.0006)
	seg2.rotation.z = deg_to_rad(-12.0)
	var seg3 := _cbox(r, Vector3(0.03, 0.014, 0), Vector3(0.0018, 0.022, 0.01), lever, 0.0006)
	seg3.rotation.z = deg_to_rad(-4.0)
	# кольцо чеки
	var ring := _torus(r, Vector3(-0.016, 0.05, 0.0), 0.0085, 0.0102, lever)
	ring.rotation.x = PI * 0.5
	r.set_meta("muzzle", Vector3(0, 0.05, 0))
	r.set_meta("sight_h", 0.0)
	r.set_meta("ads_z", 0.3)


# ---------------------------------------------------------------- примитивы

## Коробка с фаской b: ловит блик на рёбрах — главное, что отличает «аккуратное» от «кубиков».
static func _cbox(parent: Node3D, at: Vector3, size: Vector3, mat: Material, b: float) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = chamfer_box(size, b)
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


static func _box(parent: Node3D, at: Vector3, size: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Цилиндр вдоль Z (ствол); top_r — радиус у дула, если конус.
static func _cyl(parent: Node3D, at: Vector3, r: float, length: float, mat: Material, top_r: float = -1.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var key := "cyl:%.4f:%.4f:%.4f" % [r, length, top_r]
	if not _meshes.has(key):
		var cm := CylinderMesh.new()
		cm.bottom_radius = r
		cm.top_radius = r if top_r < 0.0 else top_r
		cm.height = length
		cm.radial_segments = 28
		cm.rings = 1
		_meshes[key] = cm
	mi.mesh = _meshes[key]
	mi.rotation.x = PI * 0.5
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Цилиндр вдоль X (поперечные оси, барабанчики сбоку).
static func _cyl_x(parent: Node3D, at: Vector3, r: float, length: float, mat: Material) -> MeshInstance3D:
	var mi := _cyl(parent, at, r, length, mat)
	mi.rotation = Vector3(0, 0, PI * 0.5)
	return mi


static func _sphere(parent: Node3D, at: Vector3, r: float, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var key := "sph:%.4f" % r
	if not _meshes.has(key):
		var sm := SphereMesh.new()
		sm.radius = r
		sm.height = r * 2.0
		sm.radial_segments = 24
		sm.rings = 12
		_meshes[key] = sm
	mi.mesh = _meshes[key]
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Тор в плоскости XZ; поворачивать узел, чтобы положить в нужную плоскость.
static func _torus(parent: Node3D, at: Vector3, inner: float, outer: float, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var key := "tor:%.4f:%.4f" % [inner, outer]
	if not _meshes.has(key):
		var tm := TorusMesh.new()
		tm.inner_radius = inner
		tm.outer_radius = outer
		tm.rings = 28
		tm.ring_segments = 10
		_meshes[key] = tm
	mi.mesh = _meshes[key]
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Деталь «за щекой» (приклад, затыльник): в виде от первого лица её не видно — она под
## щекой и у плеча, а без этого флага приклад заслоняет низ экрана вдоль прицельной линии.
static func _cheek(mi: MeshInstance3D) -> MeshInstance3D:
	mi.set_meta("hide_ads", true)
	return mi


## Протяжка восьмиугольного сечения (прямоугольник со скошенными углами) по пути в плоскости YZ.
## pts — центры сечений, sizes — (ширина по X, толщина поперёк пути). Так делаются приклады,
## цевья, изогнутый магазин: плавное сужение и изгиб вместо ступенек из коробок.
static func _sweep(parent: Node3D, pts: Array[Vector3], sizes: Array[Vector2], mat: Material, chamfer: float = 0.3) -> MeshInstance3D:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings: Array = []
	for i in range(pts.size()):
		var t: Vector3
		if i == 0:
			t = pts[1] - pts[0]
		elif i == pts.size() - 1:
			t = pts[i] - pts[i - 1]
		else:
			t = pts[i + 1] - pts[i - 1]
		t = t.normalized()
		var u := t.cross(Vector3.RIGHT).normalized()
		var hw := sizes[i].x * 0.5
		var hh := sizes[i].y * 0.5
		var c := minf(hw, hh) * chamfer * 2.0
		var ring: Array[Vector3] = []
		for q: Vector2 in [Vector2(hw, hh - c), Vector2(hw - c, hh), Vector2(-hw + c, hh), Vector2(-hw, hh - c),
				Vector2(-hw, -hh + c), Vector2(-hw + c, -hh), Vector2(hw - c, -hh), Vector2(hw, -hh + c)]:
			ring.append(pts[i] + Vector3.RIGHT * q.x + u * q.y)
		rings.append(ring)
	for i in range(pts.size() - 1):
		var a: Array[Vector3] = rings[i]
		var b: Array[Vector3] = rings[i + 1]
		var mid := (pts[i] + pts[i + 1]) * 0.5
		for k in range(8):
			var k2 := (k + 1) % 8
			var fc := (a[k] + a[k2] + b[k] + b[k2]) * 0.25
			var n := (b[k] - a[k]).cross(a[k2] - a[k]).normalized()
			if n.dot(fc - mid) < 0.0:
				n = -n
			_tri(st, a[k], a[k2], b[k2], n)
			_tri(st, a[k], b[k2], b[k], n)
	for e in [0, pts.size() - 1]:
		var ring: Array[Vector3] = rings[e]
		var n := (pts[e] - pts[1 if e == 0 else e - 1]).normalized()
		for k in range(1, 7):
			_tri(st, ring[0], ring[k], ring[k + 1], n)
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Меш коробки с фаской: 6 граней, 12 скосов по рёбрам, 8 треугольников по углам.
static func chamfer_box(size: Vector3, b: float) -> ArrayMesh:
	var key := "cb:%.4f:%.4f:%.4f:%.4f" % [size.x, size.y, size.z, b]
	if _meshes.has(key):
		return _meshes[key]
	var h := size * 0.5
	b = minf(b, minf(h.x, minf(h.y, h.z)) * 0.9)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	# P(s, a): угол-знаки s, координата по оси a — полная, по остальным — утоплена на фаску.
	var p := func(s: Vector3, a: int) -> Vector3:
		var v := Vector3(s.x * (h.x - b), s.y * (h.y - b), s.z * (h.z - b))
		v[a] = s[a] * h[a]
		return v
	var signs: Array[Vector3] = []
	for sx in [-1.0, 1.0]:
		for sy in [-1.0, 1.0]:
			for sz in [-1.0, 1.0]:
				signs.append(Vector3(sx, sy, sz))
	# грани
	for a in range(3):
		for sa in [-1.0, 1.0]:
			var pts: Array[Vector3] = []
			for s in signs:
				if s[a] == sa:
					pts.append(p.call(s, a))
			_convex_quad(st, pts, _axis(a) * sa)
	# скосы по рёбрам
	for a in range(3):
		for c in range(a + 1, 3):
			for sa in [-1.0, 1.0]:
				for sc in [-1.0, 1.0]:
					var pts: Array[Vector3] = []
					for s in signs:
						if s[a] == sa and s[c] == sc:
							pts.append(p.call(s, a))
							pts.append(p.call(s, c))
					_convex_quad(st, pts, (_axis(a) * sa + _axis(c) * sc).normalized())
	# углы
	for s in signs:
		_tri(st, p.call(s, 0), p.call(s, 1), p.call(s, 2), s.normalized())
	var mesh := st.commit()
	_meshes[key] = mesh
	return mesh


static func _axis(a: int) -> Vector3:
	return [Vector3.RIGHT, Vector3.UP, Vector3.BACK][a]


## Четыре точки выпуклого многоугольника в одной плоскости — упорядочить по кругу и разбить.
static func _convex_quad(st: SurfaceTool, pts: Array[Vector3], n: Vector3) -> void:
	var c := Vector3.ZERO
	for q in pts:
		c += q
	c /= pts.size()
	var u := (pts[0] - c).normalized()
	var w := n.cross(u)
	pts.sort_custom(func(a: Vector3, bb: Vector3) -> bool:
		return atan2((a - c).dot(w), (a - c).dot(u)) < atan2((bb - c).dot(w), (bb - c).dot(u)))
	for i in range(1, pts.size() - 1):
		_tri(st, pts[0], pts[i], pts[i + 1], n)


## Треугольник наружу: Godot рисует лицом грани, обходимые по часовой, если смотреть снаружи.
static func _tri(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, n: Vector3) -> void:
	if (b - a).cross(c - a).dot(n) > 0.0:
		var t := b
		b = c
		c = t
	st.set_normal(n)
	st.add_vertex(a)
	st.set_normal(n)
	st.add_vertex(b)
	st.set_normal(n)
	st.add_vertex(c)


# ---------------------------------------------------------------- материалы

static func _mat(id: String) -> StandardMaterial3D:
	if _mats.has(id):
		return _mats[id]
	var m := StandardMaterial3D.new()
	match id:
		"blued":
			m.albedo_color = Color(0.12, 0.125, 0.135)
			m.metallic = 0.85
			m.roughness = 0.36
		"gunmetal":
			m.albedo_color = Color(0.2, 0.2, 0.21)
			m.metallic = 0.8
			m.roughness = 0.45
		"steel_light":
			m.albedo_color = Color(0.55, 0.55, 0.53)
			m.metallic = 0.9
			m.roughness = 0.3
		"dark":
			m.albedo_color = Color(0.02, 0.02, 0.022)
			m.roughness = 0.6
		"bore":
			m.albedo_color = Color(0.0, 0.0, 0.0)
			m.roughness = 1.0
		"polymer":
			m.albedo_color = Color(0.07, 0.07, 0.075)
			m.roughness = 0.62
		"polymer_grip":
			m.albedo_color = Color(0.055, 0.055, 0.06)
			m.roughness = 0.85
		"polymer_plum":
			m.albedo_color = Color(0.2, 0.09, 0.06)
			m.roughness = 0.55
		"wood_red":
			m.albedo_color = Color(0.3, 0.12, 0.055)
			m.roughness = 0.45
			m.clearcoat_enabled = true
			m.clearcoat = 0.25
			m.clearcoat_roughness = 0.45
		"wood_walnut":
			m.albedo_color = Color(0.22, 0.12, 0.06)
			m.roughness = 0.45
			m.clearcoat_enabled = true
			m.clearcoat = 0.3
			m.clearcoat_roughness = 0.4
		"wood_dark":
			m.albedo_color = Color(0.13, 0.06, 0.03)
			m.roughness = 0.6
		"rubber":
			m.albedo_color = Color(0.05, 0.05, 0.05)
			m.roughness = 0.9
		"brass":
			m.albedo_color = Color(0.85, 0.66, 0.3)
			m.metallic = 1.0
			m.roughness = 0.25
		"dot":
			m.albedo_color = Color(0.95, 0.95, 0.9)
			m.emission_enabled = true
			m.emission = Color(0.7, 1.0, 0.6)
			m.emission_energy_multiplier = 0.6
		"scope":
			m.albedo_color = Color(0.05, 0.05, 0.055)
			m.metallic = 0.5
			m.roughness = 0.4
		"lens":
			m.albedo_color = Color(0.12, 0.2, 0.3)
			m.metallic = 0.3
			m.roughness = 0.05
			m.emission_enabled = true
			m.emission = Color(0.15, 0.3, 0.45)
			m.emission_energy_multiplier = 0.4
		"olive":
			m.albedo_color = Color(0.24, 0.27, 0.16)
			m.roughness = 0.65
		"olive_dark":
			m.albedo_color = Color(0.17, 0.19, 0.11)
			m.roughness = 0.75
	# Поверхность: дерево и краска гранаты — фото-текстуры Poly Haven (CC0), трипланарно (у
	# процедурных мешей нет UV); сталь и полимер — тонкий процедурный микрорельеф.
	# Без assets/textures остаётся чистый цвет — игра обязана работать и так.
	match id:
		"wood_red":
			_photo(m, "sapele_veneer", 3.0, Color(0.62, 0.3, 0.19))
		"wood_walnut":
			_photo(m, "natural_walnut_veneer", 3.0, Color(0.42, 0.26, 0.15))
		"olive":
			_photo(m, "green_metal_rust", 9.0, Color(0.95, 1.0, 0.85))
		"blued", "gunmetal", "scope":
			_micro(m, 28.0, 0.35, 0.9)
		"polymer", "polymer_plum":
			_micro(m, 40.0, 0.6, 1.4)
		"polymer_grip", "rubber":
			_micro(m, 70.0, 1.0, 3.0)
	_mats[id] = m
	return m


static func _photo(m: StandardMaterial3D, tex_id: String, scale: float, tint: Color) -> void:
	var base := "res://assets/textures/%s/" % tex_id
	if not ResourceLoader.exists(base + "albedo.jpg"):
		return
	m.albedo_texture = load(base + "albedo.jpg")
	m.albedo_color = tint
	if ResourceLoader.exists(base + "arm.jpg"):
		var arm: Texture2D = load(base + "arm.jpg")
		m.roughness = 1.0
		m.roughness_texture = arm
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.ao_enabled = true
		m.ao_texture = arm
		m.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	if ResourceLoader.exists(base + "normal.jpg"):
		m.normal_enabled = true
		m.normal_texture = load(base + "normal.jpg")
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * scale
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC


## Микрорельеф: шум как карта нормалей — воронение и полимер перестают быть «пластиком из
## редактора», блик дробится. freq — частота шума, bump — сила, scale — плотность на метр/10.
static func _micro(m: StandardMaterial3D, scale: float, bump: float, freq: float) -> void:
	var nt := NoiseTexture2D.new()
	nt.width = 256
	nt.height = 256
	nt.seamless = true
	nt.as_normal_map = true
	nt.bump_strength = bump * 4.0
	var fn := FastNoiseLite.new()
	fn.noise_type = FastNoiseLite.TYPE_SIMPLEX
	fn.frequency = 0.05 * freq
	fn.fractal_octaves = 3
	nt.noise = fn
	m.normal_enabled = true
	m.normal_texture = nt
	m.normal_scale = bump
	m.uv1_triplanar = true
	m.uv1_scale = Vector3.ONE * scale
