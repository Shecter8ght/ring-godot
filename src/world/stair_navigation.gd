class_name StairNavigation
extends Node3D
## Навигация на лестницах. Сетка пути (Balance.URBAN_WORLD) рвётся на крутом и узком марше и не покрывает крохотные
## площадки у его концов (причины и числа — Balance.STAIR_NAV и tools/nav_stair_probe.tscn), поэтому каждому маршу,
## зарегистрированному через register (StudyGeometry.stairs), после запуска сетки строится «ковёр»: один многоугольник
## по наклонной плите марша вместе с площадками на концах, и связки его концов с ближайшей сеткой карты (или с ковром
## соседнего марша). Выпеченные тайлы (кэш) не меняются, ковры и связки — только в живой карте; идут по ним физикой,
## как по пандусу.

## Метка марша: узел-запись в сцене (группа Balance.STAIR_NAV.group), данные в meta "stair" — в координатах родителя.
const META := "stair"

var _links: int = 0
## Отчёт последней сборки по маршам: {low, high — концы ковра, low_to, high_to — куда привязан конец (NAN — никуда), kind —
## "net" / "pair" / "" для каждого конца}; для стендов и проверок (tools/prospekt_nav_stairs.tscn).
static var report: Array[Dictionary] = []
## Печатать концы без связки (стенды).
static var debug: bool = false


## Запомнить марш (вызывает сборщик геометрии; start / finish — концы наклонной плиты в координатах parent).
static func register(parent: Node3D, start: Vector3, finish: Vector3, width: float) -> void:
	if not bool(Balance.STAIR_NAV.on) or parent == null:
		return
	var spot := Node3D.new()
	spot.name = "StairSpot"
	spot.set_meta(META, {"start": start, "finish": finish, "width": width})
	spot.add_to_group(String(Balance.STAIR_NAV.group))
	parent.add_child(spot)


## Построить ковры и связки для всех меток в дереве; вернёт число маршей. Зовёт UrbanNavigation, когда сетка карты готова.
static func build(host: Node, map: RID) -> int:
	var spots: Array = []
	for node: Node in host.get_tree().get_nodes_in_group(String(Balance.STAIR_NAV.group)):
		if node is Node3D and node.is_inside_tree() and node.has_meta(META):
			spots.append(node)
	if spots.is_empty():
		return 0
	var builder := StairNavigation.new()
	builder.name = "StairNavigation"
	host.add_child(builder)
	return await builder._build(spots, map)


func _build(spots: Array, map: RID) -> int:
	var cfg: Dictionary = Balance.STAIR_NAV
	var pad: float = float(cfg.pad_m)
	var lift: float = float(cfg.lift) + float(cfg.bias)
	var offsets: Array = cfg.link_offsets
	# мировые данные каждого марша: концы ковра (с площадками), пол у концов и половина ширины
	var stairs: Array[Dictionary] = []
	for spot: Node3D in spots:
		var data: Dictionary = spot.get_meta(META)
		var start: Vector3 = spot.global_transform * (data.start as Vector3)
		var finish: Vector3 = spot.global_transform * (data.finish as Vector3)
		var flat := Vector3(finish.x - start.x, 0.0, finish.z - start.z)
		if flat.length() < 0.5:
			continue
		var dir: Vector3 = flat.normalized()
		var half: float = clampf(float(data.width) * 0.5 - float(cfg.edge_m), float(cfg.half_min), float(cfg.half_max))
		var low: Vector3 = start - dir * pad + Vector3.UP * lift
		var high: Vector3 = finish + dir * pad + Vector3.UP * lift
		stairs.append({"low": low, "high": high, "dir": dir, "half": half, "span": flat.length() + pad * 2.0,
			"floor_low": start.y, "floor_high": finish.y})
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var regions: Array[NavigationRegion3D] = []
	var linked_net: int = 0
	var linked_pair: int = 0
	report = []
	# сетку карты ищем до того, как ковры попали в карту (сетка как она есть); концы всех маршей — для связок «марш к маршу»
	var mids: Array[Vector3] = []
	for s: Dictionary in stairs:
		mids.append(_on_carpet(s, false, float(offsets[offsets.size() / 2])))
		mids.append(_on_carpet(s, true, float(offsets[offsets.size() / 2])))
	for i in range(stairs.size()):
		var s: Dictionary = stairs[i]
		regions.append(_carpet(s))
		var row: Dictionary = {"low": _on_carpet(s, false, 0.5), "high": _on_carpet(s, true, 0.5),
			"low_to": Vector3(NAN, NAN, NAN), "high_to": Vector3(NAN, NAN, NAN), "low_kind": "", "high_kind": ""}
		report.append(row)
		for k in range(2):
			var top: bool = k == 1
			var which: String = "high" if top else "low"
			var floor_y: float = float(s.floor_high if top else s.floor_low)
			var made: int = 0
			# выход с ковра — на offset м за концом марша (дальше концов поручней), ближе — если там стена
			for offset: float in offsets:
				var pos: Vector3 = _on_carpet(s, top, offset)
				for target: Vector3 in _nearest_nets(map, pos):
					if _clear(space, pos, floor_y, target):
						_link(pos, target)
						if made == 0:
							row[which] = pos
							row[which + "_to"] = target
							row[which + "_kind"] = "net"
						made += 1
				if made > 0:
					break
			if made > 0:
				linked_net += 1
				continue
			# сетки рядом нет — к концу ковра соседнего марша на той же площадке
			var pos_mid: Vector3 = mids[i * 2 + k]
			var best: int = -1
			var best_d: float = float(cfg.pair_m)
			for j in range(mids.size()):
				if j / 2 == i:
					continue
				var d: float = Vector2(mids[j].x - pos_mid.x, mids[j].z - pos_mid.z).length()
				if d < best_d and absf(mids[j].y - pos_mid.y) <= float(cfg.pair_y) and _clear(space, pos_mid, floor_y, mids[j]):
					best = j
					best_d = d
			if best >= 0:
				_link(pos_mid, mids[best])
				linked_pair += 1
				row[which] = pos_mid
				row[which + "_to"] = mids[best]
				row[which + "_kind"] = "pair"
			elif debug:
				print("навигация лестниц: конец без связки %s" % pos_mid)
	var iteration: int = NavigationServer3D.map_get_iteration_id(map)
	for region: NavigationRegion3D in regions:
		add_child(region)
	# дождаться, пока сервер выпустит ковры и связки в карту (на большой карте это секунды: итерация карты — целиком)
	var t0: int = Time.get_ticks_msec()
	var frames: int = 0
	while frames < 4 or NavigationServer3D.map_get_iteration_id(map) <= iteration or not _published(regions):
		await get_tree().physics_frame
		frames += 1
		if Time.get_ticks_msec() - t0 > int(float(cfg.publish_sec) * 1000.0) and frames > 30:
			push_warning("навигация лестниц: ковры не опубликованы за %.0f с" % float(cfg.publish_sec))
			break
	print("навигация лестниц: маршей %d, концов к сетке %d, к соседнему маршу %d, без связки %d, %d мс" % [
		stairs.size(), linked_net, linked_pair, stairs.size() * 2 - linked_net - linked_pair, Time.get_ticks_msec() - t0])
	return stairs.size()


func _published(regions: Array[NavigationRegion3D]) -> bool:
	for region: NavigationRegion3D in regions:
		if NavigationServer3D.region_get_iteration_id(region.get_rid()) == 0:
			return false
	return true


## Точка на ковре на offset м за концом марша (top — верхний конец); лежит строго на плоскости ковра.
func _on_carpet(s: Dictionary, top: bool, offset: float) -> Vector3:
	var t: float = (float(Balance.STAIR_NAV.pad_m) - offset) / float(s.span)
	return (s.low as Vector3).lerp(s.high as Vector3, 1.0 - t if top else t)


## Ковёр марша: один плоский многоугольник по плите вместе с площадками (четыре точки — всегда одна плоскость).
func _carpet(s: Dictionary) -> NavigationRegion3D:
	var dir: Vector3 = s.dir
	var side: Vector3 = dir.cross(Vector3.UP) * float(s.half)
	var low: Vector3 = s.low
	var high: Vector3 = s.high
	var mesh := NavigationMesh.new()
	mesh.vertices = PackedVector3Array([low - side, low + side, high + side, high - side])
	mesh.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	var region := NavigationRegion3D.new()
	region.name = "Carpet"
	region.navigation_mesh = mesh
	region.use_edge_connections = false
	return region


func _link(a: Vector3, b: Vector3) -> void:
	var link := NavigationLink3D.new()
	_links += 1
	link.name = "StairLink_%d" % _links
	link.bidirectional = true
	link.travel_cost = float(Balance.STAIR_NAV.travel_cost)
	add_child(link)
	link.start_position = a
	link.end_position = b


## Точки сетки карты вокруг конца ковра (до nets_max штук): по кольцу на каждое расстояние из search_rings берётся ближайшая
## к концу, лежащая на нужной высоте (не дальше y_tol) и не ближе nets_gap к уже взятым.
func _nearest_nets(map: RID, at: Vector3) -> Array[Vector3]:
	var cfg: Dictionary = Balance.STAIR_NAV
	var y_tol: float = float(cfg.y_tol)
	var dirs: int = int(cfg.search_dirs)
	var found: Array[Vector3] = []
	for ring: float in cfg.search_rings:
		var best := Vector3(NAN, NAN, NAN)
		var best_d: float = INF
		for k in range(dirs):
			var angle: float = TAU * float(k) / float(dirs)
			var probe: Vector3 = at + Vector3(cos(angle), 0.0, sin(angle)) * ring
			var net: Vector3 = NavigationServer3D.map_get_closest_point(map, probe)
			# точка сетки лежит прямо под / над пробой (а не в стороне), и на нужной высоте
			if Vector2(net.x - probe.x, net.z - probe.z).length() > 0.3 or absf(net.y - at.y) > y_tol:
				continue
			var near: bool = false
			for taken: Vector3 in found:
				near = near or Vector2(net.x - taken.x, net.z - taken.z).length() < float(cfg.nets_gap)
			var d: float = Vector2(net.x - at.x, net.z - at.z).length()
			if not near and d < best_d:
				best_d = d
				best = net
		if best.is_finite():
			found.append(best)
			if found.size() >= int(cfg.nets_max):
				break
	return found


## Между концом ковра и точкой сетки нет препятствия для тела: капсула бойца (радиус и высота — Balance.STAIR_NAV) идёт
## от одного к другому по полу (floor_y — пол у конца марша); лучи на колене и груди пропускали торцы поручней.
func _clear(space: PhysicsDirectSpaceState3D, a: Vector3, floor_y: float, b: Vector3) -> bool:
	var cfg: Dictionary = Balance.STAIR_NAV
	var shape := CapsuleShape3D.new()
	shape.radius = float(cfg.body_r)
	shape.height = float(cfg.body_h)
	var query := PhysicsShapeQueryParameters3D.new()
	query.shape = shape
	query.collision_mask = Hitscan.LAYER_WORLD
	# капсула приподнята над полом на body_up: пол и ступенька ей не мешают, а поручни (0,45 и 0,9 м) — мешают
	var up: float = float(cfg.body_up) + shape.height * 0.5
	query.transform = Transform3D(Basis(), Vector3(a.x, floor_y + up, a.z))
	# по горизонтали: цели на одной высоте с концом марша (y_tol), а сетка на самом марше (клочки) отсеивается — на подъём капсула упрётся
	query.motion = Vector3(b.x - a.x, 0.0, b.z - a.z)
	var fractions: PackedFloat32Array = space.cast_motion(query)
	var free: bool = fractions.size() >= 2 and fractions[0] >= 0.999
	if debug and not free:
		var overlap: Array[Dictionary] = space.intersect_shape(query, 3)
		print("навигация лестниц: тело не проходит %s → %s, доли %s, под телом: %s" % [a, b, fractions,
			overlap.map(func(o: Dictionary) -> String: return str((o.collider as Node).get_path()))])
	return free
