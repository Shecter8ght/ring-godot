class_name WeaponMods
extends RefCounted
## Обвес на модели оружия. Точки крепления (сокеты) — в данных: data/weapons.json →
## models.<основа>.sockets (метры, оси модели: +Z к дулу, +Y вверх, −X — правая сторона стрелка;
## у планки — rail_z [от, до]); обвес — по своему виду (attach.look). Сокета нет — обвес не
## рисуется (характеристики работают). Сборка — дерево WeaponBuild: устройство встаёт в свой паз
## планки, переходник (кронштейн 45°, проставка, удлинитель, поворотный) даёт новую точку, на
## которую ставится следующее. Прицел — на планку (ставится, если её нет), линия прицеливания —
## через центр линзы; глушитель/компенсатор — на резьбу, дульный срез переезжает на торец;
## рукоятка — под цевьё; приклад, магазин — вместо штатных (помечены meta "part" и прячутся).
## Меняет meta модели: sight_h (основная линия прицеливания), sights {путь: {x, h, roll}}, muzzle,
## scoped. Фонари и ЛЦУ — узлы "Flashlight_<точка>" (SpotLight3D) и "LaserBeam_<точка>" с meta
## "mount": включает игрок (T — фонари, L — лазеры) по состоянию обвеса.

## Высота планки Пикатинни (основание + зубцы), м.
const RAIL_H := 0.006
## Профиль рефлектора: мягкое центральное пятно и слабая широкая периферия, без обрезанного круга.
const FLASHLIGHT_BEAM: Texture2D = preload("res://assets/textures/lights/flashlight_beam.tres")


## Сокет точки mount у основы model_key: словарь с Vector3 pos (из массива данных); {} — нет.
static func socket(model_key: String, mount: String) -> Dictionary:
	var sk: Dictionary = (WeaponDb.model(model_key).get("sockets", {}) as Dictionary).get(mount, {})
	if sk.is_empty():
		return {}
	var m := sk.duplicate(true)
	var p: Array = sk.get("pos", [0, 0, 0])
	m.pos = Vector3(float(p[0]), float(p[1]), float(p[2]))
	return m


## mods — путь точки → {id[, slot, flip, angle, light, laser]} (или просто id у старых записей);
## дерево и пазы — WeaponBuild. Ставится от родителя к детям: у точки оружия — от её сокета (на
## планке — со сдвигом по пазу), у точки переходника — от рамки, которую он даёт. Линия каждого
## прицела — в meta "sights" {ключ: {x, h, roll}}; основной (WeaponBuild.primary_key) — ещё и
## прежними sight_h / ocular / ads_z модели.
static func fit(root: Node3D, model_key: String, mods: Dictionary, lod: int = 0, weapon_id: String = "") -> void:
	var rig: WeaponRig = WeaponRig.find_on(root)
	if rig:
		rig.set_external_muzzle(false)
		rig.set_suppressed(false)
	var bare_muzzle: Variant = root.get_meta("muzzle", Vector3.ZERO)
	var main: String = WeaponBuild.primary_key(mods)
	# рамка установленного переходника в осях модели — от неё встают его дети
	var frames: Dictionary = {}
	var sights: Dictionary = {}
	var rail_tops: Dictionary = {}
	for key: String in WeaponBuild.sorted_keys(mods):
		var id := WeaponDb.mod_id(mods[key])
		var a := WeaponDb.attachment(id)
		if a.is_empty():
			continue
		var base: String = WeaponBuild.base_of(key)
		var top_level: bool = WeaponBuild.depth(key) == 0
		if top_level and String(a.get("look", "")) == "asset":
			if rig and rig.has_suppressor_part():
				rig.set_suppressed(true)
				# Срез на собственном глушителе ведёт сам риг — это не внешняя насадка.
				bare_muzzle = root.get_meta("muzzle", Vector3.ZERO)
			else:
				# Ассет может отсутствовать; обвес сохраняет читаемость на запасном пистолете.
				var fallback: Dictionary = socket(model_key, base)
				fallback["pos"] = root.get_meta("muzzle", Vector3.ZERO)
				fallback["mount"] = key
				fallback["bore_r"] = float(fallback.get("bore_r", a.get("bore_r_m", 0.0045)))
				var size: Array = a.get("size_m", [0.019, 0.175])
				_suppressor(root, fallback, float(size[0]), float(size[1]))
				root.set_meta("suppressor_installed", true)
			continue
		var m: Dictionary
		var frame := Transform3D.IDENTITY
		if top_level:
			m = socket(model_key, base)
			if m.is_empty():
				continue
			m["native_rail"] = m.has("rail_z") and not bool(m.get("rail", false))
			var p: Vector3 = m.pos
			p.z = WeaponBuild.placed_z(model_key, mods, key)
			# планка, которой у модели нет, рисуется один раз во всю длину — устройства встают на неё
			if bool(m.get("rail", false)) or float(m.get("riser", 0.0)) > 0.0:
				if not rail_tops.has(base):
					rail_tops[base] = _socket_rail(root, model_key, base)
				p.y = float(rail_tops[base])
				m["rail"] = false
				m["riser"] = 0.0
			m.pos = p
		else:
			var parent: String = WeaponBuild.parent_key(key)
			var g: Dictionary = WeaponBuild.geo(model_key, mods, key)
			if not frames.has(parent) or g.is_empty():
				continue
			var roll: float = deg_to_rad(WeaponBuild.point_roll(model_key, mods, key))
			frame = (frames[parent] as Transform3D) * Transform3D(Basis(Vector3(0, 0, 1), roll), Vector3.ZERO) * Transform3D(Basis.IDENTITY, g.pos)
			m = {"pos": Vector3(0, 0, WeaponBuild.placed_z(model_key, mods, key)), "rail": false, "riser": 0.0}
		m["mount"] = key
		m["att"] = a
		m["lod"] = lod
		if top_level:
			if rig and base == "muzzle" and bare_muzzle is Vector3:
				# Сокеты основы сняты с процедурной модели; на импортированной насадка встаёт на её срез.
				m.pos = bare_muzzle
			if key == "optic_primary":
				# прицел на планке — целик сложен: иначе торчит в нижней части окна прицела
				_hide_part(root, "rear_sight")
			if base == "muzzle":
				_hide_part(root, "muzzle_device")
			if base == "stock":
				_hide_part(root, "stock")
		var part: Node3D = Node3D.new()
		part.name = "Attachment_" + WeaponBuild.node_name(key)
		part.set_meta("condition_part", true)
		part.set_meta("mount", key)
		root.add_child(part)
		var optic: bool = WeaponDb.is_optic(id)
		var pivot: Node3D = null
		if key == "optic_offset":
			_offset_optic(part, m, a)
			sights[key] = part.get_meta("sight_offset", {})
		elif top_level and base in ["side_left", "side_right"] and optic:
			_side_optic(part, m, a)
			sights[key] = part.get_meta("sight_" + key, {})
		elif not (a.get("provides", {}) as Dictionary).is_empty():
			pivot = _pivot(part, _mount_frame(model_key, base, m, frame, top_level))
			var rolls: Dictionary = {}
			for point_name: Variant in a.provides:
				rolls[String(point_name)] = WeaponBuild.point_roll(model_key, mods, key + WeaponBuild.SEP + String(point_name))
			m["rolls"] = rolls
			_adapter(pivot, m, a)
			frames[key] = pivot.transform
		elif top_level and (not optic or key == main):
			# прежний путь: строитель в осях модели (основной прицел, дульное, рукоятка, фонарь…)
			_build_look(part, m, a)
		else:
			# дополнительный прицел или устройство на переходнике — в рамке своей точки; у рамки +Y —
			# от оружия наружу: прицел строится вверх, подвесное (рукоятка, фонарь) — вниз, поэтому разворот
			var xf: Transform3D = _mount_frame(model_key, base, m, frame, top_level)
			if not optic:
				xf = xf * Transform3D(Basis(Vector3(0, 0, 1), PI), Vector3.ZERO)
			pivot = _pivot(part, xf)
			var sub: Dictionary = m.duplicate(true)
			sub["pos"] = Vector3.ZERO
			sub["side"] = false
			# крупный прицел на угловом кронштейне — на своей проставке, дальше от основной оптики
			var raise: float = float(a.get("offset_raise_m", 0.0))
			if optic and not top_level and raise > 0.0 and not is_zero_approx(WeaponBuild.point_roll(model_key, mods, key)):
				WeaponModels._cbox(pivot, Vector3(0, raise * 0.5, 0), Vector3(0.022, raise, 0.032), _mat("anodized"), 0.0012)
				sub["pos"] = Vector3(0, raise, 0)
			_build_look(pivot, sub, a)
			if optic:
				var pt: Vector3 = pivot.transform * Vector3(0, float(pivot.get_meta("sight_h", 0.02)), 0)
				var up: Vector3 = pivot.transform.basis.y
				sights[key] = {"x": pt.x, "h": pt.y, "roll": atan2(-up.x, up.y)}
				if key == main:
					_primary_from_pivot(root, pivot, pt)
		if pivot and pivot.get_meta("asset_loaded", false):
			part.set_meta("asset_loaded", true)
		for meta: StringName in part.get_meta_list():
			if meta not in [&"condition_part", &"mount"]:
				root.set_meta(meta, part.get_meta(meta))
		for node: Node in part.find_children("*", "MeshInstance3D", true, false):
			var mesh: MeshInstance3D = node as MeshInstance3D
			var material: Material = mesh.get_active_material(0) if mesh.mesh and mesh.mesh.get_surface_count() > 0 else null
			# светящаяся метка прицела (её красит ПНВ и ведёт люфт) — тёплое свечение; голубоватое стекло
			# линзы оптики к меткам не относится (иначе линза становилась красным диском)
			var glow: Color = (material as StandardMaterial3D).emission if material is StandardMaterial3D and (material as StandardMaterial3D).emission_enabled else Color.BLACK
			if material is StandardMaterial3D and (material as StandardMaterial3D).emission_enabled and optic and glow.r >= glow.b:
				mesh.set_meta("reticle_dot", true)
				mesh.set_meta("mount", key)
	root.set_meta("frames", frames)
	Metka4Model.fit(root, model_key, mods, weapon_id)
	update_condition(root, mods)
	if rig and root.get_meta("muzzle", Vector3.ZERO) != bare_muzzle:
		# Процедурный глушитель или тормоз на модели без своей детали: дульный срез — от насадки,
		# риг не возвращает его на голый ствол при каждой позе.
		rig.set_external_muzzle(true)
	# основная линия прицеливания и остальные — для камеры (CameraRig выбирает по прицелу)
	# ось основного прицела вбок (ПСО на боковом креплении) — sight_x; у прочих прицелов 0
	var primary_line: Dictionary = {"x": float(root.get_meta("sight_x", 0.0)), "h": float(root.get_meta("sight_h", 0.0)), "roll": 0.0}
	root.set_meta("sight_primary", primary_line)
	sights["primary"] = primary_line
	root.set_meta("sights", sights)
	# рамки переходников — от них конструктор считает точки, которые они дают (point_frame)
	root.set_meta("frames", frames)


## Рамка точки key в осях модели root (после fit): начало — середина точки на поверхности планки
## (у планки — её середина, если устройство не стоит), +Y — от оружия, +Z — к дулу. Для занятой
## точки — там, где стоит устройство.
static func point_frame(root: Node3D, model_key: String, mods: Dictionary, key: String) -> Transform3D:
	var parent: String = WeaponBuild.parent_key(key)
	var base: String = WeaponBuild.base_of(key)
	var g: Dictionary = WeaponBuild.geo(model_key, mods, key)
	var z: float = WeaponBuild.placed_z(model_key, mods, key) if mods.has(key) else (float(g.rail[0]) + float(g.rail[1])) * 0.5 if WeaponBuild.is_rail(g) else float(g.get("z", 0.0))
	if parent == "":
		var sk: Dictionary = socket(model_key, base)
		if sk.is_empty():
			return Transform3D.IDENTITY
		var p: Vector3 = sk.pos
		p.y += float(sk.get("riser", 0.0)) + (RAIL_H if bool(sk.get("rail", false)) else 0.0)
		p.z = z
		return _mount_frame(model_key, base, {"pos": p}, Transform3D.IDENTITY, true)
	var frames: Dictionary = root.get_meta("frames", {})
	if not frames.has(parent) or g.is_empty():
		return Transform3D.IDENTITY
	var roll: float = deg_to_rad(WeaponBuild.point_roll(model_key, mods, key))
	return (frames[parent] as Transform3D) * Transform3D(Basis(Vector3(0, 0, 1), roll), Vector3.ZERO) * Transform3D(Basis.IDENTITY, g.pos) * Transform3D(Basis.IDENTITY, Vector3(0, 0, z))


## Концы планки точки key в осях модели ([] — точка без планки).
static func rail_ends(root: Node3D, model_key: String, mods: Dictionary, key: String) -> Array[Vector3]:
	var g: Dictionary = WeaponBuild.geo(model_key, mods, key)
	var out: Array[Vector3] = []
	if not WeaponBuild.is_rail(g):
		return out
	var probe: Dictionary = mods.duplicate()
	probe.erase(key)
	var xf: Transform3D = point_frame(root, model_key, probe, key)
	var mid: float = (float(g.rail[0]) + float(g.rail[1])) * 0.5
	out.append(xf * Vector3(0, 0, float(g.rail[0]) - mid))
	out.append(xf * Vector3(0, 0, float(g.rail[1]) - mid))
	return out


## Рамка устройства: у точки оружия — сокет (на боковой планке +Y смотрит наружу, под цевьём —
## вниз), у точки переходника — его рамка со сдвигом по пазу.
static func _mount_frame(model_key: String, base: String, m: Dictionary, frame: Transform3D, top_level: bool) -> Transform3D:
	if not top_level:
		return frame * Transform3D(Basis.IDENTITY, m.pos)
	var p: Vector3 = m.pos
	var roll: float = 0.0
	if bool(socket(model_key, base).get("side", false)):
		roll = -signf(p.x) * PI * 0.5
	elif base == "underbarrel":
		roll = PI
	return Transform3D(Basis(Vector3(0, 0, 1), roll), p)


static func _pivot(part: Node3D, xf: Transform3D) -> Node3D:
	var pivot: Node3D = Node3D.new()
	pivot.name = "Mount"
	pivot.transform = xf
	part.add_child(pivot)
	return pivot


## Основной прицел над проставкой: его линия, окуляр и вынос глаза — в осях модели.
static func _primary_from_pivot(root: Node3D, pivot: Node3D, line_point: Vector3) -> void:
	root.set_meta("sight_h", line_point.y)
	for flag: StringName in [&"scoped", &"ocular_r", &"lumar_reticle", &"reticle_tex", &"reticle_illum"]:
		if pivot.has_meta(flag):
			root.set_meta(flag, pivot.get_meta(flag))
	if pivot.has_meta("ocular"):
		var local: Vector3 = pivot.get_meta("ocular")
		var placed: Vector3 = pivot.transform * local
		root.set_meta("ocular", placed)
		if pivot.has_meta("ads_z"):
			root.set_meta("ads_z", float(pivot.get_meta("ads_z")) + local.z - placed.z)


## Планка (и проставка), которой у модели нет: во всю длину точки. Возвращает высоту верха.
static func _socket_rail(root: Node3D, model_key: String, base: String) -> float:
	var sk: Dictionary = socket(model_key, base)
	var g: Dictionary = WeaponBuild.geo(model_key, {}, base)
	var p: Vector3 = sk.pos
	var rail: Array = g.get("rail", [])
	var z0: float = float(rail[0]) if not rail.is_empty() else p.z - 0.05
	var z1: float = float(rail[1]) if not rail.is_empty() else p.z + 0.05
	var y: float = p.y
	var riser: float = float(sk.get("riser", 0.0))
	if riser > 0.0:
		# проставка повторяет крышку: ложится на рёбра, шире планки
		WeaponModels._cbox(root, Vector3(0, y + riser * 0.5, (z0 + z1) * 0.5), Vector3(0.026, riser, z1 - z0), _mat("anodized"), 0.0012)
		y += riser
	if bool(sk.get("rail", false)):
		y = _rail_z(root, y, (z0 + z1) * 0.5, z1 - z0)
	return y


# ---------------------------------------------------------------- переходники

## Переходник по виду (attach.look) в своей рамке: +Y — от оружия, начало — середина зажима на
## поверхности планки. Точки, которые он даёт, — по данным provides (WeaponBuild.geo), крен —
## m.rolls (сторона и угол из записи). Пока процедурный; модель из Blender — attach.asset.
static func _adapter(pivot: Node3D, m: Dictionary, a: Dictionary) -> void:
	var al := _mat("anodized")
	var clamp: float = float(a.get("clamp_m", WeaponBuild.DEFAULT_CLAMP))
	var spec: Dictionary = (a.get("provides", {}) as Dictionary).get("rail", {})
	var p: Array = spec.get("pos", [0, 0, 0])
	var top := Vector3(float(p[0]), float(p[1]), float(p[2]))
	var roll: float = deg_to_rad(float((m.get("rolls", {}) as Dictionary).get("rail", 0.0)))
	var path: String = String(a.get("asset", ""))
	if path != "" and ResourceLoader.exists(path, "PackedScene"):
		# модель из Blender (tools/build_adapters.py): поворотная часть — узел Arm, вокруг оси планки
		var model: Node3D = (load(path) as PackedScene).instantiate() as Node3D
		model.name = "Adapter"
		pivot.add_child(model)
		var arm_node: Node3D = model.find_child("Arm", true, false) as Node3D
		if arm_node:
			arm_node.rotation.z = roll
		return
	# запасной вид без assets/: зажим Пикатинни — колодка с губками по бокам и винт
	WeaponModels._cbox(pivot, Vector3(0, 0.004, 0), Vector3(0.024, 0.008, clamp), al, 0.0012)
	for sx: float in [-1.0, 1.0]:
		WeaponModels._cbox(pivot, Vector3(sx * 0.0115, -0.002, 0), Vector3(0.003, 0.008, clamp), al, 0.0006)
	WeaponModels._cyl_x(pivot, Vector3(0.0145, 0.0, 0), 0.0035, 0.004, _mat("gunmetal"))
	match String(a.get("look", "")):
		"mount_offset45", "mount_adjustable":
			var arm := Node3D.new()
			arm.rotation.z = roll
			pivot.add_child(arm)
			if String(a.look) == "mount_adjustable":
				# поворотная шайба
				WeaponModels._cyl(arm, Vector3(0, 0.009, 0), 0.011, 0.004, _mat("gunmetal")).rotation = Vector3.ZERO
			var h: float = top.y
			WeaponModels._cbox(arm, Vector3(0, h * 0.5, 0), Vector3(0.016, h, 0.02), al, 0.0015)
			# площадка под мини-коллиматор
			WeaponModels._cbox(arm, Vector3(0, h - 0.002, 0), Vector3(0.024, 0.004, 0.034), al, 0.0008)
		"mount_riser":
			var body_h: float = top.y - RAIL_H
			WeaponModels._cbox(pivot, Vector3(0, body_h * 0.5, 0), Vector3(0.022, body_h, clamp), al, 0.0015)
			var rail: Array = spec.get("rail_z", [-clamp * 0.5, clamp * 0.5])
			_rail_z(pivot, body_h, (float(rail[0]) + float(rail[1])) * 0.5, float(rail[1]) - float(rail[0]))
		"mount_rail_ext":
			var rail2: Array = spec.get("rail_z", [-0.02, 0.1])
			_rail_z(pivot, top.y - RAIL_H, top.z + (float(rail2[0]) + float(rail2[1])) * 0.5, float(rail2[1]) - float(rail2[0]))
		"mount_pm":
			# крепление к затвору ПМ (ЗОРИН К-1): седло на затворе и короткая планка над ним
			var rail3: Array = spec.get("rail_z", [-0.027, 0.027])
			var length: float = float(rail3[1]) - float(rail3[0])
			WeaponModels._cbox(pivot, Vector3(0, top.y * 0.5 - RAIL_H * 0.5, top.z), Vector3(0.026, maxf(top.y - RAIL_H, 0.002), length * 0.4), al, 0.001)
			_rail_z(pivot, top.y - RAIL_H, top.z + (float(rail3[0]) + float(rail3[1])) * 0.5, length)


static func _build_look(root: Node3D, m: Dictionary, a: Dictionary) -> void:
	# готовая модель обвеса (tools/prepare_veras_attachments.py); нет файла — процедурный вид ниже
	if a.has("model") and _model_part(root, m, a):
		return
	match String(a.get("look", "")):
		"red_dot":
			_red_dot(root, m)
		"holo":
			if not _lumar(root, m, a):
				_holo(root, m)
		"rmr":
			_rmr(root, m)
		"scope4x":
			_scope4x(root, m)
		"lpvo":
			_scope4x(root, m, 1.25, 1.1)
		"scope8x":
			_scope4x(root, m, 1.55, 1.35)
		"suppressor":
			var sz: Array = a.get("size_m", [0.019, 0.175])
			_suppressor(root, m, float(sz[0]), float(sz[1]))
		"compensator", "flash_hider":
			_compensator(root, m)
		"grip_vertical":
			_scaled(root, m, float(a.get("scale", 1.0)), _grip_vertical)
		"grip_angled":
			_scaled(root, m, float(a.get("scale", 1.0)), _grip_angled)
		"grip_offset":
			_grip_offset(root, m)
		"stock_tele":
			_stock_tele(root, m)
		"flashlight":
			_flashlight(root, m, a, 1.0)
		"flashlight_hp":
			_flashlight(root, m, a, 1.3)
		"laser":
			_laser(root, m)
		"combo":
			_combo(root, m, a)
		"bipod":
			_bipod(root, m)


## Обвес готовой моделью: a.model = {scene, offset [x, y, z] от точки, length_m — длина дульной насадки,
## sight_h — у прицела высота центра линзы над началом модели (линия прицеливания); у оптики ещё ocular [x, y, z] —
## центр задней линзы в осях модели, ocular_r — её радиус, eye_relief — вынос глаза, м, sight_x — ось вбок от начала
## (ПСО на боковом «ласточкином хвосте» ВСС-М: ось левее ствола) — по ним камера показывает картинку в окуляре}.
## Сетки Body / Body_LOD1 (вид со стороны), карты лежат рядом с моделью:
## <имя>_100_{base_color,roughness,metallic,normal}.png (вид один при любой прочности, решение владельца
## 2026-10-19), жировые следы рук — <имя>_100_coat.png, если есть. Начало модели — место посадки:
## у рукоятки — нижняя плоскость планки, у глушителя — задний торец на оси ствола, у ЗОРИН К-1 — корень
## крепления на затворе ПМ. Остальные сетки модели (Lens — стекло, Reticle — светящаяся метка) — как в файле.
static func _model_part(root: Node3D, m: Dictionary, a: Dictionary) -> bool:
	var spec: Dictionary = a.model
	var path: String = String(spec.get("scene", ""))
	if path == "" or not ResourceLoader.exists(path, "PackedScene"):
		return false
	var model: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	if model == null:
		return false
	var full: StandardMaterial3D = _model_material(path.get_basename() + "_100_") as StandardMaterial3D
	if full == null:
		model.free()
		return false
	var coated: ShaderMaterial = WeaponCondition.wear_material(full)
	var material: Material = coated if coated else full
	var o: Array = spec.get("offset", [0, 0, 0])
	var at: Vector3 = (m.pos as Vector3) + Vector3(float(o[0]), float(o[1]), float(o[2]))
	model.position = at
	root.add_child(model)
	for raw: Node in model.find_children("Body*", "MeshInstance3D", true, false):
		var body: MeshInstance3D = raw as MeshInstance3D
		body.material_override = material
		body.visible = String(body.name).contains("LOD1") == (int(m.get("lod", 0)) > 0)
		if String(body.name).contains("Eyecup"):
			# наглазник оптики: у глаза заходит за ближнюю плоскость камеры — CameraRig его прячет
			body.set_meta("near_hide", true)
	if spec.has("sight_h"):
		# прицел-модель (ЗОРИН К-1): линия прицеливания — через центр линзы
		root.set_meta("sight_h", at.y + float(spec.sight_h))
		root.set_meta("sight_x", at.x + float(spec.get("sight_x", 0.0)))
	if spec.has("ocular"):
		# оптика-модель: как у процедурной (_scope4x) — окуляр, его радиус и вынос глаза
		var oc: Array = spec.ocular
		var ocular: Vector3 = at + Vector3(float(oc[0]), float(oc[1]), float(oc[2]))
		root.set_meta("scoped", true)
		root.set_meta("ocular", ocular)
		root.set_meta("ocular_r", float(spec.get("ocular_r", 0.0148)))
		root.set_meta("ads_z", maxf(float(spec.get("eye_relief", 0.075)) - ocular.z, Balance.SCOPE_ADS_Z_MIN))
		# своя сетка в окуляре (текстура: R — нити, G — подсветка) и подсветка клавишей фонаря
		if spec.has("reticle"):
			root.set_meta("reticle_tex", String(spec.reticle))
		if bool(spec.get("illum", false)):
			root.set_meta("reticle_illum", true)
	if spec.has("length_m"):
		# дульная насадка: штатный тормоз снят, срез — на её торце
		if bool(m.get("replace", false)):
			_hide_part(root, "muzzle_device")
		root.set_meta("muzzle", at + Vector3(0, 0, float(spec.length_m)))
		if bool((a.get("fx", {}) as Dictionary).get("suppressed", false)):
			root.set_meta("suppressed", true)
	return true


## Обвес готовой моделью сам по себе (значок, предмет на полу): середина модели — в начале узла.
## null — у обвеса нет модели или файла.
static func standalone(id: String) -> Node3D:
	var a: Dictionary = WeaponDb.attachment(id)
	if a.is_empty() or not a.has("model"):
		return null
	var root: Node3D = Node3D.new()
	root.name = "Item_" + id
	if not _model_part(root, {"pos": Vector3.ZERO, "lod": 0}, a):
		root.free()
		return null
	var center: Vector3 = ItemModels.bounds(root).get_center()
	for child: Node in root.get_children():
		if child is Node3D:
			(child as Node3D).position -= center
	return root


## Материал модели обвеса по её картам (общий на все экземпляры); нет карт — null.
static func _model_material(prefix: String) -> Material:
	var key: String = "model:" + prefix
	if WeaponModels._mats.has(key):
		return WeaponModels._mats[key] as Material
	if not ResourceLoader.exists(prefix + "base_color.png"):
		return null
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_texture = load(prefix + "base_color.png") as Texture2D
	material.metallic = 1.0
	material.metallic_texture = load(prefix + "metallic.png") as Texture2D
	material.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.roughness_texture = load(prefix + "roughness.png") as Texture2D
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.normal_enabled = true
	material.normal_texture = load(prefix + "normal.png") as Texture2D
	WeaponModels._mats[key] = material
	return material


## Игровая модель ЛУМАР: общий крепёж, карты 100 (вид один при любой прочности) и отдельные стекло/марка.
static func _lumar(root: Node3D, m: Dictionary, attachment: Dictionary) -> bool:
	var path: String = String(attachment.get("asset", ""))
	if path == "" or not ResourceLoader.exists(path, "PackedScene"):
		return false
	var model: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	if model == null:
		return false
	model.name = "LUMAR_H1"
	model.position = m.pos
	model.position.y = _optic_base(root, m, 0.09)
	root.add_child(model)
	var material: StandardMaterial3D = StandardMaterial3D.new()
	var prefix: String = path.get_base_dir() + "/lumar_100_"
	material.albedo_texture = load(prefix + "base_color.png") as Texture2D
	material.metallic = 1.0
	material.metallic_texture = load(prefix + "metallic.png") as Texture2D
	material.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.roughness_texture = load(prefix + "roughness.png") as Texture2D
	material.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	material.normal_enabled = true
	material.normal_texture = load(prefix + "normal.png") as Texture2D
	for raw: Node in model.find_children("Body*", "MeshInstance3D", true, false):
		var body: MeshInstance3D = raw as MeshInstance3D
		body.material_override = material
		body.visible = String(body.name).contains("LOD1") == (int(m.get("lod", 0)) > 0)
	var lens: MeshInstance3D = model.find_child("Lens", true, false) as MeshInstance3D
	if lens:
		var glass: ShaderMaterial = ShaderMaterial.new()
		glass.shader = load("res://src/combat/lumar_glass.gdshader") as Shader
		lens.material_override = glass
	var reticle: MeshInstance3D = model.find_child("Reticle", true, false) as MeshInstance3D
	if reticle:
		# метка рисуется шейдером на квадрате (форма, цвет, толщина — на выбор игрока), а не сеткой
		# из модели: та была одной формы и одного цвета
		var quad: QuadMesh = QuadMesh.new()
		quad.size = Vector2.ONE * float(Balance.LUMAR.reticle_m)
		reticle.mesh = quad
		var mark: ShaderMaterial = ShaderMaterial.new()
		mark.shader = load("res://src/combat/lumar_reticle.gdshader") as Shader
		mark.render_priority = 1
		reticle.material_override = mark
		apply_reticle(reticle, 1.0)
		reticle.set_meta("reticle_dot", true)
		reticle.set_meta("lumar_reticle", true)
		reticle.set_meta("mount", String(m.mount))
	if lens:
		lens.set_meta("lumar_lens", true)
	root.set_meta("asset_loaded", true)
	var axis: Node3D = model.find_child("SightAxis", true, false) as Node3D
	root.set_meta("sight_h", model.position.y + (axis.position.y if axis else 0.056))
	return true


## Метке ЛУМАРа — форма, цвет и толщина из настроек игрока (Settings.reticle); k — множитель яркости
## (ПНВ на голове), износ прицела учитывается сам (meta "condition_k").
static func apply_reticle(mesh: MeshInstance3D, k: float) -> void:
	var mat: ShaderMaterial = mesh.material_override as ShaderMaterial
	if mat == null:
		return
	var prefs: Dictionary = Settings.reticle
	mat.set_shader_parameter("shape", int(prefs.shape))
	mat.set_shader_parameter("tint", SightMenu.COLORS[clampi(int(prefs.color), 0, SightMenu.COLORS.size() - 1)][1])
	mat.set_shader_parameter("bold", float(SightMenu.BOLDS[clampi(int(prefs.bold), 0, SightMenu.BOLDS.size() - 1)][0]))
	mat.set_shader_parameter("energy", k * float(mesh.get_meta("condition_k", 1.0)))


## Ресурс устройств меняется без пересоздания геометрии и сброса анимаций.
static func update_condition(root: Node3D, mods: Dictionary) -> void:
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		if not raw.has_meta("reticle_dot"):
			continue
		var mount: String = String(raw.get_meta("mount", ""))
		if not mods.has(mount):
			continue
		var state: Dictionary = WeaponCondition.mod_entry(mods[mount])
		(raw as MeshInstance3D).visible = not WeaponCondition.broken(state)
		var mesh: MeshInstance3D = raw as MeshInstance3D
		if mesh.has_meta("lumar_reticle"):
			# метка шейдером: износ — множителем яркости (ставит apply_reticle)
			mesh.set_meta("condition_k", lerpf(float(Balance.CONDITION.reticle_min), 1.0, WeaponCondition.effectiveness(state)))
			continue
		if not mesh.has_meta("condition_reticle_material"):
			var source: Material = mesh.get_active_material(0) if mesh.mesh and mesh.mesh.get_surface_count() > 0 else null
			if source is StandardMaterial3D:
				var local: StandardMaterial3D = source.duplicate() as StandardMaterial3D
				mesh.material_override = local
				mesh.set_meta("condition_reticle_material", local)
				mesh.set_meta("condition_reticle_energy", local.emission_energy_multiplier)
		if mesh.has_meta("condition_reticle_material"):
			var local: StandardMaterial3D = mesh.get_meta("condition_reticle_material") as StandardMaterial3D
			local.emission_energy_multiplier = float(mesh.get_meta("condition_reticle_energy")) * lerpf(float(Balance.CONDITION.reticle_min), 1.0, WeaponCondition.effectiveness(state))
	for raw: Node in root.find_children("Flashlight*", "SpotLight3D", true, false):
		var light: SpotLight3D = raw as SpotLight3D
		var mount: String = String(light.get_meta("mount", ""))
		if not light.has_meta("condition_energy"):
			light.set_meta("condition_energy", light.light_energy)
		if mods.has(mount):
			light.light_energy = float(light.get_meta("condition_energy")) * WeaponCondition.effectiveness(WeaponCondition.mod_entry(mods[mount]))


static func _scaled(root: Node3D, m: Dictionary, k: float, build: Callable) -> void:
	if is_equal_approx(k, 1.0):
		build.call(root, m)
		return
	var n := Node3D.new()
	n.position = m.pos
	n.scale = Vector3.ONE * k
	root.add_child(n)
	var mm := m.duplicate()
	mm.pos = Vector3.ZERO
	build.call(n, mm)


## Угловой прицел: кронштейн 45° на планке (поворотный узел по крену сокета), на нём мини-коллиматор.
## Его линия прицеливания в осях модели — meta sight_offset {x, h, roll}.
static func _offset_optic(root: Node3D, m: Dictionary, a: Dictionary) -> void:
	var roll := deg_to_rad(float(m.get("roll", 45.0)))
	var pivot := Node3D.new()
	pivot.name = "OffsetMount"
	pivot.position = m.pos
	pivot.rotation.z = roll
	root.add_child(pivot)
	var al := _mat("anodized")
	# Крупный коллиматор отнесён дальше от основной оптики; миниатюрному хватит короткого плеча.
	var height: float = 0.008 + float(a.get("offset_raise_m", 0.0))
	WeaponModels._cbox(pivot, Vector3(0, height * 0.5, 0), Vector3(0.022, height, 0.032), al, 0.0012)
	var sub: Dictionary = m.duplicate(true)
	sub["pos"] = Vector3(0, height, 0)
	sub["rail"] = false
	sub["riser"] = 0.0
	_build_look(pivot, sub, a)
	if pivot.get_meta("asset_loaded", false):
		root.set_meta("asset_loaded", true)
	var h := float(pivot.get_meta("sight_h", 0.02))
	var pt := pivot.transform * Vector3(0, h, 0)
	root.set_meta("sight_offset", {"x": pt.x, "h": pt.y, "roll": roll})


## Запасное крепление на боковой планке цевья: основание касается планки, окно смотрит к дулу.
## Прицел лежит на боку; камера компенсирует этот крен при выборе по СКМ.
static func _side_optic(root: Node3D, m: Dictionary, a: Dictionary) -> void:
	var p: Vector3 = m.pos
	var outer: float = p.x if bool(m.get("native_rail", false)) else _rail_side(root, p.x, p.y, p.z, 0.09)
	var roll: float = -signf(p.x) * PI * 0.5
	var pivot: Node3D = Node3D.new()
	pivot.name = "SideOpticMount"
	pivot.position = Vector3(outer, p.y, p.z)
	pivot.rotation.z = roll
	root.add_child(pivot)
	var sub: Dictionary = m.duplicate(true)
	sub["pos"] = Vector3.ZERO
	sub["rail"] = false
	sub["riser"] = 0.0
	_build_look(pivot, sub, a)
	if pivot.get_meta("asset_loaded", false):
		root.set_meta("asset_loaded", true)
	var pt: Vector3 = pivot.transform * Vector3(0, float(pivot.get_meta("sight_h", 0.02)), 0)
	root.set_meta("sight_" + String(m.mount), {"x": pt.x, "h": pt.y, "roll": roll})


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
	WeaponModels._sphere(root, Vector3(0, cy, zc + 0.0385), 0.0007, _mat("reticle")).set_meta("reticle_dot", true)
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
	WeaponModels._sphere(root, Vector3(0, wy, zc + 0.0385), 0.0006, _mat("reticle")).set_meta("reticle_dot", true)
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
	WeaponModels._sphere(root, Vector3(0, wy, p.z + 0.0115), 0.0005, _mat("reticle")).set_meta("reticle_dot", true)
	root.set_meta("sight_h", wy)


## Оптика 4×: призменный корпус, объектив и окуляр, волоконный указатель сверху.
static func _scope4x(root: Node3D, m: Dictionary, len_k: float = 1.0, obj_k: float = 1.0) -> void:
	var p: Vector3 = m.pos
	var top := _optic_base(root, m, 0.1)
	var al := _mat("anodized")
	var zc := p.z
	WeaponModels._cbox(root, Vector3(0, top + 0.005, zc), Vector3(0.026, 0.01, 0.05), al, 0.0015)
	var cy := top + 0.01 + 0.017
	WeaponModels._cbox(root, Vector3(0, cy, zc), Vector3(0.036, 0.034, 0.075 * len_k), al, 0.004)
	var fz := 0.0375 * len_k
	WeaponModels._cyl(root, Vector3(0, cy, zc + fz + 0.015), 0.0165, 0.03, al, 0.0205 * obj_k)
	WeaponModels._cyl(root, Vector3(0, cy, zc + fz + 0.032), 0.0205 * obj_k, 0.004, al)
	WeaponModels._cyl(root, Vector3(0, cy, zc - 0.049), 0.0175, 0.024, al, 0.016)
	WeaponModels._cyl(root, Vector3(0, cy, zc + fz + 0.0342), 0.018 * obj_k, 0.001, _mat("lens"))
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
	# прицел далеко на цевье: оружие к лицу ближе Balance.SCOPE_ADS_Z_MIN не подтягивается (приклад не
	# проходит сквозь голову) — окуляр остаётся дальше от глаза, картинка в нём меньше, как и в жизни
	root.set_meta("ads_z", maxf(0.075 - oz, Balance.SCOPE_ADS_Z_MIN))


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


## Рукоятка под 45° влево от стрелка (запасной вид без модели): вертикальная, повёрнутая вокруг ствола.
static func _grip_offset(root: Node3D, m: Dictionary) -> void:
	var p: Vector3 = m.pos
	var n := Node3D.new()
	n.position = p
	# +X модели — левая сторона стрелка: низ рукоятки уходит к +X
	n.rotation.z = deg_to_rad(45.0)
	root.add_child(n)
	var mm := m.duplicate()
	mm.pos = Vector3.ZERO
	_grip_vertical(n, mm)


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


## Магазин в оружии для вида модели: "*" — штатный (модель как есть), "" — магазина нет (у оружия
## без встроенного магазина), иначе id вставленного. Отсутствие патронов вид не меняет.
static func mag_state(entry: Dictionary) -> String:
	var wid: String = String(entry.get("id", ""))
	var w: Dictionary = WeaponDb.weapon(wid)
	if w.is_empty() or w.has("internal_mag") or not w.has("mag_if"):
		return "*"
	var mag: Dictionary = entry.get("mag", {}) if entry.get("mag") is Dictionary else {}
	var mid: String = WeaponDb.canonical(String(mag.get("id", "")))
	if mid == "":
		return ""
	return "*" if mid == WeaponDb.default_mag(wid) else mid


## Магазин на модели: штатная деталь (meta part = "mag") видна, если вставлен магазин без своего
## вида; у магазина с видом (attach look в данных магазина) — свой корпус на сокете "mag";
## mag == "" — магазина нет вовсе (пустой вставленный магазин при этом остаётся на месте).
## look "asset" — модель из файла (магазины ВЕРАС-54 на 45 и 60, tools/veras54_mags): начало модели — точка
## крепления, она встаёт в asset_pos сокета (или в pos); detail — подробная модель (asset_detail) вместо мировой.
static func set_magazine(root: Node3D, weapon_id: String, mag: String, detail: bool = false) -> void:
	var old: Node = root.find_child("MagLook", false, false)
	if old:
		old.free()
	var spec: Dictionary = WeaponDb.magazine(mag) if mag != "" else {}
	var look: String = String(spec.get("look", ""))
	var sk: Dictionary = socket(String(WeaponDb.weapon(weapon_id).get("model", "")), "mag")
	if look != "" and sk.is_empty():
		look = ""
	for node: Node in root.find_children("*", "Node3D", true, false):
		if String(node.get_meta("part", "")) == "mag":
			(node as Node3D).visible = mag != "" and look == ""
	if look == "":
		return
	var holder: Node3D = Node3D.new()
	holder.name = "MagLook"
	root.add_child(holder)
	var m: Dictionary = sk.duplicate(true)
	m["mount"] = "mag"
	m["capacity"] = int(spec.get("capacity", 30))
	match look:
		"mag_ak45":
			_mag_ak45(holder, m)
		"mag_pistol_ext":
			_mag_pistol_ext(holder, m)
		"asset":
			var path: String = String(spec.get("asset_detail" if detail else "asset", spec.get("asset", "")))
			if not _mag_asset(holder, path, m):
				# нет файла — прежний вид удлинённого магазина
				_mag_ak45(holder, m)


## Магазин из файла на сокете «mag»: модель в осях игры, начало — точка крепления. false — файла нет.
static func _mag_asset(holder: Node3D, path: String, m: Dictionary) -> bool:
	if path == "" or not ResourceLoader.exists(path, "PackedScene"):
		return false
	var model: Node3D = (ResourceLoader.load(path, "PackedScene") as PackedScene).instantiate() as Node3D
	if model == null:
		return false
	model.name = "MagAsset"
	model.position = m.pos as Vector3
	if m.has("asset_pos"):
		var at: Array = m.asset_pos as Array
		model.position = Vector3(float(at[0]), float(at[1]), float(at[2]))
	holder.add_child(model)
	return true


## Удлинённый коробчатый магазин: та же дуга, что у штатного, длина — по ёмкости (45 — на треть
## длиннее штатного на 30).
static func _mag_ak45(root: Node3D, m: Dictionary) -> void:
	_hide_part(root, "mag")
	var mp: Array[Vector3] = []
	var ms: Array[Vector2] = []
	var q: Vector3 = m.pos
	var ang := 0.0
	for i in range(clampi(roundi(12.0 * float(m.get("capacity", 45)) / 45.0), 8, 18)):
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
		var outer: float = p.x if bool(m.get("native_rail", false)) else _rail_side(root, p.x, p.y, p.z, 0.05)
		t.position = Vector3(outer + signf(p.x) * 0.011, p.y, p.z)
	else:
		WeaponModels._cbox(root, Vector3(p.x, p.y - 0.004, p.z), Vector3(0.022, 0.008, 0.03), _mat("anodized"), 0.001)
		# корпус касается хомута снизу (радиус корпуса 0.0105)
		t.position = Vector3(p.x, p.y - 0.008 - 0.0102, p.z + 0.004)
	return t


static func _flashlight(root: Node3D, m: Dictionary, a: Dictionary, size_k: float) -> void:
	var t := _tac_body(root, m)
	var al := _mat("anodized")
	WeaponModels._cyl(t, Vector3(0, 0, 0), 0.0105 * size_k, 0.07, al)
	WeaponModels._cyl(t, Vector3(0, 0, 0.042), 0.0128 * size_k, 0.016, al, 0.0132 * size_k)
	WeaponModels._cyl(t, Vector3(0, 0, 0.0505), 0.0115 * size_k, 0.001, _mat("light_lens"))
	WeaponModels._cyl(t, Vector3(0, 0, -0.037), 0.009, 0.006, _mat("rubber"))
	_light_node(t, m, a, Vector3(0, 0, 0.052))


## Луч фонаря по данным обвеса (attach.light: дальность, угол, сила, отражённый, блик, в воздухе).
static func _light_node(t: Node3D, m: Dictionary, a: Dictionary, at: Vector3) -> void:
	var ls: Dictionary = a.get("light", {})
	var light := SpotLight3D.new()
	light.name = "Flashlight_" + String(m.get("mount", ""))
	light.set_meta("mount", String(m.get("mount", "")))
	light.position = at
	light.rotation.y = PI
	# Калиброванный свет обвеса: общее Settings.soften не меняет профиль и отражённый свет.
	light.set_meta("soft", true)
	light.light_color = Color(0.96, 0.98, 1.0)
	light.light_energy = float(ls.get("energy", 3.2))
	light.spot_range = float(ls.get("range", 30.0))
	light.spot_angle = float(ls.get("angle", 28.0))
	light.spot_attenuation = 0.8
	light.spot_angle_attenuation = 0.8
	light.light_projector = FLASHLIGHT_BEAM
	light.light_indirect_energy = float(ls.get("indirect", 0.8))
	light.light_specular = float(ls.get("specular", 0.4))
	light.shadow_enabled = true
	light.shadow_bias = 0.03
	light.shadow_normal_bias = 0.5
	light.shadow_blur = 1.2
	light.light_volumetric_fog_energy = float(ls.get("fog", 2.0))
	light.visible = false
	# светит в глаза — слепит (LightGlare у игрока, мародёры целятся хуже)
	light.add_to_group("glare_lights")
	# по мокрому асфальту — отражённый луч дальше
	light.add_child(WetBounce.new())
	# сам фонарь светится: видно издали и в оптике (у своего в руках — смотрит от камеры, не мешает)
	LampGlow.attach(light)
	t.add_child(light)


static func _laser(root: Node3D, m: Dictionary) -> void:
	var t := _tac_body(root, m)
	var al := _mat("anodized")
	WeaponModels._cbox(t, Vector3(0, 0, 0), Vector3(0.024, 0.02, 0.046), al, 0.003)
	WeaponModels._cyl(t, Vector3(0, 0.003, 0.0235), 0.003, 0.002, _mat("reticle"))
	WeaponModels._cbox(t, Vector3(0, 0.011, -0.006), Vector3(0.01, 0.003, 0.014), _mat("rubber"), 0.001)
	_beam_node(t, m, Vector3(0, 0.003, 0.0245))


## ЛЦУ: узел LaserSight у излучателя, по оси +Z (луч до преграды, точка на ней). Включает его
## состояние обвеса (Player.tac_on), по умолчанию выключен.
static func _beam_node(t: Node3D, m: Dictionary, at: Vector3) -> void:
	var beam := LaserSight.new()
	beam.name = "LaserBeam_" + String(m.get("mount", ""))
	beam.set_meta("mount", String(m.get("mount", "")))
	beam.position = at
	beam.visible = false
	t.add_child(beam)


## Блок фонарь + ЛЦУ: корпус с линзой и окошком лазера; фонарь и лазер — независимо.
static func _combo(root: Node3D, m: Dictionary, a: Dictionary) -> void:
	var t := _tac_body(root, m)
	var al := _mat("anodized")
	WeaponModels._cbox(t, Vector3(0, -0.002, 0), Vector3(0.03, 0.028, 0.07), al, 0.003)
	WeaponModels._cyl(t, Vector3(0, -0.004, 0.036), 0.0105, 0.002, _mat("light_lens"))
	WeaponModels._cyl(t, Vector3(0, 0.009, 0.036), 0.003, 0.002, _mat("reticle"))
	_light_node(t, m, a, Vector3(0, -0.004, 0.038))
	_beam_node(t, m, Vector3(0, 0.009, 0.037))


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
