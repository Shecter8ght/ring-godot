class_name AttachmentRemote
extends RefCounted
## Два крепления одного комплекта. Пульт — вложенное место в записи блока,
## поэтому масса, ресурс, цена, снятие и передача по сети учитываются ровно один раз.

const FOREEND := ["top_front", "side_left", "side_right", "underbarrel"]
const MAIN_POINTS := ["optic_primary", "top_front", "side_left", "side_right", "underbarrel"]
const START := Vector3(0.014, 0.0153, -0.0394)
const END := Vector3(0, 0.00285, -0.024)
const LENGTH := 0.152246


static func spec(id: String) -> Dictionary:
	return WeaponDb.attachment(id).get("remote", {})


static func host_block(id: String, key: String) -> String:
	if String(WeaponDb.weapon(id).get("class", "")) == "PISTOL":
		return "МЕТКА-4 слишком велика для пистолета"
	if not WeaponBuild.top_mount(key) in MAIN_POINTS:
		return "для блока нужна оружейная планка Пикатинни"
	return ""


static func overlap(a: Vector2, b: Vector2) -> bool:
	return a.x < b.y - 0.0001 and b.x < a.y - 0.0001


static func remote_span(model: String, rec: Dictionary) -> Vector2:
	var s: Dictionary = spec(WeaponDb.mod_id(rec))
	var place: Dictionary = rec.get("remote", {})
	var g: Dictionary = WeaponBuild.geo(model, {}, String(place.get("point", "")))
	if s.is_empty() or not WeaponBuild.is_rail(g):
		return Vector2.ZERO
	var z: float = WeaponBuild.slot_z(g.rail, float(s.clamp_m), int(place.get("slot", 0)))
	var footprint: Array = s.footprint_m
	if bool(place.get("reverse", false)):
		return Vector2(z - float(footprint[1]), z - float(footprint[0]))
	return Vector2(z + float(footprint[0]), z + float(footprint[1]))


static func frame(model: String, point: String, z: float) -> Transform3D:
	var sk: Dictionary = WeaponMods.socket(model, point)
	if sk.is_empty():
		return Transform3D.IDENTITY
	var p: Vector3 = sk.pos
	p.y += float(sk.get("riser", 0.0)) + (WeaponMods.RAIL_H if bool(sk.get("rail", false)) else 0.0)
	p.z = z
	return WeaponMods._mount_frame(model, point, {"pos": p}, Transform3D.IDENTITY, true)


static func main_frame(model: String, mods: Dictionary, key: String) -> Transform3D:
	var parent: String = WeaponBuild.parent_key(key)
	if parent == "":
		return frame(model, WeaponBuild.base_of(key), WeaponBuild.placed_z(model, mods, key))
	var g: Dictionary = WeaponBuild.geo(model, mods, key)
	var roll: float = deg_to_rad(WeaponBuild.point_roll(model, mods, key))
	return main_frame(model, mods, parent) * Transform3D(Basis(Vector3(0, 0, 1), roll), Vector3.ZERO) * Transform3D(Basis.IDENTITY, g.get("pos", Vector3.ZERO)) * Transform3D(Basis.IDENTITY, Vector3(0, 0, WeaponBuild.placed_z(model, mods, key)))


static func remote_frame(model: String, rec: Dictionary) -> Transform3D:
	var p: Dictionary = rec.get("remote", {})
	var point: String = String(p.get("point", ""))
	var g: Dictionary = WeaponBuild.geo(model, {}, point)
	if not WeaponBuild.is_rail(g):
		return Transform3D.IDENTITY
	var z: float = WeaponBuild.slot_z(g.rail, float(spec(WeaponDb.mod_id(rec)).clamp_m), int(p.get("slot", 0)))
	var result: Transform3D = frame(model, point, z)
	if bool(p.get("reverse", false)):
		result.basis = result.basis * Basis(Vector3.UP, PI)
	return result


## Все свободные положения пульта с учётом длины провода и физических габаритов.
static func options(id: String, mods: Dictionary, key: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var rec: Dictionary = WeaponCondition.mod_entry(mods.get(key, {}))
	var s: Dictionary = spec(WeaponDb.mod_id(rec))
	if s.is_empty() or host_block(id, key) != "":
		return out
	var model: String = WeaponBuild.model_of(id)
	var mf: Transform3D = main_frame(model, mods, key)
	for point: String in FOREEND:
		if point == WeaponBuild.top_mount(key):
			continue
		var g: Dictionary = WeaponBuild.point(id, mods, point)
		if not WeaponBuild.is_rail(g) or not String(g.get("iface", "")).begins_with("RAIL_"):
			continue
		for slot: int in range(WeaponBuild.slot_count(g.rail, float(s.clamp_m))):
			for reverse: bool in [false, true]:
				var candidate: Dictionary = rec.duplicate(true)
				candidate["remote"] = {"point": point, "slot": slot, "reverse": reverse}
				var span: Vector2 = remote_span(model, candidate)
				var bounds: Array = WeaponMods.socket(model, point).get("remote_bounds_z", [])
				if bounds.size() == 2 and (span.x < float(bounds[0]) - 0.0001 or span.y > float(bounds[1]) + 0.0001):
					continue
				var blocked: bool = false
				for other: String in WeaponBuild.sorted_keys(mods):
					if WeaponBuild.point_key(other) == point and overlap(span, WeaponBuild.span(model, mods, other)):
						blocked = true
					var o: Dictionary = WeaponCondition.mod_entry(mods[other])
					if other != key and not spec(WeaponDb.mod_id(o)).is_empty() and String((o.get("remote", {}) as Dictionary).get("point", "")) == point and overlap(span, remote_span(model, o)):
						blocked = true
				if blocked:
					continue
				var rf: Transform3D = remote_frame(model, candidate)
				var route: PackedVector3Array = cable_route(mf * START, rf * END, foreend_center(model), 0.0, foreend_radii(model))
				if route_length(route) <= LENGTH + 0.0001:
					out.append({"point": point, "slot": slot, "reverse": reverse, "distance": mf.origin.distance_squared_to(rf.origin)})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.distance) < float(b.distance))
	return out


## Разрешить автоматические места; явно выбранное занятое место не переносим молча.
static func resolve(id: String, mods: Dictionary) -> Dictionary:
	var result: Dictionary = mods.duplicate(true)
	var keys: Array[String] = WeaponBuild.sorted_keys(result)
	for key: String in keys:
		var rec: Dictionary = WeaponCondition.mod_entry(result[key])
		if not spec(WeaponDb.mod_id(rec)).is_empty() and rec.has("remote") and not rec.remote is Dictionary:
			return {"mods": result, "why": "неверное место пульта МЕТКА-4"}
	# Сначала явные места, затем автоматические — чтобы новый пульт не занял выбранное старым.
	keys.sort_custom(func(a: String, b: String) -> bool:
		return (result[a] is Dictionary and (result[a] as Dictionary).has("remote")) and not (result[b] is Dictionary and (result[b] as Dictionary).has("remote")))
	for key: String in keys:
		var rec: Dictionary = WeaponCondition.mod_entry(result[key])
		if spec(WeaponDb.mod_id(rec)).is_empty():
			continue
		var why: String = host_block(id, key)
		if why != "":
			return {"mods": result, "why": why}
		var possible: Array[Dictionary] = options(id, result, key)
		var chosen: Dictionary = {}
		if rec.has("remote"):
			if not rec.remote is Dictionary:
				return {"mods": result, "why": "неверное место пульта МЕТКА-4"}
			for p: Dictionary in possible:
				if String(p.point) == String(rec.remote.get("point", "")) and int(p.slot) == int(rec.remote.get("slot", -1)) and (not rec.remote.has("reverse") or bool(rec.remote.reverse) == bool(p.reverse)):
					chosen = p
		else:
			if not possible.is_empty():
				chosen = possible[0]
		if chosen.is_empty():
			return {"mods": result, "why": "для пульта МЕТКА-4 нужна вторая свободная планка в пределах провода"}
		rec.erase("n")
		rec["remote"] = {"point": String(chosen.point), "slot": int(chosen.slot), "reverse": bool(chosen.reverse)}
		result[key] = rec
	return {"mods": result, "why": ""}


## Старый ЛЦУ получает второе крепление; несовместимый комплект возвращается целиком.
static func upgrade(entry: Dictionary) -> Array:
	var e: Dictionary = entry.duplicate(true)
	var spill: Array = []
	for key: String in WeaponBuild.sorted_keys(e.get("mods", {})):
		var rec: Dictionary = WeaponCondition.mod_entry(e.mods[key])
		if spec(WeaponDb.mod_id(rec)).is_empty():
			continue
		var why: String = WeaponBuild.block(e, key, WeaponDb.mod_id(rec))
		if why == "":
			var resolved: Dictionary = resolve(String(e.id), e.mods)
			if String(resolved.why) == "":
				e.mods = resolved.mods
				continue
		var removed: Array = WeaponBuild.extract(e, key)
		e = removed[0]
		spill.append(removed[1])
	return [e, spill]


static func foreend_center(model: String) -> Vector3:
	var c: Vector3 = Vector3.ZERO
	var n: int = 0
	for p: String in FOREEND:
		var sk: Dictionary = WeaponMods.socket(model, p)
		if not sk.is_empty():
			c += sk.pos as Vector3
			n += 1
	return c / maxf(n, 1)


static func foreend_radii(model: String) -> Vector3:
	var center: Vector3 = foreend_center(model)
	var radii: Vector3 = Vector3(0.012, 0.012, 0.012)
	for point: String in FOREEND:
		var sk: Dictionary = WeaponMods.socket(model, point)
		if not sk.is_empty():
			var p: Vector3 = sk.pos
			radii.x = maxf(radii.x, absf(p.x - center.x) + 0.002)
			radii.y = maxf(radii.y, p.y - center.y + 0.002)
			radii.z = maxf(radii.z, center.y - p.y + 0.002)
	return radii


## Гладкая трасса сзади блоков, огибающая цевьё по короткой дуге.
## slack добавляет провис, а не растягивает провод. Концы всегда совпадают со штуцерами.
static func cable_route(start: Vector3, end: Vector3, center: Vector3, slack: float, radii: Vector3) -> PackedVector3Array:
	var a: float = atan2(start.y - center.y, start.x - center.x)
	var b: float = a + wrapf(atan2(end.y - center.y, end.x - center.x) - a, -PI, PI)
	var ra: float = Vector2(start.x - center.x, start.y - center.y).length()
	var rb: float = Vector2(end.x - center.x, end.y - center.y).length()
	var controls: PackedVector3Array = [start]
	for i: int in range(9):
		var t: float = float(i) / 8.0
		var angle: float = lerpf(a, b, t)
		var radius: float = lerpf(ra, rb, t)
		var ry: float = radii.y if sin(angle) >= 0.0 else radii.z
		var envelope: float = 1.0 / sqrt(pow(cos(angle) / radii.x, 2) + pow(sin(angle) / ry, 2))
		# Цевьё выше, чем шире: круговая дуга тратила длину провода в пустоте по бокам.
		radius = minf(radius, maxf(envelope, radius * (1.0 - 0.35 * pow(sin(PI * t), 2))))
		controls.append(Vector3(center.x + cos(angle) * radius, center.y + sin(angle) * radius, lerpf(start.z, end.z, t) - 0.002 - sin(PI * t) * slack))
	controls.append(end)
	var curve: Curve3D = Curve3D.new()
	curve.bake_interval = 0.001
	for i: int in range(controls.size()):
		var before: Vector3 = controls[maxi(0, i - 1)]
		var after: Vector3 = controls[mini(controls.size() - 1, i + 1)]
		var tangent: Vector3 = (after - before) / 6.0
		curve.add_point(controls[i], -tangent if i > 0 else Vector3.ZERO, tangent if i < controls.size() - 1 else Vector3.ZERO)
	return curve.get_baked_points()


static func route_length(points: PackedVector3Array) -> float:
	var total: float = 0.0
	for i: int in range(1, points.size()):
		total += points[i - 1].distance_to(points[i])
	return total


static func cable_points(mf: Transform3D, rf: Transform3D, center: Vector3, radii: Vector3) -> PackedVector3Array:
	var start: Vector3 = mf * START
	var end: Vector3 = rf * END
	var lo: float = 0.0
	var hi: float = LENGTH * 0.5
	for i: int in range(14):
		var mid: float = (lo + hi) * 0.5
		if route_length(cable_route(start, end, center, mid, radii)) < LENGTH:
			lo = mid
		else:
			hi = mid
	return cable_route(start, end, center, (lo + hi) * 0.5, radii)
