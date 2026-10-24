class_name Vault
extends RefCounted
## Перелезание через низкие преграды — одна проверка для игрока и ИИ.
##  find — можно ли от ног p перелезть в сторону dir: преграда по пояс (Balance.VAULT min_h…max_h)
##  в пределах reach, над ней свободно, за ней — пол на той же высоте (не обрыв, не помост), место
##  для тела. Возвращает путь {p, up, over, land, top, thick} или {}. Залезть на преграду — Climb.
##  pos_at — точка на этом пути в доле t (0…1): подъём на край, через верх, спуск.
##  build_links — связки навигации «перелезть» для мародёров: вдоль краёв навмеша, где за
##  преградой по пояс тоже навмеш, а обход долгий (Balance.VAULT_LINKS).

const MASK := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
const GROUP := "vault_links"


static func find(space: PhysicsDirectSpaceState3D, p: Vector3, dir: Vector3, exclude: Array[RID] = [], reach: float = -1.0) -> Dictionary:
	var v: Dictionary = Balance.VAULT
	dir.y = 0.0
	if dir.length_squared() < 0.01:
		return {}
	dir = dir.normalized()
	var r := float(v.reach) if reach < 0.0 else reach
	var min_h := float(v.min_h)
	var max_h := float(v.max_h)
	# 1. преграда на уровне колен
	var knee := _ray(space, p + Vector3.UP * (min_h - 0.05), p + Vector3.UP * (min_h - 0.05) + dir * r, exclude)
	if knee.is_empty():
		return {}
	var d0 := (Vector3(knee.position.x, p.y, knee.position.z) - p).length()
	# 2. выше макс. высоты — свободно (это не стена)
	var clear_y := max_h + 0.35
	if not _ray(space, p + Vector3.UP * clear_y, p + Vector3.UP * clear_y + dir * (d0 + float(v.max_thick) + 0.6), exclude).is_empty():
		return {}
	# 3. верх преграды
	var top_hit := _ray(space, p + dir * (d0 + 0.12) + Vector3.UP * clear_y, p + dir * (d0 + 0.12) + Vector3.UP * 0.02, exclude)
	if top_hit.is_empty():
		return {}
	var top := float(top_hit.position.y) - p.y
	if top < min_h or top > max_h:
		return {}
	# 4. дальний край: сверху вниз, пока не найдём пол на нашей высоте
	var k := d0 + 0.2
	var far := -1.0
	while k <= d0 + float(v.max_thick) + 0.3:
		var h := _ray(space, p + dir * k + Vector3.UP * clear_y, p + dir * k + Vector3.DOWN * 1.0, exclude)
		if h.is_empty():
			return {}
		var y := float(h.position.y) - p.y
		if absf(y) < 0.3:
			far = k
			break
		if y < -0.3:
			# обрыв за преградой — не прыгаем вниз
			return {}
		k += 0.1
	if far < 0.0:
		return {}
	# 5. место для тела за преградой
	var land := p + dir * (far + 0.45)
	var floor_hit := _ray(space, land + Vector3.UP * 0.6, land + Vector3.DOWN * 0.6, exclude)
	if floor_hit.is_empty() or absf(float(floor_hit.position.y) - p.y) > 0.3:
		return {}
	land.y = float(floor_hit.position.y)
	var shape := CapsuleShape3D.new()
	shape.radius = 0.3
	shape.height = 1.6
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	q.transform = Transform3D(Basis(), land + Vector3.UP * 0.9)
	q.collision_mask = MASK
	q.exclude = exclude
	if not space.intersect_shape(q, 1).is_empty():
		return {}
	var top_y := p.y + top + 0.15
	# thick — толщина преграды: толстую, на которую можно встать, игрок не перелезает, а залезает (Climb)
	return {"p": p, "up": Vector3(p.x, top_y, p.z) + dir * maxf(0.0, d0 - 0.15), "over": Vector3(p.x, top_y, p.z) + dir * far,
		"land": land, "top": top, "thick": far - d0}


## Точка пути перелезания в доле t: плавная дуга (Катмулл — Ром через начало, край, дальний край
## и приземление), без «ступенек»: подъём плавно нарастает, спуск плавно гаснет. Время по длине
## участков, с мягким разгоном и торможением.
static func pos_at(path: Dictionary, t: float) -> Vector3:
	var p: Vector3 = path.p
	var up: Vector3 = path.up
	var over: Vector3 = path.over
	var land: Vector3 = path.land
	# начало подъёма — чуть дальше от преграды по ходу: тело идёт вперёд и вверх, а не в лифте
	var dir: Vector3 = Vector3(land.x - p.x, 0.0, land.z - p.z).normalized()
	var a: Vector3 = up - dir * 0.05
	var pts: Array[Vector3] = [p - dir * 0.6, p, a, over, land, land + dir * 0.6]
	var lens: Array[float] = [p.distance_to(a), a.distance_to(over), over.distance_to(land)]
	var total: float = lens[0] + lens[1] + lens[2]
	var e: float = clampf(t, 0.0, 1.0)
	e = lerpf(e, smoothstep(0.0, 1.0, e), 0.5)
	var d: float = e * total
	var seg: int = 0
	while seg < 2 and d > lens[seg]:
		d -= lens[seg]
		seg += 1
	var u: float = clampf(d / maxf(lens[seg], 0.001), 0.0, 1.0)
	var q: Vector3 = _catmull(pts[seg], pts[seg + 1], pts[seg + 2], pts[seg + 3], u)
	# дуга не проходит ниже верха преграды над ней
	if seg == 1:
		q.y = maxf(q.y, minf(up.y, over.y))
	return q


static func _catmull(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, u: float) -> Vector3:
	var u2: float = u * u
	var u3: float = u2 * u
	return 0.5 * ((2.0 * p1) + (-p0 + p2) * u + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3)


static func _ray(space: PhysicsDirectSpaceState3D, a: Vector3, b: Vector3, exclude: Array[RID]) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(a, b, MASK, exclude)
	return space.intersect_ray(q)


## Связки для ИИ по испечённому навмешу region: вдоль краёв (ребро только у одного полигона) —
## образцы, в сторону от полигона; перелезть можно и за преградой навмеш, а обход долгий — связка.
## Работает по кусочку за кадр (budget_ms), чтобы не было заминки в начале рейда. Возвращает,
## сколько поставлено (корутина — ждать через await).
static func build_links(region: NavigationRegion3D, parent: Node, budget_ms: int = 4) -> int:
	var nm := region.navigation_mesh
	if nm == null:
		return 0
	var space := region.get_world_3d().direct_space_state
	var map := region.get_world_3d().navigation_map
	var cfg: Dictionary = Balance.VAULT_LINKS
	var verts := nm.get_vertices()
	var xf := region.global_transform
	var edges := {}
	var centers := {}
	for i in range(nm.get_polygon_count()):
		var poly := nm.get_polygon(i)
		var c := Vector3.ZERO
		for vi in poly:
			c += verts[vi]
		c /= float(poly.size())
		for j in range(poly.size()):
			var a := poly[j]
			var b := poly[(j + 1) % poly.size()]
			var key := Vector2i(mini(a, b), maxi(a, b))
			edges[key] = int(edges.get(key, 0)) + 1
			centers[key] = c
	var made: Array[Vector3] = []
	var pairs: Array = []
	var count := 0
	var t0 := Time.get_ticks_msec()
	for key in edges:
		if int(edges[key]) != 1:
			continue
		if budget_ms > 0 and Time.get_ticks_msec() - t0 > budget_ms:
			await region.get_tree().process_frame
			if not is_instance_valid(region) or not region.is_inside_tree():
				return 0
			t0 = Time.get_ticks_msec()
		var a := xf * verts[key.x]
		var b := xf * verts[key.y]
		var e := b - a
		e.y = 0.0
		var len := e.length()
		if len < 0.3:
			continue
		var n := Vector3(-e.z, 0.0, e.x).normalized()
		var mid := (a + b) * 0.5
		var c: Vector3 = xf * (centers[key] as Vector3)
		if n.dot(mid - c) < 0.0:
			n = -n
		var samples := maxi(1, int(len / float(cfg.step)))
		for s in range(samples):
			var p := a.lerp(b, (float(s) + 0.5) / float(samples))
			var near := false
			for m in made:
				if m.distance_to(p) < float(cfg.spacing_m):
					near = true
					break
			if near:
				continue
			# навмеш висит над полом на пару см… до ячейки — встать на настоящий пол
			var fl := _ray(space, p + Vector3.UP * 0.5, p + Vector3.DOWN * 0.8, [])
			if fl.is_empty():
				continue
			p.y = float(fl.position.y)
			# навмеш отступает от преград на радиус агента — дотянуться чуть дальше
			var path := find(space, p, n, [], 1.2)
			if path.is_empty():
				continue
			var land: Vector3 = path.land
			var on := NavigationServer3D.map_get_closest_point(map, land)
			if Vector2(on.x - land.x, on.z - land.z).length() > 0.6 or absf(on.y - land.y) > 0.8:
				continue
			# обход короткий — связка не нужна
			var around := NavigationServer3D.map_get_path(map, p, on, true)
			var plen := 0.0
			for i in range(1, around.size()):
				plen += around[i - 1].distance_to(around[i])
			if not around.is_empty() and around[around.size() - 1].distance_to(on) < 0.5 and plen < float(cfg.detour_m):
				continue
			pairs.append([p, on])
			made.append(p)
			made.append(on)
	# все разом — карта навигации меняется один раз (иначе мародёры перестраивают путь на каждой)
	if not is_instance_valid(parent) or not parent.is_inside_tree():
		return 0
	for pr in pairs:
		var link := NavigationLink3D.new()
		link.name = "Vault_%d" % count
		link.bidirectional = true
		link.travel_cost = float(cfg.travel_cost)
		link.add_to_group(GROUP)
		link.set_meta("vault", true)
		parent.add_child(link)
		link.global_position = Vector3.ZERO
		link.start_position = pr[0]
		link.end_position = pr[1]
		count += 1
	return count
