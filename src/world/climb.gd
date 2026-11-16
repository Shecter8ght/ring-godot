class_name Climb
extends RefCounted
## Залезть наверх — на то, на чём можно стоять: машина, ящик, край платформы, крыша пристройки, площадка
## у верха лестницы (Ladder). Одна проверка для игрока, мародёров и лестниц; перелезть через — Vault.
##  find — от ног p в сторону dir: впереди (не дальше reach) стенка, её верх от VAULT.min_h до max_h над
##  ногами, наверху пол, на котором стоят (не круче FLOOR_DEG), ногам есть куда встать, телу хватает места
##  во весь рост или сидя, у стенки над головой свободно — есть куда подтянуться. Возвращает путь
##  {pts: [ноги, у стенки, на краю, наверху], land, top, crouch} или {}.
##  pos_at — точка пути в доле t: плавная кривая через точки пути (reverse — в обратную сторону,
##  linear — ровным ходом, без разгона и торможения).

## Круче — не пол, а скат (как floor_max_angle у CharacterBody3D по умолчанию).
const FLOOR_DEG := 45.0


static func find(space: PhysicsDirectSpaceState3D, p: Vector3, dir: Vector3, exclude: Array[RID] = [],
		max_h: float = -1.0, reach: float = -1.0) -> Dictionary:
	var c: Dictionary = Balance.CLIMB
	dir.y = 0.0
	if dir.length_squared() < 0.01:
		return {}
	dir = dir.normalized()
	var r := float(c.reach) if reach < 0.0 else reach
	var min_h := float(Balance.VAULT.min_h)
	var top_max := float(c.max_h) if max_h < 0.0 else max_h
	var radius := float(Balance.CAPSULE_RADIUS)
	var floor_y := cos(deg_to_rad(FLOOR_DEG))
	# 1. стенка впереди — лучами на нескольких высотах: у машины низ борта и верх на разном расстоянии;
	# ниже колена (бордюр) — не стенка, на неё шагают (STEP_UP)
	var d0 := INF
	var y := min_h - 0.05
	while y <= top_max - 0.05:
		var hit := Vault._ray(space, p + Vector3.UP * y, p + Vector3.UP * y + dir * r, exclude)
		if not hit.is_empty():
			d0 = minf(d0, Vector2(float(hit.position.x) - p.x, float(hit.position.z) - p.z).length())
		y += 0.3
	if d0 == INF:
		return {}
	# 2. выше досягаемого — стена, а не край
	var over_y := top_max + 0.3
	if not Vault._ray(space, p + Vector3.UP * over_y, p + Vector3.UP * over_y + dir * (d0 + 0.6), exclude).is_empty():
		return {}
	# 3. край: сверху вниз от стенки вглубь, пока не найдём пол (скаты кромки — борт машины — пропускаем);
	# lip — самое высокое место по дороге: через него переносят тело
	var low := p.y + min_h - 0.15
	var lip := -INF
	var stand_k := -1.0
	var k := d0 + 0.08
	while k <= d0 + 1.0:
		var h := _down(space, p + dir * k, p.y + over_y, low, exclude)
		if h.is_empty():
			# провал сразу за кромкой (тонкая стенка, за ней ниже) — не на что встать
			return {}
		lip = maxf(lip, float(h.position.y))
		if (h.normal as Vector3).y >= floor_y:
			# Первой горизонтальной грани может быть рамка окна: за ней пусто. Ищем дальше,
			# пока и центр тела, и точка впереди него не стоят на полу.
			var probe := p + dir * (k + radius + 0.05)
			var ph := _down(space, probe, p.y + over_y, low, exclude)
			var pf := _down(space, probe + dir * 0.25, p.y + over_y, low, exclude)
			if not ph.is_empty() and (ph.normal as Vector3).y >= floor_y and not pf.is_empty() \
				and absf(float(pf.position.y) - float(ph.position.y)) <= 0.3:
				stand_k = k
				break
		k += 0.1
	if stand_k < 0.0:
		return {}
	# 4. где встать: тело целиком за кромкой, под ногами пол на той же высоте и дальше — ещё на шаг
	var land := p + dir * (stand_k + radius + 0.05)
	var lh := _down(space, land, p.y + over_y, low, exclude)
	if lh.is_empty() or (lh.normal as Vector3).y < floor_y:
		return {}
	land.y = float(lh.position.y)
	if absf(land.y - lip) > 0.35 and land.y < lip:
		# за кромкой ниже, чем она сама (бортик, парапет) — это не площадка
		return {}
	var foot := _down(space, land + dir * 0.25, p.y + over_y, low, exclude)
	if foot.is_empty() or absf(float(foot.position.y) - land.y) > 0.3:
		return {}
	var top := land.y - p.y
	lip = maxf(lip, land.y)
	if top < min_h or top > top_max or lip - p.y > top_max + 0.1:
		return {}
	# 5. место наверху: во весь рост, иначе — сидя
	var crouch := false
	if _blocked(space, land, float(Balance.STANCE_HEIGHT.stand), radius, exclude):
		if _blocked(space, land, float(Balance.STANCE_HEIGHT.crouch), radius, exclude):
			return {}
		crouch = true
	# 6. подтянуться: на краю над кромкой — место хотя бы сидя (нет навеса, полки, потолка)
	var hang_d := maxf(0.0, d0 - radius - 0.05)
	var edge := p + dir * maxf(hang_d, d0 - 0.1)
	edge.y = lip + 0.06
	if _blocked(space, edge, float(Balance.STANCE_HEIGHT.crouch), radius, exclude):
		return {}
	var pts := PackedVector3Array([p])
	if top > 1.0:
		# высоко — сначала вверх у стенки (подтягивается), потом колени на край
		pts.append(Vector3(p.x, p.y + top * 0.55, p.z) + dir * hang_d)
	pts.append(edge)
	pts.append(land)
	return {"pts": pts, "land": land, "top": top, "crouch": crouch}


## Точка пути в доле t (0…1). Участки — по «усилию»: подтянуться вверх дольше, чем шагнуть вперёд или
## спрыгнуть вниз. Кривая плавная (Катмулл — Ром) и между точками не ныряет ниже нижней из них.
static func pos_at(path: Dictionary, t: float) -> Vector3:
	var pts: PackedVector3Array = path.pts
	if bool(path.get("reverse", false)):
		pts = pts.duplicate()
		pts.reverse()
	var n := pts.size()
	if n == 0:
		return Vector3.ZERO
	if n == 1:
		return pts[0]
	var e := clampf(t, 0.0, 1.0)
	if not bool(path.get("linear", false)):
		e = lerpf(e, smoothstep(0.0, 1.0, e), 0.6)
	var costs: Array[float] = []
	var total := 0.0
	for i in range(n - 1):
		var d := pts[i + 1] - pts[i]
		var cost := Vector2(d.x, d.z).length() + maxf(d.y, 0.0) * 1.6 + maxf(-d.y, 0.0) * 0.8 + 0.001
		costs.append(cost)
		total += cost
	var left := e * total
	var seg := 0
	while seg < n - 2 and left > costs[seg]:
		left -= costs[seg]
		seg += 1
	var u := clampf(left / costs[seg], 0.0, 1.0)
	var a: Vector3 = pts[seg]
	var b: Vector3 = pts[seg + 1]
	# на концах — продолжение крайнего участка: туда и оттуда тело идёт по прямой
	var before: Vector3 = pts[seg - 1] if seg > 0 else a * 2.0 - b
	var after: Vector3 = pts[seg + 2] if seg + 2 < n else b * 2.0 - a
	var q := Vault._catmull(before, a, b, after, u)
	q.y = maxf(q.y, minf(a.y, b.y))
	return q


static func _down(space: PhysicsDirectSpaceState3D, at: Vector3, from_y: float, to_y: float, exclude: Array[RID]) -> Dictionary:
	return Vault._ray(space, Vector3(at.x, from_y, at.z), Vector3(at.x, to_y, at.z), exclude)


## Тело ростом h (капсула игрока) на ногах в at во что-то упирается.
static func _blocked(space: PhysicsDirectSpaceState3D, at: Vector3, h: float, radius: float, exclude: Array[RID]) -> bool:
	var shape := CapsuleShape3D.new()
	shape.radius = radius
	shape.height = h
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = shape
	# чуть выше пола: выпуклая крыша машины не должна «задевать» низ капсулы
	q.transform = Transform3D(Basis(), at + Vector3.UP * (h * 0.5 + 0.08))
	q.collision_mask = Vault.MASK
	q.exclude = exclude
	return not space.intersect_shape(q, 1).is_empty()
