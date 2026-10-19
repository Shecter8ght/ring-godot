@tool
extends Node3D
## Сквер у ТЦ — парк (владелец, 2026-10-17: «лавочки, памятник, фонтан, ларьки с едой, карусели, колесо
## обозрения, больше деревьев, заборчики, интересные тропинки»). Данные — filler.park в
## data/blockouts/mall_study.json (tools/mall_study_park.py). Здесь — дорожки и площади плиткой, песок
## детской площадки, фонтан, колесо обозрения, кованая ограда; лавочки, ларьки, аттракционы, памятник —
## наборы наполнения (src/blockout/mall_filler.gd), деревья — MallLandscape.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const MallLandscape = preload("res://src/blockout/mall_landscape.gd")
const MallGround = preload("res://src/blockout/mall_ground.gd")

## Колесо обозрения: высота оси, радиус обода, число кабинок.
const WHEEL_HUB: float = 16.0
const WHEEL_R: float = 13.0
const WHEEL_CABINS: int = 16

var landscape: MallLandscape
var generated: Node3D


func _ready() -> void:
	landscape = get_node_or_null("../Landscape") as MallLandscape
	if landscape == null or landscape.plan.is_empty():
		return
	rebuild()


func rebuild() -> void:
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Park"
	add_child(generated)
	var park: Dictionary = (landscape.plan.get("filler", {}) as Dictionary).get("park", {}) as Dictionary
	if park.is_empty():
		return
	var g: RefCounted = Geometry.new(generated, _palette())
	for path: Dictionary in park.get("paths", []):
		landscape.drape_strip(g, MallLandscape.poly(path.points), float(path.width), "paving", 0.05)
	for plaza: Array in park.get("plazas", []):
		landscape.drape_disk(g, Vector2(float(plaza[0]), float(plaza[1])), float(plaza[2]), "paving", 0.055)
	var pg: Dictionary = park.get("playground", {}) as Dictionary
	if not pg.is_empty():
		landscape.drape_rect(g, Vector2(float(pg.at[0]), float(pg.at[1])), Vector2(float(pg.size[0]), float(pg.size[1])),
			float(pg.yaw), "sand", 0.06)
	var fountain: Array = park.get("fountain", [])
	if fountain.size() == 3:
		_fountain(g, Vector2(float(fountain[0]), float(fountain[1])), float(fountain[2]))
	var wheel: Array = park.get("wheel", [])
	if wheel.size() == 3:
		_wheel(g, Vector2(float(wheel[0]), float(wheel[1])), float(wheel[2]))
	for fence: Dictionary in park.get("fence", []):
		_fence(g, MallLandscape.poly(fence.points), float(fence.height), fence.get("gaps", []) as Array)
	g.finish()


func _palette() -> Dictionary:
	var result: Dictionary = Geometry.materials()
	var extra: Dictionary = {"paving": Color("a39a85"), "sand": Color("b3a37c"), "fence": Color("2c2f2c"),
		"wheel": Color("c9c6bd"), "cabin_a": Color("b8473b"), "cabin_b": Color("3f6d9e"), "cabin_c": Color("d2a63a")}
	for key: String in extra:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = extra[key]
		material.roughness = 0.85
		result[key] = material
	result["paving"] = MallGround.material("paving")
	# бортик фонтана, колонна, площадка колеса — бетон по граням (как стенки у земли)
	result["concrete"] = MallGround.concrete("wall")
	return result


## Фонтан: чаша с бортиком, вода, в середине — ступенчатая колонна с верхней чашей.
func _fountain(g: RefCounted, c: Vector2, r: float) -> void:
	var y: float = landscape.ground(c.x, c.y)
	var n: int = 24
	for i: int in range(n):
		var p: Vector2 = c + MallLandscape.polar(360.0 * float(i) / float(n), r)
		var q: Vector2 = c + MallLandscape.polar(360.0 * float(i + 1) / float(n), r)
		var mid: Vector2 = (p + q) * 0.5
		g.box(Vector3(mid.x, y + 0.35, mid.y), Vector3(p.distance_to(q) + 0.1, 0.7, 0.6), "concrete", true, -atan2((q - p).y, (q - p).x))
	for i: int in range(n):
		var p: Vector2 = c + MallLandscape.polar(360.0 * float(i) / float(n), r - 0.3)
		var q: Vector2 = c + MallLandscape.polar(360.0 * float(i + 1) / float(n), r - 0.3)
		g.tri(Vector3(c.x, y + 0.45, c.y), Vector3(p.x, y + 0.45, p.y), Vector3(q.x, y + 0.45, q.y), "water")
	g.box(Vector3(c.x, y + 1.0, c.y), Vector3(1.6, 2.0, 1.6), "concrete", true, PI * 0.25)
	for k: int in range(8):
		var p: Vector2 = c + MallLandscape.polar(45.0 * float(k), 1.6)
		g.box(Vector3(p.x, y + 2.1, p.y), Vector3(1.3, 0.25, 0.4), "concrete", false, -deg_to_rad(45.0 * float(k) + 90.0))
	g.box(Vector3(c.x, y + 2.9, c.y), Vector3(0.6, 1.4, 0.6), "concrete", false)


## Колесо обозрения: два обода на оси, спицы, опоры буквой «А» с обеих сторон, кабинки внизу обода;
## плоскость колеса — поперёк луча от центра ТЦ (к зданию — ребром), ориентир со всей карты.
func _wheel(g: RefCounted, c: Vector2, angle: float) -> void:
	var base: float = landscape.ground(c.x, c.y)
	var n: Vector3 = Vector3(cos(deg_to_rad(angle)), 0.0, sin(deg_to_rad(angle)))
	var t: Vector3 = Vector3(-n.z, 0.0, n.x)
	var hub: Vector3 = Vector3(c.x, base + WHEEL_HUB, c.y)
	var segments: int = 32
	for side: float in [-1.0, 1.0]:
		var o: Vector3 = n * side * 1.0
		var previous: Vector3 = hub + o + t * WHEEL_R
		for k: int in range(1, segments + 1):
			var th: float = TAU * float(k) / float(segments)
			var p: Vector3 = hub + o + t * WHEEL_R * cos(th) + Vector3.UP * WHEEL_R * sin(th)
			g.beam(previous, p, 0.28, 0.28, "wheel")
			if k % 2 == 0:
				g.beam(hub + o, p, 0.12, 0.12, "wheel")
			previous = p
		# опоры: от земли по обе стороны колеса к оси
		for leg: float in [-1.0, 1.0]:
			var foot: Vector3 = Vector3(c.x, 0.0, c.y) + t * leg * 8.5 + n * side * 3.2
			foot.y = landscape.ground(foot.x, foot.z)
			g.beam(foot, hub + n * side * 1.2, 0.5, 0.5, "steel", true)
	g.beam(hub - n * 1.6, hub + n * 1.6, 0.7, 0.7, "steel")
	# кабинки висят под ободом
	for k: int in range(WHEEL_CABINS):
		var th: float = TAU * float(k) / float(WHEEL_CABINS)
		var p: Vector3 = hub + t * WHEEL_R * cos(th) + Vector3.UP * (WHEEL_R * sin(th) - 1.3)
		var key: String = ["cabin_a", "cabin_b", "cabin_c"][k % 3]
		g.box(p, Vector3(1.6, 1.7, 1.4), key, false, -atan2(t.z, t.x))
		g.box(p + Vector3.UP * 1.0, Vector3(1.8, 0.12, 1.6), "wheel", false, -atan2(t.z, t.x))
	# площадка посадки у подножия
	g.box(Vector3(c.x, base + 0.3, c.y), Vector3(6.0, 0.6, 4.0), "concrete", true, -atan2(t.z, t.x))


## Кованая ограда: столбы через 2,5 м, тёмная решётка между ними, прорезь ворот; коллизия — тонкой полосой.
func _fence(g: RefCounted, line: PackedVector2Array, height: float, gaps: Array) -> void:
	for i: int in range(line.size() - 1):
		var a: Vector2 = line[i]
		var b: Vector2 = line[i + 1]
		var pieces: Array[Vector2] = [Vector2(0.0, 1.0)]
		for gap: Array in gaps:
			if int(gap[0]) != i:
				continue
			var rest: Array[Vector2] = []
			for piece: Vector2 in pieces:
				if float(gap[1]) > piece.x:
					rest.append(Vector2(piece.x, minf(piece.y, float(gap[1]))))
				if float(gap[2]) < piece.y:
					rest.append(Vector2(maxf(piece.x, float(gap[2])), piece.y))
			pieces = rest
		for piece: Vector2 in pieces:
			if piece.y - piece.x < 0.02:
				continue
			var p: Vector2 = a.lerp(b, piece.x)
			var q: Vector2 = a.lerp(b, piece.y)
			var yp: float = landscape.ground(p.x, p.y)
			var yq: float = landscape.ground(q.x, q.y)
			var mid: Vector2 = (p + q) * 0.5
			var ym: float = (yp + yq) * 0.5
			var yaw: float = -atan2((q - p).y, (q - p).x)
			g.box(Vector3(mid.x, ym + height * 0.5, mid.y), Vector3(p.distance_to(q), height - 0.15, 0.03), "fence", true, yaw)
			g.beam(Vector3(p.x, yp + height, p.y), Vector3(q.x, yq + height, q.y), 0.06, 0.06, "fence")
			g.box(Vector3(p.x, yp + height * 0.5 + 0.1, p.y), Vector3(0.12, height + 0.2, 0.12), "fence", false)
